import json
import os
import shutil
import sys
from pathlib import Path

from localtool.core import BaseTool


def _shorten(path: str) -> str:
    home = str(Path.home())
    if path.startswith(home):
        return "~" + path[len(home):]
    return path


# ── Shell integration snippets for `pj setup` ────────────────────────
_MARKER = "# pj shell integration — managed by `pj setup`"

_PWSH_WRAPPER = f"""\
{_MARKER}
function global:pj {{
    if ($args[0] -eq 'go' -or $args.Count -eq 0) {{
        $dir = & pj.exe @args
        if ($LASTEXITCODE -eq 0 -and $dir) {{ Set-Location $dir }}
    }} else {{
        & pj.exe @args
    }}
}}
Register-ArgumentCompleter -CommandName pj -ScriptBlock {{
    param($word, $ast, $pos)
    $words = $ast.CommandElements | %{{ $_.ToString().Trim('"','''') }}
    if ($words.Count -eq 2) {{
        @('add','go','remove','setup','list') | ?{{ $_ -like "$word*" }}
    }} elseif ($words.Count -eq 3 -and $words[1] -in 'go','remove') {{
        & pj.exe list 2>$null | ?{{ $_ -like "$word*" }}
    }}
}}"""

_BASH_WRAPPER = f"""\
{_MARKER}
pj() {{
    if [[ "$1" == "go" || $# -eq 0 ]]; then
        local dir
        dir=$(pj "$@") && [[ -n "$dir" ]] && cd "$dir"
    else
        pj "$@"
    fi
}}
_pj_complete() {{
    local cur prev words cword
    _init_completion 2>/dev/null || {{ cur="${{COMP_WORDS[COMP_CWORD]}}"; prev="${{COMP_WORDS[COMP_CWORD-1]}}"; }}
    if [[ $COMP_CWORD -eq 1 ]]; then
        COMPREPLY=($(compgen -W "add go remove setup list" -- "$cur"))
    elif [[ $COMP_CWORD -eq 2 ]] && [[ "$prev" =~ ^(go|remove)$ ]]; then
        COMPREPLY=($(compgen -W "$(pj list 2>/dev/null)" -- "$cur"))
    fi
}}
complete -F _pj_complete pj"""

_ZSH_WRAPPER = f"""\
{_MARKER}
pj() {{
    if [[ "$1" == "go" || $# -eq 0 ]]; then
        local dir
        dir=$(pj "$@") && [[ -n "$dir" ]] && cd "$dir"
    else
        pj "$@"
    fi
}}
_pj() {{
    local -a commands; commands=('add:bookmark' 'go:jump' 'remove:unbookmark' 'setup:install' 'list:list')
    if (( CURRENT == 2 )); then
        _describe 'command' commands
    elif (( CURRENT == 3 )); then
        case $words[2] in
            go|remove) local -a projects; projects=(${{(f)"$(pj list 2>/dev/null)"}}); _describe 'project' projects ;;
        esac
    fi
}}
compdef _pj pj"""

_FISH_WRAPPER = f"""\
{_MARKER}
function pj
    if test "$argv[1]" = go -o (count $argv) -eq 0
        set dir (pj $argv)
        test -n "$dir" -a -d "$dir" && cd "$dir"
    else
        pj $argv
    end
end
complete -c pj -f -n 'test (count (commandline -opc)) -eq 1' -a 'add go remove setup list'
complete -c pj -f -n 'test (count (commandline -opc)) -eq 2; and contains (commandline -opc)[2] go remove' -a '(pj list 2>/dev/null)'"""

_WRAPPERS: dict[str, str] = {
    "powershell": _PWSH_WRAPPER,
    "bash": _BASH_WRAPPER,
    "zsh": _ZSH_WRAPPER,
    "fish": _FISH_WRAPPER,
}


def _ps_profile() -> str:
    """Best-effort PowerShell profile path.

    Tries the 7+ path (PowerShell) first, then falls back to 5.x
    (WindowsPowerShell).
    """
    for ver in ("PowerShell", "WindowsPowerShell"):
        p = str(Path.home() / "Documents" / ver / "Microsoft.PowerShell_profile.ps1")
        if Path(p).parent.exists():
            return p
    return str(Path.home() / "Documents" / "PowerShell" / "Microsoft.PowerShell_profile.ps1")


_PROFILES: dict[str, str] = {
    "powershell": os.environ.get("PROFILE") or _ps_profile(),
    "bash": str(Path.home() / ".bashrc"),
    "zsh": str(Path.home() / ".zshrc"),
    "fish": str(Path.home() / ".config" / "fish" / "config.fish"),
}

# ── ANSI escape helpers ──────────────────────────────────────────────
_ESC = "\033"
_CSI = f"{_ESC}["
_SGR = lambda *cs: f"{_CSI}{';'.join(map(str, cs))}m"
_R = _SGR(0)  # reset
_B = _SGR(1)  # bold
_D = _SGR(2)  # dim
_FG_C = _SGR(36)  # cyan
_FG_W = _SGR(37)  # white
_FG_k = _SGR(90)  # gray
_BG_b = _SGR(44)  # blue bg


def _vis_len(s: str) -> int:
    """Visible length — strip ANSI escape sequences."""
    import re
    return len(re.sub(r"\033\[[0-9;]*m", "", s))


# ── Cross-platform raw-key reader (stdlib only) ─────────────────────

class _Key:
    UP = "up"
    DOWN = "down"
    ENTER = "enter"
    ESC = "escape"
    QUIT = "quit"


class _KeyReader:
    """Context manager — puts terminal in raw mode, yields key events."""

    def __init__(self):
        self._win = sys.platform == "win32"
        self._fd = sys.stdin.fileno()
        self._saved = None

    def __enter__(self):
        if not self._win:
            import termios
            import tty
            self._saved = termios.tcgetattr(self._fd)
            tty.setraw(self._fd)
        return self

    def __exit__(self, *_):
        if not self._win and self._saved is not None:
            import termios
            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._saved)

    def _read(self, n: int = 1) -> bytes:
        if self._win:
            import msvcrt
            return msvcrt.getch()
        return os.read(self._fd, n)

    def get(self) -> str:
        b = self._read(1)
        if self._win:
            if b in (b"\xe0", b"\x00"):
                b2 = self._read(1)
                return {b"H": _Key.UP, b"P": _Key.DOWN}.get(b2, "")
            if b == b"\x03":
                raise KeyboardInterrupt
            s = b.decode("utf-8", errors="replace")
            if s == "\r":
                return _Key.ENTER
            if s == "\x1b":
                return _Key.ESC
            if s.lower() == "q":
                return _Key.QUIT
            return s
        if b == b"\x03":
            raise KeyboardInterrupt
        if b == b"\x1b":
            import select
            if select.select([sys.stdin], [], [], 0.01)[0]:
                b2 = os.read(self._fd, 1)
                if b2 == b"[":
                    b3 = os.read(self._fd, 1)
                    return {b"A": _Key.UP, b"B": _Key.DOWN}.get(b3, "")
            return _Key.ESC
        if b == b"\r":
            return _Key.ENTER
        s = b.decode("utf-8", errors="replace")
        if s.lower() == "q":
            return _Key.QUIT
        return s


# ── Interactive menu ─────────────────────────────────────────────────

def _menu_select(names: list[str], paths: list[str]) -> int | None:
    """Draw an ANSI-styled picker, return *index* or ``None`` (cancelled).

    All rendering goes to **stderr** so the shell wrapper can safely
    capture stdout for the final directory path.
    """
    total = len(names)
    tw = shutil.get_terminal_size().columns
    num_w = len(str(total))
    idx = 0

    def _render():
        out: list[str] = []
        hdr = f"{_B}{_FG_C} pj {_R}{_FG_W}— select a project"
        hint = f"{_D}{_FG_k}  ↑↓/jk  ↵  q quit{_R}"
        out.append(hdr + " " * max(0, tw - _vis_len(hdr) - _vis_len(hint)) + hint)
        out.append(f"{_D}{_FG_k}{'─' * tw}{_R}")
        for i, (name, path) in enumerate(zip(names, paths)):
            num = f"{i + 1:>{num_w}}"
            if i == idx:
                out.append(
                    f"{_BG_b}{_B}{_FG_W} ▶ {num}  {name}  "
                    f"{_shorten(path)}{_R}"
                )
            else:
                out.append(
                    f"   {num}  {_FG_C}{name}{_R}  "
                    f"{_D}{_FG_k}{_shorten(path)}{_R}"
                )
        out.append(f"{_D}{_FG_k}{'─' * tw}{_R}")
        return "\n".join(out)

    _e = sys.stderr

    _e.write(f"{_CSI}?25l")
    _e.write(f"{_CSI}2J{_CSI}H")
    _e.write(_render())
    _e.flush()

    try:
        with _KeyReader() as kr:
            while True:
                k = kr.get()
                if k in (_Key.UP, "k"):
                    idx = (idx - 1) % total
                elif k in (_Key.DOWN, "j"):
                    idx = (idx + 1) % total
                elif k == _Key.ENTER:
                    break
                elif k in (_Key.ESC, _Key.QUIT):
                    idx = -1
                    break
                elif k.isdigit():
                    n = int(k)
                    if 1 <= n <= min(total, 9):
                        idx = n - 1
                        break
                else:
                    continue
                _e.write(f"{_CSI}{total + 3}A")
                _e.write(_render())
                _e.flush()
    except (KeyboardInterrupt, EOFError):
        idx = -1
    finally:
        _e.write(f"{_CSI}?25h\n")
        _e.flush()

    return None if idx < 0 else idx


# ── Tool ──────────────────────────────────────────────────────────────

class PjTool(BaseTool):
    name = "pj"
    help = "bookmark and jump to project directories"

    @property
    def _data_file(self) -> Path:
        p = Path.home() / ".localtool" / "projects.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def _load(self) -> dict[str, str]:
        try:
            return json.loads(self._data_file.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save(self, data: dict[str, str]) -> None:
        self._data_file.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8",
        )

    # ── run ──────────────────────────────────────────────────────────

    def run(self, args: list[str] | None = None) -> int:
        parser = self.make_parser()
        sub = parser.add_subparsers(dest="command")

        ap = sub.add_parser("add", help="bookmark current directory as <name>")
        ap.add_argument("name", help="project name")

        gp = sub.add_parser("go", help="print saved directory for <name>")
        gp.add_argument("name", help="project name")

        rp = sub.add_parser("remove", help="remove a bookmarked project")
        rp.add_argument("name", help="project name")

        sp = sub.add_parser("setup", help="install shell wrapper with tab completion")
        sp.add_argument("--shell", choices=["powershell", "bash", "zsh", "fish"],
                        help="override shell detection")

        sub.add_parser("list", help="list all saved project names")

        ns = self.parse(parser, args)
        if ns is None:
            return 1

        data = self._load()

        if ns.command == "add":
            return self._add(data, ns.name)
        elif ns.command == "go":
            return self._go(data, ns.name)
        elif ns.command == "remove":
            return self._remove(data, ns.name)
        elif ns.command == "list":
            return self._list(data)
        elif ns.command == "setup":
            return self._setup(ns.shell)
        else:
            return self._interactive(data)

    # ── commands ──────────────────────────────────────────────────────

    def _add(self, data: dict[str, str], name: str) -> int:
        data[name] = str(Path.cwd())
        self._save(data)
        print(f"pj: added '{name}' -> {_shorten(data[name])}")
        return 0

    def _go(self, data: dict[str, str], name: str) -> int:
        if name not in data:
            print(f"error: project '{name}' not found", file=sys.stderr)
            return 1
        print(data[name])
        return 0

    def _remove(self, data: dict[str, str], name: str) -> int:
        if name not in data:
            print(f"error: project '{name}' not found", file=sys.stderr)
            return 1
        del data[name]
        self._save(data)
        print(f"pj: removed '{name}'")
        return 0

    @staticmethod
    def _list(data: dict[str, str]) -> int:
        if not data:
            return 0
        for name in data:
            print(name)
        return 0

    # ── setup ────────────────────────────────────────────────────────

    @staticmethod
    def _setup(shell: str | None) -> int:
        if shell is None:
            shell = PjTool._detect_shell()
        wrapper = _WRAPPERS.get(shell)
        profile = Path(_PROFILES.get(shell, ""))
        if wrapper is None:
            print(f"error: unsupported shell '{shell}'", file=sys.stderr)
            return 1

        # Read existing profile content
        try:
            content = profile.read_text(encoding="utf-8")
        except FileNotFoundError:
            content = ""

        if _MARKER in content:
            before = content[:content.index(_MARKER)].strip()
            action = "updated"
        else:
            before = content.strip()
            action = "installed"

        profile.parent.mkdir(parents=True, exist_ok=True)
        profile.write_text(before + "\n\n" + wrapper + "\n", encoding="utf-8",
                           newline="\n")
        print(f"pj: {action} shell integration in {_shorten(str(profile))}")
        print(f"    restart your shell, or run:  . {profile}")
        return 0

    @staticmethod
    def _detect_shell() -> str:
        if sys.platform == "win32":
            return "powershell"
        shell_path = os.environ.get("SHELL", "")
        if "zsh" in shell_path:
            return "zsh"
        if "fish" in shell_path:
            return "fish"
        return "bash"

    # ── interactive ──────────────────────────────────────────────────

    def _interactive(self, data: dict[str, str]) -> int:
        if not data:
            print("pj: no projects saved", file=sys.stderr)
            return 1

        names = list(data.keys())
        paths = [data[n] for n in names]

        if not (sys.stderr.isatty() and sys.stdin.isatty()):
            return self._simple_select(data)

        try:
            idx = _menu_select(names, paths)
        except Exception:
            sys.stderr.write(f"{_CSI}?25h\n")
            sys.stderr.flush()
            return self._simple_select(data)

        if idx is None:
            return 0
        print(paths[idx])
        return 0

    @staticmethod
    def _simple_select(data: dict[str, str]) -> int:
        """Plain ``input()`` fallback for non-TTY environments."""
        names = list(data.keys())
        print("pj: select a project:")
        for i, name in enumerate(names, 1):
            print(f"  {i}. {name}  ->  {_shorten(data[name])}")
        print("  0. exit")
        try:
            choice = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("")
            return 0
        if choice in ("0", ""):
            return 0
        try:
            idx = int(choice) - 1
        except ValueError:
            print("error: invalid input", file=sys.stderr)
            return 1
        if 0 <= idx < len(names):
            print(data[names[idx]])
            return 0
        print("error: invalid selection", file=sys.stderr)
        return 1


run = PjTool.entry_point
