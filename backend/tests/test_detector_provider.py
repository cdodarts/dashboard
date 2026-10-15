"""Run with: python -m unittest discover -s tests -v (from backend)."""

import copy
import fcntl
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from flask import Flask
from services.detector_provider import DetectorError, DetectorProvider, PROVIDERS
from routes import detectors
from routes import modules
import autodarts


class FakeSystemctl:
    def __init__(self):
        self.states = {
            "autodarts.service": {"load": "loaded", "active": "active", "enabled": "enabled"},
            "cdo-dart-detector.service": {"load": "loaded", "active": "inactive", "enabled": "disabled"},
        }
        self.calls = []
        self.failures = []
        self.delay = 0

    def __call__(self, argv, **kwargs):
        assert argv[:2] == ["systemctl", "--no-ask-password"]
        assert 0 < kwargs["timeout"] <= 12
        args = argv[2:]
        command = args[0]
        unit = next(arg for arg in args if arg.endswith(".service"))
        assert unit in self.states  # Never touches the manager or arbitrary units.
        self.calls.append((command, unit))
        if self.delay:
            time.sleep(self.delay)
        if self.failures and self.failures[0] == (command, unit):
            self.failures.pop(0)
            return subprocess.CompletedProcess(argv, 1, "", "injected failure")
        state = self.states[unit]
        if command == "show":
            output = (f"LoadState={state['load']}\nActiveState={state['active']}\n"
                      f"UnitFileState={state['enabled']}\nExecStart={{ path=/bin/true ; }}\n")
            return subprocess.CompletedProcess(argv, int(state["load"] == "not-found"), output, "")
        if command == "stop":
            state["active"] = "inactive"
        elif command in {"start", "restart"}:
            other = next(value for key, value in self.states.items() if key != unit)
            assert other["active"] == "inactive", "Started while other detector held cameras"
            state["active"] = "active"
        elif command == "enable":
            state["enabled"] = "enabled-runtime" if "--runtime" in args else "enabled"
        elif command == "disable":
            state["enabled"] = "disabled"
        else:
            raise AssertionError(command)
        return subprocess.CompletedProcess(argv, 0, "", "")


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "state" / "detector-provider.json"
        self.fake = FakeSystemctl()
        self.manager = DetectorProvider(self.path, self.fake)
        self.chown = patch("services.detector_provider.os.fchown")
        self.mock_chown = self.chown.start()
        self.addCleanup(self.chown.stop)

    def seed(self, provider="autodarts"):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"selected": provider}) + "\n")

    def test_status_is_read_only_and_fixed_ports(self):
        result = self.manager.status()
        self.assertFalse(self.path.parent.exists())
        self.assertEqual(result["selected"], "autodarts")
        self.assertEqual(result["active"], "autodarts")
        self.assertEqual([p["port"] for p in result["providers"]], [3180, 41975])
        self.assertTrue(all(command == "show" for command, _ in self.fake.calls))

    def test_stop_disable_verify_precede_enable_start_and_persist(self):
        result = self.manager.switch("cdo")
        commands = [call for call in self.fake.calls if call[0] != "show"]
        self.assertEqual(commands, [
            ("stop", "autodarts.service"), ("disable", "autodarts.service"),
            ("enable", "cdo-dart-detector.service"), ("start", "cdo-dart-detector.service"),
        ])
        self.assertEqual(result["selected"], "cdo")
        self.assertEqual(result["active"], "cdo")
        self.assertEqual(json.loads(self.path.read_text()), {"selected": "cdo"})
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.mock_chown.assert_called_with(unittest.mock.ANY, 0, 0)
        self.assertEqual(list(self.path.parent.glob(".detector-provider-*")), [])

    def test_switch_back_and_restart(self):
        self.manager.switch("cdo")
        result = self.manager.switch("autodarts", restart=True)
        self.assertEqual(result["active"], "autodarts")
        self.assertIn(("restart", "autodarts.service"), self.fake.calls)

    def test_invalid_provider_never_runs_command(self):
        for provider in [None, [], {}, 0, "shell.service", "cdo; reboot"]:
            with self.subTest(provider=provider), self.assertRaises(DetectorError) as error:
                self.manager.switch(provider)
            self.assertEqual(error.exception.status, 400)
        self.assertEqual(self.fake.calls, [])

    def test_absent_unit_reports_uninstalled_and_rejects_switch(self):
        self.fake.states["cdo-dart-detector.service"]["load"] = "not-found"
        self.assertFalse(self.manager.status()["providers"][1]["installed"])
        with self.assertRaises(DetectorError) as error:
            self.manager.switch("cdo")
        self.assertEqual(error.exception.status, 409)
        self.assertTrue(all(command == "show" for command, _ in self.fake.calls))

    def test_missing_executable_rejects_switch(self):
        with patch("services.detector_provider.os.access", return_value=False):
            self.assertFalse(self.manager.status()["providers"][1]["installed"])
            with self.assertRaises(DetectorError) as error:
                self.manager.switch("cdo")
        self.assertEqual(error.exception.status, 409)

    def test_failures_restore_running_enabled_and_selection(self):
        for command, unit in [
            ("stop", "autodarts.service"), ("disable", "autodarts.service"),
            ("enable", "cdo-dart-detector.service"), ("start", "cdo-dart-detector.service"),
        ]:
            with self.subTest(command=command):
                self.fake = FakeSystemctl()
                self.manager.runner = self.fake
                original = copy.deepcopy(self.fake.states)
                self.seed()
                previous = self.path.read_bytes()
                self.fake.failures = [(command, unit)]
                with self.assertRaises(DetectorError) as error:
                    self.manager.switch("cdo")
                self.assertIn("previous detector state restored", str(error.exception))
                self.assertEqual(self.fake.states, original)
                self.assertEqual(self.path.read_bytes(), previous)

    def test_persistence_failure_restores_and_removes_new_selection(self):
        original = copy.deepcopy(self.fake.states)
        with patch.object(self.manager, "_atomic_write", side_effect=OSError("disk full")):
            with self.assertRaises(DetectorError):
                self.manager.switch("cdo")
        self.assertEqual(self.fake.states, original)
        self.assertFalse(self.path.exists())

    def test_rollback_enable_failure_still_restores_running_owner(self):
        self.fake.failures = [("start", "cdo-dart-detector.service"), ("enable", "autodarts.service")]
        with self.assertRaises(DetectorError) as error:
            self.manager.switch("cdo")
        self.assertIn("rollback incomplete", str(error.exception))
        self.assertEqual(self.fake.states["autodarts.service"]["active"], "active")
        self.assertEqual(self.fake.states["cdo-dart-detector.service"]["active"], "inactive")

    def test_runtime_enablement_restored_exactly(self):
        self.fake.states["autodarts.service"]["enabled"] = "enabled-runtime"
        original = copy.deepcopy(self.fake.states)
        self.fake.failures = [("start", "cdo-dart-detector.service")]
        with self.assertRaises(DetectorError):
            self.manager.switch("cdo")
        self.assertEqual(self.fake.states, original)

    def test_rollback_disable_failure_still_restores_running_owner(self):
        self.fake.failures = [("start", "cdo-dart-detector.service"), ("disable", "cdo-dart-detector.service")]
        with self.assertRaises(DetectorError) as error:
            self.manager.switch("cdo")
        self.assertIn("rollback incomplete", str(error.exception))
        self.assertEqual(self.fake.states["autodarts.service"]["active"], "active")
        self.assertEqual(self.fake.states["cdo-dart-detector.service"]["active"], "inactive")

    def test_persistence_failure_after_replace_restores_previous_bytes(self):
        self.seed()
        previous = self.path.read_bytes()
        original = copy.deepcopy(self.fake.states)
        write = self.manager._atomic_write
        calls = []
        def failing_write(data):
            write(data)
            calls.append(data)
            if len(calls) == 1:
                raise OSError("directory fsync failed")
        with patch.object(self.manager, "_atomic_write", side_effect=failing_write):
            with self.assertRaises(DetectorError):
                self.manager.switch("cdo")
        self.assertEqual(self.path.read_bytes(), previous)
        self.assertEqual(self.fake.states, original)

    def test_systemctl_timeout_rolls_back(self):
        original = copy.deepcopy(self.fake.states)
        fired = []
        def runner(argv, **kwargs):
            if "start" in argv and "cdo-dart-detector.service" in argv and not fired:
                fired.append(True)
                raise subprocess.TimeoutExpired(argv, kwargs["timeout"])
            return self.fake(argv, **kwargs)
        self.manager.runner = runner
        with self.assertRaises(DetectorError) as error:
            self.manager.switch("cdo")
        self.assertIn("timed out", str(error.exception))
        self.assertEqual(self.fake.states, original)

    def test_file_lock_blocks_another_manager(self):
        self.seed()
        with self.manager.lock_path.open("a") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(DetectorError) as error:
                with self.manager._locked(time.monotonic() + 0.05):
                    self.fail("Acquired a held file lock")
        self.assertEqual(error.exception.status, 409)
        self.assertEqual(self.fake.calls, [])

    def test_threaded_switches_are_serialized(self):
        self.fake.delay = 0.005
        entered = threading.Event()
        def runner(*args, **kwargs):
            entered.set()  # Set inside the first switch's held lock.
            return self.fake(*args, **kwargs)
        self.manager.runner = runner
        errors = []
        def switch(provider):
            try:
                self.manager.switch(provider)
            except Exception as exc:
                errors.append(exc)
        threads = [threading.Thread(target=switch, args=(provider,)) for provider in ("cdo", "autodarts")]
        threads[0].start()
        self.assertTrue(entered.wait(timeout=1))
        threads[1].start()
        for thread in threads:
            thread.join(timeout=5)
        self.assertEqual(errors, [])
        self.assertEqual(self.manager.status()["active"], "autodarts")
        self.assertEqual(json.loads(self.path.read_text())["selected"], "autodarts")

    def test_conflict_is_visible(self):
        self.fake.states["cdo-dart-detector.service"]["active"] = "active"
        self.assertEqual(self.manager.status()["active"], "conflict")


class RouteTests(unittest.TestCase):
    def setUp(self):
        ProviderTests.setUp(self)
        self.app = Flask(__name__)
        self.app.register_blueprint(detectors.bp)
        self.app.register_blueprint(autodarts.bp)
        self.app.register_blueprint(modules.bp)
        self.client = self.app.test_client()
        self.patch_manager = patch.object(detectors, "manager", self.manager)
        self.patch_manager.start()
        self.addCleanup(self.patch_manager.stop)

    def test_non_object_and_invalid_json_rejected(self):
        for value in [None, [], "cdo", {}, {"provider": []}, {"provider": "nope"}]:
            response = self.client.post("/api/detectors/switch", json=value)
            self.assertEqual(response.status_code, 400)
        response = self.client.post("/api/detectors/switch", data="{", content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.fake.calls, [])

    def test_foreign_origin_null_and_cross_site_rejected(self):
        for headers in [
            {"Origin": "https://attacker.invalid"}, {"Origin": "null"},
            {"Origin": "http://localhost", "Sec-Fetch-Site": "cross-site"},
            {"Origin": "http://[invalid"},
            {"Sec-Fetch-Site": "same-site"},
        ]:
            response = self.client.post("/api/detectors/switch", json={"provider": "cdo"}, headers=headers)
            self.assertEqual(response.status_code, 403)
        self.assertEqual(self.fake.calls, [])

    def test_same_origin_switch_and_read_only_get(self):
        self.assertEqual(self.client.get("/api/detectors").status_code, 200)
        self.assertFalse(self.path.parent.exists())
        response = self.client.post("/api/detectors/switch", json={"provider": "cdo"},
                                    headers={"Origin": "http://localhost", "Sec-Fetch-Site": "same-origin"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["active"], "cdo")

    def test_legacy_start_and_restart_use_exclusive_manager(self):
        self.manager.switch("cdo")
        response = self.client.post("/api/autodarts/service/start")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["active"], "autodarts")
        response = self.client.post("/api/autodarts/service/restart", headers={"Origin": "https://attacker.invalid"})
        self.assertEqual(response.status_code, 403)

    def test_module_start_restart_aliases_use_exclusive_manager(self):
        with patch.object(modules.registry, "get_module", return_value={"name": "autodarts-manager"}), \
                patch.object(modules.registry, "proxy") as proxy:
            for action in ("start", "restart"):
                self.manager.switch("cdo")
                response = self.client.post(f"/api/modules/autodarts-manager/v1/service/{action}")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json["active"], "autodarts")
            proxy.assert_not_called()
            response = self.client.post("/api/modules/autodarts-manager/v1/service/start",
                                        headers={"Origin": "https://attacker.invalid"})
            self.assertEqual(response.status_code, 403)

    def test_installer_aliases_reject_cdo_preference_or_active_owner(self):
        endpoints = ["/api/autodarts/install", "/api/autodarts/update", "/api/apps/autodarts/install",
                     "/api/modules/autodarts-manager/v1/install", "/api/modules/autodarts-manager/v1/update"]
        with patch.object(modules.registry, "get_module", return_value={"name": "autodarts-manager"}), \
                patch.object(modules.registry, "proxy") as proxy, patch.object(autodarts, "_proxy_post") as post:
            for selected, active in (("cdo", "autodarts"), ("autodarts", "cdo")):
                self.path.parent.mkdir(parents=True, exist_ok=True)
                self.path.write_text(json.dumps({"selected": selected}))
                for provider, info in PROVIDERS.items():
                    self.fake.states[info["unit"]]["active"] = "active" if provider == active else "inactive"
                for endpoint in endpoints:
                    with self.subTest(endpoint=endpoint, selected=selected, active=active):
                        response = self.client.post(endpoint, json={})
                        self.assertEqual(response.status_code, 409)
                        self.assertEqual(response.json["error"],
                                         "Select Autodarts on the dashboard before installing or updating Autodarts.")
            proxy.assert_not_called()
            post.assert_not_called()

    def test_installer_aliases_reject_foreign_origin_and_allow_autodarts(self):
        endpoints = ["/api/autodarts/install", "/api/autodarts/update",
                     "/api/modules/autodarts-manager/v1/install", "/api/modules/autodarts-manager/v1/update"]
        response_stub = SimpleNamespace(content=b'{"success":true}', status_code=200,
                                        headers={"Content-Type": "application/json"})
        with patch.object(modules.registry, "get_module", return_value={"name": "autodarts-manager"}), \
                patch.object(modules.registry, "proxy", return_value=response_stub) as proxy, \
                patch.object(autodarts, "_proxy_post", return_value=({"success": True}, 200)) as post:
            for endpoint in [*endpoints, "/api/apps/autodarts/install"]:
                response = self.client.post(endpoint, json={}, headers={"Origin": "https://attacker.invalid"})
                self.assertEqual(response.status_code, 403)
            self.assertEqual(self.fake.calls, [])
            for endpoint in endpoints:
                response = self.client.post(endpoint, json={}, headers={"Origin": "http://localhost"})
                self.assertEqual(response.status_code, 200)
            self.assertEqual(proxy.call_count, 2)
            self.assertEqual(post.call_count, 2)

    def test_unrelated_module_proxy_preserves_existing_behavior(self):
        response_stub = SimpleNamespace(content=b'{"ok":true}', status_code=201,
                                        headers={"Content-Type": "application/json"})
        with patch.object(modules.registry, "get_module", return_value={"name": "wifi-manager"}), \
                patch.object(modules.registry, "proxy", return_value=response_stub) as proxy:
            response = self.client.post("/api/modules/wifi-manager/v1/service/start", json={"network": "test"})
            self.assertEqual(response.status_code, 201)
            proxy.assert_called_once_with(module_name="wifi-manager", path="v1/service/start", method="POST",
                                          data={"network": "test"}, params={})
            self.assertEqual(self.fake.calls, [])


if __name__ == "__main__":
    unittest.main()
