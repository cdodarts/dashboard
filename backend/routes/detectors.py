"""Same-origin detector ownership API."""

from urllib.parse import urlsplit

from flask import Blueprint, jsonify, request
from services.detector_provider import DetectorError, manager

bp = Blueprint("detectors", __name__, url_prefix="/api/detectors")


def require_same_origin():
    # CLI clients omit browser headers. Browser mutations must originate at this host.
    if request.headers.get("Sec-Fetch-Site") not in (None, "same-origin", "none"):
        raise DetectorError("Detector changes require a same-origin request", 403)
    origin = request.headers.get("Origin")
    if origin:
        try:
            expected = urlsplit(request.host_url)
            actual = urlsplit(origin)
        except ValueError as exc:
            raise DetectorError("Detector changes require a same-origin request", 403) from exc
        if (actual.scheme, actual.netloc) != (expected.scheme, expected.netloc) or actual.path not in ("", "/"):
            raise DetectorError("Detector changes require a same-origin request", 403)


def switch_response(provider, restart=False):
    try:
        require_same_origin()
        return jsonify({"success": True, **manager.switch(provider, restart=restart)})
    except DetectorError as exc:
        return jsonify({"success": False, "error": str(exc)}), exc.status
    except OSError:
        return jsonify({"success": False, "error": "Detector state storage is unavailable"}), 503


def autodarts_install_guard_response():
    """Practical installer admission check; systemd enforces runtime exclusivity."""
    try:
        require_same_origin()
        state = manager.status()
        if state["selected"] == "cdo" or state["active"] in {"cdo", "conflict"}:
            raise DetectorError(
                "Select Autodarts on the dashboard before installing or updating Autodarts.", 409,
            )
    except DetectorError as exc:
        return jsonify({"success": False, "error": str(exc)}), exc.status
    return None


@bp.route("", methods=["GET"])
def get_detectors():
    try:
        return jsonify(manager.status())
    except DetectorError as exc:
        return jsonify({"error": str(exc)}), exc.status


@bp.route("/switch", methods=["POST"])
def switch_detector():
    try:
        require_same_origin()
    except DetectorError as exc:
        return jsonify({"success": False, "error": str(exc)}), exc.status
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"success": False, "error": "Expected a JSON object with provider"}), 400
    return switch_response(data.get("provider"))
