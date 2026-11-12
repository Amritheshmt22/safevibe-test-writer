"""SQLite artifact store.

Every run, target, iteration, candidate and metric is recorded so the
published evaluation bundle can regenerate every reported number
(SafeVibe plan, "Evaluation hygiene": no result is reported that the
bundle cannot regenerate).
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS run (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,            -- 'loop' | 'baseline' | 'experiment'
    started_at REAL NOT NULL,
    config_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS target (
    id INTEGER PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES run(id),
    repo TEXT NOT NULL,
    module TEXT NOT NULL,
    baseline_coverage REAL,
    baseline_branch_coverage REAL,
    baseline_mutation_score REAL,
    final_coverage REAL,
    final_mutation_score REAL,
    accepted_count INTEGER
);
CREATE TABLE IF NOT EXISTS iteration (
    id INTEGER PRIMARY KEY,
    target_id INTEGER NOT NULL REFERENCES target(id),
    round INTEGER NOT NULL,
    prompt TEXT NOT NULL,
    raw_output TEXT NOT NULL,
    candidates_collected INTEGER NOT NULL,
    passing_real INTEGER NOT NULL,
    surviving_filter INTEGER NOT NULL,
    coverage_after REAL,
    branch_coverage_after REAL,
    mutation_score_after REAL,
    duration_s REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS accepted_test (
    id INTEGER PRIMARY KEY,
    target_id INTEGER NOT NULL REFERENCES target(id),
    round INTEGER NOT NULL,
    nodeid TEXT NOT NULL,
    source TEXT NOT NULL,
    mutants_killed INTEGER NOT NULL
);
"""


class Store:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.executescript(_SCHEMA)

    def start_run(self, kind: str, config: dict) -> int:
        cur = self.db.execute(
            "INSERT INTO run (kind, started_at, config_json) VALUES (?,?,?)",
            (kind, time.time(), json.dumps(config, sort_keys=True)))
        self.db.commit()
        return cur.lastrowid

    def add_target(self, run_id: int, repo: str, module: str) -> int:
        cur = self.db.execute(
            "INSERT INTO target (run_id, repo, module) VALUES (?,?,?)",
            (run_id, repo, module))
        self.db.commit()
        return cur.lastrowid

    def set_baseline(self, target_id: int, coverage: float | None,
                     branch_coverage: float | None,
                     mutation_score: float | None) -> None:
        self.db.execute(
            "UPDATE target SET baseline_coverage=?, baseline_branch_coverage=?,"
            " baseline_mutation_score=? WHERE id=?",
            (coverage, branch_coverage, mutation_score, target_id))
        self.db.commit()

    def set_final(self, target_id: int, coverage: float | None,
                  mutation_score: float | None, accepted_count: int) -> None:
        self.db.execute(
            "UPDATE target SET final_coverage=?, final_mutation_score=?,"
            " accepted_count=? WHERE id=?",
            (coverage, mutation_score, accepted_count, target_id))
        self.db.commit()

    def add_iteration(self, target_id: int, round_no: int, prompt: str,
                      raw_output: str, collected: int, passing: int,
                      surviving: int, coverage_after: float | None,
                      branch_after: float | None, ms_after: float | None,
                      duration_s: float) -> None:
        self.db.execute(
            "INSERT INTO iteration (target_id, round, prompt, raw_output,"
            " candidates_collected, passing_real, surviving_filter,"
            " coverage_after, branch_coverage_after, mutation_score_after,"
            " duration_s) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (target_id, round_no, prompt, raw_output, collected, passing,
             surviving, coverage_after, branch_after, ms_after, duration_s))
        self.db.commit()

    def add_accepted_tests(self, target_id: int, round_no: int,
                           tests: list[tuple[str, str, int]]) -> None:
        self.db.executemany(
            "INSERT INTO accepted_test (target_id, round, nodeid, source,"
            " mutants_killed) VALUES (?,?,?,?,?)",
            [(target_id, round_no, nid, src, killed)
             for nid, src, killed in tests])
        self.db.commit()

    def close(self) -> None:
        self.db.close()
