from __future__ import annotations

import argparse
import json
import re
import socket
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qs, urlparse

from core.control_layer import ControlLayer
from core.models import ConversationState, UserIntent
from core.policy import PolicyStage
from core.source_policy import DEFAULT_ALLOWED_SOURCE_CATEGORIES, SourceCategory, SourcePolicy
from services.logging.store import JsonlLogger
from services.retrieval.config import (
    MCPConnectedSourceConfig,
    WorkspaceRetrievalConfig,
    load_retrieval_embedding_config,
    load_retrieval_enable_indexing,
    load_retrieval_llm_config,
    load_retrieval_qdrant_config,
    source_categories_from_strings,
)
from services.retrieval.mcp import MCPConnectedSourceAdapter, MCPConnectedSourceError
from services.retrieval.workspace import WorkspaceRetrievalStage


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8790
CONFIG_DIR_NAME = ".guided-intelligence"
CONFIG_FILE_NAME = "config.json"
RUNS_DIR_NAME = "runs"


class RetrievalServerError(RuntimeError):
    def __init__(self, message: str, *, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


class RuntimeState:
    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root.resolve()
        self.config_path = self.workspace_root / CONFIG_DIR_NAME / CONFIG_FILE_NAME
        self.config = self._load_or_default_config()

    @property
    def runs_root(self) -> Path:
        configured = str(self.config.get("runs_dir") or "").strip()
        if configured:
            path = Path(configured)
            return path if path.is_absolute() else self.workspace_root / path
        return self.workspace_root / CONFIG_DIR_NAME / RUNS_DIR_NAME

    def public_health(self) -> dict[str, Any]:
        env_path = self.workspace_root / ".env"
        return {
            "status": "ok",
            "workspace_root": str(self.workspace_root),
            "config_path": str(self.config_path),
            "config_exists": self.config_path.exists(),
            "env_exists": env_path.exists(),
            "qdrant_configured": _config_loader_ok(load_retrieval_qdrant_config, self.workspace_root),
            "llm_configured": _config_loader_ok(load_retrieval_llm_config, self.workspace_root),
            "embedding_configured": _config_loader_ok(load_retrieval_embedding_config, self.workspace_root),
            "runs_dir": str(self.runs_root),
        }

    def get_config(self) -> dict[str, Any]:
        return _deepcopy_json(self.config)

    def update_config(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, Mapping):
            raise RetrievalServerError("Config payload must be an object.")
        updated = _merge_config(self._default_config(), dict(payload))
        _validate_config(updated)
        self.config = updated
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps(updated, indent=2, sort_keys=True), encoding="utf-8")
        return self.get_config()

    def test_connection(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        source = _mcp_config_from_mapping(payload)
        adapter = MCPConnectedSourceAdapter(source)
        query = str(payload.get("test_query") or "test").strip() or "test"
        try:
            documents = adapter.search(query)
        except MCPConnectedSourceError as exc:
            return {
                "ok": False,
                "name": source.name,
                "source_category": source.source_category.value,
                "error": str(exc),
            }
        return {
            "ok": True,
            "name": source.name,
            "source_category": source.source_category.value,
            "result_count": len(documents),
            "documents": [document.to_dict() for document in documents],
        }

    def run_retrieval(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        prompt = str(payload.get("prompt") or "").strip()
        if not prompt:
            raise RetrievalServerError("`prompt` is required.")
        allowed_sources = _allowed_sources_from_payload(payload, self.config)
        run_id = _safe_run_id(str(payload.get("run_id") or ""))
        if not run_id:
            run_id = f"run-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
        run_dir = self.runs_root / run_id
        run_dir.mkdir(parents=True, exist_ok=False)

        llm_config = load_retrieval_llm_config(self.workspace_root / ".env")
        retrieval_stage = WorkspaceRetrievalStage(
            WorkspaceRetrievalConfig(
                workspace_root=str(self.workspace_root),
                index_dir=str(self.workspace_root / CONFIG_DIR_NAME / "index"),
                run_dir=str(run_dir),
                llm_config=llm_config,
                embedding_config=load_retrieval_embedding_config(self.workspace_root / ".env"),
                qdrant_config=load_retrieval_qdrant_config(self.workspace_root / ".env"),
                enable_indexing=load_retrieval_enable_indexing(self.workspace_root / ".env"),
                enabled_source_categories=tuple(allowed_sources),
                mcp_connected_sources=_configured_mcp_sources(self.config),
            )
        )
        policy = PolicyStage(SourcePolicy(allowed_categories=tuple(allowed_sources), policy_name="local_web_ui"))
        control = ControlLayer(
            policy_stage=policy,
            retrieval_stage=retrieval_stage,
            logger=JsonlLogger(run_dir / "orchestration-trace.jsonl"),
            response_llm_config=llm_config,
        )
        state = ConversationState(
            conversation_id=run_id,
            user_input=prompt,
            intent=UserIntent.UNDERSTAND_CODE,
        )
        result = control.run(state)
        result_payload = result.to_dict()
        (run_dir / "orchestration-result.json").write_text(
            json.dumps(result_payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        evidence = result.retrieval_result.evidence if result.retrieval_result is not None else ()
        (run_dir / "evidence-items.json").write_text(
            json.dumps([item.to_dict() for item in evidence], indent=2, sort_keys=True),
            encoding="utf-8",
        )
        metadata = {
            "run_id": run_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "workspace_root": str(self.workspace_root),
            "prompt": prompt,
            "allowed_sources": [source.value for source in allowed_sources],
            "run_dir": str(run_dir),
        }
        (run_dir / "run-metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
        return _run_summary_from_payload(run_id, run_dir, result_payload)

    def list_runs(self) -> list[dict[str, Any]]:
        runs_root = self.runs_root
        if not runs_root.exists():
            return []
        summaries: list[dict[str, Any]] = []
        for run_dir in sorted((path for path in runs_root.iterdir() if path.is_dir()), reverse=True):
            run_id = run_dir.name
            result = _load_json(run_dir / "orchestration-result.json", {})
            summaries.append(_run_summary_from_payload(run_id, run_dir, result))
        return summaries

    def run_detail(self, run_id: str) -> dict[str, Any]:
        run_dir = self._run_dir(run_id)
        result = _load_json(run_dir / "orchestration-result.json", {})
        if not result:
            raise RetrievalServerError(f"Run not found: {run_id}", status=404)
        return {
            **_run_summary_from_payload(run_id, run_dir, result),
            "result": result,
            "evidence": _load_json(run_dir / "evidence-items.json", []),
        }

    def run_trace(self, run_id: str) -> dict[str, Any]:
        run_dir = self._run_dir(run_id)
        return {
            "run_id": run_id,
            "retrieval_trace": _load_jsonl(run_dir / "retrieval-trace.jsonl"),
            "orchestration_trace": _load_jsonl(run_dir / "orchestration-trace.jsonl"),
        }

    def _run_dir(self, run_id: str) -> Path:
        safe = _safe_run_id(run_id)
        if not safe:
            raise RetrievalServerError("Invalid run id.", status=400)
        return self.runs_root / safe

    def _load_or_default_config(self) -> dict[str, Any]:
        if not self.config_path.exists():
            return self._default_config()
        payload = _load_json(self.config_path, {})
        if not isinstance(payload, Mapping):
            return self._default_config()
        return _merge_config(self._default_config(), dict(payload))

    def _default_config(self) -> dict[str, Any]:
        return {
            "workspace_root": str(self.workspace_root),
            "runs_dir": f"{CONFIG_DIR_NAME}/{RUNS_DIR_NAME}",
            "enabled_source_categories": [source.value for source in DEFAULT_ALLOWED_SOURCE_CATEGORIES],
            "connections": {
                "mcp_sources": [],
            },
            "ui": {
                "default_prompt": "Explain where abstract class parsing and validation happen.",
            },
        }


class Handler(BaseHTTPRequestHandler):
    state: RuntimeState

    def do_OPTIONS(self) -> None:
        self._send_json({"ok": True})

    def do_GET(self) -> None:
        try:
            parsed = urlparse(self.path)
            if parsed.path == "/health":
                self._send_json(self.state.public_health())
                return
            if parsed.path == "/config":
                self._send_json(self.state.get_config())
                return
            if parsed.path == "/connections":
                self._send_json({"mcp_sources": self.state.get_config().get("connections", {}).get("mcp_sources", [])})
                return
            if parsed.path == "/runs":
                self._send_json({"runs": self.state.list_runs()})
                return
            run_match = re.fullmatch(r"/runs/([^/]+)", parsed.path)
            if run_match:
                self._send_json(self.state.run_detail(run_match.group(1)))
                return
            trace_match = re.fullmatch(r"/runs/([^/]+)/trace", parsed.path)
            if trace_match:
                self._send_json(self.state.run_trace(trace_match.group(1)))
                return
            self._send_json({"error": "Not found"}, status=404)
        except RetrievalServerError as exc:
            self._send_json({"error": str(exc)}, status=exc.status)
        except Exception as exc:  # pragma: no cover - safety for local server
            self._send_json({"error": str(exc)}, status=500)

    def do_PUT(self) -> None:
        try:
            if urlparse(self.path).path == "/config":
                self._send_json(self.state.update_config(self._read_json()))
                return
            self._send_json({"error": "Not found"}, status=404)
        except RetrievalServerError as exc:
            self._send_json({"error": str(exc)}, status=exc.status)
        except Exception as exc:  # pragma: no cover
            self._send_json({"error": str(exc)}, status=500)

    def do_POST(self) -> None:
        try:
            parsed = urlparse(self.path)
            payload = self._read_json()
            if parsed.path == "/workspaces/open":
                root = Path(str(payload.get("workspace_root") or "")).resolve()
                if not root.exists() or not root.is_dir():
                    raise RetrievalServerError(f"Workspace does not exist: {root}", status=404)
                self.__class__.state = RuntimeState(root)
                self._send_json(self.state.public_health())
                return
            if parsed.path == "/connections/test":
                self._send_json(self.state.test_connection(payload))
                return
            if parsed.path == "/retrieve":
                self._send_json(self.state.run_retrieval(payload), status=201)
                return
            self._send_json({"error": "Not found"}, status=404)
        except RetrievalServerError as exc:
            self._send_json({"error": str(exc)}, status=exc.status)
        except Exception as exc:  # pragma: no cover
            self._send_json({"error": str(exc)}, status=500)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise RetrievalServerError("Request body must be valid JSON.") from exc
        if not isinstance(payload, dict):
            raise RetrievalServerError("Request JSON must be an object.")
        return payload

    def _send_json(self, payload: Mapping[str, Any], *, status: int = 200) -> None:
        body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"{self.address_string()} - {fmt % args}")


def _config_loader_ok(loader: Any, workspace_root: Path) -> bool:
    try:
        loader(workspace_root / ".env")
    except Exception:
        return False
    return True


def _merge_config(defaults: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    merged = _deepcopy_json(defaults)
    for key, value in payload.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), dict):
            merged[key] = _merge_config(merged[key], dict(value))
        else:
            merged[key] = value
    return merged


def _validate_config(payload: Mapping[str, Any]) -> None:
    source_categories_from_strings(tuple(str(item) for item in payload.get("enabled_source_categories", ())))
    connections = payload.get("connections", {})
    if not isinstance(connections, Mapping):
        raise RetrievalServerError("`connections` must be an object.")
    mcp_sources = connections.get("mcp_sources", [])
    if not isinstance(mcp_sources, list):
        raise RetrievalServerError("`connections.mcp_sources` must be an array.")
    for item in mcp_sources:
        if not isinstance(item, Mapping):
            raise RetrievalServerError("Each MCP source must be an object.")
        _mcp_config_from_mapping(item)


def _allowed_sources_from_payload(payload: Mapping[str, Any], config: Mapping[str, Any]) -> tuple[SourceCategory, ...]:
    raw = payload.get("allowed_sources")
    if raw is None:
        raw = config.get("enabled_source_categories", ())
    if not isinstance(raw, list):
        raise RetrievalServerError("`allowed_sources` must be an array.")
    return source_categories_from_strings(tuple(str(item) for item in raw))


def _configured_mcp_sources(config: Mapping[str, Any]) -> tuple[MCPConnectedSourceConfig, ...]:
    connections = config.get("connections", {})
    if not isinstance(connections, Mapping):
        return ()
    sources = connections.get("mcp_sources", [])
    if not isinstance(sources, list):
        return ()
    return tuple(_mcp_config_from_mapping(item) for item in sources if isinstance(item, Mapping) and item.get("enabled", True))


def _mcp_config_from_mapping(payload: Mapping[str, Any]) -> MCPConnectedSourceConfig:
    category = SourceCategory(str(payload.get("source_category") or SourceCategory.ISSUE_TRACKER.value))
    return MCPConnectedSourceConfig(
        name=str(payload.get("name") or "").strip(),
        source_category=category,
        command=str(payload.get("command") or "").strip(),
        args=tuple(str(item) for item in payload.get("args", ()) if str(item).strip()),
        env={str(key): str(value) for key, value in dict(payload.get("env", {}) or {}).items()},
        cwd=str(payload.get("cwd") or "").strip() or None,
        query_tool_name=str(payload.get("query_tool_name") or "").strip(),
        query_argument_name=str(payload.get("query_argument_name") or "query").strip(),
        limit_argument_name=str(payload.get("limit_argument_name") or "limit").strip(),
        result_limit=int(payload.get("result_limit") or 5),
        timeout_seconds=int(payload.get("timeout_seconds") or 20),
        static_tool_arguments={str(key): str(value) for key, value in dict(payload.get("static_tool_arguments", {}) or {}).items()},
        id_fields=tuple(str(item) for item in payload.get("id_fields", ("source_id", "id", "url", "html_url", "number"))),
        title_fields=tuple(str(item) for item in payload.get("title_fields", ("title", "name", "subject"))),
        content_fields=tuple(str(item) for item in payload.get("content_fields", ("content", "body", "text", "description", "summary"))),
    )


def _run_summary_from_payload(run_id: str, run_dir: Path, result: Mapping[str, Any]) -> dict[str, Any]:
    retrieval = result.get("retrieval_result") if isinstance(result.get("retrieval_result"), Mapping) else {}
    summary = retrieval.get("retrieval_summary") if isinstance(retrieval.get("retrieval_summary"), Mapping) else {}
    response = result.get("response_payload") if isinstance(result.get("response_payload"), Mapping) else {}
    plan = summary.get("retrieval_plan") if isinstance(summary.get("retrieval_plan"), Mapping) else {}
    return {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "prompt": str(plan.get("raw_prompt") or _load_json(run_dir / "run-metadata.json", {}).get("prompt") or ""),
        "coverage_status": retrieval.get("coverage_status", "unknown"),
        "sufficient": bool(retrieval.get("sufficient", False)),
        "selected_count": len(retrieval.get("evidence", []) or []),
        "stop_reason": summary.get("stop_reason", ""),
        "response_preview": str(response.get("content") or "")[:500],
    }


def _load_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            events.append(payload)
    return events


def _safe_run_id(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-.")[:120]


def _deepcopy_json(value: Any) -> Any:
    return json.loads(json.dumps(value))


def _find_free_port(preferred: int) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        if sock.connect_ex((DEFAULT_HOST, preferred)) != 0:
            return preferred
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((DEFAULT_HOST, 0))
        return int(sock.getsockname()[1])


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the Guided Intelligence local web API.")
    parser.add_argument("--workspace-root", type=Path, default=Path.cwd())
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()

    Handler.state = RuntimeState(args.workspace_root)
    port = _find_free_port(args.port)
    server = ThreadingHTTPServer((args.host, port), Handler)
    print(f"Guided Intelligence API serving {Handler.state.workspace_root}")
    print(f"http://{args.host}:{port}/health")
    server.serve_forever()


if __name__ == "__main__":
    main()
