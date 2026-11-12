"""The mutant filter: the heart of the Test-Writer.

A generated test only counts if it *asserts something real*. The filter
keeps a test iff:

1. it passes against the real (unmutated) code, and
2. it kills at least one injected mutant - i.e. the test fails when the
   code is subtly broken.

Everything else (tests that fail on real code, tests that vacuously pass
against every mutant, files that do not even collect) is rejected and
recorded, so the share of generated tests that survive the filter is
itself a reported metric (SafeVibe plan, experiment E2).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .mutate import Mutant
from .sandbox import Sandbox


@dataclass
class MutantOutcome:
    mutant_id: str
    status: str  # "killed" | "survived" | "incompetent" | "timeout"
    killer_tests: list[str] = field(default_factory=list)


@dataclass
class FilterResult:
    collected_nodeids: list[str]
    passing_real: list[str]
    failing_real: list[str]
    mutant_outcomes: list[MutantOutcome]
    surviving_tests: list[str]  # pass real AND kill >= 1 mutant
    weak_tests: list[str]  # pass real but kill nothing

    @property
    def killed(self) -> int:
        return sum(1 for m in self.mutant_outcomes if m.status in ("killed", "timeout"))

    @property
    def survived(self) -> int:
        return sum(1 for m in self.mutant_outcomes if m.status == "survived")

    @property
    def incompetent(self) -> int:
        return sum(1 for m in self.mutant_outcomes if m.status == "incompetent")

    @property
    def competent_mutants(self) -> int:
        return self.killed + self.survived

    @property
    def mutation_score(self) -> float | None:
        """Killed / competent mutants. Timeouts count as killed; mutants
        that cannot even be imported are excluded from the denominator."""
        if self.competent_mutants == 0:
            return None
        return self.killed / self.competent_mutants


def run_mutant_filter(sandbox: Sandbox, module_relpath: str,
                      test_source: str, mutants: list[Mutant],
                      test_name: str = "test_generated.py") -> FilterResult:
    """Run the full filter for one candidate test file against one module.

    *module_relpath* is the path of the mutated module inside the sandbox
    (e.g. "exrex.py" or "mypkg/core.py").
    """
    test_files = {test_name: test_source}

    nodeids = sandbox.collect_nodeids(test_files)
    if not nodeids:
        return FilterResult([], [], [], [], [], [])

    # Stage 1: keep only tests that pass on the real code.
    real = sandbox.run_pytest(test_files)
    if real.all_passed:
        passing = list(nodeids)
    else:
        passing = []
        for nid in nodeids:
            r = sandbox.run_pytest(test_files, nodeids=[nid])
            if r.all_passed:
                passing.append(nid)

    failing = [n for n in nodeids if n not in passing]
    if not passing:
        return FilterResult(nodeids, [], failing, [], [], [])

    # Stage 2: run the passing tests against every mutant.
    outcomes: list[MutantOutcome] = []
    kills_by_test: dict[str, list[str]] = {n: [] for n in passing}
    for mutant in mutants:
        r = sandbox.run_pytest(test_files,
                               overrides={module_relpath: mutant.source},
                               nodeids=passing)
        if r.timed_out:
            outcomes.append(MutantOutcome(mutant.id, "timeout", []))
            continue
        if r.all_passed:
            outcomes.append(MutantOutcome(mutant.id, "survived"))
            continue
        if r.failed_nodeids:
            killers = [n for n in r.failed_nodeids if n in kills_by_test]
            if not killers:
                # failed node not among collected (defensive) - still killed
                killers = []
            outcomes.append(MutantOutcome(mutant.id, "killed", killers))
            for k in killers:
                kills_by_test[k].append(mutant.id)
        else:
            # failures with no FAILED lines = import/collection error:
            # the mutant broke the module itself, so it says little
            # about assertion quality; excluded from the score.
            outcomes.append(MutantOutcome(mutant.id, "incompetent"))

    surviving = [n for n in passing if kills_by_test.get(n)]
    weak = [n for n in passing if not kills_by_test.get(n)]
    return FilterResult(nodeids, passing, failing, outcomes, surviving, weak)
