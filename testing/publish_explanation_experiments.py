from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish saved-evidence explanation experiments to UI run history.")
    parser.add_argument("experiment_dirs", nargs="+", type=Path)
    args = parser.parse_args()

    root = Path.cwd().resolve()
    for raw_dir in args.experiment_dirs:
        experiment_dir = raw_dir if raw_dir.is_absolute() else root / raw_dir
        _publish_experiment(root, experiment_dir.resolve())


def _publish_experiment(root: Path, experiment_dir: Path) -> None:
    manifest = _mapping(_load_json(experiment_dir / "manifest.json"))
    source_name = str(manifest.get("source") or manifest.get("source_run") or "").strip()
    if not source_name:
        raise RuntimeError(f"Experiment manifest has no source: {experiment_dir}")
    prompt = str(manifest.get("user_prompt") or "").strip()
    evidence, retrieval_result = _source_material(root, source_name, prompt=prompt)
    timestamp = _experiment_timestamp(experiment_dir.name)
    source_label = _source_label(source_name)

    result_paths = sorted(
        path
        for path in experiment_dir.glob("*.json")
        if path.name != "manifest.json"
    )
    for result_path in result_paths:
        experiment_result = _mapping(_load_json(result_path))
        if str(experiment_result.get("status") or "") != "complete":
            continue
        run_id = _run_id(timestamp, source_label, result_path.stem)
        run_dir = root / ".guided-intelligence" / "runs" / run_id
        if run_dir.exists():
            print(f"SKIP existing {run_id}", flush=True)
            continue
        run_dir.mkdir(parents=True)
        elapsed = float(experiment_result.get("elapsed_seconds") or 0.0)
        completed_at = timestamp + timedelta(seconds=max(0.0, elapsed))
        expectation_results = _mapping(experiment_result.get("expectation_results"))
        format_miss = bool(expectation_results) and not bool(expectation_results.get("passed", False))
        title = _title(source_label, experiment_result, format_miss=format_miss)
        response_payload = _response_payload(
            experiment_result,
            selected_intents=manifest.get("selected_intents", ()),
            title=title,
            experiment_dir=experiment_dir,
            result_path=result_path,
            format_miss=format_miss,
        )
        orchestration = {
            "conversation_id": run_id,
            "policy_result": {
                "allowed": True,
                "allowed_sources": sorted({str(item.get("source_category") or "") for item in evidence}),
                "assistance_request": "understand_code",
                "boundary_choices": [],
                "reason": "Saved-evidence explanation replay published to UI history.",
                "retrieval_required": False,
                "source_policy_name": "explanation_replay",
                "turn_type": "guided_explanation",
                "violations": [],
            },
            "response_payload": response_payload,
            "retrieval_result": retrieval_result,
            "run_trace_summary": {
                "allowed": True,
                "coverage_status": retrieval_result.get("coverage_status", "unknown"),
                "intents": list(manifest.get("selected_intents", ())),
                "retrieval_invoked": False,
                "turn_type": "guided_explanation",
                "violation_count": 0,
            },
        }
        metadata = {
            "run_id": run_id,
            "status": "complete",
            "phase": "complete",
            "created_at": timestamp.isoformat(),
            "completed_at": completed_at.isoformat(),
            "elapsed_seconds": elapsed,
            "workspace_root": str(root),
            "retrieval_mode": "saved_evidence_replay",
            "prompt": prompt,
            "allowed_sources": sorted({str(item.get("source_category") or "") for item in evidence}),
            "run_dir": str(run_dir),
            "progress_percent": 100,
            "progress_message": "Saved-evidence explanation replay complete.",
            "progress_logs": [
                "Previously retrieved evidence reused; retrieval was not rerun.",
                f"Explanation generated with {experiment_result.get('model', '')}.",
                "Experiment result published to UI history.",
            ],
            "retry_count": int(_mapping(experiment_result.get("metrics")).get("flow_repairs") or 0),
            "experiment_source": str(experiment_dir),
            "experiment_result": result_path.name,
        }
        _write_json(run_dir / "run-metadata.json", metadata)
        _write_json(run_dir / "orchestration-result.json", orchestration)
        _write_json(run_dir / "evidence-items.json", evidence)
        shutil.copy2(result_path, run_dir / "experiment-result.json")
        print(f"PUBLISHED {run_id}", flush=True)


def _source_material(root: Path, source_name: str, *, prompt: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_run_dir = root / ".guided-intelligence" / "runs" / source_name
    if source_run_dir.exists():
        evidence = _list_of_mappings(_load_json(source_run_dir / "evidence-items.json"))
        original = _mapping(_load_json(source_run_dir / "orchestration-result.json"))
        retrieval = _mapping(original.get("retrieval_result"))
        return evidence, retrieval

    fixture_path = root / "testing" / "fixtures" / f"{source_name}.json"
    fixture = _mapping(_load_json(fixture_path))
    evidence = _list_of_mappings(fixture.get("evidence"))
    retrieval = {
        "coverage_status": str(fixture.get("coverage_status") or "complete"),
        "sufficient": bool(fixture.get("sufficient", True)),
        "evidence": evidence,
        "retrieval_summary": {
            "retriever": "saved_evidence_fixture",
            "retrieval_plan": {"raw_prompt": prompt},
            "selected_count": len(evidence),
            "stop_reason": "saved_evidence_replay",
            "evidence_connections": {"version": 1, "status": "complete", "connections": []},
        },
    }
    return evidence, retrieval


def _response_payload(
    result: Mapping[str, Any],
    *,
    selected_intents: Any,
    title: str,
    experiment_dir: Path,
    result_path: Path,
    format_miss: bool,
) -> dict[str, Any]:
    story_flow = _list_of_mappings(result.get("story_flow"))
    ordered_stage_ids = [str(stage.get("stage_id") or "") for stage in story_flow]
    return {
        "content": str(result.get("markdown") or ""),
        "evidence_refs": [str(value) for value in result.get("used_evidence_refs", ())],
        "metadata": {
            "selected_intents": [str(value) for value in selected_intents],
            "answer_flow": {"ordered_stage_ids": ordered_stage_ids, "stages": story_flow},
            "story_flow": story_flow,
            "presentation_sections": list(result.get("presentation_sections", ())),
            "presentation_lists": list(result.get("presentation_lists", ())),
            "examples": list(result.get("examples", ())),
            "comparison_tables": list(result.get("comparison_tables", ())),
            "additional_implementation_observations": list(
                result.get("additional_implementation_observations", ())
            ),
            "source_attributions": list(result.get("source_attributions", ())),
            "understanding_checks": list(result.get("understanding_checks", ())),
            "concept_definitions": [],
            "next_checks": [],
            "render_notes": {
                "title": title,
                "summary": "Saved-evidence explanation replay; retrieval was not rerun.",
            },
            "model": str(result.get("model") or ""),
            "experiment": {
                "variant": str(result.get("variant") or ""),
                "provider": str(result.get("provider") or ""),
                "source_dir": str(experiment_dir),
                "result_file": result_path.name,
                "format_expectation_missed": format_miss,
                "metrics": _mapping(result.get("metrics")),
                "expectation_results": _mapping(result.get("expectation_results")),
            },
        },
    }


def _experiment_timestamp(name: str) -> datetime:
    match = re.search(r"(\d{8}T\d{6}Z)", name)
    if not match:
        return datetime.now(timezone.utc)
    return datetime.strptime(match.group(1), "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)


def _run_id(timestamp: datetime, source_label: str, result_name: str) -> str:
    stamp = timestamp.strftime("%Y%m%dT%H%M%SZ")
    slug = re.sub(r"[^a-z0-9-]+", "-", f"{source_label}-{result_name}".lower()).strip("-")
    return f"run-{stamp}-luna-{slug}"


def _source_label(source_name: str) -> str:
    if source_name.startswith("run-"):
        return "intent-flow"
    return source_name.removeprefix("explanation_").removesuffix("_case").replace("_", "-")


def _title(source_label: str, result: Mapping[str, Any], *, format_miss: bool) -> str:
    source = source_label.replace("-", " ").title()
    variant = str(result.get("variant") or "baseline").replace("-", " ").title()
    repeat = str(result.get("name") or "").rsplit("-", 1)[-1]
    suffix = " · format miss" if format_miss else ""
    return f"Luna replay · {source} · {variant} {repeat}{suffix}"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _list_of_mappings(value: Any) -> list[dict[str, Any]]:
    return [dict(item) for item in value] if isinstance(value, list) else []


if __name__ == "__main__":
    main()
