import json
import os
import sys
import urllib.request

from localtool.core import BaseTool


class DeepSeekTool(BaseTool):
    name = "deepseek"
    help = "query DeepSeek API account balance"

    BASE = "https://api.deepseek.com"

    def run(self, args: list[str] | None = None) -> int:
        if not args:
            args = []

        api_key = None

        it = iter(args)
        for arg in it:
            if arg in ("-k", "--key"):
                try:
                    api_key = next(it)
                except StopIteration:
                    print("error: -k requires an API key", file=sys.stderr)
                    return 1
            elif arg in ("-h", "--help"):
                self._usage()
                return 0
            elif arg.startswith("-"):
                print(f"error: unknown flag '{arg}'", file=sys.stderr)
                return 1

        if api_key is None:
            api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            print("error: no API key provided (use -k or set DEEPSEEK_API_KEY)", file=sys.stderr)
            return 1

        balance = self._fetch_balance(api_key)
        if balance is None:
            return 1

        print("DeepSeek Account")
        print("-" * 40)
        self._print_balance(balance)
        return 0

    def _fetch_balance(self, api_key: str) -> list[dict] | None:
        try:
            req = urllib.request.Request(f"{self.BASE}/user/balance")
            req.add_header("Authorization", f"Bearer {api_key}")
            req.add_header("Accept", "application/json")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")
            print(f"error: HTTP {e.code}: {body}", file=sys.stderr)
            return None
        except Exception as e:
            print(f"error: request failed: {e}", file=sys.stderr)
            return None

        return data.get("balance_infos", [])

    def _print_balance(self, balance: list[dict]):
        for item in balance:
            currency = item.get("currency", "unknown")
            total = float(item.get("total_balance", 0))
            topped_up = float(item.get("topped_up_balance", 0))
            granted = float(item.get("granted_balance", 0))

            print(f"  Currency:       {currency}")
            print(f"  Total Balance:  {total:.2f}")
            print(f"    └─ Topped up: {topped_up:.2f}")
            print(f"    └─ Granted:   {granted:.2f}")

    @staticmethod
    def _usage():
        print("usage: deepseek [-k <key>]", file=sys.stderr)
        print("  -k, --key   API key (default: $DEEPSEEK_API_KEY)", file=sys.stderr)
        print(file=sys.stderr)
        print("  export DEEPSEEK_API_KEY=sk-xxx", file=sys.stderr)
        print("  deepseek", file=sys.stderr)


run = DeepSeekTool.entry_point