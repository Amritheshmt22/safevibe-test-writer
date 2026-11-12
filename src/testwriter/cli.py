"""testwriter command-line interface.

Commands:
  analyze     measure a repo's existing coverage, flag under-tested modules
  mutate      list the mutants the engine generates for a module
  run         the full iterative Test-Writer loop on one module
  baseline    the naive one-shot comparison arm on one module
  experiment  run experiment E2 from a config file
  report      rebuild the dashboard/results from a store
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .coverage_analysis import measure_coverage
from .experiment import run_experiment
from .generate import ScriptedBackend, backend_from_config
from .loop import Target, run_baseline, run_loop
from .mutate import generate_mutants
from .report import write_dashboard, write_results
from .store import Store


def _cmd_analyze(args: argparse.Namespace) -> int:
    cov = measure_coverage(Path(args.repo), source=args.source,
                           test_paths=args.tests)
    print(f"total line coverage: {cov.total_percent:.1f}%"
          + (f", branch: {cov.branch_percent:.1f}%"
             if cov.branch_percent is not None else ""))
    for path, fc in sorted(cov.files.items(), key=lambda kv: kv[1].percent):
        flag = "  <-- under-tested" if fc.percent < args.threshold else ""
        print(f"  {fc.percent:6.1f}%  {path}{flag}")
    return 0


def _cmd_mutate(args: argparse.Namespace) -> int:
    source = Path(args.module).read_text(encoding="utf-8")
    mutants = generate_mutants(source, max_mutants=args.max_mutants)
    print(f"{len(mutants)} mutants for {args.module}")
    if args.list:
        for m in mutants:
            print(f"  {m.id}  {m.operator:4s} line {m.lineno:<4d} {m.description}")
    return 0


def _target_from_args(args: argparse.Namespace) -> Target:
    module = Path(args.module)
    return Target(
        repo=args.repo_name or Path(args.repo).name,
        source_root=Path(args.repo).resolve(),
        module_relpath=str(module),
        module_name=args.module_name or module.stem,
        import_stmt=args.import_stmt or f"import {module.stem}",
        existing_test_paths=args.existing_tests or [],
    )


def _print_result(r) -> None:
    print(f"repo: {r.target.repo}  module: {r.target.module_relpath}")
    print(f"  baseline coverage:        {r.baseline_coverage}")
    print(f"  final coverage:           {r.final_coverage}")
    print(f"  baseline mutation score:  {r.baseline_mutation_score}")
    print(f"  final mutation score:     {r.final_mutation_score}")
    print(f"  accepted tests:           {len(r.accepted_tests)}")


def _cmd_run(args: argparse.Namespace) -> int:
    store = Store(args.store)
    try:
        if args.backend == "scripted":
            backend = ScriptedBackend(args.completions)
        else:
            backend = backend_from_config({"backend": args.backend,
                                           "model": args.model})
        result = run_loop(_target_from_args(args), backend, store,
                          max_rounds=args.rounds,
                          max_mutants=args.max_mutants)
    finally:
        store.close()
    _print_result(result)
    if args.out:
        Path(args.out).write_text(result.accepted_source, encoding="utf-8")
        print(f"  accepted suite written to {args.out}")
    return 0


def _cmd_baseline(args: argparse.Namespace) -> int:
    store = Store(args.store)
    try:
        if args.backend == "scripted":
            backend = ScriptedBackend(args.completions)
        else:
            backend = backend_from_config({"backend": args.backend,
                                           "model": args.model})
        result = run_baseline(_target_from_args(args), backend, store,
                              max_mutants=args.max_mutants)
    finally:
        store.close()
    _print_result(result)
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    from .report import rebuild_from_store
    rebuild_from_store(args.store, args.results, args.dashboard)
    print(f"reports rebuilt from {args.store}")
    return 0


def _cmd_experiment(args: argparse.Namespace) -> int:
    arms = run_experiment(args.config, args.store, args.results,
                          args.completions, max_rounds=args.rounds,
                          max_mutants=args.max_mutants,
                          only_repo=args.repo)
    for r in arms["loop"]:
        _print_result(r)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="testwriter",
                                 description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version",
                    version=f"%(prog)s {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("analyze", help="measure existing coverage")
    p.add_argument("--repo", required=True)
    p.add_argument("--source", required=True,
                   help="package/module to measure, e.g. exrex")
    p.add_argument("--tests", nargs="+", required=True)
    p.add_argument("--threshold", type=float, default=30.0)
    p.set_defaults(func=_cmd_analyze)

    p = sub.add_parser("mutate", help="list mutants for a module")
    p.add_argument("--module", required=True)
    p.add_argument("--max-mutants", type=int, default=150)
    p.add_argument("--list", action="store_true")
    p.set_defaults(func=_cmd_mutate)

    for name, func, helptext in (("run", _cmd_run, "iterative Test-Writer loop"),
                                 ("baseline", _cmd_baseline, "one-shot baseline arm")):
        p = sub.add_parser(name, help=helptext)
        p.add_argument("--repo", required=True,
                       help="path to the repository checkout (sandbox root)")
        p.add_argument("--repo-name", default=None)
        p.add_argument("--module", required=True,
                       help="module path relative to --repo")
        p.add_argument("--module-name", default=None)
        p.add_argument("--import-stmt", default=None)
        p.add_argument("--existing-tests", nargs="*", default=[])
        p.add_argument("--backend", choices=["ollama", "openai", "scripted"],
                       default="ollama")
        p.add_argument("--model", default="qwen2.5-coder:7b")
        p.add_argument("--completions", default=None,
                       help="directory of recorded completions (scripted)")
        p.add_argument("--rounds", type=int, default=3)
        p.add_argument("--max-mutants", type=int, default=150)
        p.add_argument("--store", default="testwriter.sqlite")
        p.add_argument("--out", default=None,
                       help="write the accepted suite here (run only)")
        p.set_defaults(func=func)

    p = sub.add_parser("experiment", help="run experiment E2")
    p.add_argument("--config", required=True)
    p.add_argument("--completions", required=True)
    p.add_argument("--store", required=True)
    p.add_argument("--results", required=True)
    p.add_argument("--rounds", type=int, default=3)
    p.add_argument("--max-mutants", type=int, default=150)
    p.add_argument("--repo", default=None, help="only this repo")
    p.set_defaults(func=_cmd_experiment)

    p = sub.add_parser("report", help="rebuild results/dashboard from a store")
    p.add_argument("--store", required=True)
    p.add_argument("--results", required=True)
    p.add_argument("--dashboard", default=None)
    p.set_defaults(func=_cmd_report)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
