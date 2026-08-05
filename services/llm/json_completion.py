from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
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
    if str(getattr(config, "api_style", "")).strip() == "codex_cli":
        return _complete_json_with_codex_cli(
            config,
            messages,
            response_format=response_format,
            log_event=log_event,
        )

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


def _complete_json_with_codex_cli(
    config: Any,
    messages: Sequence[Mapping[str, str]],
    *,
    response_format: Mapping[str, Any] | None,
    log_event: Callable[[str, Mapping[str, Any]], None] | None,
) -> Mapping[str, Any]:
    effective_messages = _messages_with_continuity(config, messages)
    schema = _codex_output_schema(response_format)
    prompt = _codex_prompt_from_messages(effective_messages)
    model = str(getattr(config, "model", "")).strip()
    if not model:
        raise ValueError("Codex CLI LLM config requires model.")
    command_prefix = tuple(str(part) for part in getattr(config, "codex_command", ("codex",)) if str(part).strip())
    if not command_prefix:
        raise ValueError("Codex CLI LLM config requires codex_command.")

    with tempfile.TemporaryDirectory(prefix="guided-llm-codex-") as temp_dir:
        temp_path = Path(temp_dir)
        schema_path = temp_path / "response.schema.json"
        output_path = temp_path / "response.json"
        schema_path.write_text(json.dumps(schema, indent=2, sort_keys=True), encoding="utf-8")
        command = [
            *command_prefix,
            "--disable",
            "plugins",
            "-a",
            "never",
            "-c",
            'web_search="disabled"',
            "exec",
            "--json",
            "--ephemeral",
            "--sandbox",
            "read-only",
            "--ignore-rules",
            "--model",
            model,
            "--output-schema",
            str(schema_path),
            "-o",
            str(output_path),
            prompt,
        ]
        if bool(getattr(config, "codex_ignore_user_config", True)):
            command.insert(command.index("--sandbox"), "--ignore-user-config")
        started_at = time.perf_counter()
        if log_event is not None:
            log_event(
                "llm_request_sent",
                {
                    "model": model,
                    "endpoint_url": "codex_cli",
                    "request_payload": {
                        "messages": [dict(message) for message in effective_messages],
                        "response_format": dict(response_format or {"type": "json_object"}),
                        "command": list(command_prefix),
                    },
                },
            )
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=_codex_subprocess_env(command_prefix),
                timeout=int(getattr(config, "timeout_seconds", 30)),
                check=False,
            )
        except FileNotFoundError as exc:
            _log_codex_failure(log_event, config, started_at, "FileNotFoundError", str(exc), command_prefix)
            raise RuntimeError("Codex CLI LLM request failed: codex command was not found.") from exc
        except subprocess.TimeoutExpired as exc:
            _log_codex_failure(log_event, config, started_at, "TimeoutExpired", str(exc), command_prefix)
            raise RuntimeError(f"Codex CLI LLM request timed out after {getattr(config, 'timeout_seconds', 30)} seconds.") from exc
        duration_ms = round((time.perf_counter() - started_at) * 1000, 3)
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()[:1200]
            if log_event is not None:
                log_event(
                    "llm_request_failed",
                    {
                        "model": model,
                        "endpoint_url": "codex_cli",
                        "duration_ms": duration_ms,
                        "error_type": "CodexCLIError",
                        "returncode": completed.returncode,
                        "stdout": completed.stdout,
                        "stderr": completed.stderr,
                    },
                )
            raise RuntimeError(f"Codex CLI LLM request failed with exit code {completed.returncode}: {detail}")
        try:
            parsed = _parse_json_object(output_path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise RuntimeError("Codex CLI LLM request did not write a JSON output file.") from exc
        _store_continuity_response(config, parsed)
        if log_event is not None:
            log_event(
                "llm_response_received",
                {
                    "model": model,
                    "endpoint_url": "codex_cli",
                    "duration_ms": duration_ms,
                    "request_payload": {
                        "messages": [dict(message) for message in effective_messages],
                        "response_format": dict(response_format or {"type": "json_object"}),
                        "command": list(command_prefix),
                    },
                    "raw_response": {
                        "content": parsed,
                        "stdout": completed.stdout,
                        "stderr": completed.stderr,
                    },
                },
            )
        return parsed


def _codex_output_schema(response_format: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not response_format:
        return {"type": "object", "additionalProperties": True}
    if response_format.get("type") == "json_schema":
        json_schema = response_format.get("json_schema")
        if isinstance(json_schema, Mapping) and isinstance(json_schema.get("schema"), Mapping):
            return dict(json_schema["schema"])
    return {"type": "object", "additionalProperties": True}


def _codex_prompt_from_messages(messages: Sequence[Mapping[str, str]]) -> str:
    sections: list[str] = [
        "Return only the JSON object requested by the provided output schema.",
        "Conversation messages:",
    ]
    for message in messages:
        role = str(message.get("role") or "user").strip() or "user"
        content = str(message.get("content") or "")
        sections.append(f"\n[{role}]\n{content}")
    return "\n".join(sections)


def _log_codex_failure(
    log_event: Callable[[str, Mapping[str, Any]], None] | None,
    config: Any,
    started_at: float,
    error_type: str,
    error: str,
    command_prefix: Sequence[str],
) -> None:
    if log_event is None:
        return
    log_event(
        "llm_request_failed",
        {
            "model": getattr(config, "model", ""),
            "endpoint_url": "codex_cli",
            "duration_ms": round((time.perf_counter() - started_at) * 1000, 3),
            "error_type": error_type,
            "error": error,
            "request_payload": {"command": list(command_prefix)},
        },
    )


def _codex_subprocess_env(command: Sequence[str]) -> dict[str, str]:
    env = dict(os.environ)
    if os.name != "nt":
        return env
    path_parts = _codex_path_prefixes(command)
    if not path_parts:
        return env
    existing_path = env.get("PATH") or env.get("Path") or ""
    path_key = "Path" if "Path" in env else "PATH"
    env[path_key] = os.pathsep.join((*path_parts, existing_path))
    return env


def _codex_path_prefixes(command: Sequence[str]) -> tuple[str, ...]:
    candidates: list[Path] = []
    repo_root = Path(__file__).resolve().parents[2]
    candidates.append(repo_root / ".venv" / "Scripts")
    if command:
        command_path = Path(str(command[0]))
        if command_path.is_file():
            candidates.append(command_path.parent)
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        codex_bin = Path(local_app_data) / "OpenAI" / "Codex" / "bin"
        if codex_bin.is_dir():
            candidates.extend(
                path
                for path in sorted(codex_bin.iterdir(), key=lambda path: path.stat().st_mtime, reverse=True)
                if path.is_dir() and (path / "codex-windows-sandbox-setup.exe").is_file()
            )
    plugin_helper_dir = Path.home() / ".codex" / "plugins" / ".plugin-appserver"
    candidates.append(plugin_helper_dir)
    seen: set[str] = set()
    resolved: list[str] = []
    for candidate in candidates:
        if not candidate.is_dir():
            continue
        value = str(candidate)
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        resolved.append(value)
    return tuple(resolved)


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
