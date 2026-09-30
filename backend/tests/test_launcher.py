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
        self.temp.cleanup()

    def _make_workbench(self) -> None:
        server = self.root / "server.sh"
        server.write_text(
            "#!/bin/sh\n"
            "STATE=\"$(dirname \"$0\")/running\"\n"
            "case \"${1:-}\" in\n"
            "status) [ -f \"$STATE\" ] && { echo 'authserver running'; echo 'worldserver running'; exit 0; }; echo stopped; exit 3;;\n"
            "start|restart) : > \"$STATE\"; echo started;;\n"
            "stop) rm -f \"$STATE\"; echo stopped;;\n"
            "*) exit 64;; esac\n",
            encoding="utf-8",
        )
        os.chmod(server, 0o755)
        client = self.root / "client.sh"
        client.write_text("#!/bin/sh\necho fake-client-$1\n", encoding="utf-8")
        os.chmod(client, 0o755)
        wow = self.root / "client" / "ChromieCraft_3.3.5a" / "Wow.exe"
        wow.parent.mkdir(parents=True)
        wow.write_bytes(b"MZ-fake")

    def request(self, path: str, method: str = "GET") -> tuple[int, dict]:
        req = Request(self.base + path, method=method, headers={"X-Request-Id": "launcher-test"})
        try:
            with urlopen(req, timeout=3) as response:
                return response.status, json.load(response)
        except HTTPError as exc:
            return exc.code, json.load(exc)

    def test_launcher_ready_before_server_start(self) -> None:
        code, payload = self.request("/launcher/status")
        self.assertEqual(200, code)
        self.assertEqual("PLAY", payload["data"]["mode"])
        self.assertTrue(payload["data"]["can_play"])
        blocking = [g for g in payload["data"]["gates"] if g["blocking"]]
        self.assertTrue(all(g["status"] == "pass" for g in blocking))

    def test_play_starts_realm_then_launches_client(self) -> None:
        code, payload = self.request("/launcher/play", "POST")
        self.assertEqual(200, code)
        self.assertTrue(payload["success"])
        steps = payload["data"]["steps"]
        self.assertEqual("server.start", steps[0]["step"])
        self.assertEqual("client.launch", steps[1]["step"])
        self.assertTrue((self.root / "running").exists())

    def test_repair_plan_is_non_destructive(self) -> None:
        self.db.close()
        code, payload = self.request("/launcher/repair", "POST")
        self.assertEqual(200, code)
        self.assertTrue(payload["success"])
        actions = payload["data"]["actions"]
        self.assertIn("start-database", [item["action"] for item in actions])
        self.assertFalse((self.root / "running").exists())


if __name__ == "__main__":
    unittest.main()
