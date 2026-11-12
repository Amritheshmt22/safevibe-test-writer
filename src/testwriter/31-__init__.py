"""SafeVibe Legacy Test-Writer (SafeVibe Component 2).

Iterative, mutation-checked LLM regression-test generation for
under-tested Python modules.

Pipeline: pick a low-coverage module -> generate candidate tests with an
LLM -> run them in a sandbox -> keep only tests that pass on the real
code AND kill at least one injected mutant -> measure coverage and
mutation-score deltas -> iterate with feedback.
"""

__version__ = "0.1.0"
