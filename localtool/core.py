import argparse
import sys
from abc import ABC


class BaseTool(ABC):
    name: str = ""
    help: str = ""
    _registry: dict[str, type["BaseTool"]] = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.name:
            BaseTool._registry[cls.name] = cls

    def run(self, args: list[str] | None = None) -> int:
        raise NotImplementedError

    @classmethod
    def entry_point(cls):
        inst = cls()
        return inst.run(None if len(sys.argv) <= 1 else sys.argv[1:])

    @staticmethod
    def get(name: str):
        cls = BaseTool._registry.get(name)
        if cls is None:
            return None
        return cls()

    @staticmethod
    def list_all() -> dict[str, str]:
        return {name: cls.help for name, cls in sorted(BaseTool._registry.items())}

    def make_parser(self) -> argparse.ArgumentParser:
        return argparse.ArgumentParser(
            prog=self.name,
            description=self.help,
            exit_on_error=False,
        )

    @staticmethod
    def parse(parser: argparse.ArgumentParser, args: list[str] | None) -> argparse.Namespace | None:
        try:
            return parser.parse_args(args)
        except (argparse.ArgumentError, SystemExit):
            return None
