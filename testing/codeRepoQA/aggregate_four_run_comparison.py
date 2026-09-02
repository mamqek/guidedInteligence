from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from datetime import datetime
from itertools import combinations
from pathlib import Path
from statistics import mean, median, pstdev
from typing import Any, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
TEST_ROOT = Path(r"C:\Programming\guidedInteligence_testcases")
RUNS_DIR = ROOT / "testing" / "codeRepoQA" / "statistics" / "runs"
MANIFEST_PATH = ROOT / "testing" / "codeRepoQA" / "corpus" / "selection_manifest.json"
TOPOLOGY_PATH = ROOT / "testing" / "codeRepoQA" / "statistics" / "retrieval_topology_assignments.json"
WORKSPACE_LEDGERS = (
    RUNS_DIR / "2026-09-02-workspace-four-runs.json",
    RUNS_DIR / "2026-09-02-workspace-two-worker-a.json",
    RUNS_DIR / "2026-09-02-workspace-two-worker-b.json",
)
CODEX_LEDGER = RUNS_DIR / "2026-08-26-codex-luna-four-runs.json"
MERGED_LEDGER = RUNS_DIR / "2026-09-02-workspace-four-runs-complete.json"
REPORT_JSON = RUNS_DIR / "2026-09-02-workspace-vs-codex-four-run-comparison.json"
REPORT_MD = RUNS_DIR / "2026-09-02-workspace-vs-codex-four-run-comparison.md"
MAIN_REPORT_JSON = RUNS_DIR / "2026-09-02-workspace-vs-codex-main-statistics.json"
MAIN_REPORT_MD = RUNS_DIR / "2026-09-02-workspace-vs-codex-main-statistics.md"
K_VALUES = (1, 2, 5, 10)
METRIC_KEYS = tuple(f"{family}@{k}" for family in ("p", "r", "ndcg") for k in K_VALUES)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected object in {path}")
    return value


def unique_paths(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return list(dict.fromkeys(str(item).replace("\\", "/") for item in value if str(item)))


def iso_seconds(started_at: str, completed_at: str) -> float:
    return (datetime.fromisoformat(completed_at) - datetime.fromisoformat(started_at)).total_seconds()


def retrieval_metrics(comparison: Mapping[str, Any], implementation: Sequence[str], supporting: Sequence[str]) -> dict[str, float]:
    ranked = unique_paths(comparison.get("retrieved_source_files"))
    implementation_set = set(implementation)
    supporting_set = set(supporting) - implementation_set
    ideal_grades = [2] * len(implementation_set) + [1] * len(supporting_set)
    result: dict[str, float] = {}
    for k in K_VALUES:
        top = ranked[:k]
        hits = sum(path in implementation_set for path in top)
        result[f"p@{k}"] = hits / k
        result[f"r@{k}"] = hits / len(implementation_set)
        dcg = 0.0
        for index in range(k):
            path = ranked[index] if index < len(ranked) else ""
            grade = 2 if path in implementation_set else 1 if path in supporting_set else 0
            dcg += (2**grade - 1) / math.log2(index + 2)
        idcg = sum((2**grade - 1) / math.log2(index + 2) for index, grade in enumerate(ideal_grades[:k]))
        result[f"ndcg@{k}"] = dcg / idcg if idcg else 0.0
    result["retrieved_file_count"] = float(len(ranked))
    result["implementation_hit_count"] = float(sum(path in implementation_set for path in ranked))
    result["implementation_any_hit"] = float(any(path in implementation_set for path in ranked))
    result["implementation_full_recall"] = float(implementation_set.issubset(ranked))
    return result


def workspace_usage(summary: Mapping[str, Any]) -> dict[str, int]:
    usage_objects: list[Mapping[str, Any]] = []
    for key in ("coverage_usage", "initial_owner_comparison_usage", "qualification_usage"):
        value = summary.get(key)
        if isinstance(value, Mapping):
            usage_objects.append(value)
    for key in ("connected_source_context", "evidence_consolidation"):
        value = summary.get(key)
        usage = value.get("usage") if isinstance(value, Mapping) else None
        if isinstance(usage, Mapping):
            usage_objects.append(usage)
    return {
        key: sum(int(value.get(key, 0) or 0) for value in usage_objects)
        for key in ("prompt_tokens", "completion_tokens", "total_tokens")
    }


def run_artifacts(case_id: str, run_id: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    run_dir = TEST_ROOT / case_id / "runs" / run_id
    paths = tuple(run_dir / name for name in ("run-metadata.json", "orchestration-result.json", "evaluator-comparison.json"))
    missing = [path.name for path in paths if not path.exists()]
    if missing:
        raise RuntimeError(f"{case_id}/{run_id} missing {missing}")
    return tuple(load_json(path) for path in paths)  # type: ignore[return-value]


def index_trace_info(trace_path: Path) -> dict[str, Any]:
    result = {
        "collection_name": "",
        "document_count": None,
        "rebuilt": False,
        "codegraph_seconds": None,
        "semantic_seconds": None,
    }
    if not trace_path.is_file():
        return result
    with trace_path.open(encoding="utf-8") as stream:
        for line in stream:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            event_type = event.get("event_type")
            payload = event.get("payload") if isinstance(event.get("payload"), Mapping) else {}
            if event_type == "workspace_index_ready":
                result["collection_name"] = str(payload.get("collection_name") or "")
                result["document_count"] = payload.get("document_count")
                result["rebuilt"] = bool(payload.get("rebuilt"))
            elif event_type == "retrieval_stage_completed":
                elapsed = payload.get("elapsed_ms")
                if not isinstance(elapsed, (int, float)):
                    continue
                if payload.get("stage_key") == "index_codegraph":
                    result["codegraph_seconds"] = elapsed / 1000
                elif payload.get("stage_key") == "index_bm25_qdrant":
                    result["semantic_seconds"] = elapsed / 1000
    values = [
        value
        for value in (result["codegraph_seconds"], result["semantic_seconds"])
        if isinstance(value, (int, float))
    ]
    result["total_seconds"] = sum(values) if values else None
    return result


def matching_index_build(case_id: str, selected_run_id: str) -> dict[str, Any]:
    """Find the latest exact-collection rebuild at or before a selected run."""
    selected_dir = TEST_ROOT / case_id / "runs" / selected_run_id
    selected_metadata = load_json(selected_dir / "run-metadata.json")
    selected_trace = index_trace_info(selected_dir / "retrieval-trace.jsonl")
    collection_name = selected_trace["collection_name"]
    for run_dir in sorted((TEST_ROOT / case_id / "runs").glob("run-*"), reverse=True):
        if run_dir.name > selected_run_id:
            continue
        metadata_path = run_dir / "run-metadata.json"
        if not metadata_path.is_file():
            continue
        metadata = load_json(metadata_path)
        if metadata.get("retrieval_mode") != "workspace":
            continue
        if metadata.get("repo_pre_commit") != selected_metadata.get("repo_pre_commit"):
            continue
        trace = index_trace_info(run_dir / "retrieval-trace.jsonl")
        if not trace["rebuilt"]:
            continue
        if collection_name and trace["collection_name"] != collection_name:
            continue
        return {"source_run_id": run_dir.name, **trace}
    return {
        "source_run_id": None,
        "collection_name": collection_name,
        "document_count": selected_trace["document_count"],
        "rebuilt": False,
        "codegraph_seconds": None,
        "semantic_seconds": None,
        "total_seconds": None,
    }


def merge_workspace_ledgers(case_ids: Sequence[str]) -> dict[str, Any]:
    ledgers = [load_json(path) for path in WORKSPACE_LEDGERS]
    merged_cases: dict[str, Any] = {}
    all_run_ids: set[str] = set()
    for case_id in case_ids:
        runs: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []
        sources: list[str] = []
        for path, ledger in zip(WORKSPACE_LEDGERS, ledgers):
            case = (ledger.get("cases") or {}).get(case_id, {})
            if not isinstance(case, Mapping):
                continue
            current_runs = [dict(item) for item in case.get("campaign_runs", ()) if isinstance(item, Mapping)]
            current_failures = [dict(item) for item in case.get("failed_attempts", ()) if isinstance(item, Mapping)]
            if current_runs or current_failures:
                sources.append(path.name)
            runs.extend(current_runs)
            failures.extend(current_failures)
        if len(runs) != 4:
            raise RuntimeError(f"{case_id}: expected four workspace runs, found {len(runs)}")
        run_ids = [str(item.get("run_id") or "") for item in runs]
        if len(set(run_ids)) != 4 or any(run_id in all_run_ids for run_id in run_ids):
            raise RuntimeError(f"{case_id}: duplicate workspace run ID")
        all_run_ids.update(run_ids)
        merged_cases[case_id] = {
            "status": "complete",
            "source_ledgers": sources,
            "campaign_runs": runs,
            "failed_attempts": failures,
        }
    if len(all_run_ids) != 140:
        raise RuntimeError(f"Expected 140 unique workspace runs, found {len(all_run_ids)}")
    merged = {
        "schema_version": 1,
        "campaign": "2026-09-02-workspace-four-runs-complete",
        "retrieval_mode": "workspace",
        "run_config": "configs/testing/statistics-workspace.json",
        "target_valid_runs_per_case": 4,
        "stop_reason": "complete",
        "source_ledgers": [path.name for path in WORKSPACE_LEDGERS],
        "valid_run_count": 140,
        "failed_attempt_count": sum(len(item["failed_attempts"]) for item in merged_cases.values()),
        "cases": merged_cases,
    }
    MERGED_LEDGER.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    return merged


def mean_dict(rows: Sequence[Mapping[str, Any]], key: str = "metrics") -> dict[str, float]:
    return {
        metric: mean(float(row[key][metric]) for row in rows)
        for metric in (*METRIC_KEYS, "retrieved_file_count", "implementation_hit_count", "implementation_any_hit", "implementation_full_recall")
    }


def system_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    case_groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        case_groups[str(row["case_id"])].append(row)
    case_metrics = []
    for case_id, items in sorted(case_groups.items()):
        values = mean_dict(items)
        values["case_id"] = case_id
        case_metrics.append(values)
    macro = {
        metric: mean(float(item[metric]) for item in case_metrics)
        for metric in (*METRIC_KEYS, "retrieved_file_count", "implementation_hit_count", "implementation_any_hit", "implementation_full_recall")
    }
    return {
        "case_count": len(case_groups),
        "run_count": len(rows),
        "metrics": macro,
        "coverage_status_counts": dict(Counter(str(row["coverage_status"]) for row in rows)),
        "sufficient_rate": mean(float(bool(row["sufficient"])) for row in rows),
        "mean_elapsed_seconds": mean(float(row["elapsed_seconds"]) for row in rows),
        "mean_flow_tokens": mean(float(row["flow_tokens"]) for row in rows),
    }


def grouped_summaries(rows: Sequence[Mapping[str, Any]], dimension: str) -> dict[str, Any]:
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row[dimension])].append(row)
    return {group: system_summary(items) for group, items in sorted(groups.items())}


def pairwise_jaccard(sets: Sequence[set[str]]) -> float:
    values = []
    for left, right in combinations(sets, 2):
        union = left | right
        values.append(len(left & right) / len(union) if union else 1.0)
    return mean(values) if values else 1.0


def case_stability(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "mean_pairwise_retrieved_file_jaccard": pairwise_jaccard([set(row["retrieved_files"]) for row in rows]),
        "r10_population_stddev": pstdev(float(row["metrics"]["r@10"]) for row in rows),
        "any_implementation_hit_runs": sum(int(row["metrics"]["implementation_any_hit"]) for row in rows),
        "full_implementation_recall_runs": sum(int(row["metrics"]["implementation_full_recall"]) for row in rows),
        "sufficient_runs": sum(bool(row["sufficient"]) for row in rows),
    }


def fmt(value: float) -> str:
    return f"{value:.3f}"


def markdown_metric_table(workspace: Mapping[str, Any], codex: Mapping[str, Any]) -> list[str]:
    lines = [
        "| System | Cases | Runs | P@1 | P@2 | P@5 | P@10 | R@1 | R@2 | R@5 | R@10 | NDCG@1 | NDCG@2 | NDCG@5 | NDCG@10 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, summary in (("Workspace", workspace), ("Codex Luna efficient", codex)):
        metrics = summary["metrics"]
        values = [metrics[f"{family}@{k}"] for family in ("p", "r", "ndcg") for k in K_VALUES]
        lines.append(f"| {name} | {summary['case_count']} | {summary['run_count']} | " + " | ".join(fmt(value) for value in values) + " |")
    return lines


def write_main_statistics(
    rows: Sequence[Mapping[str, Any]],
    four_run_summaries: Mapping[str, Any],
    per_case: Mapping[str, Any],
) -> None:
    """Write the protocol headline (first valid run) beside four-run stability results."""
    selected = [row for row in rows if int(row["repetition"]) == 1]
    workspace = [row for row in selected if row["system"] == "workspace"]
    codex = [row for row in selected if row["system"] == "codex"]
    if len(workspace) != 35 or len(codex) != 35:
        raise RuntimeError("Main statistics require one first-valid run for every case and system")
    for row in workspace:
        row["index_build"] = matching_index_build(str(row["case_id"]), str(row["run_id"]))
    for row in codex:
        row["index_build"] = {
            "source_run_id": None,
            "total_seconds": 0.0,
            "status": "not_applicable_direct_repository_inspection",
        }
    observed_index_seconds = [
        float(row["index_build"]["total_seconds"])
        for row in workspace
        if isinstance(row["index_build"].get("total_seconds"), (int, float))
    ]
    headline = {"workspace": system_summary(workspace), "codex": system_summary(codex)}
    breakdowns: dict[str, Any] = {}
    for dimension in ("partition", "category", "retrieval_topology", "repository"):
        breakdowns[dimension] = {
            "workspace": grouped_summaries(workspace, dimension),
            "codex": grouped_summaries(codex, dimension),
        }
    delta = {
        key: headline["workspace"]["metrics"][key] - headline["codex"]["metrics"][key]
        for key in METRIC_KEYS
    }
    payload = {
        "schema_version": 1,
        "title": "Workspace vs Codex Luna efficient — main retrieval statistics",
        "status": "workspace_complete_codex_condition_invalid",
        "comparison_valid": False,
        "comparison_invalid_reason": "All 140 Codex runs had repository shell commands rejected by execution policy; 134 returned no usable evidence.",
        "headline_selection_rule": "First valid campaign run per testcase and system; never selected by score.",
        "headline_run_count_per_system": 35,
        "stability_runs_per_case_per_system": 4,
        "headline_summaries": headline,
        "workspace_minus_codex": delta,
        "breakdowns": breakdowns,
        "headline_run_inventory": selected,
        "workspace_index_build_duration": {
            "matched_case_count": len(observed_index_seconds),
            "unavailable_case_count": len(workspace) - len(observed_index_seconds),
            "mean_seconds": mean(observed_index_seconds),
            "median_seconds": median(observed_index_seconds),
            "minimum_seconds": min(observed_index_seconds),
            "maximum_seconds": max(observed_index_seconds),
        },
        "four_run_stability_summaries": four_run_summaries,
        "per_case_four_run_stability": per_case,
        "source_four_run_report": REPORT_JSON.relative_to(ROOT).as_posix(),
        "limitations": [
            "Workspace indexing-token usage is not provider-logged; indexing and combined totals are unavailable rather than estimated.",
            "The frozen Codex campaign is invalid for retrieval comparison: all 140 runs had repository commands rejected by execution policy and 134 returned no usable evidence.",
            "Workspace response generation was skipped; final evidence selection remained enabled.",
            "The Workspace campaign was repaired during execution for final-selection contract handling and coverage-payload budgeting; this is disclosed as a campaign implementation boundary rather than hidden.",
        ],
    }
    MAIN_REPORT_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Workspace vs Codex Luna Efficient — Main Retrieval Statistics",
        "",
        "## Status and scope",
        "",
        "Workspace retrieval is complete over 35 CodeRepoQA cases: seven issue categories, three repositories, 28 development cases, and seven frozen final-evaluation cases. The Codex campaign is not a valid comparison condition: all 140 executions had repository shell commands rejected by policy, and 134 returned no usable evidence. Its rows are retained below only to audit that failure.",
        "",
        "## Conditions",
        "",
        "- Workspace: `configs/testing/statistics-workspace.json`, `gpt-5.6-luna`, qualification-first controller, response generation skipped, final evidence selection enabled.",
        "- Codex: `gpt-5.6-luna`, `efficient` prompt profile, frozen campaign ledger `2026-08-26-codex-luna-four-runs.json`.",
        "- Headline selection: the first valid campaign run for every testcase and system; no run was selected or replaced using its score.",
        "- Four-run stability: calculate every run, average four repetitions within each case, then macro-average the 35 case means.",
        "- Twenty-one Workspace attempts exited with code 1 before producing required artifacts. They are excluded and remain auditable in the source ledgers; the ledger does not preserve a precise cause for every attempt.",
        "",
        "## Metric note",
        "",
        "Files are ranked and deduplicated by repository-relative path. Implementation Oracle files define P@k and R@k. Test/validation and documentation Oracle files receive partial NDCG relevance. Missing ranks are nonrelevant. P@k always uses k as its denominator.",
        "",
        "## Headline run inventory and cost",
        "",
        "Indexing-token totals for Workspace are unavailable because the reused-index build usage was not provider-logged. They are not estimated. Observed build duration is recovered only from an earlier trace with the same case snapshot and exact Qdrant collection identity. `Flow` is the recorded non-indexing retrieval usage.",
        "",
        f"Matching build duration was recovered for {len(observed_index_seconds)}/35 Workspace cases: mean {mean(observed_index_seconds):.1f}s, median {median(observed_index_seconds):.1f}s, range {min(observed_index_seconds):.1f}–{max(observed_index_seconds):.1f}s. Codex performs direct repository inspection and has no index-build stage.",
        "",
        "| Case | Part. | Category | Topology | System | Run | Seconds | Index build seconds | Build source run | Index tokens | Flow | Cached in | Uncached in | Output |",
        "| --- | --- | --- | --- | --- | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in sorted(selected, key=lambda item: (str(item["case_id"]), str(item["system"]))):
        detail = row["token_detail"]
        indexing = "unavailable" if row["system"] == "workspace" else "0"
        cached = str(detail.get("cached_input_tokens", "—"))
        uncached = str(detail.get("uncached_input_tokens", "—"))
        output = str(detail.get("output_tokens", detail.get("completion_tokens", "—")))
        build = row["index_build"]
        build_seconds = build.get("total_seconds")
        build_seconds_text = f"{build_seconds:.1f}" if isinstance(build_seconds, (int, float)) else "unavailable"
        build_source = f"`{build['source_run_id']}`" if build.get("source_run_id") else "not applicable" if row["system"] == "codex" else "unavailable"
        lines.append(
            f"| `{row['case_id']}` | `{row['partition']}` | `{row['category']}` | `{row['retrieval_topology']}` | {row['system']} | `{row['run_id']}` | {row['elapsed_seconds']:.1f} | {build_seconds_text} | {build_source} | {indexing} | {row['flow_tokens']} | {cached} | {uncached} | {output} |"
        )
    lines.extend(["", "## Descriptive headline metrics — Codex condition invalid", "", *markdown_metric_table(headline["workspace"], headline["codex"]), "", "No Workspace-minus-Codex quality conclusion is valid from these values. The Codex condition must be rerun with working read-only repository inspection."])
    for dimension, title in (
        ("partition", "Partition breakdown"),
        ("category", "Issue-category breakdown"),
        ("retrieval_topology", "Retrieval-topology breakdown"),
        ("repository", "Repository breakdown"),
    ):
        lines.extend(["", f"## {title}", "", "| Group | System | Cases | P@5 | R@5 | NDCG@5 | Any hit | Full recall |", "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |"])
        groups = sorted(set(breakdowns[dimension]["workspace"]) | set(breakdowns[dimension]["codex"]))
        for group in groups:
            for system, label in (("workspace", "Workspace"), ("codex", "Codex")):
                summary = breakdowns[dimension][system][group]
                metrics = summary["metrics"]
                lines.append(f"| `{group}` | {label} | {summary['case_count']} | {fmt(metrics['p@5'])} | {fmt(metrics['r@5'])} | {fmt(metrics['ndcg@5'])} | {fmt(metrics['implementation_any_hit'])} | {fmt(metrics['implementation_full_recall'])} |")
    lines.extend(["", "## Per-case headline results", "", "| Case | System | P@5 | R@5 | NDCG@5 | Files | Oracle hits |", "| --- | --- | ---: | ---: | ---: | ---: | ---: |"])
    for row in sorted(selected, key=lambda item: (str(item["case_id"]), str(item["system"]))):
        metrics = row["metrics"]
        lines.append(f"| `{row['case_id']}` | {row['system']} | {fmt(metrics['p@5'])} | {fmt(metrics['r@5'])} | {fmt(metrics['ndcg@5'])} | {len(row['retrieved_files'])} | {int(metrics['implementation_hit_count'])} |")
    lines.extend([
        "",
        "## Four-run stability analysis",
        "",
        "The companion four-run report contains all 280 valid executions, per-case hit counts, full-recall counts, retrieved-file Jaccard stability, and run-level token/time data. Its macro-average is descriptive stability evidence, not the one-run protocol headline.",
        "",
        *markdown_metric_table(four_run_summaries["workspace"], four_run_summaries["codex"]),
        "",
        "## Limitations",
        "",
        "- Workspace indexing tokens and combined indexing-plus-flow totals are unavailable because no matching provider-logged build artifact was retained.",
        "- The Codex condition is invalid for quality comparison: every execution encountered repository-command policy rejection, and 134/140 returned no usable evidence.",
        "- Workspace response generation was skipped; this report evaluates retrieval through final evidence selection, not prose quality.",
        "- The Workspace campaign contains a disclosed implementation boundary: final-selection contract handling and coverage-payload budgeting were repaired while the batch was running. Results are retained as the requested campaign, but they are not evidence from one immutable commit.",
        "- Standard P@k penalizes short result lists because unreturned ranks are nonrelevant.",
        "",
        "## Reproduction",
        "",
        f"- Generator: `{Path(__file__).relative_to(ROOT).as_posix()}`",
        f"- Workspace merged ledger: `{MERGED_LEDGER.relative_to(ROOT).as_posix()}`",
        f"- Codex ledger: `{CODEX_LEDGER.relative_to(ROOT).as_posix()}`",
        f"- Four-run JSON: `{REPORT_JSON.relative_to(ROOT).as_posix()}`",
        f"- Full-precision main JSON: `{MAIN_REPORT_JSON.relative_to(ROOT).as_posix()}`",
        "",
    ])
    MAIN_REPORT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    manifest = load_json(MANIFEST_PATH)
    cases = [item for item in manifest.get("cases", ()) if item.get("group") != "question_usage"]
    if len(cases) != 35:
        raise RuntimeError(f"Expected 35 cases, found {len(cases)}")
    case_by_id = {str(item["case_id"]): item for item in cases}
    case_ids = tuple(case_by_id)
    topology = load_json(TOPOLOGY_PATH).get("assignments", {})
    if set(topology) != set(case_ids):
        raise RuntimeError("Topology assignment set does not match the 35-case corpus")

    workspace_ledger = merge_workspace_ledgers(case_ids)
    codex_ledger = load_json(CODEX_LEDGER)
    rows: list[dict[str, Any]] = []
    for system, ledger in (("workspace", workspace_ledger), ("codex", codex_ledger)):
        seen: set[str] = set()
        for case_id in case_ids:
            run_entries = ledger["cases"][case_id]["campaign_runs"]
            if len(run_entries) != 4:
                raise RuntimeError(f"{system}/{case_id}: expected four runs")
            verification = load_json(ROOT / "testing" / "codeRepoQA" / "corpus" / "cases" / case_id / "verification.json")
            oracle = verification.get("oracle", {})
            implementation = unique_paths(oracle.get("implementation_files"))
            supporting = unique_paths([
                *unique_paths(oracle.get("test_or_validation_files")),
                *unique_paths(oracle.get("documentation_files")),
            ])
            if not implementation:
                raise RuntimeError(f"{case_id}: no implementation Oracle")
            for repetition, entry in enumerate(run_entries, start=1):
                run_id = str(entry["run_id"])
                if run_id in seen:
                    raise RuntimeError(f"Duplicate {system} run {run_id}")
                seen.add(run_id)
                metadata, orchestration, comparison = run_artifacts(case_id, run_id)
                retrieval = orchestration.get("retrieval_result", {})
                summary = retrieval.get("retrieval_summary", {}) if isinstance(retrieval, Mapping) else {}
                evidence = retrieval.get("evidence", ()) if isinstance(retrieval, Mapping) else ()
                metrics = retrieval_metrics(comparison, implementation, supporting)
                if system == "workspace":
                    usage = workspace_usage(summary)
                    token_detail = {
                        "prompt_tokens": usage["prompt_tokens"],
                        "completion_tokens": usage["completion_tokens"],
                    }
                    flow_tokens = usage["total_tokens"]
                    model = str((metadata.get("llm_config") or {}).get("model", ""))
                    profile = "qualification_first_controller_v1"
                    index_rebuilt = bool(summary.get("index_rebuilt", False))
                else:
                    usage = summary.get("usage", {}) if isinstance(summary, Mapping) else {}
                    flow_tokens = int(usage.get("input_plus_output_tokens", 0) or 0)
                    token_detail = {
                        "cached_input_tokens": int(usage.get("cached_input_tokens", 0) or 0),
                        "uncached_input_tokens": int(usage.get("uncached_input_tokens", 0) or 0),
                        "output_tokens": int(usage.get("output_tokens", 0) or 0),
                        "reasoning_output_tokens": int(usage.get("reasoning_output_tokens", 0) or 0),
                    }
                    model = str(metadata.get("codex_model", ""))
                    profile = str(metadata.get("codex_prompt_profile", ""))
                    index_rebuilt = False
                case = case_by_id[case_id]
                rows.append({
                    "system": system,
                    "case_id": case_id,
                    "repository": str(case["repository"]),
                    "category": str(case["group"]),
                    "partition": str(case["statistics_partition"]),
                    "retrieval_topology": str(topology[case_id]),
                    "repetition": repetition,
                    "run_id": run_id,
                    "model": model,
                    "profile": profile,
                    "elapsed_seconds": iso_seconds(str(entry["started_at"]), str(entry["completed_at"])),
                    "coverage_status": str(retrieval.get("coverage_status", "unknown")),
                    "sufficient": bool(retrieval.get("sufficient", False)),
                    "evidence_count": len(evidence) if isinstance(evidence, list) else 0,
                    "retrieved_files": unique_paths(comparison.get("retrieved_source_files")),
                    "implementation_oracle_files": implementation,
                    "implementation_overlap_files": unique_paths(comparison.get("implementation_overlap_files")),
                    "metrics": metrics,
                    "flow_tokens": flow_tokens,
                    "token_detail": token_detail,
                    "index_rebuilt": index_rebuilt,
                    "indexing_tokens": None if system == "workspace" else 0,
                })
        if len(seen) != 140:
            raise RuntimeError(f"Expected 140 unique {system} runs, found {len(seen)}")

    workspace_rows = [row for row in rows if row["system"] == "workspace"]
    codex_rows = [row for row in rows if row["system"] == "codex"]
    summaries = {"workspace": system_summary(workspace_rows), "codex": system_summary(codex_rows)}
    breakdowns: dict[str, Any] = {}
    for dimension in ("partition", "category", "retrieval_topology", "repository"):
        breakdowns[dimension] = {
            "workspace": grouped_summaries(workspace_rows, dimension),
            "codex": grouped_summaries(codex_rows, dimension),
        }
    per_case: dict[str, Any] = {}
    for case_id in case_ids:
        item: dict[str, Any] = {}
        for system, system_rows in (("workspace", workspace_rows), ("codex", codex_rows)):
            selected = [row for row in system_rows if row["case_id"] == case_id]
            item[system] = {
                "mean_metrics": mean_dict(selected),
                "stability": case_stability(selected),
                "coverage_statuses": dict(Counter(str(row["coverage_status"]) for row in selected)),
                "mean_flow_tokens": mean(float(row["flow_tokens"]) for row in selected),
                "mean_elapsed_seconds": mean(float(row["elapsed_seconds"]) for row in selected),
                "run_ids": [row["run_id"] for row in selected],
            }
        item.update({
            "category": case_by_id[case_id]["group"],
            "partition": case_by_id[case_id]["statistics_partition"],
            "repository": case_by_id[case_id]["repository"],
            "retrieval_topology": topology[case_id],
        })
        per_case[case_id] = item

    delta = {
        key: summaries["workspace"]["metrics"][key] - summaries["codex"]["metrics"][key]
        for key in METRIC_KEYS
    }
    report = {
        "schema_version": 1,
        "title": "Workspace vs Codex Luna efficient — 35-case four-run comparison",
        "status": "workspace_complete_codex_condition_invalid",
        "comparison_valid": False,
        "comparison_invalid_reason": "All 140 Codex runs had repository shell commands rejected by execution policy; 134 returned no usable evidence.",
        "case_count": 35,
        "runs_per_case_per_system": 4,
        "workspace_run_count": 140,
        "codex_run_count": 140,
        "workspace_ledger": str(MERGED_LEDGER.relative_to(ROOT)).replace("\\", "/"),
        "codex_ledger": str(CODEX_LEDGER.relative_to(ROOT)).replace("\\", "/"),
        "aggregation": "Compute each run, average four runs per case, then macro-average 35 case means.",
        "summaries": summaries,
        "workspace_minus_codex": delta,
        "breakdowns": breakdowns,
        "per_case": per_case,
        "run_inventory": rows,
        "limitations": [
            "Workspace indexing-token usage is not provider-logged, so flow tokens are compared separately and indexing totals are unavailable.",
            "Workspace runs after the first three cases used two concurrent workers; elapsed time is reported as requested.",
            "Response generation was skipped for workspace runs; the comparison concerns retrieval and final evidence selection.",
            "Excluded failed attempts remain in the source ledgers and do not enter metrics.",
        ],
    }
    REPORT_JSON.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Workspace vs Codex Luna Efficient — 35-Case Four-Run Comparison",
        "",
        "## Status and scope",
        "",
        "Workspace complete: 35 cases and 140 valid retrieval runs. The frozen Codex ledger contains 140 artifact-complete executions, but it is not a valid retrieval condition: every run had repository shell commands rejected by execution policy and 134 returned no usable evidence. Codex values below are retained for failure audit only and must not be presented as a functioning Workspace-versus-Codex comparison.",
        "",
        "## Conditions",
        "",
        "- Workspace: `configs/testing/statistics-workspace.json`, `gpt-5.6-luna`, qualification-first controller, response generation skipped, final evidence selection enabled.",
        "- Codex: frozen `2026-08-26-codex-luna-four-runs.json`, `gpt-5.6-luna`, `efficient` prompt profile.",
        "- Aggregation: calculate each run, average four runs within each case, then macro-average the 35 case means.",
        "- Workspace collection used two workers for the final 32 cases; elapsed time is compared directly as requested.",
        "",
        "## Metric note",
        "",
        "Files are ranked. Implementation Oracle files define precision and recall; test/validation and documentation Oracle files receive partial NDCG relevance. Missing ranks are nonrelevant. Values are calculated at 1, 2, 5, and 10.",
        "",
        "## Descriptive metrics — Codex condition invalid",
        "",
        *markdown_metric_table(summaries["workspace"], summaries["codex"]),
        "",
        "No inferential Workspace-minus-Codex conclusion is valid from this campaign because the Codex repository-inspection condition failed.",
        "",
        "## Operational summary",
        "",
        "| System | Sufficient rate | Mean retrieved files | Any implementation hit | Full implementation recall | Mean flow tokens | Mean elapsed seconds |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, key in (("Workspace", "workspace"), ("Codex Luna efficient", "codex")):
        summary = summaries[key]
        metrics = summary["metrics"]
        lines.append(
            f"| {name} | {fmt(summary['sufficient_rate'])} | {fmt(metrics['retrieved_file_count'])} | {fmt(metrics['implementation_any_hit'])} | {fmt(metrics['implementation_full_recall'])} | {summary['mean_flow_tokens']:.0f} | {summary['mean_elapsed_seconds']:.1f} |"
        )

    for dimension, title in (
        ("partition", "Partition breakdown"),
        ("category", "Issue-category breakdown"),
        ("retrieval_topology", "Retrieval-topology breakdown"),
        ("repository", "Repository breakdown"),
    ):
        lines.extend(["", f"## {title}", "", "| Group | System | Cases | Runs | P@5 | R@5 | NDCG@5 | Any hit | Full recall |", "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"])
        groups = sorted(set(breakdowns[dimension]["workspace"]) | set(breakdowns[dimension]["codex"]))
        for group in groups:
            for system, label in (("workspace", "Workspace"), ("codex", "Codex")):
                summary = breakdowns[dimension][system][group]
                metrics = summary["metrics"]
                lines.append(f"| `{group}` | {label} | {summary['case_count']} | {summary['run_count']} | {fmt(metrics['p@5'])} | {fmt(metrics['r@5'])} | {fmt(metrics['ndcg@5'])} | {fmt(metrics['implementation_any_hit'])} | {fmt(metrics['implementation_full_recall'])} |")

    lines.extend(["", "## Per-case results", "", "| Case | Partition | Topology | System | P@5 | R@5 | NDCG@5 | Any-hit runs | Full-recall runs | Mean files | Mean tokens | Mean seconds |", "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"])
    for case_id in sorted(per_case):
        case = per_case[case_id]
        for system, label in (("workspace", "Workspace"), ("codex", "Codex")):
            item = case[system]
            metrics = item["mean_metrics"]
            stability = item["stability"]
            lines.append(
                f"| `{case_id}` | `{case['partition']}` | `{case['retrieval_topology']}` | {label} | {fmt(metrics['p@5'])} | {fmt(metrics['r@5'])} | {fmt(metrics['ndcg@5'])} | {stability['any_implementation_hit_runs']}/4 | {stability['full_implementation_recall_runs']}/4 | {fmt(metrics['retrieved_file_count'])} | {item['mean_flow_tokens']:.0f} | {item['mean_elapsed_seconds']:.1f} |"
            )

    lines.extend(["", "## Run inventory", "", "The JSON companion contains normalized ranked files, Oracle overlap, all metric values, and token components for every row.", "", "| Case | System | Rep | Run | Coverage | Sufficient | Evidence | Files | Flow tokens | Seconds |", "| --- | --- | ---: | --- | --- | --- | ---: | ---: | ---: | ---: |"])
    for row in sorted(rows, key=lambda item: (item["case_id"], item["system"], item["repetition"])):
        lines.append(f"| `{row['case_id']}` | {row['system']} | {row['repetition']} | `{row['run_id']}` | `{row['coverage_status']}` | {str(row['sufficient']).lower()} | {row['evidence_count']} | {len(row['retrieved_files'])} | {row['flow_tokens']} | {row['elapsed_seconds']:.1f} |")

    lines.extend(["", "## Limitations", "", "- Workspace indexing-token usage is not provider-logged. The report compares recorded non-indexing retrieval-flow tokens and marks Workspace indexing totals unavailable.", "- Response generation was skipped for Workspace; this is a retrieval and final-evidence comparison.", "- Failed attempts are retained in the three source Workspace ledgers but excluded from the 140 valid-run inventory.", "- The complete topology assignment file was finalized from frozen issue/Oracle structure without consulting retrieval output; the earlier documentation contained only five explicit examples.", "", "## Reproduction", "", f"- Script: `{Path(__file__).relative_to(ROOT).as_posix()}`", f"- Workspace ledger: `{MERGED_LEDGER.relative_to(ROOT).as_posix()}`", f"- Codex ledger: `{CODEX_LEDGER.relative_to(ROOT).as_posix()}`", f"- JSON report: `{REPORT_JSON.relative_to(ROOT).as_posix()}`", ""])
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    write_main_statistics(rows, summaries, per_case)

    print(json.dumps({
        "workspace_runs": len(workspace_rows),
        "codex_runs": len(codex_rows),
        "workspace": summaries["workspace"],
        "codex": summaries["codex"],
        "report_json": str(REPORT_JSON),
        "report_md": str(REPORT_MD),
        "main_report_json": str(MAIN_REPORT_JSON),
        "main_report_md": str(MAIN_REPORT_MD),
    }, indent=2))


if __name__ == "__main__":
    main()
