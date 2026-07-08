from __future__ import annotations

# Owns run trace persistence and tool-event recording. Do not place retrieval policy, candidate selection, or stage orchestration here.

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from services.retrieval.workspace.tools import ToolObservation, ToolRequest
from services.retrieval.workspace.pipeline.file_level import tool_summary_payload


class RetrievalTrace:
    def __init__(self, *, run_dir: str | Path | None) -> None:
        self.run_dir = Path(run_dir) if run_dir else None

    def record_tool(self, request: ToolRequest, observation: ToolObservation, *, round_index: int) -> None:
        self.record("tool_call_requested", {"round": round_index, **request.to_dict()})
        self.record("tool_observation_created", {"round": round_index, **observation.to_dict()})
        self.record(
            "tool_result_summary",
            {
                "round": round_index,
                "tool_name": request.tool_name,
                "request_reason": request.reason,
                "request_arguments": dict(request.arguments),
                "status": observation.status,
                **tool_summary_payload(observation),
            },
        )

    def record(self, event_type: str, payload: Mapping[str, Any]) -> None:
        if self.run_dir is None:
            return
        run_dir = self.run_dir
        run_dir.mkdir(parents=True, exist_ok=True)
        event = {
            "event_type": event_type,
            "conversation_id": payload.get("conversation_id", ""),
            "payload": dict(payload),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        with (run_dir / "retrieval-trace.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")

    def start_stage(self, stage_key: str, stage_label: str, **payload: Any) -> float:
        self.record(
            "retrieval_stage_started",
            {
                "stage_key": stage_key,
                "stage_label": stage_label,
                **payload,
            },
        )
        return time.perf_counter()

    def complete_stage(
        self,
        stage_key: str,
        stage_label: str,
        started_at: float,
        **payload: Any,
    ) -> None:
        self.record(
            "retrieval_stage_completed",
            {
                "stage_key": stage_key,
                "stage_label": stage_label,
                "elapsed_ms": int((time.perf_counter() - started_at) * 1000),
                **payload,
            },
        )
