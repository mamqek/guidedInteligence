"""Score final September runs against the required-evidence reference."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
DEFAULT_REFERENCE = HERE / "source-transition-oracle.json"
DEFAULT_INVENTORY = ROOT / "testing/codeRepoQA/statistics/runs/2026-09-16-five-mode-four-runs.json"
DEFAULT_OUTPUT = HERE / "corpus-required-evidence-audit.json"
DEFAULT_REPORT = HERE / "corpus-required-evidence-audit.md"
DEFAULT_APPENDIX = HERE / "appendix-required-evidence-audit.md"
DEFAULT_MANUSCRIPT_APPENDIX = ROOT / "thesis/manuscript/appendix-required-evidence-audit.md"

MODE_LABELS = {
    "full": "Full Workspace",
    "no-codegraph": "Without CodeGraph",
    "no-controller": "Without controller",
    "neither": "Without either",
    "codex": "Codex",
}
STATUS_ORDER = {"absent": 0, "partial": 1, "present": 2}
DECLARATION_PREFIXES = ("def ", "function ", "class ", "interface ")
STAGES = [
    ("raw_retrieval", {"initial_query_channel_results"}),
    ("range_preparation", {"initial_exact_ranges_deduplicated", "initial_codegraph_ranges_resolved", "initial_ranges_without_codegraph", "initial_snippets_canonicalized"}),
    ("initial_comparison", {"initial_files_admitted", "initial_owner_comparison_created", "round_zero_snippets_selected"}),
    ("controller_or_qualification", {"qualification_decisions_created", "qualification_reuse_evaluated", "controller_action_executed", "owner_continuation_executed", "tool_observation_created"}),
    ("candidate_pool", {"final_candidate_pool_created"}),
]
LOSS_LABELS = {
    "raw_retrieval": "raw retrieval",
    "range_preparation": "range preparation",
    "initial_comparison": "initial comparison",
    "controller_or_qualification": "controller recovery or qualification",
    "candidate_pool": "candidate-pool construction",
    "final_selection": "final evidence selection",
    "codex_internal_trace_unavailable": "Codex internal trace unavailable",
    "none": "—",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--appendix", type=Path, default=DEFAULT_APPENDIX)
    parser.add_argument("--manuscript-appendix", type=Path, default=DEFAULT_MANUSCRIPT_APPENDIX)
    parser.add_argument("--test-root", type=Path, default=Path(r"C:\Programming\guidedInteligence_testcases"))
    return parser.parse_args()


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_path(value: Any) -> str:
    return str(value or "").replace("\\", "/").lstrip("./")


def collect_fragments(value: Any) -> list[dict[str, Any]]:
    """Collect source-bearing objects recursively from one artifact or trace payload."""
    found: list[dict[str, Any]] = []

    def visit(item: Any) -> None:
        if isinstance(item, list):
            for child in item:
                visit(child)
            return
        if not isinstance(item, dict):
            return
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        handle = item.get("handle") if isinstance(item.get("handle"), dict) else {}
        source = item.get("source") if isinstance(item.get("source"), dict) else {}
        path = normalize_path(item.get("path") or item.get("file") or metadata.get("path") or handle.get("path") or source.get("path"))
        start = safe_int(item.get("line_start") or metadata.get("line_start") or handle.get("full_line_start") or handle.get("line_start") or source.get("line_start"))
        end = safe_int(item.get("line_end") or metadata.get("line_end") or handle.get("full_line_end") or handle.get("line_end") or source.get("line_end"))
        texts = [item[key] for key in ("snippet", "text", "source_text", "qualification_reason", "reason") if isinstance(item.get(key), str)]
        if path:
            found.append({"path": path, "line_start": start, "line_end": end, "text": "\n".join(texts)})
        for child in item.values():
            if isinstance(child, (dict, list)):
                visit(child)

    visit(value)
    return found


def source_lines(snapshot_root: Path, path: str) -> list[str]:
    source = snapshot_root / Path(path)
    if not source.is_file():
        return []
    return source.read_text(encoding="utf-8", errors="replace").splitlines()


def anchor_lines(unit: dict[str, Any], snapshot_root: Path) -> list[int]:
    source = unit["source"]
    lines = source_lines(snapshot_root, source["path"])
    positions: list[int] = []
    for anchor in unit.get("anchors", []):
        location = None
        for index in range(source["line_start"] - 1, min(source["line_end"], len(lines))):
            if anchor in lines[index]:
                location = index + 1
                break
        if location is None:
            raise ValueError(f"anchor missing while scoring: {source['path']}:{source['line_start']}-{source['line_end']} {anchor!r}")
        positions.append(location)
    return positions


def unit_status(unit: dict[str, Any], fragments: Iterable[dict[str, Any]], snapshot_root: Path) -> str:
    source = unit["source"]
    target_path = normalize_path(source["path"])
    relevant = [fragment for fragment in fragments if normalize_path(fragment.get("path")) == target_path]
    if not relevant:
        return "absent"
    anchors = unit.get("anchors", [])
    positions = anchor_lines(unit, snapshot_root)
    if anchors:
        covered = [
            any(
                anchor in fragment.get("text", "")
                or (fragment.get("line_start") is not None and fragment.get("line_end") is not None and fragment["line_start"] <= position <= fragment["line_end"])
                for fragment in relevant
            )
            for anchor, position in zip(anchors, positions)
        ]
        required_anchor_indexes = list(range(len(anchors)))
        if len(anchors) > 1 and anchors[0].lstrip().startswith(DECLARATION_PREFIXES):
            required_anchor_indexes = required_anchor_indexes[1:]
        if all(covered[index] for index in required_anchor_indexes):
            return "present"
        if any(covered):
            return "partial"
    start = source["line_start"]
    end = source["line_end"]
    if any(fragment.get("line_start") is not None and fragment.get("line_end") is not None and fragment["line_start"] <= start and fragment["line_end"] >= end for fragment in relevant):
        return "present"
    if any(fragment.get("line_start") is not None and fragment.get("line_end") is not None and fragment["line_start"] <= end and fragment["line_end"] >= start for fragment in relevant):
        return "partial"
    partial_range = unit.get("partial_range")
    if partial_range and any(
        fragment.get("line_start") is not None
        and fragment.get("line_end") is not None
        and fragment["line_start"] <= partial_range["line_end"]
        and fragment["line_end"] >= partial_range["line_start"]
        for fragment in relevant
    ):
        return "partial"
    return "absent"


def final_fragments(run: dict[str, Any], snapshot_root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    run_dir = Path(run["run_dir"])
    if run["mode"] == "codex":
        artifact = load_json(run_dir / "codex-evidence.json")
        fragments = []
        for item in artifact.get("evidence", []):
            path = normalize_path(item.get("file"))
            start = safe_int(item.get("line_start"))
            end = safe_int(item.get("line_end"))
            lines = source_lines(snapshot_root, path)
            text = "\n".join(lines[start - 1 : end]) if start is not None and end is not None and lines else ""
            fragments.append({"path": path, "line_start": start, "line_end": end, "text": text})
    else:
        fragments = collect_fragments(load_json(run_dir / "evidence-items.json"))
    files = sorted({fragment["path"] for fragment in fragments if fragment.get("path")})
    return fragments, files


def trace_stage_fragments(run: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    if run["mode"] == "codex":
        return {}
    grouped: dict[str, list[dict[str, Any]]] = {name: [] for name, _ in STAGES}
    trace_path = Path(run["run_dir"]) / "retrieval-trace.jsonl"
    with trace_path.open(encoding="utf-8") as handle:
        events = [json.loads(line) for line in handle if line.strip()]
    for stage, types in STAGES:
        for event in events:
            if event.get("event_type") in types:
                if stage == "controller_or_qualification" and event.get("event_type") == "tool_observation_created":
                    round_number = safe_int(event.get("payload", {}).get("round"))
                    if round_number is None or round_number <= 0:
                        continue
                grouped[stage].extend(collect_fragments(event.get("payload", {})))
    return grouped


def decisive_loss(final_status: str, stage_statuses: dict[str, str], mode: str) -> tuple[str, str]:
    if final_status == "present":
        return "none", "confirmed"
    if mode == "codex":
        return "codex_internal_trace_unavailable", "artifact_limited"
    ordered = [(name, stage_statuses.get(name, "absent")) for name, _ in STAGES]
    surviving = [index for index, (_, status) in enumerate(ordered) if STATUS_ORDER[status] > STATUS_ORDER[final_status]]
    if surviving:
        last = max(surviving)
        return ("final_selection", "confirmed") if last == len(ordered) - 1 else (ordered[last + 1][0], "derived")
    equal_or_better = [index for index, (_, status) in enumerate(ordered) if STATUS_ORDER[status] >= STATUS_ORDER[final_status] and status != "absent"]
    if equal_or_better:
        return ordered[min(equal_or_better)][0], "derived"
    return "raw_retrieval", "derived"


def score_run(run: dict[str, Any], case: dict[str, Any], test_root: Path) -> dict[str, Any]:
    snapshot_root = test_root / case["case_id"] / "s" / case["pre_resolution"]["snapshot"]
    final, selected_files = final_fragments(run, snapshot_root)
    inventory_files = sorted({normalize_path(path) for path in run.get("retrieved_files", [])})
    if selected_files != inventory_files:
        raise ValueError(
            f"final selected files disagree with campaign inventory for {run['run_id']}: "
            f"artifacts={selected_files}, inventory={inventory_files}"
        )
    stage_fragments = trace_stage_fragments(run)
    unit_results = []
    for unit in case["evidence_units"]:
        status = unit_status(unit, final, snapshot_root)
        stage_statuses = {stage: unit_status(unit, fragments, snapshot_root) for stage, fragments in stage_fragments.items()}
        boundary, confidence = decisive_loss(status, stage_statuses, run["mode"])
        unit_results.append({"unit_id": unit["id"], "status": status, "first_decisive_loss": boundary, "loss_confidence": confidence, "stage_statuses": stage_statuses})
    complete = all(result["status"] == "present" for result in unit_results)
    incomplete = [result for result in unit_results if result["status"] != "present"]
    first_loss = Counter(result["first_decisive_loss"] for result in incomplete).most_common(1)[0][0] if incomplete else "none"
    if not incomplete:
        first_loss_basis = "not_applicable"
    elif first_loss == "codex_internal_trace_unavailable":
        first_loss_basis = "trace_unavailable"
    elif all(result["loss_confidence"] == "confirmed" for result in incomplete if result["first_decisive_loss"] == first_loss):
        first_loss_basis = "directly_recorded"
    else:
        first_loss_basis = "inferred_from_stage_observations"
    required_paths = {normalize_path(unit["source"]["path"]) for unit in case["evidence_units"]}
    implementation_paths = {normalize_path(path) for path in case["implementation_oracle_files"]}
    return {
        "case": case["case_id"], "mode": run["mode"], "condition": MODE_LABELS[run["mode"]],
        "repetition": run["repetition"], "run_id": run["run_id"], "run_dir": run["run_dir"],
        "connected_required_evidence": case["connected_required_evidence"], "required_file_count": case["required_file_count"],
        "selected_file_count": len(selected_files), "selected_required_file_count": len(set(selected_files) & required_paths),
        "implementation_oracle_file_count": case["implementation_oracle_file_count"],
        "selected_implementation_oracle_file_count": len(set(selected_files) & implementation_paths),
        "selected_nonimplementation_file_count": len(set(selected_files) - implementation_paths),
        "selected_files": selected_files, "evidence_complete": complete,
        "present_unit_count": sum(result["status"] == "present" for result in unit_results),
        "partial_unit_count": sum(result["status"] == "partial" for result in unit_results),
        "required_unit_count": len(unit_results), "first_decisive_loss": first_loss,
        "first_loss_basis": first_loss_basis, "unit_results": unit_results,
    }


def aggregate(runs: list[dict[str, Any]], cases: dict[str, dict[str, Any]]) -> dict[str, Any]:
    by_mode = {}
    for mode in MODE_LABELS:
        selected = [run for run in runs if run["mode"] == mode]
        units = sum(run["required_unit_count"] for run in selected)
        by_mode[mode] = {
            "runs": len(selected), "complete_runs": sum(run["evidence_complete"] for run in selected),
            "complete_rate": sum(run["evidence_complete"] for run in selected) / len(selected),
            "present_units": sum(run["present_unit_count"] for run in selected), "required_units": units,
            "unit_survival_rate": sum(run["present_unit_count"] for run in selected) / units,
            "mean_selected_files": mean(run["selected_file_count"] for run in selected),
            "mean_selected_required_files": mean(run["selected_required_file_count"] for run in selected),
            "mean_selected_implementation_oracle_files": mean(run["selected_implementation_oracle_file_count"] for run in selected),
            "mean_selected_nonimplementation_files": mean(run["selected_nonimplementation_file_count"] for run in selected),
            "capacity_shortfall_runs": sum(run["selected_file_count"] < run["required_file_count"] for run in selected),
            "implementation_capacity_shortfall_runs": sum(run["selected_file_count"] < run["implementation_oracle_file_count"] for run in selected),
            "complete_implementation_oracle_file_coverage_runs": sum(run["selected_implementation_oracle_file_count"] == run["implementation_oracle_file_count"] for run in selected),
            "loss_boundaries": dict(Counter(run["first_decisive_loss"] for run in selected if not run["evidence_complete"])),
            "unit_loss_boundaries": dict(Counter(result["first_decisive_loss"] for run in selected for result in run["unit_results"] if result["status"] != "present")),
        }
    by_connection = {}
    for connected in (True, False):
        label = "connected" if connected else "independent"
        by_connection[label] = {}
        for mode in MODE_LABELS:
            selected = [run for run in runs if run["mode"] == mode and run["connected_required_evidence"] == connected]
            units = sum(run["required_unit_count"] for run in selected)
            by_connection[label][mode] = {
                "cases": len({run["case"] for run in selected}), "runs": len(selected),
                "complete_runs": sum(run["evidence_complete"] for run in selected),
                "complete_rate": sum(run["evidence_complete"] for run in selected) / len(selected) if selected else 0.0,
                "unit_survival_rate": sum(run["present_unit_count"] for run in selected) / units if units else 0.0,
            }
    by_required_file_count = {}
    for required_file_count in sorted({run["required_file_count"] for run in runs}):
        by_required_file_count[str(required_file_count)] = {}
        for mode in MODE_LABELS:
            selected = [run for run in runs if run["mode"] == mode and run["required_file_count"] == required_file_count]
            by_required_file_count[str(required_file_count)][mode] = {
                "cases": len({run["case"] for run in selected}),
                "runs": len(selected),
                "complete_runs": sum(run["evidence_complete"] for run in selected),
                "complete_rate": sum(run["evidence_complete"] for run in selected) / len(selected),
                "mean_selected_files": mean(run["selected_file_count"] for run in selected),
                "mean_required_files_represented": mean(run["selected_required_file_count"] for run in selected),
            }
    per_case = {}
    for case_id, case in cases.items():
        case_runs = [run for run in runs if run["case"] == case_id]
        per_case[case_id] = {"connected_required_evidence": case["connected_required_evidence"], "required_file_count": case["required_file_count"], "required_unit_count": len(case["evidence_units"]), "conditions": {}}
        for mode in MODE_LABELS:
            selected = [run for run in case_runs if run["mode"] == mode]
            per_case[case_id]["conditions"][mode] = {
                "complete_runs": sum(run["evidence_complete"] for run in selected), "runs": len(selected),
                "mean_selected_files": mean(run["selected_file_count"] for run in selected),
                "mean_selected_required_files": mean(run["selected_required_file_count"] for run in selected),
                "mean_selected_implementation_oracle_files": mean(run["selected_implementation_oracle_file_count"] for run in selected),
                "unit_survival": {unit["id"]: {status: sum(result["status"] == status for run in selected for result in run["unit_results"] if result["unit_id"] == unit["id"]) for status in ("present", "partial", "absent")} for unit in case["evidence_units"]},
            }
    return {"by_mode": by_mode, "by_connection": by_connection, "by_required_file_count": by_required_file_count, "per_case": per_case}


def percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def render_report(data: dict[str, Any]) -> str:
    summary = data["summary"]
    lines = ["# Corpus-wide required-evidence audit", "", "This report scores the 700 runs in the final September campaign against exact pre-resolution evidence requirements. File presence alone never satisfies a unit. Connections classify cases but are not separately scored at run level.", "", "## Overall results", "", "| Condition | Complete runs | Required-unit survival | Mean final files | Mean required files represented | Mean implementation-Oracle files represented | Mean other files | Capacity-shortfall runs |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for mode, label in MODE_LABELS.items():
        item = summary["by_mode"][mode]
        lines.append(f"| {label} | {item['complete_runs']}/{item['runs']} ({percent(item['complete_rate'])}) | {item['present_units']}/{item['required_units']} ({percent(item['unit_survival_rate'])}) | {item['mean_selected_files']:.2f} | {item['mean_selected_required_files']:.2f} | {item['mean_selected_implementation_oracle_files']:.2f} | {item['mean_selected_nonimplementation_files']:.2f} | {item['capacity_shortfall_runs']}/{item['runs']} |")
    lines.extend(["", "## Connected versus independent required evidence", "", "| Evidence layout | Condition | Cases | Complete runs | Required-unit survival |", "|---|---|---:|---:|---:|"])
    for connection in ("connected", "independent"):
        for mode, label in MODE_LABELS.items():
            item = summary["by_connection"][connection][mode]
            lines.append(f"| {connection.capitalize()} | {label} | {item['cases']} | {item['complete_runs']}/{item['runs']} ({percent(item['complete_rate'])}) | {percent(item['unit_survival_rate'])} |")
    lines.extend(["", "## Required-file count", "", "| Required files | Condition | Cases | Complete runs | Mean final files | Mean required files represented |", "|---:|---|---:|---:|---:|---:|"])
    for file_count, modes in summary["by_required_file_count"].items():
        for mode, label in MODE_LABELS.items():
            item = modes[mode]
            lines.append(f"| {file_count} | {label} | {item['cases']} | {item['complete_runs']}/{item['runs']} ({percent(item['complete_rate'])}) | {item['mean_selected_files']:.2f} | {item['mean_required_files_represented']:.2f} |")
    lines.extend(["", "## Interpretation boundary", "", "These measurements establish whether the exact required snippets survive together. Final-selection omissions are directly recorded. Earlier boundaries are inferred by comparing the last recorded stage where a unit is visible with the next stage where it is unavailable; they locate the boundary but not necessarily the exact internal decision responsible. The measurements do not establish that the response model understood a connection merely because both endpoints were present. Connectedness and required-file count are therefore explanatory case characteristics, not additional success criteria.", "", "Detailed per-case and per-run results are generated in appendix-required-evidence-audit.md.", ""])
    return "\n".join(lines)


def short_status(status: str) -> str:
    return {"present": "P", "partial": "Partial", "absent": "A"}[status]


def render_appendix(data: dict[str, Any], cases: dict[str, dict[str, Any]]) -> str:
    lines = ["# Appendix: Required-Evidence Audit", "", "This appendix reports all 700 run-level judgements. P means present, Partial means related source survives without all required anchors, and A means absent. `Final files` is the total number of distinct files returned by final selection. The two represented-file columns show how many files from the required-evidence reference and the broader implementation Oracle occur in that result. A directly recorded loss is supported by an explicit final-selection omission. An inferred boundary is the first stage at which a unit is unavailable after appearing in an earlier recorded stage; it does not identify the exact internal decision responsible.", ""]
    for case_id, case in cases.items():
        case_runs = [run for run in data["runs"] if run["case"] == case_id]
        units = [unit["id"] for unit in case["evidence_units"]]
        unit_labels = ", ".join(unit["id"] for unit in case["evidence_units"])
        lines.extend([f"## {case_id}", "", case["mechanism_summary"], "", f"Connected required evidence: **{'yes' if case['connected_required_evidence'] else 'no'}**. Required-evidence files: **{case['required_file_count']}**. Implementation-Oracle files: **{case['implementation_oracle_file_count']}**. Required units: {unit_labels}.", "", "| Unit | Exact pre-resolution source | Required responsibility |", "|---|---|---|"])
        for unit in case["evidence_units"]:
            source = unit["source"]
            lines.append(f"| {unit['id']} | `{source['path']}:{source['line_start']}-{source['line_end']}` (`{source['symbol']}`) | {unit['description']} |")
        lines.extend(["", "| Condition | Repetition / run ID | " + " | ".join(units) + " | Complete? | Final files | Required files represented | Implementation-Oracle files represented | Unit unavailability boundaries |", "|---|---|" + "---|" * len(units) + "---:|---:|---:|---:|---|"])
        for run in case_runs:
            statuses = {item["unit_id"]: short_status(item["status"]) for item in run["unit_results"]}
            losses = []
            for result in run["unit_results"]:
                if result["status"] == "present":
                    continue
                basis = {"confirmed": "direct", "derived": "inferred", "artifact_limited": "trace unavailable"}[result["loss_confidence"]]
                losses.append(f"{result['unit_id']}: {LOSS_LABELS[result['first_decisive_loss']]} [{basis}]")
            loss_text = "; ".join(losses) if losses else "—"
            lines.append(f"| {run['condition']} | {run['repetition']} · {run['run_id']} | " + " | ".join(statuses[unit] for unit in units) + f" | {'Yes' if run['evidence_complete'] else 'No'} | {run['selected_file_count']} | {run['selected_required_file_count']}/{run['required_file_count']} | {run['selected_implementation_oracle_file_count']}/{run['implementation_oracle_file_count']} | {loss_text} |")
        lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    reference = load_json(args.reference)
    inventory = load_json(args.inventory)
    cases = {case["case_id"]: case for case in reference["cases"]}
    scored = [score_run(run, cases[run["case"]], args.test_root) for run in inventory["run_inventory"]]
    if len(scored) != 700:
        raise ValueError(f"expected 700 runs, scored {len(scored)}")
    data = {
        "schema_version": 1, "audit_name": "final-september-required-evidence-audit",
        "campaign_inventory": str(args.inventory.relative_to(ROOT)).replace("\\", "/"),
        "reference": str(args.reference.relative_to(ROOT)).replace("\\", "/"),
        "reference_sha256": hashlib.sha256(args.reference.read_bytes()).hexdigest(),
        "run_count": len(scored), "case_count": len(cases), "boundary_vocabulary": LOSS_LABELS,
        "scoring_policy": {"file_presence_is_not_unit_presence": True, "present_requires_all_behavior_anchors": True, "leading_declaration_may_be_identity_only": True, "partial_requires_some_anchor_or_range_overlap": True, "connections_are_case_classification_only": True, "initial_comparison_definition": "the reduction from prepared ranges or owners to round-zero snippets admitted for qualification"},
        "summary": aggregate(scored, cases), "runs": scored,
    }
    args.output.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    args.report.write_text(render_report(data), encoding="utf-8")
    appendix_text = render_appendix(data, cases)
    args.appendix.write_text(appendix_text, encoding="utf-8")
    args.manuscript_appendix.write_text(appendix_text, encoding="utf-8")
    print(f"Scored {len(scored)} runs across {len(cases)} cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
