# Completion provenance manifest

How every recorded completion in this bundle was produced. Each row is one
experiment run: one prompt file sent, one raw completion recorded and
replayed verbatim through the `scripted` backend.

| target | arm / round | prompt (verbatim) | raw completion | generated |
|--------|-------------|-------------------|----------------|-----------|
| exrex | one-shot baseline | ../prompts/exrex-baseline.md | exrex/baseline.txt | 2026-11-12 |
| exrex | loop round 1 | ../prompts/exrex-round-1.md | exrex/round-1.txt | 2026-11-12 |
| exrex | loop round 2 | ../prompts/exrex-round-2.md | exrex/round-2.txt | 2026-11-12 |
| clint | one-shot baseline | ../prompts/clint-baseline.md | clint/baseline.txt | 2026-11-12 |
| clint | loop round 1 | ../prompts/clint-round-1.md | clint/round-1.txt | 2026-11-12 |
| clint | loop round 2 | ../prompts/clint-round-2.md | clint/round-2.txt | 2026-11-12 |
| pox | one-shot baseline | ../prompts/pox-baseline.md | pox/baseline.txt | 2026-11-12 |
| pox | loop round 1 | ../prompts/pox-round-1.md | pox/round-1.txt | 2026-11-12 |
| pox | loop round 2 | ../prompts/pox-round-2.md | pox/round-2.txt | 2026-11-12 |

- **Generator**: an AI coding assistant (Instinct "Lumi"), acting as the
  LLM in the loop. Prompt templates are versioned (`PROMPT_VERSION` in
  `src/testwriter/prompts.py`); the prompt files linked above are the
  exact strings sent, and round-2 files are pulled verbatim from
  `results/store.sqlite` (they embed the loop's missing-lines feedback).
- **Replay**: `testwriter experiment --completions experiments/e2_test_backfill/llm_outputs`
  replays these files byte-for-byte; the pipeline then re-runs sandbox
  execution, the mutant filter, coverage and mutation scoring from
  scratch. No downstream number is copied from the generation session.
- **Re-generation**: the same prompts can be sent to a local open-weight
  model (`--backend ollama`, e.g. qwen2.5-coder:7b, temperature 0.2,
  seed 42) or a free hosted tier (`--backend openai`) to reproduce the
  study with a different generator.
- **Dataset sources**: target modules are staged from the upstream
  repositories at the commits pinned in `../config.json`
  (exrex f180f21, clint 9d3693d, pox 7e75686), under
  `../targets/` with their own licenses.
