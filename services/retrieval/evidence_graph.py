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
from services.retrieval.resource_references import RESOURCE_EXTENSIONS, resource_reference_between_files


PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
SEMANTIC_PROMPT_PATH = PROMPTS_DIR / "evidence_graph_semantic.md"
SEMANTIC_SCHEMA_PATH = PROMPTS_DIR / "evidence_graph_semantic.schema.json"
ORGANIZER_PROMPT_PATH = PROMPTS_DIR / "codex_evidence_organizer.md"
ORGANIZER_SCHEMA_PATH = PROMPTS_DIR / "codex_evidence_organizer.schema.json"
CODEGRAPH_BRIDGE_PATH = Path(__file__).resolve().parent / "codegraph" / "selected_evidence_edges.mjs"
GRAPH_VERSION = 2
GRAPH_PROMPT_VERSION = "codegraph_semantic_v8"
ORGANIZER_VERSION = "codex_evidence_organizer_v1"
MAX_EVIDENCE_ITEMS = 12
MAX_CODEGRAPH_EDGES = 24
MAX_ORGANIZER_CODEGRAPH_EDGES = 40
MAX_CONNECTIONS = 16
ORGANIZER_MIN_SELECTED = 8
ORGANIZER_MAX_SELECTED = 16

LogEvent = Callable[[str, Mapping[str, Any]], None]


class EvidenceOrganizationError(RuntimeError):
    pass


class EvidenceOrganizationValidationError(ValueError):
    def __init__(self, errors: Sequence[str]) -> None:
        self.errors = tuple(str(error) for error in errors if str(error).strip())
        super().__init__("; ".join(self.errors))


def build_evidence_graph(
    retrieval_result: RetrievalResult,
    *,
    workspace_root: str | Path,
    user_prompt: str,
    llm_config: Any,
    organizer_enabled: bool = False,
    neutralize_candidate_order: bool = False,
    intent_flow: Mapping[str, Any] | None = None,
    log_event: LogEvent | None = None,
) -> RetrievalResult:
    if organizer_enabled:
        return _organize_codex_evidence(
            retrieval_result,
            workspace_root=workspace_root,
            user_prompt=user_prompt,
            intent_flow=intent_flow or {},
            neutralize_candidate_order=neutralize_candidate_order,
            llm_config=llm_config,
            log_event=log_event,
        )
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


def build_candidate_connections(
    evidence: Sequence[EvidenceItem],
    *,
    workspace_root: str | Path,
    existing_connections: Sequence[Mapping[str, Any]] = (),
) -> list[dict[str, str]]:
    """Build the deterministic graph used by the all-candidates UI mode.

    This does not select, promote, or otherwise alter generation evidence.
    Existing semantic connections may be included alongside CodeGraph and
    document-reference relationships.
    """
    items = tuple(evidence)
    if not items:
        return []
    root = Path(workspace_root).resolve()
    structural = _codegraph_edges(root, items)
    document_edges = _document_reference_edges(root, items)
    direct = _structural_connections(
        codegraph_edges=structural.get("direct_candidates", ()),
        document_reference_edges=document_edges,
    )
    valid_refs = {item.source_id for item in items}
    preserved = [
        dict(connection)
        for connection in existing_connections
        if str(connection.get("source_ref") or "") in valid_refs
        and str(connection.get("target_ref") or "") in valid_refs
    ]
    return _unique_connection_pairs([*direct, *preserved])


def _organize_codex_evidence(
    retrieval_result: RetrievalResult,
    *,
    workspace_root: str | Path,
    user_prompt: str,
    intent_flow: Mapping[str, Any],
    neutralize_candidate_order: bool,
    llm_config: Any,
    log_event: LogEvent | None,
) -> RetrievalResult:
    evidence = tuple(retrieval_result.evidence)
    model_evidence = (
        _stable_evidence_permutation(evidence, user_prompt=user_prompt)
        if neutralize_candidate_order
        else evidence
    )
    candidate_count = len(evidence)
    if not evidence:
        organization = {
            "version": ORGANIZER_VERSION,
            "status": "complete",
            "candidate_count": 0,
            "selected_count": 0,
            "excluded_count": 0,
            "coverage_facets": [],
            "assessments": [],
            "selected_refs": [],
            "excluded_refs": [],
            "repair_attempts": 0,
        }
        return replace(
            retrieval_result,
            retrieval_summary={
                **dict(retrieval_result.retrieval_summary),
                "selected_count": 0,
                "evidence_organization": organization,
                "evidence_connections": {"version": GRAPH_VERSION, "status": "complete", "connections": []},
            },
        )

    selected_min = min(candidate_count, ORGANIZER_MIN_SELECTED)
    selected_max = min(candidate_count, ORGANIZER_MAX_SELECTED)
    root = Path(workspace_root).resolve()
    if log_event is not None:
        log_event(
            "evidence_organization_started",
            {
                "candidate_count": candidate_count,
                "selected_min": selected_min,
                "selected_max": selected_max,
                "workspace_root": str(root),
            },
        )
    organizer_token_usage = {
        "request_count": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "cached_tokens": 0,
        "reasoning_tokens": 0,
    }

    def record_organizer_event(event_type: str, event_payload: Mapping[str, Any]) -> None:
        if log_event is not None:
            log_event(event_type, event_payload)
        if event_type != "llm_response_received":
            return
        raw_response = event_payload.get("raw_response")
        usage = raw_response.get("usage") if isinstance(raw_response, Mapping) else None
        if not isinstance(usage, Mapping):
            return
        organizer_token_usage["request_count"] += 1
        for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
            organizer_token_usage[key] += int(usage.get(key) or 0)
        prompt_details = usage.get("prompt_tokens_details")
        if isinstance(prompt_details, Mapping):
            organizer_token_usage["cached_tokens"] += int(prompt_details.get("cached_tokens") or 0)
        completion_details = usage.get("completion_tokens_details")
        if isinstance(completion_details, Mapping):
            organizer_token_usage["reasoning_tokens"] += int(completion_details.get("reasoning_tokens") or 0)
    try:
        structural = _codegraph_edges(root, evidence)
        document_edges = _document_reference_edges(root, evidence)
        payload = _organizer_payload(
            model_evidence=model_evidence,
            user_prompt=user_prompt,
            intent_flow=intent_flow,
            selected_min=selected_min,
            selected_max=selected_max,
            codegraph_edges=structural.get("direct_candidates", ()),
            document_reference_edges=document_edges,
        )
        response_format = _organizer_response_format(
            tuple(item.source_id for item in model_evidence),
            selected_min=selected_min,
            selected_max=selected_max,
        )
        response = complete_json(
            llm_config,
            (
                {"role": "system", "content": ORGANIZER_PROMPT_PATH.read_text(encoding="utf-8")},
                {"role": "user", "content": json.dumps(payload, sort_keys=True)},
            ),
            response_format=response_format,
            log_event=record_organizer_event,
        )
        repair_attempts = 0
        try:
            validated = _validate_organizer_response(
                response,
                evidence=evidence,
                model_evidence=model_evidence,
                selected_min=selected_min,
                selected_max=selected_max,
                codegraph_edges=payload["codegraph_edges"],
                document_reference_edges=document_edges,
            )
        except EvidenceOrganizationValidationError as exc:
            repair_attempts = 1
            repair_errors = _organizer_model_errors(exc.errors, model_evidence)
            if log_event is not None:
                log_event(
                    "evidence_organization_repair_attempted",
                    {"errors": list(exc.errors), "candidate_count": candidate_count},
                )
            repaired_payload = {
                **payload,
                "repair": {
                    "validation_errors": repair_errors,
                    "previous_response": dict(response),
                    "instruction": (
                        "Correct every validation error exactly. Return the complete organizer response, preserve "
                        "one assessment per candidate, and do not repeat the invalid response unchanged. When an "
                        "error names selected evidence outside the main flow, either add honest supported "
                        "connections that make those references reachable from root_ref or add every named "
                        "reference to disconnected_evidence with a specific reason."
                    ),
                },
            }
            repair_directive = (
                "REPAIR REQUIRED. The previous organizer response failed deterministic validation. "
                "Fix every error below and return the entire corrected JSON object. Do not return the previous "
                "response unchanged.\n\n- "
                + "\n- ".join(repair_errors)
            )
            repaired = complete_json(
                llm_config,
                (
                    {"role": "system", "content": ORGANIZER_PROMPT_PATH.read_text(encoding="utf-8")},
                    {"role": "user", "content": json.dumps(repaired_payload, sort_keys=True)},
                    {"role": "user", "content": repair_directive},
                ),
                response_format=response_format,
                log_event=record_organizer_event,
            )
            try:
                validated = _validate_organizer_response(
                    repaired,
                    evidence=evidence,
                    model_evidence=model_evidence,
                    selected_min=selected_min,
                    selected_max=selected_max,
                    codegraph_edges=payload["codegraph_edges"],
                    document_reference_edges=document_edges,
                )
            except EvidenceOrganizationValidationError as repaired_exc:
                raise EvidenceOrganizationError(
                    "Codex evidence organization failed after one repair attempt: " + "; ".join(repaired_exc.errors)
                ) from repaired_exc

        evidence_by_ref = {item.source_id: item for item in evidence}
        selected = tuple(
            replace(evidence_by_ref[ref], rank=index)
            for index, ref in enumerate(validated["selected_refs"], start=1)
        )
        excluded_refs = [item.source_id for item in evidence if item.source_id not in set(validated["selected_refs"])]
        graph = {
            "version": GRAPH_VERSION,
            "status": "complete",
            "connections": validated["connections"],
            # The selected graph remains the generation-facing graph. This
            # additional deterministic forest lets diagnostics render all
            # candidates without promoting excluded evidence into generation.
            "candidate_connections": validated["candidate_connections"],
            "root_ref": validated["root_ref"],
            "disconnected_evidence": validated["disconnected_evidence"],
            "generation": {
                "strategy": ORGANIZER_VERSION,
                "structural_provider": "codegraph",
                "semantic_provider": "llm",
                "codegraph_candidate_count": len(payload["codegraph_edges"]),
                "document_reference_count": len(document_edges),
                "repair_attempts": repair_attempts,
            },
        }
        organization = {
            "version": ORGANIZER_VERSION,
            "status": "complete",
            "candidate_count": candidate_count,
            "selected_count": len(selected),
            "excluded_count": len(excluded_refs),
            "coverage_facets": validated["coverage_facets"],
            "assessments": validated["assessments"],
            "selected_refs": validated["selected_refs"],
            "excluded_refs": excluded_refs,
            # Preserve the complete validated candidate set for diagnostics and UI
            # inspection. Explanation generation still receives only ``selected``.
            "candidate_evidence": [item.to_dict() for item in evidence],
            "candidate_order_mode": "prompt_seeded_stable_permutation" if neutralize_candidate_order else "codex_order",
            "model_candidate_order": [
                {
                    "candidate_id": f"c{index}",
                    "source_ref": item.source_id,
                    "original_position": next(
                        original_index
                        for original_index, original in enumerate(evidence, start=1)
                        if original.source_id == item.source_id
                    ),
                }
                for index, item in enumerate(model_evidence, start=1)
            ],
            "repair_attempts": repair_attempts,
            "graph_status": "complete",
            "token_usage": dict(organizer_token_usage),
        }
        summary = {
            **dict(retrieval_result.retrieval_summary),
            "candidate_count": candidate_count,
            "selected_count": len(selected),
            "evidence_organization": organization,
            "evidence_connections": graph,
        }
        if log_event is not None:
            log_event(
                "evidence_organization_completed",
                {
                    "candidate_count": candidate_count,
                    "selected_count": len(selected),
                    "excluded_count": len(excluded_refs),
                    "selected_refs": list(validated["selected_refs"]),
                    "excluded_refs": excluded_refs,
                    "coverage_facets": validated["coverage_facets"],
                    "assessments": validated["assessments"],
                    "graph_status": "complete",
                    "repair_attempts": repair_attempts,
                    "candidate_order_mode": "prompt_seeded_stable_permutation" if neutralize_candidate_order else "codex_order",
                    "model_candidate_order": [item.source_id for item in model_evidence],
                    "token_usage": dict(organizer_token_usage),
                },
            )
        return replace(retrieval_result, evidence=selected, retrieval_summary=summary, sufficient=bool(selected))
    except Exception as exc:
        if log_event is not None:
            log_event(
                "evidence_organization_failed",
                {
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                    "candidate_count": candidate_count,
                    "token_usage": dict(organizer_token_usage),
                },
            )
        if isinstance(exc, EvidenceOrganizationError):
            raise
        raise EvidenceOrganizationError(f"Codex evidence organization failed: {exc}") from exc


def _organizer_payload(
    *,
    model_evidence: Sequence[EvidenceItem],
    user_prompt: str,
    intent_flow: Mapping[str, Any],
    selected_min: int,
    selected_max: int,
    codegraph_edges: Any,
    document_reference_edges: Sequence[Mapping[str, str]],
) -> dict[str, Any]:
    structural = _semantic_payload(
        evidence=model_evidence,
        user_prompt=user_prompt,
        codegraph_edges=codegraph_edges,
        document_reference_edges=document_reference_edges,
        max_codegraph_edges=MAX_ORGANIZER_CODEGRAPH_EDGES,
    )
    return {
        "user_question": user_prompt[:6000],
        "intent_flow": dict(intent_flow),
        "selection_bounds": {"minimum": selected_min, "maximum": selected_max},
        "candidate_evidence": [
            {"candidate_id": f"c{index}", **_compact_organizer_evidence(item)}
            for index, item in enumerate(model_evidence, start=1)
        ],
        "codegraph_edges": structural["codegraph_edges"],
        "document_reference_edges": structural["document_reference_edges"],
    }


def _compact_organizer_evidence(item: EvidenceItem) -> dict[str, Any]:
    compact = _compact_evidence(item)
    compact["snippet"] = "\n".join(line[:160] for line in item.snippet.splitlines()[:18])
    return {
        **compact,
        "coverage_area_hint": str(item.metadata.get("coverage_area") or "")[:160],
        "artifact_kind": str(
            item.metadata.get("deterministic_artifact_kind") or item.metadata.get("artifact_kind") or "unknown"
        )[:100],
    }


def _stable_evidence_permutation(
    evidence: Sequence[EvidenceItem],
    *,
    user_prompt: str,
) -> tuple[EvidenceItem, ...]:
    """Return a reproducible order independent of Codex candidate rank."""

    prompt_key = hashlib.sha256(user_prompt.strip().encode("utf-8")).hexdigest()
    return tuple(
        sorted(
            evidence,
            key=lambda item: hashlib.sha256(
                f"{prompt_key}\0{item.source_id}".encode("utf-8")
            ).hexdigest(),
        )
    )


def _organizer_response_format(
    evidence_refs: Sequence[str],
    *,
    selected_min: int,
    selected_max: int,
) -> Mapping[str, Any]:
    schema = json.loads(ORGANIZER_SCHEMA_PATH.read_text(encoding="utf-8"))
    refs = list(evidence_refs)
    model_refs = [f"c{index}" for index in range(1, len(refs) + 1)]
    schema["properties"]["selected_refs"].update({"minItems": selected_min, "maxItems": selected_max})
    schema["properties"]["selected_refs"]["items"]["enum"] = model_refs
    schema["properties"]["root_ref"]["enum"] = model_refs
    assessment_item = schema.pop("$defs")["assessment"]
    schema["properties"]["assessments"] = {
        "type": "object",
        "properties": {ref: json.loads(json.dumps(assessment_item)) for ref in model_refs},
        "required": model_refs,
        "additionalProperties": False,
    }
    schema["properties"]["coverage_facets"]["items"]["properties"]["selected_refs"]["items"]["enum"] = model_refs
    connections = schema["properties"]["connections"]["items"]["properties"]
    connections["source_ref"]["enum"] = model_refs
    connections["target_ref"]["enum"] = model_refs
    schema["properties"]["disconnected_evidence"]["items"]["properties"]["evidence_ref"]["enum"] = model_refs
    return {
        "type": "json_schema",
        "json_schema": {"name": "codex_evidence_organizer", "strict": True, "schema": schema},
    }


def _validate_organizer_response(
    response: Mapping[str, Any],
    *,
    evidence: Sequence[EvidenceItem],
    model_evidence: Sequence[EvidenceItem],
    selected_min: int,
    selected_max: int,
    codegraph_edges: Sequence[Mapping[str, Any]],
    document_reference_edges: Sequence[Mapping[str, str]],
) -> dict[str, Any]:
    response = _expand_organizer_candidate_ids(response, model_evidence)
    valid_refs = {item.source_id for item in evidence}
    errors: list[str] = []
    selected_refs = _string_sequence(response.get("selected_refs"))
    if len(selected_refs) != len(set(selected_refs)):
        errors.append("selected_refs contains duplicates")
    if not selected_min <= len(selected_refs) <= selected_max:
        errors.append(f"selected_refs must contain between {selected_min} and {selected_max} items")
    if any(ref not in valid_refs for ref in selected_refs):
        errors.append("selected_refs contains an unknown evidence reference")
    selected_set = set(selected_refs)

    raw_facets = response.get("coverage_facets")
    facets = [dict(item) for item in raw_facets if isinstance(item, Mapping)] if isinstance(raw_facets, list) else []
    facet_ids = [str(item.get("id") or "").strip() for item in facets]
    if not facets or any(not item for item in facet_ids) or len(facet_ids) != len(set(facet_ids)):
        errors.append("coverage_facets must contain unique non-empty IDs")
    facet_id_set = set(facet_ids)
    for facet in facets:
        status = str(facet.get("status") or "")
        refs = _string_sequence(facet.get("selected_refs"))
        if len(refs) != len(set(refs)) or any(ref not in valid_refs for ref in refs):
            errors.append(f"facet {facet.get('id')} contains unknown or duplicate evidence references")
        selected_support = tuple(ref for ref in refs if ref in selected_set)
        facet["selected_refs"] = list(selected_support)
        if status in {"covered", "partial"} and not selected_support:
            errors.append(f"facet {facet.get('id')} is {status} without selected support")
        if status in {"missing", "unclear"} and refs:
            errors.append(f"facet {facet.get('id')} is {status} but names selected support")

    raw_assessments = response.get("assessments")
    if isinstance(raw_assessments, Mapping):
        assessments = [
            {"evidence_ref": str(ref), **dict(value)}
            for ref, value in raw_assessments.items()
            if isinstance(value, Mapping)
        ]
    elif isinstance(raw_assessments, list):
        assessments = [dict(item) for item in raw_assessments if isinstance(item, Mapping)]
    else:
        assessments = []
    assessment_refs = [str(item.get("evidence_ref") or "").strip() for item in assessments]
    if len(assessments) != len(evidence) or set(assessment_refs) != valid_refs or len(assessment_refs) != len(set(assessment_refs)):
        errors.append("assessments must cover every candidate reference exactly once")
    for assessment in assessments:
        ref = str(assessment.get("evidence_ref") or "").strip()
        status = str(assessment.get("status") or "").strip()
        assigned_facets = _string_sequence(assessment.get("facet_ids"))
        if any(facet_id not in facet_id_set for facet_id in assigned_facets):
            errors.append(f"assessment {ref} names an unknown facet")
        if ref in selected_set and status not in {"core", "supporting"}:
            errors.append(f"selected assessment {ref} must be core or supporting")
        if ref in selected_set and status == "core" and not assigned_facets:
            errors.append(f"core assessment {ref} must support at least one facet")

    root_ref = str(response.get("root_ref") or "").strip()
    if root_ref not in selected_set:
        errors.append("root_ref must be selected")
    selected_evidence = tuple(item for item in evidence if item.source_id in selected_set)
    try:
        semantic_connections = _validated_connections(
            response.get("connections"),
            evidence=evidence,
            document_reference_edges=document_reference_edges,
            require_nonempty=False,
        )
    except RuntimeError as exc:
        errors.append(str(exc))
        semantic_connections = []
    structural_connections = _structural_connections(
        codegraph_edges=codegraph_edges,
        document_reference_edges=document_reference_edges,
    )
    candidate_connections = _unique_connection_pairs([*structural_connections, *semantic_connections])
    combined = [
        connection
        for connection in (*structural_connections, *semantic_connections)
        if connection["source_ref"] in selected_set and connection["target_ref"] in selected_set
    ]
    connections = _minimal_connection_forest(combined)
    coverage_response = {
        "root_ref": root_ref,
        "disconnected_evidence": response.get("disconnected_evidence"),
    }
    try:
        _, disconnected, _ = _graph_coverage(
            coverage_response,
            connections=connections,
            evidence=selected_evidence,
            infer_unaccounted=True,
        )
    except RuntimeError as exc:
        errors.append(str(exc))
        disconnected = []
    if errors:
        raise EvidenceOrganizationValidationError(errors)
    return {
        "coverage_facets": facets,
        "assessments": assessments,
        "selected_refs": list(selected_refs),
        "root_ref": root_ref,
        "connections": connections,
        "candidate_connections": candidate_connections,
        "disconnected_evidence": disconnected,
    }


def _string_sequence(value: Any) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())


def _expand_organizer_candidate_ids(
    response: Mapping[str, Any], evidence: Sequence[EvidenceItem]
) -> dict[str, Any]:
    id_to_ref = {f"c{index}": item.source_id for index, item in enumerate(evidence, start=1)}

    def expand(value: Any) -> str:
        text = str(value or "").strip()
        return id_to_ref.get(text, text)

    normalized = dict(response)
    normalized["selected_refs"] = [expand(item) for item in _string_sequence(response.get("selected_refs"))]
    normalized["root_ref"] = expand(response.get("root_ref"))
    raw_facets = response.get("coverage_facets")
    if isinstance(raw_facets, list):
        normalized["coverage_facets"] = [
            {
                **dict(item),
                "selected_refs": [expand(ref) for ref in _string_sequence(item.get("selected_refs"))],
            }
            for item in raw_facets
            if isinstance(item, Mapping)
        ]
    raw_assessments = response.get("assessments")
    if isinstance(raw_assessments, Mapping):
        normalized["assessments"] = {expand(ref): dict(value) for ref, value in raw_assessments.items()}
    elif isinstance(raw_assessments, list):
        normalized["assessments"] = [
            {**dict(item), "evidence_ref": expand(item.get("evidence_ref"))}
            for item in raw_assessments
            if isinstance(item, Mapping)
        ]
    raw_connections = response.get("connections")
    if isinstance(raw_connections, list):
        normalized["connections"] = [
            {**dict(item), "source_ref": expand(item.get("source_ref")), "target_ref": expand(item.get("target_ref"))}
            for item in raw_connections
            if isinstance(item, Mapping)
        ]
    raw_disconnected = response.get("disconnected_evidence")
    if isinstance(raw_disconnected, list):
        normalized["disconnected_evidence"] = [
            {**dict(item), "evidence_ref": expand(item.get("evidence_ref"))}
            for item in raw_disconnected
            if isinstance(item, Mapping)
        ]
    return normalized


def _organizer_model_errors(errors: Sequence[str], evidence: Sequence[EvidenceItem]) -> list[str]:
    output = list(errors)
    for index, item in enumerate(evidence, start=1):
        output = [error.replace(item.source_id, f"c{index}") for error in output]
    return output


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
    max_codegraph_edges: int = MAX_CODEGRAPH_EDGES,
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
            if len(compact_edges) >= max_codegraph_edges:
                break
    return {
        "user_question": user_prompt[:6000],
        "selected_evidence": [_compact_evidence(item) for item in evidence],
        "codegraph_edges": compact_edges,
        "document_reference_edges": [dict(item) for item in document_reference_edges],
    }


def _document_reference_edges(workspace_root: Path, evidence: Sequence[EvidenceItem]) -> list[dict[str, str]]:
    documents = [item for item in evidence if Path(_evidence_path(item)).suffix.lower() in RESOURCE_EXTENSIONS]
    if not documents:
        return []
    output: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for source_item in evidence:
        source_path = _evidence_path(source_item)
        if Path(source_path).suffix.lower() in RESOURCE_EXTENSIONS:
            continue
        for document_item in documents:
            reference = resource_reference_between_files(
                workspace_root,
                source_path,
                _evidence_path(document_item),
            )
            if reference is None:
                continue
            key = (source_item.source_id, document_item.source_id)
            if key in seen:
                continue
            seen.add(key)
            output.append(
                {
                    "source_ref": source_item.source_id,
                    "target_ref": document_item.source_id,
                    "relationship": "resource_reference",
                    "resource_literal": str(reference.get("literal") or "resource path literal"),
                    "document": Path(_evidence_path(document_item)).name,
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
    require_nonempty: bool = True,
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
    if require_nonempty and not accepted:
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
        resource_literal = str(edge.get("resource_literal") or "the selected resource literal")
        document = str(edge.get("document") or "the selected document")
        connections.append(
            {
                "source_ref": str(edge.get("source_ref") or ""),
                "target_ref": str(edge.get("target_ref") or ""),
                "relationship_kind": "configuration",
                "label": f"loads {document}"[:100],
                "description": f"The selected code references {document} through {resource_literal}."[:500],
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
    infer_unaccounted: bool = False,
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
        if not infer_unaccounted:
            raise RuntimeError(
                "Evidence graph model left selected evidence outside the main flow without a disconnected reason: "
                + ", ".join(sorted(unaccounted))
            )
        for evidence_ref in sorted(unaccounted):
            disconnected.append(
                {
                    "evidence_ref": evidence_ref,
                    "reason": "No accepted CodeGraph or semantic edge connects this evidence to the main component.",
                }
            )
            disconnected_refs.add(evidence_ref)
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


def _unique_connection_pairs(connections: Sequence[dict[str, str]]) -> list[dict[str, str]]:
    """Keep every distinct relationship pair, preferring earlier grounding."""
    accepted: list[dict[str, str]] = []
    seen: set[frozenset[str]] = set()
    for connection in connections:
        source_ref = str(connection.get("source_ref") or "")
        target_ref = str(connection.get("target_ref") or "")
        if not source_ref or not target_ref or source_ref == target_ref:
            continue
        pair = frozenset((source_ref, target_ref))
        if pair in seen:
            continue
        seen.add(pair)
        accepted.append(dict(connection))
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
