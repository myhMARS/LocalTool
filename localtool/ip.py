import json
import socket
import sys
import urllib.request

from localtool.core import BaseTool


class IpTool(BaseTool):
    name = "ip"
    help = "show public and local IP with geolocation"

    def run(self, args: list[str] | None = None) -> int:
        try:
            req = urllib.request.Request("http://ip-api.com/json/?lang=zh-CN")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
        except Exception as e:
            print(f"error: request failed: {e}", file=sys.stderr)
            return 1

        if data.get("status") != "success":
            print(f"error: {data.get('message', 'unknown error')}", file=sys.stderr)
            return 1

        print(f"内网IP: {self._get_local_ip()}")
        print(f"公网IP: {data['query']}")
        print(f"地址: {data['country']} {data['regionName']} {data['city']}")
        print(f"ISP: {data['isp']}")
        return 0

    @staticmethod
    def _get_local_ip() -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("114.114.114.114", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except OSError:
            return "unknown"


run = IpTool.entry_point
