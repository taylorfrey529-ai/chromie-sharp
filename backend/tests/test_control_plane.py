from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from chromie_backend.api import build_server
from chromie_backend.app import build_services
from chromie_backend.config import Settings


class ControlPlaneTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self._make_fake_workbench()
        settings = Settings(
            workbench_root=self.root,
            api_host="127.0.0.1",
            api_port=0,
            db_host="127.0.0.1",
            db_port=1,
            display=":88",
        )
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
        self.temp.cleanup()

    def _make_fake_workbench(self) -> None:
        state = self.root / "fake.running"
        server = self.root / "server.sh"
        server.write_text(
            "#!/bin/sh\n"
            "STATE=\"$(dirname \"$0\")/fake.running\"\n"
            "case \"${1:-}\" in\n"
            " status) if [ -f \"$STATE\" ]; then echo 'authserver running'; echo 'worldserver running'; exit 0; else echo 'stopped'; exit 3; fi ;;\n"
            " start) : > \"$STATE\"; echo started ;;\n"
            " stop) rm -f \"$STATE\"; echo stopped ;;\n"
            " restart) : > \"$STATE\"; echo restarted ;;\n"
            " *) exit 64 ;;\n"
            "esac\n",
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
        req = Request(self.base + path, method=method, headers={"X-Request-Id": "test-request"})
        try:
            with urlopen(req, timeout=3) as response:
                return response.status, json.load(response)
        except HTTPError as exc:
            return exc.code, json.load(exc)

    def test_health_envelope(self) -> None:
        status, payload = self.request("/health")
        self.assertEqual(200, status)
        self.assertTrue(payload["success"])
        self.assertEqual("test-request", payload["request_id"])
        self.assertEqual("health", payload["operation"])

    def test_server_lifecycle(self) -> None:
        code, status = self.request("/status")
        self.assertEqual(200, code)
        self.assertEqual("stopped", status["data"]["worldserver"]["state"])

        code, started = self.request("/server/start", "POST")
        self.assertEqual(200, code)
        self.assertTrue(started["success"])

        _, running = self.request("/status")
        self.assertEqual("running", running["data"]["authserver"]["state"])
        self.assertEqual("running", running["data"]["worldserver"]["state"])

        code, stopped = self.request("/server/stop", "POST")
        self.assertEqual(200, code)
        self.assertTrue(stopped["success"])

    def test_client_preflight(self) -> None:
        code, payload = self.request("/client/preflight")
        self.assertEqual(200, code)
        self.assertTrue(payload["success"])
        self.assertTrue(payload["data"]["wow_exe"].endswith("Wow.exe"))


class MissingWorkbenchTests(unittest.TestCase):
    def test_missing_is_reported_not_reconstructed(self) -> None:
        with tempfile.TemporaryDirectory() as parent:
            missing = Path(parent) / "not-mounted"
            settings = Settings(missing, "127.0.0.1", 0, "127.0.0.1", 1, ":88")
            services = build_services(settings)
            snapshot = services.status.snapshot().to_dict()
            self.assertEqual("missing", snapshot["workbench"]["state"])
            self.assertEqual("missing", snapshot["client"]["state"])
            self.assertEqual("missing", snapshot["worldserver"]["state"])


if __name__ == "__main__":
    unittest.main()
