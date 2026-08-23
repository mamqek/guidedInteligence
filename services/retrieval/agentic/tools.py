from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Any, Mapping, Sequence

from services.retrieval.agentic.contracts import AgentState, AgentToolCall, AgentToolOutcome, ArtifactRecord


@dataclass(frozen=True)
class ToolRequest:
    tool_name: str
    arguments: Mapping[str, Any]
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "arguments": dict(self.arguments),
            "reason": self.reason,
        }


TOOL_NAMES = (
    "list_leads",
    "inspect_lead",
    "open_source",
    "graph_neighbors",
    "exact_search",
    "semantic_search",
)


class AgentToolExecutor:
    def __init__(self, *, qdrant_tool: Any, structural_tools: Mapping[str, Any], trace: Any) -> None:
        self.qdrant_tool = qdrant_tool
        self.structural_tools = structural_tools
        self.trace = trace

    def execute(self, state: AgentState, call: AgentToolCall) -> tuple[dict[str, Any], tuple[str, ...]]:
        if call.tool not in TOOL_NAMES:
            raise RuntimeError(f"agent_tool_unknown:{call.tool}")
        before = set(state.artifacts)
        try:
            if call.tool == "list_leads":
                payload = self._list_leads(state, call)
            elif call.tool == "inspect_lead":
                payload = self._inspect_lead(state, call)
            elif call.tool == "open_source":
                payload = self._open_source(state, call)
            elif call.tool == "graph_neighbors":
                payload = self._graph_neighbors(state, call)
            elif call.tool == "exact_search":
                payload = self._exact_search(state, call)
            else:
                payload = self._semantic_search(state, call)
        except RuntimeError as exc:
            payload = {"status": "error", "error": str(exc)}
        added = tuple(value for value in state.artifacts if value not in before)
        state.tool_outcomes.append(
            AgentToolOutcome(
                iteration=state.iteration,
                tool=call.tool,
                status="error" if payload.get("status") == "error" else "ok",
                fingerprint=call.fingerprint(),
                result_summary=_tool_result_summary(payload),
                new_artifact_ids=added,
            )
        )
        del state.tool_outcomes[:-20]
        self.trace.record(
            "agent_tool_executed",
            {
                "iteration": state.iteration,
                "tool": call.tool,
                "purpose": call.purpose,
                "expected_signal": call.expected_signal,
                "arguments": _call_arguments(call),
                "new_artifact_ids": list(added),
                "result": payload,
            },
        )
        return payload, added

    def _list_leads(self, state: AgentState, call: AgentToolCall) -> dict[str, Any]:
        query = call.query.casefold().strip()
        path = call.path.replace("\\", "/").casefold().strip()
        values = []
        for artifact_id in state.initial_lead_ids:
            item = state.artifacts[artifact_id]
            haystack = f"{item.path} {item.symbol} {item.source_text}".casefold()
            if query and query not in haystack:
                continue
            if path and path not in item.path.casefold():
                continue
            values.append(item.summary())
            if len(values) >= _limit(call.limit, 20):
                break
        return {"leads": values, "remaining_match_count_unknown": len(values) >= _limit(call.limit, 20)}

    def _inspect_lead(self, state: AgentState, call: AgentToolCall) -> dict[str, Any]:
        item = state.artifacts.get(call.lead_id)
        if item is None:
            raise RuntimeError(f"agent_tool_invalid_lead:{call.lead_id}")
        start, end = item.line_start, item.line_end
        if item.node_id:
            # The boundary already attached the structural owner range to the lead.
            start = min(start, item.line_start)
            end = max(end, item.line_end)
        source = _read_source(state, item.path, start, end)
        item.source_text = source
        item.inspected = True
        item.status = "inspected"
        state.recent_artifact_ids.append(item.id)
        return {"artifact": item.summary(preview_chars=1200), "source_text": source}

    def _open_source(self, state: AgentState, call: AgentToolCall) -> dict[str, Any]:
        path = _safe_relative_path(state, call.path)
        start = max(1, int(call.line_start or 1))
        end = max(start, int(call.line_end or start + 39))
        end = min(end, start + state.request.budget.max_source_lines - 1)
        source = _read_source(state, path, start, end)
        artifact = _artifact(
            path=path,
            line_start=start,
            line_end=end,
            source_text=source,
            discovery_origin="open_source",
        )
        artifact.inspected = True
        artifact.status = "inspected"
        state.artifacts.setdefault(artifact.id, artifact)
        state.recent_artifact_ids.append(artifact.id)
        return {"artifact": state.artifacts[artifact.id].summary(preview_chars=1200), "source_text": source}

    def _graph_neighbors(self, state: AgentState, call: AgentToolCall) -> dict[str, Any]:
        if not call.node_id:
            raise RuntimeError("agent_tool_graph_missing_node_id")
        request = ToolRequest(
            tool_name="structural_expand_nodes",
            arguments={"node_ids": [call.node_id], "depth": 1, "limit": _limit(call.limit, 12)},
            reason=call.purpose,
        )
        result = self.structural_tools["structural_expand_nodes"].run(request)
        self.trace.record_tool(request, result, round_index=state.iteration)
        if result.status != "ok":
            raise RuntimeError(f"agent_graph_neighbors_failed:{result.payload.get('reason', 'unknown')}")
        nodes = []
        for value in result.payload.get("nodes", ()):
            if not isinstance(value, Mapping):
                continue
            path = str(value.get("path") or "").replace("\\", "/")
            if not path:
                continue
            try:
                path = _safe_relative_path(state, path)
            except RuntimeError:
                continue
            start = max(1, int(value.get("line_start") or 1))
            end = max(start, int(value.get("line_end") or start))
            artifact = _artifact(
                path=path,
                line_start=start,
                line_end=end,
                source_text="",
                symbol=str(value.get("qualified_name") or value.get("name") or ""),
                node_id=str(value.get("id") or ""),
                discovery_origin="graph",
                parent_ids=(call.node_id,),
            )
            state.artifacts.setdefault(artifact.id, artifact)
            nodes.append(state.artifacts[artifact.id].summary())
        return {"nodes": nodes, "edges": list(result.payload.get("edges", ()))[:24]}

    def _exact_search(self, state: AgentState, call: AgentToolCall) -> dict[str, Any]:
        if not call.query.strip():
            raise RuntimeError("agent_tool_exact_search_empty_query")
        workspace = Path(state.request.workspace_root).resolve()
        command = ["rg", "--json", "--fixed-strings", "--max-count", "2", call.query]
        for excluded in state.request.scope.excluded_paths:
            command.extend(("--glob", f"!{excluded.rstrip('/')}/**"))
        if call.path:
            command.append(_safe_search_path(state, call.path))
        else:
            command.append(".")
        matches: list[dict[str, Any]] = []
        process = subprocess.Popen(
            command,
            cwd=str(workspace),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        try:
            assert process.stdout is not None
            for raw in process.stdout:
                try:
                    event = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if event.get("type") != "match":
                    continue
                data = event.get("data", {})
                path = str(data.get("path", {}).get("text") or "").replace("\\", "/")
                line = max(1, int(data.get("line_number") or 1))
                try:
                    path = _safe_relative_path(state, path)
                except RuntimeError:
                    continue
                source = _read_source(state, path, line, line)
                artifact = _artifact(
                    path=path,
                    line_start=line,
                    line_end=line,
                    source_text=source,
                    discovery_origin="exact_search",
                )
                artifact.inspected = True
                artifact.status = "inspected"
                state.artifacts.setdefault(artifact.id, artifact)
                state.recent_artifact_ids.append(artifact.id)
                matches.append(state.artifacts[artifact.id].summary(preview_chars=500))
                if len(matches) >= _limit(call.limit, 20):
                    process.terminate()
                    break
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
            if process.stdout is not None:
                process.stdout.close()
            if process.stderr is not None:
                process.stderr.close()
        return {"matches": matches}

    def _semantic_search(self, state: AgentState, call: AgentToolCall) -> dict[str, Any]:
        if not call.query.strip():
            raise RuntimeError("agent_tool_semantic_search_empty_query")
        arguments: dict[str, Any] = {
            "query": call.query,
            "sparse_query": call.query,
            "dense_enabled": state.request.scope.dense_search_enabled,
            "limit": _limit(call.limit, 12),
            "max_per_path": 2,
            "source_category": "source_code",
            "file_role": "any",
        }
        if call.path:
            arguments["path"] = _safe_relative_path(state, call.path)
        request = ToolRequest(tool_name="qdrant_hybrid_search", arguments=arguments, reason=call.purpose)
        result = self.qdrant_tool.run(request)
        self.trace.record_tool(request, result, round_index=state.iteration)
        if result.status != "ok":
            raise RuntimeError(f"agent_semantic_search_failed:{result.payload.get('reason', 'unknown')}")
        matches = []
        for value in result.payload.get("results", ()):
            if not isinstance(value, Mapping):
                continue
            path = _safe_relative_path(state, str(value.get("path") or ""))
            start = max(1, int(value.get("line_start") or 1))
            end = max(start, int(value.get("line_end") or start))
            source = _read_source(state, path, start, end)
            artifact = _artifact(
                path=path,
                line_start=start,
                line_end=end,
                source_text=source,
                discovery_origin="semantic_search",
            )
            artifact.inspected = True
            artifact.status = "inspected"
            state.artifacts.setdefault(artifact.id, artifact)
            state.recent_artifact_ids.append(artifact.id)
            matches.append(state.artifacts[artifact.id].summary(preview_chars=700))
        return {"matches": matches}


def _artifact(
    *, path: str, line_start: int, line_end: int, source_text: str,
    symbol: str = "", node_id: str = "", discovery_origin: str,
    parent_ids: Sequence[str] = (), artifact_kind: str = "other",
    obligation_ids: Sequence[str] = (),
) -> ArtifactRecord:
    identity = f"{path}:{line_start}:{line_end}:{node_id}:{discovery_origin}"
    artifact_id = "artifact_" + hashlib.sha1(identity.encode("utf-8")).hexdigest()[:16]
    return ArtifactRecord(
        id=artifact_id,
        path=path,
        line_start=line_start,
        line_end=line_end,
        source_text=source_text,
        symbol=symbol,
        node_id=node_id,
        artifact_kind=artifact_kind,
        obligation_ids=tuple(obligation_ids),
        discovery_origin=discovery_origin,
        parent_ids=tuple(parent_ids),
    )


def artifact_from_lead(lead: Any) -> ArtifactRecord:
    structural = lead.structural_handles[0] if lead.structural_handles else None
    return ArtifactRecord(
        id=lead.id,
        path=lead.path,
        line_start=structural.line_start if structural else lead.line_start,
        line_end=structural.line_end if structural else lead.line_end,
        source_text=lead.preview,
        symbol=structural.symbol if structural else "",
        node_id=structural.node_id if structural else "",
        artifact_kind=lead.artifact_kind,
        obligation_ids=lead.obligation_ids,
        discovery_origin="initial_lead",
    )


def _safe_relative_path(state: AgentState, value: str) -> str:
    normalized = _validated_scope_path(state, value)
    root = Path(state.request.workspace_root).resolve()
    resolved = (root / normalized).resolve()
    if not resolved.is_file():
        raise RuntimeError(f"agent_tool_file_not_found:{normalized}")
    return resolved.relative_to(root).as_posix()


def _safe_search_path(state: AgentState, value: str) -> str:
    normalized = _validated_scope_path(state, value)
    root = Path(state.request.workspace_root).resolve()
    resolved = (root / normalized).resolve()
    if not resolved.exists():
        raise RuntimeError(f"agent_tool_search_path_not_found:{normalized}")
    return resolved.relative_to(root).as_posix()


def _validated_scope_path(state: AgentState, value: str) -> str:
    normalized = value.strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    if not normalized:
        raise RuntimeError("agent_tool_empty_path")
    relative = Path(normalized)
    if relative.is_absolute() or ".." in relative.parts:
        raise RuntimeError(f"agent_tool_path_outside_workspace:{value}")
    folded = normalized.casefold().rstrip("/")
    for excluded in state.request.scope.excluded_paths:
        prefix = excluded.strip().replace("\\", "/").strip("/").casefold()
        if prefix and (folded == prefix or folded.startswith(prefix + "/")):
            raise RuntimeError(f"agent_tool_excluded_path:{normalized}")
    root = Path(state.request.workspace_root).resolve()
    resolved = (root / relative).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise RuntimeError(f"agent_tool_path_outside_workspace:{value}") from exc
    return resolved.relative_to(root).as_posix()


def _read_source(state: AgentState, path: str, line_start: int, line_end: int) -> str:
    normalized = _safe_relative_path(state, path)
    root = Path(state.request.workspace_root).resolve()
    lines = (root / normalized).read_text(encoding="utf-8", errors="replace").splitlines()
    start = max(1, line_start)
    end = min(len(lines), max(start, line_end), start + state.request.budget.max_source_lines - 1)
    return "\n".join(f"{number}: {lines[number - 1]}" for number in range(start, end + 1))


def _call_arguments(call: AgentToolCall) -> dict[str, Any]:
    return {
        "lead_id": call.lead_id,
        "path": call.path,
        "line_start": call.line_start,
        "line_end": call.line_end,
        "node_id": call.node_id,
        "direction": call.direction,
        "query": call.query,
        "limit": call.limit,
    }


def _limit(value: int, default: int) -> int:
    return max(1, min(int(value or default), 50))


def _tool_result_summary(payload: Mapping[str, Any]) -> str:
    if payload.get("status") == "error":
        return f"error:{str(payload.get('error') or 'unknown')[:300]}"
    for key in ("matches", "nodes", "leads"):
        values = payload.get(key)
        if isinstance(values, Sequence) and not isinstance(values, (str, bytes)):
            paths = tuple(
                str(value.get("path") or "")
                for value in values[:5]
                if isinstance(value, Mapping) and str(value.get("path") or "")
            )
            suffix = f";paths={','.join(paths)}" if paths else ""
            return f"{key}={len(values)}{suffix}"
    artifact = payload.get("artifact")
    if isinstance(artifact, Mapping):
        return (
            f"artifact={str(artifact.get('id') or '')};"
            f"path={str(artifact.get('path') or '')};inspected={bool(artifact.get('inspected'))}"
        )
    return "ok"
