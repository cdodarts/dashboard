"""Exclusive detector ownership. Only these two fixed systemd units are managed."""

import contextlib
import fcntl
import json
import logging
import os
from pathlib import Path
import re
import subprocess
import tempfile
import threading
import time

logger = logging.getLogger(__name__)
PROVIDERS = {
    "autodarts": {"name": "Autodarts", "unit": "autodarts.service", "port": 3180},
    "cdo": {"name": "CDO Dart Detector", "unit": "cdo-dart-detector.service", "port": 41975},
}
SELECTION_PATH = Path("/var/lib/cdo/dashboard/detector-provider.json")
_TRANSITION_LOCK = threading.Lock()


class DetectorError(Exception):
    def __init__(self, message, status=503):
        super().__init__(message)
        self.status = status


class DetectorProvider:
    def __init__(self, selection_path=SELECTION_PATH, runner=subprocess.run):
        self.selection_path = Path(selection_path)
        self.lock_path = self.selection_path.with_suffix(".lock")
        self.runner = runner

    def _command(self, args, deadline, check=True):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise DetectorError("Detector operation timed out")
        try:
            result = self.runner(
                ["systemctl", "--no-ask-password", *args],
                capture_output=True, text=True, timeout=min(12, remaining),
            )
        except subprocess.TimeoutExpired as exc:
            raise DetectorError("Detector service operation timed out") from exc
        except OSError as exc:
            raise DetectorError("Cannot contact systemd") from exc
        if check and result.returncode:
            detail = " ".join((result.stderr or result.stdout or "systemctl failed").split())[:240]
            raise DetectorError(f"Detector service operation failed: {detail}")
        return result

    def _state(self, provider, deadline):
        result = self._command([
            "show", PROVIDERS[provider]["unit"], "--no-pager",
            "--property=LoadState,ActiveState,UnitFileState,ExecStart",
        ], deadline, check=False)
        values = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
        if result.returncode and values.get("LoadState") != "not-found":
            raise DetectorError("Cannot read detector service state")
        installed = values.get("LoadState") == "loaded"
        # A stale unit pointing at an uninstalled executable is not an installed provider.
        executable = re.search(r"(?:^|[ ;{])path=([^ ;}]+)", values.get("ExecStart", ""))
        if executable and not os.access(executable.group(1), os.X_OK):
            installed = False
        return {
            "unit_exists": values.get("LoadState") == "loaded",
            "installed": installed,
            "active": values.get("ActiveState") in {"active", "reloading", "activating"},
            "enabled": values.get("UnitFileState") in {"enabled", "enabled-runtime"},
            "active_state": values.get("ActiveState", "unknown"),
            "unit_file_state": values.get("UnitFileState", "unknown"),
        }

    def _read_selection(self):
        try:
            value = json.loads(self.selection_path.read_text())
            selected = value.get("selected") if isinstance(value, dict) else None
            return selected if selected in PROVIDERS else None
        except (OSError, ValueError):
            return None

    def _status(self, states):
        active = [provider for provider, state in states.items() if state["active"]]
        selected = self._read_selection() or (active[0] if len(active) == 1 else "autodarts")
        return {
            "selected": selected,
            "active": active[0] if len(active) == 1 else "conflict" if active else None,
            "providers": [
                {"id": provider, "name": info["name"], "port": info["port"],
                 **{key: states[provider][key] for key in ("installed", "active", "enabled")}}
                for provider, info in PROVIDERS.items()
            ],
        }

    def status(self):
        # GET only observes services and the existing selection; it never creates files.
        deadline = time.monotonic() + 15
        return self._status({provider: self._state(provider, deadline) for provider in PROVIDERS})

    def _atomic_write(self, data):
        fd, name = tempfile.mkstemp(prefix=".detector-provider-", dir=self.selection_path.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                os.fchmod(stream.fileno(), 0o600)
                os.fchown(stream.fileno(), 0, 0)
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.selection_path)
            directory = os.open(self.selection_path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    @contextlib.contextmanager
    def _locked(self, deadline):
        if not _TRANSITION_LOCK.acquire(timeout=max(0, min(5, deadline - time.monotonic()))):
            raise DetectorError("A detector switch is already in progress", 409)
        try:
            self.selection_path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
            fd = os.open(self.lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "a") as stream:
                while True:
                    try:
                        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except BlockingIOError:
                        if time.monotonic() >= deadline:
                            raise DetectorError("A detector switch is already in progress", 409)
                        time.sleep(0.05)
                try:
                    yield
                finally:
                    fcntl.flock(stream, fcntl.LOCK_UN)
        finally:
            _TRANSITION_LOCK.release()

    def _wait(self, provider, active, deadline):
        while True:
            state = self._state(provider, deadline)
            if active and state["active_state"] == "active":
                return state
            if not active and state["active_state"] in {"inactive", "failed"}:
                return state
            if active and state["active_state"] == "failed":
                raise DetectorError("Selected detector failed to start")
            if time.monotonic() >= deadline:
                raise DetectorError("Detector service did not reach the required state")
            time.sleep(0.2)

    def _rollback(self, snapshot, previous_selection, deadline):
        errors = []
        def attempt(callback):
            try:
                callback()
            except Exception as exc:
                errors.append(str(exc))

        # Stop providers that were originally stopped before restoring the previous owner.
        for provider, state in snapshot.items():
            if state["unit_exists"] and not state["active"]:
                attempt(lambda p=provider: self._command(["stop", PROVIDERS[p]["unit"]], deadline))
                attempt(lambda p=provider: self._wait(p, False, deadline))
        stop_failed = bool(errors)
        for provider, state in snapshot.items():
            if state["unit_exists"]:
                args = ["enable" if state["enabled"] else "disable"]
                if state["unit_file_state"] == "enabled-runtime":
                    # Remove persistent links created by the failed switch before
                    # restoring the original boot-lifetime-only enablement.
                    attempt(lambda p=provider: self._command(["disable", PROVIDERS[p]["unit"]], deadline))
                    args.append("--runtime")
                attempt(lambda p=provider, a=args: self._command([*a, PROVIDERS[p]["unit"]], deadline))
        if not stop_failed:
            for provider, state in snapshot.items():
                if state["active"]:
                    attempt(lambda p=provider: self._command(["start", PROVIDERS[p]["unit"]], deadline))
                    attempt(lambda p=provider: self._wait(p, True, deadline))
        for provider, state in snapshot.items():
            if state["unit_exists"]:
                def verify(p=provider, original=state):
                    current = self._state(p, deadline)
                    if (current["active"], current["enabled"]) != (original["active"], original["enabled"]):
                        raise DetectorError("Previous detector state was not fully restored")
                attempt(verify)
        try:
            if previous_selection is None:
                self.selection_path.unlink(missing_ok=True)
            else:
                self._atomic_write(previous_selection)
        except Exception as exc:
            errors.append(str(exc))
        if errors:
            logger.error("Detector rollback incomplete: %s", "; ".join(errors))
        return errors

    def switch(self, provider, restart=False):
        if not isinstance(provider, str) or provider not in PROVIDERS:
            raise DetectorError("provider must be autodarts or cdo", 400)
        started = time.monotonic()
        with self._locked(started + 5):
            deadline = started + 55  # Leave up to 20 seconds for rollback within a 90s client timeout.
            snapshot = {p: self._state(p, deadline) for p in PROVIDERS}
            if not snapshot[provider]["installed"]:
                raise DetectorError("Selected detector is not installed", 409)
            if any(s["active_state"] in {"activating", "deactivating", "reloading"} for s in snapshot.values()):
                raise DetectorError("A detector service is changing state; try again shortly", 409)
            previous_selection = self.selection_path.read_bytes() if self.selection_path.exists() else None
            other = "cdo" if provider == "autodarts" else "autodarts"
            try:
                if snapshot[other]["unit_exists"]:
                    self._command(["stop", PROVIDERS[other]["unit"]], deadline)
                    self._command(["disable", PROVIDERS[other]["unit"]], deadline)
                    if self._wait(other, False, deadline)["enabled"]:
                        raise DetectorError("Previous detector is still enabled")
                self._command(["enable", PROVIDERS[provider]["unit"]], deadline)
                self._command(["restart" if restart else "start", PROVIDERS[provider]["unit"]], deadline)
                self._wait(provider, True, deadline)
                states = {p: self._state(p, deadline) for p in PROVIDERS}
                if states[other]["active"] or states[other]["enabled"] or not states[provider]["enabled"]:
                    raise DetectorError("Detector exclusivity verification failed")
                self._atomic_write(json.dumps({"selected": provider}).encode() + b"\n")
                return self._status(states)
            except Exception as exc:
                rollback_errors = self._rollback(snapshot, previous_selection, min(started + 80, time.monotonic() + 20))
                message = str(exc) if isinstance(exc, DetectorError) else "Could not save detector selection"
                if rollback_errors:
                    message += "; rollback incomplete: inspect detector services before retrying"
                else:
                    message += "; previous detector state restored"
                raise DetectorError(message) from exc


manager = DetectorProvider()
