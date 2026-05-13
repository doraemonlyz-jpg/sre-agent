"""
Command-line interface.

Examples:
  sre-agent scenarios                                   # list mock scenarios
  sre-agent investigate --scenario redis-pool-exhaustion
  sre-agent investigate --service checkout-api --severity SEV-1 \\
                        --description "p99 latency 3.2s, error rate 12%"
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from uuid import uuid4

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from sre_agent.graph import build_graph
from sre_agent.logging import setup_logging
from sre_agent.providers.mock import MockProvider
from sre_agent.schemas import AlertIn, Severity

app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="SRE Agent — multi-agent on-call assistant.",
)
console = Console()


@app.callback()
def _root() -> None:
    setup_logging()


@app.command()
def scenarios() -> None:
    """List the bundled mock scenarios."""
    mp = MockProvider()
    table = Table(title="Mock scenarios", box=box.ROUNDED, header_style="bold cyan")
    table.add_column("ID", style="green")
    table.add_column("Label")
    table.add_column("Service", style="magenta")
    for s in mp.list_scenarios():
        table.add_row(s["id"], s["label"], s["service"])
    console.print(table)


@app.command()
def investigate(
    scenario: str | None = typer.Option(
        None,
        "--scenario",
        "-s",
        help="Mock scenario ID (from `sre-agent scenarios`).",
    ),
    service: str | None = typer.Option(None, "--service", help="Service name (custom alert)."),
    severity: str | None = typer.Option(
        "SEV-2", "--severity", help="SEV-1 | SEV-2 | SEV-3 | SEV-4."
    ),
    description: str | None = typer.Option(
        None, "--description", "-d", help="Alert description."
    ),
    show_events: bool = typer.Option(True, help="Print live agent events."),
    json_out: bool = typer.Option(False, "--json", help="Dump the full report as JSON."),
) -> None:
    """Run a full investigation through the LangGraph."""
    if scenario:
        mp = MockProvider()
        try:
            seed = mp.get_scenario_alert(scenario)
        except KeyError:
            console.print(f"[red]Unknown scenario: {scenario}[/red]")
            raise typer.Exit(2)
        alert = AlertIn(
            service=seed["service"],
            severity=Severity(seed["severity"]),
            description=seed["description"],
            started_at=seed.get("started_at") or datetime.now(timezone.utc),
            tags=seed.get("tags", []),
            scenario_id=scenario,
        )
    elif service and description:
        alert = AlertIn(
            service=service,
            severity=Severity(severity or "SEV-2"),
            description=description,
            started_at=datetime.now(timezone.utc),
            tags=[],
        )
    else:
        console.print("[red]Pass either --scenario OR --service + --description.[/red]")
        raise typer.Exit(2)

    console.print(
        Panel.fit(
            f"[bold]Service:[/bold] {alert.service}    "
            f"[bold]Severity:[/bold] {alert.severity.value}\n"
            f"[bold]Description:[/bold] {alert.description}",
            title="[cyan]Alert[/cyan]",
            border_style="cyan",
        )
    )

    graph = build_graph()
    thread_id = f"cli-{uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}

    if show_events:
        console.print(f"\n[dim]Streaming agent events (thread_id={thread_id})...[/dim]\n")

    final_state = None
    for chunk in graph.stream({"alert": alert, "events": []}, config=config):
        for node_name, partial in chunk.items():
            if show_events:
                for ev in partial.get("events", []) or []:
                    console.print(
                        f"  [dim]{ev['ts'][11:19]}[/dim]  "
                        f"[bold cyan]{ev['agent']:>22}[/bold cyan]  "
                        f"[yellow]{ev['kind']:>8}[/yellow]  {ev['message']}"
                    )
            final_state = partial

    # Fetch final assembled state from the checkpointer.
    state = graph.get_state(config).values
    report = state.get("report")
    if not report:
        console.print("[red]No report produced.[/red]")
        raise typer.Exit(1)

    if json_out:
        sys.stdout.write(report.model_dump_json(indent=2, exclude_none=True))
        sys.stdout.write("\n")
        return

    _print_report_pretty(report)


def _print_report_pretty(report) -> None:
    elapsed = ""
    if report.diagnosed_at and report.started_at:
        ms = int((report.diagnosed_at - report.started_at).total_seconds() * 1000)
        elapsed = f"  (took {ms}ms)"

    color = {"diagnosed": "green", "no_signal": "yellow", "failed": "red"}.get(report.phase, "white")
    console.print(
        Panel.fit(
            f"[{color}]{report.phase.upper()}[/{color}]{elapsed}",
            title="[bold]Incident outcome[/bold]",
            border_style=color,
        )
    )

    if report.hypotheses and report.hypotheses.hypotheses:
        t = Table(title="Hypotheses", box=box.ROUNDED, header_style="bold magenta")
        t.add_column("#", style="dim")
        t.add_column("Title")
        t.add_column("Conf", justify="right")
        t.add_column("Supporting")
        for i, h in enumerate(report.hypotheses.hypotheses, 1):
            t.add_row(
                str(i),
                h.title,
                f"{h.confidence:.0%}",
                ", ".join(h.supporting_evidence) or "—",
            )
        console.print(t)

    if report.remediation and report.remediation.actions:
        t = Table(title="Suggested actions", box=box.ROUNDED, header_style="bold green")
        t.add_column("Risk", style="bold")
        t.add_column("Action")
        t.add_column("Command", style="yellow")
        for a in report.remediation.actions:
            risk_color = {"LOW": "green", "MEDIUM": "yellow", "HIGH": "red"}.get(
                a.risk.value, "white"
            )
            t.add_row(f"[{risk_color}]{a.risk.value}[/{risk_color}]", a.title, a.command)
        console.print(t)

    if report.remediation and report.remediation.do_not_do:
        console.print("\n[bold red]DO NOT:[/bold red]")
        for d in report.remediation.do_not_do:
            console.print(f"  ✗ {d}")


@app.command()
def graph_image(output: str = "graph.png") -> None:
    """Render the LangGraph topology to a PNG (requires graphviz)."""
    try:
        g = build_graph()
        png = g.get_graph().draw_mermaid_png()
        with open(output, "wb") as f:
            f.write(png)
        console.print(f"[green]Wrote {output}[/green]")
    except Exception as e:  # pragma: no cover
        console.print(f"[red]graph_image failed: {e}[/red]")
        console.print("[dim]Falling back to ASCII mermaid:[/dim]\n")
        console.print(build_graph().get_graph().draw_mermaid())


@app.command("seed")
def seed_command(
    n: int = typer.Option(1000, help="Number of synthetic incidents to generate."),
    seed_value: int = typer.Option(42, "--seed", help="Random seed (deterministic output)."),
    days_back: int = typer.Option(7, help="Spread incidents across this many days back."),
    ab_fraction: float = typer.Option(
        0.1, help="Fraction of incidents routed to the conservative variant."
    ),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON summary on stdout."),
) -> None:
    """
    Generate synthetic incidents, feedback, and harness records.

    Use this when you don't have a live production deployment but want the
    L6 features (winner promotion, auto-runbook draft) to have data to
    consume. The seeded distributions deliberately encode signals that
    the L6 mechanisms should detect — e.g. the conservative prompt
    variant gets ~6pp higher thumbs-up rate.

    Note: harness records are in-process; if you run `sre-agent seed`
    standalone they fill *this process's* ring buffer and die when it
    exits. To populate the running dashboard, instead set
    `SRE_SEED_ON_BOOT=N` in the dashboard's env.
    """
    from sre_agent.seed import seed

    result = seed(
        n=n, seed_value=seed_value, days_back=days_back, ab_fraction=ab_fraction
    )
    if json_out:
        print(json.dumps(result.as_dict(), indent=2))
    else:
        console.print(
            f"[green]Seeded {result.n_incidents} incidents in "
            f"{result.duration_s:.1f}s[/green]"
        )
        console.print(
            f"  feedback records  : {result.n_feedback}\n"
            f"  llm call records  : {result.n_llm_records}\n"
            f"  cache-hit records : {result.n_cache_hits}"
        )


@app.command("winner")
def winner_command(
    alpha: float = typer.Option(0.05, help="Significance threshold for the z-test."),
    min_per_group: int = typer.Option(50, help="Minimum sample size per arm."),
    min_delta_pp: float = typer.Option(
        3.0, help="Minimum point-estimate delta in percentage points."
    ),
    baselines: str | None = typer.Option(
        None,
        help=(
            "Optional baseline map as agent=sha pairs (comma-separated). "
            "Example: --baselines hypothesis-gen=0c8f14d5,remediation-sug=812a99ee"
        ),
    ),
    out_md: str | None = typer.Option(
        None, "--out-md", help="Write Markdown report to this path."
    ),
    out_json: str | None = typer.Option(
        None, "--out-json", help="Write JSON report to this path."
    ),
    promote_exit_code: int = typer.Option(
        0,
        help=(
            "Process exit code when ≥1 agent qualifies for promotion. "
            "Set to 1 in CI to let the job FAIL_LOUDLY and surface action items."
        ),
    ),
) -> None:
    """
    Analyze the feedback corpus and recommend prompt promotions.

    Reads from the on-disk feedback store, partitions records by the
    `prompt_shas_seen` map, runs a two-proportion z-test per agent, and
    emits a Markdown decision document that drops straight into a PR.

    Typical workflow:

        sre-agent winner --baselines hypothesis-gen=0c8f14d5 \\
                         --out-md /tmp/winner.md \\
                         --out-json /tmp/winner.json
    """
    from sre_agent.winner import analyze, to_json

    baseline_map: dict[str, str] = {}
    if baselines:
        for piece in baselines.split(","):
            piece = piece.strip()
            if not piece or "=" not in piece:
                continue
            agent, sha = piece.split("=", 1)
            baseline_map[agent.strip()] = sha.strip()

    report = analyze(
        baselines=baseline_map,
        alpha=alpha,
        min_per_group=min_per_group,
        min_delta_pp=min_delta_pp,
    )

    md = report.to_markdown()
    if out_md:
        from pathlib import Path
        Path(out_md).write_text(md)
        console.print(f"[green]wrote markdown report to {out_md}[/green]")
    else:
        print(md)

    if out_json:
        from pathlib import Path
        Path(out_json).write_text(to_json(report))
        console.print(f"[green]wrote json report to {out_json}[/green]")

    n_promote = sum(1 for d in report.decisions if d.verdict == "promote")
    if n_promote and promote_exit_code:
        raise typer.Exit(promote_exit_code)


@app.command("autorunbook")
def autorunbook_command(
    min_occurrences: int = typer.Option(
        2, help="Suppress clusters with fewer than this many corrections."
    ),
    out_md: str | None = typer.Option(
        None, "--out-md", help="Write the draft Markdown to this path."
    ),
) -> None:
    """
    Draft new runbook entries from oncall corrections.

    Looks at every feedback record with verdict ∈ {thumbs_down, incorrect}
    that also has a `correct_root_cause` field, clusters them by
    (service, alert-shape), and prints a Markdown draft for human
    review. Output is **never** auto-merged — runbooks need eyes.
    """
    from sre_agent.autorunbook import draft

    report = draft(min_occurrences=min_occurrences)
    md = report.to_markdown()
    if out_md:
        from pathlib import Path
        Path(out_md).write_text(md)
        console.print(
            f"[green]wrote {len(report.clusters)} cluster(s) to {out_md}[/green]"
        )
    else:
        print(md)


@app.command("eval-drift")
def eval_drift(
    baseline: str = typer.Option(
        "tests/eval/baseline.json",
        help="Path to baseline JSON. Created by --update-baseline if missing.",
    ),
    update_baseline: bool = typer.Option(
        False,
        "--update-baseline",
        help="Run eval, write the result as the new baseline, exit 0.",
    ),
    threshold: float = typer.Option(
        0.05,
        help="Fail if mean score drops by more than this from baseline.",
    ),
    json_out: bool = typer.Option(
        False, "--json", help="Emit JSON to stdout instead of a Rich table."
    ),
    require_llm: bool = typer.Option(
        False,
        "--require-llm",
        help="Include cases tagged requires_llm:true (assumes a live model is reachable).",
    ),
) -> None:
    """
    Run the golden-incident eval suite and compare against a stored baseline.

    Use this as a CI / cron gate. A typical setup:

        # First-time baselining (do once after a known-good run):
        sre-agent eval-drift --update-baseline

        # CI / nightly check:
        sre-agent eval-drift                # exits non-zero if score dropped > 5%

    Exit codes:
      0  — at or above baseline (within `--threshold`)
      1  — drift detected (score dropped more than `--threshold`)
      2  — a case errored / could not run
    """
    import os
    from pathlib import Path

    if require_llm:
        os.environ["SRE_EVAL_REQUIRES_LLM"] = "1"

    try:
        from tests.eval.runner import list_cases, run_case, score
    except Exception as e:
        console.print(f"[red]Could not import eval harness: {e}[/red]")
        raise typer.Exit(2) from e

    cases = list_cases()
    if not cases:
        console.print("[yellow]No golden cases found under tests/eval/cases/[/yellow]")
        raise typer.Exit(2)

    skip_llm = not require_llm

    per_case: dict[str, dict] = {}
    errors: list[str] = []
    for case in cases:
        if case.requires_llm and skip_llm:
            per_case[case.id] = {"skipped": True, "score": None, "threshold": case.threshold}
            continue
        try:
            report = run_case(case)
            result = score(case, report)
            per_case[case.id] = {
                "score": result.score,
                "threshold": result.threshold,
                "passed": result.passed,
                "phase": report.get("phase"),
                "checks": [(n, ok) for n, ok, _ in result.checks],
            }
        except Exception as e:
            errors.append(f"{case.id}: {e}")
            per_case[case.id] = {"error": str(e)[:200]}

    scored = [v["score"] for v in per_case.values() if v.get("score") is not None]
    mean_score = sum(scored) / len(scored) if scored else 0.0
    passed_count = sum(1 for v in per_case.values() if v.get("passed"))
    skipped_count = sum(1 for v in per_case.values() if v.get("skipped"))

    summary = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "n_cases": len(cases),
        "scored": len(scored),
        "skipped": skipped_count,
        "errors": errors,
        "passed": passed_count,
        "mean_score": round(mean_score, 4),
        "per_case": per_case,
    }

    baseline_path = Path(baseline)

    if update_baseline:
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_text(json.dumps(summary, indent=2), "utf-8")
        if not json_out:
            console.print(
                f"[green]Wrote baseline:[/green] {baseline_path} "
                f"(mean_score={mean_score:.3f}, passed={passed_count}/{len(cases)})"
            )
        else:
            print(json.dumps({"updated_baseline": True, **summary}))
        return

    drift: float | None = None
    baseline_score: float | None = None
    if baseline_path.is_file():
        try:
            base = json.loads(baseline_path.read_text("utf-8"))
            baseline_score = float(base.get("mean_score", 0.0))
            drift = baseline_score - mean_score
        except Exception:
            console.print(f"[yellow]Baseline {baseline_path} is unreadable; treating as none.[/yellow]")

    summary["baseline_mean_score"] = baseline_score
    summary["drift"] = drift
    summary["drift_threshold"] = threshold

    if json_out:
        print(json.dumps(summary, indent=2))
    else:
        t = Table(title="Eval drift", box=box.ROUNDED, header_style="bold magenta")
        t.add_column("Case")
        t.add_column("Score", justify="right")
        t.add_column("Thr", justify="right")
        t.add_column("Pass")
        for case_id, v in per_case.items():
            if v.get("skipped"):
                t.add_row(case_id, "—", f"{v['threshold']:.2f}", "[dim]skip[/dim]")
            elif "error" in v:
                t.add_row(case_id, "[red]ERR[/red]", "—", v["error"][:40])
            else:
                color = "green" if v["passed"] else "red"
                t.add_row(
                    case_id,
                    f"[{color}]{v['score']:.2f}[/{color}]",
                    f"{v['threshold']:.2f}",
                    "✓" if v["passed"] else "✗",
                )
        console.print(t)
        if baseline_score is not None:
            sign = "↓" if (drift or 0) > 0 else "↑" if (drift or 0) < 0 else "·"
            console.print(
                f"\nmean_score = {mean_score:.3f}  baseline = {baseline_score:.3f}  "
                f"drift = {sign}{abs(drift or 0):.3f}  "
                f"threshold = {threshold:.3f}"
            )
        else:
            console.print(
                f"\nmean_score = {mean_score:.3f}  "
                "[dim](no baseline; run with --update-baseline to set one)[/dim]"
            )

    if errors:
        raise typer.Exit(2)
    if drift is not None and drift > threshold:
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
