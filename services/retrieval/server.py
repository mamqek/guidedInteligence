from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import secrets
import socket
import statistics
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import parse_qs, urlencode, urlparse

from core.control_layer import ControlLayer
from core.models import AssistanceRequestType, ConversationState
from core.policy import PolicyStage
from core.source_policy import DEFAULT_ALLOWED_SOURCE_CATEGORIES, SourceCategory, SourcePolicy
from services.comprehension import generate_followup
from services.guidance.answer_evaluation import evaluate_answers
from services.intent import compose_intent_flow
from services.llm.json_completion import complete_json
from services.retrieval.workspace.bm25 import DEFAULT_EXCLUDED_PATHS, estimate_indexing_scope, load_index
from services.logging.store import JsonlLogger
from services.retrieval.config import (
    DEFAULT_CODEX_PROMPT_PROFILE,
    DEFAULT_CONNECTED_CONTEXT_DISCLAIMER_REQUIRED_TERMS,
    DEFAULT_CONNECTED_CONTEXT_STALE_BLOCK_TERMS,
    RETRIEVAL_MODE_CODEX,
    RETRIEVAL_MODE_WORKSPACE,
    SUPPORTED_CODEX_PROMPT_PROFILES,
    MCPConnectedSourceConfig,
    RemoteMCPConnectedSourceConfig,
    RetrievalEmbeddingConfig,
    RetrievalQdrantConfig,
    RunLLMConfig,
    WorkspaceRetrievalConfig,
    _parse_env_file,
    load_retrieval_embedding_config,
    load_retrieval_enable_indexing,
    load_retrieval_qdrant_config,
    source_categories_from_strings,
)
from services.retrieval.evidence_graph import build_candidate_connections, build_evidence_graph
from services.retrieval.codex.provider import (
    CodexRetrievalStage,
    _codex_subprocess_env,
    _evidence_conversion_from_payload,
)
from services.retrieval.codex.cli import resolve_codex_command
from services.retrieval.workspace.mcp import (
    LocalMCPConnectedSourceAdapter,
    MCPConnectedSourceError,
    RemoteMCPConnectedSourceAdapter,
    RemoteMCPConnectedSourceError,
)
from services.retrieval.workspace.qdrant_backend import QdrantHybridBackend
from services.retrieval.workspace.tools.contracts import ToolRequest
from services.retrieval.workspace.tools.codegraph import close_codegraph_bridge
from services.retrieval.workspace import WorkspaceRetrievalStage
from services.retrieval.workspace.pipeline.execution_flow.index_setup import rebuild_index, structural_tools as build_structural_tools


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8790
CONFIG_DIR_NAME = ".guided-intelligence"
CONFIG_FILE_NAME = "config.json"
SECRETS_FILE_NAME = "secrets.json"
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
RETRIEVAL_STAGE_WINDOWS: dict[str, tuple[int, int]] = {
    "index_codegraph": (12, 36),
    "index_bm25_qdrant": (36, 52),
    "obligation_retrieval": (52, 96),
}
RETRIEVAL_STAGE_MESSAGES: dict[str, str] = {
    "index_codegraph": "Refreshing the code graph.",
    "index_bm25_qdrant": "Syncing the local search indexes.",
    "obligation_retrieval": "Resolving and connecting required evidence.",
}
DEFAULT_RETRIEVAL_STAGE_HINT_SECONDS: dict[str, float] = {
    "index_codegraph": 30.0,
    "index_bm25_qdrant": 45.0,
    "obligation_retrieval": 45.0,
}


class RetrievalServerError(RuntimeError):
    def __init__(self, message: str, *, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


class DirectoryPickerUnavailable(RuntimeError):
    pass


class RuntimeState:
    def __init__(self, workspace_root: Path, *, tool_root: Path | None = None) -> None:
        self.workspace_root = workspace_root.resolve()
        self.tool_root = (tool_root or Path.cwd()).resolve()
        self.config_path = self.workspace_root / CONFIG_DIR_NAME / CONFIG_FILE_NAME
        self.secrets_path = self.workspace_root / CONFIG_DIR_NAME / SECRETS_FILE_NAME
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
        api_status = self._api_connection_status()
        codex_status = self._codex_connection_status()
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
            "llm_configured": api_status["configured"],
            "api_llm_configured": api_status["configured"],
            "api_llm_status_detail": api_status["detail"],
            "codex_configured": codex_status["configured"],
            "codex_status_detail": codex_status["detail"],
            "embedding_configured": _config_loader_ok(load_retrieval_embedding_config, self.tool_root),
            "runs_dir": str(self.runs_root),
            "github_repository": self.github_repository(),
            "retrieval_mode": _retrieval_mode(self.config),
            "codex_prompt_profile": str(
                _retrieval_settings(self.config).get("codex_prompt_profile") or DEFAULT_CODEX_PROMPT_PROFILE
            ),
        }

    def _api_connection_status(self) -> dict[str, Any]:
        try:
            config = self._api_llm_config()
        except Exception as exc:
            return {"configured": False, "detail": str(exc)}
        return {"configured": True, "detail": f"{config.model} at {config.endpoint_url}"}

    def _codex_connection_status(self) -> dict[str, Any]:
        codex = _normalize_codex_connection(_connections_mapping(self.config).get("codex", {}), retrieval=_retrieval_settings(self.config))
        command = resolve_codex_command(_string_list(codex.get("command", ["codex"])))
        try:
            completed = subprocess.run(
                [*command, "--version"],
                cwd=str(self.workspace_root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=_codex_subprocess_env(command),
                timeout=5,
                check=False,
            )
        except Exception as exc:
            return {"configured": False, "detail": str(exc)}
        if completed.returncode != 0:
            return {"configured": False, "detail": (completed.stderr or completed.stdout or "").strip()[:300]}
        return {"configured": True, "detail": (completed.stdout or completed.stderr or "Codex CLI available").strip()}

    def codex_models(self) -> dict[str, Any]:
        retrieval_settings = _retrieval_settings(self.config)
        command = [
            *resolve_codex_command(_string_list(retrieval_settings.get("codex_command", ["codex"]))),
            "debug",
            "models",
        ]
        try:
            completed = subprocess.run(
                command,
                cwd=str(self.workspace_root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
        except FileNotFoundError as exc:
            raise RetrievalServerError(f"Codex command was not found: {command[0]}", status=404) from exc
        except subprocess.TimeoutExpired as exc:
            raise RetrievalServerError("Codex model catalog request timed out.", status=504) from exc
        except OSError as exc:
            raise RetrievalServerError(f"Codex model catalog request failed: {exc}", status=502) from exc
        stdout = completed.stdout.strip()
        stderr = completed.stderr.strip()
        if completed.returncode != 0:
            detail = stderr or stdout or f"exit code {completed.returncode}"
            raise RetrievalServerError(f"Codex model catalog request failed: {detail}", status=502)
        try:
            catalog = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise RetrievalServerError("Codex model catalog response was not valid JSON.", status=502) from exc
        return {
            "ok": True,
            "command": command,
            "models": _codex_model_options(catalog),
            "stderr": stderr,
        }

    def codex_runtime_capabilities(self) -> dict[str, Any]:
        retrieval_settings = _retrieval_settings(self.config)
        codex_command = resolve_codex_command(_string_list(retrieval_settings.get("codex_command", ["codex"])))
        mcp_command = [*codex_command, "mcp", "list", "--json"]
        mcp_probe = _codex_global_mcp_servers(mcp_command, workspace_root=self.workspace_root)
        return {
            "ok": True,
            "command": list(codex_command),
            "global_mcp": mcp_probe,
            "retrieval_overrides": _codex_retrieval_override_indicators(
                retrieval_settings,
                _normalize_codex_connection(_connections_mapping(self.config).get("codex", {}), retrieval=retrieval_settings),
            ),
            "notes": [
                "global_mcp describes the user's configured Codex MCP servers, not the tools used when Codex retrieval ignores user config.",
                "tool schemas are not listed here because Codex CLI exposes configured MCP servers deterministically, while per-tool schemas require starting each server.",
            ],
        }

    def test_api_llm_connection(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        settings = _normalize_api_llm_connection(payload or _connections_mapping(self.config).get("api_llm", {}))
        config = self._api_llm_config(model_override=str(settings.get("model") or ""), settings=settings)
        config = RunLLMConfig(
            api_style=config.api_style,
            model=config.model,
            endpoint_url=config.endpoint_url,
            api_key=config.api_key,
            temperature=config.temperature,
            max_tokens=min(config.max_tokens, 64),
            timeout_seconds=min(config.timeout_seconds, 15),
            planner_strategy=config.planner_strategy,
            continuity_enabled=False,
        )
        response = complete_json(
            config,
            (
                {"role": "system", "content": "Return JSON only."},
                {"role": "user", "content": "Return {\"ok\": true}."},
            ),
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "guided_intelligence_api_connection_test",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {"ok": {"type": "boolean"}},
                        "required": ["ok"],
                        "additionalProperties": False,
                    },
                },
            },
        )
        return {
            "ok": bool(response.get("ok")),
            "provider": "api",
            "model": config.model,
            "endpoint_url": config.endpoint_url,
        }

    def test_codex_connection(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        configured = _normalize_codex_connection(payload or _connections_mapping(self.config).get("codex", {}), retrieval=_retrieval_settings(self.config))
        command_prefix = resolve_codex_command(_string_list(configured.get("command", ["codex"])))
        command = [*command_prefix, "debug", "models"]
        try:
            completed = subprocess.run(
                command,
                cwd=str(self.workspace_root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=_codex_subprocess_env(command_prefix),
                timeout=int(configured.get("timeout_seconds") or 30),
                check=False,
            )
        except FileNotFoundError as exc:
            raise RetrievalServerError(f"Codex command was not found: {command_prefix[0]}", status=404) from exc
        except subprocess.TimeoutExpired as exc:
            raise RetrievalServerError("Codex connection test timed out.", status=504) from exc
        stdout = completed.stdout.strip()
        stderr = completed.stderr.strip()
        if completed.returncode != 0:
            detail = stderr or stdout or f"exit code {completed.returncode}"
            raise RetrievalServerError(f"Codex connection test failed: {detail}", status=502)
        try:
            catalog = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise RetrievalServerError("Codex model catalog response was not valid JSON.", status=502) from exc
        models = _codex_model_options(catalog)
        return {
            "ok": True,
            "provider": "codex",
            "command": list(command_prefix),
            "model_count": len(models),
            "models": models,
            "stderr": stderr,
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
        return self._public_config(self.config)

    def _public_config(self, config: Mapping[str, Any]) -> dict[str, Any]:
        output = _deepcopy_json(config)
        api_llm = output.get("connections", {}).get("api_llm") if isinstance(output.get("connections"), Mapping) else None
        if isinstance(api_llm, dict):
            api_llm.pop("api_key", None)
            api_llm["api_key_configured"] = self._api_llm_key_configured()
        return output

    def _load_secrets(self) -> dict[str, Any]:
        payload = _load_json(self.secrets_path, {})
        return dict(payload) if isinstance(payload, Mapping) else {}

    def _save_secrets(self, payload: Mapping[str, Any]) -> None:
        self.secrets_path.parent.mkdir(parents=True, exist_ok=True)
        self.secrets_path.write_text(json.dumps(dict(payload), indent=2, sort_keys=True), encoding="utf-8")

    def _api_llm_key(self) -> str:
        secrets_payload = self._load_secrets()
        api_llm = secrets_payload.get("api_llm")
        if not isinstance(api_llm, Mapping):
            return ""
        return str(api_llm.get("api_key") or "").strip()

    def _api_llm_key_configured(self) -> bool:
        return bool(self._api_llm_key())

    def _save_api_llm_key(self, api_key: str) -> None:
        clean_key = api_key.strip()
        if not clean_key:
            return
        payload = self._load_secrets()
        api_llm = payload.get("api_llm")
        if not isinstance(api_llm, dict):
            api_llm = {}
            payload["api_llm"] = api_llm
        api_llm["api_key"] = clean_key
        self._save_secrets(payload)

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
        redirect_uri = _oauth_redirect_uri(request_host, self.tool_root)
        if registration:
            auth_metadata = _provider_oauth_metadata(provider, endpoint_url, {})
        else:
            auth_metadata = _discover_oauth_metadata(endpoint_url)
            registration = _register_oauth_client(auth_metadata, redirect_uri=redirect_uri, provider=provider)
        verifier = _oauth_code_verifier()
        state = secrets.token_urlsafe(32)
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
        incoming_api_key = _incoming_api_llm_key(payload)
        updated = _normalize_config(_merge_config(self._default_config(), dict(payload)))
        if incoming_api_key:
            self._save_api_llm_key(incoming_api_key)
        api_llm = updated.get("connections", {}).get("api_llm") if isinstance(updated.get("connections"), Mapping) else None
        if isinstance(api_llm, dict):
            api_llm.pop("api_key", None)
            api_llm["api_key_configured"] = self._api_llm_key_configured()
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
        try:
            selected = _choose_directory(start_path)
        except DirectoryPickerUnavailable as exc:
            return {
                "workspace_root": "",
                "cancelled": True,
                "picker_available": False,
                "message": f"{exc} Paste the repository path into the field instead.",
            }
        return {
            "workspace_root": str(selected) if selected is not None else "",
            "cancelled": selected is None,
            "picker_available": True,
        }

    def index_estimate(self) -> dict[str, Any]:
        indexing = self.config.get("indexing", {})
        if not isinstance(indexing, Mapping):
            indexing = {}
        retrieval_mode = _retrieval_mode(self.config)
        exclude_paths = _string_list(indexing.get("exclude_paths", []))
        if retrieval_mode == RETRIEVAL_MODE_CODEX:
            estimate = {"file_count": 0, "total_bytes": 0, "estimated_chunks": 0, "sample_paths": []}
            return {
                **estimate,
                **_index_time_estimate(estimate),
                "exclude_paths": exclude_paths,
                "enable_indexing": False,
                "index_ready": True,
                "index_status": "codex_mode",
                "index_status_detail": "Codex retrieval mode uses the selected workspace directly and skips local indexing.",
                "index_last_built_at": "",
            }
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
        codegraph_db_path = self.workspace_root / ".codegraph" / "codegraph.db"
        bm25_manifest = _load_json(index_dir / "bm25-scope-manifest.json", {})
        expected_scope = {
            "workspace_root": str(self.workspace_root.resolve()),
            "exclude_paths": list(exclude_paths),
            "chunk_line_count": chunk_line_count,
            "chunk_line_overlap": chunk_line_overlap,
        }
        if not codegraph_db_path.exists():
            return {
                "index_ready": False,
                "index_status": "missing_or_stale",
                "index_status_detail": "CodeGraph structural index is missing.",
                "index_last_built_at": _manifest_timestamp(index_dir / "qdrant-sync-manifest.json"),
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
                phase="codegraph",
                message="Refreshing CodeGraph structural index.",
                progress_percent=5,
                log="Refreshing code graph.",
            )
            indexing_estimate = self.index_estimate()
            if not indexing_estimate.get("enable_indexing", True):
                raise RetrievalServerError("Indexing is disabled in workspace settings.", status=400)
            run_dir.mkdir(parents=True, exist_ok=True)
            stage = WorkspaceRetrievalStage(self._workspace_retrieval_config(run_dir=run_dir))
            graph_tools = build_structural_tools(stage.context)
            try:
                index_observation = graph_tools["structural_index_repo"].run(
                    ToolRequest(tool_name="structural_index_repo", arguments={}, reason="manual index preparation")
                )
            finally:
                close_codegraph_bridge(stage.config)
            stage.context.trace.record_tool(ToolRequest(tool_name="structural_index_repo", arguments={}), index_observation, round_index=0)
            if index_observation.status != "ok":
                raise RetrievalServerError(_structural_graph_failure_message(index_observation.payload), status=500)
            self._update_index_job(
                job_id,
                phase="bm25",
                message="Building BM25 workspace index.",
                progress_percent=15,
                log="Code graph refreshed.",
            )
            original_record = stage.context.trace.record

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

            stage.context.trace.record = record_progress  # type: ignore[method-assign]
            index_setup = rebuild_index(stage.context)
            index = index_setup.index
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
            "retrieval_mode": _retrieval_mode(self.config),
            "codex_prompt_profile": str(
                _retrieval_settings(self.config).get("codex_prompt_profile") or DEFAULT_CODEX_PROMPT_PROFILE
            ),
            "prompt": prompt,
            "allowed_sources": list(allowed_source_keys),
            "run_dir": str(run_dir),
            "index_estimate": indexing_estimate,
            "progress_percent": 1,
            "progress_message": "Queued explanation run.",
            "progress_logs": [],
            "progress_timeline": [],
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
        completed_embedding_batches = 0
        stage_duration_hints = _load_historical_stage_duration_hints(self.runs_root, exclude_run_id=run_id)
        try:
            retrieval_mode = _retrieval_mode(self.config)
            if retrieval_mode == RETRIEVAL_MODE_CODEX:
                embedding_config = RetrievalEmbeddingConfig(
                    model="codex-not-used",
                    endpoint_url="codex-not-used",
                    api_key="codex-not-used",
                )
            else:
                embedding_config = load_retrieval_embedding_config(self.tool_root / ".env")
            estimated_chunks = int(indexing_estimate.get("estimated_chunks") or 0)
            estimated_embedding_batches = max(1, (estimated_chunks + embedding_config.batch_size - 1) // embedding_config.batch_size)
        except Exception:
            estimated_chunks = int(indexing_estimate.get("estimated_chunks") or 0)
            estimated_embedding_batches = max(1, estimated_chunks // 32)
        retrieval_mode = _retrieval_mode(self.config)
        initial_phase = "codex" if retrieval_mode == RETRIEVAL_MODE_CODEX else "indexing"
        self._update_run_progress(run_dir, phase=initial_phase, percent=5, message="Checking retrieval mode.")
        try:
            if retrieval_mode != RETRIEVAL_MODE_CODEX:
                self.ensure_qdrant_runtime()
            self._update_run_progress(run_dir, phase="retrieval", percent=10, message="Starting retrieval.")
            retrieval_llm_config = self._retrieval_llm_config()
            generation_llm_config = self._generation_llm_config()
            retrieval_config = self._workspace_retrieval_config(
                run_dir=run_dir,
                enabled_source_categories=tuple(allowed_categories),
                enabled_sources=tuple(allowed_source_keys),
                llm_config=retrieval_llm_config,
            )
            if retrieval_config.retrieval_mode == RETRIEVAL_MODE_CODEX:
                retrieval_stage = CodexRetrievalStage(retrieval_config)
            else:
                retrieval_stage = WorkspaceRetrievalStage(retrieval_config)
            if isinstance(retrieval_stage, WorkspaceRetrievalStage):
                original_record = retrieval_stage.context.trace.record
            else:
                original_record = retrieval_stage._record

            def record_retrieval_progress(event_type: str, event_payload: Mapping[str, Any]) -> None:
                nonlocal completed_embedding_batches
                original_record(event_type, event_payload)
                if event_type == "retrieval_stage_started":
                    stage_key = str(event_payload.get("stage_key") or "").strip()
                    if stage_key:
                        phase, percent, message, timeline_event = _progress_update_for_stage_start(
                            stage_key,
                            event_payload,
                            duration_hints=stage_duration_hints,
                        )
                        self._update_run_progress(run_dir, phase=phase, percent=percent, message=message, log=message, timeline_event=timeline_event)
                elif event_type == "retrieval_stage_completed":
                    stage_key = str(event_payload.get("stage_key") or "").strip()
                    if stage_key:
                        observed_seconds = _elapsed_seconds_from_payload(event_payload)
                        if observed_seconds is not None:
                            stage_duration_hints[stage_key] = observed_seconds
                        phase, percent, message, log, timeline_event = _progress_update_for_stage_completion(
                            stage_key,
                            event_payload,
                            duration_hints=stage_duration_hints,
                        )
                        self._update_run_progress(run_dir, phase=phase, percent=percent, message=message, log=log, timeline_event=timeline_event)
                elif event_type == "workspace_bm25_index_reused":
                    self._update_run_progress(run_dir, phase="qdrant", percent=44, message="Local search index is already in sync.", log="BM25 index reused.")
                elif event_type == "workspace_bm25_index_rebuilt":
                    self._update_run_progress(run_dir, phase="qdrant", percent=45, message="BM25 index rebuilt; syncing embeddings.", log="BM25 index rebuilt.")
                elif event_type == "embedding_batch_completed":
                    completed_embedding_batches += 1
                    display_total = max(estimated_embedding_batches, completed_embedding_batches)
                    stage_start, stage_end = RETRIEVAL_STAGE_WINDOWS["index_bm25_qdrant"]
                    percent = stage_start + int(min(1.0, completed_embedding_batches / display_total) * max(1, stage_end - stage_start - 1))
                    self._update_run_progress(
                        run_dir,
                        phase="embeddings",
                        percent=percent,
                        message=f"Syncing embeddings into Qdrant ({completed_embedding_batches}/{display_total} batches).",
                    )
                elif event_type == "workspace_index_reused":
                    self._update_run_progress(run_dir, phase="retrieval", percent=46, message="Index is ready.", log="Index ready.")
                elif event_type == "codex_retrieval_started":
                    self._update_run_progress(
                        run_dir,
                        phase="codex",
                        percent=20,
                        message="Asking Codex for code evidence.",
                        log="Codex retrieval started.",
                        timeline_event=_codex_retrieval_progress_start_event(retrieval_config.codex_timeout_seconds),
                    )
                elif event_type == "codex_retrieval_completed":
                    self._update_run_progress(
                        run_dir,
                        phase="codex",
                        percent=86,
                        message="Codex evidence received.",
                        log="Codex evidence received.",
                        timeline_event=_codex_retrieval_progress_completed_event(),
                    )

            if isinstance(retrieval_stage, WorkspaceRetrievalStage):
                retrieval_stage.context.trace.record = record_retrieval_progress  # type: ignore[method-assign]
            else:
                retrieval_stage._record = record_retrieval_progress  # type: ignore[method-assign]
            policy = PolicyStage(SourcePolicy(allowed_categories=tuple(allowed_categories), policy_name="local_web_ui"))
            progress_logger = _ProgressJsonlLogger(run_dir / "orchestration-trace.jsonl", run_dir)
            control = ControlLayer(
                policy_stage=policy,
                retrieval_stage=retrieval_stage,
                logger=progress_logger,
                response_llm_config=generation_llm_config,
                intent_enabled=True,
                # Observational only; production profiles leave this disabled.
                intent_sufficiency_enabled=bool(_experiments_settings(self.config).get("intent_sufficiency_enabled", False)),
                evidence_graph_builder=lambda retrieval_result, graph_state, record_event: build_evidence_graph(
                    retrieval_result,
                    workspace_root=self.workspace_root,
                    user_prompt=graph_state.user_input,
                    llm_config=generation_llm_config,
                    organizer_enabled=(
                        retrieval_config.retrieval_mode == RETRIEVAL_MODE_CODEX
                        and retrieval_config.codex_evidence_organizer_enabled
                    ),
                    neutralize_candidate_order=bool(
                        _experiments_settings(self.config).get("codex_candidate_order_neutralization_enabled", True)
                    ),
                    intent_flow=(
                        compose_intent_flow(graph_state.intent_context.intents).to_generation_dict()
                        if graph_state.intent_context is not None and graph_state.intent_context.intents
                        else {}
                    ),
                    log_event=record_event,
                ),
                multi_intent_stage_order_neutralization_enabled=bool(
                    _experiments_settings(self.config).get("multi_intent_stage_order_neutralization_enabled", False)
                ),
            )
            state = ConversationState(
                conversation_id=run_id,
                user_input=prompt,
                assistance_request=AssistanceRequestType.UNDERSTAND_CODE,
            )
            result = control.run(state)
            retry_count = 0
            if _response_generation_timed_out(result.to_dict()):
                retry_count = 1
                self._update_run_progress(
                    run_dir,
                    phase="generation",
                    percent=92,
                    message="Explanation generation timed out; retrying retrieval once.",
                    log="Explanation generation timed out; retrying retrieval once.",
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
            logs = list(metadata.get("progress_logs", [])) if isinstance(metadata.get("progress_logs"), list) else []
            final_generation_error = _response_generation_error(result_payload)
            final_generation_timeout = _response_generation_timed_out(result_payload)
            if retry_count and not final_generation_error:
                logs.append("Retry completed successfully.")
            if retry_count and final_generation_timeout:
                logs.append("Retry also timed out; showing explicit explanation error.")
            metadata.update(
                {
                    "run_id": run_id,
                    "status": "complete",
                    "phase": "complete",
                    "completed_at": completed_at.isoformat(),
                    "elapsed_seconds": round((completed_at - started_at).total_seconds(), 2),
                    "progress_percent": 100,
                    "progress_message": _response_generation_progress_message(final_generation_error, retry_count=retry_count),
                    "workspace_root": str(self.workspace_root),
                    "prompt": prompt,
                    "allowed_sources": list(allowed_source_keys),
                    "run_dir": str(run_dir),
                    "index_estimate": indexing_estimate,
                    "progress_active_stage": {},
                    "retry_count": retry_count,
                    "progress_logs": logs[-8:],
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
                    "progress_active_stage": {},
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
        timeline_event: Mapping[str, Any] | None = None,
    ) -> None:
        _update_run_metadata_progress(run_dir, phase=phase, percent=percent, message=message, log=log, timeline_event=timeline_event)

    def _api_llm_config(
        self,
        *,
        model_override: str = "",
        max_tokens_override: int | None = None,
        timeout_override: int | None = None,
        settings: Mapping[str, Any] | None = None,
    ) -> RunLLMConfig:
        api_settings = settings or _connections_mapping(self.config).get("api_llm", {})
        api_settings = _normalize_api_llm_connection(api_settings)
        model = model_override.strip() or str(api_settings.get("model") or "").strip()
        endpoint_url = str(api_settings.get("endpoint_url") or "").strip()
        api_key = str(api_settings.get("api_key") or "").strip() or self._api_llm_key()
        api_style = str(api_settings.get("api_style") or "").strip() or "openai_chat_completions"
        if not model or not endpoint_url or not api_key:
            raise ValueError("OpenAI-compatible API connection requires endpoint URL, API key, and model.")
        return RunLLMConfig(
            api_style=api_style,
            model=model,
            endpoint_url=endpoint_url,
            api_key=api_key,
            temperature=float(api_settings.get("temperature") if api_settings.get("temperature") is not None else 0.0),
            max_tokens=max_tokens_override or int(api_settings.get("max_tokens") or 800),
            timeout_seconds=timeout_override or int(api_settings.get("timeout_seconds") or 30),
            continuity_enabled=False,
        )

    def _codex_llm_config(self, *, model: str, timeout_seconds: int | None = None) -> RunLLMConfig:
        codex = _normalize_codex_connection(_connections_mapping(self.config).get("codex", {}), retrieval=_retrieval_settings(self.config))
        resolved_model = model.strip() or str(_retrieval_settings(self.config).get("codex_model") or "gpt-5.4-mini").strip() or "gpt-5.4-mini"
        return RunLLMConfig(
            api_style="codex_cli",
            model=resolved_model,
            timeout_seconds=timeout_seconds or int(codex.get("timeout_seconds") or 30),
            codex_command=tuple(resolve_codex_command(_string_list(codex.get("command", ["codex"])))),
            codex_ignore_user_config=bool(codex.get("ignore_user_config", True)),
        )

    def _retrieval_llm_config(self) -> RunLLMConfig:
        retrieval = _retrieval_settings(self.config)
        if _retrieval_mode(self.config) == RETRIEVAL_MODE_CODEX:
            generation = _generation_settings(self.config)
            if str(generation.get("provider") or "api") == "codex":
                return self._codex_llm_config(model=str(generation.get("codex_model") or retrieval.get("codex_model") or ""))
        return self._api_llm_config(model_override=str(retrieval.get("workspace_model") or ""))

    def _generation_llm_config(self) -> RunLLMConfig:
        generation = _generation_settings(self.config)
        if str(generation.get("provider") or "api") == "codex":
            return self._codex_llm_config(
                model=str(generation.get("codex_model") or _retrieval_settings(self.config).get("codex_model") or ""),
                timeout_seconds=int(generation.get("timeout_seconds") or 120),
            )
        return self._api_llm_config(
            model_override=str(generation.get("api_model") or ""),
            max_tokens_override=int(generation.get("max_tokens") or 4000),
            timeout_override=int(generation.get("timeout_seconds") or 120),
        )

    def _workspace_retrieval_config(
        self,
        *,
        run_dir: str | Path,
        enabled_source_categories: tuple[SourceCategory, ...] | None = None,
        enabled_sources: tuple[str, ...] | None = None,
        llm_config: RunLLMConfig | None = None,
    ) -> WorkspaceRetrievalConfig:
        tool_env_path = self.tool_root / ".env"
        indexing = self.config.get("indexing", {})
        if not isinstance(indexing, Mapping):
            indexing = {}
        connected_context = self.config.get("connected_context", {})
        if not isinstance(connected_context, Mapping):
            connected_context = {}
        index_exclude_paths = tuple(_string_list(indexing.get("exclude_paths", [])))
        connections = _connections_mapping(self.config)
        retrieval_settings = _retrieval_settings(self.config)
        codex_settings = _normalize_codex_connection(connections.get("codex", {}), retrieval=retrieval_settings)
        retrieval_mode = _retrieval_mode(self.config)
        if retrieval_mode == RETRIEVAL_MODE_CODEX:
            embedding_config = RetrievalEmbeddingConfig(
                model="codex-not-used",
                endpoint_url="codex-not-used",
                api_key="codex-not-used",
            )
            qdrant_config = RetrievalQdrantConfig(
                url="codex-not-used",
                collection_name="codex_not_used",
                timeout_seconds=30,
            )
        else:
            embedding_config = load_retrieval_embedding_config(tool_env_path)
            qdrant_config = load_retrieval_qdrant_config(tool_env_path)
        return WorkspaceRetrievalConfig(
            workspace_root=str(self.workspace_root),
            index_dir=str(self.workspace_root / CONFIG_DIR_NAME / "index"),
            run_dir=str(run_dir),
            llm_config=llm_config or self._retrieval_llm_config(),
            embedding_config=embedding_config,
            qdrant_config=qdrant_config,
            retrieval_mode=retrieval_mode,
            codex_command=resolve_codex_command(_string_list(retrieval_settings.get("codex_command", ["codex"]))),
            codex_model=str(retrieval_settings.get("codex_model") or "gpt-5.4-mini").strip() or "gpt-5.4-mini",
            codex_prompt_profile=str(
                retrieval_settings.get("codex_prompt_profile") or DEFAULT_CODEX_PROMPT_PROFILE
            ).strip().lower(),
            codex_timeout_seconds=int(retrieval_settings.get("codex_timeout_seconds") or 900),
            codex_ignore_user_config=bool(codex_settings.get("ignore_user_config", True)),
            codex_evidence_organizer_enabled=bool(
                _experiments_settings(self.config).get("codex_evidence_organizer_enabled", True)
            ),
            enable_indexing=bool(indexing.get("enable_indexing", load_retrieval_enable_indexing(tool_env_path))),
            structural_graph_timeout_seconds=900,
            index_exclude_paths=index_exclude_paths,
            enabled_source_categories=enabled_source_categories if enabled_source_categories is not None else tuple(DEFAULT_ALLOWED_SOURCE_CATEGORIES),
            enabled_sources=enabled_sources if enabled_sources is not None else tuple(_enabled_sources_from_config(self.config)),
            connected_context_enabled=bool(connected_context.get("enabled", True)),
            connected_context_max_sources=int(connected_context.get("max_sources") or 8),
            connected_context_max_calls=int(connected_context.get("max_calls") or 8),
            connected_context_max_candidates_per_source=int(
                connected_context.get("max_candidates_per_source") or 5
            ),
            connected_context_max_candidates_total=int(connected_context.get("max_candidates_total") or 20),
            connected_context_max_candidate_chars=int(connected_context.get("max_candidate_chars") or 2400),
            connected_context_max_candidate_chars_total=int(
                connected_context.get("max_candidate_chars_total") or 24000
            ),
            connected_context_max_selected_context=int(connected_context.get("max_selected_context") or 4),
            connected_context_max_selected_evidence=int(connected_context.get("max_selected_evidence") or 2),
            connected_context_timeout_seconds=int(connected_context.get("timeout_seconds") or 45),
            connected_context_disclaimer_required_terms=tuple(
                _string_list(
                    connected_context.get(
                        "disclaimer_required_terms",
                        list(DEFAULT_CONNECTED_CONTEXT_DISCLAIMER_REQUIRED_TERMS),
                    )
                )
            ),
            connected_context_stale_block_terms=tuple(
                _string_list(
                    connected_context.get(
                        "stale_block_terms",
                        list(DEFAULT_CONNECTED_CONTEXT_STALE_BLOCK_TERMS),
                    )
                )
            ),
            remote_mcp_connected_sources=_configured_remote_mcp_sources(self.config, self.provider_auth()),
            mcp_connected_sources=_configured_mcp_sources(self.config),
        )

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
        llm_config = self._generation_llm_config()
        evaluations = evaluate_answers(
            checks=tuple(item for item in checks if isinstance(item, Mapping)),
            answers={str(key): str(value) for key, value in answers.items()},
            llm_config=llm_config,
        )
        output = {
            "run_id": run_id,
            "evaluations": [evaluation.to_dict() for evaluation in evaluations],
        }
        answer_flow = metadata.get("answer_flow", {})
        story_flow = metadata.get("story_flow", ())
        if isinstance(answer_flow, Mapping) and isinstance(story_flow, list):
            followup = generate_followup(
                answer_flow=answer_flow,
                story_flow=tuple(item for item in story_flow if isinstance(item, Mapping)),
                checks=tuple(item for item in checks if isinstance(item, Mapping)),
                evaluations=tuple(evaluation.to_dict() for evaluation in evaluations),
                answers={str(key): str(value) for key, value in answers.items()},
                llm_config=llm_config,
            )
            output["comprehension_followup"] = followup.to_dict()
            (run_dir / "comprehension-followup.json").write_text(
                json.dumps(followup.to_dict(), indent=2, sort_keys=True),
                encoding="utf-8",
            )
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
        evidence = _load_json(run_dir / "evidence-items.json", [])
        candidate_evidence = _run_candidate_evidence(run_dir, result, evidence)
        evidence_connections = _with_historical_candidate_connections(
            run_dir,
            result,
            _run_evidence_connections(result),
        )
        return {
            **_run_summary_from_payload(run_id, run_dir, result),
            "result": result,
            "evidence": evidence,
            "candidate_evidence": candidate_evidence,
            "evidence_connections": evidence_connections,
            "evidence_organization": _run_evidence_organization(result),
            "answer_evaluation": _load_json(run_dir / "answer-evaluation.json", {}),
            "comprehension_followup": _load_json(run_dir / "comprehension-followup.json", {}),
        }

    def run_trace(self, run_id: str) -> dict[str, Any]:
        run_dir = self._run_dir(run_id)
        return {
            "run_id": run_id,
            "retrieval_trace": _load_jsonl(run_dir / "retrieval-trace.jsonl"),
            "orchestration_trace": _load_jsonl(run_dir / "orchestration-trace.jsonl"),
        }

    def open_source_file(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self._open_source_file_from_root(self.workspace_root, payload)

    def open_run_source_file(self, run_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        run_dir = self._run_dir(run_id)
        if not run_dir.exists():
            raise RetrievalServerError(f"Run not found: {run_id}", status=404)
        return self._open_source_file_from_root(_run_workspace_root(run_dir) or self.workspace_root, payload)

    def _open_source_file_from_root(self, source_root: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
        raw_path = str(payload.get("path") or "").strip().replace("\\", "/").lstrip("/")
        if not raw_path:
            raise RetrievalServerError("Missing source file path.", status=400)
        line = ""
        if "#" in raw_path:
            raw_path, line = raw_path.split("#", 1)
        candidate = (source_root / raw_path).resolve()
        try:
            candidate.relative_to(source_root)
        except ValueError:
            raise RetrievalServerError("Source file path must stay inside the workspace.", status=400)
        if not candidate.is_file():
            raise RetrievalServerError(f"Source file not found: {raw_path}", status=404)
        vscode_url = _vscode_file_url(candidate, line)
        if os.name == "nt":
            os.startfile(vscode_url)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", vscode_url])
        else:
            subprocess.Popen(["xdg-open", vscode_url])
        return {"opened": True, "path": str(candidate), "vscode_url": vscode_url}

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
        config = _normalize_config(_merge_config(self._default_config(), dict(payload)))
        inline_api_key = _incoming_api_llm_key(config)
        if inline_api_key:
            self._save_api_llm_key(inline_api_key)
            api_llm = config.get("connections", {}).get("api_llm") if isinstance(config.get("connections"), Mapping) else None
            if isinstance(api_llm, dict):
                api_llm.pop("api_key", None)
                api_llm["api_key_configured"] = True
        return config

    def _default_config(self) -> dict[str, Any]:
        return {
            "workspace_root": str(self.workspace_root),
            "runs_dir": f"{CONFIG_DIR_NAME}/{RUNS_DIR_NAME}",
            "enabled_source_categories": [source.value for source in DEFAULT_ALLOWED_SOURCE_CATEGORIES],
            "enabled_sources": list(DEFAULT_ALLOWED_SOURCE_KEYS),
            "connections": {
                "api_llm": _default_api_llm_connection(),
                "codex": _default_codex_connection(),
                "remote_mcp_sources": _default_remote_mcp_sources(),
                "mcp_sources": [],
            },
            "indexing": {
                "enable_indexing": load_retrieval_enable_indexing(self.tool_root / ".env"),
                "exclude_paths": list(DEFAULT_EXCLUDED_PATHS),
            },
            "retrieval": {
                "mode": RETRIEVAL_MODE_WORKSPACE,
                "codex_command": ["codex"],
                "codex_model": "gpt-5.4-mini",
                "workspace_model": "",
                "codex_prompt_profile": DEFAULT_CODEX_PROMPT_PROFILE,
                "codex_timeout_seconds": 900,
            },
            "generation": {
                "provider": "api",
                "api_model": "gpt-5.6-luna",
                "codex_model": "gpt-5.4-mini",
                "max_tokens": 4000,
                "timeout_seconds": 120,
            },
            "experiments": {
                "codex_evidence_organizer_enabled": True,
                "codex_candidate_order_neutralization_enabled": True,
                "multi_intent_stage_order_neutralization_enabled": False,
                "intent_sufficiency_enabled": False,
            },
            "connected_context": {
                "enabled": True,
                "max_sources": 8,
                "max_calls": 8,
                "max_candidates_per_source": 5,
                "max_candidates_total": 20,
                "max_candidate_chars": 2400,
                "max_candidate_chars_total": 24000,
                "max_selected_context": 4,
                "max_selected_evidence": 2,
                "timeout_seconds": 45,
                "disclaimer_required_terms": list(DEFAULT_CONNECTED_CONTEXT_DISCLAIMER_REQUIRED_TERMS),
                "stale_block_terms": list(DEFAULT_CONNECTED_CONTEXT_STALE_BLOCK_TERMS),
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
            if parsed.path == "/codex/models":
                self._send_json(self.state.codex_models())
                return
            if parsed.path == "/codex/runtime-capabilities":
                self._send_json(self.state.codex_runtime_capabilities())
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
            if parsed.path == "/connections/api-llm/test":
                self._send_json(self.state.test_api_llm_connection(payload))
                return
            if parsed.path == "/connections/codex/test":
                self._send_json(self.state.test_codex_connection(payload))
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
            if parsed.path == "/source/open":
                self._send_json(self.state.open_source_file(payload))
                return
            run_source_match = re.fullmatch(r"/runs/([^/]+)/source/open", parsed.path)
            if run_source_match:
                self._send_json(self.state.open_run_source_file(run_source_match.group(1), payload))
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
    timeline_event: Mapping[str, Any] | None = None,
) -> None:
    metadata_path = run_dir / "run-metadata.json"
    metadata = _load_json(metadata_path, {})
    logs = list(metadata.get("progress_logs", [])) if isinstance(metadata.get("progress_logs"), list) else []
    timeline = list(metadata.get("progress_timeline", [])) if isinstance(metadata.get("progress_timeline"), list) else []
    if log:
        logs.append(log)
    if timeline_event:
        timeline.append(dict(timeline_event))
    active_stage = dict(metadata.get("progress_active_stage", {})) if isinstance(metadata.get("progress_active_stage"), Mapping) else {}
    if timeline_event:
        event_kind = str(timeline_event.get("event") or "")
        if event_kind == "stage_started":
            active_stage = dict(timeline_event)
        elif event_kind == "stage_completed":
            active_stage = {}
    metadata.update(
        {
            "status": "running",
            "phase": phase,
            "progress_percent": max(0, min(99, percent)),
            "progress_message": message,
            "progress_logs": logs[-8:],
            "progress_timeline": timeline[-64:],
            "progress_active_stage": active_stage,
        }
    )
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")


def _orchestration_progress_for_event(event_type: str) -> tuple[int, str, str, str | None] | None:
    mapping: dict[str, tuple[int, str, str, str | None]] = {
        "run_started": (12, "policy", "Analyzing request.", None),
        "turn_decision": (16, "policy", "Checking source policy.", None),
        "retrieval_plan": (22, "planning", "Preparing retrieval.", None),
        "evidence_graph_generation_started": (87, "graph", "Connecting selected evidence.", "Evidence graph generation started."),
        "evidence_graph_cache_hit": (88, "graph", "Reusing evidence graph.", "Evidence graph cache reused."),
        "evidence_graph_generation_completed": (88, "graph", "Evidence graph ready.", "Evidence graph generated."),
        "evidence_graph_generation_failed": (88, "graph", "Evidence graph generation failed.", "Evidence graph generation failed."),
        "evidence_selected": (89, "synthesis", "Evidence selected.", "Evidence selected."),
        "response_plan": (90, "synthesis", "Planning explanation response.", None),
        "prompt_payload": (91, "synthesis", "Preparing explanation prompt.", None),
        "response_generation_requested": (93, "generation", "Generating explanation.", "Explanation generation started."),
        "response_generation_request_payload": (93, "generation", "Generating explanation.", "Explanation generation started."),
        "response_generation_received": (97, "generation", "Received explanation response.", None),
        "response_generation_response_payload": (97, "generation", "Received explanation response.", None),
        "response_payload": (99, "generation", "Finalizing explanation.", None),
        "run_completed": (99, "complete", "Finalizing run.", None),
    }
    return mapping.get(event_type)


def _progress_update_for_stage_start(
    stage_key: str,
    event_payload: Mapping[str, Any],
    *,
    duration_hints: Mapping[str, float],
) -> tuple[str, int, str, dict[str, Any]]:
    window_start, window_end = RETRIEVAL_STAGE_WINDOWS.get(stage_key, (12, 96))
    message = RETRIEVAL_STAGE_MESSAGES.get(stage_key, str(event_payload.get("stage_label") or "Working.").strip() or "Working.")
    started_at = datetime.now(timezone.utc).isoformat()
    expected_seconds = round(float(duration_hints.get(stage_key) or 0.0), 2)
    timeline_event = {
        "event": "stage_started",
        "stage_key": stage_key,
        "stage_label": str(event_payload.get("stage_label") or message).strip() or message,
        "started_at": started_at,
        "window_start_percent": window_start,
        "window_end_percent": window_end,
        "expected_seconds": expected_seconds,
    }
    return stage_key, window_start, message, timeline_event


def _progress_update_for_stage_completion(
    stage_key: str,
    event_payload: Mapping[str, Any],
    *,
    duration_hints: Mapping[str, float],
) -> tuple[str, int, str, str, dict[str, Any]]:
    window_start, window_end = RETRIEVAL_STAGE_WINDOWS.get(stage_key, (12, 96))
    message = RETRIEVAL_STAGE_MESSAGES.get(stage_key, str(event_payload.get("stage_label") or "Working.").strip() or "Working.")
    observed_seconds = _elapsed_seconds_from_payload(event_payload)
    effective_seconds = observed_seconds if observed_seconds is not None else float(duration_hints.get(stage_key) or 0.0)
    timeline_event = {
        "event": "stage_completed",
        "stage_key": stage_key,
        "stage_label": str(event_payload.get("stage_label") or message).strip() or message,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "window_start_percent": window_start,
        "window_end_percent": window_end,
        "elapsed_seconds": round(effective_seconds, 2),
    }
    return stage_key, max(window_start, window_end - 1), message, f"{message.rstrip('.')}{_duration_suffix(observed_seconds)}.", timeline_event


def _codex_retrieval_progress_start_event(timeout_seconds: int) -> dict[str, Any]:
    expected_seconds = min(180.0, max(45.0, float(timeout_seconds) * 0.35))
    return {
        "event": "stage_started",
        "stage_key": "codex_retrieval",
        "stage_label": "Asking Codex for code evidence.",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "window_start_percent": 20,
        "window_end_percent": 86,
        "expected_seconds": round(expected_seconds, 2),
    }


def _codex_retrieval_progress_completed_event() -> dict[str, Any]:
    return {
        "event": "stage_completed",
        "stage_key": "codex_retrieval",
        "stage_label": "Codex evidence received.",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "window_start_percent": 20,
        "window_end_percent": 86,
    }


def _response_generation_timed_out(result_payload: Mapping[str, Any]) -> bool:
    error = _response_generation_error(result_payload)
    return "timed out" in error.casefold() or "timeout" in error.casefold()


def _response_generation_error(result_payload: Mapping[str, Any]) -> str:
    response = result_payload.get("response_payload")
    if not isinstance(response, Mapping):
        return ""
    metadata = response.get("metadata")
    if not isinstance(metadata, Mapping):
        return ""
    return str(metadata.get("error") or "")


def _response_generation_progress_message(error: str, *, retry_count: int) -> str:
    if not error:
        return "Explanation complete."
    if retry_count and ("timed out" in error.casefold() or "timeout" in error.casefold()):
        return "Explanation generation timed out after retry."
    if retry_count:
        return f"Explanation generation failed after retry: {error}"
    return f"Explanation generation failed: {error}"


def _elapsed_seconds_from_payload(payload: Mapping[str, Any]) -> float | None:
    elapsed_ms = payload.get("elapsed_ms")
    if isinstance(elapsed_ms, (int, float)) and not isinstance(elapsed_ms, bool):
        return max(0.0, float(elapsed_ms) / 1000.0)
    elapsed_seconds = payload.get("elapsed_seconds")
    if isinstance(elapsed_seconds, (int, float)) and not isinstance(elapsed_seconds, bool):
        return max(0.0, float(elapsed_seconds))
    return None


def _duration_suffix(seconds: float | None) -> str:
    if seconds is None or seconds <= 0:
        return ""
    return f" in {_format_elapsed_compact(seconds)}"


def _format_elapsed_compact(seconds: float) -> str:
    total_seconds = max(0, int(round(seconds)))
    minutes, remaining_seconds = divmod(total_seconds, 60)
    if minutes <= 0:
        return f"{remaining_seconds}s"
    hours, remaining_minutes = divmod(minutes, 60)
    if hours <= 0:
        return f"{remaining_minutes}m {remaining_seconds}s"
    return f"{hours}h {remaining_minutes}m {remaining_seconds}s"


def _subquery_progress_percent(stage_key: str, *, completed: int, total: int) -> int:
    window_start, window_end = RETRIEVAL_STAGE_WINDOWS.get(stage_key, (12, 96))
    usable_width = max(1, window_end - window_start - 1)
    ratio = min(1.0, max(0.0, completed / max(total, 1)))
    return window_start + int(usable_width * ratio)


def _load_historical_stage_duration_hints(runs_root: Path, *, exclude_run_id: str) -> dict[str, float]:
    durations: dict[str, list[float]] = {}
    hints = dict(DEFAULT_RETRIEVAL_STAGE_HINT_SECONDS)
    if not runs_root.exists():
        return hints
    try:
        run_dirs = sorted((path for path in runs_root.iterdir() if path.is_dir()), key=lambda item: item.stat().st_mtime, reverse=True)
    except OSError:
        return hints
    for run_dir in run_dirs[:24]:
        if run_dir.name == exclude_run_id:
            continue
        metadata = _load_json(run_dir / "run-metadata.json", {})
        timeline = metadata.get("progress_timeline") if isinstance(metadata.get("progress_timeline"), list) else []
        for entry in timeline:
            if not isinstance(entry, Mapping):
                continue
            if str(entry.get("event") or "") != "stage_completed":
                continue
            stage_key = str(entry.get("stage_key") or "").strip()
            elapsed_seconds = entry.get("elapsed_seconds")
            if not stage_key or not isinstance(elapsed_seconds, (int, float)) or isinstance(elapsed_seconds, bool) or elapsed_seconds <= 0:
                continue
            durations.setdefault(stage_key, []).append(float(elapsed_seconds))
    for stage_key, samples in durations.items():
        if samples:
            hints[stage_key] = float(statistics.median(samples))
    return hints


def _display_progress_percent(metadata: Mapping[str, Any]) -> int:
    stored = int(metadata.get("progress_percent") or 0)
    if str(metadata.get("status") or "") != "running":
        return stored
    active_stage = metadata.get("progress_active_stage")
    if not isinstance(active_stage, Mapping):
        return stored
    stage_start = active_stage.get("started_at")
    if not isinstance(stage_start, str) or not stage_start.strip():
        return stored
    expected_seconds = active_stage.get("expected_seconds")
    if not isinstance(expected_seconds, (int, float)) or isinstance(expected_seconds, bool) or expected_seconds <= 0:
        return stored
    try:
        started_at = datetime.fromisoformat(stage_start)
    except ValueError:
        return stored
    window_start = int(active_stage.get("window_start_percent") or stored)
    window_end = int(active_stage.get("window_end_percent") or stored)
    elapsed_seconds = max(0.0, (datetime.now(timezone.utc) - started_at).total_seconds())
    ratio = min(0.97, elapsed_seconds / float(expected_seconds))
    simulated = window_start + int(max(0, window_end - window_start) * ratio)
    return max(stored, min(99, simulated))


def _qdrant_reachable(url: str, *, timeout_seconds: float) -> bool:
    target = url.rstrip("/") + "/collections"
    request = urllib.request.Request(target, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return 200 <= int(response.status) < 500
    except (OSError, urllib.error.URLError, TimeoutError):
        return False


def _structural_graph_failure_message(payload: Mapping[str, Any]) -> str:
    reason = str(payload.get("reason") or "CodeGraph index preparation failed.").strip()
    if "timed out" in reason.lower():
        return (
            "CodeGraph index preparation timed out. The structural index did not finish within the configured timeout. "
            f"Details: {reason}"
        )
    return f"CodeGraph index preparation failed. Details: {reason}"


def _index_time_estimate(estimate: Mapping[str, Any]) -> dict[str, Any]:
    files = int(estimate.get("file_count") or 0)
    chunks = int(estimate.get("estimated_chunks") or 0)
    if files <= 0 or chunks <= 0:
        return {
            "estimated_seconds_min": 0,
            "estimated_seconds_max": 0,
            "structural_estimated_seconds_min": 0,
            "structural_estimated_seconds_max": 0,
            "index_estimate_notes": [],
        }
    min_seconds = max(10, int(chunks * 0.05 + files * 0.002))
    max_seconds = max(min_seconds + 10, int(chunks * 0.15 + files * 0.006))
    structural_midpoint_seconds = max(5, int(files * 0.006))
    structural_min_seconds = max(3, int(structural_midpoint_seconds * 0.6))
    structural_max_seconds = max(structural_min_seconds + 5, int(structural_midpoint_seconds * 1.8))
    notes: list[str] = []
    oversized_file_count = int(estimate.get("oversized_file_count") or 0)
    if oversized_file_count:
        notes.append(
            f"Skipped {oversized_file_count} files above the per-file character limit; "
            "review the excluded oversized paths if one is a required source owner."
        )
    if max_seconds > 900:
        notes.append(
            "Estimated BM25/Qdrant indexing exceeds 15 minutes. Deselect generated outputs or large corpus "
            "directories before starting an interactive run."
        )
    return {
        "estimated_seconds_min": min_seconds,
        "estimated_seconds_max": max_seconds,
        "structural_estimated_seconds_min": structural_min_seconds,
        "structural_estimated_seconds_max": structural_max_seconds,
        "index_estimate_notes": notes,
    }


def _merge_config(defaults: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    merged = _deepcopy_json(defaults)
    for key, value in payload.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), dict):
            merged[key] = _merge_config(merged[key], dict(value))
        else:
            merged[key] = value
    return merged


def _default_api_llm_connection() -> dict[str, Any]:
    return {
        "api_style": "openai_chat_completions",
        "endpoint_url": "",
        "api_key": "",
        "api_key_configured": False,
        "model": "",
        "temperature": 0.0,
        "max_tokens": 800,
        "timeout_seconds": 30,
    }


def _default_codex_connection() -> dict[str, Any]:
    return {
        "command": ["codex"],
        "ignore_user_config": True,
        "timeout_seconds": 30,
    }


def _incoming_api_llm_key(payload: Mapping[str, Any]) -> str:
    connections = payload.get("connections")
    if not isinstance(connections, Mapping):
        return ""
    api_llm = connections.get("api_llm")
    if not isinstance(api_llm, Mapping):
        return ""
    return str(api_llm.get("api_key") or "").strip()


def _normalize_api_llm_connection(value: Any) -> dict[str, Any]:
    source = value if isinstance(value, Mapping) else {}
    return {
        "api_style": str(source.get("api_style") or "openai_chat_completions").strip() or "openai_chat_completions",
        "endpoint_url": str(source.get("endpoint_url") or "").strip(),
        "api_key": str(source.get("api_key") or "").strip(),
        "api_key_configured": bool(source.get("api_key_configured", False)),
        "model": str(source.get("model") or "").strip(),
        "temperature": _float_setting(source.get("temperature"), 0.0),
        "max_tokens": max(1, _int_setting(source.get("max_tokens"), 800)),
        "timeout_seconds": max(1, _int_setting(source.get("timeout_seconds"), 30)),
    }


def _normalize_codex_connection(value: Any, *, retrieval: Mapping[str, Any]) -> dict[str, Any]:
    source = value if isinstance(value, Mapping) else {}
    command = source.get("command", retrieval.get("codex_command", ["codex"]))
    if isinstance(command, str):
        command = [command]
    return {
        "command": _string_list(command) or ["codex"],
        "ignore_user_config": _boolean_setting(source.get("ignore_user_config"), bool(retrieval.get("codex_ignore_user_config", True))),
        "timeout_seconds": max(1, _int_setting(source.get("timeout_seconds"), 30)),
    }


def _int_setting(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _float_setting(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_config(config: dict[str, Any]) -> dict[str, Any]:
    retrieval = config.get("retrieval")
    if not isinstance(retrieval, dict):
        retrieval = {}
        config["retrieval"] = retrieval
    retrieval["mode"] = str(retrieval.get("mode") or RETRIEVAL_MODE_WORKSPACE).strip().lower()
    if retrieval["mode"] not in {RETRIEVAL_MODE_WORKSPACE, RETRIEVAL_MODE_CODEX}:
        retrieval["mode"] = RETRIEVAL_MODE_WORKSPACE
    command = retrieval.get("codex_command", ["codex"])
    if isinstance(command, str):
        command = [command]
    retrieval["codex_command"] = _string_list(command) or ["codex"]
    retrieval["codex_model"] = str(retrieval.get("codex_model") or "gpt-5.4-mini").strip() or "gpt-5.4-mini"
    retrieval["workspace_model"] = str(retrieval.get("workspace_model") or "").strip()
    retrieval["codex_prompt_profile"] = str(
        retrieval.get("codex_prompt_profile") or DEFAULT_CODEX_PROMPT_PROFILE
    ).strip().lower()
    try:
        timeout_seconds = int(retrieval.get("codex_timeout_seconds") or 900)
    except (TypeError, ValueError):
        timeout_seconds = 900
    retrieval["codex_timeout_seconds"] = timeout_seconds
    generation = config.get("generation")
    if not isinstance(generation, dict):
        generation = {}
        config["generation"] = generation
    generation["provider"] = str(generation.get("provider") or "api").strip().lower()
    if generation["provider"] not in {"api", "codex"}:
        generation["provider"] = "api"
    generation["api_model"] = str(generation.get("api_model") or "").strip()
    generation["codex_model"] = str(generation.get("codex_model") or retrieval["codex_model"]).strip() or retrieval["codex_model"]
    try:
        generation_max_tokens = int(generation.get("max_tokens") or 4000)
    except (TypeError, ValueError):
        generation_max_tokens = 4000
    generation["max_tokens"] = max(1, generation_max_tokens)
    try:
        generation_timeout_seconds = int(generation.get("timeout_seconds") or 120)
    except (TypeError, ValueError):
        generation_timeout_seconds = 120
    generation["timeout_seconds"] = max(1, generation_timeout_seconds)
    config.pop("assistance", None)
    retrieval.pop("max_gap_retrieval_passes", None)
    config.pop("intent", None)
    experiments = config.get("experiments")
    if not isinstance(experiments, dict):
        experiments = {}
        config["experiments"] = experiments
    experiments["intent_sufficiency_enabled"] = _boolean_setting(
        experiments.get("intent_sufficiency_enabled"), False
    )
    experiments["codex_evidence_organizer_enabled"] = _boolean_setting(
        experiments.get("codex_evidence_organizer_enabled"), True
    )
    experiments["codex_candidate_order_neutralization_enabled"] = _boolean_setting(
        experiments.get("codex_candidate_order_neutralization_enabled"), True
    )
    experiments["multi_intent_stage_order_neutralization_enabled"] = _boolean_setting(
        experiments.get("multi_intent_stage_order_neutralization_enabled"), False
    )
    indexing = config.get("indexing")
    if isinstance(indexing, dict):
        indexing.pop("include_paths", None)
    connected_context = config.get("connected_context")
    if not isinstance(connected_context, dict):
        connected_context = {}
        config["connected_context"] = connected_context
    connected_context["disclaimer_required_terms"] = _normalize_string_list_setting(
        connected_context.get("disclaimer_required_terms"),
        DEFAULT_CONNECTED_CONTEXT_DISCLAIMER_REQUIRED_TERMS,
    )
    connected_context["stale_block_terms"] = _normalize_string_list_setting(
        connected_context.get("stale_block_terms"),
        DEFAULT_CONNECTED_CONTEXT_STALE_BLOCK_TERMS,
    )
    connections = config.get("connections")
    if not isinstance(connections, dict):
        connections = {}
        config["connections"] = connections
    connections["api_llm"] = _normalize_api_llm_connection(connections.get("api_llm", {}))
    connections["codex"] = _normalize_codex_connection(connections.get("codex", {}), retrieval=retrieval)
    retrieval.pop("codex_ignore_user_config", None)
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


def _normalize_string_list_setting(value: Any, defaults: tuple[str, ...]) -> list[str]:
    if isinstance(value, str):
        raw_values = value.split(",")
    elif isinstance(value, list):
        raw_values = value
    else:
        raw_values = list(defaults)
    normalized: list[str] = []
    for item in raw_values:
        text = str(item).strip()
        if text and text not in normalized:
            normalized.append(text)
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
    retrieval = payload.get("retrieval", {})
    if not isinstance(retrieval, Mapping):
        raise RetrievalServerError("`retrieval` must be an object.")
    mode = str(retrieval.get("mode") or RETRIEVAL_MODE_WORKSPACE).strip()
    if mode not in {RETRIEVAL_MODE_WORKSPACE, RETRIEVAL_MODE_CODEX}:
        raise RetrievalServerError("`retrieval.mode` must be either `workspace` or `codex`.")
    command = retrieval.get("codex_command", [])
    if not isinstance(command, list) or not _string_list(command):
        raise RetrievalServerError("`retrieval.codex_command` must be a non-empty array.")
    if not str(retrieval.get("codex_model") or "").strip():
        raise RetrievalServerError("`retrieval.codex_model` is required.")
    prompt_profile = str(retrieval.get("codex_prompt_profile") or "").strip()
    if prompt_profile not in SUPPORTED_CODEX_PROMPT_PROFILES:
        raise RetrievalServerError(
            "`retrieval.codex_prompt_profile` must be one of: "
            + ", ".join(SUPPORTED_CODEX_PROMPT_PROFILES)
            + "."
        )
    try:
        codex_timeout_seconds = int(retrieval.get("codex_timeout_seconds") or 0)
    except (TypeError, ValueError) as exc:
        raise RetrievalServerError("`retrieval.codex_timeout_seconds` must be an integer.") from exc
    if codex_timeout_seconds <= 0:
        raise RetrievalServerError("`retrieval.codex_timeout_seconds` must be greater than zero.")
    if "codex_ignore_user_config" in retrieval and not isinstance(retrieval.get("codex_ignore_user_config"), bool):
        raise RetrievalServerError("`retrieval.codex_ignore_user_config` must be a boolean.")
    generation = payload.get("generation", {})
    if not isinstance(generation, Mapping):
        raise RetrievalServerError("`generation` must be an object.")
    if str(generation.get("provider") or "api") not in {"api", "codex"}:
        raise RetrievalServerError("`generation.provider` must be either `api` or `codex`.")
    if str(generation.get("provider") or "api") == "api" and "api_model" in generation and not isinstance(generation.get("api_model"), str):
        raise RetrievalServerError("`generation.api_model` must be a string.")
    if str(generation.get("provider") or "api") == "codex" and not str(generation.get("codex_model") or "").strip():
        raise RetrievalServerError("`generation.codex_model` is required when generation.provider is `codex`.")
    connections = payload.get("connections", {})
    if not isinstance(connections, Mapping):
        raise RetrievalServerError("`connections` must be an object.")
    api_llm = connections.get("api_llm", {})
    if api_llm is not None and not isinstance(api_llm, Mapping):
        raise RetrievalServerError("`connections.api_llm` must be an object.")
    codex_connection = connections.get("codex", {})
    if codex_connection is not None and not isinstance(codex_connection, Mapping):
        raise RetrievalServerError("`connections.codex` must be an object.")
    connected_context = payload.get("connected_context", {})
    if not isinstance(connected_context, Mapping):
        raise RetrievalServerError("`connected_context` must be an object.")
    for key in ("disclaimer_required_terms", "stale_block_terms"):
        value = connected_context.get(key)
        if value is not None and not isinstance(value, list):
            raise RetrievalServerError(f"`connected_context.{key}` must be an array.")
        if isinstance(value, list) and not _string_list(value):
            raise RetrievalServerError(f"`connected_context.{key}` must contain only strings.")
    experiments = payload.get("experiments", {})
    if not isinstance(experiments, Mapping):
        raise RetrievalServerError("`experiments` must be an object.")
    if "intent_sufficiency_enabled" in experiments and not _is_boolean_like(experiments.get("intent_sufficiency_enabled")):
        raise RetrievalServerError("`experiments.intent_sufficiency_enabled` must be a boolean.")
    if "codex_evidence_organizer_enabled" in experiments and not _is_boolean_like(
        experiments.get("codex_evidence_organizer_enabled")
    ):
        raise RetrievalServerError("`experiments.codex_evidence_organizer_enabled` must be a boolean.")
    for experiment_name in (
        "codex_candidate_order_neutralization_enabled",
        "multi_intent_stage_order_neutralization_enabled",
    ):
        if experiment_name in experiments and not _is_boolean_like(experiments.get(experiment_name)):
            raise RetrievalServerError(f"`experiments.{experiment_name}` must be a boolean.")
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


def _retrieval_settings(config: Mapping[str, Any]) -> Mapping[str, Any]:
    retrieval = config.get("retrieval", {})
    return retrieval if isinstance(retrieval, Mapping) else {}


def _generation_settings(config: Mapping[str, Any]) -> Mapping[str, Any]:
    generation = config.get("generation", {})
    return generation if isinstance(generation, Mapping) else {}


def _experiments_settings(config: Mapping[str, Any]) -> Mapping[str, Any]:
    experiments = config.get("experiments", {})
    return experiments if isinstance(experiments, Mapping) else {}


def _retrieval_mode(config: Mapping[str, Any]) -> str:
    mode = str(_retrieval_settings(config).get("mode") or RETRIEVAL_MODE_WORKSPACE).strip().lower()
    return mode if mode in {RETRIEVAL_MODE_WORKSPACE, RETRIEVAL_MODE_CODEX} else RETRIEVAL_MODE_WORKSPACE


def _boolean_setting(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    if value is None:
        return default
    return bool(value)


def _is_boolean_like(value: Any) -> bool:
    if isinstance(value, bool):
        return True
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on", "0", "false", "no", "off"}
    return False


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


def _codex_model_options(catalog: Any) -> list[dict[str, Any]]:
    if not isinstance(catalog, Mapping):
        return []
    raw_models = catalog.get("models")
    if not isinstance(raw_models, list):
        return []
    models: list[dict[str, Any]] = []
    for item in raw_models:
        if not isinstance(item, Mapping):
            continue
        slug = str(item.get("slug") or "").strip()
        if not slug:
            continue
        reasoning_levels: list[dict[str, str]] = []
        raw_levels = item.get("supported_reasoning_levels")
        if isinstance(raw_levels, list):
            for level in raw_levels:
                if not isinstance(level, Mapping):
                    continue
                effort = str(level.get("effort") or "").strip()
                if not effort:
                    continue
                reasoning_levels.append(
                    {
                        "effort": effort,
                        "description": str(level.get("description") or "").strip(),
                    }
                )
        models.append(
            {
                "slug": slug,
                "display_name": str(item.get("display_name") or slug).strip(),
                "description": str(item.get("description") or "").strip(),
                "default_reasoning_level": str(item.get("default_reasoning_level") or "").strip(),
                "supported_reasoning_levels": reasoning_levels,
                "visibility": str(item.get("visibility") or "").strip(),
                "supported_in_api": bool(item.get("supported_in_api")),
                "priority": item.get("priority") if isinstance(item.get("priority"), int) else None,
                "additional_speed_tiers": _plain_string_list(item.get("additional_speed_tiers")),
            }
        )
    return sorted(models, key=lambda model: (model.get("priority") is None, model.get("priority") or 9999, str(model.get("slug") or "")))


def _codex_global_mcp_servers(command: Sequence[str], *, workspace_root: Path) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            list(command),
            cwd=str(workspace_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=_codex_subprocess_env(command),
            timeout=30,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RetrievalServerError(f"Codex command was not found: {command[0]}", status=404) from exc
    except subprocess.TimeoutExpired as exc:
        raise RetrievalServerError("Codex MCP server list request timed out.", status=504) from exc
    except OSError as exc:
        raise RetrievalServerError(f"Codex MCP server list request failed: {exc}", status=502) from exc
    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()
    if completed.returncode != 0:
        detail = stderr or stdout or f"exit code {completed.returncode}"
        raise RetrievalServerError(f"Codex MCP server list request failed: {detail}", status=502)
    try:
        raw_servers = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise RetrievalServerError("Codex MCP server list response was not valid JSON.", status=502) from exc
    if not isinstance(raw_servers, list):
        raise RetrievalServerError("Codex MCP server list response must be an array.", status=502)
    servers = [_public_codex_mcp_server(server) for server in raw_servers if isinstance(server, Mapping)]
    return {
        "ok": True,
        "command": list(command),
        "server_count": len(servers),
        "enabled_server_count": sum(1 for server in servers if server.get("enabled")),
        "servers": servers,
        "stderr": stderr,
    }


def _public_codex_mcp_server(server: Mapping[str, Any]) -> dict[str, Any]:
    transport = server.get("transport")
    public_transport = _public_codex_mcp_transport(transport if isinstance(transport, Mapping) else {})
    return {
        "name": str(server.get("name") or "").strip(),
        "enabled": bool(server.get("enabled")),
        "disabled_reason": str(server.get("disabled_reason") or "").strip(),
        "transport": public_transport,
        "startup_timeout_sec": server.get("startup_timeout_sec") if isinstance(server.get("startup_timeout_sec"), (int, float)) else None,
        "tool_timeout_sec": server.get("tool_timeout_sec") if isinstance(server.get("tool_timeout_sec"), (int, float)) else None,
        "auth_status": str(server.get("auth_status") or "").strip(),
    }


def _public_codex_mcp_transport(transport: Mapping[str, Any]) -> dict[str, Any]:
    transport_type = str(transport.get("type") or "").strip()
    public: dict[str, Any] = {"type": transport_type}
    if transport_type == "stdio":
        public["command"] = str(transport.get("command") or "").strip()
        public["args"] = _plain_string_list(transport.get("args"))
        public["cwd"] = str(transport.get("cwd") or "").strip()
        env = transport.get("env")
        public["env_keys"] = sorted(str(key) for key in env.keys()) if isinstance(env, Mapping) else []
        public["env_vars"] = _plain_string_list(transport.get("env_vars"))
        return public
    if transport_type in {"streamable_http", "sse", "http"}:
        public["url"] = str(transport.get("url") or "").strip()
        public["bearer_token_env_var"] = str(transport.get("bearer_token_env_var") or "").strip()
        http_headers = transport.get("http_headers")
        env_http_headers = transport.get("env_http_headers")
        public["http_header_keys"] = sorted(str(key) for key in http_headers.keys()) if isinstance(http_headers, Mapping) else []
        public["env_http_header_keys"] = sorted(str(key) for key in env_http_headers.keys()) if isinstance(env_http_headers, Mapping) else []
        return public
    return public


def _codex_retrieval_override_indicators(retrieval_settings: Mapping[str, Any], codex_settings: Mapping[str, Any]) -> dict[str, Any]:
    model = str(retrieval_settings.get("codex_model") or "").strip()
    ignore_user_config = bool(codex_settings.get("ignore_user_config", True))
    return {
        "ignore_user_config": {
            "overridden": ignore_user_config,
            "flag": "--ignore-user-config",
            "effect": (
                "Codex retrieval does not load globally configured MCP servers, profiles, or user config defaults."
                if ignore_user_config
                else "Codex retrieval may load the user's global Codex config."
            ),
        },
        "plugins": {
            "overridden": True,
            "flag": "--disable plugins",
            "effect": "Codex retrieval disables Codex plugins for this run.",
        },
        "rules": {
            "overridden": True,
            "flag": "--ignore-rules",
            "effect": "Codex retrieval does not apply repository or user instruction rules from Codex.",
        },
        "web_search": {
            "overridden": True,
            "flag": "-c web_search=\"disabled\"",
            "effect": "Codex retrieval cannot use live web search.",
        },
        "approval_policy": {
            "overridden": True,
            "flag": "-a never",
            "effect": "Codex retrieval will not ask for approvals.",
        },
        "sandbox": {
            "overridden": True,
            "flag": "--sandbox read-only",
            "effect": "Codex retrieval is constrained to read-only workspace access.",
        },
        "model": {
            "overridden": bool(model),
            "flag": "--model",
            "value": model,
            "effect": "Codex retrieval uses the model selected in Guided Intelligence instead of a Codex user-config default.",
        },
    }


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
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "pick-directory.mjs"
    electron_command = _electron_command(script_path)
    try:
        completed = subprocess.run(
            [*electron_command, str(start_path)],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
    except OSError as exc:
        raise DirectoryPickerUnavailable("Directory picker is unavailable: Electron could not be started. Run `npm install`.") from exc
    except subprocess.TimeoutExpired as exc:
        raise DirectoryPickerUnavailable("Directory picker timed out.") from exc

    if completed.returncode != 0:
        detail = _electron_picker_error(completed.stdout, completed.stderr)
        raise DirectoryPickerUnavailable(f"Directory picker is unavailable: {detail}") from None

    payload = _electron_picker_payload(completed.stdout)
    if payload.get("error"):
        raise DirectoryPickerUnavailable(f"Directory picker is unavailable: {payload['error']}")
    selected = str(payload.get("path") or "").strip()
    return Path(selected).resolve() if selected else None


def _electron_command(script_path: Path) -> tuple[str, ...]:
    tool_root = script_path.parents[1]
    bin_name = "electron.cmd" if sys.platform == "win32" else "electron"
    electron_bin = tool_root / "node_modules" / ".bin" / bin_name
    if electron_bin.exists():
        return (str(electron_bin), str(script_path))
    return ("npx", "--no-install", "electron", str(script_path))


def _electron_picker_payload(stdout: str) -> Mapping[str, Any]:
    for line in reversed(stdout.splitlines()):
        text = line.strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        return payload if isinstance(payload, Mapping) else {}
    raise DirectoryPickerUnavailable("Directory picker did not return a valid response.")


def _electron_picker_error(stdout: str, stderr: str) -> str:
    try:
        payload = _electron_picker_payload(stdout)
    except DirectoryPickerUnavailable:
        payload = {}
    detail = str(payload.get("error") or "").strip() if isinstance(payload, Mapping) else ""
    return detail or stderr.strip() or stdout.strip() or "Electron folder picker failed."


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
    request = urllib.request.Request(
        endpoint_url,
        headers={
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": "2024-11-05",
            "User-Agent": "guided-intelligence-retrieval/1.0",
        },
        method="GET",
    )
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
            if key.startswith("GITHUB_OAUTH_") or key.startswith("GUIDED_INTELLIGENCE_")
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
    return dict(discovered)


def _register_oauth_client(auth_metadata: Mapping[str, Any], *, redirect_uri: str, provider: str) -> dict[str, Any]:
    registration_endpoint = str(auth_metadata.get("registration_endpoint") or "").strip()
    if not registration_endpoint:
        normalized_provider = provider.strip().lower()
        if normalized_provider == "github":
            raise RetrievalServerError(
                "GitHub browser connect requires one tool-level OAuth app. Add GITHUB_OAUTH_CLIENT_ID and "
                "GITHUB_OAUTH_CLIENT_SECRET to the tool .env. GitHub callback URL: "
                f"{redirect_uri}",
                status=502,
            )
        raise RetrievalServerError(
            "OAuth server does not support dynamic client registration. A one-click browser connect needs provider OAuth client configuration for this server.",
            status=502,
        )
    payload = {
        "client_name": f"Guided Intelligence {provider}",
        "redirect_uris": [redirect_uri],
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
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "guided-intelligence-retrieval/1.0",
        },
    )
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
    request = urllib.request.Request(
        url,
        data=raw,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "guided-intelligence-retrieval/1.0",
        },
        method="POST",
    )
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
    request = urllib.request.Request(
        url,
        data=raw,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "User-Agent": "guided-intelligence-retrieval/1.0",
        },
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
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Basic {credentials}",
            "User-Agent": "guided-intelligence-retrieval/1.0",
        },
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
    display_percent = _display_progress_percent(metadata)
    if not result:
        estimate = metadata.get("index_estimate") if isinstance(metadata.get("index_estimate"), Mapping) else {}
        metrics = _run_metrics(run_dir, metadata)
        return {
            "run_id": run_id,
            "run_dir": str(run_dir),
            "title": "",
            "prompt": str(metadata.get("prompt") or ""),
            "status": str(metadata.get("status") or "running"),
            "phase": str(metadata.get("phase") or "indexing"),
            "coverage_status": "preparing_index",
            "sufficient": False,
            "selected_count": 0,
            "stop_reason": "",
            "response_preview": "",
            "index_estimate": _deepcopy_json(estimate),
            "progress_percent": display_percent,
            "progress_message": str(metadata.get("progress_message") or ""),
            "progress_logs": _plain_string_list(metadata.get("progress_logs", [])),
            "retry_count": int(metadata.get("retry_count") or 0),
            **metrics,
        }
    retrieval = result.get("retrieval_result") if isinstance(result.get("retrieval_result"), Mapping) else {}
    summary = retrieval.get("retrieval_summary") if isinstance(retrieval.get("retrieval_summary"), Mapping) else {}
    response = result.get("response_payload") if isinstance(result.get("response_payload"), Mapping) else {}
    response_metadata = response.get("metadata") if isinstance(response.get("metadata"), Mapping) else {}
    render_notes = response_metadata.get("render_notes") if isinstance(response_metadata.get("render_notes"), Mapping) else {}
    plan = summary.get("retrieval_plan") if isinstance(summary.get("retrieval_plan"), Mapping) else {}
    metrics = _run_metrics(run_dir, metadata)
    return {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "title": str(render_notes.get("title") or ""),
        "prompt": str(plan.get("raw_prompt") or metadata.get("prompt") or ""),
        "status": str(metadata.get("status") or "complete"),
        "phase": str(metadata.get("phase") or "complete"),
        "coverage_status": retrieval.get("coverage_status", "unknown"),
        "sufficient": bool(retrieval.get("sufficient", False)),
        "selected_count": len(retrieval.get("evidence", []) or []),
        "stop_reason": summary.get("stop_reason", ""),
        "response_preview": str(response.get("content") or "")[:500],
        "index_estimate": _deepcopy_json(metadata.get("index_estimate") or {}),
        "progress_percent": display_percent if str(metadata.get("status") or "") == "running" else int(metadata.get("progress_percent") or 100),
        "progress_message": str(metadata.get("progress_message") or ""),
        "progress_logs": _plain_string_list(metadata.get("progress_logs", [])),
        "retry_count": int(metadata.get("retry_count") or 0),
        **metrics,
    }


def _run_evidence_connections(result: Mapping[str, Any]) -> dict[str, Any]:
    retrieval = result.get("retrieval_result") if isinstance(result.get("retrieval_result"), Mapping) else {}
    summary = retrieval.get("retrieval_summary") if isinstance(retrieval.get("retrieval_summary"), Mapping) else {}
    graph = summary.get("evidence_connections")
    if not isinstance(graph, Mapping):
        return {"version": 1, "connections": []}
    output = {
        "version": int(graph.get("version") or 1),
        "status": str(graph.get("status") or "complete"),
        "connections": _deepcopy_json(graph.get("connections") if isinstance(graph.get("connections"), list) else []),
    }
    for key in ("candidate_connections", "root_ref", "disconnected_evidence", "generation", "error"):
        if key in graph:
            output[key] = _deepcopy_json(graph[key])
    return output


def _run_evidence_organization(result: Mapping[str, Any]) -> dict[str, Any]:
    retrieval = result.get("retrieval_result") if isinstance(result.get("retrieval_result"), Mapping) else {}
    summary = retrieval.get("retrieval_summary") if isinstance(retrieval.get("retrieval_summary"), Mapping) else {}
    organization = summary.get("evidence_organization")
    return _deepcopy_json(organization) if isinstance(organization, Mapping) else {}


def _run_candidate_evidence(
    run_dir: Path,
    result: Mapping[str, Any],
    selected_evidence: Any,
) -> list[dict[str, Any]]:
    """Return all valid organizer candidates without changing generation evidence.

    New runs persist the converted candidates in the organizer result. For runs
    created before that field existed, reconstruct the same UI representation
    from the preserved raw Codex artifact.
    """
    organization = _run_evidence_organization(result)
    stored = organization.get("candidate_evidence")
    if isinstance(stored, list):
        return _deepcopy_json(stored)

    raw = _load_json(run_dir / "codex-evidence.json", {})
    workspace_root = _run_workspace_root(run_dir)
    if isinstance(raw, Mapping) and workspace_root is not None:
        candidates, _ = _evidence_conversion_from_payload(raw, workspace_root=workspace_root, limit=40)
        if candidates:
            return [item.to_dict() for item in candidates]

    return _deepcopy_json(selected_evidence) if isinstance(selected_evidence, list) else []


def _with_historical_candidate_connections(
    run_dir: Path,
    result: Mapping[str, Any],
    graph: dict[str, Any],
) -> dict[str, Any]:
    """Backfill candidate-wide CodeGraph edges for pre-feature Codex runs."""
    if isinstance(graph.get("candidate_connections"), list):
        return graph
    organization = _run_evidence_organization(result)
    if organization.get("status") != "complete" or not organization.get("candidate_count"):
        return graph

    cache_path = run_dir / "candidate-evidence-connections.json"
    cached = _load_json(cache_path, {})
    if isinstance(cached, Mapping) and cached.get("status") == "complete" and isinstance(cached.get("connections"), list):
        return {**graph, "candidate_connections": _deepcopy_json(cached["connections"]), "candidate_connections_backfilled": True}

    raw = _load_json(run_dir / "codex-evidence.json", {})
    workspace_root = _run_workspace_root(run_dir)
    if not isinstance(raw, Mapping) or workspace_root is None:
        return {**graph, "candidate_connections_error": "Historical candidate graph cannot be reconstructed from this run."}
    evidence, _ = _evidence_conversion_from_payload(raw, workspace_root=workspace_root, limit=40)
    try:
        connections = build_candidate_connections(
            evidence,
            workspace_root=workspace_root,
            existing_connections=graph.get("connections") if isinstance(graph.get("connections"), list) else (),
        )
    except Exception as exc:
        error = f"Historical candidate graph reconstruction failed: {exc}"
        cache_path.write_text(json.dumps({"status": "error", "error": error}, indent=2), encoding="utf-8")
        return {**graph, "candidate_connections_error": error}

    cache_path.write_text(
        json.dumps({"status": "complete", "connections": connections}, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return {**graph, "candidate_connections": connections, "candidate_connections_backfilled": True}


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
        return json.loads(path.read_text(encoding="utf-8-sig"))
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


def _run_workspace_root(run_dir: Path) -> Path | None:
    for event in _load_jsonl(run_dir / "retrieval-trace.jsonl"):
        payload = event.get("payload")
        if not isinstance(payload, Mapping):
            continue
        workspace_root = str(payload.get("workspace_root") or "").strip()
        if not workspace_root:
            continue
        path = Path(workspace_root).resolve()
        if path.exists() and path.is_dir():
            return path
    result = _load_json(run_dir / "orchestration-result.json", {})
    retrieval = result.get("retrieval_result") if isinstance(result, Mapping) else None
    summary = retrieval.get("retrieval_summary") if isinstance(retrieval, Mapping) else None
    workspace_root = str(summary.get("workspace_root") or "").strip() if isinstance(summary, Mapping) else ""
    if workspace_root:
        path = Path(workspace_root).resolve()
        if path.exists() and path.is_dir():
            return path
    return None


def _vscode_file_url(path: Path, line_fragment: str = "") -> str:
    match = re.search(r"L(?P<line>\d+)", line_fragment or "")
    line = f":{match.group('line')}" if match else ""
    return f"vscode://file/{path.as_posix()}{line}"


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
