"""
Module Registry Service
========================
Reads /etc/cdo/modules.d/*.json to discover installed modules,
probes their health endpoints, and provides an HTTP proxy for
forwarding requests from the dashboard to any module API.

The dashboard never imports code from another module — all
inter-module communication goes through this registry + HTTP.
"""

import os
import json
import glob
import logging
from typing import Dict, List, Optional

import requests as http_client  # renamed to avoid confusion with flask.request

REGISTRY_DIR = os.environ.get("CDO_REGISTRY_DIR", "/etc/cdo/modules.d")

logger = logging.getLogger(__name__)


class ModuleRegistry:
    """Discover and communicate with CDO modules."""

    def __init__(self, registry_dir: str = REGISTRY_DIR):
        self.registry_dir = registry_dir
        self._modules: Dict[str, dict] = {}
        self.reload()

    # ─── Discovery ────────────────────────────────────────────────────

    def reload(self):
        """Re-read all *.json files from the registry directory."""
        self._modules = {}
        pattern = os.path.join(self.registry_dir, "*.json")

        for filepath in sorted(glob.glob(pattern)):
            try:
                with open(filepath) as f:
                    data = json.load(f)
                name = data.get("name")
                if name:
                    self._modules[name] = data
                    logger.info(f"Registered module: {name} @ {data.get('baseUrl')}")
            except Exception as e:
                logger.warning(f"Failed to load {filepath}: {e}")

        logger.info(f"Registry loaded: {len(self._modules)} module(s)")

    def list_modules(self) -> List[dict]:
        """Return all registered module entries."""
        return list(self._modules.values())

    def get_module(self, name: str) -> Optional[dict]:
        """Look up a single module by name."""
        return self._modules.get(name)

    # ─── Health ───────────────────────────────────────────────────────

    def probe_health(self, name: str) -> dict:
        """Probe a module's health endpoint and return a status dict."""
        module = self._modules.get(name)
        if not module:
            return {"status": "not_registered"}

        health_path = module.get("endpoints", {}).get("health", "/v1/health")
        url = f"{module['baseUrl']}{health_path}"

        try:
            resp = http_client.get(url, timeout=3)
            if resp.status_code == 200:
                return {"status": "ok", **resp.json()}
            return {"status": "unhealthy", "http": resp.status_code}
        except http_client.ConnectionError:
            return {"status": "offline"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def get_all_with_health(self) -> List[dict]:
        """Return every module enriched with live health status."""
        results = []
        for name, module in self._modules.items():
            results.append({**module, "health": self.probe_health(name)})
        return results

    # ─── HTTP proxy ───────────────────────────────────────────────────

    def proxy(
        self,
        module_name: str,
        path: str,
        method: str = "GET",
        data: Optional[dict] = None,
        params: Optional[dict] = None,
        timeout: int = 60,
    ) -> Optional[http_client.Response]:
        """
        Forward an HTTP request to a module's API.

        Returns the raw ``requests.Response`` or ``None`` on failure.
        """
        module = self._modules.get(module_name)
        if not module:
            return None

        url = f"{module['baseUrl']}/{path.lstrip('/')}"

        try:
            return http_client.request(
                method=method,
                url=url,
                json=data,
                params=params,
                timeout=timeout,
            )
        except Exception as e:
            logger.error(f"Proxy to {module_name} ({url}) failed: {e}")
            return None
