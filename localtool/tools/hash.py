import hashlib
import sys

from localtool.core import BaseTool


class WinHashTool(BaseTool):
    name = "hash"
    help = "compute file hashes (default: md5)"

    def run(self, args: list[str] | None = None) -> int:
        parser = self.make_parser()
        parser.add_argument("-a", "--algorithm", default="md5",
                            help="hash algorithm (default: md5)")
        parser.add_argument("-f", "--file", action="append", default=[],
                            help="file to hash (repeatable)")
        parser.add_argument("-r", "--raw", action="append", default=[],
                            help="raw text to hash (repeatable)")
        parser.add_argument("-o", "--output",
                            help="write result to file")
        ns = self.parse(parser, args)
        if ns is None:
            return 1

        try:
            hashlib.new(ns.algorithm)
        except ValueError:
            print(f"error: unsupported algorithm '{ns.algorithm}'", file=sys.stderr)
            return 1

        results: list[str] = []

        for filepath in ns.file:
            try:
                with open(filepath, "rb") as f:
                    digest = self._compute_hash(f.read(), ns.algorithm)
                results.append(f"{ns.algorithm}: {digest}  {filepath}")
            except FileNotFoundError:
                print(f"error: file not found: {filepath}", file=sys.stderr)
                return 1
            except OSError as e:
                print(f"error: {filepath}: {e}", file=sys.stderr)
                return 1

        for t in ns.raw:
            digest = self._compute_hash(t.encode("utf-8"), ns.algorithm)
            results.append(f"{ns.algorithm}: {digest}")

        if not results:
            print("error: at least one file (-f) or text (-r) is required", file=sys.stderr)
            return 1

        output = "\n".join(results)
        if ns.output:
            with open(ns.output, "w") as f:
                f.write(output + "\n")
        else:
            print(output)

        return 0

    @staticmethod
    def _compute_hash(data: bytes, algorithm: str) -> str:
        h = hashlib.new(algorithm)
        h.update(data)
        return h.hexdigest()



run = WinHashTool.entry_point
