import base64
import sys

from localtool.core import BaseTool


class Base64Tool(BaseTool):
    name = "base64"
    help = "encode / decode base64 strings"

    def run(self, args: list[str] | None = None) -> int:
        parser = self.make_parser()
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("-e", "--encode", action="store_true",
                           help="encode to base64")
        group.add_argument("-d", "--decode", action="store_true",
                           help="decode from base64")
        parser.add_argument("-u", "--urlsafe", action="store_true",
                            help="use URL-safe alphabet")
        parser.add_argument("-f", "--file", action="append", default=[],
                            help="file to read (repeatable)")
        parser.add_argument("-o", "--output",
                            help="write result to file")
        parser.add_argument("text", nargs="*",
                            help="text to encode/decode")
        ns = self.parse(parser, args)
        if ns is None:
            return 1

        mode = "encode" if ns.encode else "decode"
        results: list[bytes] = []

        for filepath in ns.file:
            try:
                with open(filepath, "rb") as f:
                    raw = f.read()
                if mode == "encode":
                    enc = self._encode(raw, ns.urlsafe)
                    results.append(enc.encode("ascii"))
                else:
                    text = raw.decode("ascii").strip()
                    results.append(self._decode(text, ns.urlsafe))
            except FileNotFoundError:
                print(f"error: file not found: {filepath}", file=sys.stderr)
                return 1
            except OSError as e:
                print(f"error: {filepath}: {e}", file=sys.stderr)
                return 1
            except Exception as e:
                print(f"error: {filepath}: {e}", file=sys.stderr)
                return 1

        if ns.text:
            for text in ns.text:
                try:
                    if mode == "encode":
                        results.append(self._encode(text.encode("utf-8"), ns.urlsafe).encode("ascii"))
                    else:
                        results.append(self._decode(text, ns.urlsafe))
                except Exception as e:
                    print(f"error: {e}", file=sys.stderr)
                    return 1

        if not ns.text and not ns.file:
            if not sys.stdin.isatty():
                raw = sys.stdin.buffer.read()
                try:
                    if mode == "encode":
                        results.append(self._encode(raw, ns.urlsafe).encode("ascii"))
                    else:
                        text = raw.decode("ascii").strip()
                        results.append(self._decode(text, ns.urlsafe))
                except Exception as e:
                    print(f"error: {e}", file=sys.stderr)
                    return 1
            else:
                print("error: no input provided", file=sys.stderr)
                return 1

        if ns.output:
            try:
                with open(ns.output, "wb") as f:
                    f.write(b"\n".join(results))
            except OSError as e:
                print(f"error: {ns.output}: {e}", file=sys.stderr)
                return 1
        else:
            for data in results:
                sys.stdout.buffer.write(data + b"\n")
                sys.stdout.buffer.flush()

        return 0

    @staticmethod
    def _encode(data: bytes, urlsafe: bool) -> str:
        if urlsafe:
            return base64.urlsafe_b64encode(data).decode("ascii")
        return base64.b64encode(data).decode("ascii")

    @staticmethod
    def _decode(text: str, urlsafe: bool) -> bytes:
        data = text.encode("ascii")
        if urlsafe:
            return base64.urlsafe_b64decode(data + b"==")
        return base64.b64decode(data)



run = Base64Tool.entry_point
