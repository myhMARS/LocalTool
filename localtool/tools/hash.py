import hashlib
import sys

from localtool.core import BaseTool


class WinHashTool(BaseTool):
    name = "hash"
    help = "compute file hashes (default: md5)"

    def run(self, args: list[str] | None = None) -> int:
        if args is None:
            args = sys.argv[1:]

        algorithm = "md5"
        files: list[str] = []
        texts: list[str] = []
        output_file: str | None = None

        it = iter(args)
        for arg in it:
            if arg in ("-a", "--algorithm"):
                try:
                    algorithm = next(it)
                except StopIteration:
                    print("error: --algorithm requires a value", file=sys.stderr)
                    return 1
            elif arg.startswith("--algorithm="):    
                algorithm = arg.split("=", 1)[1]
            elif arg in ("-f", "--file"):
                try:
                    files.append(next(it))
                except StopIteration:
                    print("error: -f requires a file path", file=sys.stderr)
                    return 1
            elif arg in ("-r", "--raw"):
                try:
                    texts.append(next(it))
                except StopIteration:
                    print("error: -r requires text input", file=sys.stderr)
                    return 1
            elif arg in ("-o", "--output"):
                try:
                    output_file = next(it)
                except StopIteration:
                    print("error: -o requires a file path", file=sys.stderr)
                    return 1
            elif arg in ("-h", "--help"):
                print("usage: hash [-a ALGORITHM] -f <file> [...] [-r <text>] [-o <output>]")
                return 0
            else:
                print(f"error: unknown argument '{arg}'", file=sys.stderr)
                return 1

        try:
            hashlib.new(algorithm)
        except ValueError:
            print(f"error: unsupported algorithm '{algorithm}'", file=sys.stderr)
            return 1

        results: list[str] = []

        for filepath in files:
            try:
                with open(filepath, "rb") as f:
                    digest = self._compute_hash(f.read(), algorithm)
                results.append(f"{algorithm}: {digest}  {filepath}")
            except FileNotFoundError:
                print(f"error: file not found: {filepath}", file=sys.stderr)
                return 1
            except OSError as e:
                print(f"error: {filepath}: {e}", file=sys.stderr)
                return 1

        for t in texts:
            digest = self._compute_hash(t.encode("utf-8"), algorithm)
            results.append(f"{algorithm}: {digest}")

        if not results:
            print("error: at least one file (-f) or text (-r) is required", file=sys.stderr)
            return 1

        output = "\n".join(results)
        if output_file:
            with open(output_file, "w") as f:
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
