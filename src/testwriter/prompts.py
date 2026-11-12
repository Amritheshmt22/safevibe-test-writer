"""Pinned prompt templates for test generation.

Prompt text is part of the experiment: it is versioned
(PROMPT_VERSION) and every prompt actually sent to a model is stored
verbatim in the artifact store / experiment bundle so a run can be
reproduced exactly (SafeVibe plan, "Evaluation hygiene").
"""
from __future__ import annotations

PROMPT_VERSION = "1.0"

SYSTEM_PROMPT = """\
You are a meticulous test engineer. You write pytest regression tests for
existing Python code. Rules:
- Output ONLY Python code inside one ```python fenced block. No prose.
- Tests must call the real functions/classes of the module and assert on
  the values they actually return. Never assert something the code does
  not guarantee.
- No mocking of the module under test. No network, no files outside the
  test itself, no sleeps, no randomness without a fixed seed.
- Every test must fail if the code's behaviour were subtly wrong
  (wrong constant, flipped comparison, swapped operator).
- Keep tests deterministic, fast (<1s each) and independent.
"""

INITIAL_PROMPT = """\
Module under test: `{module_name}`

```python
{module_source}
```

Write a pytest test file that thoroughly exercises this module's
observable behaviour: normal cases, boundary values, edge cases and
error cases. Import the module as `{import_stmt}`.
"""

ITERATION_PROMPT = """\
Module under test: `{module_name}`

```python
{module_source}
```

The test file below is already accepted. These lines are still NOT
covered: {missing_lines}.

```python
{existing_tests}
```

Write a NEW pytest test file containing ONLY additional tests that cover
the missing lines and any related edge cases. Do not repeat existing
tests. Import the module as `{import_stmt}`.
"""

BASELINE_ONESHOT_PROMPT = """\
Module under test: `{module_name}`

```python
{module_source}
```

Write tests for this module. Import the module as `{import_stmt}`.
"""


def render_initial(module_name: str, module_source: str, import_stmt: str) -> str:
    return INITIAL_PROMPT.format(module_name=module_name,
                                 module_source=module_source,
                                 import_stmt=import_stmt)


def render_iteration(module_name: str, module_source: str, import_stmt: str,
                     missing_lines: list[int], existing_tests: str) -> str:
    return ITERATION_PROMPT.format(module_name=module_name,
                                   module_source=module_source,
                                   import_stmt=import_stmt,
                                   missing_lines=", ".join(map(str, missing_lines[:80])),
                                   existing_tests=existing_tests)


def render_baseline(module_name: str, module_source: str, import_stmt: str) -> str:
    return BASELINE_ONESHOT_PROMPT.format(module_name=module_name,
                                          module_source=module_source,
                                          import_stmt=import_stmt)
