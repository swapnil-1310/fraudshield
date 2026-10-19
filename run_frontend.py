"""
FinGuard Frontend Server (Standalone)
Runs the frontend static web application on http://localhost:3000 with SPA routing
and transparent API reverse proxying to http://localhost:8000.
"""
import http.server
import socketserver
import os
import sys
import urllib.request
import urllib.error

PORT = int(os.environ.get("PORT", 3000))
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000").rstrip("/")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class FinGuardFrontendHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def do_GET(self):
        # Forward API requests directly to backend server
        if self.path.startswith("/api/"):
            return self._proxy_request("GET")

        # Handle SPA client-side routes: serve /static/index.html
        clean_path = self.path.split("?")[0]
        full_path = os.path.join(BASE_DIR, clean_path.lstrip("/"))

        if clean_path in ("/", "") or not os.path.exists(full_path):
            self.path = "/static/index.html"

        return super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api/"):
            return self._proxy_request("POST")
        self.send_error(405, "Method Not Allowed")

    def _proxy_request(self, method):
        target_url = f"{BACKEND_URL}{self.path}"
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else None

        req_headers = {}
        for key, val in self.headers.items():
            if key.lower() not in ("host", "connection", "content-length"):
                req_headers[key] = val

        try:
            req = urllib.request.Request(target_url, data=body, headers=req_headers, method=method)
            with urllib.request.urlopen(req, timeout=120) as resp:
                self.send_response(resp.status)
                for header_key, header_val in resp.getheaders():
                    if header_key.lower() not in ("transfer-encoding", "content-length", "connection"):
                        self.send_header(header_key, header_val)
                resp_data = resp.read()
                self.send_header("Content-Length", str(len(resp_data)))
                self.end_headers()
                self.wfile.write(resp_data)
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            for header_key, header_val in e.headers.items():
                if header_key.lower() not in ("transfer-encoding", "content-length", "connection"):
                    self.send_header(header_key, header_val)
            err_data = e.read()
            self.send_header("Content-Length", str(len(err_data)))
            self.end_headers()
            self.wfile.write(err_data)
        except Exception as e:
            self.send_error(502, f"Failed to connect to backend service at {BACKEND_URL}: {e}")

def start_server():
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), FinGuardFrontendHandler) as httpd:
        print(f"=======================================================")
        print(f"  FinGuard Frontend is running at: http://localhost:{PORT}")
        print(f"  Backend API target: {BACKEND_URL}")
        print(f"  Root serving from: {BASE_DIR}")
        print(f"  Press Ctrl+C to stop the server")
        print(f"=======================================================")
        sys.stdout.flush()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down frontend server.")

if __name__ == "__main__":
    start_server()
