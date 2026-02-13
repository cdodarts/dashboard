"""Settings management routes.
===========================
API endpoints for managing user settings.
"""

import logging
from flask import Blueprint, jsonify, request
from services.settings_manager import SettingsManager

logger = logging.getLogger(__name__)
bp = Blueprint('settings', __name__, url_prefix='/api/settings')

# Shared service instance
settings_manager = SettingsManager()


@bp.route('', methods=['GET'])
def get_all_settings():
    """Get all user settings."""
    try:
        settings = settings_manager.get_all()
        return jsonify(settings)
    except Exception as e:
        logger.error(f"Error getting settings: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('', methods=['POST'])
def update_settings():
    """Update all or partial settings (deep merge with existing)."""
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({'success': False, 'error': 'No JSON data provided'}), 400

        updated = settings_manager.update(data)
        return jsonify({'success': True, 'settings': updated})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error updating settings: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/auto-update', methods=['GET'])
def get_auto_update_settings():
    """Get auto-update settings only."""
    try:
        settings = settings_manager.get_all()
        return jsonify(settings.get('auto_update', {}))
    except Exception as e:
        logger.error(f"Error getting auto-update settings: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/auto-update', methods=['POST'])
def update_auto_update_settings():
    """Update auto-update settings."""
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({'success': False, 'error': 'No JSON data provided'}), 400

        updated = settings_manager.update({'auto_update': data})

        # Trigger scheduler update
        _notify_scheduler_update()

        return jsonify({'success': True, 'auto_update': updated.get('auto_update', {})})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error updating auto-update settings: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/reset', methods=['POST'])
def reset_settings():
    """Reset all settings to defaults."""
    try:
        defaults = settings_manager.reset()
        _notify_scheduler_update()
        return jsonify({'success': True, 'settings': defaults})
    except Exception as e:
        logger.error(f"Error resetting settings: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


def _notify_scheduler_update():
    """Notify the scheduler that settings have changed."""
    try:
        from services.scheduler import SchedulerService
        from app import scheduler
        sched_service = SchedulerService(scheduler)
        sched_service.register_auto_update_job()
        logger.info("Scheduler updated after settings change")
    except Exception as e:
        logger.warning(f"Could not update scheduler: {e}")
