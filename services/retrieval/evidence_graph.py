from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from core.models import EvidenceItem, RetrievalResult
from services.llm.json_completion import complete_json


PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
SEMANTIC_PROMPT_PATH = PROMPTS_DIR / "evidence_graph_semantic.md"
SEMANTIC_SCHEMA_PATH = PROMPTS_DIR / "evidence_graph_semantic.schema.json"
CODEGRAPH_BRIDGE_PATH = Path(__file__).resolve().parent / "codegraph" / "selected_evidence_edges.mjs"
GRAPH_VERSION = 2
GRAPH_PROMPT_VERSION = "codegraph_semantic_v8"
MAX_EVIDENCE_ITEMS = 12
MAX_CODEGRAPH_EDGES = 24
MAX_CONNECTIONS = 16

LogEvent = Callable[[str, Mapping[str, Any]], None]


def build_evidence_graph(
    retrieval_result: RetrievalResult,
    *,
    workspace_root: str | Path,
    user_prompt: str,
    llm_config: Any,
    log_event: LogEvent | None = None,
) -> RetrievalResult:
    evidence = tuple(retrieval_result.evidence[:MAX_EVIDENCE_ITEMS])
    if len(evidence) < 2:
        return _with_graph(
            retrieval_result,
            {
                "version": GRAPH_VERSION,
                "status": "complete",
                "connections": [],
                "generation": {"reason": "fewer_than_two_evidence_items"},
            },
        )

    root = Path(workspace_root).resolve()
    if log_event is not None:
        log_event(
            "evidence_graph_generation_started",
            {"evidence_count": len(evidence), "workspace_root": str(root)},
        )
    try:
        structural = _codegraph_edges(root, evidence)
        payload = _semantic_payload(
            evidence=evidence,
            user_prompt=user_prompt,
            codegraph_edges=structural.get("direct_candidates", ()),
            document_reference_edges=_document_reference_edges(root, evidence),
        )
        cache_path = _cache_path(root, payload)
        cached = _load_cached_graph(cache_path)
        if cached is not None:
            graph = {
                **cached,
                "generation": {**dict(cached.get("generation") or {}), "cache_hit": True},
            }
            if log_event is not None:
                log_event(
                    "evidence_graph_cache_hit",
                    {"cache_path": str(cache_path), "connection_count": len(graph.get("connections", ()))},
                )
            return _with_graph(retrieval_result, graph)

        response = complete_json(
            llm_config,
            (
                {"role": "system", "content": SEMANTIC_PROMPT_PATH.read_text(encoding="utf-8")},
                {"role": "user", "content": json.dumps(payload, sort_keys=True)},
            ),
            response_format=_semantic_response_format(tuple(item.source_id for item in evidence)),
            log_event=log_event,
        )
        connections = _minimal_connection_forest(
            _structural_connections(
                codegraph_edges=payload["codegraph_edges"],
                document_reference_edges=payload["document_reference_edges"],
            )
            + _validated_connections(
                response.get("connections"),
                evidence=evidence,
                document_reference_edges=payload["document_reference_edges"],
            )
        )
        root_ref, disconnected, connected_refs = _graph_coverage(response, connections=connections, evidence=evidence)
        graph = {
            "version": GRAPH_VERSION,
            "status": "complete",
            "connections": connections,
            "root_ref": root_ref,
            "disconnected_evidence": disconnected,
            "generation": {
                "strategy": GRAPH_PROMPT_VERSION,
                "structural_provider": "codegraph",
                "semantic_provider": "llm",
                "codegraph_candidate_count": len(payload["codegraph_edges"]),
                "document_reference_count": len(payload["document_reference_edges"]),
                "connected_evidence_count": len(connected_refs),
                "cache_hit": False,
            },
        }
        _write_cached_graph(cache_path, graph)
        if log_event is not None:
            log_event(
                "evidence_graph_generation_completed",
                {
                    "connection_count": len(connections),
                    "codegraph_candidate_count": len(payload["codegraph_edges"]),
                    "document_reference_count": len(payload["document_reference_edges"]),
                    "connected_evidence_count": graph["generation"]["connected_evidence_count"],
                    "cache_path": str(cache_path),
                },
            )
        return _with_graph(retrieval_result, graph)
    except Exception as exc:
        graph = {
            "version": GRAPH_VERSION,
            "status": "error",
            "connections": [],
            "error": f"Evidence graph generation failed: {exc}",
            "generation": {"strategy": GRAPH_PROMPT_VERSION, "cache_hit": False},
        }
        if log_event is not None:
            log_event("evidence_graph_generation_failed", {"error": str(exc), "error_type": type(exc).__name__})
        return _with_graph(retrieval_result, graph)


def _codegraph_edges(workspace_root: Path, evidence: Sequence[EvidenceItem]) -> Mapping[str, Any]:
    payload = {
        "workspace_root": str(workspace_root),
        "evidence": [
            {
                "source_ref": item.source_id,
                "path": _evidence_path(item),
                "line_start": _evidence_lines(item)[0],
                "line_end": _evidence_lines(item)[1],
            }
            for item in evidence
        ],
    }
    completed = subprocess.run(
        ("node", str(CODEGRAPH_BRIDGE_PATH)),
        input=json.dumps(payload),
        cwd=str(Path(__file__).resolve().parents[2]),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "unknown CodeGraph error").strip()[:1600]
        raise RuntimeError(f"CodeGraph selected-evidence analysis failed: {detail}")
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("CodeGraph selected-evidence analysis returned invalid JSON.") from exc
    if not isinstance(parsed, Mapping):
        raise RuntimeError("CodeGraph selected-evidence analysis returned a non-object result.")
    return parsed


def _semantic_payload(
    *,
    evidence: Sequence[EvidenceItem],
    user_prompt: str,
    codegraph_edges: Any,
    document_reference_edges: Sequence[Mapping[str, str]],
) -> dict[str, Any]:
    valid_refs = {item.source_id for item in evidence}
    compact_edges: list[dict[str, Any]] = []
    if isinstance(codegraph_edges, Sequence) and not isinstance(codegraph_edges, (str, bytes)):
        for index, raw in enumerate(codegraph_edges, start=1):
            if not isinstance(raw, Mapping):
                continue
            source_ref = str(raw.get("source_ref") or "")
            target_ref = str(raw.get("target_ref") or "")
            if source_ref not in valid_refs or target_ref not in valid_refs or source_ref == target_ref:
                continue
            compact_edges.append(
                {
                    "id": f"cg{index}",
                    "source_ref": source_ref,
                    "target_ref": target_ref,
                    "edge_kind": str(raw.get("edge_kind") or "references"),
                    "source_symbol": str(raw.get("source_symbol") or ""),
                    "target_symbol": str(raw.get("target_symbol") or ""),
                    "source_file": str(raw.get("source_file") or ""),
                    "target_file": str(raw.get("target_file") or ""),
                    "provenance": str(raw.get("provenance") or ""),
                }
            )
            if len(compact_edges) >= MAX_CODEGRAPH_EDGES:
                break
    return {
        "user_question": user_prompt[:6000],
        "selected_evidence": [_compact_evidence(item) for item in evidence],
        "codegraph_edges": compact_edges,
        "document_reference_edges": [dict(item) for item in document_reference_edges],
    }


def _document_reference_edges(workspace_root: Path, evidence: Sequence[EvidenceItem]) -> list[dict[str, str]]:
    documents = {
        Path(_evidence_path(item)).name.lower(): item.source_id
        for item in evidence
        if Path(_evidence_path(item)).suffix.lower() in {".md", ".json", ".yaml", ".yml", ".toml"}
    }
    if not documents:
        return []
    output: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in evidence:
        path = _evidence_path(item)
        if Path(path).suffix.lower() in {".md", ".json", ".yaml", ".yml", ".toml"}:
            continue
        full_path = workspace_root / path
        try:
            source = full_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        identifiers = set(re.findall(r"\b[A-Z][A-Z0-9_]{2,}\b", item.snippet))
        for identifier in sorted(identifiers):
            assignment = re.search(
                rf"(?m)^\s*(?:const\s+|let\s+|var\s+)?{re.escape(identifier)}(?:\s*:[^=]+)?\s*=\s*([^\n;]+)",
                source,
            )
            if assignment is None:
                continue
            string_values = re.findall(r"[\"']([^\"']+)[\"']", assignment.group(1))
            for value in string_values:
                target_ref = documents.get(Path(value).name.lower())
                key = (item.source_id, target_ref or "")
                if not target_ref or key in seen:
                    continue
                seen.add(key)
                output.append(
                    {
                        "source_ref": item.source_id,
                        "target_ref": target_ref,
                        "relationship": "references selected document through a path constant",
                        "path_constant": identifier,
                        "document": Path(value).name,
                    }
                )
    return output


def _compact_evidence(item: EvidenceItem) -> dict[str, Any]:
    lines = item.snippet.splitlines()[:60]
    snippet = "\n".join(line[:240] for line in lines)
    line_start, line_end = _evidence_lines(item)
    return {
        "source_ref": item.source_id,
        "title": str(item.metadata.get("claim_supported") or item.metadata.get("why_relevant") or _evidence_path(item))[:300],
        "path": _evidence_path(item),
        "line_start": line_start,
        "line_end": line_end,
        "snippet": snippet,
    }


def _validated_connections(
    value: Any,
    *,
    evidence: Sequence[EvidenceItem],
    document_reference_edges: Sequence[Mapping[str, str]] = (),
) -> list[dict[str, str]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise RuntimeError("Evidence graph model response is missing the connections array.")
    valid_refs = {item.source_id for item in evidence}
    allowed_kinds = {"dependency", "control_flow", "data_flow", "configuration", "validation", "rendering", "other"}
    document_refs = {
        item.source_id
        for item in evidence
        if Path(_evidence_path(item)).suffix.lower() in {".md", ".json", ".yaml", ".yml", ".toml"}
    }
    direct_document_pairs = {
        frozenset((str(item.get("source_ref") or ""), str(item.get("target_ref") or "")))
        for item in document_reference_edges
    }
    accepted: list[dict[str, str]] = []
    seen_pairs: set[frozenset[str]] = set()
    for raw in value:
        if not isinstance(raw, Mapping):
            continue
        source_ref = str(raw.get("source_ref") or "").strip()
        target_ref = str(raw.get("target_ref") or "").strip()
        kind = str(raw.get("relationship_kind") or "").strip().lower()
        label = str(raw.get("label") or "").strip()
        description = str(raw.get("description") or "").strip()
        grounding = str(raw.get("grounding") or "").strip().lower()
        confidence = str(raw.get("confidence") or "").strip().lower()
        if source_ref not in valid_refs or target_ref not in valid_refs or source_ref == target_ref:
            continue
        if kind not in allowed_kinds or not label or not description:
            continue
        if grounding not in {"direct", "inferred"} or confidence not in {"high", "medium", "low"}:
            continue
        if grounding == "direct" and (source_ref in document_refs or target_ref in document_refs):
            if frozenset((source_ref, target_ref)) not in direct_document_pairs:
                continue
        if grounding == "inferred" and confidence == "high":
            confidence = "medium"
        pair = frozenset((source_ref, target_ref))
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        accepted.append(
            {
                "source_ref": source_ref,
                "target_ref": target_ref,
                "relationship_kind": kind,
                "label": label[:100],
                "description": description[:500],
                "grounding": grounding,
                "confidence": confidence,
            }
        )
        if len(accepted) >= MAX_CONNECTIONS:
            break
    if not accepted:
        raise RuntimeError("Evidence graph model returned no valid connections.")
    return accepted


def _structural_connections(
    *,
    codegraph_edges: Sequence[Mapping[str, Any]],
    document_reference_edges: Sequence[Mapping[str, str]],
) -> list[dict[str, str]]:
    connections: list[dict[str, str]] = []
    kind_map = {
        "calls": "control_flow",
        "imports": "dependency",
        "references": "dependency",
        "extends": "dependency",
        "implements": "dependency",
    }
    for edge in codegraph_edges:
        source_ref = str(edge.get("source_ref") or "")
        target_ref = str(edge.get("target_ref") or "")
        edge_kind = str(edge.get("edge_kind") or "references").lower()
        source_symbol = str(edge.get("source_symbol") or Path(str(edge.get("source_file") or "source")).name)
        target_symbol = str(edge.get("target_symbol") or Path(str(edge.get("target_file") or "target")).name)
        verb = "calls" if edge_kind == "calls" else edge_kind.rstrip("s") or "references"
        connections.append(
            {
                "source_ref": source_ref,
                "target_ref": target_ref,
                "relationship_kind": kind_map.get(edge_kind, "dependency"),
                "label": f"{source_symbol} {verb} {target_symbol}"[:100],
                "description": f"CodeGraph resolves a direct {edge_kind} relationship from {source_symbol} to {target_symbol}."[:500],
                "grounding": "direct",
                "confidence": "high",
            }
        )
    for edge in document_reference_edges:
        constant = str(edge.get("path_constant") or "the selected path constant")
        document = str(edge.get("document") or "the selected document")
        connections.append(
            {
                "source_ref": str(edge.get("source_ref") or ""),
                "target_ref": str(edge.get("target_ref") or ""),
                "relationship_kind": "configuration",
                "label": f"loads {document}"[:100],
                "description": f"The selected code references {document} through {constant}."[:500],
                "grounding": "direct",
                "confidence": "high",
            }
        )
    return connections


def _semantic_response_format(evidence_refs: Sequence[str]) -> Mapping[str, Any]:
    schema = json.loads(SEMANTIC_SCHEMA_PATH.read_text(encoding="utf-8"))
    item = schema["properties"]["connections"]["items"]
    item["properties"]["source_ref"]["enum"] = list(evidence_refs)
    item["properties"]["target_ref"]["enum"] = list(evidence_refs)
    schema["properties"]["root_ref"]["enum"] = list(evidence_refs)
    schema["properties"]["disconnected_evidence"]["items"]["properties"]["evidence_ref"]["enum"] = list(evidence_refs)
    return {
        "type": "json_schema",
        "json_schema": {"name": "evidence_graph_semantic", "strict": True, "schema": schema},
    }


def _graph_coverage(
    response: Mapping[str, Any],
    *,
    connections: Sequence[Mapping[str, str]],
    evidence: Sequence[EvidenceItem],
) -> tuple[str, list[dict[str, str]], set[str]]:
    valid_refs = {item.source_id for item in evidence}
    root_ref = str(response.get("root_ref") or "").strip()
    if root_ref not in valid_refs:
        raise RuntimeError("Evidence graph model returned an invalid root_ref.")
    disconnected: list[dict[str, str]] = []
    disconnected_refs: set[str] = set()
    raw_disconnected = response.get("disconnected_evidence")
    if isinstance(raw_disconnected, Sequence) and not isinstance(raw_disconnected, (str, bytes)):
        for raw in raw_disconnected:
            if not isinstance(raw, Mapping):
                continue
            evidence_ref = str(raw.get("evidence_ref") or "").strip()
            reason = str(raw.get("reason") or "").strip()
            if evidence_ref not in valid_refs or evidence_ref == root_ref or not reason or evidence_ref in disconnected_refs:
                continue
            disconnected_refs.add(evidence_ref)
            disconnected.append({"evidence_ref": evidence_ref, "reason": reason[:300]})

    adjacency = {ref: set() for ref in valid_refs}
    for connection in connections:
        source_ref = connection["source_ref"]
        target_ref = connection["target_ref"]
        adjacency[source_ref].add(target_ref)
        adjacency[target_ref].add(source_ref)
    connected = {root_ref}
    pending = [root_ref]
    while pending:
        current = pending.pop()
        for neighbor in adjacency[current] - connected:
            connected.add(neighbor)
            pending.append(neighbor)
    if connected & disconnected_refs:
        disconnected = [item for item in disconnected if item["evidence_ref"] not in connected]
        disconnected_refs = {item["evidence_ref"] for item in disconnected}
    unaccounted = valid_refs - connected - disconnected_refs
    if unaccounted:
        raise RuntimeError(
            "Evidence graph model left selected evidence outside the main flow without a disconnected reason: "
            + ", ".join(sorted(unaccounted))
        )
    return root_ref, disconnected, connected


def _minimal_connection_forest(connections: Sequence[dict[str, str]]) -> list[dict[str, str]]:
    parents: dict[str, str] = {}

    def find(value: str) -> str:
        parents.setdefault(value, value)
        while parents[value] != value:
            parents[value] = parents[parents[value]]
            value = parents[value]
        return value

    accepted: list[dict[str, str]] = []
    for connection in connections:
        source_root = find(connection["source_ref"])
        target_root = find(connection["target_ref"])
        if source_root == target_root:
            continue
        parents[target_root] = source_root
        accepted.append(connection)
    return accepted


def _evidence_path(item: EvidenceItem) -> str:
    path = str(item.metadata.get("path") or "").strip()
    if path:
        return path.replace("\\", "/")
    source_id = item.source_id.split(":", 1)[-1]
    return source_id.rsplit(":L", 1)[0].replace("\\", "/")


def _evidence_lines(item: EvidenceItem) -> tuple[int, int]:
    value = str(item.metadata.get("line_range") or item.source_id.rsplit(":", 1)[-1])
    if value.startswith("L") and "-L" in value:
        start, end = value[1:].split("-L", 1)
        if start.isdigit() and end.isdigit():
            return int(start), int(end)
    return 1, max(1, len(item.snippet.splitlines()))


def _cache_path(workspace_root: Path, payload: Mapping[str, Any]) -> Path:
    digest_input = json.dumps(
        {"version": GRAPH_PROMPT_VERSION, "payload": payload},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    digest = hashlib.sha256(digest_input).hexdigest()
    return workspace_root / ".guided-intelligence" / "evidence-graph-cache" / f"{digest}.json"


def _load_cached_graph(path: Path) -> Mapping[str, Any] | None:
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(value, Mapping) or value.get("status") != "complete":
        return None
    connections = value.get("connections")
    if not isinstance(connections, list) or not connections:
        return None
    return value


def _write_cached_graph(path: Path, graph: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(graph, indent=2, sort_keys=True), encoding="utf-8")


def _with_graph(retrieval_result: RetrievalResult, graph: Mapping[str, Any]) -> RetrievalResult:
    summary = dict(retrieval_result.retrieval_summary)
    summary["evidence_connections"] = dict(graph)
    return replace(retrieval_result, retrieval_summary=summary)
