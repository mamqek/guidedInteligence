from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import secrets
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qs, urlencode, urlparse

from core.control_layer import ControlLayer
from core.models import ConversationState, UserIntent
from core.policy import PolicyStage
from core.source_policy import DEFAULT_ALLOWED_SOURCE_CATEGORIES, SourceCategory, SourcePolicy
from services.guidance.answer_evaluation import evaluate_answers
from services.retrieval.bm25 import DEFAULT_EXCLUDED_PATHS, estimate_indexing_scope, load_index
from services.logging.store import JsonlLogger
from services.retrieval.config import (
    MCPConnectedSourceConfig,
    RemoteMCPConnectedSourceConfig,
    WorkspaceRetrievalConfig,
    _parse_env_file,
    load_retrieval_embedding_config,
    load_retrieval_enable_indexing,
    load_retrieval_llm_config,
    load_retrieval_qdrant_config,
    source_categories_from_strings,
)
from services.retrieval.mcp import (
    LocalMCPConnectedSourceAdapter,
    MCPConnectedSourceError,
    RemoteMCPConnectedSourceAdapter,
    RemoteMCPConnectedSourceError,
)
from services.retrieval.qdrant_backend import QdrantHybridBackend
from services.retrieval.tools.contracts import ToolRequest
from services.retrieval.workspace import WorkspaceRetrievalStage


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8790
CONFIG_DIR_NAME = ".guided-intelligence"
CONFIG_FILE_NAME = "config.json"
WORKSPACES_FILE_NAME = "workspaces.json"
PROVIDER_AUTH_FILE_NAME = "provider-auth.json"
RUNS_DIR_NAME = "runs"
MAX_WORKSPACE_HISTORY = 25
REMOTE_MCP_CREDENTIAL_FIELDS = ("oauth_access_token", "bearer_token", "api_key")
BUILTIN_SOURCE_KEYS = ("source_code", "repo_docs", "local_notes", "notebooklm")
DEFAULT_REMOTE_MCP_SOURCE_KEYS = (
    "github_issues",
    "github_pull_requests",
    "notion",
    "jira",
    "confluence",
    "shortcut",
    "linear",
    "slack",
    "google_drive",
)
DEFAULT_ALLOWED_SOURCE_KEYS = (*BUILTIN_SOURCE_KEYS, *DEFAULT_REMOTE_MCP_SOURCE_KEYS)


class RetrievalServerError(RuntimeError):
    def __init__(self, message: str, *, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


class RuntimeState:
    def __init__(self, workspace_root: Path, *, tool_root: Path | None = None) -> None:
        self.workspace_root = workspace_root.resolve()
        self.tool_root = (tool_root or Path.cwd()).resolve()
        self.config_path = self.workspace_root / CONFIG_DIR_NAME / CONFIG_FILE_NAME
        self.workspaces_path = self.tool_root / CONFIG_DIR_NAME / WORKSPACES_FILE_NAME
        self.provider_auth_path = self.tool_root / CONFIG_DIR_NAME / PROVIDER_AUTH_FILE_NAME
        self.config = self._load_or_default_config()
        self._index_jobs: dict[str, dict[str, Any]] = {}
        self._index_jobs_lock = threading.Lock()
        self._oauth_sessions: dict[str, dict[str, Any]] = {}

    @property
    def runs_root(self) -> Path:
        configured = str(self.config.get("runs_dir") or "").strip()
        if configured:
            path = Path(configured)
            return path if path.is_absolute() else self.workspace_root / path
        return self.workspace_root / CONFIG_DIR_NAME / RUNS_DIR_NAME

    def public_health(self) -> dict[str, Any]:
        env_path = self.tool_root / ".env"
        qdrant_live = self.qdrant_runtime_status()
        return {
            "status": "ok",
            "workspace_root": str(self.workspace_root),
            "tool_root": str(self.tool_root),
            "config_path": str(self.config_path),
            "config_exists": self.config_path.exists(),
            "env_exists": env_path.exists(),
            "env_path": str(env_path),
            "qdrant_configured": _config_loader_ok(load_retrieval_qdrant_config, self.tool_root),
            "qdrant_reachable": qdrant_live["reachable"],
            "qdrant_status_detail": qdrant_live["detail"],
            "llm_configured": _config_loader_ok(load_retrieval_llm_config, self.tool_root),
            "embedding_configured": _config_loader_ok(load_retrieval_embedding_config, self.tool_root),
            "runs_dir": str(self.runs_root),
            "github_repository": self.github_repository(),
        }

    def github_repository(self) -> str:
        try:
            completed = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=str(self.workspace_root),
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return ""
        if completed.returncode != 0:
            return ""
        return _github_repository_from_remote_url(completed.stdout.strip())

    def get_config(self) -> dict[str, Any]:
        return _deepcopy_json(self.config)

    def provider_auth(self) -> dict[str, Any]:
        payload = _load_json(self.provider_auth_path, {})
        if not isinstance(payload, Mapping):
            return {}
        return {str(provider): dict(value) for provider, value in payload.items() if isinstance(value, Mapping)}

    def public_provider_auth(self) -> dict[str, Any]:
        return {
            provider: _public_provider_auth_entry(auth)
            for provider, auth in self.provider_auth().items()
        }

    def update_provider_auth(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        provider = str(payload.get("provider") or "").strip()
        if not provider:
            raise RetrievalServerError("Provider is required.", status=400)
        current = self.provider_auth()
        auth = _normalize_provider_auth(payload)
        if auth["auth_type"] == "none":
            current.pop(provider, None)
        else:
            current[provider] = auth
        self.provider_auth_path.parent.mkdir(parents=True, exist_ok=True)
        self.provider_auth_path.write_text(json.dumps(current, indent=2, sort_keys=True), encoding="utf-8")
        return self.public_provider_auth()

    def start_provider_oauth(self, payload: Mapping[str, Any], *, request_host: str) -> dict[str, Any]:
        provider = str(payload.get("provider") or "").strip()
        endpoint_url = str(payload.get("endpoint_url") or "").strip()
        if not provider:
            raise RetrievalServerError("Provider is required.", status=400)
        if not endpoint_url:
            raise RetrievalServerError("Remote MCP endpoint URL is required.", status=400)
        if provider == "shortcut":
            auth = _configured_provider_token_auth(provider, self.tool_root)
            if not auth:
                raise RetrievalServerError("Shortcut connect requires SHORTCUT_API_TOKEN in the tool .env.", status=502)
            self.update_provider_auth({"provider": provider, **auth})
            return {"ok": True, "provider": provider, "authorize_url": _local_ui_url(request_host, self.tool_root)}

        registration = _configured_provider_oauth_client(provider, self.tool_root)
        if registration:
            auth_metadata = _provider_oauth_metadata(provider, endpoint_url, {})
        else:
            auth_metadata = _discover_oauth_metadata(endpoint_url)
            registration = _register_oauth_client(auth_metadata, request_host, provider)
        verifier = _oauth_code_verifier()
        state = secrets.token_urlsafe(32)
        redirect_uri = _oauth_redirect_uri(request_host, self.tool_root)
        challenge = _oauth_code_challenge(verifier)
        client_id = str(registration.get("client_id") or "")
        if not client_id:
            raise RetrievalServerError("OAuth client registration did not return a client_id.", status=502)

        auth_params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "state": state,
        }
        if registration.get("pkce", True):
            auth_params["code_challenge"] = challenge
            auth_params["code_challenge_method"] = "S256"
        if provider == "notion":
            auth_params["owner"] = "user"
        scope = str(registration.get("scope") or payload.get("oauth_scope") or "").strip()
        if scope:
            auth_params["scope"] = scope
        resource = str(auth_metadata.get("resource") or endpoint_url).strip()
        if resource and auth_metadata.get("include_resource", True):
            auth_params["resource"] = resource

        self._oauth_sessions[state] = {
            "provider": provider,
            "token_endpoint": auth_metadata["token_endpoint"],
            "client_id": client_id,
            "client_secret": str(registration.get("client_secret") or ""),
            "redirect_uri": redirect_uri,
            "code_verifier": verifier,
            "token_auth_method": str(registration.get("token_auth_method") or "form"),
        }
        authorize_url = f"{auth_metadata['authorization_endpoint']}?{urlencode(auth_params)}"
        return {"ok": True, "provider": provider, "authorize_url": authorize_url}

    def finish_provider_oauth(self, query: Mapping[str, list[str]]) -> str:
        error = _first_query_value(query, "error")
        if error:
            description = _first_query_value(query, "error_description") or error
            raise RetrievalServerError(f"OAuth failed: {description}", status=400)
        state = _first_query_value(query, "state")
        code = _first_query_value(query, "code")
        if not state or not code:
            raise RetrievalServerError("OAuth callback is missing code or state.", status=400)
        session = self._oauth_sessions.pop(state, None)
        if not session:
            raise RetrievalServerError("OAuth session expired or is unknown. Start the connection again.", status=400)
        token_response = _exchange_oauth_code(session, code)
        access_token = str(token_response.get("access_token") or "").strip()
        if not access_token:
            raise RetrievalServerError("OAuth token response did not include an access_token.", status=502)
        self.update_provider_auth(
            {
                "provider": session["provider"],
                "auth_type": "oauth",
                "oauth_access_token": access_token,
            }
        )
        return str(session["provider"])

    def list_workspaces(self) -> list[dict[str, Any]]:
        payload = _load_json(self.workspaces_path, [])
        if not isinstance(payload, list):
            return []
        entries: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in payload:
            if isinstance(item, str):
                raw_path = item
                last_opened_at = ""
            elif isinstance(item, Mapping):
                raw_path = str(item.get("workspace_root") or "")
                last_opened_at = str(item.get("last_opened_at") or "")
            else:
                continue
            if not raw_path.strip():
                continue
            root = Path(raw_path).expanduser().resolve()
            key = str(root).casefold()
            if key in seen:
                continue
            seen.add(key)
            entries.append(
                {
                    "workspace_root": str(root),
                    "name": root.name or str(root),
                    "last_opened_at": last_opened_at,
                    "exists": root.exists() and root.is_dir(),
                    "current": root == self.workspace_root,
                }
            )
        return entries

    def remember_workspace(self, workspace_root: Path | None = None) -> list[dict[str, Any]]:
        root = (workspace_root or self.workspace_root).expanduser().resolve()
        current_entry = {
            "workspace_root": str(root),
            "name": root.name or str(root),
            "last_opened_at": datetime.now(timezone.utc).isoformat(),
        }
        existing = [
            entry
            for entry in self.list_workspaces()
            if str(entry.get("workspace_root") or "").casefold() != str(root).casefold()
        ]
        payload = [current_entry, *existing[: MAX_WORKSPACE_HISTORY - 1]]
        self.workspaces_path.parent.mkdir(parents=True, exist_ok=True)
        self.workspaces_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return self.list_workspaces()

    def update_config(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, Mapping):
            raise RetrievalServerError("Config payload must be an object.")
        updated = _normalize_config(_merge_config(self._default_config(), dict(payload)))
        _validate_config(updated)
        self.config = updated
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps(updated, indent=2, sort_keys=True), encoding="utf-8")
        return self.get_config()

    def test_connection(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        source = _mcp_config_from_mapping(payload)
        adapter = LocalMCPConnectedSourceAdapter(source)
        query = str(payload.get("test_query") or "test").strip() or "test"
        try:
            documents = adapter.search(query)
        except MCPConnectedSourceError as exc:
            return {
                "ok": False,
                "name": source.name,
                "source_key": source.source_key,
                "source_category": source.source_category.value,
                "error": str(exc),
            }
        return {
            "ok": True,
            "name": source.name,
            "source_key": source.source_key,
            "source_category": source.source_category.value,
            "result_count": len(documents),
            "documents": [document.to_dict() for document in documents],
        }

    def test_remote_mcp_connection(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        source = _remote_mcp_config_from_mapping(payload, self.provider_auth())
        adapter = RemoteMCPConnectedSourceAdapter(source)
        query = str(payload.get("test_query") or "test").strip() or "test"
        try:
            documents = adapter.search(query)
        except RemoteMCPConnectedSourceError as exc:
            return {
                "ok": False,
                "name": source.name,
                "provider": source.provider,
                "source_key": source.source_key,
                "source_category": source.source_category.value,
                "error": str(exc),
            }
        return {
            "ok": True,
            "name": source.name,
            "provider": source.provider,
            "source_key": source.source_key,
            "source_category": source.source_category.value,
            "result_count": len(documents),
            "documents": [document.to_dict() for document in documents],
        }

    def list_remote_mcp_tools(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        source = _remote_mcp_config_from_mapping(payload, self.provider_auth())
        adapter = RemoteMCPConnectedSourceAdapter(source)
        try:
            tools = adapter.list_tools()
        except RemoteMCPConnectedSourceError as exc:
            return {
                "ok": False,
                "name": source.name,
                "provider": source.provider,
                "error": str(exc),
                "tools": [],
            }
        return {
            "ok": True,
            "name": source.name,
            "provider": source.provider,
            "tools": [dict(tool) for tool in tools],
            "tool_count": len(tools),
        }

    def browse_workspace(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        start_path = Path(str(payload.get("start_path") or self.workspace_root)).expanduser().resolve()
        if not start_path.exists() or not start_path.is_dir():
            start_path = self.workspace_root
        selected = _choose_directory(start_path)
        return {
            "workspace_root": str(selected) if selected is not None else "",
            "cancelled": selected is None,
        }

    def index_estimate(self) -> dict[str, Any]:
        indexing = self.config.get("indexing", {})
        if not isinstance(indexing, Mapping):
            indexing = {}
        exclude_paths = _string_list(indexing.get("exclude_paths", []))
        chunk_line_count = 40
        chunk_line_overlap = 10
        estimate = estimate_indexing_scope(
            self.workspace_root,
            exclude_paths=tuple(exclude_paths),
            chunk_line_count=chunk_line_count,
            chunk_line_overlap=chunk_line_overlap,
        )
        readiness = self._index_readiness(
            estimate=estimate,
            exclude_paths=tuple(exclude_paths),
            chunk_line_count=chunk_line_count,
            chunk_line_overlap=chunk_line_overlap,
        )
        return {
            **estimate,
            **_index_time_estimate(estimate),
            **readiness,
            "exclude_paths": exclude_paths,
            "enable_indexing": bool(indexing.get("enable_indexing", True)),
        }

    def _index_readiness(
        self,
        *,
        estimate: Mapping[str, Any],
        exclude_paths: tuple[str, ...],
        chunk_line_count: int,
        chunk_line_overlap: int,
    ) -> dict[str, Any]:
        index_dir = self.workspace_root / CONFIG_DIR_NAME / "index"
        index_path = index_dir / "bm25-index.json"
        bm25_manifest = _load_json(index_dir / "bm25-scope-manifest.json", {})
        expected_scope = {
            "workspace_root": str(self.workspace_root.resolve()),
            "exclude_paths": list(exclude_paths),
            "chunk_line_count": chunk_line_count,
            "chunk_line_overlap": chunk_line_overlap,
        }
        if not index_path.exists() or not _manifest_scope_matches(bm25_manifest, expected_scope):
            return {
                "index_ready": False,
                "index_status": "missing_or_stale",
                "index_status_detail": "BM25 index is missing or does not match current exclude settings.",
                "index_last_built_at": _manifest_timestamp(index_dir / "bm25-scope-manifest.json", bm25_manifest),
            }
        try:
            index = load_index(index_dir)
            stage = WorkspaceRetrievalStage(self._workspace_retrieval_config(run_dir=index_dir / "readiness-check"))
            backend = QdrantHybridBackend(
                index=index,
                qdrant_config=stage.config.qdrant_config,
                embedding_config=stage.config.embedding_config,
                cache_path=index_dir / "qdrant-embeddings-cache.json",
            )
            qdrant_manifest = _load_json(index_dir / "qdrant-sync-manifest.json", {})
            last_built_at = _manifest_timestamp(index_dir / "qdrant-sync-manifest.json", qdrant_manifest)
            expected_signature = backend.index_signature()
            if (
                str(qdrant_manifest.get("index_signature") or "") != expected_signature
                or str(qdrant_manifest.get("collection_name") or "") != stage.config.qdrant_config.collection_name
            ):
                return {
                    "index_ready": False,
                    "index_status": "missing_or_stale",
                    "index_status_detail": "Qdrant sync manifest is missing or stale.",
                    "index_last_built_at": last_built_at,
                }
            point_count = backend.point_count() if backend.collection_exists() else 0
            expected_count = len(index.documents)
            if point_count != expected_count:
                return {
                    "index_ready": False,
                    "index_status": "missing_or_stale",
                    "index_status_detail": f"Qdrant has {point_count} points; expected {expected_count}.",
                    "index_last_built_at": last_built_at,
                }
        except Exception as exc:
            return {
                "index_ready": False,
                "index_status": "unknown",
                "index_status_detail": f"Could not verify index readiness: {exc}",
                "index_last_built_at": _manifest_timestamp(index_dir / "qdrant-sync-manifest.json"),
            }
        return {
            "index_ready": True,
            "index_status": "ready",
            "index_last_built_at": last_built_at,
            "index_status_detail": (
                f"BM25 and Qdrant are fresh for {int(estimate.get('file_count') or 0)} files / "
                f"{len(index.documents)} chunks."
            ),
        }

    def qdrant_runtime_status(self) -> dict[str, Any]:
        try:
            config = load_retrieval_qdrant_config(self.tool_root / ".env")
        except Exception as exc:
            return {"reachable": False, "detail": f"Qdrant config is missing or invalid: {exc}"}
        if _qdrant_reachable(config.url, timeout_seconds=1.0):
            return {"reachable": True, "detail": f"Reachable at {config.url}"}
        return {"reachable": False, "detail": f"Qdrant is not reachable at {config.url}"}

    def ensure_qdrant_runtime(self) -> None:
        config = load_retrieval_qdrant_config(self.tool_root / ".env")
        if _qdrant_reachable(config.url, timeout_seconds=1.0):
            return
        parsed = urlparse(config.url)
        host = (parsed.hostname or "").lower()
        if host not in {"localhost", "127.0.0.1", "::1"}:
            raise RetrievalServerError(
                f"Qdrant is required but not reachable at {config.url}. "
                "This is a remote/non-local Qdrant URL, so the tool cannot start it automatically.",
                status=503,
            )
        compose_path = self.tool_root / "docker-compose.qdrant.yml"
        if not compose_path.exists():
            raise RetrievalServerError(
                f"Qdrant is required but not reachable at {config.url}, and {compose_path} is missing.",
                status=503,
            )
        try:
            completed = subprocess.run(
                ["docker", "compose", "-f", str(compose_path), "up", "-d"],
                cwd=str(self.tool_root),
                capture_output=True,
                text=True,
                timeout=90,
                check=False,
            )
        except FileNotFoundError as exc:
            raise RetrievalServerError(
                "Qdrant is required but Docker is not installed or not on PATH. "
                "Install/start Docker Desktop so the tool can run local Qdrant automatically.",
                status=503,
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise RetrievalServerError(
                "Qdrant is required. The tool tried to start it with docker compose, but Docker did not respond in time.",
                status=503,
            ) from exc
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()
            if "dockerDesktopLinuxEngine" in detail or "pipe" in detail or "Cannot connect" in detail:
                reason = "Docker Desktop is not running."
            else:
                reason = "Docker compose failed."
            raise RetrievalServerError(
                "Qdrant is required for indexing/retrieval but is not reachable at "
                f"{config.url}. I tried to start it with `docker compose -f docker-compose.qdrant.yml up -d`, "
                f"but {reason} Details: {detail}",
                status=503,
            )
        deadline = time.time() + 30
        while time.time() < deadline:
            if _qdrant_reachable(config.url, timeout_seconds=1.0):
                return
            time.sleep(1)
        raise RetrievalServerError(
            f"Qdrant was started with Docker compose, but {config.url} did not become reachable within 30 seconds.",
            status=503,
        )

    def start_prepare_index(self) -> dict[str, Any]:
        job_id = f"index-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
        indexing_estimate = self.index_estimate()
        if not indexing_estimate.get("enable_indexing", True):
            raise RetrievalServerError("Indexing is disabled in workspace settings.", status=400)
        self.ensure_qdrant_runtime()
        job = {
            "job_id": job_id,
            "status": "running",
            "phase": "queued",
            "message": "Queued index preparation.",
            "progress_percent": 0,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": "",
            "elapsed_seconds": 0,
            "workspace_root": str(self.workspace_root),
            "index_dir": str(self.workspace_root / CONFIG_DIR_NAME / "index"),
            "document_count": 0,
            "index_estimate": indexing_estimate,
            "logs": [],
        }
        with self._index_jobs_lock:
            self._index_jobs[job_id] = job
        threading.Thread(target=self._run_prepare_index_job, args=(job_id,), daemon=True).start()
        return self.index_job(job_id)

    def index_job(self, job_id: str) -> dict[str, Any]:
        with self._index_jobs_lock:
            job = self._index_jobs.get(job_id)
            if job is None:
                raise RetrievalServerError(f"Index job not found: {job_id}", status=404)
            return _deepcopy_json(job)

    def _update_index_job(
        self,
        job_id: str,
        *,
        phase: str,
        message: str,
        progress_percent: int,
        log: str | None = None,
    ) -> None:
        with self._index_jobs_lock:
            job = self._index_jobs[job_id]
            job.update(
                {
                    "phase": phase,
                    "message": message,
                    "progress_percent": max(0, min(99, progress_percent)),
                }
            )
            if log:
                logs = list(job.get("logs", []))
                logs.append(log)
                job["logs"] = logs[-8:]

    def _finish_index_job(self, job_id: str, payload: Mapping[str, Any]) -> None:
        with self._index_jobs_lock:
            self._index_jobs[job_id].update(payload)

    def _run_prepare_index_job(self, job_id: str) -> None:
        started_at = datetime.now(timezone.utc)
        job = self.index_job(job_id)
        indexing_estimate = job.get("index_estimate") if isinstance(job.get("index_estimate"), Mapping) else {}
        estimated_chunks = int(indexing_estimate.get("estimated_chunks") or 0)
        try:
            embedding_config = load_retrieval_embedding_config(self.tool_root / ".env")
            estimated_embedding_batches = max(1, (estimated_chunks + embedding_config.batch_size - 1) // embedding_config.batch_size)
        except Exception:
            estimated_embedding_batches = max(1, estimated_chunks // 32)
        completed_embedding_batches = 0
        run_dir = self.workspace_root / CONFIG_DIR_NAME / "index-prep"
        try:
            self._update_index_job(
                job_id,
                phase="cgc",
                message="Refreshing code graph.",
                progress_percent=5,
                log="Refreshing code graph.",
            )
            indexing_estimate = self.index_estimate()
            if not indexing_estimate.get("enable_indexing", True):
                raise RetrievalServerError("Indexing is disabled in workspace settings.", status=400)
            run_dir.mkdir(parents=True, exist_ok=True)
            self._sync_cgcignore_excludes()
            stage = WorkspaceRetrievalStage(self._workspace_retrieval_config(run_dir=run_dir))
            cgc_tools = stage._cgc_tools()
            index_observation = cgc_tools["cgc_index_repo"].run(
                ToolRequest(tool_name="cgc_index_repo", arguments={}, reason="manual index preparation")
            )
            stage._record_tool(ToolRequest(tool_name="cgc_index_repo", arguments={}), index_observation, round_index=0)
            if index_observation.status != "ok":
                raise RetrievalServerError(_cgc_failure_message(index_observation.payload), status=500)
            self._update_index_job(
                job_id,
                phase="bm25",
                message="Building BM25 workspace index.",
                progress_percent=15,
                log="Code graph refreshed.",
            )
            original_record = stage._record

            def record_progress(event_type: str, payload: Mapping[str, Any]) -> None:
                nonlocal completed_embedding_batches
                original_record(event_type, payload)
                if event_type == "embedding_batch_completed":
                    completed_embedding_batches += 1
                    display_total = max(estimated_embedding_batches, completed_embedding_batches)
                    percent = 30 + int(min(1.0, completed_embedding_batches / display_total) * 55)
                    self._update_index_job(
                        job_id,
                        phase="embeddings",
                        message=f"Syncing embeddings into Qdrant ({completed_embedding_batches}/{display_total} batches).",
                        progress_percent=percent,
                    )
                elif event_type == "workspace_index_reused":
                    self._update_index_job(
                        job_id,
                        phase="complete",
                        message="Existing index is in sync.",
                        progress_percent=95,
                        log="Existing Qdrant index reused.",
                    )
                elif event_type == "workspace_index_rebuilt":
                    self._update_index_job(
                        job_id,
                        phase="qdrant",
                        message="Finalizing Qdrant index sync.",
                        progress_percent=95,
                        log="Qdrant index synchronized.",
                    )

            stage._record = record_progress  # type: ignore[method-assign]
            index = stage._rebuild_index()
            completed_at = datetime.now(timezone.utc)
            self._finish_index_job(
                job_id,
                {
                    "status": "complete",
                    "phase": "complete",
                    "message": "Index preparation complete.",
                    "progress_percent": 100,
                    "completed_at": completed_at.isoformat(),
                    "elapsed_seconds": round((completed_at - started_at).total_seconds(), 2),
                    "document_count": len(index.documents),
                },
            )
            payload = self.index_job(job_id)
            (run_dir / "index-prepare-result.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        except Exception as exc:
            completed_at = datetime.now(timezone.utc)
            logs = list(job.get("logs", []))
            logs.append(f"Failed: {exc}")
            self._finish_index_job(
                job_id,
                {
                    "status": "failed",
                    "phase": "failed",
                    "message": str(exc),
                    "progress_percent": 100,
                    "completed_at": completed_at.isoformat(),
                    "elapsed_seconds": round((completed_at - started_at).total_seconds(), 2),
                    "logs": logs[-8:],
                },
            )

    def run_retrieval(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        prompt = str(payload.get("prompt") or "").strip()
        if not prompt:
            raise RetrievalServerError("`prompt` is required.")
        allowed_source_keys = _allowed_source_keys_from_payload(payload, self.config)
        allowed_categories = _source_categories_for_keys(allowed_source_keys, self.config)
        run_id = _safe_run_id(str(payload.get("run_id") or ""))
        if not run_id:
            run_id = f"run-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
        run_dir = self.runs_root / run_id
        run_dir.mkdir(parents=True, exist_ok=False)
        indexing_estimate = self.index_estimate()
        metadata = {
            "run_id": run_id,
            "status": "running",
            "phase": "indexing" if indexing_estimate.get("enable_indexing", True) else "retrieval",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "workspace_root": str(self.workspace_root),
            "prompt": prompt,
            "allowed_sources": list(allowed_source_keys),
            "run_dir": str(run_dir),
            "index_estimate": indexing_estimate,
            "progress_percent": 1,
            "progress_message": "Queued explanation run.",
            "progress_logs": [],
        }
        (run_dir / "run-metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
        threading.Thread(
            target=self._run_retrieval_job,
            args=(run_id, run_dir, prompt, tuple(allowed_source_keys), tuple(allowed_categories), indexing_estimate),
            daemon=True,
        ).start()
        return _run_summary_from_payload(run_id, run_dir, {})

    def _run_retrieval_job(
        self,
        run_id: str,
        run_dir: Path,
        prompt: str,
        allowed_source_keys: tuple[str, ...],
        allowed_categories: tuple[SourceCategory, ...],
        indexing_estimate: Mapping[str, Any],
    ) -> None:
        started_at = datetime.now(timezone.utc)
        role_subquery_count = 0
        completed_embedding_batches = 0
        try:
            embedding_config = load_retrieval_embedding_config(self.tool_root / ".env")
            estimated_chunks = int(indexing_estimate.get("estimated_chunks") or 0)
            estimated_embedding_batches = max(1, (estimated_chunks + embedding_config.batch_size - 1) // embedding_config.batch_size)
        except Exception:
            estimated_chunks = int(indexing_estimate.get("estimated_chunks") or 0)
            estimated_embedding_batches = max(1, estimated_chunks // 32)
        self._update_run_progress(run_dir, phase="indexing", percent=5, message="Checking index readiness.")
        try:
            self.ensure_qdrant_runtime()
            self._sync_cgcignore_excludes()
            self._update_run_progress(run_dir, phase="retrieval", percent=10, message="Starting retrieval.")
            llm_config = load_retrieval_llm_config(self.tool_root / ".env")
            retrieval_stage = WorkspaceRetrievalStage(
                self._workspace_retrieval_config(
                    run_dir=run_dir,
                    enabled_source_categories=tuple(allowed_categories),
                    enabled_sources=tuple(allowed_source_keys),
                )
            )
            original_record = retrieval_stage._record

            def record_retrieval_progress(event_type: str, event_payload: Mapping[str, Any]) -> None:
                nonlocal role_subquery_count, completed_embedding_batches
                original_record(event_type, event_payload)
                if event_type == "workspace_index_cgc_started":
                    self._update_run_progress(run_dir, phase="cgc", percent=12, message="Refreshing code graph.", log="Refreshing code graph.")
                elif event_type == "workspace_index_bm25_started":
                    self._update_run_progress(run_dir, phase="bm25", percent=15, message="Building BM25 workspace index.", log="Code graph refreshed.")
                elif event_type == "workspace_bm25_index_reused":
                    self._update_run_progress(run_dir, phase="qdrant", percent=18, message="BM25 index is in sync.", log="BM25 index reused.")
                elif event_type == "workspace_bm25_index_rebuilt":
                    self._update_run_progress(run_dir, phase="qdrant", percent=20, message="BM25 index rebuilt; syncing embeddings.", log="BM25 index rebuilt.")
                elif event_type == "embedding_batch_completed":
                    completed_embedding_batches += 1
                    display_total = max(estimated_embedding_batches, completed_embedding_batches)
                    percent = 30 + int(min(1.0, completed_embedding_batches / display_total) * 55)
                    self._update_run_progress(
                        run_dir,
                        phase="embeddings",
                        percent=percent,
                        message=f"Syncing embeddings into Qdrant ({completed_embedding_batches}/{display_total} batches).",
                    )
                elif event_type == "workspace_index_reused":
                    self._update_run_progress(run_dir, phase="retrieval", percent=18, message="Index is ready.", log="Index ready.")
                elif event_type == "workspace_index_rebuilt":
                    self._update_run_progress(run_dir, phase="retrieval", percent=86, message="Index is ready.", log="Index ready.")
                elif event_type == "retrieval_plan_created":
                    self._update_run_progress(run_dir, phase="planning", percent=30, message="Retrieval plan created.", log="Retrieval plan created.")
                elif event_type == "role_subquery_started":
                    role_subquery_count += 1
                    percent = min(70, 38 + role_subquery_count * 4)
                    role = str(event_payload.get("role") or "role")
                    self._update_run_progress(run_dir, phase="retrieval", percent=percent, message=f"Retrieving evidence for {role}.")
                elif event_type in {"role_followup_completed", "deterministic_coverage_gate_completed", "gap_check_completed"}:
                    self._update_run_progress(run_dir, phase="retrieval", percent=76, message="Checking evidence coverage.")
                elif event_type == "retrieval_refinement_evaluated":
                    self._update_run_progress(run_dir, phase="retrieval", percent=82, message="Evaluating retrieval sufficiency.")

            retrieval_stage._record = record_retrieval_progress  # type: ignore[method-assign]
            policy = PolicyStage(SourcePolicy(allowed_categories=tuple(allowed_categories), policy_name="local_web_ui"))
            progress_logger = _ProgressJsonlLogger(run_dir / "orchestration-trace.jsonl", run_dir)
            control = ControlLayer(
                policy_stage=policy,
                retrieval_stage=retrieval_stage,
                logger=progress_logger,
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
            completed_at = datetime.now(timezone.utc)
            metadata = _load_json(run_dir / "run-metadata.json", {})
            metadata.update(
                {
                    "run_id": run_id,
                    "status": "complete",
                    "phase": "complete",
                    "completed_at": completed_at.isoformat(),
                    "elapsed_seconds": round((completed_at - started_at).total_seconds(), 2),
                    "progress_percent": 100,
                    "progress_message": "Explanation complete.",
                    "workspace_root": str(self.workspace_root),
                    "prompt": prompt,
                    "allowed_sources": list(allowed_source_keys),
                    "run_dir": str(run_dir),
                    "index_estimate": indexing_estimate,
                }
            )
            (run_dir / "run-metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
        except Exception as exc:
            completed_at = datetime.now(timezone.utc)
            metadata = _load_json(run_dir / "run-metadata.json", {})
            logs = list(metadata.get("progress_logs", [])) if isinstance(metadata.get("progress_logs"), list) else []
            logs.append(f"Failed: {exc}")
            metadata.update(
                {
                    "status": "failed",
                    "phase": "failed",
                    "completed_at": completed_at.isoformat(),
                    "elapsed_seconds": round((completed_at - started_at).total_seconds(), 2),
                    "progress_percent": 100,
                    "progress_message": str(exc),
                    "progress_logs": logs[-8:],
                }
            )
            (run_dir / "run-metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")

    def _update_run_progress(
        self,
        run_dir: Path,
        *,
        phase: str,
        percent: int,
        message: str,
        log: str | None = None,
    ) -> None:
        _update_run_metadata_progress(run_dir, phase=phase, percent=percent, message=message, log=log)

    def _workspace_retrieval_config(
        self,
        *,
        run_dir: str | Path,
        enabled_source_categories: tuple[SourceCategory, ...] | None = None,
        enabled_sources: tuple[str, ...] | None = None,
    ) -> WorkspaceRetrievalConfig:
        tool_env_path = self.tool_root / ".env"
        indexing = self.config.get("indexing", {})
        if not isinstance(indexing, Mapping):
            indexing = {}
        index_exclude_paths = tuple(_string_list(indexing.get("exclude_paths", [])))
        connections = _connections_mapping(self.config)
        return WorkspaceRetrievalConfig(
            workspace_root=str(self.workspace_root),
            index_dir=str(self.workspace_root / CONFIG_DIR_NAME / "index"),
            run_dir=str(run_dir),
            llm_config=load_retrieval_llm_config(tool_env_path),
            embedding_config=load_retrieval_embedding_config(tool_env_path),
            qdrant_config=load_retrieval_qdrant_config(tool_env_path),
            enable_indexing=bool(indexing.get("enable_indexing", load_retrieval_enable_indexing(tool_env_path))),
            cgc_repo_path=str(self.workspace_root),
            cgc_db_path=str(self.workspace_root / CONFIG_DIR_NAME / "index" / "cgc-kuzu"),
            cgc_force_reindex_each_request=False,
            cgc_timeout_seconds=180,
            index_exclude_paths=index_exclude_paths,
            enabled_source_categories=enabled_source_categories if enabled_source_categories is not None else tuple(DEFAULT_ALLOWED_SOURCE_CATEGORIES),
            enabled_sources=enabled_sources if enabled_sources is not None else tuple(_enabled_sources_from_config(self.config)),
            remote_mcp_connected_sources=_configured_remote_mcp_sources(self.config, self.provider_auth()),
            mcp_connected_sources=_configured_mcp_sources(self.config),
        )

    def _sync_cgcignore_excludes(self) -> None:
        indexing = self.config.get("indexing", {})
        if not isinstance(indexing, Mapping):
            indexing = {}
        exclude_paths = _string_list(indexing.get("exclude_paths", []))
        _sync_cgcignore(self.workspace_root, tuple(exclude_paths))

    def evaluate_run_answers(self, run_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        run_dir = self._run_dir(run_id)
        result = _load_json(run_dir / "orchestration-result.json", {})
        if not result:
            raise RetrievalServerError(f"Run not found: {run_id}", status=404)
        response = result.get("response_payload") if isinstance(result.get("response_payload"), Mapping) else {}
        metadata = response.get("metadata") if isinstance(response.get("metadata"), Mapping) else {}
        checks = metadata.get("understanding_checks", ())
        if not isinstance(checks, list) or not checks:
            raise RetrievalServerError("Run has no understanding checks to evaluate.", status=400)
        answers = payload.get("answers", {})
        if not isinstance(answers, Mapping):
            raise RetrievalServerError("`answers` must be an object keyed by question id.", status=400)
        llm_config = load_retrieval_llm_config(self.tool_root / ".env")
        evaluations = evaluate_answers(
            checks=tuple(item for item in checks if isinstance(item, Mapping)),
            answers={str(key): str(value) for key, value in answers.items()},
            llm_config=llm_config,
        )
        output = {
            "run_id": run_id,
            "evaluations": [evaluation.to_dict() for evaluation in evaluations],
        }
        (run_dir / "answer-evaluation.json").write_text(json.dumps(output, indent=2, sort_keys=True), encoding="utf-8")
        return output

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
        if not result and not run_dir.exists():
            raise RetrievalServerError(f"Run not found: {run_id}", status=404)
        return {
            **_run_summary_from_payload(run_id, run_dir, result),
            "result": result,
            "evidence": _load_json(run_dir / "evidence-items.json", []),
            "answer_evaluation": _load_json(run_dir / "answer-evaluation.json", {}),
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
        return _normalize_config(_merge_config(self._default_config(), dict(payload)))

    def _default_config(self) -> dict[str, Any]:
        return {
            "workspace_root": str(self.workspace_root),
            "runs_dir": f"{CONFIG_DIR_NAME}/{RUNS_DIR_NAME}",
            "enabled_source_categories": [source.value for source in DEFAULT_ALLOWED_SOURCE_CATEGORIES],
            "enabled_sources": list(DEFAULT_ALLOWED_SOURCE_KEYS),
            "connections": {
                "remote_mcp_sources": _default_remote_mcp_sources(),
                "mcp_sources": [],
            },
            "indexing": {
                "enable_indexing": load_retrieval_enable_indexing(self.tool_root / ".env"),
                "exclude_paths": list(DEFAULT_EXCLUDED_PATHS),
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
            if parsed.path == "/workspaces":
                self._send_json({"workspaces": self.state.list_workspaces()})
                return
            if parsed.path == "/connections":
                self._send_json({"mcp_sources": self.state.get_config().get("connections", {}).get("mcp_sources", [])})
                return
            if parsed.path == "/connections/provider-auth":
                self._send_json(self.state.public_provider_auth())
                return
            if parsed.path == "/connections/provider-auth/callback":
                provider = self.state.finish_provider_oauth(parse_qs(parsed.query))
                app_url = _local_ui_url(self.headers.get("Host", f"{DEFAULT_HOST}:{DEFAULT_PORT}"), self.state.tool_root)
                self._send_html(
                    f"<html><body style=\"font-family: system-ui, sans-serif; max-width: 560px; margin: 64px auto; line-height: 1.5;\">"
                    f"<h1>{_html_escape(provider)} connected</h1>"
                    "<p>You can return to Guided Intelligence and test the connection.</p>"
                    f"<p><a href=\"{_html_escape(app_url)}\" style=\"display: inline-block; padding: 10px 14px; background: #2563eb; color: white; text-decoration: none; border-radius: 6px;\">Return to Guided Intelligence</a></p>"
                    "</body></html>"
                )
                return
            if parsed.path == "/index/estimate":
                self._send_json(self.state.index_estimate())
                return
            index_job_match = re.fullmatch(r"/index/prepare/([^/]+)", parsed.path)
            if index_job_match:
                self._send_json(self.state.index_job(index_job_match.group(1)))
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
                next_state = RuntimeState(root, tool_root=self.state.tool_root)
                next_state.remember_workspace(root)
                self.__class__.state = next_state
                self._send_json(self.state.public_health())
                return
            if parsed.path == "/workspaces/browse":
                self._send_json(self.state.browse_workspace(payload))
                return
            if parsed.path == "/index/prepare":
                self._send_json(self.state.start_prepare_index(), status=202)
                return
            if parsed.path == "/connections/test":
                self._send_json(self.state.test_connection(payload))
                return
            if parsed.path == "/connections/remote-mcp/test":
                self._send_json(self.state.test_remote_mcp_connection(payload))
                return
            if parsed.path == "/connections/remote-mcp/tools":
                self._send_json(self.state.list_remote_mcp_tools(payload))
                return
            if parsed.path == "/connections/provider-auth":
                self._send_json(self.state.update_provider_auth(payload))
                return
            if parsed.path == "/connections/provider-auth/connect":
                self._send_json(self.state.start_provider_oauth(payload, request_host=self.headers.get("Host", f"{DEFAULT_HOST}:{DEFAULT_PORT}")))
                return
            if parsed.path == "/retrieve":
                self._send_json(self.state.run_retrieval(payload), status=201)
                return
            answer_match = re.fullmatch(r"/runs/([^/]+)/answers", parsed.path)
            if answer_match:
                self._send_json(self.state.evaluate_run_answers(answer_match.group(1), payload), status=201)
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

    def _send_html(self, html: str, *, status: int = 200) -> None:
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"{self.address_string()} - {fmt % args}")


class _ProgressJsonlLogger(JsonlLogger):
    def __init__(self, path: str | Path, run_dir: Path) -> None:
        super().__init__(path)
        self.run_dir = run_dir

    def record(self, event: Any) -> None:
        super().record(event)
        raw_event_type = getattr(event, "event_type", "")
        event_type = str(getattr(raw_event_type, "value", raw_event_type))
        event_type = event_type.strip()
        progress = _orchestration_progress_for_event(event_type)
        if progress is None:
            return
        percent, phase, message, log = progress
        _update_run_metadata_progress(self.run_dir, phase=phase, percent=percent, message=message, log=log)


def _config_loader_ok(loader: Any, workspace_root: Path) -> bool:
    try:
        loader(workspace_root / ".env")
    except Exception:
        return False
    return True


def _update_run_metadata_progress(
    run_dir: Path,
    *,
    phase: str,
    percent: int,
    message: str,
    log: str | None = None,
) -> None:
    metadata_path = run_dir / "run-metadata.json"
    metadata = _load_json(metadata_path, {})
    logs = list(metadata.get("progress_logs", [])) if isinstance(metadata.get("progress_logs"), list) else []
    if log:
        logs.append(log)
    metadata.update(
        {
            "status": "running",
            "phase": phase,
            "progress_percent": max(0, min(99, percent)),
            "progress_message": message,
            "progress_logs": logs[-8:],
        }
    )
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")


def _orchestration_progress_for_event(event_type: str) -> tuple[int, str, str, str | None] | None:
    mapping: dict[str, tuple[int, str, str, str | None]] = {
        "run_started": (12, "policy", "Analyzing request.", None),
        "turn_decision": (16, "policy", "Checking source policy.", None),
        "retrieval_plan": (22, "planning", "Preparing retrieval.", None),
        "evidence_selected": (86, "synthesis", "Evidence selected.", "Evidence selected."),
        "response_plan": (88, "synthesis", "Planning explanation response.", None),
        "prompt_payload": (90, "synthesis", "Preparing explanation prompt.", None),
        "response_generation_requested": (92, "generation", "Generating explanation.", "Explanation generation started."),
        "response_generation_request_payload": (92, "generation", "Generating explanation.", "Explanation generation started."),
        "response_generation_received": (97, "generation", "Received explanation response.", None),
        "response_generation_response_payload": (97, "generation", "Received explanation response.", None),
        "response_payload": (99, "generation", "Finalizing explanation.", None),
        "run_completed": (99, "complete", "Finalizing run.", None),
    }
    return mapping.get(event_type)


def _qdrant_reachable(url: str, *, timeout_seconds: float) -> bool:
    target = url.rstrip("/") + "/collections"
    request = urllib.request.Request(target, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return 200 <= int(response.status) < 500
    except (OSError, urllib.error.URLError, TimeoutError):
        return False


CGCIGNORE_START = "# BEGIN guided-intelligence managed excludes"
CGCIGNORE_END = "# END guided-intelligence managed excludes"


def _sync_cgcignore(workspace_root: Path, exclude_paths: tuple[str, ...]) -> None:
    cgcignore_path = workspace_root / ".cgcignore"
    existing = cgcignore_path.read_text(encoding="utf-8") if cgcignore_path.exists() else ""
    cleaned = _remove_managed_cgcignore_block(existing).rstrip()
    managed_lines = [CGCIGNORE_START]
    for path in _normalize_cgcignore_excludes(exclude_paths):
        managed_lines.append(path)
    managed_lines.append(CGCIGNORE_END)
    next_text = "\n".join(part for part in (cleaned, "\n".join(managed_lines)) if part).rstrip() + "\n"
    if next_text != existing:
        cgcignore_path.write_text(next_text, encoding="utf-8")


def _remove_managed_cgcignore_block(text: str) -> str:
    pattern = re.compile(
        rf"(^|\n){re.escape(CGCIGNORE_START)}\n.*?\n{re.escape(CGCIGNORE_END)}\n?",
        re.DOTALL,
    )
    return pattern.sub("\n", text).strip("\n")


def _normalize_cgcignore_excludes(exclude_paths: tuple[str, ...]) -> tuple[str, ...]:
    output: list[str] = []
    for value in exclude_paths:
        item = value.strip().replace("\\", "/").strip("/")
        if not item:
            continue
        if "." in Path(item).name:
            pattern = item
        else:
            pattern = item.rstrip("/") + "/"
        if pattern not in output:
            output.append(pattern)
    return tuple(output)


def _cgc_failure_message(payload: Mapping[str, Any]) -> str:
    reason = str(payload.get("reason") or "CGC index preparation failed.").strip()
    stdout = str(payload.get("stdout") or "").strip()
    stderr = str(payload.get("stderr") or "").strip()
    detail = stdout or stderr or reason
    if "timed out" in reason.lower():
        return (
            "CGC index preparation timed out. The code graph index did not finish within the configured timeout. "
            f"Details: {reason}"
        )
    if "could not set lock" in detail.lower():
        return (
            "CGC index preparation failed because its Kuzu database is locked by another process. "
            "Close other running retrieval/indexing jobs or restart the local API, then try again. "
            f"Details: {detail}"
        )
    return f"CGC index preparation failed. Details: {detail}"


def _index_time_estimate(estimate: Mapping[str, Any]) -> dict[str, Any]:
    files = int(estimate.get("file_count") or 0)
    chunks = int(estimate.get("estimated_chunks") or 0)
    if files <= 0 or chunks <= 0:
        return {"estimated_seconds_min": 0, "estimated_seconds_max": 0}
    min_seconds = max(10, int(chunks * 0.05 + files * 0.002))
    max_seconds = max(min_seconds + 10, int(chunks * 0.15 + files * 0.006))
    return {
        "estimated_seconds_min": min_seconds,
        "estimated_seconds_max": max_seconds,
    }


def _merge_config(defaults: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    merged = _deepcopy_json(defaults)
    for key, value in payload.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), dict):
            merged[key] = _merge_config(merged[key], dict(value))
        else:
            merged[key] = value
    return merged


def _normalize_config(config: dict[str, Any]) -> dict[str, Any]:
    indexing = config.get("indexing")
    if isinstance(indexing, dict):
        indexing.pop("include_paths", None)
    connections = config.get("connections")
    if not isinstance(connections, dict):
        connections = {}
        config["connections"] = connections
    for key in ("github_repository", "github_fetch_issues", "github_fetch_pull_requests"):
        connections.pop(key, None)
    connections["remote_mcp_sources"] = _normalize_remote_mcp_sources(connections.get("remote_mcp_sources", []))
    mcp_sources = connections.get("mcp_sources", [])
    if isinstance(mcp_sources, list):
        normalized_mcp_sources: list[dict[str, Any]] = []
        for source in mcp_sources:
            if not isinstance(source, Mapping) or _is_legacy_github_mcp_source(source):
                continue
            normalized_source = dict(source)
            normalized_source.setdefault("source_key", _source_key_from_mapping(normalized_source))
            normalized_mcp_sources.append(normalized_source)
        connections["mcp_sources"] = normalized_mcp_sources
    else:
        connections["mcp_sources"] = []
    has_only_default_enabled_sources = (
        isinstance(config.get("enabled_sources"), list)
        and list(config.get("enabled_sources", [])) == list(DEFAULT_ALLOWED_SOURCE_KEYS)
        and isinstance(config.get("enabled_source_categories"), list)
        and list(config.get("enabled_source_categories", [])) != [source.value for source in DEFAULT_ALLOWED_SOURCE_CATEGORIES]
    )
    if not isinstance(config.get("enabled_sources"), list) or has_only_default_enabled_sources:
        config["enabled_sources"] = _migrate_enabled_sources(config)
    else:
        config["enabled_sources"] = _normalize_source_keys(config.get("enabled_sources", []), config)
    config["enabled_source_categories"] = [
        source.value for source in _source_categories_for_keys(tuple(config["enabled_sources"]), config)
    ]
    return config


def _normalize_remote_mcp_sources(value: Any) -> list[dict[str, Any]]:
    defaults = _default_remote_mcp_sources()
    by_name = {str(item.get("name") or ""): item for item in defaults}
    ordered_names = [str(item.get("name") or "") for item in defaults]
    custom_sources: list[dict[str, Any]] = []
    if isinstance(value, list):
        for item in value:
            if not isinstance(item, Mapping):
                continue
            name = str(item.get("name") or "").strip()
            if name and name in by_name:
                by_name[name] = _repair_remote_mcp_defaults(_merge_config(by_name[name], dict(item)), by_name[name])
            else:
                custom = dict(item)
                custom.setdefault("source_key", _source_key_from_mapping(custom))
                custom_sources.append(custom)
    normalized = [_strip_remote_mcp_credentials(by_name[name]) for name in ordered_names if name]
    normalized.extend(_strip_remote_mcp_credentials(source) for source in custom_sources)
    return normalized


def _strip_remote_mcp_credentials(source: Mapping[str, Any]) -> dict[str, Any]:
    cleaned = dict(source)
    for field in REMOTE_MCP_CREDENTIAL_FIELDS:
        cleaned[field] = ""
    return cleaned


def _repair_remote_mcp_defaults(source: Mapping[str, Any], defaults: Mapping[str, Any]) -> dict[str, Any]:
    repaired = dict(source)
    if str(defaults.get("title") or "").strip():
        repaired["title"] = defaults["title"]
    for key in ("source_key", "endpoint_url", "auth_type", "query_tool_name", "fetch_tool_name", "query_argument_name", "limit_argument_name"):
        if not str(repaired.get(key) or "").strip() and str(defaults.get(key) or "").strip():
            repaired[key] = defaults[key]
    if defaults.get("enrich_results", False):
        repaired["enrich_results"] = True
    if int(defaults.get("enrich_limit") or 0) > 0 and int(repaired.get("enrich_limit") or 0) <= 0:
        repaired["enrich_limit"] = defaults["enrich_limit"]
    return repaired


def _enabled_sources_from_config(config: Mapping[str, Any]) -> tuple[str, ...]:
    raw = config.get("enabled_sources")
    if isinstance(raw, list):
        return tuple(_normalize_source_keys(raw, config))
    return tuple(_migrate_enabled_sources(config))


def _normalize_source_keys(values: Any, config: Mapping[str, Any]) -> list[str]:
    if not isinstance(values, list):
        return []
    valid = _valid_source_keys(config)
    output: list[str] = []
    for value in values:
        key = str(value).strip()
        if not key:
            continue
        key = _legacy_source_key_alias(key)
        if key in valid and key not in output:
            output.append(key)
    return output


def _valid_source_keys(config: Mapping[str, Any]) -> set[str]:
    keys = set(BUILTIN_SOURCE_KEYS)
    connections = _connections_mapping(config)
    for source in connections.get("remote_mcp_sources", []):
        if isinstance(source, Mapping):
            keys.add(_source_key_from_mapping(source))
    for source in connections.get("mcp_sources", []):
        if isinstance(source, Mapping):
            keys.add(_source_key_from_mapping(source))
    return keys


def _migrate_enabled_sources(config: Mapping[str, Any]) -> list[str]:
    raw_categories = config.get("enabled_source_categories", [])
    categories: set[str] = {str(item) for item in raw_categories} if isinstance(raw_categories, list) else set()
    migrated: list[str] = []
    if SourceCategory.SOURCE_CODE.value in categories:
        migrated.append("source_code")
    if SourceCategory.DOCUMENTATION.value in categories:
        migrated.append("repo_docs")
    if SourceCategory.LOCAL_NOTES.value in categories:
        migrated.append("local_notes")
    if SourceCategory.NOTEBOOKLM.value in categories:
        migrated.append("notebooklm")
    connections = _connections_mapping(config)
    for source in connections.get("remote_mcp_sources", []):
        if not isinstance(source, Mapping) or not source.get("enabled", False):
            continue
        category = str(source.get("source_category") or "")
        key = _source_key_from_mapping(source)
        if category in categories and key not in migrated:
            migrated.append(key)
    for source in connections.get("mcp_sources", []):
        if not isinstance(source, Mapping) or not source.get("enabled", True):
            continue
        category = str(source.get("source_category") or "")
        key = _source_key_from_mapping(source)
        if category in categories and key not in migrated:
            migrated.append(key)
    return migrated


def _source_categories_for_keys(source_keys: tuple[str, ...], config: Mapping[str, Any]) -> tuple[SourceCategory, ...]:
    categories: list[SourceCategory] = []

    def add(category: SourceCategory) -> None:
        if category not in categories:
            categories.append(category)

    for key in source_keys:
        if key == "source_code":
            add(SourceCategory.SOURCE_CODE)
        elif key == "repo_docs":
            add(SourceCategory.DOCUMENTATION)
        elif key == "local_notes":
            add(SourceCategory.LOCAL_NOTES)
        elif key == "notebooklm":
            add(SourceCategory.NOTEBOOKLM)
    source_categories_by_key: dict[str, SourceCategory] = {}
    connections = _connections_mapping(config)
    for collection_name in ("remote_mcp_sources", "mcp_sources"):
        for source in connections.get(collection_name, []):
            if not isinstance(source, Mapping):
                continue
            try:
                source_categories_by_key[_source_key_from_mapping(source)] = SourceCategory(str(source.get("source_category") or SourceCategory.DOCUMENTATION.value))
            except ValueError:
                continue
    for key in source_keys:
        category = source_categories_by_key.get(key)
        if category is not None:
            add(category)
    return tuple(categories)


def _source_key_from_mapping(source: Mapping[str, Any]) -> str:
    explicit = str(source.get("source_key") or "").strip()
    if explicit:
        return _legacy_source_key_alias(explicit)
    name = str(source.get("name") or "").strip()
    provider = str(source.get("provider") or "").strip()
    category = str(source.get("source_category") or "").strip()
    if name == "github-issues":
        return "github_issues"
    if name == "github-prs":
        return "github_pull_requests"
    if name == "notion-pages":
        return "notion"
    if name == "jira-issues":
        return "jira"
    if name == "confluence-pages":
        return "confluence"
    if name == "shortcut-stories":
        return "shortcut"
    if name == "linear-issues":
        return "linear"
    if name == "slack-messages":
        return "slack"
    if name == "google-drive-documents":
        return "google_drive"
    if provider == "github" and category == "issue_tracker":
        return "github_issues"
    if provider == "github" and category == "pull_request":
        return "github_pull_requests"
    if provider == "atlassian" and category == "issue_tracker":
        return "jira"
    if provider == "atlassian" and category == "documentation":
        return "confluence"
    return _slug_key(name or provider or category or "connected_source")


def _legacy_source_key_alias(value: str) -> str:
    return {
        "documentation": "repo_docs",
        "pull_request": "github_pull_requests",
    }.get(value, value)


def _slug_key(value: str) -> str:
    key = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return key or "connected_source"


def _is_legacy_github_mcp_source(source: Mapping[str, Any]) -> bool:
    command = str(source.get("command") or "").lower()
    return "github-mcp-server" in command


def _validate_config(payload: Mapping[str, Any]) -> None:
    if not isinstance(payload.get("enabled_sources", []), list):
        raise RetrievalServerError("`enabled_sources` must be an array.")
    unknown_sources = [
        str(item)
        for item in payload.get("enabled_sources", [])
        if str(item).strip() and str(item).strip() not in _valid_source_keys(payload)
    ]
    if unknown_sources:
        raise RetrievalServerError(f"Unknown enabled source key: {unknown_sources[0]}")
    source_categories_from_strings(tuple(str(item) for item in payload.get("enabled_source_categories", ())))
    connections = payload.get("connections", {})
    if not isinstance(connections, Mapping):
        raise RetrievalServerError("`connections` must be an object.")
    remote_mcp_sources = connections.get("remote_mcp_sources", [])
    if not isinstance(remote_mcp_sources, list):
        raise RetrievalServerError("`connections.remote_mcp_sources` must be an array.")
    for item in remote_mcp_sources:
        if not isinstance(item, Mapping):
            raise RetrievalServerError("Each remote MCP source must be an object.")
        _remote_mcp_config_from_mapping(item)
    mcp_sources = connections.get("mcp_sources", [])
    if not isinstance(mcp_sources, list):
        raise RetrievalServerError("`connections.mcp_sources` must be an array.")
    for item in mcp_sources:
        if not isinstance(item, Mapping):
            raise RetrievalServerError("Each MCP source must be an object.")
        _mcp_config_from_mapping(item)
    indexing = payload.get("indexing", {})
    if not isinstance(indexing, Mapping):
        raise RetrievalServerError("`indexing` must be an object.")
    values = indexing.get("exclude_paths", [])
    if not isinstance(values, list):
        raise RetrievalServerError("`indexing.exclude_paths` must be an array.")
    for value in values:
        text = str(value).strip()
        if Path(text).is_absolute() or ".." in Path(text).parts:
            raise RetrievalServerError("`indexing.exclude_paths` entries must be workspace-relative safe paths.")


def _allowed_source_keys_from_payload(payload: Mapping[str, Any], config: Mapping[str, Any]) -> tuple[str, ...]:
    raw = payload.get("allowed_sources")
    if raw is None:
        raw = config.get("enabled_sources", ())
    if not isinstance(raw, list):
        raise RetrievalServerError("`allowed_sources` must be an array.")
    if raw and all(_is_source_category_value(str(item).strip()) for item in raw if str(item).strip()):
        migrated_config = dict(config)
        migrated_config["enabled_source_categories"] = [str(item).strip() for item in raw if str(item).strip()]
        return tuple(_migrate_enabled_sources(migrated_config))
    keys = _normalize_source_keys(raw, config)
    if len(keys) != len([item for item in raw if str(item).strip()]):
        valid = _valid_source_keys(config)
        for item in raw:
            key = _legacy_source_key_alias(str(item).strip())
            if key and key not in valid:
                raise RetrievalServerError(f"Unknown source key: {item}")
    return tuple(keys)


def _is_source_category_value(value: str) -> bool:
    try:
        SourceCategory(value)
    except ValueError:
        return False
    return True


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    output: list[str] = []
    for item in value:
        text = str(item).strip().replace("\\", "/").strip("/")
        if text and text not in output:
            output.append(text)
    return output


def _plain_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _connections_mapping(config: Mapping[str, Any]) -> Mapping[str, Any]:
    connections = config.get("connections", {})
    return connections if isinstance(connections, Mapping) else {}


def _configured_mcp_sources(config: Mapping[str, Any]) -> tuple[MCPConnectedSourceConfig, ...]:
    connections = _connections_mapping(config)
    sources = connections.get("mcp_sources", [])
    if not isinstance(sources, list):
        return ()
    return tuple(_mcp_config_from_mapping(item) for item in sources if isinstance(item, Mapping) and item.get("enabled", True))


def _configured_remote_mcp_sources(
    config: Mapping[str, Any],
    provider_auth: Mapping[str, Any] | None = None,
) -> tuple[RemoteMCPConnectedSourceConfig, ...]:
    connections = _connections_mapping(config)
    sources = connections.get("remote_mcp_sources", [])
    if not isinstance(sources, list):
        return ()
    return tuple(
        _remote_mcp_config_from_mapping(item, provider_auth)
        for item in sources
        if isinstance(item, Mapping) and item.get("enabled", False)
    )


def _choose_directory(start_path: Path) -> Path | None:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as exc:  # pragma: no cover - depends on local Python install
        raise RetrievalServerError(f"Directory picker is unavailable: {exc}", status=500) from exc

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        selected = filedialog.askdirectory(
            parent=root,
            initialdir=str(start_path),
            title="Select project directory",
            mustexist=True,
        )
    finally:
        root.destroy()
    return Path(selected).resolve() if selected else None


def _mcp_config_from_mapping(payload: Mapping[str, Any]) -> MCPConnectedSourceConfig:
    category = SourceCategory(str(payload.get("source_category") or SourceCategory.ISSUE_TRACKER.value))
    return MCPConnectedSourceConfig(
        name=str(payload.get("name") or "").strip(),
        source_category=category,
        command=str(payload.get("command") or "").strip(),
        source_key=_source_key_from_mapping(payload),
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


def _remote_mcp_config_from_mapping(
    payload: Mapping[str, Any],
    provider_auth: Mapping[str, Any] | None = None,
) -> RemoteMCPConnectedSourceConfig:
    category = SourceCategory(str(payload.get("source_category") or SourceCategory.DOCUMENTATION.value))
    auth_payload = _remote_mcp_payload_with_provider_auth(payload, provider_auth or {})
    return RemoteMCPConnectedSourceConfig(
        enabled=bool(payload.get("enabled", False)),
        name=str(payload.get("name") or "").strip(),
        provider=str(payload.get("provider") or "").strip(),
        source_category=category,
        endpoint_url=str(payload.get("endpoint_url") or "").strip(),
        source_key=_source_key_from_mapping(payload),
        auth_type=str(auth_payload.get("auth_type") or "none").strip(),
        bearer_token=str(auth_payload.get("bearer_token") or "").strip(),
        oauth_access_token=str(auth_payload.get("oauth_access_token") or "").strip(),
        api_key=str(auth_payload.get("api_key") or "").strip(),
        api_key_header=str(auth_payload.get("api_key_header") or "").strip(),
        oauth_authorize_url=str(payload.get("oauth_authorize_url") or "").strip(),
        headers={str(key): str(value) for key, value in dict(payload.get("headers", {}) or {}).items()},
        scope=str(payload.get("scope") or "").strip(),
        features={str(key): bool(value) for key, value in dict(payload.get("features", {}) or {}).items()},
        query_tool_name=str(payload.get("query_tool_name") or "").strip(),
        fetch_tool_name=str(payload.get("fetch_tool_name") or "").strip(),
        query_argument_name=str(payload.get("query_argument_name") or "query").strip(),
        limit_argument_name=str(payload.get("limit_argument_name") or "limit").strip(),
        result_limit=int(payload.get("result_limit") or 5),
        enrich_results=bool(payload.get("enrich_results", False)),
        enrich_limit=int(payload.get("enrich_limit") or 3),
        timeout_seconds=int(payload.get("timeout_seconds") or 20),
        min_score=float(payload.get("min_score") or 0.0),
        static_tool_arguments={str(key): str(value) for key, value in dict(payload.get("static_tool_arguments", {}) or {}).items()},
        score_fields=tuple(str(item) for item in payload.get("score_fields", ("score", "relevance", "rank_score", "_score"))),
        id_fields=tuple(str(item) for item in payload.get("id_fields", ("source_id", "id", "url", "html_url", "key", "number"))),
        title_fields=tuple(str(item) for item in payload.get("title_fields", ("title", "name", "summary", "subject"))),
        content_fields=tuple(str(item) for item in payload.get("content_fields", ("content", "body", "text", "description", "summary"))),
    )


def _remote_mcp_payload_with_provider_auth(
    payload: Mapping[str, Any],
    provider_auth: Mapping[str, Any],
) -> Mapping[str, Any]:
    provider = str(payload.get("provider") or "").strip()
    auth = provider_auth.get(provider)
    if not isinstance(auth, Mapping):
        return payload
    merged = dict(payload)
    auth_type = str(auth.get("auth_type") or "").strip()
    if provider == "shortcut" and auth_type == "api_key" and auth.get("api_key"):
        auth_type = "bearer"
        merged["auth_type"] = "bearer"
        merged["bearer_token"] = str(auth.get("api_key") or "").strip()
        return merged
    if auth_type:
        merged["auth_type"] = auth_type
    for field in REMOTE_MCP_CREDENTIAL_FIELDS:
        value = str(auth.get(field) or "").strip()
        if value:
            merged[field] = value
    api_key_header = str(auth.get("api_key_header") or "").strip()
    if api_key_header:
        merged["api_key_header"] = api_key_header
    return merged


def _discover_oauth_metadata(endpoint_url: str) -> dict[str, Any]:
    challenge = _oauth_challenge_from_endpoint(endpoint_url)
    resource_metadata_url = str(challenge.get("resource_metadata") or "").strip()
    authorization_server = str(challenge.get("authorization_uri") or challenge.get("authorization_server") or "").strip()
    resource = str(challenge.get("resource") or endpoint_url).strip()
    if resource_metadata_url:
        resource_metadata = _get_json(resource_metadata_url)
        servers = resource_metadata.get("authorization_servers")
        if isinstance(servers, list) and servers:
            authorization_server = str(servers[0] or "").strip()
        resource = str(resource_metadata.get("resource") or resource).strip()
    if not authorization_server:
        raise RetrievalServerError(
            "Remote MCP server did not advertise an OAuth authorization server. This provider needs a manual token or a hosted OAuth client.",
            status=502,
        )
    auth_metadata = _oauth_server_metadata(authorization_server)
    for field in ("authorization_endpoint", "token_endpoint"):
        if not str(auth_metadata.get(field) or "").strip():
            raise RetrievalServerError(f"OAuth metadata is missing {field}.", status=502)
    auth_metadata["resource"] = resource
    return auth_metadata


def _oauth_challenge_from_endpoint(endpoint_url: str) -> dict[str, str]:
    request = urllib.request.Request(endpoint_url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=15):
            raise RetrievalServerError("Remote MCP endpoint did not request OAuth authentication.", status=400)
    except urllib.error.HTTPError as exc:
        header = exc.headers.get("WWW-Authenticate", "")
        if exc.code not in {401, 403} or "bearer" not in header.lower():
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise RetrievalServerError(f"Remote MCP HTTP {exc.code}: {detail or 'OAuth challenge was not provided.'}", status=502) from exc
        return _parse_www_authenticate_params(header)
    except urllib.error.URLError as exc:
        raise RetrievalServerError(f"Remote MCP OAuth discovery failed: {exc.reason}", status=502) from exc


def _parse_www_authenticate_params(header: str) -> dict[str, str]:
    _, _, params_text = header.partition(" ")
    params: dict[str, str] = {}
    for match in re.finditer(r'([A-Za-z_][A-Za-z0-9_-]*)=("(?:[^"\\]|\\.)*"|[^,\s]+)', params_text):
        value = match.group(2).strip()
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1].replace('\\"', '"')
        params[match.group(1)] = value
    return params


def _oauth_server_metadata(authorization_server: str) -> dict[str, Any]:
    if authorization_server.endswith("/.well-known/oauth-authorization-server"):
        return _get_json(authorization_server)
    parsed = urlparse(authorization_server)
    if not parsed.scheme or not parsed.netloc:
        raise RetrievalServerError("OAuth authorization server URL is invalid.", status=502)
    base = f"{parsed.scheme}://{parsed.netloc}"
    path = parsed.path.rstrip("/")
    candidates = [
        f"{base}/.well-known/oauth-authorization-server{path}",
        f"{base}/.well-known/oauth-authorization-server",
        f"{base}/.well-known/openid-configuration{path}",
        f"{base}/.well-known/openid-configuration",
    ]
    last_error = ""
    for candidate in candidates:
        try:
            return _get_json(candidate)
        except RetrievalServerError as exc:
            last_error = str(exc)
    raise RetrievalServerError(f"Could not load OAuth server metadata: {last_error}", status=502)


def _configured_provider_oauth_client(provider: str, tool_root: Path) -> dict[str, Any] | None:
    values = dict(_parse_env_file(tool_root / ".env"))
    values.update(
        {
            key: value
            for key, value in os.environ.items()
            if key.startswith("GITHUB_OAUTH_") or key.startswith("NOTION_OAUTH_") or key.startswith("GUIDED_INTELLIGENCE_")
        }
    )
    normalized_provider = provider.strip().lower()
    if normalized_provider == "github":
        client_id = str(values.get("GITHUB_OAUTH_CLIENT_ID") or values.get("GUIDED_INTELLIGENCE_GITHUB_OAUTH_CLIENT_ID") or "").strip()
        client_secret = str(values.get("GITHUB_OAUTH_CLIENT_SECRET") or values.get("GUIDED_INTELLIGENCE_GITHUB_OAUTH_CLIENT_SECRET") or "").strip()
        scope = str(values.get("GITHUB_OAUTH_SCOPE") or "repo read:org").strip()
        if not client_id:
            return None
        return {"client_id": client_id, "client_secret": client_secret, "scope": scope, "pkce": True, "token_auth_method": "form"}
    if normalized_provider == "notion":
        client_id = str(values.get("NOTION_OAUTH_CLIENT_ID") or values.get("GUIDED_INTELLIGENCE_NOTION_OAUTH_CLIENT_ID") or "").strip()
        client_secret = str(values.get("NOTION_OAUTH_CLIENT_SECRET") or values.get("GUIDED_INTELLIGENCE_NOTION_OAUTH_CLIENT_SECRET") or "").strip()
        if not client_id:
            return None
        return {"client_id": client_id, "client_secret": client_secret, "pkce": False, "token_auth_method": "basic_json"}
    return None


def _configured_provider_token_auth(provider: str, tool_root: Path) -> dict[str, Any] | None:
    values = dict(_parse_env_file(tool_root / ".env"))
    values.update({key: value for key, value in os.environ.items() if key.startswith("SHORTCUT_") or key.startswith("GUIDED_INTELLIGENCE_")})
    normalized_provider = provider.strip().lower()
    if normalized_provider == "shortcut":
        token = str(values.get("SHORTCUT_API_TOKEN") or values.get("GUIDED_INTELLIGENCE_SHORTCUT_API_TOKEN") or "").strip()
        if not token:
            return None
        return {"auth_type": "bearer", "bearer_token": token}
    return None


def _provider_oauth_metadata(provider: str, endpoint_url: str, discovered: Mapping[str, Any]) -> dict[str, Any]:
    normalized_provider = provider.strip().lower()
    if normalized_provider == "github":
        return {
            "authorization_endpoint": "https://github.com/login/oauth/authorize",
            "token_endpoint": "https://github.com/login/oauth/access_token",
            "resource": "",
            "mcp_resource": endpoint_url,
        }
    if normalized_provider == "notion":
        return {
            "authorization_endpoint": "https://api.notion.com/v1/oauth/authorize",
            "token_endpoint": "https://api.notion.com/v1/oauth/token",
            "resource": "",
            "include_resource": False,
            "mcp_resource": endpoint_url,
        }
    return dict(discovered)


def _register_oauth_client(auth_metadata: Mapping[str, Any], request_host: str, provider: str) -> dict[str, Any]:
    registration_endpoint = str(auth_metadata.get("registration_endpoint") or "").strip()
    if not registration_endpoint:
        normalized_provider = provider.strip().lower()
        if normalized_provider == "github":
            raise RetrievalServerError(
                "GitHub browser connect requires one tool-level OAuth app. Add GITHUB_OAUTH_CLIENT_ID and "
                "GITHUB_OAUTH_CLIENT_SECRET to the tool .env. GitHub callback URL: "
                f"{_oauth_redirect_uri(request_host)}",
                status=502,
            )
        if normalized_provider == "notion":
            raise RetrievalServerError(
                "Notion browser connect requires one tool-level public OAuth integration. Add NOTION_OAUTH_CLIENT_ID and "
                "NOTION_OAUTH_CLIENT_SECRET to the tool .env. Notion redirect URI: "
                f"{_oauth_redirect_uri(request_host)}",
                status=502,
            )
        raise RetrievalServerError(
            "OAuth server does not support dynamic client registration. A one-click browser connect needs provider OAuth client configuration for this server.",
            status=502,
        )
    payload = {
        "client_name": f"Guided Intelligence {provider}",
        "redirect_uris": [_oauth_redirect_uri(request_host)],
        "grant_types": ["authorization_code"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
    }
    return _post_json(registration_endpoint, payload)


def _oauth_redirect_uri(request_host: str, tool_root: Path | None = None) -> str:
    return _oauth_redirect_uri_for_base(request_host, tool_root)


def _oauth_redirect_uri_for_base(request_host: str, tool_root: Path | None = None) -> str:
    configured_base = _oauth_redirect_base_url(tool_root)
    if configured_base:
        return f"{configured_base}/connections/provider-auth/callback"
    host = request_host.split(",", 1)[0].strip() or f"{DEFAULT_HOST}:{DEFAULT_PORT}"
    return f"http://{host}/connections/provider-auth/callback"


def _oauth_redirect_base_url(tool_root: Path | None = None) -> str:
    values: dict[str, str] = {}
    if tool_root is not None:
        values.update(_parse_env_file(tool_root / ".env"))
    values.update(
        {
            key: value
            for key, value in os.environ.items()
            if key in {"OAUTH_REDIRECT_BASE_URL", "GUIDED_INTELLIGENCE_OAUTH_REDIRECT_BASE_URL"}
        }
    )
    raw = str(values.get("OAUTH_REDIRECT_BASE_URL") or values.get("GUIDED_INTELLIGENCE_OAUTH_REDIRECT_BASE_URL") or "").strip()
    return raw.rstrip("/")


def _local_ui_url(request_host: str, tool_root: Path | None = None) -> str:
    configured = _oauth_return_base_url(tool_root)
    if configured:
        return f"{configured}/#connections"
    if _oauth_redirect_base_url(tool_root):
        return "http://127.0.0.1:5173/#connections"
    host = request_host.split(",", 1)[0].strip() or f"{DEFAULT_HOST}:{DEFAULT_PORT}"
    hostname = host.rsplit(":", 1)[0] if ":" in host else host
    return f"http://{hostname}:5173/#connections"


def _oauth_return_base_url(tool_root: Path | None = None) -> str:
    values: dict[str, str] = {}
    if tool_root is not None:
        values.update(_parse_env_file(tool_root / ".env"))
    values.update(
        {
            key: value
            for key, value in os.environ.items()
            if key in {"OAUTH_RETURN_BASE_URL", "GUIDED_INTELLIGENCE_OAUTH_RETURN_BASE_URL"}
        }
    )
    raw = str(values.get("OAUTH_RETURN_BASE_URL") or values.get("GUIDED_INTELLIGENCE_OAUTH_RETURN_BASE_URL") or "").strip()
    return raw.rstrip("/")


def _oauth_code_verifier() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(48)).decode("ascii").rstrip("=")


def _oauth_code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _get_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RetrievalServerError(f"HTTP {exc.code} while loading {url}: {detail}", status=502) from exc
    except urllib.error.URLError as exc:
        raise RetrievalServerError(f"Request failed while loading {url}: {exc.reason}", status=502) from exc
    except json.JSONDecodeError as exc:
        raise RetrievalServerError(f"{url} returned invalid JSON.", status=502) from exc
    if not isinstance(payload, dict):
        raise RetrievalServerError(f"{url} returned a non-object JSON response.", status=502)
    return payload


def _post_json(url: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    raw = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=raw, headers={"Content-Type": "application/json", "Accept": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RetrievalServerError(f"HTTP {exc.code} while posting to {url}: {detail}", status=502) from exc
    except urllib.error.URLError as exc:
        raise RetrievalServerError(f"Request failed while posting to {url}: {exc.reason}", status=502) from exc
    except json.JSONDecodeError as exc:
        raise RetrievalServerError(f"{url} returned invalid JSON.", status=502) from exc
    if not isinstance(response_payload, dict):
        raise RetrievalServerError(f"{url} returned a non-object JSON response.", status=502)
    return response_payload


def _post_form_json(url: str, payload: Mapping[str, str]) -> dict[str, Any]:
    raw = urlencode(payload).encode("utf-8")
    request = urllib.request.Request(url, data=raw, headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RetrievalServerError(f"HTTP {exc.code} while exchanging OAuth code: {detail}", status=502) from exc
    except urllib.error.URLError as exc:
        raise RetrievalServerError(f"OAuth token exchange failed: {exc.reason}", status=502) from exc
    except json.JSONDecodeError as exc:
        raise RetrievalServerError("OAuth token endpoint returned invalid JSON.", status=502) from exc
    if not isinstance(response_payload, dict):
        raise RetrievalServerError("OAuth token endpoint returned a non-object JSON response.", status=502)
    return response_payload


def _exchange_oauth_code(session: Mapping[str, Any], code: str) -> dict[str, Any]:
    token_auth_method = str(session.get("token_auth_method") or "form")
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": str(session["redirect_uri"]),
    }
    if token_auth_method == "basic_json":
        return _post_basic_json(
            str(session["token_endpoint"]),
            payload,
            username=str(session["client_id"]),
            password=str(session.get("client_secret") or ""),
        )
    payload["client_id"] = str(session["client_id"])
    code_verifier = str(session.get("code_verifier") or "")
    if code_verifier:
        payload["code_verifier"] = code_verifier
    if session.get("client_secret"):
        payload["client_secret"] = str(session["client_secret"])
    return _post_form_json(str(session["token_endpoint"]), payload)


def _post_basic_json(url: str, payload: Mapping[str, str], *, username: str, password: str) -> dict[str, Any]:
    raw = json.dumps(payload).encode("utf-8")
    credentials = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    request = urllib.request.Request(
        url,
        data=raw,
        headers={"Content-Type": "application/json", "Accept": "application/json", "Authorization": f"Basic {credentials}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RetrievalServerError(f"HTTP {exc.code} while exchanging OAuth code: {detail}", status=502) from exc
    except urllib.error.URLError as exc:
        raise RetrievalServerError(f"OAuth token exchange failed: {exc.reason}", status=502) from exc
    except json.JSONDecodeError as exc:
        raise RetrievalServerError("OAuth token endpoint returned invalid JSON.", status=502) from exc
    if not isinstance(response_payload, dict):
        raise RetrievalServerError("OAuth token endpoint returned a non-object JSON response.", status=502)
    return response_payload


def _first_query_value(query: Mapping[str, list[str]], key: str) -> str:
    values = query.get(key) or []
    return str(values[0]) if values else ""


def _html_escape(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _normalize_provider_auth(payload: Mapping[str, Any]) -> dict[str, Any]:
    auth_type = str(payload.get("auth_type") or "none").strip()
    if auth_type not in {"oauth", "bearer", "api_key", "none"}:
        raise RetrievalServerError("Unsupported provider auth type.", status=400)
    return {
        "auth_type": auth_type,
        "oauth_access_token": str(payload.get("oauth_access_token") or "").strip(),
        "bearer_token": str(payload.get("bearer_token") or "").strip(),
        "api_key": str(payload.get("api_key") or "").strip(),
        "api_key_header": str(payload.get("api_key_header") or "").strip(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def _public_provider_auth_entry(auth: Mapping[str, Any]) -> dict[str, Any]:
    auth_type = str(auth.get("auth_type") or "none").strip()
    return {
        "auth_type": auth_type,
        "connected": (
            (auth_type == "oauth" and bool(auth.get("oauth_access_token")))
            or (auth_type == "bearer" and bool(auth.get("bearer_token")))
            or (auth_type == "api_key" and bool(auth.get("api_key")))
        ),
        "oauth_access_token_configured": bool(auth.get("oauth_access_token")),
        "bearer_token_configured": bool(auth.get("bearer_token")),
        "api_key_configured": bool(auth.get("api_key")),
        "api_key_header": str(auth.get("api_key_header") or ""),
        "updated_at": str(auth.get("updated_at") or ""),
    }


def _default_remote_mcp_sources() -> list[dict[str, Any]]:
    return [
        _remote_mcp_preset("github-issues", "github_issues", "github", "GitHub issues", SourceCategory.ISSUE_TRACKER, {"issues": True}, endpoint_url="https://api.githubcopilot.com/mcp/", query_tool_name="search_issues"),
        _remote_mcp_preset("github-prs", "github_pull_requests", "github", "GitHub PRs", SourceCategory.PULL_REQUEST, {"pull_requests": True}, endpoint_url="https://api.githubcopilot.com/mcp/", query_tool_name="search_pull_requests"),
        _remote_mcp_preset(
            "notion-pages",
            "notion",
            "notion",
            "Notion",
            SourceCategory.DOCUMENTATION,
            {"pages": True, "databases": True, "data_sources": True, "comments": False},
            endpoint_url="https://mcp.notion.com/mcp",
            query_tool_name="notion-search",
            fetch_tool_name="notion-fetch",
            enrich_results=True,
            enrich_limit=3,
        ),
        _remote_mcp_preset(
            "jira-issues",
            "jira",
            "atlassian",
            "Jira",
            SourceCategory.ISSUE_TRACKER,
            {"issues": True, "comments": True, "linked_pages": True, "projects": False},
            endpoint_url="https://mcp.atlassian.com/v1/mcp/authv2",
            query_tool_name="searchJiraIssuesUsingJql",
            fetch_tool_name="getJiraIssue",
            enrich_results=True,
            enrich_limit=3,
        ),
        _remote_mcp_preset(
            "confluence-pages",
            "confluence",
            "atlassian",
            "Confluence",
            SourceCategory.DOCUMENTATION,
            {"pages": True, "spaces": False, "comments": False},
            endpoint_url="https://mcp.atlassian.com/v1/mcp/authv2",
            query_tool_name="searchConfluenceUsingCql",
            fetch_tool_name="getConfluencePage",
            enrich_results=True,
            enrich_limit=3,
        ),
        _remote_mcp_preset(
            "shortcut-stories",
            "shortcut",
            "shortcut",
            "Shortcut",
            SourceCategory.ISSUE_TRACKER,
            {"stories": True, "epics": True, "docs": True, "comments": False},
            endpoint_url="https://mcp.shortcut.com/mcp",
            enrich_results=True,
            enrich_limit=3,
        ),
        _remote_mcp_preset(
            "linear-issues",
            "linear",
            "linear",
            "Linear",
            SourceCategory.ISSUE_TRACKER,
            {"issues": True, "projects": True, "comments": True},
            endpoint_url="https://mcp.linear.app/sse",
            enrich_results=True,
            enrich_limit=3,
        ),
        _remote_mcp_preset(
            "slack-messages",
            "slack",
            "slack",
            "Slack",
            SourceCategory.LOCAL_NOTES,
            {"messages": True, "files": True, "channels": False, "threads": True, "users": False},
            endpoint_url="https://mcp.slack.com/mcp",
            enrich_results=True,
            enrich_limit=3,
        ),
        _remote_mcp_preset(
            "google-drive-documents",
            "google_drive",
            "google_drive",
            "Google Drive",
            SourceCategory.DOCUMENTATION,
            {"docs": True, "sheets": True, "slides": True, "folders": False, "files": True},
            endpoint_url="https://drivemcp.googleapis.com/mcp/v1",
            query_tool_name="search_files",
            enrich_results=True,
            enrich_limit=3,
        ),
    ]


def _remote_mcp_preset(
    name: str,
    source_key: str,
    provider: str,
    title: str,
    source_category: SourceCategory,
    features: Mapping[str, bool],
    *,
    endpoint_url: str = "",
    query_tool_name: str = "",
    fetch_tool_name: str = "",
    enrich_results: bool = False,
    enrich_limit: int = 3,
) -> dict[str, Any]:
    return {
        "enabled": False,
        "name": name,
        "source_key": source_key,
        "provider": provider,
        "title": title,
        "source_category": source_category.value,
        "endpoint_url": endpoint_url,
        "auth_type": "oauth",
        "bearer_token": "",
        "oauth_access_token": "",
        "api_key": "",
        "api_key_header": "",
        "oauth_authorize_url": "",
        "headers": {},
        "scope": "",
        "features": dict(features),
        "query_tool_name": query_tool_name,
        "fetch_tool_name": fetch_tool_name,
        "query_argument_name": "query",
        "limit_argument_name": "limit",
        "result_limit": 5,
        "enrich_results": enrich_results,
        "enrich_limit": enrich_limit,
        "timeout_seconds": 20,
        "min_score": 0.0,
        "static_tool_arguments": {},
        "score_fields": ["score", "relevance", "rank_score", "_score"],
        "id_fields": ["source_id", "id", "url", "html_url", "key", "number"],
        "title_fields": ["title", "name", "summary", "subject"],
        "content_fields": ["content", "body", "text", "description", "summary"],
    }


def _github_repository_from_remote_url(value: str) -> str:
    remote = value.strip()
    if not remote:
        return ""
    patterns = (
        r"^https://github\.com/(?P<owner>[^/\s]+)/(?P<repo>[^/\s]+?)(?:\.git)?/?$",
        r"^git@github\.com:(?P<owner>[^/\s]+)/(?P<repo>[^/\s]+?)(?:\.git)?$",
        r"^ssh://git@github\.com/(?P<owner>[^/\s]+)/(?P<repo>[^/\s]+?)(?:\.git)?/?$",
    )
    for pattern in patterns:
        match = re.match(pattern, remote)
        if match is None:
            continue
        owner = match.group("owner").strip()
        repo = match.group("repo").strip()
        if owner and repo:
            return f"{owner}/{repo}"
    return ""


def _run_summary_from_payload(run_id: str, run_dir: Path, result: Mapping[str, Any]) -> dict[str, Any]:
    metadata = _load_json(run_dir / "run-metadata.json", {})
    if not result:
        estimate = metadata.get("index_estimate") if isinstance(metadata.get("index_estimate"), Mapping) else {}
        metrics = _run_metrics(run_dir, metadata)
        return {
            "run_id": run_id,
            "run_dir": str(run_dir),
            "prompt": str(metadata.get("prompt") or ""),
            "status": str(metadata.get("status") or "running"),
            "phase": str(metadata.get("phase") or "indexing"),
            "coverage_status": "preparing_index",
            "sufficient": False,
            "selected_count": 0,
            "stop_reason": "",
            "response_preview": "",
            "index_estimate": _deepcopy_json(estimate),
            "progress_percent": int(metadata.get("progress_percent") or 0),
            "progress_message": str(metadata.get("progress_message") or ""),
            "progress_logs": _plain_string_list(metadata.get("progress_logs", [])),
            **metrics,
        }
    retrieval = result.get("retrieval_result") if isinstance(result.get("retrieval_result"), Mapping) else {}
    summary = retrieval.get("retrieval_summary") if isinstance(retrieval.get("retrieval_summary"), Mapping) else {}
    response = result.get("response_payload") if isinstance(result.get("response_payload"), Mapping) else {}
    plan = summary.get("retrieval_plan") if isinstance(summary.get("retrieval_plan"), Mapping) else {}
    metrics = _run_metrics(run_dir, metadata)
    return {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "prompt": str(plan.get("raw_prompt") or metadata.get("prompt") or ""),
        "status": str(metadata.get("status") or "complete"),
        "phase": str(metadata.get("phase") or "complete"),
        "coverage_status": retrieval.get("coverage_status", "unknown"),
        "sufficient": bool(retrieval.get("sufficient", False)),
        "selected_count": len(retrieval.get("evidence", []) or []),
        "stop_reason": summary.get("stop_reason", ""),
        "response_preview": str(response.get("content") or "")[:500],
        "index_estimate": _deepcopy_json(metadata.get("index_estimate") or {}),
        "progress_percent": int(metadata.get("progress_percent") or 100),
        "progress_message": str(metadata.get("progress_message") or ""),
        "progress_logs": _plain_string_list(metadata.get("progress_logs", [])),
        **metrics,
    }


def _run_metrics(run_dir: Path, metadata: Mapping[str, Any]) -> dict[str, Any]:
    elapsed = metadata.get("elapsed_seconds")
    elapsed_seconds = float(elapsed) if isinstance(elapsed, (int, float)) else None
    output: dict[str, Any] = {
        "created_at": str(metadata.get("created_at") or ""),
        "completed_at": str(metadata.get("completed_at") or ""),
        "elapsed_seconds": elapsed_seconds,
        "token_usage": _run_token_usage(run_dir),
    }
    return output


def _run_token_usage(run_dir: Path) -> dict[str, int]:
    totals = {
        "request_count": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "cached_tokens": 0,
        "reasoning_tokens": 0,
    }
    for trace_name in ("retrieval-trace.jsonl", "orchestration-trace.jsonl"):
        for event in _load_jsonl(run_dir / trace_name):
            if str(event.get("event_type") or "") != "llm_response_received":
                continue
            payload = event.get("payload") if isinstance(event.get("payload"), Mapping) else {}
            raw = payload.get("raw_response") if isinstance(payload.get("raw_response"), Mapping) else {}
            usage = raw.get("usage") if isinstance(raw.get("usage"), Mapping) else {}
            if not usage:
                continue
            totals["request_count"] += 1
            totals["prompt_tokens"] += _int_usage_value(usage.get("prompt_tokens"))
            totals["completion_tokens"] += _int_usage_value(usage.get("completion_tokens"))
            totals["total_tokens"] += _int_usage_value(usage.get("total_tokens"))
            prompt_details = usage.get("prompt_tokens_details") if isinstance(usage.get("prompt_tokens_details"), Mapping) else {}
            completion_details = usage.get("completion_tokens_details") if isinstance(usage.get("completion_tokens_details"), Mapping) else {}
            totals["cached_tokens"] += _int_usage_value(prompt_details.get("cached_tokens"))
            totals["reasoning_tokens"] += _int_usage_value(completion_details.get("reasoning_tokens"))
    return totals


def _int_usage_value(value: Any) -> int:
    return int(value) if isinstance(value, int) and not isinstance(value, bool) else 0


def _load_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def _manifest_timestamp(path: Path, manifest: Mapping[str, Any] | None = None) -> str:
    if manifest is not None:
        for key in ("updated_at", "created_at", "built_at"):
            value = str(manifest.get(key) or "").strip()
            if value:
                return value
    if not path.exists():
        return ""
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
    except OSError:
        return ""


def _manifest_scope_matches(manifest: Mapping[str, Any], expected_scope: Mapping[str, Any]) -> bool:
    return {key: manifest.get(key) for key in expected_scope} == dict(expected_scope)


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
    parser.add_argument("--tool-root", type=Path, default=Path.cwd())
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()

    Handler.state = RuntimeState(args.workspace_root, tool_root=args.tool_root)
    Handler.state.remember_workspace(args.workspace_root)
    port = _find_free_port(args.port)
    server = ThreadingHTTPServer((args.host, port), Handler)
    print(f"Guided Intelligence API serving {Handler.state.workspace_root}")
    print(f"http://{args.host}:{port}/health")
    server.serve_forever()


if __name__ == "__main__":
    main()
