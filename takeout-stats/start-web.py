#!/usr/bin/env python3
import argparse
import http.server
import socketserver
import json
import os
import threading
import webbrowser
from pathlib import Path

PORT = 9000
DATA_DIR = "data"

class CustomHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()

    def do_GET(self):
        if self.path in ('/', '/index.html'):
            self.path = '/app.html'

        if self.path == '/api/list-json':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()

            json_files = []
            data_path = Path(DATA_DIR)
            if data_path.exists():
                json_files = [f.name for f in data_path.glob("*.json")]

            self.wfile.write(json.dumps(json_files).encode())
            return

        super().do_GET()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Serve the mail viewer app")
    parser.add_argument("--no-browser", action="store_true",
                        help="do not open the default browser")
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()

    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    url = f"http://localhost:{args.port}/"
    print(f"Server running at {url}")
    if not args.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()

    with socketserver.TCPServer(("", args.port), CustomHandler) as httpd:
        httpd.serve_forever()
