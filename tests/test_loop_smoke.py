"""Full pipeline smoke test: scripted backend + toy module end to end.

Proves the whole loop runs: baseline measurement, generation replay,
mutant filter, acceptance, coverage improvement and store writes.
"""
import textwrap
from pathlib import Path

from testwriter.generate import ScriptedBackend
from testwriter.loop import Target, run_baseline, run_loop
from testwriter.store import Store

MODULE = textwrap.dedent('''
    def classify(n):
        if n < 0:
            return -1
        if n == 0:
            return 0
        return 1
''')

GOOD_TESTS = """\
```python
import toy

def test_negative():
    assert toy.classify(-10) == -1

def test_zero():
    assert toy.classify(0) == 0

def test_positive():
    assert toy.classify(7) == 1
```
"""

VACUOUS = """\
```python
import toy

def test_calls():
    toy.classify(1)
```
"""


def _target(tmp_path: Path) -> Target:
    (tmp_path / "toy.py").write_text(MODULE)
    return Target(repo="toyrepo", source_root=tmp_path,
                  module_relpath="toy.py", module_name="toy",
                  import_stmt="import toy")


def test_loop_accepts_asserting_tests(tmp_path):
    comp = tmp_path / "completions"
    comp.mkdir()
    (comp / "round-1.txt").write_text(GOOD_TESTS)
    store = Store(tmp_path / "s.sqlite")
    r = run_loop(_target(tmp_path), ScriptedBackend(comp), store)
    store.close()
    assert r.final_coverage == 100.0
    assert r.final_mutation_score is not None and r.final_mutation_score > 0.3
    assert len(r.accepted_tests) == 3


def test_loop_rejects_vacuous_and_stops(tmp_path):
    comp = tmp_path / "completions"
    comp.mkdir()
    (comp / "round-1.txt").write_text(VACUOUS)
    store = Store(tmp_path / "s.sqlite")
    r = run_loop(_target(tmp_path), ScriptedBackend(comp), store)
    store.close()
    assert r.accepted_tests == []
    assert len(r.iterations) == 1  # stopped after the empty round


def test_baseline_arm_runs(tmp_path):
    comp = tmp_path / "completions"
    comp.mkdir()
    (comp / "baseline.txt").write_text(GOOD_TESTS)
    store = Store(tmp_path / "s.sqlite")
    r = run_baseline(_target(tmp_path), ScriptedBackend(comp), store)
    store.close()
    assert r.final_coverage == 100.0
    assert len(r.accepted_tests) == 3
