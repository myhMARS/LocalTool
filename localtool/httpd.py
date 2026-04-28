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
        if args is None:
            args = sys.argv[1:]

        port = 8080

        it = iter(args)
        for arg in it:
            if arg in ("-p", "--port"):
                try:
                    port = int(next(it))
                except StopIteration:
                    print("error: -p requires a port number", file=sys.stderr)
                    return 1
            elif arg in ("-h", "--help"):
                print("usage: httpd [-p PORT]")
                return 0
            else:
                print(f"error: unknown argument '{arg}'", file=sys.stderr)
                return 1

        server = HTTPServer(("0.0.0.0", port), LogHandler)
        print(f"listening on http://0.0.0.0:{port}")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        return 0


run = HttpdTool.entry_point
