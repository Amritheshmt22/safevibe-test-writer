# SafeVibe Test-Writer

**Component 2 of [SafeVibe](docs/architecture.md) ("Legacy Test-Writer"): an LLM agent that backfills regression tests for under-tested Python modules and proves them in a sandbox - keeping only tests that pass on the real code *and* kill at least one injected mutant.**

AI coding assistants happily produce test suites that look plausible but assert nothing. The Test-Writer closes that gap with a measurable loop:

```
pick low-coverage module -> generate candidate tests (LLM)
  -> run in sandbox -> MUTANT FILTER (pass on real code AND kill >= 1 mutant)
  -> measure coverage + mutation score -> feed missing lines back -> iterate
```

"The agent wrote tests" becomes a number a maintainer can watch: line/branch coverage delta, mutation score, and the share of generated tests that actually assert something.

## Why mutation filtering matters

In experiment E2 on real open-source modules (below), **about a third of LLM-generated tests passed on the real code but killed zero mutants** - they called the code and asserted trivia. Without the filter, those tests inflate coverage while adding no fault-detection ability. The filter rejects them, and the loop iterates on the remaining gaps.

## Installation

```bash
pip install -e .          # Python >= 3.10
```

## Quick start

```bash
# 1. measure a repo's existing coverage, flag under-tested modules
testwriter analyze --repo /path/to/repo --source mypackage --tests tests/

# 2. see what mutants the engine generates for a module
testwriter mutate --module mypackage/core.py --list

# 3. run the iterative Test-Writer loop (local, free, reproducible)
testwriter run --repo /path/to/repo --module mypackage/core.py \
    --backend ollama --model qwen2.5-coder:7b --rounds 3 \
    --out tests/test_generated.py

# 4. the naive one-shot baseline arm (for comparison)
testwriter baseline --repo /path/to/repo --module mypackage/core.py --backend ollama
```

### LLM backends (all free)

| backend | how | notes |
|---------|-----|-------|
| `ollama` (default) | runs against a local [Ollama](https://ollama.com) server | zero inference budget; pinned model + temperature 0.2 + seed 42 = reproducible |
| `openai` | any free hosted tier speaking the OpenAI chat API (OpenRouter free models, Gemini free tier, GitHub Models) | configure via `TESTWRITER_LLM_BASE_URL`, `TESTWRITER_LLM_API_KEY`, `TESTWRITER_LLM_MODEL` - keys come from the environment, never stored |
| `scripted` | replays recorded raw completions from a directory | powers the published, exactly reproducible experiment bundle |

## Experiment E2: iterative Test-Writer vs naive one-shot baseline

Research question RQ2 of the SafeVibe plan: *can an iterative, mutation-checked LLM test writer raise coverage and mutation score on real under-tested repositories beyond a naive one-shot LLM baseline?*

**Scope of the claim.** This is a pilot on 3 small, real repositories.
It demonstrates that the pipeline runs end to end and that, on these
targets, the iterative mutation-checked loop beats a naive one-shot
baseline on every metric. It is **not** a general claim that the loop
improves test quality across projects; the SafeVibe plan's full study is
10-20 repositories, and mutation-guided LLM test generation is an active
research area - a related-work comparison against published tools and
benchmarks is planned for the paper phase before any novelty framing.

**Targets** (real OSS modules, selected by measurement - see
[experiments/e2_test_backfill/candidates.md](experiments/e2_test_backfill/candidates.md)
including the popular libraries we measured and rejected for being too
well tested):

| repo | module | existing coverage |
|------|--------|-------------------|
| [exrex](https://github.com/asciimoo/exrex) | exrex.py | 13% |
| [clint](https://github.com/kennethreitz-archive/clint) | clint/arguments.py | 22% |
| [pox](https://github.com/uqfoundation/pox) | pox/_disk.py | 12% |

**Results** - full tables in
[experiments/e2_test_backfill/results/summary.md](experiments/e2_test_backfill/results/summary.md),
dashboard in
[experiments/e2_test_backfill/dashboard/index.html](experiments/e2_test_backfill/dashboard/index.html):

| repo | one-shot baseline coverage | Test-Writer coverage | one-shot mutation score | Test-Writer mutation score |
|------|---------------------------|----------------------|-------------------------|----------------------------|
| exrex | 28.8% | 77.4% | 13.5% | 74.3% |
| clint/arguments.py | 26.3% | 94.2% | 12.3% | 61.4% |
| pox/_disk.py | 71.2% | 100.0% | 38.5% | 69.2% |

Reproduce every number:

```bash
testwriter experiment \
  --config experiments/e2_test_backfill/config.json \
  --completions experiments/e2_test_backfill/llm_outputs \
  --store experiments/e2_test_backfill/results/store.sqlite \
  --results experiments/e2_test_backfill/results
testwriter report --store experiments/e2_test_backfill/results/store.sqlite \
  --results experiments/e2_test_backfill/results \
  --dashboard experiments/e2_test_backfill/dashboard
```

## Provenance

Every experiment run is auditable end to end:

- **Dataset sources**: upstream repo, pinned commit and license for each
  target are in `experiments/e2_test_backfill/config.json` /
  `targets/`; selection was by measured existing coverage
  (`candidates.md`, including measured rejects).
- **Generation record**: the exact prompt strings live in
  `experiments/e2_test_backfill/prompts/` and verbatim in
  `results/store.sqlite`; the raw completions in
  `experiments/e2_test_backfill/llm_outputs/` carry a
  [manifest](experiments/e2_test_backfill/llm_outputs/MANIFEST.md)
  naming the generator, the mode (scripted replay) and the date for
  every run.
- **Model identity**: the published bundle used an AI coding assistant
  (Instinct "Lumi") as the generator; re-running generation with a named
  local model via `--backend ollama` (pinned model, temperature 0.2,
  seed 42) or a free hosted tier via `--backend openai` is the supported
  path to reproduce with a different generator.

## How it works

- **Mutation engine** (`mutate.py`): six standard operators (AOR, ROR, LCR, UOI, CRP, RVR) applied to the module AST, one mutation per mutant, deterministic and capped. No external dependencies.
- **Sandbox** (`sandbox.py`): every test run is a fresh subprocess with a staged copy of the code, CPU/memory rlimits, a wall-clock timeout and a scrubbed environment. See [docs/architecture.md](docs/architecture.md) for the isolation model and its limits.
- **Mutant filter** (`filtering.py`): splits candidate files per test; a test survives iff it passes on the real code and kills >= 1 mutant. Kill attribution is per test; timeouts count as killed; mutants that break import are excluded from the score.
- **Iteration policy** (`loop.py`): after each accepted round, missing lines from coverage.py go back into the next prompt; the loop stops when a round accepts nothing, the round budget is spent, or the coverage target is met.
- **Artifact store** (`store.py`): every prompt, raw completion, filter verdict and metric in SQLite. No reported number is unrecoverable.

## Repository layout

```
src/testwriter/            the tool
tests/                     the tool's own test suite (19 tests)
experiments/e2_test_backfill/
  config.json              E2 targets with pinned upstream commits
  candidates.md            measured target selection (+ measured rejects)
  prompts/                 exact prompts sent
  llm_outputs/             raw recorded model completions
  targets/                 staged module sources (pinned commits)
  results/                 results.json, summary.md, store.sqlite
  dashboard/index.html     self-contained results dashboard
docs/architecture.md       design + sandbox model
docs/evaluation-hygiene.md reproducibility rules and known limits
```

## Development

```bash
pip install -e .
python -m pytest tests        # 19 tests
```

## Honest disclosure

Built with AI assistance (Instinct "Lumi") - code, recorded test suites and docs - per the SafeVibe plan's writing-hygiene rules; every experiment number is computed by the pipeline, never hand-written. Known limits (equivalent mutants, sandbox scope, 3-target E2 vs the plan's 10-20) are in [docs/evaluation-hygiene.md](docs/evaluation-hygiene.md). MIT licensed; target modules remain under their own licenses (see `experiments/e2_test_backfill/targets/`).

Part of the SafeVibe research project (Amrithesh MT and collaborators). Components 1 (Vibe-Code Firewall) and 3 (Agent-PR Shepherd) are separate work.
