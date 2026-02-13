"""
Scheduler Service
==================
Manages background tasks using Flask-APScheduler.
Handles auto-update checks based on user settings.
"""

import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

AUTO_UPDATE_JOB_ID = 'autodarts_auto_update_check'


class SchedulerService:
    """Manage background scheduled tasks."""

    def __init__(self, scheduler):
        self._scheduler = scheduler

    def register_auto_update_job(self):
        """
        Register (or re-register) the auto-update check job
        based on current user settings.
        """
        from services.settings_manager import SettingsManager

        settings_manager = SettingsManager()
        settings = settings_manager.get_all()
        auto_update = settings.get('auto_update', {})

        # Remove existing job if present
        self._remove_job(AUTO_UPDATE_JOB_ID)

        if not auto_update.get('enabled', False):
            logger.info("Auto-update is disabled; no scheduled job registered")
            return

        interval_hours = auto_update.get('check_interval_hours', 24)

        try:
            self._scheduler.add_job(
                id=AUTO_UPDATE_JOB_ID,
                func=_auto_update_check_task,
                trigger='interval',
                hours=interval_hours,
                misfire_grace_time=900,  # 15 minutes
                replace_existing=True,
            )
            logger.info(
                f"Auto-update check job registered: every {interval_hours} hours"
            )
        except Exception as e:
            logger.error(f"Failed to register auto-update job: {e}")

    def _remove_job(self, job_id: str):
        """Safely remove a scheduled job by ID."""
        try:
            self._scheduler.remove_job(job_id)
            logger.debug(f"Removed scheduled job: {job_id}")
        except Exception:
            pass  # Job may not exist yet


def _auto_update_check_task():
    """
    Background task: check for Autodarts updates and optionally install.
    This function runs inside the scheduler context.
    """
    logger.info("Running auto-update check...")

    try:
        from services.autodarts_manager import AutodartsManagerService
        from services.settings_manager import SettingsManager

        settings = SettingsManager().get_all()
        auto_update = settings.get('auto_update', {})

        if not auto_update.get('enabled', False):
            logger.info("Auto-update is disabled, skipping check")
            return

        manager = AutodartsManagerService()
        if not manager.available:
            logger.warning("Autodarts manager not available, skipping update check")
            return

        result = manager.check_update()
        update_available = result.get('update_available', False)

        if update_available:
            latest = result.get('latest_version', 'unknown')
            current = result.get('current_version', 'unknown')
            logger.info(
                f"Autodarts update available: {current} -> {latest}"
            )

            if auto_update.get('auto_install', False):
                logger.info("Auto-install enabled, installing update...")
                install_result = manager.update()
                if install_result.get('success'):
                    logger.info("Autodarts auto-update completed successfully")
                else:
                    logger.error(
                        f"Autodarts auto-update failed: {install_result.get('error')}"
                    )
            else:
                logger.info("Auto-install disabled; update available but not installing")
        else:
            logger.info("No Autodarts update available")

    except Exception as e:
        logger.error(f"Error in auto-update check task: {e}")
