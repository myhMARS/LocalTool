import os
import stat
import sys
import time

from localtool.core import BaseTool


class LlTool(BaseTool):
    name = "ll"
    help = "list files with details (like ls -lah)"

    def run(self, args: list[str] | None = None) -> int:
        parser = self.make_parser()
        parser.add_argument("path", nargs="?", default=".")
        ns = self.parse(parser, args)
        if ns is None:
            return 1

        path = ns.path
        if not os.path.exists(path):
            print(f"error: {path}: no such file or directory", file=sys.stderr)
            return 1

        if os.path.isfile(path):
            st = os.stat(path)
            mtime = time.strftime("%b %d %H:%M", time.localtime(st.st_mtime))
            print(f"{self._mode_str(st.st_mode)} {self._size_str(st.st_size):>5} {mtime} {path}")
            return 0

        entries = os.listdir(path)
        total_blocks = 0
        rows: list[tuple[str, str, str, str]] = []

        for name in sorted(entries, key=lambda n: n.lstrip(".").lower()):
            full = os.path.join(path, name)
            try:
                st = os.lstat(full)
            except OSError:
                continue
            total_blocks += (st.st_size + 511) // 512
            mtime = time.strftime("%b %d %H:%M", time.localtime(st.st_mtime))
            rows.append((self._mode_str(st.st_mode), self._size_str(st.st_size), mtime, name))

        print(f"total {total_blocks}")
        for mode, size, mtime, name in rows:
            print(f"{mode} {size:>5} {mtime} {name}")
        return 0

    @staticmethod
    def _mode_str(mode: int) -> str:
        m = "d" if stat.S_ISDIR(mode) else "-"
        for shift in (6, 3, 0):
            m += "r" if mode & (4 << shift) else "-"
            m += "w" if mode & (2 << shift) else "-"
            m += "x" if mode & (1 << shift) else "-"
        return m

    @staticmethod
    def _size_str(size: int) -> str:
        for unit in ("B", "K", "M", "G", "T"):
            if abs(size) < 1024:
                return f"{size:>4}{unit}"
            size //= 1024
        return f"{size:>4}P"



run = LlTool.entry_point
