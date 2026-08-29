"""
FinGuard Frontend Server (Standalone)
Runs ONLY the frontend static web application on http://localhost:3000
"""
import http.server
import socketserver
import os
import sys

PORT = int(os.environ.get("PORT", 3000))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class FinGuardFrontendHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def do_GET(self):
        # Redirect root / to /static/index.html
        if self.path in ("/", "") or self.path.startswith("/?"):
            query = self.path[1:] if self.path.startswith("/?") else ""
            self.path = "/static/index.html" + query
        return super().do_GET()

def start_server():
    # Allow port reuse immediately
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), FinGuardFrontendHandler) as httpd:
        print(f"=======================================================")
        print(f"  FinGuard Frontend is running at: http://localhost:{PORT}")
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
