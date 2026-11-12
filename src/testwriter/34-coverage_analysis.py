"""Coverage measurement built on coverage.py.

Runs a test suite under coverage inside the sandbox and parses the JSON
report, giving per-file line/branch coverage and the missing-line lists
that feed the generator's feedback prompt.
"""
from __future__ import annotations

import json
import os
import resource
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FileCoverage:
    path: str
    percent: float
    covered_lines: int
    missing_lines: list[int]
    missing_branches: int
    num_branches: int

    @property
    def branch_percent(self) -> float | None:
        if self.num_branches == 0:
            return None
        return 100.0 * (self.num_branches - self.missing_branches) / self.num_branches


@dataclass
class CoverageReport:
    total_percent: float
    branch_percent: float | None
    files: dict[str, FileCoverage] = field(default_factory=dict)

    def missing_lines_for(self, path_suffix: str) -> list[int]:
        for path, fc in self.files.items():
            if path.endswith(path_suffix):
                return fc.missing_lines
        return []


def _apply_limits(cpu_seconds: int, mem_bytes: int) -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
    resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
    os.setsid()


def measure_coverage(source_root: Path | str, source: str,
                     test_files: dict[str, str] | None = None,
                     test_paths: list[str] | None = None,
                     timeout_s: int = 300, cpu_s: int = 240,
                     mem_mb: int = 1024) -> CoverageReport:
    """Measure line+branch coverage of *source* (a package/module path
    relative to *source_root*) while running the given tests.

    Exactly one of *test_files* (relpath -> content, staged into the
    sandbox) or *test_paths* (paths already inside *source_root*) must
    be given.
    """
    source_root = Path(source_root)
    workdir = Path(tempfile.mkdtemp(prefix="testwriter-cov-"))
    try:
        for item in source_root.iterdir():
            if item.name in (".git", "__pycache__", ".pytest_cache"):
                continue
            dest = workdir / item.name
            if item.is_dir():
                shutil.copytree(item, dest, ignore=shutil.ignore_patterns(
                    "__pycache__", "*.pyc", ".git", ".coverage*"))
            else:
                shutil.copy2(item, dest)
        for name, content in (test_files or {}).items():
            target = workdir / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(workdir),
            "PYTHONPATH": str(workdir),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        targets = [str(workdir / p) for p in (test_paths or [])]
        targets += [str(workdir / n) for n in (test_files or {})]
        if not targets:
            raise ValueError("no tests given")
        run_cmd = [sys.executable, "-m", "coverage", "run", "--branch",
                   f"--source={source}", "-m", "pytest", "-q",
                   "-p", "no:cacheprovider", *targets]
        proc = subprocess.run(run_cmd, cwd=workdir, env=env, capture_output=True,
                              text=True, timeout=timeout_s,
                              preexec_fn=lambda: _apply_limits(cpu_s,
                                                               mem_mb * 1024 * 1024))
        # pytest exit != 0 is fine for measurement (some tests may fail);
        # no-data (rc of coverage json) is the real failure.
        json_cmd = [sys.executable, "-m", "coverage", "json", "-o",
                    str(workdir / "coverage.json")]
        subprocess.run(json_cmd, cwd=workdir, env=env, capture_output=True,
                       text=True, timeout=60)
        data = json.loads((workdir / "coverage.json").read_text())
    finally:
        if not (workdir / "coverage.json").exists():
            shutil.rmtree(workdir, ignore_errors=True)
            raise RuntimeError(
                "coverage produced no data - tests did not run or import failed\n"
                + (proc.stdout[-2000:] if "proc" in dir() else "")
                + (proc.stderr[-2000:] if "proc" in dir() else ""))
        report = _parse_json(data)
        shutil.rmtree(workdir, ignore_errors=True)
    return report


def _parse_json(data: dict) -> CoverageReport:
    files: dict[str, FileCoverage] = {}
    for path, fdata in data["files"].items():
        s = fdata["summary"]
        files[path] = FileCoverage(
            path=path,
            percent=s["percent_covered"],
            covered_lines=s["covered_lines"],
            missing_lines=fdata["missing_lines"],
            missing_branches=s.get("missing_branches", 0),
            num_branches=s.get("num_branches", 0),
        )
    t = data["totals"]
    nb = t.get("num_branches", 0)
    branch_pct = None
    if nb:
        branch_pct = 100.0 * t.get("covered_branches", 0) / nb
    return CoverageReport(total_percent=t["percent_covered"],
                          branch_percent=branch_pct, files=files)
