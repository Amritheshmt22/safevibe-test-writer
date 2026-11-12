from pathlib import Path

from testwriter.coverage_analysis import measure_coverage
from testwriter.store import Store


def test_measure_coverage_partial(tmp_path):
    (tmp_path / "toy.py").write_text(
        "def f(x):\n    if x > 0:\n        return 1\n    return -1\n")
    tests = {"test_toy.py": "import toy\n\ndef test_pos():\n    assert toy.f(1) == 1\n"}
    cov = measure_coverage(tmp_path, source="toy", test_files=tests)
    fc = cov.files[next(iter(cov.files))]
    assert 0 < fc.percent < 100
    assert fc.missing_lines  # the `return -1` line is missing


def test_store_roundtrip(tmp_path):
    store = Store(tmp_path / "s.sqlite")
    run_id = store.start_run("loop", {"a": 1})
    tid = store.add_target(run_id, "repo", "mod.py")
    store.set_baseline(tid, 10.0, 5.0, 0.1)
    store.add_iteration(tid, 1, "prompt", "raw", 3, 2, 1, 50.0, 40.0, 0.6, 1.5)
    store.add_accepted_tests(tid, 1, [("t.py::test_a", "src", 4)])
    store.close()

    import sqlite3
    db = sqlite3.connect(tmp_path / "s.sqlite")
    assert db.execute("SELECT kind FROM run").fetchone()[0] == "loop"
    assert db.execute("SELECT baseline_coverage FROM target").fetchone()[0] == 10.0
    assert db.execute("SELECT surviving_filter FROM iteration").fetchone()[0] == 1
    assert db.execute("SELECT mutants_killed FROM accepted_test").fetchone()[0] == 4
    db.close()
