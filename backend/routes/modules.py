"""
Module Discovery & Proxy Routes
=================================
Generic endpoints that let the dashboard frontend discover installed
modules, check their health, proxy arbitrary requests, reload the
registry, and trigger a factory reset across every module.

No module-specific logic lives here — the registry files and each
module's own API provide all the detail.
"""

import logging
from flask import Blueprint, Response, jsonify, request
from services.registry import ModuleRegistry

logger = logging.getLogger(__name__)

bp = Blueprint("modules", __name__, url_prefix="/api")

# Shared registry instance — loaded once at import time, can be
# refreshed via POST /api/modules/reload.
registry = ModuleRegistry()


# ─────────────────────────────────────────────────────────────────────────
# Module discovery
# ─────────────────────────────────────────────────────────────────────────

@bp.route("/modules", methods=["GET"])
def list_modules():
    """List every registered module with live health status."""
    try:
        modules = registry.get_all_with_health()
        return jsonify({"modules": modules})
    except Exception as e:
        logger.error(f"Error listing modules: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route("/modules/reload", methods=["POST"])
def reload_registry():
    """Re-scan /etc/cdo/modules.d/ for registry files."""
    registry.reload()
    return jsonify({
        "message": "Registry reloaded",
        "module_count": len(registry.list_modules()),
    })


@bp.route("/modules/<module_name>/health", methods=["GET"])
def module_health(module_name):
    """Probe a single module's health endpoint."""
    result = registry.probe_health(module_name)
    return jsonify(result)


# ─────────────────────────────────────────────────────────────────────────
# Generic proxy  — forwards ANY request to a module API
# ─────────────────────────────────────────────────────────────────────────

@bp.route("/modules/<module_name>/<path:path>", methods=["GET", "POST", "PUT", "DELETE"])
def proxy_to_module(module_name, path):
    """
    Transparent proxy: the dashboard frontend can call

        /api/modules/autodarts-manager/v1/status

    and this will forward to http://127.0.0.1:9912/v1/status.
    """
    module = registry.get_module(module_name)
    if module is None:
        return jsonify({"error": f"Module '{module_name}' not found"}), 404

    data = (
        request.get_json(silent=True)
        if request.method in ("POST", "PUT")
        else None
    )

    resp = registry.proxy(
        module_name=module_name,
        path=path,
        method=request.method,
        data=data,
        params=request.args.to_dict(),
    )

    if resp is None:
        return jsonify({"error": f"Module '{module_name}' is not responding"}), 502

    # Return the module's response as-is
    return Response(
        response=resp.content,
        status=resp.status_code,
        content_type=resp.headers.get("Content-Type", "application/json"),
    )


# ─────────────────────────────────────────────────────────────────────────
# Factory reset — calls /v1/reset on every registered module then
#                 resets the dashboard's own settings.
# ─────────────────────────────────────────────────────────────────────────

@bp.route("/factory-reset", methods=["POST"])
def factory_reset():
    """
    Reset the entire device to factory defaults.

    For each registered module the dashboard POSTs to its ``reset``
    endpoint.  Each module owns its own cleanup logic so the dashboard
    never needs module-specific code.
    """
    results = {}

    for module in registry.list_modules():
        name = module["name"]
        reset_path = module.get("endpoints", {}).get("reset", "/v1/reset")

        resp = registry.proxy(name, reset_path, method="POST")
        if resp is not None and resp.status_code == 200:
            try:
                results[name] = resp.json()
            except ValueError:
                results[name] = {"success": True}
        elif resp is not None:
            results[name] = {"success": False, "error": f"HTTP {resp.status_code}"}
        else:
            results[name] = {"success": False, "error": "Module not responding"}

    # Reset dashboard's own settings
    try:
        from settings_manager import SettingsManager
        settings = SettingsManager()
        settings.reset()
        results["dashboard"] = {"success": True, "message": "Settings reset to defaults"}
    except Exception as e:
        results["dashboard"] = {"success": False, "error": str(e)}

    all_ok = all(r.get("success", False) for r in results.values())
    return jsonify({
        "success": all_ok,
        "message": "Factory reset complete" if all_ok else "Factory reset completed with errors",
        "results": results,
    })
