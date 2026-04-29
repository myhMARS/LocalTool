import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

from localtool.core import BaseTool


class LogHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_request(self, method: str):
        body = b""
        length = int(self.headers.get("Content-Length", 0))
        if length:
            body = self.rfile.read(length)

        print(f"[{method}] {self.path}")
        for k, v in self.headers.items():
            print(f"  {k}: {v}")
        if body:
            print()
            try:
                print(body.decode("utf-8"))
            except UnicodeDecodeError:
                print(body.hex(" "))
        print()

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def do_GET(self): self.do_request("GET")
    def do_POST(self): self.do_request("POST")
    def do_PUT(self): self.do_request("PUT")
    def do_DELETE(self): self.do_request("DELETE")
    def do_PATCH(self): self.do_request("PATCH")
    def do_HEAD(self): self.do_request("HEAD")
    def do_OPTIONS(self): self.do_request("OPTIONS")


class HttpdTool(BaseTool):
    name = "httpd"
    help = "HTTP server that logs all incoming requests"

    def run(self, args: list[str] | None = None) -> int:
        parser = self.make_parser()
        parser.add_argument("-p", "--port", type=int, default=8080)
        ns = self.parse(parser, args)
        if ns is None:
            return 1

        server = HTTPServer(("0.0.0.0", ns.port), LogHandler)
        print(f"listening on http://0.0.0.0:{ns.port}")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        return 0



run = HttpdTool.entry_point
