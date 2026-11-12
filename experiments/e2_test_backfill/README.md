# Experiment E2 - test backfill quality on real under-tested repos

Protocol (SafeVibe plan, section 6, E2; research question RQ2):

> Can an iterative, mutation-checked LLM test writer raise coverage and
> mutation score on real under-tested repositories beyond a naive
> one-shot LLM baseline?
> Hypothesis: sandboxed iteration plus the mutant filter yields larger,
> genuinely asserting test suites than one-shot generation.

## Arms

- **Arm A (naive baseline):** one-shot "write tests for this module"
  prompting (`prompts.BASELINE_ONESHOT_PROMPT`). The suite is kept if it
  passes on the real code; no iteration, no mutant filter - the way a
  developer would use a chat model today.
- **Arm B (Test-Writer):** the iterative loop: generate -> sandbox ->
  mutant filter -> keep surviving tests -> feed missing lines back ->
  iterate (max 3 rounds). Scored on the merged accepted suite.

Both arms use the same recorded generator (see
docs/evaluation-hygiene.md) with all prompts in `prompts/` and raw
completions in `llm_outputs/`.

## Targets

Real open-source modules under 30% existing line coverage, selected by
measurement - see `candidates.md` (including the popular repos we
measured and *rejected* for being too well tested).

| repo | module | why it qualifies |
|------|--------|------------------|
| exrex | exrex.py | 13%; shipped tests.py is a script, not a runnable suite |
| clint | clint/arguments.py | 22% module coverage |
| pox | pox/_disk.py | 12% module coverage, zero direct tests |

## Metrics

Per repo: line/branch coverage before vs after, mutation score
(killed/competent AST mutants) before vs after, share of generated
tests surviving the mutant filter, and per-round acceptance rates.
Everything is recomputed by:

```
pip install -e .
testwriter experiment \
  --config experiments/e2_test_backfill/config.json \
  --completions experiments/e2_test_backfill/llm_outputs \
  --store experiments/e2_test_backfill/results/store.sqlite \
  --results experiments/e2_test_backfill/results
```

Outputs: `results/results.json`, `results/store.sqlite`,
`dashboard/index.html`.

## Results

See `results/summary.md` (generated numbers with run metadata).
