import sys
from datetime import datetime, timedelta

from localtool.core import BaseTool


def _fmt_bytes(n: int) -> str:
    """Human-readable byte size."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def _fmt_duration(td: timedelta) -> str:
    """Short human duration."""
    total = int(td.total_seconds())
    if total < 60:
        return f"{total}s"
    if total < 3600:
        m, s = divmod(total, 60)
        return f"{m}m {s}s"
    h, remainder = divmod(total, 3600)
    m = remainder // 60
    return f"{h}h {m}m"


def _fmt_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _fmt_time(s: float) -> str:
    """Format a CPU-time value compactly."""
    if s < 0.001:
        return "0s"
    if s < 1:
        return f"{s*1000:.0f}ms"
    if s < 60:
        return f"{s:.1f}s"
    m, sec = divmod(s, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{int(h)}h{int(m)}m{sec:.0f}s"
    return f"{int(m)}m{sec:.0f}s"


# ── ANSI helpers ──────────────────────────────────────────────────────
_ESC = "\033"
_CSI = f"{_ESC}["
_SGR = lambda *cs: f"{_CSI}{';'.join(map(str, cs))}m"
_R = _SGR(0)
_B = _SGR(1)
_D = _SGR(2)
_FG_C = _SGR(36)
_FG_W = _SGR(37)
_FG_G = _SGR(32)
_FG_Y = _SGR(33)
_FG_R = _SGR(31)
_FG_k = _SGR(90)
_SECTION = f"{_B}{_FG_C}"


# ── Worker script (runs in isolated subprocess for uv‑trampoline safety) ─
# The subprocess does ctypes + PowerShell calls, emits JSON, then exits cleanly.
# All thread handles are released in the *child* process — the parent never
# touches them, so the uv trampoline never sees stale handles on exit.

_WORKER_SCRIPT = r"""
import json, subprocess, sys

pid = int(sys.argv[1])

# ── thread states via PowerShell ──
states = {}
ps_cmd = (
    "Get-Process -Id {} -ErrorAction Stop | "
    "Select-Object -ExpandProperty Threads | "
    "ForEach-Object {{ "
    "\"TID={{0}}`tState={{1}}`tWait={{2}}`tPriority={{3}}\" -f "
    "$_.Id, $_.ThreadState, $_.WaitReason, $_.PriorityLevel "
    "}}"
).format(pid)
state_out = subprocess.run(
    ["powershell", "-NoProfile", "-Command", ps_cmd],
    capture_output=True, text=True, timeout=10,
)
for line in state_out.stdout.strip().splitlines():
    if not line.strip():
        continue
    parts = dict(p.split("=", 1) for p in line.split(chr(9)) if "=" in p)
    try:
        tid = int(parts.get("TID", ""))
    except ValueError:
        continue
    states[tid] = {
        "state": parts.get("State", "?"),
        "wait_reason": parts.get("Wait", ""),
        "priority": parts.get("Priority", "?"),
    }

json.dump({"names": {}, "states": states}, sys.stdout)
"""


# ══════════════════════════════════════════════════════════════════════
# Tool
# ══════════════════════════════════════════════════════════════════════

class PtTool(BaseTool):
    """Query detailed information about a running process by PID or name."""

    name = "pt"
    help = "show detailed info for a specified process"

    def run(self, args: list[str] | None = None) -> int:
        parser = self.make_parser()
        parser.add_argument(
            "target", nargs="?", default=None,
            help="process ID (PID) or process name (e.g. 1234 or chrome.exe)",
        )
        parser.add_argument(
            "--list", "-l", action="store_true",
            help="list all running processes (brief table)",
        )
        parser.add_argument(
            "--threads", "-t", action="store_true",
            help="show per-thread details (TID, CPU%%, user/kernel time)",
        )
        ns = self.parse(parser, args)
        if ns is None:
            return 1

        try:
            import psutil
        except ImportError:
            print("error: psutil is required. Install it with: pip install psutil",
                  file=sys.stderr)
            return 1

        if ns.list:
            return self._list_all(show_threads=ns.threads)
        if ns.target is None:
            print("error: specify a PID or process name, or use --list", file=sys.stderr)
            return 1
        return self._show_detail(ns.target, show_threads=ns.threads)

    # ── list all processes ────────────────────────────────────────────

    @staticmethod
    def _list_all(show_threads: bool = False) -> int:
        import psutil

        procs = []
        for p in psutil.process_iter(["pid", "name", "num_threads", "memory_info"]):
            try:
                info = p.info
                procs.append((
                    info["pid"],
                    info["name"] or "?",
                    info["num_threads"] or 0,
                    info["memory_info"].rss if info["memory_info"] else 0,
                ))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        procs.sort(key=lambda x: x[0])

        print(f"{'PID':>7}  {'THREADS':>7}  {'MEM':>10}  NAME")
        print(f"{'─' * 7}  {'─' * 7}  {'─' * 10}  {'─' * 20}")
        for pid, name, nthreads, rss in procs:
            if show_threads:
                tids = PtTool._get_thread_ids(pid)
                tids_str = ",".join(str(t) for t in tids[:6])
                if len(tids) > 6:
                    tids_str += f" ...+{len(tids)-6}"
                extra = f"  [{tids_str}]" if tids else ""
            else:
                extra = ""
            print(f"{pid:>7}  {nthreads:>7}  {_fmt_bytes(rss):>10}  {name}{extra}")
        print(f"\n{'─' * 7}  {'─' * 7}  {'─' * 10}  {'─' * 20}")
        print(f"{len(procs)} processes")
        return 0

    @staticmethod
    def _get_thread_ids(pid: int) -> list[int]:
        """Get thread IDs for a process using psutil (lightweight)."""
        import psutil
        try:
            return [t.id for t in psutil.Process(pid).threads()]
        except Exception:
            return []

    # ── detail view ───────────────────────────────────────────────────

    def _show_detail(self, target: str, show_threads: bool = False) -> int:
        import psutil

        procs = self._find_procs(target)
        if procs is None:
            return 1
        if not procs:
            print(f"error: no process matching '{target}' found", file=sys.stderr)
            return 1

        if len(procs) > 1:
            return self._show_multi(procs, show_threads=show_threads)

        return self._print_detail(procs[0], show_threads=show_threads)

    @staticmethod
    def _find_procs(target: str) -> list | None:
        """Return list of psutil.Process objects, or None on fatal error."""
        import psutil

        try:
            pid = int(target)
            try:
                return [psutil.Process(pid)]
            except psutil.NoSuchProcess:
                print(f"error: no process with PID {pid}", file=sys.stderr)
                return None
        except ValueError:
            pass

        results = []
        for p in psutil.process_iter(["name"]):
            try:
                name = p.info["name"] or ""
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            if target.lower() in name.lower():
                results.append(p)
        return results

    @staticmethod
    def _show_multi(procs: list, show_threads: bool = False) -> int:
        """Multiple matches — print a selection table, then detail for the first."""
        import psutil

        rows = []
        for p in procs:
            try:
                with p.oneshot():
                    rows.append((
                        p.pid,
                        p.name() or "?",
                        p.num_threads(),
                        p.memory_info().rss if p.memory_info() else 0,
                        p.cpu_percent(interval=0),
                    ))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if not rows:
            print("error: all matched processes have exited", file=sys.stderr)
            return 1

        print(f"{'PID':>7}  {'CPU%':>6}  {'THREADS':>7}  {'MEM':>10}  NAME")
        print(f"{'─' * 7}  {'─' * 6}  {'─' * 7}  {'─' * 10}  {'─' * 20}")
        for pid, name, nthreads, rss, cpu in rows:
            print(f"{pid:>7}  {cpu:>5.1f}%  {nthreads:>7}  {_fmt_bytes(rss):>10}  {name}")
        print()
        print(f"Found {len(rows)} matches. Detail for PID {rows[0][0]}:\n")

        return PtTool._print_detail(procs[0], show_threads=show_threads)

    @staticmethod
    def _print_detail(p, show_threads: bool = False) -> int:
        """Pretty-print all details of a single process."""
        import psutil

        try:
            with p.oneshot():
                pid = p.pid
                name = p.name() or "?"
                ppid = p.ppid()
                username = p.username()
                status = p.status()
                create_time = datetime.fromtimestamp(p.create_time())
                uptime = datetime.now() - create_time
                exe = p.exe()
                cmdline = " ".join(p.cmdline()) if p.cmdline() else ""
                cpu_pct = p.cpu_percent(interval=0)
                cpu_times = p.cpu_times()
                mem = p.memory_info()
                mem_full = p.memory_full_info() if hasattr(p, "memory_full_info") else None
                nthreads = p.num_threads()
                num_handles = p.num_handles() if hasattr(p, "num_handles") else None
                num_ctx = p.num_ctx_switches()
                io_counters = p.io_counters() if hasattr(p, "io_counters") else None

            # Parent name
            try:
                parent_name = psutil.Process(ppid).name()
            except Exception:
                parent_name = "?"

            tw = 80

            # ── header ──
            header = f" Process: {name} (PID {pid}) "
            pad = max(0, tw - len(header) - 2)
            print(f"{_SECTION}╔══{header}{'═' * pad}╗{_R}")

            # ── basic info ──
            status_color = _FG_G if status == "running" else _FG_Y if status == "sleeping" else _FG_R
            lines = [
                ("PID", f"{pid}"),
                ("Parent", f"{ppid} ({parent_name})"),
                ("User", username),
                ("Status", f"{status_color}{status}{_R}"),
                ("Started", f"{_fmt_dt(create_time)}  ({_FG_W}{_fmt_duration(uptime)}{_R} ago)"),
                ("Path", exe or "?"),
            ]
            if cmdline:
                # Allow a wider command line in the thread view (it looks better)
                max_cmd = 120
                truncated = cmdline if len(cmdline) <= max_cmd else cmdline[:max_cmd - 3] + "..."
                lines.append(("Command", truncated))

            PtTool._print_kv(lines)
            print()

            # ── performance ──
            print(f"{_SECTION}── Performance{_R}")
            total_cpu = cpu_times.user + cpu_times.system
            lines = [
                ("CPU", f"{cpu_pct:.1f}%  (user {cpu_times.user:.1f}s, kernel {cpu_times.system:.1f}s)"),
                ("Memory (RSS)", _fmt_bytes(mem.rss)),
                ("Memory (VMS)", _fmt_bytes(mem.vms)),
                ("Threads", f"{_B}{nthreads}{_R}"),
            ]
            if num_handles is not None:
                lines.append(("Handles", str(num_handles)))
            ctx = f"voluntary {num_ctx.voluntary}, involuntary {num_ctx.involuntary}"
            lines.append(("Ctx switches", ctx))
            PtTool._print_kv(lines)
            print()

            # ── I/O ──
            if io_counters:
                print(f"{_SECTION}── I/O{_R}")
                lines = [
                    ("Read", f"{_fmt_bytes(io_counters.read_bytes)}  /  {io_counters.read_count:,} ops"),
                    ("Written", f"{_fmt_bytes(io_counters.write_bytes)}  /  {io_counters.write_count:,} ops"),
                ]
                if hasattr(io_counters, "other_bytes"):
                    lines.append(("Other", f"{_fmt_bytes(io_counters.other_bytes)}  /  {io_counters.other_count:,} ops"))
                PtTool._print_kv(lines)
                print()

            # ── memory detail ──
            if mem_full:
                extras = []
                if hasattr(mem_full, "uss"):
                    extras.append(("USS", _fmt_bytes(mem_full.uss)))
                if hasattr(mem_full, "pss"):
                    extras.append(("PSS", _fmt_bytes(mem_full.pss)))
                if hasattr(mem_full, "pagefile"):
                    extras.append(("Pagefile", _fmt_bytes(mem_full.pagefile)))
                if extras:
                    print(f"{_SECTION}── Memory detail{_R}")
                    PtTool._print_kv(extras)
                    print()

            # ── thread list ──
            if show_threads and nthreads > 0:
                PtTool._print_threads(pid, total_cpu)

            # ── footer ──
            print(f"{_SECTION}{'═' * tw}{_R}")

        except psutil.NoSuchProcess:
            print("error: process has exited", file=sys.stderr)
            return 1
        except psutil.AccessDenied:
            print("error: access denied (try running as administrator)", file=sys.stderr)
            return 1

        return 0

    # ── thread detail enrichment (subprocess‑isolated) ─────────────────

    @staticmethod
    def _enrich_threads(pid: int) -> dict[int, dict]:
        """Query thread states in an isolated subprocess.

        Returns {tid: {state, wait_reason, priority}}.
        On any failure returns empty dict — caller degrades gracefully.
        """
        import json
        import subprocess

        try:
            r = subprocess.run(
                [sys.executable, "-c", _WORKER_SCRIPT, str(pid)],
                capture_output=True, text=True, timeout=15,
            )
            if r.returncode != 0:
                return {}
            data = json.loads(r.stdout)
            return {int(k): v for k, v in data.get("states", {}).items()}
        except Exception:
            return {}

    # ── thread listing ────────────────────────────────────────────────

    @staticmethod
    def _print_threads(pid: int, total_cpu: float) -> None:
        """Print a per-thread breakdown table."""
        import psutil

        try:
            raw = psutil.Process(pid).threads()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            print(f"\n{_SECTION}── Threads{_R}")
            print(f"  {_FG_k}(unable to enumerate threads){_R}")
            return

        if not raw:
            return

        # sort by total CPU time descending (hottest threads first)
        raw = sorted(raw, key=lambda t: t.user_time + t.system_time, reverse=True)

        # ── enrich (subprocess‑isolated, degrades gracefully) ──
        thread_states = PtTool._enrich_threads(pid)

        # Use sum-of-thread-CPU as denominator (avoids >100% from snapshot skew)
        thread_total_cpu = sum(t.user_time + t.system_time for t in raw)
        denom = max(total_cpu, thread_total_cpu, 0.001)

        # Decide columns based on what enrichment is available
        has_state = bool(thread_states)

        print(f"\n{_SECTION}── Threads  ({_B}{len(raw)}{_R}){_R}")
        if has_state:
            print(f"  {_FG_k}{'TID':>7}  {'%CPU':>6}  {'User':>9}  {'Kernel':>9}  {'State':<20}  {'Priority':>9}{_R}")
            print(f"  {_FG_k}{'─'*7}  {'─'*6}  {'─'*9}  {'─'*9}  {'─'*20}  {'─'*9}{_R}")
        else:
            print(f"  {_FG_k}{'TID':>7}  {'%CPU':>6}  {'User':>9}  {'Kernel':>9}{_R}")
            print(f"  {_FG_k}{'─'*7}  {'─'*6}  {'─'*9}  {'─'*9}{_R}")

        for t in raw:
            tid = t.id
            user_t = t.user_time
            kern_t = t.system_time
            thread_cpu = user_t + kern_t
            pct = (thread_cpu / denom) * 100 if denom > 0 else 0

            # color-code hot threads
            if pct > 20:
                color = _FG_R
            elif pct > 5:
                color = _FG_Y
            else:
                color = ""

            line = (
                f"  {tid:>7}  "
                f"{color}{pct:>5.1f}%{_R if color else ''}  "
                f"{_fmt_time(user_t):>9}  "
                f"{_fmt_time(kern_t):>9}"
            )

            if has_state:
                st = thread_states.get(tid, {})
                state = st.get("state", "?")
                wait = st.get("wait_reason", "")
                pri = st.get("priority", "")

                if state == "Wait" and wait and wait != "UserRequest":
                    state_str = f"Wait:{wait}"
                elif state == "Wait":
                    state_str = "Wait"
                elif state == "Running":
                    state_str = f"{_FG_G}Running{_R}"
                else:
                    state_str = state

                line += f"  {state_str:<26}  {pri:>9}"

            print(line)

    # ── helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _print_kv(lines: list[tuple[str, str]]) -> None:
        """Print key-value pairs, aligned."""
        kw = max(len(k) for k, _ in lines)
        for k, v in lines:
            print(f"  {_FG_k}{k:<{kw}}{_R}  {v}")


def _main():
    """Entry point with top-level exception reporting."""
    try:
        return PtTool.entry_point()
    except Exception as e:
        import traceback
        traceback.print_exc()
        return 1


run = _main
