"""
System Monitoring Routes
========================
API endpoints for system resource monitoring.
"""

import logging
from flask import Blueprint, jsonify
from services.system_monitor import SystemMonitor

logger = logging.getLogger(__name__)
bp = Blueprint('system', __name__, url_prefix='/api/system')

# Shared service instance
monitor = SystemMonitor()


@bp.route('/status', methods=['GET'])
def get_system_status():
    """Get comprehensive system status overview."""
    try:
        status = monitor.get_system_status()
        return jsonify(status)
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/cpu', methods=['GET'])
def get_cpu_info():
    """Get CPU usage information."""
    try:
        return jsonify(monitor.get_cpu_info())
    except Exception as e:
        logger.error(f"Error getting CPU info: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/memory', methods=['GET'])
def get_memory_info():
    """Get memory usage information."""
    try:
        return jsonify(monitor.get_memory_info())
    except Exception as e:
        logger.error(f"Error getting memory info: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/disk', methods=['GET'])
def get_disk_info():
    """Get disk usage information."""
    try:
        return jsonify(monitor.get_disk_info())
    except Exception as e:
        logger.error(f"Error getting disk info: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/temperature', methods=['GET'])
def get_temperature():
    """Get system temperature (Raspberry Pi specific)."""
    try:
        return jsonify(monitor.get_temperature())
    except Exception as e:
        logger.error(f"Error getting temperature: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/network', methods=['GET'])
def get_network_info():
    """Get network interfaces and statistics."""
    try:
        return jsonify(monitor.get_network_info())
    except Exception as e:
        logger.error(f"Error getting network info: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/wifi', methods=['GET'])
def get_wifi_info():
    """Get WiFi signal strength and quality."""
    try:
        return jsonify(monitor.get_wifi_info())
    except Exception as e:
        logger.error(f"Error getting WiFi info: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/uptime', methods=['GET'])
def get_uptime():
    """Get system uptime information."""
    try:
        return jsonify(monitor.get_uptime_info())
    except Exception as e:
        logger.error(f"Error getting uptime info: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/hostname', methods=['GET'])
def get_hostname():
    """Get system hostname."""
    try:
        return jsonify(monitor.get_hostname())
    except Exception as e:
        logger.error(f"Error getting hostname: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
