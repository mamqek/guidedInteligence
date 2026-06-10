from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Mapping, Sequence


_TEMPERATURE_DISABLED_MODELS: set[tuple[str, str]] = set()
_CONTINUITY_STATE: dict[tuple[str, str], str] = {}


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
    effective_messages = _messages_with_continuity(config, messages)
    payload = _request_payload(config, effective_messages, response_format=response_format)

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
            response_data = _attempt(_request_payload(config, effective_messages, response_format=response_format))
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
        parsed = _parse_json_object(content_text)
        _store_continuity_response(config, parsed)
        return parsed
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


def parse_json_object(content: str) -> Mapping[str, Any]:
    return _parse_json_object(content)


def reset_runtime_state() -> None:
    _TEMPERATURE_DISABLED_MODELS.clear()
    _CONTINUITY_STATE.clear()


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


def _messages_with_continuity(config: Any, messages: Sequence[Mapping[str, str]]) -> Sequence[Mapping[str, str]]:
    if not bool(getattr(config, "continuity_enabled", False)):
        return messages
    previous = _CONTINUITY_STATE.get(_temperature_cache_key(config))
    if not previous:
        return messages
    continuity_message = {
        "role": "system",
        "content": (
            "Experimental retrieval continuity is enabled. "
            "Use this compact previous JSON result only as process-local orientation; do not treat it as evidence.\n"
            f"{previous}"
        ),
    }
    return (continuity_message, *messages)


def _store_continuity_response(config: Any, response: Mapping[str, Any]) -> None:
    if not bool(getattr(config, "continuity_enabled", False)):
        return
    compact = json.dumps(_compact_continuity_response(response), sort_keys=True)
    _CONTINUITY_STATE[_temperature_cache_key(config)] = compact[:2000]


def _compact_continuity_response(response: Mapping[str, Any]) -> Mapping[str, Any]:
    keep_keys = (
        "prompt_summary",
        "retrieval_terms",
        "required_roles",
        "supporting_roles",
        "llm_subqueries",
        "accepted_anchor_refs",
        "rejected_anchor_refs",
        "missing_areas",
        "follow_up_queries",
        "snippet_assessment",
        "stop_reason",
    )
    compact: dict[str, Any] = {}
    for key in keep_keys:
        if key in response:
            compact[key] = response[key]
    return compact


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
