"""Plot Twist: a garden planner that runs on your laptop. Python standard library only.

    python server.py            -> http://127.0.0.1:8000
"""
import datetime as dt
import json
import os
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import climate
import coach
from planner import build_plan

STATIC = Path(__file__).parent / "static"
PORT = int(os.environ.get("PORT", 8000))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write(f"  {self.command} {self.path.split('?')[0]}\n")

    def _send(self, status, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        q = {k: v[0] for k, v in urllib.parse.parse_qs(url.query).items()}
        try:
            if url.path == "/":
                self._send(200, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
            elif url.path == "/api/health":
                self._send(200, coach.health())
            elif url.path == "/api/geocode":
                self._send(200, climate.geocode(q.get("q", "")))
            elif url.path == "/api/plan":
                lat, lon = round(float(q["lat"]), 2), round(float(q["lon"]), 2)
                today = dt.date.fromisoformat(q["date"]) if q.get("date") else dt.date.today()
                c = climate.climate(lat, lon)
                fc = climate.forecast(lat, lon) if not q.get("date") else None
                self._send(200, build_plan(c, fc, today, q.get("name", f"{lat}, {lon}")))
            else:
                self._send(404, {"error": "not found"})
        except OSError as e:
            self._send(502, {"error": f"Couldn't reach the weather service ({e}). First lookup for a place needs internet."})
        except (KeyError, ValueError) as e:
            self._send(400, {"error": f"Bad request: {e}"})

    def do_POST(self):
        if self.path != "/api/brief":
            return self._send(404, {"error": "not found"})
        facts = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        try:
            for chunk in coach.stream_brief(facts):
                self.wfile.write(chunk.encode())
                self.wfile.flush()
        except (OSError, RuntimeError) as e:
            self.wfile.write(f"\n\n_(The local model isn't answering: {e}. Is Ollama running with {coach.MODEL}?)_".encode())


if __name__ == "__main__":
    print(f"Plot Twist on http://127.0.0.1:{PORT}  (model: {coach.MODEL})")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
