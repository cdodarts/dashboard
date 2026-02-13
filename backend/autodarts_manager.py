"""
Autodarts Manager Service
==========================
Integrates with /opt/autodarts-manager to manage
Autodarts installation, updates, and service lifecycle.
"""

import logging
import subprocess
import sys
import os
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Attempt to import the AutodartsInstaller from the existing installation
_autodarts_installer = None
_import_error = None

try:
    autodarts_manager_path = os.environ.get(
        'AUTODARTS_MANAGER_PATH', '/opt/autodarts-manager'
    )
    if autodarts_manager_path not in sys.path:
        sys.path.insert(0, autodarts_manager_path)
    from scripts.autodarts_installer import AutodartsInstaller
    _autodarts_installer = AutodartsInstaller
    logger.info("AutodartsInstaller imported successfully")
except ImportError as e:
    _import_error = str(e)
    logger.warning(f"Could not import AutodartsInstaller: {e}")


class AutodartsManagerService:
    """Service for managing Autodarts via autodarts-manager."""

    def __init__(self):
        self._installer = None
        if _autodarts_installer is not None:
            try:
                self._installer = _autodarts_installer()
            except Exception as e:
                logger.error(f"Failed to instantiate AutodartsInstaller: {e}")

    @property
    def available(self) -> bool:
        """Check if the autodarts-manager integration is available."""
        return self._installer is not None

    def get_status(self) -> Dict:
        """
        Get installation status, version, and service state.
        Returns a consistent status dict even if autodarts-manager is unavailable.
        """
        if not self.available:
            return self._unavailable_response()

        try:
            installed = self._installer.is_installed() if hasattr(self._installer, 'is_installed') else False
            version = None
            active = False
            enabled = False
            service_status = 'unknown'
            update_available = False
            latest_version = None

            if installed:
                if hasattr(self._installer, 'get_installed_version'):
                    version = self._installer.get_installed_version()
                if hasattr(self._installer, 'is_service_active'):
                    active = self._installer.is_service_active()
                if hasattr(self._installer, 'is_service_enabled'):
                    enabled = self._installer.is_service_enabled()

                service_status = 'running' if active else 'stopped'

                try:
                    if hasattr(self._installer, 'get_latest_version'):
                        latest_version = self._installer.get_latest_version()
                    if version and latest_version:
                        update_available = latest_version != version
                except Exception:
                    pass

            return {
                'installed': installed,
                'version': version,
                'active': active,
                'enabled': enabled,
                'status': service_status,
                'update_available': update_available,
                'latest_version': latest_version,
                'manager_available': True,
            }
        except Exception as e:
            logger.error(f"Error getting Autodarts status: {e}")
            return {
                'installed': False,
                'version': None,
                'active': False,
                'enabled': False,
                'status': 'error',
                'update_available': False,
                'latest_version': None,
                'manager_available': True,
                'error': str(e),
            }

    def install(self, version: Optional[str] = None, enable_autostart: bool = True) -> Dict:
        """Install Autodarts."""
        if not self.available:
            return self._unavailable_response()

        try:
            kwargs = {}
            if version:
                kwargs['version'] = version
            if hasattr(self._installer, 'install'):
                self._installer.install(**kwargs)
            if enable_autostart and hasattr(self._installer, 'enable_service'):
                self._installer.enable_service()

            return {'success': True, 'message': 'Autodarts installed successfully'}
        except Exception as e:
            logger.error(f"Error installing Autodarts: {e}")
            return {'success': False, 'error': str(e)}

    def update(self, version: Optional[str] = None) -> Dict:
        """Update Autodarts to latest or specific version."""
        if not self.available:
            return self._unavailable_response()

        try:
            kwargs = {}
            if version:
                kwargs['version'] = version
            if hasattr(self._installer, 'update'):
                self._installer.update(**kwargs)
            elif hasattr(self._installer, 'install'):
                self._installer.install(**kwargs)

            return {'success': True, 'message': 'Autodarts updated successfully'}
        except Exception as e:
            logger.error(f"Error updating Autodarts: {e}")
            return {'success': False, 'error': str(e)}

    def check_update(self) -> Dict:
        """Check if an update is available."""
        if not self.available:
            return self._unavailable_response()

        try:
            current = None
            latest = None

            if hasattr(self._installer, 'get_installed_version'):
                current = self._installer.get_installed_version()
            if hasattr(self._installer, 'get_latest_version'):
                latest = self._installer.get_latest_version()

            update_available = (
                current is not None
                and latest is not None
                and current != latest
            )

            return {
                'update_available': update_available,
                'current_version': current,
                'latest_version': latest,
            }
        except Exception as e:
            logger.error(f"Error checking for updates: {e}")
            return {'success': False, 'error': str(e)}

    def start_service(self) -> Dict:
        """Start the Autodarts service."""
        return self._manage_service('start')

    def stop_service(self) -> Dict:
        """Stop the Autodarts service."""
        return self._manage_service('stop')

    def restart_service(self) -> Dict:
        """Restart the Autodarts service."""
        return self._manage_service('restart')

    def get_logs(self, lines: int = 50) -> Dict:
        """Get the last N lines of Autodarts service logs."""
        try:
            output = subprocess.check_output(
                ['journalctl', '-u', 'autodarts', '-n', str(lines), '--no-pager'],
                stderr=subprocess.STDOUT,
                timeout=10
            ).decode('utf-8', errors='replace')

            return {
                'success': True,
                'lines': lines,
                'logs': output,
            }
        except FileNotFoundError:
            return {'success': False, 'error': 'journalctl not found'}
        except subprocess.SubprocessError as e:
            logger.error(f"Error getting logs: {e}")
            return {'success': False, 'error': str(e)}

    # ─── Private helpers ──────────────────────────────────────────────

    def _manage_service(self, action: str) -> Dict:
        """Start, stop, or restart the Autodarts service."""
        if not self.available:
            return self._unavailable_response()

        method_name = f'{action}_service'
        try:
            if hasattr(self._installer, method_name):
                getattr(self._installer, method_name)()
            else:
                subprocess.check_call(
                    ['sudo', 'systemctl', action, 'autodarts'],
                    timeout=30
                )
            return {'success': True, 'message': f'Autodarts service {action}ed'}
        except Exception as e:
            logger.error(f"Error {action}ing service: {e}")
            return {'success': False, 'error': str(e)}

    @staticmethod
    def _unavailable_response() -> Dict:
        """Standard response when autodarts-manager is not available."""
        return {
            'success': False,
            'error': 'autodarts-manager is not installed or not accessible',
            'manager_available': False,
            'import_error': _import_error,
        }
