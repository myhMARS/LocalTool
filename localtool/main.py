import sys

from localtool.core import BaseTool


def main() -> int:
    BaseTool.discover()

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
