from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from chromie_backend.api import build_server
from chromie_backend.app import build_services
from chromie_backend.config import Settings


class TcpProbe:
    def __init__(self) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(4)
        self.port = self.sock.getsockname()[1]
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self) -> None:
        self.sock.settimeout(0.1)
        while not self.stop.is_set():
            try:
                conn, _ = self.sock.accept()
                conn.close()
            except TimeoutError:
                pass
            except OSError:
                break

    def close(self) -> None:
        self.stop.set()
        self.sock.close()
        self.thread.join(timeout=1)


class LauncherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.original_path = os.environ.get("PATH", "")
        self._make_workbench()
        self.db = TcpProbe()
        settings = Settings(self.root, "127.0.0.1", 0, "127.0.0.1", self.db.port, ":88")
        self.services = build_services(settings)
        self.httpd = build_server("127.0.0.1", 0, self.services)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.httpd.server_address[:2]
        self.base = f"http://{host}:{port}/api/v1"

    def tearDown(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2)
        self.db.close()
        os.environ["PATH"] = self.original_path
        self.temp.cleanup()

    def _make_workbench(self) -> None:
        server = self.root / "server.sh"
        server.write_text(
            "#!/bin/sh\n"
            "STATE=\"$(dirname \"$0\")/running\"\n"
            "case \"$1\" in\n"
            "status) [ -f \"$STATE\" ] && { echo 'authserver running'; echo 'worldserver running'; exit 0; }; echo stopped; exit 3;;\n"
            "preflight) echo 'preflight=ready'; exit 0;;\n"
            "start|restart) : > \"$STATE\"; echo started;;\n"
            "stop) rm -f \"$STATE\"; echo stopped;;\n"
            "*) exit 64;; esac\n",
            encoding="utf-8",
        )
        os.chmod(server, 0o755)

        client_root = self.root / "client" / "ChromieCraft_3.3.5a"
        locale = client_root / "Data" / "enUS"
        locale.mkdir(parents=True)
        (client_root / "Wow.exe").write_bytes(b"MZ-fake")
        (locale / "realmlist.wtf").write_text("set realmlist 127.0.0.1\n", encoding="utf-8")

        client = self.root / "client.sh"
        client.write_text(
            "#!/bin/sh\n"
            "ROOT=\"$(dirname \"$0\")\"\n"
            "STATE=\"$ROOT/running\"\n"
            "REALM=\"$ROOT/client/ChromieCraft_3.3.5a/Data/enUS/realmlist.wtf\"\n"
            "case \"$1\" in\n"
            "preflight) echo 'Wine mode: fake'; echo 'Client: Wow.exe'; exit 0;;\n"
            "wine-check) echo 'Wine 32-bit process bootstrap: OK'; exit 0;;\n"
            "dxvk-check) echo 'DXVK 3.1.1 payload: OK'; exit 0;;\n"
            "configure) printf '%s\\n' 'set realmlist 127.0.0.1' > \"$REALM\"; exit 0;;\n"
            "server-ports) if [ -f \"$STATE\" ]; then echo '127.0.0.1:3724 ready'; echo '127.0.0.1:8085 ready'; exit 0; else echo '127.0.0.1:3724 not listening'; echo '127.0.0.1:8085 not listening'; exit 3; fi;;\n"
            "launch) echo fake-client-launch; exit 0;;\n"
            "*) echo fake-client-$1; exit 0;; esac\n",
            encoding="utf-8",
        )
        os.chmod(client, 0o755)

        data = self.root / "state" / "data"
        for name in ("dbc", "maps", "vmaps", "mmaps"):
            (data / name).mkdir(parents=True, exist_ok=True)

        manifests = self.root / "manifests"
        manifests.mkdir()
        (manifests / "portable-runtime.env").write_text(
            "CHROMIECRAFT_PRODUCT=ChromieCraft_3.3.5a\n"
            "CHROMIECRAFT_BUILD=12340\n",
            encoding="utf-8",
        )

        auth_dir = self.root / "run" / "x11"
        auth_dir.mkdir(parents=True)
        os.chmod(auth_dir, 0o700)
        authority = auth_dir / "Xauthority"
        authority.write_bytes(b"private-test-authority")
        os.chmod(authority, 0o600)

        fake_bin = self.root / "fake-bin"
        fake_bin.mkdir()
        xdpyinfo = fake_bin / "xdpyinfo"
        xdpyinfo.write_text(
            "#!/bin/sh\n"
            f"if [ \"$XAUTHORITY\" = \"{authority}\" ]; then exit 0; fi\n"
            "echo 'Authorization required' >&2\n"
            "exit 1\n",
            encoding="utf-8",
        )
        os.chmod(xdpyinfo, 0o755)
        os.environ["PATH"] = f"{fake_bin}:{self.original_path}"

    def request(self, path: str, method: str = "GET") -> tuple[int, dict]:
        req = Request(self.base + path, method=method, headers={"X-Request-Id": "launcher-test"})
        try:
            with urlopen(req, timeout=5) as response:
                return response.status, json.load(response)
        except HTTPError as exc:
            return exc.code, json.load(exc)

    def test_strict_launcher_ready_before_server_start(self) -> None:
        code, payload = self.request("/launcher/status")
        self.assertEqual(200, code)
        self.assertEqual("PLAY", payload["data"]["mode"])
        self.assertTrue(payload["data"]["can_play"])
        blocking = [g for g in payload["data"]["gates"] if g["blocking"]]
        self.assertTrue(all(g["status"] == "pass" for g in blocking))

    def test_play_validates_wine_starts_realm_checks_ports_then_launches(self) -> None:
        code, payload = self.request("/launcher/play", "POST")
        self.assertEqual(200, code)
        self.assertTrue(payload["success"])
        steps = [item["step"] for item in payload["data"]["steps"]]
        self.assertEqual(
            ["client.wine-check", "server.start", "server.listeners", "client.launch"],
            steps,
        )
        self.assertTrue((self.root / "running").exists())

    def test_stopped_database_is_standby_not_blocking(self) -> None:
        self.db.close()
        code, payload = self.request("/launcher/status")
        self.assertEqual(200, code)
        self.assertTrue(payload["data"]["can_play"])
        database = next(g for g in payload["data"]["gates"] if g["key"] == "database")
        self.assertEqual("standby", database["status"])
        self.assertFalse(database["blocking"])

    def test_repair_plan_flags_missing_server_data_without_mutation(self) -> None:
        os.rmdir(self.root / "state" / "data" / "mmaps")
        code, payload = self.request("/launcher/repair", "POST")
        self.assertEqual(200, code)
        self.assertTrue(payload["success"])
        actions = payload["data"]["actions"]
        self.assertIn("prepare-server-data", [item["action"] for item in actions])
        self.assertFalse((self.root / "running").exists())

    def test_build_mismatch_blocks_play(self) -> None:
        (self.root / "manifests" / "portable-runtime.env").write_text(
            "CHROMIECRAFT_PRODUCT=ChromieCraft_3.3.5a\nCHROMIECRAFT_BUILD=9999\n",
            encoding="utf-8",
        )
        _, payload = self.request("/launcher/status")
        self.assertFalse(payload["data"]["can_play"])
        self.assertIn("build", payload["data"]["repair_reasons"])

    def test_display_host_bypass_blocks_play(self) -> None:
        xdpyinfo = self.root / "fake-bin" / "xdpyinfo"
        xdpyinfo.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        os.chmod(xdpyinfo, 0o755)
        _, payload = self.request("/launcher/status")
        self.assertFalse(payload["data"]["can_play"])
        self.assertIn("display", payload["data"]["repair_reasons"])


if __name__ == "__main__":
    unittest.main()
