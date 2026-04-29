import argparse
import sys
from abc import ABC
from importlib.metadata import entry_points


EP_GROUP = "localtool.tools"


class BaseTool(ABC):
    name: str = ""
    help: str = ""
    _registry: dict[str, type["BaseTool"]] = {}
    _discovered: bool = False

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
    def discover():
        """Discover and register all tools.

        1. Try ``importlib.metadata`` entry-points (works after install).
        2. Fall back to ``pkgutil`` scan (works during development without
           reinstalling after adding a new tool file).

        Idempotent — safe to call multiple times.
        """
        if BaseTool._discovered:
            return

        # ── entry-points (installed tools) ──
        for ep in entry_points(group=EP_GROUP):
            try:
                ep.load()
            except Exception as exc:
                pass

        # ── pkgutil scan (development — catches new files without reinstalling) ──
        BaseTool._discover_pkgutil()

        BaseTool._discovered = True

    @staticmethod
    def _discover_pkgutil():
        """Import all modules under localtool/tools/ and localtool/ via pkgutil."""
        import importlib
        import pkgutil
        import localtool.tools
        import localtool

        for _, modname, _ in pkgutil.iter_modules(localtool.tools.__path__):
            try:
                importlib.import_module(f"localtool.tools.{modname}")
            except Exception:
                pass

        for _, modname, _ in pkgutil.iter_modules(localtool.__path__):
            try:
                importlib.import_module(f"localtool.{modname}")
            except Exception:
                pass

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
