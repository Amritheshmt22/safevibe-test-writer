"""The iterative Test-Writer loop (SafeVibe Component 2).

For one target module:

1. measure baseline coverage and mutation score (existing tests, if any)
2. generate candidate tests with the LLM backend
3. run the mutant filter in the sandbox
4. keep the surviving tests, measure the coverage delta and missing lines
5. feed the still-missing lines back into the next prompt and iterate,
   until no new tests survive, the round budget is exhausted, or the
   coverage target is reached
6. score the merged accepted suite against all mutants

Every prompt, raw completion, filter verdict and metric is written to
the artifact store.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from . import prompts as P
from .coverage_analysis import measure_coverage
from .filtering import FilterResult, run_mutant_filter
from .generate import Backend, ScriptedBackend, extract_code
from .mutate import MAX_MUTANTS_DEFAULT, generate_mutants
from .sandbox import Sandbox
from .store import Store


@dataclass
class Target:
    """One module under test inside a repository checkout."""
    repo: str                    # display name, e.g. "exrex"
    source_root: Path            # sandbox root (package parent)
    module_relpath: str          # module path inside source_root
    module_name: str             # coverage --source name, e.g. "exrex"
    import_stmt: str             # e.g. "import exrex"
    existing_test_paths: list[str] = field(default_factory=list)


@dataclass
class IterationRecord:
    round: int
    filter_result: FilterResult | None
    generation_error: str | None
    coverage_after: float | None
    branch_after: float | None
    duration_s: float


@dataclass
class LoopResult:
    target: Target
    baseline_coverage: float | None
    baseline_branch: float | None
    baseline_mutation_score: float | None
    final_coverage: float | None
    final_branch: float | None
    final_mutation_score: float | None
    accepted_tests: list[str]      # nodeids surviving the filter
    accepted_source: str           # merged accepted test code
    iterations: list[IterationRecord]
    mutants_total: int
    final_filter: FilterResult | None = None


def _module_coverage(target: Target, test_files: dict[str, str]) -> tuple[
        float | None, float | None, list[int]]:
    cov = measure_coverage(target.source_root, source=target.module_name,
                           test_files=test_files)
    for path, fc in cov.files.items():
        if path.endswith(target.module_relpath):
            return fc.percent, fc.branch_percent, fc.missing_lines
    return None, None, []


def _module_coverage_from_paths(target: Target) -> tuple[
        float | None, float | None]:
    cov = measure_coverage(target.source_root, source=target.module_name,
                           test_paths=target.existing_test_paths)
    for path, fc in cov.files.items():
        if path.endswith(target.module_relpath):
            return fc.percent, fc.branch_percent
    return None, None


def measure_baseline(target: Target, mutants, sandbox: Sandbox
                     ) -> tuple[float | None, float | None, float | None]:
    """Coverage and mutation score of the repo's existing suite."""
    if not target.existing_test_paths:
        return None, None, None
    try:
        cov, branch = _module_coverage_from_paths(target)
    except Exception:
        return None, None, None
    ms = None
    if cov is not None:
        existing_src = "\n\n".join(
            (target.source_root / p).read_text(encoding="utf-8")
            for p in target.existing_test_paths)
        filt = run_mutant_filter(sandbox, target.module_relpath,
                                 existing_src, mutants)
        ms = filt.mutation_score
    return cov, branch, ms


def run_loop(target: Target, backend: Backend, store: Store,
             max_rounds: int = 3, max_mutants: int = MAX_MUTANTS_DEFAULT,
             coverage_target: float = 90.0,
             scripted_round_files: list[str] | None = None) -> LoopResult:
    """Run the full iterative loop on *target*.

    With a ScriptedBackend, *scripted_round_files* names the recorded
    completion for each round (round 1, 2, ...); a missing file simply
    ends the loop (the recorded generation budget is spent).
    """
    source_path = target.source_root / target.module_relpath
    source = source_path.read_text(encoding="utf-8")
    mutants = generate_mutants(source, max_mutants=max_mutants)
    sandbox = Sandbox(target.source_root)

    run_id = store.start_run("loop", {
        "repo": target.repo, "module": target.module_relpath,
        "max_rounds": max_rounds, "max_mutants": max_mutants,
        "backend": backend.name, "prompt_version": P.PROMPT_VERSION,
    })
    target_id = store.add_target(run_id, target.repo, target.module_relpath)

    base_cov, base_branch, base_ms = measure_baseline(target, mutants, sandbox)
    store.set_baseline(target_id, base_cov, base_branch, base_ms)

    accepted_sources: list[str] = []
    accepted_nodeids: list[str] = []
    iterations: list[IterationRecord] = []
    cur_cov, cur_branch = base_cov, base_branch
    cur_missing: list[int] = []

    def accepted_files() -> dict[str, str]:
        return {f"test_generated_r{i + 1}.py": s
                for i, s in enumerate(accepted_sources)}

    for round_no in range(1, max_rounds + 1):
        start = time.monotonic()
        if round_no == 1 or not accepted_sources:
            prompt = P.render_initial(target.module_name, source,
                                      target.import_stmt)
        else:
            prompt = P.render_iteration(
                target.module_name, source, target.import_stmt,
                cur_missing, "\n\n".join(accepted_sources))

        if isinstance(backend, ScriptedBackend):
            fname = (scripted_round_files[round_no - 1]
                     if scripted_round_files
                     and round_no <= len(scripted_round_files)
                     else f"round-{round_no}.txt")
            try:
                raw = backend.load(fname)
            except FileNotFoundError:
                break  # recorded generation budget spent
        else:
            raw = backend.complete(prompt, P.SYSTEM_PROMPT)

        gen = extract_code(raw)
        if gen.code is None:
            duration = time.monotonic() - start
            iterations.append(IterationRecord(round_no, None, gen.error,
                                              cur_cov, cur_branch, duration))
            store.add_iteration(target_id, round_no, prompt, raw, 0, 0, 0,
                                cur_cov, cur_branch, None, duration)
            continue

        test_name = f"test_generated_r{round_no}.py"
        filt = run_mutant_filter(sandbox, target.module_relpath,
                                 gen.code, mutants, test_name=test_name)
        kills: dict[str, int] = {}
        for mo in filt.mutant_outcomes:
            for k in mo.killer_tests:
                kills[k] = kills.get(k, 0) + 1
        if filt.surviving_tests:
            accepted_sources.append(gen.code)
            accepted_nodeids.extend(filt.surviving_tests)
            store.add_accepted_tests(
                target_id, round_no,
                [(nid, gen.code, kills.get(nid, 0))
                 for nid in filt.surviving_tests])
            cur_cov, cur_branch, cur_missing = _module_coverage(
                target, accepted_files())

        duration = time.monotonic() - start
        iterations.append(IterationRecord(round_no, filt, None,
                                          cur_cov, cur_branch, duration))
        store.add_iteration(target_id, round_no, prompt, raw,
                            len(filt.collected_nodeids),
                            len(filt.passing_real),
                            len(filt.surviving_tests),
                            cur_cov, cur_branch, None, duration)
        if not filt.surviving_tests:
            break  # no progress this round: stop iterating
        if cur_cov is not None and cur_cov >= coverage_target:
            break

    final_ms = None
    final_filter = None
    if accepted_sources:
        final_filter = run_mutant_filter(
            sandbox, target.module_relpath,
            "\n\n".join(accepted_sources), mutants)
        final_ms = final_filter.mutation_score
    store.set_final(target_id, cur_cov, final_ms, len(accepted_nodeids))

    return LoopResult(
        target=target,
        baseline_coverage=base_cov,
        baseline_branch=base_branch,
        baseline_mutation_score=base_ms,
        final_coverage=cur_cov,
        final_branch=cur_branch,
        final_mutation_score=final_ms,
        accepted_tests=accepted_nodeids,
        accepted_source="\n\n".join(accepted_sources),
        iterations=iterations,
        mutants_total=len(mutants),
        final_filter=final_filter,
    )


def run_baseline(target: Target, backend: Backend, store: Store,
                 max_mutants: int = MAX_MUTANTS_DEFAULT,
                 scripted_file: str = "baseline.txt") -> LoopResult:
    """The naive one-shot baseline (E2 comparison arm): one
    'write tests for this module' prompt, no iteration, and NO mutant
    filter - only the pass-on-real sanity check anyone would do."""
    source_path = target.source_root / target.module_relpath
    source = source_path.read_text(encoding="utf-8")
    mutants = generate_mutants(source, max_mutants=max_mutants)
    sandbox = Sandbox(target.source_root)

    run_id = store.start_run("baseline", {
        "repo": target.repo, "module": target.module_relpath,
        "backend": backend.name, "prompt_version": P.PROMPT_VERSION,
    })
    target_id = store.add_target(run_id, target.repo, target.module_relpath)

    start = time.monotonic()
    prompt = P.render_baseline(target.module_name, source, target.import_stmt)
    if isinstance(backend, ScriptedBackend):
        raw = backend.load(scripted_file)
    else:
        raw = backend.complete(prompt, P.SYSTEM_PROMPT)
    gen = extract_code(raw)

    accepted: list[str] = []
    cov = branch = ms = None
    collected = passing = 0
    if gen.code is not None:
        nodeids = sandbox.collect_nodeids({"test_baseline.py": gen.code})
        collected = len(nodeids)
        real = sandbox.run_pytest({"test_baseline.py": gen.code})
        passing = real.passed
        if real.all_passed and nodeids:
            accepted = nodeids
            cov, branch, _ = _module_coverage(
                target, {"test_baseline.py": gen.code})
            filt = run_mutant_filter(sandbox, target.module_relpath,
                                     gen.code, mutants,
                                     test_name="test_baseline.py")
            ms = filt.mutation_score
    store.add_iteration(target_id, 1, prompt, raw, collected, passing,
                        len(accepted), cov, branch, ms,
                        time.monotonic() - start)
    store.set_final(target_id, cov, ms, len(accepted))
    return LoopResult(target, None, None, None, cov, branch, ms, accepted,
                      gen.code or "", [], len(mutants))
