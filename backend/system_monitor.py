"""
System Monitor Service
======================
Collects system metrics: CPU, memory, disk, temperature,
network, WiFi, uptime, and hostname.
"""

import logging
import platform
import socket
import subprocess
import time
import re
import os
from datetime import datetime
from typing import Dict, Optional

import psutil

logger = logging.getLogger(__name__)


class SystemMonitor:
    """Monitor system resources and status on a Raspberry Pi."""

    # Temperature thresholds (Celsius)
    TEMP_THRESHOLDS = {
        'normal': 60.0,
        'warm': 70.0,
        'hot': 80.0,
        # Above 80 is critical
    }

    # WiFi signal quality thresholds (dBm)
    WIFI_THRESHOLDS = {
        'excellent': -50,
        'good': -60,
        'fair': -70,
        # Below -70 is poor
    }

    def get_system_status(self) -> Dict:
        """Get comprehensive system status overview."""
        return {
            'cpu': self.get_cpu_info(),
            'memory': self.get_memory_info(),
            'disk': self.get_disk_info(),
            'temperature': self.get_temperature(),
            'wifi': self.get_wifi_info(),
            'network': self.get_network_info(),
            'uptime': self.get_uptime_info(),
            'hostname': self.get_hostname(),
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }

    def get_cpu_info(self) -> Dict:
        """Get CPU usage information."""
        try:
            freq = psutil.cpu_freq()
            return {
                'usage_percent': psutil.cpu_percent(interval=0.5),
                'core_count': psutil.cpu_count(logical=True),
                'physical_cores': psutil.cpu_count(logical=False),
                'frequency_mhz': round(freq.current, 1) if freq else None,
                'frequency_min_mhz': round(freq.min, 1) if freq and freq.min else None,
                'frequency_max_mhz': round(freq.max, 1) if freq and freq.max else None,
            }
        except Exception as e:
            logger.error(f"Error collecting CPU info: {e}")
            return {'error': str(e)}

    def get_memory_info(self) -> Dict:
        """Get memory usage information."""
        try:
            mem = psutil.virtual_memory()
            return {
                'total_mb': round(mem.total / (1024 * 1024), 1),
                'used_mb': round(mem.used / (1024 * 1024), 1),
                'available_mb': round(mem.available / (1024 * 1024), 1),
                'percent': mem.percent,
            }
        except Exception as e:
            logger.error(f"Error collecting memory info: {e}")
            return {'error': str(e)}

    def get_disk_info(self) -> Dict:
        """Get disk usage information for the root partition."""
        try:
            disk = psutil.disk_usage('/')
            return {
                'total_gb': round(disk.total / (1024 ** 3), 2),
                'used_gb': round(disk.used / (1024 ** 3), 2),
                'free_gb': round(disk.free / (1024 ** 3), 2),
                'percent': disk.percent,
            }
        except Exception as e:
            logger.error(f"Error collecting disk info: {e}")
            return {'error': str(e)}

    def get_temperature(self) -> Dict:
        """
        Get system temperature. Tries vcgencmd first (Raspberry Pi),
        then falls back to psutil sensors, then to thermal zone files.
        """
        temp_c = self._read_vcgencmd_temp()

        if temp_c is None:
            temp_c = self._read_psutil_temp()

        if temp_c is None:
            temp_c = self._read_thermal_zone()

        if temp_c is not None:
            temp_f = round(temp_c * 9.0 / 5.0 + 32, 1)
            status = self._classify_temperature(temp_c)
            return {
                'celsius': round(temp_c, 1),
                'fahrenheit': temp_f,
                'status': status,
            }

        return {
            'celsius': None,
            'fahrenheit': None,
            'status': 'unavailable',
            'error': 'Temperature sensor not available'
        }

    def get_network_info(self) -> Dict:
        """Get network interfaces and traffic statistics."""
        try:
            addrs = psutil.net_if_addrs()
            counters = psutil.net_io_counters(pernic=True)
            interfaces = {}

            for iface, addr_list in addrs.items():
                if iface == 'lo':
                    continue  # Skip loopback

                iface_info = {'addresses': []}
                for addr in addr_list:
                    if addr.family == socket.AF_INET:
                        iface_info['addresses'].append({
                            'type': 'ipv4',
                            'address': addr.address,
                            'netmask': addr.netmask,
                        })

                if iface in counters:
                    c = counters[iface]
                    iface_info['bytes_sent'] = c.bytes_sent
                    iface_info['bytes_recv'] = c.bytes_recv

                interfaces[iface] = iface_info

            return {'interfaces': interfaces}
        except Exception as e:
            logger.error(f"Error collecting network info: {e}")
            return {'error': str(e)}

    def get_wifi_info(self) -> Dict:
        """Get WiFi signal strength and quality using iwconfig or iw."""
        ssid = self._read_wifi_ssid()
        signal_dbm = self._read_iwconfig_signal()
        signal_percent = None

        if signal_dbm is None:
            signal_dbm = self._read_iw_signal()

        if signal_dbm is None:
            nmcli_signal, nmcli_ssid = self._read_nmcli_wifi_info()
            if ssid is None:
                ssid = nmcli_ssid
            signal_percent = nmcli_signal

        if signal_dbm is not None:
            percent = self._dbm_to_percent(signal_dbm)
            quality = self._classify_wifi_quality(signal_dbm)
            return {
                'connected': True,
                'ssid': ssid,
                'signal_dbm': signal_dbm,
                'signal_percent': percent,
                'quality': quality,
            }

        if signal_percent is not None:
            quality = self._classify_wifi_quality(self._percent_to_dbm(signal_percent))
            return {
                'connected': True,
                'ssid': ssid,
                'signal_dbm': None,
                'signal_percent': signal_percent,
                'quality': quality,
            }

        return {
            'connected': False,
            'ssid': ssid,
            'signal_dbm': None,
            'signal_percent': 0,
            'quality': 'disconnected',
        }

    def get_uptime_info(self) -> Dict:
        """Get system uptime information."""
        try:
            boot_time = psutil.boot_time()
            uptime_seconds = time.time() - boot_time
            return {
                'boot_time': datetime.fromtimestamp(boot_time).isoformat(),
                'uptime_seconds': int(uptime_seconds),
                'uptime_formatted': self._format_uptime(int(uptime_seconds)),
            }
        except Exception as e:
            logger.error(f"Error collecting uptime info: {e}")
            return {'error': str(e)}

    def get_hostname(self) -> Dict:
        """Get system hostname."""
        try:
            return {
                'hostname': socket.gethostname(),
                'platform': platform.system(),
                'architecture': platform.machine(),
            }
        except Exception as e:
            logger.error(f"Error collecting hostname: {e}")
            return {'error': str(e)}

    # ─── Private helper methods ───────────────────────────────────────

    def _read_vcgencmd_temp(self) -> Optional[float]:
        """Read temperature via Raspberry Pi vcgencmd."""
        try:
            output = subprocess.check_output(
                ['vcgencmd', 'measure_temp'],
                stderr=subprocess.DEVNULL,
                timeout=5
            ).decode('utf-8').strip()
            # Parse "temp=42.8'C"
            match = re.search(r'temp=([\d.]+)', output)
            if match:
                return float(match.group(1))
        except (FileNotFoundError, subprocess.SubprocessError):
            pass
        return None

    def _read_psutil_temp(self) -> Optional[float]:
        """Read temperature via psutil sensors."""
        try:
            temps = psutil.sensors_temperatures()
            if not temps:
                return None
            for name in ('cpu_thermal', 'cpu-thermal', 'coretemp', 'soc_thermal'):
                if name in temps and temps[name]:
                    return temps[name][0].current
            # Fallback: first available sensor
            first_key = next(iter(temps))
            if temps[first_key]:
                return temps[first_key][0].current
        except (AttributeError, StopIteration):
            pass
        return None

    def _read_thermal_zone(self) -> Optional[float]:
        """Read temperature from /sys/class/thermal/thermal_zone0."""
        try:
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                return int(f.read().strip()) / 1000.0
        except (FileNotFoundError, ValueError, PermissionError):
            return None

    def _classify_temperature(self, temp_c: float) -> str:
        """Classify temperature status."""
        if temp_c < self.TEMP_THRESHOLDS['normal']:
            return 'normal'
        elif temp_c < self.TEMP_THRESHOLDS['warm']:
            return 'warm'
        elif temp_c < self.TEMP_THRESHOLDS['hot']:
            return 'hot'
        return 'critical'

    def _read_iwconfig_signal(self) -> Optional[int]:
        """Read WiFi signal strength via iwconfig."""
        try:
            output = subprocess.check_output(
                ['iwconfig'],
                stderr=subprocess.DEVNULL,
                timeout=5
            ).decode('utf-8')
            match = re.search(r'Signal level[=:](-?\d+)\s*dBm', output)
            if match:
                return int(match.group(1))
        except (FileNotFoundError, subprocess.SubprocessError):
            pass
        return None

    def _read_wifi_ssid(self) -> Optional[str]:
        """Read the connected WiFi SSID via iwgetid or iw."""
        try:
            output = subprocess.check_output(
                ['iwgetid', '-r'],
                stderr=subprocess.DEVNULL,
                timeout=5
            ).decode('utf-8').strip()
            if output:
                return output
        except (FileNotFoundError, subprocess.SubprocessError):
            pass

        try:
            interface = self._get_wifi_interface()
            output = subprocess.check_output(
                ['iw', 'dev', interface, 'link'],
                stderr=subprocess.DEVNULL,
                timeout=5
            ).decode('utf-8')
            match = re.search(r'SSID:\s*(.+)', output)
            if match:
                return match.group(1).strip()
        except (FileNotFoundError, subprocess.SubprocessError):
            pass

        return None

    def _read_iw_signal(self) -> Optional[int]:
        """Read WiFi signal strength via iw (fallback)."""
        try:
            interface = self._get_wifi_interface()
            output = subprocess.check_output(
                ['iw', 'dev', interface, 'link'],
                stderr=subprocess.DEVNULL,
                timeout=5
            ).decode('utf-8')
            match = re.search(r'signal:\s*(-?\d+)\s*dBm', output)
            if match:
                return int(match.group(1))
        except (FileNotFoundError, subprocess.SubprocessError):
            pass
        return None

    def _read_nmcli_wifi_info(self) -> (Optional[int], Optional[str]):
        """Read WiFi signal percent and SSID via nmcli."""
        try:
            output = subprocess.check_output(
                ['nmcli', '-t', '-f', 'IN-USE,SSID,SIGNAL', 'dev', 'wifi'],
                stderr=subprocess.DEVNULL,
                timeout=5
            ).decode('utf-8')
            for line in output.splitlines():
                if line.startswith('*:'):
                    parts = line.split(':', 2)
                    if len(parts) == 3:
                        ssid = parts[1] or None
                        try:
                            signal = int(parts[2])
                        except ValueError:
                            signal = None
                        return signal, ssid
        except (FileNotFoundError, subprocess.SubprocessError):
            pass
        return None, None

    @staticmethod
    def _percent_to_dbm(percent: int) -> int:
        """Convert signal percent to an approximate dBm value."""
        percent = max(0, min(100, percent))
        return int((percent / 2) - 100)

    @staticmethod
    def _get_wifi_interface() -> str:
        """Get WiFi interface name from environment."""
        return os.environ.get('WIFI_INTERFACE', 'wlan0')

    @staticmethod
    def _dbm_to_percent(dbm: int) -> int:
        """Convert dBm to signal strength percentage (0-100)."""
        if dbm >= -50:
            return 100
        elif dbm <= -100:
            return 0
        return 2 * (dbm + 100)

    def _classify_wifi_quality(self, dbm: int) -> str:
        """Classify WiFi signal quality."""
        if dbm >= self.WIFI_THRESHOLDS['excellent']:
            return 'excellent'
        elif dbm >= self.WIFI_THRESHOLDS['good']:
            return 'good'
        elif dbm >= self.WIFI_THRESHOLDS['fair']:
            return 'fair'
        return 'poor'

    @staticmethod
    def _format_uptime(seconds: int) -> str:
        """Format uptime seconds to a human-readable string."""
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        minutes = (seconds % 3600) // 60

        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        parts.append(f"{minutes}m")

        return ' '.join(parts)
