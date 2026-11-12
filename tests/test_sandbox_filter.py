"""End-to-end sandbox + mutant-filter behaviour on a toy module."""
import textwrap
from pathlib import Path

from testwriter.filtering import run_mutant_filter
from testwriter.mutate import generate_mutants
from testwriter.sandbox import Sandbox

MODULE = textwrap.dedent('''
    def classify(n):
        """negative -> -1, zero -> 0, positive -> 1"""
        if n < 0:
            return -1
        if n == 0:
            return 0
        return 1


    def clamp(x, lo, hi):
        if x < lo:
            return lo
        if x > hi:
            return hi
        return x
''')

VACUOUS = textwrap.dedent('''
    import toy

    def test_nothing():
        toy.classify(5)
        toy.clamp(5, 1, 10)
        assert True
''')

REAL = textwrap.dedent('''
    import toy

    def test_classify_negative():
        assert toy.classify(-3) == -1

    def test_classify_zero():
        assert toy.classify(0) == 0

    def test_classify_positive():
        assert toy.classify(42) == 1

    def test_clamp_low():
        assert toy.clamp(-5, 1, 10) == 1

    def test_clamp_high():
        assert toy.clamp(99, 1, 10) == 10

    def test_clamp_inside():
        assert toy.clamp(5, 1, 10) == 5
''')

WRONG = textwrap.dedent('''
    import toy

    def test_wrong_expectation():
        assert toy.classify(5) == -7
''')


def _setup(tmp_path: Path):
    (tmp_path / "toy.py").write_text(MODULE)
    sandbox = Sandbox(tmp_path)
    mutants = generate_mutants(MODULE)
    return sandbox, mutants


def test_vacuous_test_is_rejected(tmp_path):
    sandbox, mutants = _setup(tmp_path)
    res = run_mutant_filter(sandbox, "toy.py", VACUOUS, mutants)
    assert res.passing_real  # it passes on real code
    assert res.surviving_tests == []  # but kills nothing
    assert len(res.weak_tests) == len(res.passing_real)


def test_real_asserting_tests_are_accepted_and_kill_mutants(tmp_path):
    sandbox, mutants = _setup(tmp_path)
    res = run_mutant_filter(sandbox, "toy.py", REAL, mutants)
    assert len(res.surviving_tests) == 6
    assert res.mutation_score is not None and res.mutation_score > 0.5


def test_failing_test_is_split_out(tmp_path):
    sandbox, mutants = _setup(tmp_path)
    mixed = REAL + WRONG.split("import toy", 1)[1]
    res = run_mutant_filter(sandbox, "toy.py", mixed, mutants)
    assert any("test_wrong_expectation" in n for n in res.failing_real)
    assert all("test_wrong_expectation" not in n for n in res.surviving_tests)
    assert len(res.surviving_tests) == 6


def test_uncollectable_file_is_rejected(tmp_path):
    sandbox, mutants = _setup(tmp_path)
    res = run_mutant_filter(sandbox, "toy.py", "this is not python(", mutants)
    assert res.collected_nodeids == []
    assert res.surviving_tests == []
