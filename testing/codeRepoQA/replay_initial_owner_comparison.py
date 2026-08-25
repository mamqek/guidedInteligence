from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.llm.json_completion import complete_json
from services.retrieval.workspace.pipeline.execution_flow.initial_owner_comparison import (
    _global_response_format,
    _prompt_text,
    _validate_global_response,
)
from services.retrieval.workspace.pipeline.execution_flow.tracing import RetrievalTrace
from testing.codeRepoQA.run_case import _load_project_llm_config


def _events(path: Path) -> tuple[dict[str, Any], ...]:
    return tuple(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def _saved_comparison_payload(events: tuple[dict[str, Any], ...]) -> Mapping[str, Any]:
    for event in events:
        payload = event.get("payload", {})
        if event.get("event_type") != "llm_response_received" or payload.get("stage") != "initial_owner_comparison":
            continue
        messages = payload.get("request_payload", {}).get("messages", ())
        if not messages:
            break
        return json.loads(messages[-1]["content"])
    raise RuntimeError("saved_initial_owner_comparison_request_not_found")


def _expected_groups(payload: Mapping[str, Any]) -> dict[str, tuple[str, ...]]:
    return {
        str(group["id"]): tuple(str(owner_id) for owner_id in group.get("owners", ()))
        for group in payload.get("groups", ())
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay one saved real initial-owner comparison payload.")
    parser.add_argument("--source-trace", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--run-config", default="configs/testing/workspace.json")
    parser.add_argument("--max-selected", type=int, default=24)
    args = parser.parse_args()

    source_trace = Path(args.source_trace).resolve()
    output_dir = Path(args.output_dir).resolve()
    run_config = json.loads(Path(args.run_config).read_text(encoding="utf-8"))
    llm_config = _load_project_llm_config(run_config)
    saved_payload = _saved_comparison_payload(_events(source_trace))
    expected = _expected_groups(saved_payload)
    prompt = _prompt_text(max_selected=args.max_selected)
    response_format = _global_response_format(expected, max_selected=args.max_selected)
    trace = RetrievalTrace(run_dir=output_dir)

    def log_event(event_type: str, value: Mapping[str, Any]) -> None:
        trace.record(event_type, {"stage": "initial_owner_comparison_grouped_replay", **dict(value)})

    response = complete_json(
        llm_config,
        (
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(saved_payload, sort_keys=True)},
        ),
        response_format=response_format,
        log_event=log_event,
    )
    selected_by_group = _validate_global_response(response, expected, max_selected=args.max_selected)
    owners = saved_payload.get("owners", {})
    views = saved_payload.get("views", {})
    rendered: list[dict[str, Any]] = []
    for group_id, owner_ids in selected_by_group.items():
        selected_owners: list[dict[str, Any]] = []
        for owner_id in owner_ids:
            owner = owners.get(owner_id, {})
            view_id = next(iter(owner.get("v", ())), "")
            view = views.get(view_id, {})
            selected_owners.append(
                {
                    "owner_id": owner_id,
                    "symbol": owner.get("s", ""),
                    "path": view.get("p", ""),
                    "range": view.get("r", ()),
                    "view": view.get("x", ""),
                    "selection_role": "primary" if owner_id == owner_ids[0] else "additional",
                }
            )
        rendered.append({"group_id": group_id, "owners": selected_owners})
    selected_count = sum(len(value) for value in selected_by_group.values())
    max_per_file = max((len(value) for value in selected_by_group.values()), default=0)
    trace.record(
        "grouped_owner_comparison_replay_completed",
        {
            "source_trace": str(source_trace),
            "input_candidate_count": len(owners),
            "input_file_count": len(expected),
            "selected_count": selected_count,
            "selected_file_count": len(selected_by_group),
            "primary_selected_count": len(selected_by_group),
            "additional_selected_count": selected_count - len(selected_by_group),
            "max_selected_per_file": max_per_file,
            "largest_file_selection_share": max_per_file / selected_count if selected_count else 0.0,
            "selected_groups": rendered,
        },
    )
    print(output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
