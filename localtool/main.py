import importlib
import pkgutil
import sys

import localtool
import localtool.tools
from localtool.core import BaseTool


def _import_tools():
    for _, modname, _ in pkgutil.iter_modules(localtool.__path__):
        if modname in ("tools",):
            continue
        if modname in ("main", "core"):
            continue
        importlib.import_module(f"localtool.{modname}")

    for _, modname, _ in pkgutil.iter_modules(localtool.tools.__path__):
        importlib.import_module(f"localtool.tools.{modname}")


def main() -> int:
    _import_tools()

    if len(sys.argv) < 2:
        print("usage: localtool <command> [args...]", file=sys.stderr)
        for name, help_text in BaseTool.list_all().items():
            print(f"  {name:<12} {help_text}", file=sys.stderr)
        return 1

    command = sys.argv[1]
    tool = BaseTool.get(command)
    if tool is None:
        print(f"error: unknown command '{command}'", file=sys.stderr)
        for name, help_text in BaseTool.list_all().items():
            print(f"  {name:<12} {help_text}", file=sys.stderr)
        return 1

    return tool.run(sys.argv[2:])
