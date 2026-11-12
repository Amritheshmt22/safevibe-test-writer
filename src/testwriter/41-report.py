"""Reporting: JSON results, Markdown summary, and a static HTML dashboard.

The dashboard is a single self-contained HTML file (inline CSS and SVG
bar charts, no JavaScript, no external assets) so the evaluation bundle
stays a plain folder anyone can open (SafeVibe plan, Data layer).
"""
from __future__ import annotations

import html
import json
from dataclasses import asdict
from pathlib import Path

from .loop import LoopResult


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.1f}%"


def result_to_dict(r: LoopResult) -> dict:
    iterations = []
    for it in r.iterations:
        f = it.filter_result
        iterations.append({
            "round": it.round,
            "generation_error": it.generation_error,
            "candidates_collected": len(f.collected_nodeids) if f else 0,
            "passing_real": len(f.passing_real) if f else 0,
            "surviving_filter": len(f.surviving_tests) if f else 0,
            "weak_tests": len(f.weak_tests) if f else 0,
            "mutants_killed_this_round": f.killed if f else 0,
            "mutation_score_this_round": f.mutation_score if f else None,
            "coverage_after": it.coverage_after,
            "branch_coverage_after": it.branch_after,
            "duration_s": round(it.duration_s, 2),
        })
    final = r.final_filter
    return {
        "repo": r.target.repo,
        "module": r.target.module_relpath,
        "mutants_total": r.mutants_total,
        "baseline_coverage": r.baseline_coverage,
        "baseline_branch_coverage": r.baseline_branch,
        "baseline_mutation_score": r.baseline_mutation_score,
        "final_coverage": r.final_coverage,
        "final_branch_coverage": r.final_branch,
        "final_mutation_score": r.final_mutation_score,
        "accepted_tests": len(r.accepted_tests),
        "final_filter": None if final is None else {
            "killed": final.killed,
            "survived": final.survived,
            "incompetent": final.incompetent,
            "mutation_score": final.mutation_score,
        },
        "iterations": iterations,
    }


def write_results(results: list[LoopResult], out_dir: Path | str) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    data = [result_to_dict(r) for r in results]
    (out_dir / "results.json").write_text(json.dumps(data, indent=2))
    return out_dir / "results.json"


def _bar(label: str, before: float | None, after: float | None,
         width: int = 420) -> str:
    b = before or 0.0
    a = after or 0.0
    bb = width * b / 100
    ab = width * a / 100
    return f"""
    <div class="bar-row">
      <div class="bar-label">{html.escape(label)}</div>
      <svg width="{width + 70}" height="46" role="img">
        <rect x="0" y="4" width="{bb:.1f}" height="14" fill="#c9d1d9"/>
        <text x="{bb + 5:.1f}" y="15" font-size="11" fill="#666">{_pct(before)}</text>
        <rect x="0" y="24" width="{ab:.1f}" height="14" fill="#2da44e"/>
        <text x="{ab + 5:.1f}" y="35" font-size="11" fill="#1a7f37">{_pct(after)}</text>
      </svg>
    </div>"""


def write_dashboard(arms: dict[str, list[LoopResult]], out_dir: Path | str,
                    title: str = "SafeVibe Test-Writer - E2 results") -> Path:
    """Render the dashboard for experiment arms (e.g. baseline vs loop)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    loop_results = arms.get("loop", [])
    base_results = {r.target.repo: r for r in arms.get("baseline", [])}

    rows = []
    for r in loop_results:
        b = base_results.get(r.target.repo)
        rows.append(f"""<tr>
<td>{html.escape(r.target.repo)}</td>
<td>{_pct(r.baseline_coverage)}</td>
<td>{_pct(b.final_coverage if b else None)}</td>
<td>{_pct(r.final_coverage)}</td>
<td>{_pct(b.final_mutation_score * 100 if b and b.final_mutation_score is not None else None)}</td>
<td>{_pct(r.final_mutation_score * 100 if r.final_mutation_score is not None else None)}</td>
<td>{len(r.accepted_tests)}</td>
</tr>""")

    bars = []
    for r in loop_results:
        bars.append(f"<h3>{html.escape(r.target.repo)}"
                    f" / {html.escape(r.target.module_relpath)}</h3>")
        bars.append(_bar("line coverage (grey = existing suite, green = after Test-Writer)",
                         r.baseline_coverage, r.final_coverage))
        bars.append(_bar("mutation score (grey = existing suite, green = after Test-Writer)",
                         None if r.baseline_mutation_score is None
                         else r.baseline_mutation_score * 100,
                         None if r.final_mutation_score is None
                         else r.final_mutation_score * 100))

    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ font-family: -apple-system, 'Segoe UI', Roboto, sans-serif; margin: 2rem auto; max-width: 900px; color: #1f2328; }}
table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
th, td {{ border: 1px solid #d0d7de; padding: 6px 10px; text-align: left; font-size: 14px; }}
th {{ background: #f6f8fa; }}
h1 {{ font-size: 1.5rem; }} h2 {{ font-size: 1.15rem; margin-top: 2rem; }}
.bar-row {{ display: flex; align-items: center; gap: 8px; margin: 2px 0; }}
.bar-label {{ width: 0; overflow: visible; white-space: nowrap; font-size: 0; }}
.note {{ color: #57606a; font-size: 13px; }}
</style></head><body>
<h1>{html.escape(title)}</h1>
<p class="note">Every number on this page is computed by the pipeline and can be
regenerated from the artifact store in this bundle
(<code>results/store.sqlite</code> + <code>results/results.json</code>).</p>
<h2>Per-repository results</h2>
<table>
<tr><th>repo</th><th>existing coverage</th><th>one-shot baseline coverage</th>
<th>Test-Writer coverage</th><th>one-shot mutation score</th>
<th>Test-Writer mutation score</th><th>accepted tests</th></tr>
{''.join(rows)}
</table>
<h2>Coverage and mutation score</h2>
{''.join(bars)}
</body></html>"""
    path = out_dir / "index.html"
    path.write_text(page, encoding="utf-8")
    return path


# ---------------------------------------------------------------------
# Rebuild reports from the artifact store
# ---------------------------------------------------------------------

def rebuild_from_store(store_path: Path | str, out_dir: Path | str,
                       dashboard_dir: Path | str | None = None) -> dict:
    """Rebuild results.json, summary.md and the dashboard from a store.

    Lets one store accumulate several per-repo experiment runs and still
    produce one combined report set.
    """
    import sqlite3

    db = sqlite3.connect(store_path)
    rows = db.execute(
        """SELECT t.id, r.kind, t.repo, t.module,
                  t.baseline_coverage, t.baseline_branch_coverage,
                  t.baseline_mutation_score,
                  t.final_coverage, t.final_mutation_score, t.accepted_count
           FROM target t JOIN run r ON r.id = t.run_id
           ORDER BY t.repo, r.kind""").fetchall()
    targets = []
    for (tid, kind, repo, module, bc, bbc, bms, fc, fms, acc) in rows:
        iters = db.execute(
            """SELECT round, candidates_collected, passing_real,
                      surviving_filter, coverage_after, duration_s
               FROM iteration WHERE target_id=? ORDER BY round""",
            (tid,)).fetchall()
        targets.append({
            "arm": kind, "repo": repo, "module": module,
            "baseline_coverage": bc, "baseline_branch_coverage": bbc,
            "baseline_mutation_score": bms,
            "final_coverage": fc, "final_mutation_score": fms,
            "accepted_tests": acc,
            "iterations": [
                {"round": r0, "candidates_collected": c, "passing_real": p,
                 "surviving_filter": s, "coverage_after": ca,
                 "duration_s": round(d, 2)}
                for (r0, c, p, s, ca, d) in iters],
        })
    db.close()

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "results.json").write_text(json.dumps(targets, indent=2))

    loops = {t["repo"]: t for t in targets if t["arm"] == "loop"}
    bases = {t["repo"]: t for t in targets if t["arm"] == "baseline"}

    def pct(x):
        return "n/a" if x is None else f"{x:.1f}%"

    def mspct(x):
        return "n/a" if x is None else f"{x * 100:.1f}%"

    lines = ["# E2 results - iterative Test-Writer vs naive one-shot baseline",
             "",
             "Every number regenerated from `store.sqlite` by "
             "`testwriter report`. Generation side is pinned in "
             "`llm_outputs/`; all downstream metrics are recomputed.",
             "",
             "| repo | module | existing coverage | baseline coverage "
             "(one-shot) | Test-Writer coverage | baseline mutation "
             "score | Test-Writer mutation score | accepted tests |",
             "|------|--------|-------------------|--------------------------"
             "|----------------------|-------------------------|"
             "----------------------------|----------------|"]
    for repo, t in sorted(loops.items()):
        b = bases.get(repo, {})
        lines.append(
            f"| {repo} | {t['module']} | {pct(t['baseline_coverage'])} "
            f"| {pct(b.get('final_coverage'))} "
            f"| {pct(t['final_coverage'])} "
            f"| {mspct(b.get('final_mutation_score'))} "
            f"| {mspct(t['final_mutation_score'])} "
            f"| {t['accepted_tests']} |")
    lines += ["",
              "Baseline arm = naive one-shot LLM suite, pass-on-real check "
              "only. 'existing coverage' = the repo's own suite where "
              "pytest-runnable (n/a = no runnable suite).",
              ""]
    (out_dir / "summary.md").write_text("\n".join(lines))

    if dashboard_dir:
        bars = []
        for repo, t in sorted(loops.items()):
            b = bases.get(repo, {})
            bars.append(f"<h3>{html.escape(repo)} / "
                        f"{html.escape(t['module'])}</h3>")
            bars.append(_bar("existing suite coverage",
                             t["baseline_coverage"], t["baseline_coverage"]))
            bars.append(_bar("one-shot baseline -> Test-Writer: line coverage",
                             b.get("final_coverage"), t["final_coverage"]))
            bars.append(_bar(
                "one-shot baseline -> Test-Writer: mutation score",
                None if b.get("final_mutation_score") is None
                else b["final_mutation_score"] * 100,
                None if t["final_mutation_score"] is None
                else t["final_mutation_score"] * 100))
        rows_html = []
        for repo, t in sorted(loops.items()):
            b = bases.get(repo, {})
            rows_html.append(
                f"<tr><td>{html.escape(repo)}</td>"
                f"<td>{pct(t['baseline_coverage'])}</td>"
                f"<td>{pct(b.get('final_coverage'))}</td>"
                f"<td>{pct(t['final_coverage'])}</td>"
                f"<td>{mspct(b.get('final_mutation_score'))}</td>"
                f"<td>{mspct(t['final_mutation_score'])}</td>"
                f"<td>{t['accepted_tests']}</td></tr>")
        dashboard_dir = Path(dashboard_dir)
        dashboard_dir.mkdir(parents=True, exist_ok=True)
        page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>SafeVibe Test-Writer - E2 results</title>
<style>
body {{ font-family: -apple-system, 'Segoe UI', Roboto, sans-serif; margin: 2rem auto; max-width: 900px; color: #1f2328; }}
table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
th, td {{ border: 1px solid #d0d7de; padding: 6px 10px; text-align: left; font-size: 14px; }}
th {{ background: #f6f8fa; }}
h1 {{ font-size: 1.5rem; }} h2 {{ font-size: 1.15rem; margin-top: 2rem; }}
.note {{ color: #57606a; font-size: 13px; }}
</style></head><body>
<h1>SafeVibe Test-Writer - experiment E2</h1>
<p class="note">Every number on this page is recomputed from the artifact
store (<code>results/store.sqlite</code>) by <code>testwriter report</code>.
Grey bars: before / naive one-shot baseline. Green bars: after the
iterative mutation-checked Test-Writer.</p>
<h2>Per-repository results</h2>
<table>
<tr><th>repo</th><th>existing coverage</th><th>one-shot coverage</th>
<th>Test-Writer coverage</th><th>one-shot mutation score</th>
<th>Test-Writer mutation score</th><th>accepted tests</th></tr>
{''.join(rows_html)}
</table>
<h2>Coverage and mutation score</h2>
{''.join(bars)}
</body></html>"""
        (dashboard_dir / "index.html").write_text(page, encoding="utf-8")
    return {"targets": targets}
