from __future__ import annotations

import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import time

from .models import OperationResult
from .process import run_checked
from .workbench import WorkbenchLocator


class LaunchValidationService:
    SUPPORTED_LOCALES = ("enUS", "enGB", "deDE", "esES", "esMX", "frFR", "ruRU", "koKR", "zhCN", "zhTW")
    EXPECTED_BUILD = "12340"

    def __init__(self, locator: WorkbenchLocator, display: str) -> None:
        self.locator = locator
        self.display = display

    def build_identity(self) -> OperationResult:
        manifest = self._runtime_manifest()
        if manifest is None:
            return OperationResult(
                False,
                "BUILD_MANIFEST_MISSING",
                "ChromieCraft build identity cannot be verified without the persisted runtime manifest",
                {"expected_build": self.EXPECTED_BUILD},
            )
        values = self._read_env_manifest(manifest)
        build = values.get("CHROMIECRAFT_BUILD")
        product = values.get("CHROMIECRAFT_PRODUCT")
        if build != self.EXPECTED_BUILD:
            return OperationResult(
                False,
                "BUILD_MISMATCH",
                f"ChromieCraft build {build or 'unknown'} does not match required build {self.EXPECTED_BUILD}",
                {"manifest": str(manifest), "expected_build": self.EXPECTED_BUILD, "observed_build": build, "product": product},
            )
        return OperationResult(
            True,
            "OK",
            f"ChromieCraft build {self.EXPECTED_BUILD} verified from persisted runtime manifest",
            {"manifest": str(manifest), "build": build, "product": product},
        )

    def runtime_preflight(self) -> OperationResult:
        return self._client_command(
            "preflight",
            timeout=20,
            success_message="Workbench Wine/client runtime preflight passed",
            failure_code="RUNTIME_PREFLIGHT_FAILED",
        )

    def wine_bootstrap(self) -> OperationResult:
        return self._client_command(
            "wine-check",
            timeout=45,
            success_message="Wine 32-bit process bootstrap passed",
            failure_code="WINE_BOOTSTRAP_FAILED",
        )

    def realmlist(self) -> OperationResult:
        locale = self._locale_dir()
        if locale is None:
            return OperationResult(False, "CLIENT_LOCALE_MISSING", "No supported ChromieCraft locale directory was found")
        path = locale / "realmlist.wtf"
        if not path.is_file():
            return OperationResult(False, "REALMLIST_MISSING", "realmlist.wtf is missing", {"path": str(path)})
        try:
            lines = [line.strip() for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]
        except OSError as exc:
            return OperationResult(False, "REALMLIST_READ_FAILED", str(exc), {"path": str(path)})
        local = lines == ["set realmlist 127.0.0.1"]
        return OperationResult(
            local,
            "OK" if local else "REALMLIST_NOT_LOCAL",
            "Realmlist targets the local realm" if local else "Realmlist requires local-realm configuration",
            {"path": str(path), "locale": locale.name, "target": "127.0.0.1" if local else "other"},
        )

    def configure_realmlist(self) -> OperationResult:
        configured = self._client_command(
            "configure",
            timeout=15,
            success_message="Realmlist configuration command completed",
            failure_code="REALMLIST_CONFIGURE_FAILED",
        )
        if not configured.ok:
            return configured
        verified = self.realmlist()
        if not verified.ok:
            return verified
        return OperationResult(True, "OK", "Realmlist configured and verified for the local realm", verified.evidence)

    def display_authentication(self) -> OperationResult:
        xdpyinfo = shutil.which("xdpyinfo")
        if not xdpyinfo:
            return OperationResult(False, "XDPYINFO_MISSING", "xdpyinfo is required for authenticated display validation")

        authority = Path(
            os.environ.get(
                "CHROMIE_XAUTHORITY",
                str(self.locator.root / "run" / "x11" / "Xauthority"),
            )
        )
        if not authority.is_file():
            return OperationResult(False, "XAUTHORITY_MISSING", "X11 authority file is missing", {"path": str(authority), "display": self.display})

        mode = stat.S_IMODE(authority.stat().st_mode)
        if mode != 0o600:
            return OperationResult(
                False,
                "XAUTHORITY_MODE_INVALID",
                "X11 authority file must be mode 0600",
                {"path": str(authority), "display": self.display, "mode": oct(mode)},
            )

        authorized = self._xdpyinfo(xdpyinfo, authority)
        if authorized.returncode != 0:
            return OperationResult(
                False,
                "DISPLAY_AUTH_FAILED",
                "Authenticated X11 probe failed",
                {"display": self.display, "authority": str(authority), "authority_mode": oct(mode), "authorized_returncode": authorized.returncode},
            )

        with tempfile.TemporaryDirectory(prefix="chromie-xauth-negative-") as tmp:
            os.chmod(tmp, 0o700)
            empty = Path(tmp) / "Xauthority"
            empty.touch(mode=0o600)
            unauthorized = self._xdpyinfo(xdpyinfo, empty)

        if unauthorized.returncode == 0:
            return OperationResult(
                False,
                "DISPLAY_AUTH_BYPASS",
                "Display accepted an explicitly unauthorized probe",
                {"display": self.display, "authority": str(authority), "authority_mode": oct(mode), "authorized_returncode": 0, "unauthorized_returncode": 0},
            )

        confirmed = self._xdpyinfo(xdpyinfo, authority)
        if confirmed.returncode != 0:
            return OperationResult(
                False,
                "DISPLAY_AUTH_UNSTABLE",
                "Authenticated X11 probe did not remain valid after the negative probe",
                {"display": self.display, "authority": str(authority), "authority_mode": oct(mode), "post_probe_returncode": confirmed.returncode},
            )

        return OperationResult(
            True,
            "OK",
            "Authenticated X11 display verified and unauthorized access rejected",
            {
                "display": self.display,
                "authority": str(authority),
                "authority_mode": oct(mode),
                "authorized_returncode": 0,
                "unauthorized_returncode": unauthorized.returncode,
                "post_probe_returncode": 0,
            },
        )

    def server_ports(self, wait_seconds: float = 15.0) -> OperationResult:
        deadline = time.monotonic() + max(wait_seconds, 0.0)
        last: OperationResult | None = None
        while True:
            last = self._client_command(
                "server-ports",
                timeout=5,
                success_message="Server listener probe completed",
                failure_code="SERVER_PORT_PROBE_FAILED",
            )
            stdout = str(last.evidence.get("stdout", ""))
            ready = "127.0.0.1:3724 ready" in stdout and "127.0.0.1:8085 ready" in stdout
            if last.ok and ready:
                return OperationResult(
                    True,
                    "OK",
                    "Auth and world listeners are ready on loopback",
                    {"auth": "127.0.0.1:3724", "world": "127.0.0.1:8085"},
                )
            if time.monotonic() >= deadline:
                return OperationResult(
                    False,
                    "SERVER_PORTS_NOT_READY",
                    "Auth/world listeners did not become ready before the launch deadline",
                    {"last_probe": last.evidence if last else {}},
                )
            time.sleep(0.5)

    def _client_command(self, command: str, *, timeout: float, success_message: str, failure_code: str) -> OperationResult:
        script = self.locator.client_script
        if not script.is_file():
            return OperationResult(False, "CLIENT_SCRIPT_MISSING", "client.sh is not available", {"path": str(script)})
        try:
            result = run_checked([script, command], cwd=self.locator.root, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            return OperationResult(False, f"{failure_code}_TIMEOUT", f"client.sh {command} timed out", {"timeout": exc.timeout})
        except OSError as exc:
            return OperationResult(False, f"{failure_code}_EXEC", str(exc), {"path": str(script)})
        return OperationResult(
            result.returncode == 0,
            "OK" if result.returncode == 0 else failure_code,
            success_message if result.returncode == 0 else f"client.sh {command} failed",
            result.evidence(),
        )

    def _runtime_manifest(self) -> Path | None:
        candidates = (
            self.locator.root / "manifests" / "portable-runtime.env",
            self.locator.root / "portable-runtime.env",
        )
        return next((path for path in candidates if path.is_file()), None)

    @staticmethod
    def _read_env_manifest(path: Path) -> dict[str, str]:
        values: dict[str, str] = {}
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
        return values

    def _locale_dir(self) -> Path | None:
        client_root = self.locator.wow_exe.parent if self.locator.wow_exe else self.locator.root / "client" / "ChromieCraft_3.3.5a"
        data = client_root / "Data"
        return next((data / locale for locale in self.SUPPORTED_LOCALES if (data / locale).is_dir()), None)

    def _xdpyinfo(self, executable: str, authority: Path) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["DISPLAY"] = self.display
        env["XAUTHORITY"] = str(authority)
        try:
            return subprocess.run(
                [executable, "-display", self.display],
                env=env,
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=4,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return subprocess.CompletedProcess([executable, "-display", self.display], 125, "", "")
