"""
Application Configuration
=========================
Central configuration for the Flask application.
"""

import os


class Config:
    """Flask application configuration."""

    # Flask core settings
    SECRET_KEY = os.environ.get('SECRET_KEY', 'cdo-vertex-dashboard-secret-key')
    DEBUG = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'

    # Scheduler settings
    SCHEDULER_API_ENABLED = True
    SCHEDULER_TIMEZONE = "UTC"
    SCHEDULER_JOB_DEFAULTS = {
        'misfire_grace_time': 900  # 15 minutes
    }

    # Application paths
    BASE_DIR = os.environ.get(
        'CDO_VERTEX_BASE_DIR',
        '/opt/cdo-vertex-dashboard'
    )
    DATA_DIR = os.path.join(BASE_DIR, 'data')
    SETTINGS_FILE = os.path.join(DATA_DIR, 'settings.json')

    # Autodarts manager path
    AUTODARTS_MANAGER_PATH = os.environ.get(
        'AUTODARTS_MANAGER_PATH',
        '/opt/autodarts-manager'
    )

    # Server settings
    HOST = '0.0.0.0'
    PORT = 5001
