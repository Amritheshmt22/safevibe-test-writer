# SafeVibe Test-Writer architecture

Component 2 of the SafeVibe trust pipeline ("Legacy Test-Writer"):
backfill regression tests for under-tested modules and prove them in a
sandbox, with a mutant filter that keeps only tests which actually
assert something.

```
             ┌────────────────────────────────────────────────────┐
             │                    one module                       │
             │                                                    │
  existing   │  1. baseline: coverage + mutation score (existing  │
  suite ─────┼──> suite, if pytest-runnable)                      │
             │                                                    │
  LLM ───────┼──> 2. generate candidate tests                     │
  (Ollama /  │     (pinned prompts, missing-lines feedback)       │
   free tier │                                                    │
   / replay) │  3. sandbox: pytest in a scrubbed subprocess with  │
             │     rlimits, timeouts, fresh temp dir              │
             │                                                    │
             │  4. mutant filter: keep tests that pass on real    │
             │     code AND kill >= 1 AST mutant                  │
             │                                                    │
             │  5. measure coverage delta + missing lines,        │
             │     feed back to (2) until no progress / budget    │
             │                                                    │
             │  6. merged suite -> final mutation score           │
             └────────────────────────────────────────────────────┘
                    │ every prompt, completion, verdict, metric
                    ▼
             SQLite artifact store -> results.json + dashboard.html
```

## Modules

| module | responsibility |
|--------|----------------|
| `mutate.py` | deterministic AST mutants (AOR, ROR, LCR, UOI, CRP, RVR) |
| `sandbox.py` | staged subprocess pytest runs (rlimits, timeout, scrubbed env) |
| `coverage_analysis.py` | coverage.py line+branch measurement, missing lines |
| `filtering.py` | the mutant filter + per-test kill attribution |
| `generate.py` | LLM backends: Ollama, OpenAI-compatible free tiers, scripted replay |
| `prompts.py` | pinned, versioned prompt templates |
| `loop.py` | the iterative loop and the one-shot baseline arm |
| `store.py` | SQLite artifact store |
| `report.py` | results.json, Markdown summary, static HTML dashboard |
| `experiment.py` | experiment E2 driver |
| `cli.py` | the `testwriter` command |

## Sandbox model

Process isolation, not a container: each pytest run gets a fresh temp
copy of the target, CPU/address-space rlimits, a wall-clock timeout and
a scrubbed environment. This makes runs reproducible and stops runaway
or destructive tests; it is not a security boundary against malicious
code. A Docker-backed runner behind the same interface is future work
(the SafeVibe plan names Docker; the experiment protocol only requires
isolated, reproducible runs).

## Mutation engine

Mutants are produced from the module AST, one mutation per mutant, in
sorted source order, capped (default 150) with an evenly spaced
deterministic sample. `PYTHONHASHSEED=0` in the sandbox plus pinned
operator order make runs reproducible. Equivalent-mutant detection is
out of scope for v1 (see docs/evaluation-hygiene.md).
