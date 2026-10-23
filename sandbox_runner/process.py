"""Run one process under resource limits (local backend).

Isolation that the local backend provides on its own:

* own session / process group, killed as a group on timeout;
* RLIMIT_CPU, RLIMIT_STACK, RLIMIT_FSIZE (output cap), RLIMIT_AS for plain
  builds (sanitizer and Valgrind builds need large virtual reservations);
* stdout/stderr go to files capped by RLIMIT_FSIZE, stdin comes from a file;
* drops to uid/gid 65534 when started as root;
* network namespace via ``unshare -n`` / ``unshare -rn`` when available.

Full isolation (read-only root, tmpfs, pids limit, cgroup memory) comes from
running the whole job inside the pinned container (``backend="docker"``).
"""

from __future__ import annotations

import functools
import os
import resource
import shutil
import signal
import subprocess
import time

from .config import Limits

NOBODY = 65534


def _works(argv: list[str]) -> bool:
    try:
        return subprocess.run([*argv, "true"], capture_output=True, timeout=5).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


@functools.lru_cache(maxsize=4)
def launcher(isolate_network: bool, drop_root: bool) -> tuple[tuple[str, ...], bool]:
    """Return (argv prefix, drop_root_in_preexec).

    As root: ``unshare -n setpriv --reuid=65534 ...`` (net namespace first,
    then drop privileges). As a normal user: ``unshare -rn`` (user + net
    namespace). Falls back to no namespace when neither works; the manifest
    records which one was used.
    """
    unshare, setpriv = shutil.which("unshare"), shutil.which("setpriv")
    is_root = os.geteuid() == 0
    if is_root and drop_root:
        drop = (setpriv, f"--reuid={NOBODY}", f"--regid={NOBODY}", "--clear-groups", "--") if setpriv else ()
        if isolate_network and unshare and drop and _works([unshare, "-n", *drop]):
            return (unshare, "-n", *drop), False
        if drop and _works(list(drop)):
            return drop, False
        return (), True
    if isolate_network and unshare:
        for pre in ((unshare, "-n"), (unshare, "-rn")):
            if _works(list(pre)):
                return pre, False
    return (), False


def isolation_report() -> dict:
    """What the local backend can enforce on this host (for the G0b manifest)."""
    pre, drop = launcher(True, True)
    return {"launcher": list(pre), "network_namespace": "-n" in pre or "-rn" in pre,
            "runs_as_nobody": (os.geteuid() == 0 and (drop or any("setpriv" in p for p in pre)))
            or os.geteuid() != 0, "euid": os.geteuid()}


def _preexec(limits: Limits, cpu_s: float, cap_memory: bool, drop_root: bool):
    def fn():
        os.setsid()
        cpu = int(cpu_s) + 1
        resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu + 1))
        stack = limits.stack_mb * 1024 * 1024
        try:
            resource.setrlimit(resource.RLIMIT_STACK, (stack, stack))
        except (ValueError, OSError):
            pass
        fsize = max(limits.output_bytes, limits.file_size_mb * 1024 * 1024)
        resource.setrlimit(resource.RLIMIT_FSIZE, (fsize, fsize))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        if cap_memory:
            mem = limits.memory_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
        if drop_root and os.geteuid() == 0:
            os.setgroups([])
            os.setgid(NOBODY)
            os.setuid(NOBODY)
    return fn


def _read_capped(path: str, cap: int) -> tuple[str, bool]:
    try:
        with open(path, "rb") as f:
            data = f.read(cap + 1)
    except FileNotFoundError:
        return "", False
    truncated = len(data) > cap
    return data[:cap].decode("utf-8", errors="replace"), truncated


def run_process(argv: list[str], *, stdin_path: str | None, workdir: str, timeout_s: float,
                limits: Limits, cap_memory: bool = True, env: dict | None = None,
                isolate_network: bool = True, drop_root: bool = True,
                tag: str = "run") -> dict:
    """Run ``argv`` and return rc / signal / timing / captured output."""
    out_path = os.path.join(workdir, f".{tag}.out")
    err_path = os.path.join(workdir, f".{tag}.err")
    prefix, drop = launcher(isolate_network, drop_root)
    full_env = {"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C", "HOME": workdir}
    if env:
        full_env.update(env)
    stdin_f = open(stdin_path, "rb") if stdin_path else subprocess.DEVNULL
    t0 = time.monotonic()
    timed_out = False
    try:
        with open(out_path, "wb") as out_f, open(err_path, "wb") as err_f:
            proc = subprocess.Popen(
                [*prefix, *argv], stdin=stdin_f, stdout=out_f, stderr=err_f, cwd=workdir,
                env=full_env, preexec_fn=_preexec(limits, timeout_s, cap_memory, drop),
                close_fds=True,
            )
            try:
                proc.wait(timeout=timeout_s)
            except subprocess.TimeoutExpired:
                timed_out = True
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait()
    finally:
        if stdin_path:
            stdin_f.close()
    seconds = time.monotonic() - t0
    rc = proc.returncode
    sig = -rc if rc is not None and rc < 0 else None
    stdout, out_trunc = _read_capped(out_path, limits.output_bytes)
    stderr, _ = _read_capped(err_path, limits.output_bytes)
    # SIGXFSZ means the program hit the output cap.
    output_limit = out_trunc or sig == signal.SIGXFSZ
    for p in (out_path, err_path):
        try:
            os.unlink(p)
        except OSError:
            pass
    return {"rc": rc, "signal": sig, "timed_out": timed_out, "seconds": round(seconds, 4),
            "stdout": stdout, "stderr": stderr, "output_limit": bool(output_limit)}
