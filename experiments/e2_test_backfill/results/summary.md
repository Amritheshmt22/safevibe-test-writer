# E2 results - iterative Test-Writer vs naive one-shot baseline

Every number regenerated from `store.sqlite` by `testwriter report`. Generation side is pinned in `llm_outputs/`; all downstream metrics are recomputed.

| repo | module | existing coverage | baseline coverage (one-shot) | Test-Writer coverage | baseline mutation score | Test-Writer mutation score | accepted tests |
|------|--------|-------------------|--------------------------|----------------------|-------------------------|----------------------------|----------------|
| clint | clint/arguments.py | 15.0% | 26.3% | 94.2% | 12.3% | 61.4% | 35 |
| exrex | exrex.py | n/a | 28.8% | 77.4% | 13.5% | 74.3% | 44 |
| pox | pox/_disk.py | n/a | 71.2% | 100.0% | 38.5% | 69.2% | 14 |

Baseline arm = naive one-shot LLM suite, pass-on-real check only. 'existing coverage' = the repo's own suite where pytest-runnable (n/a = no runnable suite).
