"""
Settings Manager Service
=========================
Manages user settings with JSON file persistence.
Supports deep merging and default values.
"""

import copy
import json
import logging
import os
from typing import Any, Dict

logger = logging.getLogger(__name__)

# Default settings structure
DEFAULT_SETTINGS = {
    "auto_update": {
        "enabled": False,
        "check_interval_hours": 24,
        "check_time": "03:00",
        "auto_install": False
    },
    "notifications": {
        "update_available": True,
        "installation_complete": True
    },
    "display": {
        "theme": "dark",
        "refresh_interval_seconds": 5
    }
}


class SettingsManager:
    """Manage user settings with file-based persistence."""

    def __init__(self, settings_file: str = None):
        if settings_file is None:
            from config.settings import Config
            settings_file = Config.SETTINGS_FILE
        self._settings_file = settings_file
        self._ensure_data_dir()

    def get_all(self) -> Dict:
        """Load and return all settings, applying defaults for missing keys."""
        settings = self._load()
        merged = self._deep_merge(copy.deepcopy(DEFAULT_SETTINGS), settings)
        return merged

    def update(self, new_settings: Dict) -> Dict:
        """
        Deep-merge new settings into existing settings and persist.
        Returns the full updated settings dict.
        """
        self._validate(new_settings)
        current = self.get_all()
        merged = self._deep_merge(current, new_settings)
        self._save(merged)
        logger.info("Settings updated successfully")
        return merged

    def reset(self) -> Dict:
        """Reset settings to defaults and persist."""
        defaults = copy.deepcopy(DEFAULT_SETTINGS)
        self._save(defaults)
        logger.info("Settings reset to defaults")
        return defaults

    # ─── Private helpers ──────────────────────────────────────────────

    def _ensure_data_dir(self):
        """Create the data directory if it doesn't exist."""
        data_dir = os.path.dirname(self._settings_file)
        if data_dir and not os.path.exists(data_dir):
            try:
                os.makedirs(data_dir, exist_ok=True)
                logger.info(f"Created data directory: {data_dir}")
            except OSError as e:
                logger.error(f"Could not create data directory: {e}")

    def _load(self) -> Dict:
        """Load settings from the JSON file."""
        if not os.path.exists(self._settings_file):
            logger.info("Settings file not found, using defaults")
            return {}

        try:
            with open(self._settings_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error reading settings file: {e}")
            return {}

    def _save(self, settings: Dict):
        """Persist settings to the JSON file."""
        self._ensure_data_dir()
        try:
            with open(self._settings_file, 'w') as f:
                json.dump(settings, f, indent=2)
        except IOError as e:
            logger.error(f"Error writing settings file: {e}")
            raise

    @staticmethod
    def _deep_merge(base: Dict, override: Dict) -> Dict:
        """
        Recursively merge override into base.
        Override values take precedence; nested dicts are merged recursively.
        """
        result = base.copy()
        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = SettingsManager._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    @staticmethod
    def _validate(settings: Dict):
        """
        Basic validation of settings structure.
        Raises ValueError for invalid input.
        """
        if not isinstance(settings, dict):
            raise ValueError("Settings must be a JSON object")

        # Validate known keys
        if 'auto_update' in settings:
            au = settings['auto_update']
            if not isinstance(au, dict):
                raise ValueError("auto_update must be an object")
            if 'check_interval_hours' in au:
                val = au['check_interval_hours']
                if not isinstance(val, (int, float)) or val < 1:
                    raise ValueError("check_interval_hours must be >= 1")
            if 'check_time' in au:
                val = au['check_time']
                if not isinstance(val, str) or len(val) != 5 or ':' not in val:
                    raise ValueError("check_time must be in HH:MM format")

        if 'display' in settings:
            d = settings['display']
            if not isinstance(d, dict):
                raise ValueError("display must be an object")
            if 'theme' in d and d['theme'] not in ('dark', 'light'):
                raise ValueError("theme must be 'dark' or 'light'")
            if 'refresh_interval_seconds' in d:
                val = d['refresh_interval_seconds']
                if not isinstance(val, (int, float)) or val < 1:
                    raise ValueError("refresh_interval_seconds must be >= 1")
