"""Run untrusted student code in an isolated child process.

Isolation layers (Linux):

1. bubblewrap (``bwrap``) — new mount, PID, network, IPC and UTS namespaces.
   The sandbox sees only a read-only ``/usr`` (compiler, interpreter, system
   headers), an empty ``/tmp``, and its own scratch directory mounted at
   ``/work``. No network interface, no host files (no database, no ``.env``,
   no source tree), and an empty environment.
2. Resource limits on every child: CPU seconds, address space, file size
   (caps captured output), open files, no core dumps.
3. A wall-clock timeout that kills the whole process group.
4. A global semaphore limiting concurrent executions.

If bubblewrap is unavailable (Windows/macOS dev machines, locked-down
containers), only layers 2-4 apply. That is NOT safe for untrusted code, so
``REQUIRE_SANDBOX`` (on by default in production) refuses to execute in that
case. Install with ``apt install bubblewrap``.
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from backend.app.config import settings

log = logging.getLogger("tracelearn.sandbox")

IS_POSIX = os.name == "posix"
if IS_POSIX:
    import resource
    import signal

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SANDBOX_WORKDIR = "/work"


class SandboxUnavailable(RuntimeError):
    """Raised when execution is required to be sandboxed but cannot be."""


@dataclass
class SandboxResult:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False
    output_limit_hit: bool = False
    memory_limit_hit: bool = False


# ---------------------------------------------------------------------------
# bubblewrap detection
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def bwrap_path() -> str | None:
    if not IS_POSIX or settings.sandbox_mode == "none":
        return None
    exe = shutil.which("bwrap")
    if not exe:
        return None
    try:
        probe = subprocess.run(
            [exe, *_bwrap_base_args(), "--", "/usr/bin/true"],
            capture_output=True, timeout=10, env={},
        )
    except Exception as exc:  # pragma: no cover - environment specific
        log.warning("bubblewrap present but unusable: %s", exc)
        return None
    if probe.returncode != 0:
        log.warning("bubblewrap present but unusable: %s", probe.stderr.decode(errors="replace")[:300])
        return None
    return exe


def sandbox_status() -> dict:
    exe = bwrap_path()
    return {
        "mode": "bwrap" if exe else "rlimit-only",
        "isolated": exe is not None,
        "required": settings.sandbox_required,
    }


def ensure_sandbox_policy() -> None:
    """Raise SandboxUnavailable if policy requires isolation we do not have."""
    if settings.sandbox_mode == "bwrap" or settings.sandbox_required:
        if bwrap_path() is None:
            raise SandboxUnavailable(
                "Code execution requires bubblewrap (apt install bubblewrap), which is not available on this server."
            )


def _root_links() -> list[str]:
    """Mirror /bin, /lib, /lib64, /sbin as the host has them (symlink or dir)."""
    args: list[str] = []
    for name in ("bin", "lib", "lib64", "lib32", "sbin"):
        host = Path("/") / name
        if host.is_symlink():
            args += ["--symlink", os.readlink(host), f"/{name}"]
        elif host.is_dir():
            args += ["--ro-bind", str(host), f"/{name}"]
    return args


def _bwrap_base_args() -> list[str]:
    args = [
        "--unshare-all",          # no network, new pid/ipc/uts/mount (and user, when allowed)
        "--die-with-parent",
        "--new-session",          # blocks TIOCSTI terminal injection
        "--ro-bind", "/usr", "/usr",
        *_root_links(),
        # g++/python resolve through /etc/alternatives on Debian/Ubuntu.
        "--ro-bind-try", "/etc/alternatives", "/etc/alternatives",
        "--ro-bind-try", "/etc/ld.so.cache", "/etc/ld.so.cache",
        "--proc", "/proc",
        "--dev", "/dev",
        "--tmpfs", "/tmp",
        "--clearenv",
        "--setenv", "PATH", "/usr/local/bin:/usr/bin:/bin",
        "--setenv", "HOME", SANDBOX_WORKDIR,
        "--setenv", "LANG", "C.UTF-8",
        "--setenv", "PYTHONDONTWRITEBYTECODE", "1",
    ]
    # If the application itself lives under /usr (e.g. /usr/src/app in a
    # container), hide it so student code cannot read the source, .env or DB.
    if str(PROJECT_ROOT).startswith("/usr/"):
        args += ["--tmpfs", str(PROJECT_ROOT)]
    # A Python interpreter outside /usr (conda, pyenv) must be visible read-only.
    base_prefix = os.path.realpath(sys.base_prefix)
    if not base_prefix.startswith("/usr"):
        args += ["--ro-bind", base_prefix, base_prefix]
    if IS_POSIX and os.geteuid() == 0:
        args += ["--cap-drop", "ALL"]
    return args


# ---------------------------------------------------------------------------
# execution
# ---------------------------------------------------------------------------
_slots = threading.BoundedSemaphore(max(1, settings.max_concurrent_executions))


class execution_slot:
    """Context manager limiting how many submissions execute at once."""

    def __enter__(self):
        if not _slots.acquire(timeout=60):
            raise SandboxUnavailable("Server is busy running other submissions. Try again shortly.")
        return self

    def __exit__(self, *exc):
        _slots.release()
        return False


@lru_cache(maxsize=1)
def _prlimit_path() -> str | None:
    exe = shutil.which("prlimit")
    return os.path.realpath(exe) if exe and os.path.realpath(exe).startswith("/usr/") else None


def _limits(cpu_seconds: int, memory_mb: int, file_bytes: int):
    def apply() -> None:  # runs in the child between fork and exec
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 1))
        mem = memory_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
        resource.setrlimit(resource.RLIMIT_FSIZE, (file_bytes, file_bytes))
        resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    return apply


def _read_capped(path: Path, limit: int) -> tuple[str, bool]:
    try:
        with open(path, "rb") as fh:
            data = fh.read(limit + 1)
    except FileNotFoundError:
        return "", False
    hit = len(data) > limit
    return data[:limit].decode("utf-8", errors="replace"), hit


def run_in_sandbox(
    argv: list[str],
    workdir: Path,
    *,
    stdin_data: str = "",
    timeout: float,
    memory_mb: int | None = None,
    output_bytes: int | None = None,
) -> SandboxResult:
    """Run ``argv`` with ``workdir`` as its working directory.

    Paths inside ``argv`` must be relative to the working directory (or
    absolute system paths under /usr), so they are valid both inside the
    sandbox (where workdir is /work) and in rlimit-only mode.
    """
    ensure_sandbox_policy()
    memory_mb = memory_mb or settings.max_memory_mb
    output_bytes = output_bytes or settings.max_output_bytes
    out_path = workdir / ".stdout"
    err_path = workdir / ".stderr"

    exe = bwrap_path()
    if exe:
        cmd = [exe, *_bwrap_base_args(), "--bind", str(workdir), SANDBOX_WORKDIR, "--chdir", SANDBOX_WORKDIR, "--", *argv]
        cwd = None
        env: dict[str, str] = {}
    else:
        if not getattr(run_in_sandbox, "_warned", False):
            log.warning("Executing student code WITHOUT bubblewrap isolation (rlimit-only). Not safe for untrusted code.")
            run_in_sandbox._warned = True  # type: ignore[attr-defined]
        cmd = list(argv)
        cwd = str(workdir)
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1"}
        if os.name == "nt":  # Windows needs these to start processes at all
            for k in ("SYSTEMROOT", "TEMP", "TMP", "PATHEXT", "COMSPEC"):
                if k in os.environ:
                    env[k] = os.environ[k]

    popen_kwargs: dict = {}
    if IS_POSIX:
        popen_kwargs["start_new_session"] = True
        cpu, fsize = int(timeout) + 1, output_bytes + 1024
        prlimit = _prlimit_path()
        if prlimit:
            # Limits apply to the student program only (not to bwrap), and are
            # set by an external helper, avoiding preexec_fn in a threaded server.
            limit_prefix = [
                prlimit, f"--cpu={cpu}", f"--as={memory_mb * 1024 * 1024}",
                f"--fsize={fsize}", "--nofile=64", "--core=0", "--",
            ]
            if exe:
                sep = cmd.index("--")
                cmd = cmd[: sep + 1] + limit_prefix + cmd[sep + 1:]
            else:
                cmd = limit_prefix + cmd
        else:
            popen_kwargs["preexec_fn"] = _limits(cpu, memory_mb, fsize)

    timed_out = False
    with open(out_path, "wb") as out_fh, open(err_path, "wb") as err_fh:
        proc = subprocess.Popen(
            cmd, cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=out_fh, stderr=err_fh, **popen_kwargs
        )
        try:
            proc.communicate(input=stdin_data.encode("utf-8"), timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            _kill(proc)
        except BaseException:
            _kill(proc)
            raise

    stdout, out_hit = _read_capped(out_path, output_bytes)
    stderr, _ = _read_capped(err_path, 16 * 1024)
    rc = proc.returncode if proc.returncode is not None else -9
    sig = -rc if rc < 0 else 0
    out_hit = out_hit or (IS_POSIX and sig == getattr(signal, "SIGXFSZ", -1))
    if IS_POSIX and sig == signal.SIGXCPU:
        timed_out = True
    mem_hit = "MemoryError" in stderr or "std::bad_alloc" in stderr
    return SandboxResult(rc, stdout, stderr, timed_out=timed_out, output_limit_hit=out_hit, memory_limit_hit=mem_hit)


def _kill(proc: subprocess.Popen) -> None:
    try:
        if IS_POSIX:
            os.killpg(proc.pid, signal.SIGKILL)
        else:
            proc.kill()
    except (ProcessLookupError, PermissionError, OSError):
        pass
    try:
        proc.wait(timeout=5)
    except Exception:  # pragma: no cover
        pass


def new_workdir() -> tempfile.TemporaryDirectory:
    tmp = tempfile.TemporaryDirectory(prefix="tl-run-")
    if IS_POSIX:
        os.chmod(tmp.name, 0o700)
    return tmp


# ---------------------------------------------------------------------------
# source screening (defence in depth; bubblewrap is the real boundary)
# ---------------------------------------------------------------------------
_CPP_DIRECTIVE = re.compile(r"^\s*(?:#|%:|\?\?=)\s*(\w+)(.*)$")
_SAFE_INCLUDE = re.compile(r"^\s*<[A-Za-z0-9_][A-Za-z0-9_./+-]*>\s*$")


def _strip_comments(src: str) -> str:
    out, i, n = [], 0, len(src)
    while i < n:
        if src.startswith("//", i):
            j = src.find("\n", i)
            i = n if j == -1 else j
        elif src.startswith("/*", i):
            j = src.find("*/", i + 2)
            out.append(" ")
            i = n if j == -1 else j + 2
        elif src[i] in "\"'":
            q, j = src[i], i + 1
            while j < n and src[j] != q:
                j += 2 if src[j] == "\\" else 1
            out.append(src[i:j + 1])
            i = j + 1
        else:
            out.append(src[i])
            i += 1
    return "".join(out)


def check_cpp_source(src: str) -> str | None:
    """Return an error message if the source uses disallowed directives."""
    normalized = _strip_comments(src.replace("\\\r\n", "").replace("\\\n", ""))
    for line in normalized.splitlines():
        m = _CPP_DIRECTIVE.match(line)
        if not m:
            continue
        directive, rest = m.group(1), m.group(2)
        if directive in ("include_next", "embed", "import"):
            return f"#{directive} is not allowed. Use #include <...> with standard headers."
        if directive == "include":
            target = rest.strip()
            if not _SAFE_INCLUDE.match(target) or ".." in target:
                return "Only standard library headers are allowed, e.g. #include <iostream>."
    if re.search(r"\.incbin\b", normalized):
        return "Inline .incbin is not allowed."
    return None


def clean_compiler_output(text: str, workdir: Path) -> str:
    text = text.replace(str(workdir) + os.sep, "").replace(str(workdir), "")
    text = text.replace(SANDBOX_WORKDIR + "/", "")
    return text[:8 * 1024]
