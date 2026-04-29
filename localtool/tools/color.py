import re
import sys

from localtool.core import BaseTool


class ColorTool(BaseTool):
    name = "color"
    help = "display a color block from RGB or hex (#xxxxxx) input"

    def run(self, args: list[str] | None = None) -> int:
        parser = self.make_parser()
        parser.add_argument("color", nargs="+", help="hex (#ff0000) or RGB (255,0,0)")
        ns = self.parse(parser, args)
        if ns is None:
            return 1

        input_str = " ".join(ns.color)
        r, g, b = self._parse(input_str)
        if r is None:
            print(f"error: cannot parse color '{input_str}'", file=sys.stderr)
            return 1

        self._show_color(r, g, b)
        return 0

    def _parse(self, s: str) -> tuple[int | None, int | None, int | None]:
        s = s.strip()

        hex_match = re.match(r"^#?([0-9a-fA-F]{6})$", s)
        if hex_match:
            h = hex_match.group(1)
            return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

        rgb_match = re.match(r"^rgb\s*\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)$", s)
        if rgb_match:
            return (
                self._clamp(rgb_match.group(1)),
                self._clamp(rgb_match.group(2)),
                self._clamp(rgb_match.group(3)),
            )

        num_match = re.match(r"^(\d{1,3})\s*[, ]\s*(\d{1,3})\s*[, ]\s*(\d{1,3})$", s)
        if num_match:
            return (
                self._clamp(num_match.group(1)),
                self._clamp(num_match.group(2)),
                self._clamp(num_match.group(3)),
            )

        return None, None, None

    @staticmethod
    def _clamp(v: str | int) -> int:
        return max(0, min(255, int(v)))

    @staticmethod
    def _show_color(r: int, g: int, b: int) -> None:
        block = "  "
        reset = "\033[0m"
        bg = f"\033[48;2;{r};{g};{b}m"

        line = bg + block * 10 + reset
        print(line)
        print(line)
        print(line)

        print(f"HEX: #{r:02x}{g:02x}{b:02x}")
        print(f"RGB: ({r}, {g}, {b})")


run = ColorTool.entry_point
