"""Generate the complete five-system CodeRepoQA four-run report."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any, Mapping

from aggregate_four_run_comparison import (
    CODEX_LEDGER, MANIFEST_PATH, MERGED_LEDGER, METRIC_KEYS, ROOT, RUNS_DIR,
    TOPOLOGY_PATH, case_stability, grouped_summaries, iso_seconds, load_json,
    mean_dict, retrieval_metrics, run_artifacts, system_summary, unique_paths,
    workspace_usage,
)


GRAPHLESS_LEDGER = RUNS_DIR / "2026-09-03-graphless-four-runs-complete.json"
NO_CONTROLLER_LEDGER = RUNS_DIR / "2026-09-05-workspace-no-controller-four-runs-complete.json"
GRAPHLESS_NO_CONTROLLER_LEDGER = RUNS_DIR / "2026-09-05-workspace-graphless-no-controller-four-runs-complete.json"
REPORT_JSON = RUNS_DIR / "2026-09-05-five-system-four-run-complete.json"
REPORT_MD = RUNS_DIR / "2026-09-05-five-system-four-run-complete.md"

SYSTEMS = (
    ("workspace", "Workspace", MERGED_LEDGER),
    ("codex", "Codex Luna Efficient", CODEX_LEDGER),
    ("graphless", "Workspace without CodeGraph", GRAPHLESS_LEDGER),
    ("no_controller", "Workspace without adaptive controller", NO_CONTROLLER_LEDGER),
    (
        "graphless_no_controller",
        "Workspace without CodeGraph or adaptive controller",
        GRAPHLESS_NO_CONTROLLER_LEDGER,
    ),
)
SYSTEM_LABELS = {system: label for system, label, _path in SYSTEMS}
PROFILE_NAMES = {
    "workspace": "qualification_first_controller_v1",
    "graphless": "qualification_first_controller_v1_no_codegraph",
    "no_controller": "qualification_first_no_adaptive_controller_v1",
    "graphless_no_controller": "qualification_first_no_adaptive_controller_v1_no_codegraph",
}


def build_rows(system: str, ledger: Mapping[str, Any], cases: Mapping[str, Mapping[str, Any]], topology: Mapping[str, str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case_id, case in cases.items():
        entries = ledger["cases"][case_id]["campaign_runs"]
        if len(entries) != 4:
            raise RuntimeError(f"{system}/{case_id}: expected four valid runs")
        verification = load_json(ROOT / "testing" / "codeRepoQA" / "corpus" / "cases" / case_id / "verification.json")
        oracle = verification["oracle"]
        implementation = unique_paths(oracle["implementation_files"])
        supporting = unique_paths([*oracle.get("test_or_validation_files", []), *oracle.get("documentation_files", [])])
        for repetition, entry in enumerate(entries, start=1):
            metadata, orchestration, comparison = run_artifacts(case_id, entry["run_id"])
            retrieval = orchestration["retrieval_result"]
            summary = retrieval["retrieval_summary"]
            if system == "codex":
                usage = summary.get("usage", {})
                flow_tokens = int(usage.get("input_plus_output_tokens", 0) or 0)
                model, profile = str(metadata.get("codex_model", "")), str(metadata.get("codex_prompt_profile", ""))
            else:
                flow_tokens = workspace_usage(summary)["total_tokens"]
                model = str((metadata.get("llm_config") or {}).get("model", ""))
                profile = PROFILE_NAMES[system]
            rows.append({
                "system": system, "case_id": case_id, "repository": case["repository"], "category": case["group"],
                "partition": case["statistics_partition"], "retrieval_topology": topology[case_id], "repetition": repetition,
                "run_id": entry["run_id"], "model": model, "profile": profile,
                "elapsed_seconds": iso_seconds(entry["started_at"], entry["completed_at"]),
                "coverage_status": retrieval["coverage_status"], "sufficient": bool(retrieval["sufficient"]),
                "evidence_count": len(retrieval["evidence"]), "retrieved_files": unique_paths(comparison["retrieved_source_files"]),
                "metrics": retrieval_metrics(comparison, implementation, supporting), "flow_tokens": flow_tokens,
            })
    return rows


def metric_table(summaries: Mapping[str, Mapping[str, Any]]) -> list[str]:
    lines = ["| System | Cases | Runs | P@1 | P@2 | P@5 | P@10 | R@1 | R@2 | R@5 | R@10 | NDCG@1 | NDCG@2 | NDCG@5 | NDCG@10 |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for system, label, _path in SYSTEMS:
        value, metrics = summaries[system], summaries[system]["metrics"]
        values = [metrics[f"{family}@{k}"] for family in ("p", "r", "ndcg") for k in (1, 2, 5, 10)]
        lines.append(f"| {label} | {value['case_count']} | {value['run_count']} | " + " | ".join(f"{item:.3f}" for item in values) + " |")
    return lines


def main() -> None:
    manifest = load_json(MANIFEST_PATH)
    cases = {str(item["case_id"]): item for item in manifest["cases"] if item["group"] != "question_usage"}
    topology = load_json(TOPOLOGY_PATH)["assignments"]
    ledgers = {system: load_json(path) for system, _label, path in SYSTEMS}
    rows = [row for system, ledger in ledgers.items() for row in build_rows(system, ledger, cases, topology)]
    by_system = {system: [row for row in rows if row["system"] == system] for system in ledgers}
    summaries = {system: system_summary(values) for system, values in by_system.items()}
    breakdowns = {dimension: {system: grouped_summaries(values, dimension) for system, values in by_system.items()} for dimension in ("partition", "category", "retrieval_topology", "repository")}
    per_case: dict[str, Any] = {}
    for case_id, case in cases.items():
        item: dict[str, Any] = {"category": case["group"], "partition": case["statistics_partition"], "repository": case["repository"], "retrieval_topology": topology[case_id]}
        for system, values in by_system.items():
            selected = [row for row in values if row["case_id"] == case_id]
            item[system] = {"mean_metrics": mean_dict(selected), "stability": case_stability(selected), "mean_flow_tokens": mean(row["flow_tokens"] for row in selected), "mean_elapsed_seconds": mean(row["elapsed_seconds"] for row in selected), "run_ids": [row["run_id"] for row in selected]}
        per_case[case_id] = item
    report = {"schema_version": 1, "title": "Five-system CodeRepoQA — 35-case four-run comparison", "case_count": 35, "system_count": len(SYSTEMS), "runs_per_case_per_system": 4, "aggregation": "Average four runs within each case, then macro-average the 35 case means.", "ledgers": {system: path.name for system, _label, path in SYSTEMS}, "summaries": summaries, "breakdowns": breakdowns, "per_case": per_case, "run_inventory": rows, "limitations": ["The three Workspace ablations reuse the same Qdrant/BM25 indexes; they disable CodeGraph, the adaptive controller, or both.", "Flow-token counts exclude indexing and response generation was skipped.", "Invalid attempts remain in campaign ledgers but do not enter four-run metrics."]}
    REPORT_JSON.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    lines = ["# Five-System CodeRepoQA — 35-Case Four-Run Comparison", "", "## Status and scope", "", "All five conditions contain 35 cases and four valid retrieval runs per case. The three Workspace ablations reuse the same lexical/vector indexes and disable CodeGraph, the adaptive controller, or both.", "", "## Conditions", "", "- Workspace: `gpt-5.6-luna`, qualification-first controller.", "- Codex: `gpt-5.6-luna`, `efficient` profile.", "- Without CodeGraph: `structural_graph_enabled: false`.", "- Without adaptive controller: `adaptive_controller_enabled: false`.", "- Without either: both flags are `false`.", "- Response generation was skipped and final evidence selection remained enabled in every accepted run.", "- Aggregation: average four repetitions within each case, then macro-average 35 case means.", "", "## Metric glossary", "", "All metrics inspect the first **k ordered, unique repository files** returned by a system. `@1`, `@2`, `@5`, and `@10` mean that k is respectively 1, 2, 5, or 10.", "", "- **P@k (precision):** implementation-Oracle files among the first k, divided by k. A short list still uses k as the denominator.", "- **R@k (recall):** implementation-Oracle files among the first k, divided by all implementation-Oracle files for that testcase.", "- **NDCG@k:** a rank-sensitive quality score from 0 to 1 for the first k files. Implementation-Oracle files receive relevance 2, supporting test/validation or documentation files relevance 1, and earlier ranks count more.", "", "## Four-run descriptive metrics", "", *metric_table(summaries), "", "## Operational summary", "", "| System | Sufficient rate | Mean files | Any Oracle | Full Oracle | Mean flow tokens | Mean seconds |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for system, label, _path in SYSTEMS:
        value, metrics = summaries[system], summaries[system]["metrics"]
        lines.append(f"| {label} | {value['sufficient_rate']:.3f} | {metrics['retrieved_file_count']:.3f} | {metrics['implementation_any_hit']:.3f} | {metrics['implementation_full_recall']:.3f} | {value['mean_flow_tokens']:.0f} | {value['mean_elapsed_seconds']:.1f} |")
    for dimension, title in (("partition", "Partition breakdown"), ("category", "Issue-category breakdown"), ("retrieval_topology", "Retrieval-topology breakdown"), ("repository", "Repository breakdown")):
        lines += ["", f"## {title}", "", "| Group | System | Cases | Runs | P@5 | R@5 | NDCG@5 | Any hit | Full recall |", "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
        for group in sorted(breakdowns[dimension]["workspace"]):
            for index, (system, label, _path) in enumerate(SYSTEMS):
                value, metrics = breakdowns[dimension][system][group], breakdowns[dimension][system][group]["metrics"]
                group_label = f"`{group}`" if index == 0 else ""
                lines.append(f"| {group_label} | {label} | {value['case_count']} | {value['run_count']} | {metrics['p@5']:.3f} | {metrics['r@5']:.3f} | {metrics['ndcg@5']:.3f} | {metrics['implementation_any_hit']:.3f} | {metrics['implementation_full_recall']:.3f} |")
    lines += ["", "## Per-case results", "", "| Case | Partition | Topology | System | P@5 | R@5 | NDCG@5 | Any-hit runs | Full-recall runs | Mean files | Mean tokens | Mean seconds |", "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for case_id, value in sorted(per_case.items()):
        for index, (system, label, _path) in enumerate(SYSTEMS):
            item, metrics, stability = value[system], value[system]["mean_metrics"], value[system]["stability"]
            case_label = f"`{case_id}`" if index == 0 else ""
            partition = f"`{value['partition']}`" if index == 0 else ""
            topo = f"`{value['retrieval_topology']}`" if index == 0 else ""
            lines.append(f"| {case_label} | {partition} | {topo} | {label} | {metrics['p@5']:.3f} | {metrics['r@5']:.3f} | {metrics['ndcg@5']:.3f} | {stability['any_implementation_hit_runs']}/4 | {stability['full_implementation_recall_runs']}/4 | {metrics['retrieved_file_count']:.2f} | {item['mean_flow_tokens']:.0f} | {item['mean_elapsed_seconds']:.1f} |")
    lines += ["", "## Run inventory", "", "| Case | System | Rep | Run | Coverage | Sufficient | Evidence | Files | Flow tokens | Seconds |", "| --- | --- | ---: | --- | --- | --- | ---: | ---: | ---: | ---: |"]
    prior_case, prior_system = "", ""
    for row in sorted(rows, key=lambda item: (item["case_id"], item["system"], item["repetition"])):
        case_label = f"`{row['case_id']}`" if row["case_id"] != prior_case else ""
        system_label = row["system"] if (row["case_id"], row["system"]) != (prior_case, prior_system) else ""
        lines.append(f"| {case_label} | {system_label} | {row['repetition']} | `{row['run_id']}` | `{row['coverage_status']}` | {str(row['sufficient']).lower()} | {row['evidence_count']} | {len(row['retrieved_files'])} | {row['flow_tokens']} | {row['elapsed_seconds']:.1f} |")
        prior_case, prior_system = row["case_id"], row["system"]
    lines += ["", "## Limitations", "", *[f"- {item}" for item in report["limitations"]], "", "## Reproduction", "", f"- Script: `{Path(__file__).relative_to(ROOT).as_posix()}`", *[f"- {name}: `{path}`" for name, path in report["ledgers"].items()]]
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
