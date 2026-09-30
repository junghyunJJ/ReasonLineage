"""A local HTTP server that records requests and returns a canned reply (no network needed)."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class FakeServer:
    def __init__(self, reply=None, models=("Qwen/Qwen3.8-Flash-Next-FP8",)):
        self.requests: list[dict] = []
        self.paths: list[str] = []
        self.headers: list[dict] = []
        self.reply = reply or {"status": 200, "body": {}}
        self.models = list(models)
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers["Content-Length"])
                outer.paths.append(self.path)
                outer.headers.append(dict(self.headers))
                outer.requests.append(json.loads(self.rfile.read(length)))
                self._send(outer.reply["status"], outer.reply["body"])

            def do_GET(self):
                outer.paths.append(self.path)
                self._send(200, {"data": [{"id": m} for m in outer.models]})

            def _send(self, status, body):
                data = (body if isinstance(body, str) else json.dumps(body)).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/v1"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
