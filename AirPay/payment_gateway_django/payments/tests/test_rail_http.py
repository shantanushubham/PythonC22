import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from django.test import SimpleTestCase

from payments.rails.base import RailUnavailable
from payments.rails.http import replayed, request_json


class Handler(BaseHTTPRequestHandler):
    """A tiny rail. The path picks what it does."""

    seen: list[dict] = []

    def log_message(self, *args):  # keep test output quiet
        pass

    def _reply(self, status, body: bytes, content_type="application/json", extra=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _handle(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        Handler.seen.append(
            {
                "method": self.command,
                "path": self.path,
                "body": json.loads(raw) if raw else None,
                "content_type": self.headers.get("Content-Type"),
                "accept": self.headers.get("Accept"),
                "idempotency": self.headers.get("Idempotency-Key"),
                "api_key": self.headers.get("X-Api-Key"),
            }
        )
        if self.path == "/ok":
            self._reply(201, b'{"data": {"id": "txn_1"}}', extra={"Idempotent-Replayed": "true"})
        elif self.path == "/declined":
            self._reply(402, b'{"status": "FAILED"}')
        elif self.path == "/bad":
            self._reply(400, b'{"errors": [{"field": "card", "message": "bad"}]}')
        elif self.path == "/empty":
            self._reply(204, b"")
        elif self.path == "/html-error":
            self._reply(502, b"<html>Bad gateway</html>", content_type="text/html")
        elif self.path == "/html-ok":
            self._reply(200, b"<html>hello</html>", content_type="text/html")
        elif self.path == "/slow":
            time.sleep(1.0)
            self._reply(200, b"{}")
        else:
            self._reply(404, b'{"message": "no such thing"}')

    do_GET = do_POST = _handle


class RailHttpTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        super().tearDownClass()

    def setUp(self):
        Handler.seen = []

    def test_sends_json_and_headers_and_returns_status_body_and_headers(self):
        status, body, headers = request_json(
            "POST",
            f"{self.base}/ok",
            json_body={"amount": "10.00"},
            headers={"Idempotency-Key": "k1", "X-API-Key": "secret", "Skipped": ""},
        )

        self.assertEqual((status, body), (201, {"data": {"id": "txn_1"}}))
        self.assertTrue(replayed(headers))
        sent = Handler.seen[0]
        self.assertEqual(sent["body"], {"amount": "10.00"})
        self.assertEqual(sent["content_type"], "application/json")
        self.assertEqual(sent["accept"], "application/json")
        self.assertEqual((sent["idempotency"], sent["api_key"]), ("k1", "secret"))

    def test_a_get_sends_no_body(self):
        status, body, _ = request_json("GET", f"{self.base}/ok")

        self.assertEqual(status, 201)
        self.assertIsNone(Handler.seen[0]["body"])

    def test_an_error_status_is_returned_not_raised(self):
        self.assertEqual(request_json("POST", f"{self.base}/bad", json_body={})[0:2], (400, {"errors": [{"field": "card", "message": "bad"}]}))
        self.assertEqual(request_json("GET", f"{self.base}/declined")[0:2], (402, {"status": "FAILED"}))
        self.assertEqual(request_json("GET", f"{self.base}/missing")[0], 404)

    def test_an_empty_reply_is_an_empty_body(self):
        self.assertEqual(request_json("GET", f"{self.base}/empty")[0:2], (204, {}))

    def test_an_error_page_that_is_not_json_still_returns_its_status(self):
        self.assertEqual(request_json("GET", f"{self.base}/html-error")[0:2], (502, {}))

    def test_a_success_that_is_not_json_is_unavailable(self):
        with self.assertRaisesMessage(RailUnavailable, "could not be read"):
            request_json("GET", f"{self.base}/html-ok", service="card service")

    def test_a_slow_rail_times_out(self):
        with self.assertRaisesMessage(RailUnavailable, "The card service timed out."):
            request_json("GET", f"{self.base}/slow", timeout=0.2, service="card service")

    def test_a_rail_that_is_down_is_unavailable(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]  # nothing listens here once the socket closes
        with self.assertRaisesMessage(RailUnavailable, "The UPI service is unavailable."):
            request_json("GET", f"http://127.0.0.1:{port}/x", service="UPI service")

    def test_replayed_reads_the_header_in_any_case(self):
        self.assertTrue(replayed({"idempotent-replayed": "True"}))
        self.assertFalse(replayed({}))
