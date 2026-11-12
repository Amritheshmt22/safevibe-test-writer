"""Experiment E2 runner: test-backfill quality on real under-tested repos.

Protocol (SafeVibe plan, section 6, E2):

- targets: real open-source modules whose existing test suites leave them
  under 30% line coverage (see experiments/e2_test_backfill/candidates.md)
- arm A (naive baseline): one-shot "write tests for this module"
  prompting, pass-on-real sanity check only, no mutant filter
- arm B (Test-Writer): iterative generation with missing-line feedback
  plus the mutant filter
- both arms use the same generator and comparable recorded budgets; all
  prompts and raw completions are pinned artifacts
- reported: per-repo coverage delta, mutation score, and the share of
  generated tests surviving the mutant filter
"""
from __future__ import annotations

import json
from pathlib import Path

from .generate import ScriptedBackend
from .loop import LoopResult, Target, run_baseline, run_loop
from .report import write_dashboard, write_results
from .store import Store


def load_targets(config_path: Path | str) -> list[Target]:
    cfg = json.loads(Path(config_path).read_text(encoding="utf-8"))
    root = Path(config_path).parent
    targets = []
    for t in cfg["targets"]:
        targets.append(Target(
            repo=t["repo"],
            source_root=(root / t["source_root"]).resolve(),
            module_relpath=t["module_relpath"],
            module_name=t["module_name"],
            import_stmt=t["import_stmt"],
            existing_test_paths=t.get("existing_test_paths", []),
        ))
    return targets


def run_experiment(config_path: Path | str, store_path: Path | str,
                   results_dir: Path | str, completions_dir: Path | str,
                   max_rounds: int = 3, max_mutants: int = 150,
                   only_repo: str | None = None) -> dict[str, list[LoopResult]]:
    targets = load_targets(config_path)
    store = Store(store_path)
    completions = Path(completions_dir)
    arms: dict[str, list[LoopResult]] = {"loop": [], "baseline": []}
    try:
        for target in targets:
            if only_repo and target.repo != only_repo:
                continue
            backend = ScriptedBackend(completions / target.repo)
            arms["loop"].append(run_loop(
                target, backend, store, max_rounds=max_rounds,
                max_mutants=max_mutants))
            arms["baseline"].append(run_baseline(
                target, backend, store, max_mutants=max_mutants))
        write_results(arms["loop"] + arms["baseline"], results_dir)
        write_dashboard(arms, Path(results_dir).parent / "dashboard")
    finally:
        store.close()
    return arms
