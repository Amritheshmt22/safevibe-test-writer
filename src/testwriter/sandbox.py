"""Subprocess sandbox for running untrusted generated tests.

Each run happens in a fresh temporary directory containing only the
target package and the staged test files, with:

- CPU and address-space rlimits (Unix)
- a hard wall-clock timeout
- a scrubbed environment (no user env vars; HOME and caches redirected
  into the sandbox; PYTHONDONTWRITEBYTECODE set)
- the sandbox directory as the only working directory

This is process isolation, not a container: it prevents runaway tests,
accidental writes and environment leakage, but it does not provide a
seccomp-style syscall boundary. When Docker is available the same runner
interface can be pointed at a container image (future work, see
docs/architecture.md); the SafeVibe plan's experiments only need tests
that are *reproducibly* isolated from each other, which this provides.
"""
from __future__ import annotations

import os
import re
import resource
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PytestResult:
    exit_code: int  # 0 = all passed, 1 = test failures, other = collection/internal error
    passed: int
    failed: int
    errors: int
    duration_s: float
    failed_nodeids: list[str] = field(default_factory=list)
    output: str = ""
    timed_out: bool = False

    @property
    def all_passed(self) -> bool:
        return self.exit_code == 0


_FAILED_RE = re.compile(r"^FAILED (\S+)", re.M)


def _parse_counts(output: str) -> tuple[int, int, int]:
    passed = failed = errors = 0
    for line in reversed(output.splitlines()):
        if "passed" in line or "failed" in line or "error" in line:
            m = re.search(r"(\d+) passed", line)
            if m:
                passed = int(m.group(1))
            m = re.search(r"(\d+) failed", line)
            if m:
                failed = int(m.group(1))
            m = re.search(r"(\d+) errors?", line)
            if m:
                errors = int(m.group(1))
            if passed or failed or errors:
                break
    return passed, failed, errors


def _apply_limits(cpu_seconds: int, mem_bytes: int) -> None:  # runs in child
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
    resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
    os.setsid()


class Sandbox:
    """Stages a package plus test files and runs pytest against them."""

    def __init__(self, source_root: Path | str, timeout_s: int = 60,
                 cpu_s: int = 30, mem_mb: int = 512) -> None:
        """*source_root* is the directory whose contents become the sandbox
        root (e.g. the parent of the target package, so
        ``import mypackage`` works with the sandbox root on sys.path)."""
        self.source_root = Path(source_root)
        self.timeout_s = timeout_s
        self.cpu_s = cpu_s
        self.mem_bytes = mem_mb * 1024 * 1024

    def _stage(self, test_files: dict[str, str],
               overrides: dict[str, str] | None = None) -> Path:
        workdir = Path(tempfile.mkdtemp(prefix="testwriter-sbx-"))
        for item in self.source_root.iterdir():
            if item.name in (".git", "__pycache__", ".pytest_cache"):
                continue
            dest = workdir / item.name
            if item.is_dir():
                shutil.copytree(item, dest, ignore=shutil.ignore_patterns(
                    "__pycache__", "*.pyc", ".git"))
            else:
                shutil.copy2(item, dest)
        for relpath, content in (overrides or {}).items():
            target = workdir / relpath
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        for name, content in test_files.items():
            target = workdir / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        return workdir

    def _run(self, workdir: Path, args: list[str], timeout: int) -> tuple[int, str, float, bool]:
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(workdir),
            "PYTHONPATH": str(workdir),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",
        }
        start = time.monotonic()
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", *args],
                cwd=workdir, env=env, capture_output=True, text=True,
                timeout=timeout,
                preexec_fn=lambda: _apply_limits(self.cpu_s, self.mem_bytes),
            )
            return proc.returncode, proc.stdout + proc.stderr, time.monotonic() - start, False
        except subprocess.TimeoutExpired as exc:
            out = exc.stdout or ""
            if isinstance(out, bytes):
                out = out.decode("utf-8", "replace")
            return -9, out + "\n<timeout>", time.monotonic() - start, True

    def run_pytest(self, test_files: dict[str, str],
                   overrides: dict[str, str] | None = None,
                   nodeids: list[str] | None = None,
                   timeout_s: int | None = None) -> PytestResult:
        """Run the staged tests; *overrides* replaces source files (used to
        plant a mutant). When *nodeids* is given only those tests run,
        otherwise the whole staged test files run."""
        workdir = self._stage(test_files, overrides)
        try:
            if nodeids is not None:
                if not nodeids:
                    return PytestResult(0, 0, 0, 0, 0.0)
                args = ["-x", "-q", "--tb=no", "-rf", "-p", "no:cacheprovider",
                        *nodeids]
            else:
                args = ["-x", "-q", "--tb=no", "-rf", "-p", "no:cacheprovider",
                        *[str(workdir / name) for name in test_files]]
            rc, out, duration, timed_out = self._run(workdir, args,
                                                     timeout_s or self.timeout_s)
            passed, failed, errors = _parse_counts(out)
            return PytestResult(rc, passed, failed, errors, duration,
                                [m.group(1) for m in _FAILED_RE.finditer(out)],
                                out, timed_out)
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    def collect_nodeids(self, test_files: dict[str, str]) -> list[str]:
        """Collect pytest node ids for the staged test files."""
        workdir = self._stage(test_files)
        try:
            args = ["--collect-only", "-q", "-p", "no:cacheprovider",
                    *[str(workdir / name) for name in test_files]]
            rc, out, _, _ = self._run(workdir, args, self.timeout_s)
            return [ln.strip() for ln in out.splitlines() if "::" in ln]
        finally:
            shutil.rmtree(workdir, ignore_errors=True)
