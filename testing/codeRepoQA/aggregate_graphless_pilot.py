"""Produce a standalone, four-case graphless pilot report.

This deliberately does not modify the main Workspace-versus-Codex report: the
pilot is a controlled ablation, not another comparable production system.
"""
from __future__ import annotations

import json
import argparse
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any, Mapping

from aggregate_four_run_comparison import (
    CODEX_LEDGER,
    MERGED_LEDGER,
    RUNS_DIR,
    ROOT,
    TEST_ROOT,
    case_stability,
    iso_seconds,
    load_json,
    retrieval_metrics,
    run_artifacts,
    unique_paths,
    workspace_usage,
)


GRAPHLESS_LEDGER = RUNS_DIR / "2026-09-02-graphless-pilot-four-runs.json"
REPORT_JSON = RUNS_DIR / "2026-09-02-graphless-pilot-comparison.json"
REPORT_MD = RUNS_DIR / "2026-09-02-graphless-pilot-comparison.md"


def rows_for(system: str, ledger: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case_id, record in ledger["cases"].items():
        verification = load_json(ROOT / "testing" / "codeRepoQA" / "corpus" / "cases" / case_id / "verification.json")
        oracle = verification["oracle"]
        implementation = unique_paths(oracle["implementation_files"])
        supporting = unique_paths([
            *oracle.get("test_or_validation_files", []),
            *oracle.get("documentation_files", []),
        ])
        for entry in record["campaign_runs"]:
            metadata, orchestration, comparison = run_artifacts(case_id, entry["run_id"])
            retrieval = orchestration["retrieval_result"]
            summary = retrieval["retrieval_summary"]
            usage = workspace_usage(summary) if system != "codex" else summary.get("usage", {})
            flow_tokens = int(usage.get("total_tokens", usage.get("input_plus_output_tokens", 0)) or 0)
            rows.append({
                "case_id": case_id,
                "run_id": entry["run_id"],
                "metrics": retrieval_metrics(comparison, implementation, supporting),
                "coverage_status": retrieval["coverage_status"],
                "sufficient": bool(retrieval["sufficient"]),
                "evidence_count": len(retrieval["evidence"]),
                "retrieved_files": unique_paths(comparison["retrieved_source_files"]),
                "flow_tokens": flow_tokens,
                "elapsed_seconds": iso_seconds(entry["started_at"], entry["completed_at"]),
                "structural_graph_enabled": metadata.get("structural_graph_enabled"),
            })
    return rows


def summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    keys = tuple(rows[0]["metrics"])
    return {
        "run_count": len(rows),
        "metrics": {key: mean(float(row["metrics"][key]) for row in rows) for key in keys},
        "coverage_status_counts": dict(Counter(row["coverage_status"] for row in rows)),
        "sufficient_rate": mean(float(row["sufficient"]) for row in rows),
        "mean_flow_tokens": mean(row["flow_tokens"] for row in rows),
        "mean_elapsed_seconds": mean(row["elapsed_seconds"] for row in rows),
    }


def validate_graphless(rows: list[dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    for row in rows:
        trace = TEST_ROOT / row["case_id"] / "runs" / row["run_id"] / "retrieval-trace.jsonl"
        text = trace.read_text(encoding="utf-8")
        if row["structural_graph_enabled"] is not False or '"event_type": "initial_ranges_without_codegraph"' not in text or '"provider": "disabled"' not in text:
            failures.append(f"{row['case_id']}/{row['run_id']}")
    return failures


def per_case(rows: list[dict[str, Any]], case_id: str) -> dict[str, Any]:
    selected = [row for row in rows if row["case_id"] == case_id]
    return {
        "mean_metrics": summary(selected)["metrics"],
        "stability": case_stability(selected),
        "coverage_statuses": dict(Counter(row["coverage_status"] for row in selected)),
        "mean_flow_tokens": mean(row["flow_tokens"] for row in selected),
        "mean_elapsed_seconds": mean(row["elapsed_seconds"] for row in selected),
        "run_ids": [row["run_id"] for row in selected],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare a graphless campaign without altering the main report.")
    parser.add_argument("--graphless-ledger", type=Path, default=GRAPHLESS_LEDGER)
    parser.add_argument("--report-stem", default="2026-09-02-graphless-pilot-comparison")
    args = parser.parse_args()
    graphless = rows_for("graphless", load_json(args.graphless_ledger))
    case_ids = [row["case_id"] for row in graphless[::4]]
    workspace = [row for row in rows_for("workspace", load_json(MERGED_LEDGER)) if row["case_id"] in case_ids]
    codex = [row for row in rows_for("codex", load_json(CODEX_LEDGER)) if row["case_id"] in case_ids]
    audit_failures = validate_graphless(graphless)
    payload = {
        "campaign": args.graphless_ledger.stem,
        "scope": "CodeGraph ablation; separate from the main Workspace/Codex benchmark report.",
        "sources": {"graphless": args.graphless_ledger.name, "workspace": MERGED_LEDGER.name, "codex": CODEX_LEDGER.name},
        "graphless_boundary_audit": {"valid_runs": len(graphless), "failures": audit_failures},
        "summaries": {"graphless": summary(graphless), "workspace": summary(workspace), "codex_luna_efficient": summary(codex)},
        "cases": {case_id: {"graphless": per_case(graphless, case_id), "workspace": per_case(workspace, case_id), "codex_luna_efficient": per_case(codex, case_id)} for case_id in case_ids},
    }
    report_json = RUNS_DIR / f"{args.report_stem}.json"
    report_md = RUNS_DIR / f"{args.report_stem}.md"
    report_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Workspace, Codex, and Graphless Retrieval — Four Repetitions per Case", "",
        "This consolidated comparison keeps the graphless ablation explicit while presenting all three systems together.", "",
        f"Boundary audit: **{len(graphless)}** runs used `structural_graph_enabled: false`; failures: **{len(audit_failures)}**.", "",
        "| System | Runs | P@5 | R@5 | NDCG@5 | Any Oracle | Full Oracle | Mean files | Mean flow tokens | Mean seconds |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, value in payload["summaries"].items():
        metric = value["metrics"]
        lines.append(f"| {name} | {value['run_count']} | {metric['p@5']:.3f} | {metric['r@5']:.3f} | {metric['ndcg@5']:.3f} | {metric['implementation_any_hit']:.3f} | {metric['implementation_full_recall']:.3f} | {metric['retrieved_file_count']:.2f} | {value['mean_flow_tokens']:.0f} | {value['mean_elapsed_seconds']:.1f} |")
    lines += ["", "## Per-case stability", "", "| Case | System | R@5 | Oracle-hit runs | Full-recall runs | Mean files | Flow tokens |", "| --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    for case_id, value in payload["cases"].items():
        for index, (system, case) in enumerate(value.items()):
            metric, stability = case["mean_metrics"], case["stability"]
            case_label = f"`{case_id}`" if index == 0 else ""
            lines.append(f"| {case_label} | {system} | {metric['r@5']:.3f} | {stability['any_implementation_hit_runs']}/4 | {stability['full_implementation_recall_runs']}/4 | {metric['retrieved_file_count']:.2f} | {case['mean_flow_tokens']:.0f} |")
    report_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
