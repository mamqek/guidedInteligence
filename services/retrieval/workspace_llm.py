from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Mapping, Sequence

from services.retrieval.step2.common import bounded_strings, looks_like_absolute_path
from services.retrieval.tools.local import file_role as tool_file_role


_TEMPERATURE_DISABLED_MODELS: set[tuple[str, str]] = set()


def complete_json(
    config: Any,
    messages: Sequence[Mapping[str, str]],
    *,
    response_format: Mapping[str, Any] | None = None,
    log_warning: Callable[[Mapping[str, Any]], None] | None = None,
    log_event: Callable[[str, Mapping[str, Any]], None] | None = None,
) -> Mapping[str, Any]:
    api_key = str(config.api_key).strip()
    if not api_key:
        raise ValueError("Missing LLM API key in config.")
    payload = _request_payload(config, messages, response_format=response_format)

    def _attempt(request_payload: Mapping[str, Any]) -> Mapping[str, Any]:
        started_at = time.perf_counter()
        if log_event is not None:
            log_event(
                "llm_request_sent",
                {
                    "model": config.model,
                    "endpoint_url": config.endpoint_url,
                    "request_payload": dict(request_payload),
                },
            )
        try:
            response_data = _perform_request(config, api_key, request_payload)
        except urllib.error.HTTPError as exc:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 3)
            error_body = exc.read().decode("utf-8", errors="replace")
            if log_event is not None:
                log_event(
                    "llm_request_failed",
                    {
                        "model": config.model,
                        "endpoint_url": config.endpoint_url,
                        "duration_ms": duration_ms,
                        "status_code": exc.code,
                        "error_type": "HTTPError",
                        "request_payload": dict(request_payload),
                        "error_body": error_body,
                    },
                )
            raise _LoggedHTTPError(exc, error_body) from exc
        except urllib.error.URLError as exc:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 3)
            if log_event is not None:
                log_event(
                    "llm_request_failed",
                    {
                        "model": config.model,
                        "endpoint_url": config.endpoint_url,
                        "duration_ms": duration_ms,
                        "error_type": type(exc).__name__,
                        "request_payload": dict(request_payload),
                        "error": str(exc),
                    },
                )
            raise RuntimeError(f"LLM request failed: {exc}") from exc
        except TimeoutError as exc:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 3)
            if log_event is not None:
                log_event(
                    "llm_request_failed",
                    {
                        "model": config.model,
                        "endpoint_url": config.endpoint_url,
                        "duration_ms": duration_ms,
                        "error_type": type(exc).__name__,
                        "request_payload": dict(request_payload),
                        "error": str(exc),
                    },
                )
            raise RuntimeError(f"LLM request failed: {exc}") from exc
        duration_ms = round((time.perf_counter() - started_at) * 1000, 3)
        if log_event is not None:
            log_event(
                "llm_response_received",
                {
                    "model": config.model,
                    "endpoint_url": config.endpoint_url,
                    "duration_ms": duration_ms,
                    "request_payload": dict(request_payload),
                    "raw_response": response_data,
                },
            )
        return response_data

    try:
        response_data = _attempt(payload)
    except _LoggedHTTPError as exc:
        if _is_temperature_unsupported_error(exc.status_code, exc.error_body) and "temperature" in payload:
            key = _temperature_cache_key(config)
            first_disable = key not in _TEMPERATURE_DISABLED_MODELS
            _TEMPERATURE_DISABLED_MODELS.add(key)
            if first_disable and log_warning is not None:
                log_warning(
                    {
                        "warning_type": "temperature_unsupported",
                        "model": config.model,
                        "endpoint_url": config.endpoint_url,
                        "message": "temperature parameter rejected by model; retrying without temperature for the rest of the run",
                    }
                )
            response_data = _attempt(_request_payload(config, messages, response_format=response_format))
        else:
            raise RuntimeError(f"LLM request failed: HTTP {exc.status_code}: {exc.error_body}") from exc

    try:
        content = response_data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        if log_warning is not None:
            log_warning(
                {
                    "warning_type": "llm_response_shape_unexpected",
                    "model": config.model,
                    "endpoint_url": config.endpoint_url,
                    "raw_response": _raw_json_text(response_data),
                    "message": "LLM response was missing choices[0].message.content",
                }
            )
        raise RuntimeError("LLM response missing choices[0].message.content") from exc
    content_text = str(content)
    try:
        return _parse_json_object(content_text)
    except RuntimeError:
        if log_warning is not None:
            log_warning(
                {
                    "warning_type": "llm_response_not_json",
                    "model": config.model,
                    "endpoint_url": config.endpoint_url,
                    "raw_response": _raw_json_text(response_data),
                    "message": "LLM response content was not valid JSON",
                }
            )
        raise


def assess_role_buckets_with_llm(
    *,
    intent: Any,
    role_buckets: Sequence[Mapping[str, Any]],
    current_snippets: Sequence[Mapping[str, Any]],
    missing_roles: Sequence[str],
    llm_config: Any,
    log_warning: Callable[[Mapping[str, Any]], None] | None = None,
    log_event: Callable[[str, Mapping[str, Any]], None] | None = None,
) -> Mapping[str, Any]:
    payload = {
        "intent": intent.to_dict(),
        "role_buckets": [_compact_role_bucket(bucket) for bucket in role_buckets],
        "current_snippets": [dict(snippet) for snippet in current_snippets],
        "missing_roles": list(missing_roles),
    }
    messages = (
        {
            "role": "system",
            "content": (
                "You are a late-stage retrieval assessor for code explanation. "
                "You receive role-grouped evidence that has already been retrieved and validated. "
                "Do not plan broad repo exploration. Decide only whether the current evidence is sufficient to explain "
                "the issue, which required roles remain missing, which accepted anchors are core or secondary, and which "
                "anchors are likely noise. Suggest follow-up searches only when absolutely necessary, and keep them "
                "role-scoped and specific. "
                "Return JSON with keys: acceptance_satisfied, stop_reason, missing_areas, accepted_anchor_refs, "
                "rejected_anchor_refs, snippet_assessment, follow_up_queries. "
                "snippet_assessment items must contain ref, role, and reason. follow_up_queries items must contain "
                "role, query, and reason."
            ),
        },
        {"role": "user", "content": json.dumps(payload, sort_keys=True)},
    )
    return validate_role_bucket_assessment(
        complete_json(
            llm_config,
            messages,
            response_format=_role_bucket_response_format(),
            log_warning=log_warning,
            log_event=log_event,
        )
    )


def validate_role_bucket_assessment(response: Mapping[str, Any]) -> Mapping[str, Any]:
    snippet_assessment: list[dict[str, str]] = []
    for item in response.get("snippet_assessment", ()):
        if not isinstance(item, Mapping):
            continue
        ref = str(item.get("ref", "")).strip()
        role = str(item.get("role", "")).strip().lower()
        reason = str(item.get("reason", "")).strip()
        if not ref or role not in {"core", "secondary", "noise"}:
            continue
        snippet_assessment.append({"ref": ref, "role": role, "reason": reason})
        if len(snippet_assessment) >= 12:
            break

    follow_up_queries: list[dict[str, str]] = []
    for item in response.get("follow_up_queries", ()):
        if not isinstance(item, Mapping):
            continue
        role = str(item.get("role", "")).strip()
        query = str(item.get("query", "")).strip()
        reason = str(item.get("reason", "")).strip()
        if not role or not query:
            continue
        follow_up_queries.append({"role": role, "query": query, "reason": reason})
        if len(follow_up_queries) >= 4:
            break

    return {
        "acceptance_satisfied": bool(response.get("acceptance_satisfied", False)),
        "stop_reason": str(response.get("stop_reason", "")).strip(),
        "missing_areas": list(bounded_strings(response.get("missing_areas"), limit=8)),
        "accepted_anchor_refs": list(bounded_strings(response.get("accepted_anchor_refs"), limit=16)),
        "rejected_anchor_refs": list(bounded_strings(response.get("rejected_anchor_refs"), limit=16)),
        "snippet_assessment": snippet_assessment,
        "follow_up_queries": follow_up_queries,
    }


def compact_observation(observation: Any) -> dict[str, Any]:
    payload = dict(observation.payload)
    compact: dict[str, Any] = {
        "tool_name": observation.tool_name,
        "status": observation.status,
        "metadata": dict(observation.metadata),
        "source_refs": list(observation.source_refs),
    }
    if "files" in payload and isinstance(payload["files"], list):
        compact["files"] = _compact_file_entries(payload["files"], limit=8)
    if "results" in payload and isinstance(payload["results"], list):
        compact["results"] = _compact_chunk_entries(payload["results"], limit=4)
    if "snippets" in payload and isinstance(payload["snippets"], list):
        compact["snippets"] = _compact_chunk_entries(payload["snippets"], limit=2)
    if "reason" in payload:
        compact["reason"] = payload["reason"]
    return compact


def _compact_role_bucket(bucket: Mapping[str, Any]) -> dict[str, Any]:
    compact = {
        "role": str(bucket.get("role", "")),
        "query": str(bucket.get("query", "")),
        "helper_queries": list(bucket.get("helper_queries", ()))[:4],
        "accepted_refs": list(bucket.get("accepted_refs", ()))[:8],
        "rejected_refs": list(bucket.get("rejected_refs", ()))[:8],
        "missing_reason": str(bucket.get("missing_reason", "")),
        "validation_notes": list(bucket.get("validation_notes", ()))[:6],
        "snippets": [],
    }
    for snippet in bucket.get("snippets", ())[:4]:
        if isinstance(snippet, Mapping):
            compact["snippets"].append(
                {
                    "ref": str(snippet.get("ref", "")),
                    "path": str(snippet.get("path", "")),
                    "line_range": str(snippet.get("line_range", "")),
                    "file_role": str(snippet.get("file_role", "")),
                    "snippet": str(snippet.get("snippet", ""))[:500],
                }
            )
    return compact


def _compact_file_entries(items: Sequence[Mapping[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    preferred = [dict(item) for item in items if _is_llm_prompt_path_allowed(str(item.get("path", "")))]
    selected = preferred or [dict(item) for item in items]
    return selected[:limit]


def _compact_chunk_entries(items: Sequence[Mapping[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    preferred = [item for item in items if _is_llm_prompt_path_allowed(str(item.get("path", "")))]
    selected = preferred or list(items)
    compacted: list[dict[str, Any]] = []
    for item in selected[:limit]:
        entry = dict(item)
        if "text" in entry:
            entry["text"] = str(entry["text"])[:500]
        compacted.append(entry)
    return compacted


def _is_llm_prompt_path_allowed(path: str) -> bool:
    return tool_file_role(path) in {"implementation", "documentation"}


def message_to_dict(message: Any) -> dict[str, Any]:
    return {"role": message.role, "content": message.content, "stage": message.stage.value if message.stage is not None else None}


def _parse_json_object(content: str) -> Mapping[str, Any]:
    try:
        value = json.loads(content)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"LLM response was not valid JSON: {exc}") from exc
    if not isinstance(value, Mapping):
        raise RuntimeError("LLM response must be a JSON object.")
    return value


def _max_tokens_parameter(model: str) -> str:
    if model.startswith("gpt-5") or model.startswith("o"):
        return "max_completion_tokens"
    return "max_tokens"


def _temperature_cache_key(config: Any) -> tuple[str, str]:
    return (config.endpoint_url.rstrip("/"), str(config.model))


def _request_payload(
    config: Any,
    messages: Sequence[Mapping[str, str]],
    *,
    response_format: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "model": config.model,
        "messages": list(messages),
        "response_format": dict(response_format or {"type": "json_object"}),
    }
    if _temperature_cache_key(config) not in _TEMPERATURE_DISABLED_MODELS:
        payload["temperature"] = config.temperature
    payload[_max_tokens_parameter(config.model)] = config.max_tokens
    return payload


def _perform_request(config: Any, api_key: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
    request = urllib.request.Request(
        config.endpoint_url,
        data=json.dumps(dict(payload)).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=config.timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def _is_temperature_unsupported_error(status_code: int, error_body: str) -> bool:
    if status_code != 400:
        return False
    normalized = error_body.lower()
    return "temperature" in normalized and "unsupported" in normalized


def _raw_json_text(value: Mapping[str, Any]) -> str:
    try:
        return json.dumps(value, sort_keys=True)
    except TypeError:
        return str(value)


class _LoggedHTTPError(RuntimeError):
    def __init__(self, exc: urllib.error.HTTPError, error_body: str) -> None:
        super().__init__(str(exc))
        self.status_code = exc.code
        self.error_body = error_body


def _role_bucket_response_format() -> Mapping[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "workspace_retrieval_role_bucket_assessment",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "acceptance_satisfied": {"type": "boolean"},
                    "stop_reason": {"type": "string"},
                    "missing_areas": {"type": "array", "items": {"type": "string"}},
                    "accepted_anchor_refs": {"type": "array", "items": {"type": "string"}},
                    "rejected_anchor_refs": {"type": "array", "items": {"type": "string"}},
                    "snippet_assessment": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "ref": {"type": "string"},
                                "role": {"type": "string", "enum": ["core", "secondary", "noise"]},
                                "reason": {"type": "string"},
                            },
                            "required": ["ref", "role", "reason"],
                            "additionalProperties": False,
                        },
                    },
                    "follow_up_queries": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "role": {"type": "string"},
                                "query": {"type": "string"},
                                "reason": {"type": "string"},
                            },
                            "required": ["role", "query", "reason"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": [
                    "acceptance_satisfied",
                    "stop_reason",
                    "missing_areas",
                    "accepted_anchor_refs",
                    "rejected_anchor_refs",
                    "snippet_assessment",
                    "follow_up_queries",
                ],
                "additionalProperties": False,
            },
        },
    }
