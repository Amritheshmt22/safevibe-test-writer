# E2 candidate selection (SafeVibe plan, week-1 deliverable)

Criterion from the plan: real open-source repositories (or modules) whose
existing test suites leave them under 30% line coverage. Every candidate
below was cloned and *measured* with coverage.py under pytest 9.2.0 /
coverage 7.16.2 on Python 3.10.12 - nothing here is guessed.

## Selected targets

| repo | upstream | pinned commit | module | measured coverage of existing suite |
|------|----------|---------------|--------|-------------------------------------|
| exrex | https://github.com/asciimoo/exrex | f180f21 | exrex.py | 13% (own tests.py is a script, not pytest-collectable; effectively no runnable suite) |
| clint | https://github.com/kennethreitz-archive/clint | 9d3693d | clint/arguments.py | 22% module (package total 28%; suite test_clint.py runs, 6 passed / 1 failed) |
| pox | https://github.com/uqfoundation/pox | 7e75686 | pox/_disk.py | 12% module (suite covers shutils.py/utils.py only; _disk.py has no tests) |

## Measured and rejected

Popular small libraries were *assumed* under-tested and measured anyway;
these did not meet the criterion and were excluded:

| repo | measured coverage | verdict |
|------|-------------------|---------|
| texttable | 92% | too well tested |
| rstr | 98% | too well tested |
| names | 100% | too well tested |
| moment | 75% | too well tested |
| metaphone | 86% | too well tested |
| Chronyk | 80% (21/72 tests failing) | too well tested + bit-rotted suite |
| python-titlecase | 79% | too well tested |
| pytimeparse | 97% on timeparse.py | too well tested |
| w2n | 95% | too well tested |
| javalang | 64% total (parse.py 31%) | above threshold |
| peep | does not import on modern Python/pip | unusable |
| fuzzy | C extension | out of scope (pure-Python pipeline) |

This selection step is itself reproducible: clone the pinned commits and
run `testwriter analyze --repo <path> --source <pkg> --tests <suite>`.
