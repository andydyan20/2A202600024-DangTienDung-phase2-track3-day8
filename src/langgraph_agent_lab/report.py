"""Report generation helper."""

from __future__ import annotations

from pathlib import Path

from .metrics import MetricsReport


def render_report_stub(metrics: MetricsReport) -> str:
    """Return an auto-generated metrics summary report.

    A full lab report with architecture explanations, failure analysis, and
    improvement plans is available in reports/lab_report.md.
    """
    scenario_table = "\n".join(
        f"| {m.scenario_id} | {m.expected_route} | {m.actual_route or '?'} | "
        f"{'✅' if m.success else '❌'} | {m.retry_count} | {m.interrupt_count} |"
        for m in metrics.scenario_metrics
    )
    return f"""# Day 08 Lab Report — Metrics Summary

## Results

| Scenario | Expected | Actual | Success | Retries | Interrupts |
|---|---|---|---:|---:|---:|
{scenario_table}

## Aggregate

- **Total scenarios:** {metrics.total_scenarios}
- **Success rate:** {metrics.success_rate:.2%}
- **Average nodes visited:** {metrics.avg_nodes_visited:.2f}
- **Total retries:** {metrics.total_retries}
- **Total interrupts:** {metrics.total_interrupts}

---
*For full report with architecture, state schema, failure analysis, and improvement
plan, see reports/lab_report.md*
"""


def write_report(metrics: MetricsReport, output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_report_stub(metrics), encoding="utf-8")
