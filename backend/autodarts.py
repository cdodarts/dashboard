"""
Autodarts Management Routes — HTTP Proxy
==========================================
Backward-compatible /api/autodarts/* endpoints that proxy to the
autodarts-manager module API at http://127.0.0.1:9912/v1/*.

The dashboard no longer imports any code from autodarts-manager;
all communication is over HTTP via the module's own service.
"""

import logging
import requests as http_client
from flask import Blueprint, Response, jsonify, request

logger = logging.getLogger(__name__)
bp = Blueprint('autodarts', __name__, url_prefix='/api/autodarts')

MODULE_BASE = "http://127.0.0.1:9912/v1"
TIMEOUT = 60  # seconds — installs can take a while


def _proxy_get(path, params=None):
    """Forward a GET to the module and return its response."""
    try:
        resp = http_client.get(f"{MODULE_BASE}{path}", params=params, timeout=TIMEOUT)
        return Response(resp.content, status=resp.status_code,
                        content_type=resp.headers.get("Content-Type", "application/json"))
    except http_client.ConnectionError:
        return jsonify({"success": False, "error": "autodarts-manager service is not running"}), 502
    except Exception as e:
        logger.error(f"Proxy GET {path} failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


def _proxy_post(path, data=None):
    """Forward a POST to the module and return its response."""
    try:
        resp = http_client.post(f"{MODULE_BASE}{path}", json=data, timeout=TIMEOUT)
        return Response(resp.content, status=resp.status_code,
                        content_type=resp.headers.get("Content-Type", "application/json"))
    except http_client.ConnectionError:
        return jsonify({"success": False, "error": "autodarts-manager service is not running"}), 502
    except Exception as e:
        logger.error(f"Proxy POST {path} failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route('/status', methods=['GET'])
def get_status():
    return _proxy_get("/status")


@bp.route('/install', methods=['POST'])
def install():
    from routes.detectors import autodarts_install_guard_response
    guard = autodarts_install_guard_response()
    if guard is not None:
        return guard
    return _proxy_post("/install", request.get_json(silent=True))


@bp.route('/update', methods=['POST'])
def update():
    from routes.detectors import autodarts_install_guard_response
    guard = autodarts_install_guard_response()
    if guard is not None:
        return guard
    return _proxy_post("/update", request.get_json(silent=True))


@bp.route('/check-update', methods=['GET'])
def check_update():
    return _proxy_get("/check-update")


@bp.route('/service/start', methods=['POST'])
def start_service():
    from routes.detectors import switch_response
    return switch_response("autodarts")


@bp.route('/service/stop', methods=['POST'])
def stop_service():
    return _proxy_post("/service/stop")


@bp.route('/service/restart', methods=['POST'])
def restart_service():
    from routes.detectors import switch_response
    return switch_response("autodarts", restart=True)


@bp.route('/logs', methods=['GET'])
def get_logs():
    lines = request.args.get('lines', 50, type=int)
    return _proxy_get("/logs", params={"lines": lines})
