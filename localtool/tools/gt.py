import os
import subprocess
import sys

from localtool.core import BaseTool

_DIR = "\033[34m"
_LINE = "\033[90m"
_ROOT = "\033[1;36m"
_RESET = "\033[0m"


class GtTool(BaseTool):
    name = "gt"
    help = "show directory tree of git-tracked files"

    def run(self, args: list[str] | None = None) -> int:
        parser = self.make_parser()
        if self.parse(parser, args) is None:
            return 1

        try:
            result = subprocess.run(
                ["git", "ls-files"],
                capture_output=True, text=True, check=True,
            )
        except subprocess.CalledProcessError as e:
            print(f"error: git ls-files failed: {e.stderr.strip()}", file=sys.stderr)
            return 1
        except FileNotFoundError:
            print("error: git not found", file=sys.stderr)
            return 1

        paths = [p.strip() for p in result.stdout.strip().splitlines() if p.strip()]
        if not paths:
            print("no tracked files")
            return 0

        root = os.path.basename(os.getcwd())
        if sys.stdout.isatty():
            print(f"{_ROOT}{root}{_RESET}")
        else:
            print(root)
        tree = self._build_tree(paths)
        self._print_tree(tree)
        return 0

    @staticmethod
    def _build_tree(paths: list[str]) -> dict:
        root: dict = {}
        for p in paths:
            parts = p.replace("\\", "/").split("/")
            node = root
            for part in parts:
                node = node.setdefault(part, {})
        return root

    @classmethod
    def _print_tree(cls, node: dict, prefix: str = "", is_last: bool = True, name: str = ""):
        tty = sys.stdout.isatty()
        _l = _LINE if tty else ""
        _r = _RESET if tty else ""

        if name:
            connector = "└── " if is_last else "├── "
            print(f"{_l}{prefix}{_r}{_l}{connector}{_r}{_DIR if tty else ''}{name}{_RESET if tty else ''}")
            new_prefix = prefix + ("    " if is_last else "│   ")
        else:
            new_prefix = ""

        items = sorted(node.items(), key=lambda x: (bool(x[1]), x[0].lower()))
        for i, (key, children) in enumerate(items):
            last = i == len(items) - 1
            if children:
                cls._print_tree(children, new_prefix, last, key)
            else:
                connector = "└── " if last else "├── "
                print(f"{_l}{new_prefix}{_r}{_l}{connector}{_r}{key}")


run = GtTool.entry_point
