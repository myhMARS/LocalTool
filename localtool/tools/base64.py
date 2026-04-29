import base64
import sys

from localtool.core import BaseTool


class Base64Tool(BaseTool):
    name = "base64"
    help = "encode / decode base64 strings"

    def run(self, args: list[str] | None = None) -> int:
        if not args:
            self._usage()
            return 1

        mode = None
        urlsafe = False
        files: list[str] = []
        output_file: str | None = None
        items: list[str] = []

        it = iter(args)
        for arg in it:
            if arg in ("-e", "--encode"):
                mode = "encode"
            elif arg in ("-d", "--decode"):
                mode = "decode"
            elif arg in ("-u", "--urlsafe"):
                urlsafe = True
            elif arg in ("-f", "--file"):
                try:
                    files.append(next(it))
                except StopIteration:
                    print("error: -f requires a file path", file=sys.stderr)
                    return 1
            elif arg in ("-o", "--output"):
                try:
                    output_file = next(it)
                except StopIteration:
                    print("error: -o requires a file path", file=sys.stderr)
                    return 1
            elif arg in ("-h", "--help"):
                self._usage()
                return 0
            elif arg.startswith("-"):
                print(f"error: unknown flag '{arg}'", file=sys.stderr)
                return 1
            else:
                items.append(arg)

        if mode is None:
            print("error: must specify -e (encode) or -d (decode)", file=sys.stderr)
            return 1

        results: list[bytes] = []

        for filepath in files:
            try:
                with open(filepath, "rb") as f:
                    raw = f.read()
                if mode == "encode":
                    enc = self._encode(raw, urlsafe)
                    results.append(enc.encode("ascii"))
                else:
                    text = raw.decode("ascii").strip()
                    results.append(self._decode(text, urlsafe))
            except FileNotFoundError:
                print(f"error: file not found: {filepath}", file=sys.stderr)
                return 1
            except OSError as e:
                print(f"error: {filepath}: {e}", file=sys.stderr)
                return 1
            except Exception as e:
                print(f"error: {filepath}: {e}", file=sys.stderr)
                return 1

        if items:
            for text in items:
                try:
                    if mode == "encode":
                        results.append(self._encode(text.encode("utf-8"), urlsafe).encode("ascii"))
                    else:
                        results.append(self._decode(text, urlsafe))
                except Exception as e:
                    print(f"error: {e}", file=sys.stderr)
                    return 1

        if not items and not files:
            if not sys.stdin.isatty():
                raw = sys.stdin.buffer.read()
                try:
                    if mode == "encode":
                        results.append(self._encode(raw, urlsafe).encode("ascii"))
                    else:
                        text = raw.decode("ascii").strip()
                        results.append(self._decode(text, urlsafe))
                except Exception as e:
                    print(f"error: {e}", file=sys.stderr)
                    return 1
            else:
                print("error: no input provided", file=sys.stderr)
                return 1

        if output_file:
            try:
                with open(output_file, "wb") as f:
                    f.write(b"\n".join(results))
            except OSError as e:
                print(f"error: {output_file}: {e}", file=sys.stderr)
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

    @staticmethod
    def _usage():
        print("usage: base64 -e|-d [-u] [-f <file>] [-o <output>] [text...]", file=sys.stderr)
        print("  -e, --encode   encode to base64", file=sys.stderr)
        print("  -d, --decode   decode from base64", file=sys.stderr)
        print("  -u, --urlsafe  use URL-safe alphabet", file=sys.stderr)
        print("  -f, --file     file to read (repeatable)", file=sys.stderr)
        print("  -o, --output   write result to file", file=sys.stderr)
        print(file=sys.stderr)
        print("  base64 -e hello                  # text from args", file=sys.stderr)
        print("  base64 -e -f photo.png           # encode file", file=sys.stderr)
        print("  base64 -e -f photo.png -o out.txt  # save to file", file=sys.stderr)
        print("  base64 -d -f encoded.txt         # decode file", file=sys.stderr)
        print("  echo foo | base64 -e             # stdin", file=sys.stderr)


run = Base64Tool.entry_point