from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Mapping

from services.retrieval.config import ConnectedSourceDocument, RemoteMCPConnectedSourceConfig
from services.retrieval.workspace.mcp.adapters import _extract_records, _extract_result_payload, _first_field


PROVIDER_PROFILES: dict[str, dict[str, Any]] = {
    "notion": {
        "search_tools": ("notion-search",),
        "fetch_tools": ("notion-fetch",),
        "fetch_id_arg": "id",
        "search_arg": "query",
    },
    "atlassian_jira": {
        "search_tools": ("searchJiraIssuesUsingJql", "search_jira", "searchJiraIssues", "searchJira"),
        "fetch_tools": ("getJiraIssue", "get_jira_issue", "jiraIssue"),
        "fetch_id_arg": "issueIdOrKey",
        "search_arg": "jql",
    },
    "atlassian_confluence": {
        "search_tools": ("searchConfluenceUsingCql", "search_confluence", "searchConfluence"),
        "fetch_tools": ("getConfluencePage", "get_confluence_page", "confluencePage"),
        "fetch_id_arg": "pageId",
        "search_arg": "cql",
    },
    "shortcut": {
        "search_tools": ("search_stories", "list_stories", "find_stories", "searchStories", "listStories"),
        "fetch_tools": ("get_story", "getStory", "read_story", "story"),
        "fetch_id_arg": "id",
        "search_arg": "query",
    },
    "linear": {
        "search_tools": ("list_issues", "search_issues", "listIssues", "searchIssues"),
        "fetch_tools": ("get_issue", "getIssue", "issue"),
        "fetch_id_arg": "id",
        "search_arg": "query",
    },
    "slack": {
        "search_tools": ("search_messages", "searchMessages", "search", "search_files", "searchFiles"),
        "fetch_tools": ("read_thread", "readThread", "read_file", "readFile", "read_channel", "readChannel"),
        "fetch_id_arg": "id",
        "search_arg": "query",
    },
    "google_drive": {
        "search_tools": ("search_files", "searchFiles", "search"),
        "fetch_tools": ("get_file", "getFile", "read_file", "readFile", "fetch_file", "fetchFile"),
        "fetch_id_arg": "id",
        "search_arg": "query",
    },
}


class RemoteMCPConnectedSourceError(RuntimeError):
    """Raised when a remote MCP source cannot return usable documents."""


class RemoteMCPConnectedSourceAdapter:
    """Query one hosted MCP tool over HTTP and normalize results."""

    def __init__(self, config: RemoteMCPConnectedSourceConfig) -> None:
        self.config = config
        self._next_id = 1
        self._session_id = ""

    def search(self, query: str) -> tuple[ConnectedSourceDocument, ...]:
        if self._uses_provider_profile():
            return self._search_provider_profile(query)
        tool_name = self._resolve_tool_name(self.config.query_tool_name, "search")
        arguments = self._tool_arguments(query)
        result = self._request(
            "tools/call",
            {
                "name": tool_name,
                "arguments": arguments,
            },
        )
        documents = self._documents_from_tool_result(result, tool_name=tool_name)
        return documents[: self.config.result_limit]

    def _search_provider_profile(self, query: str) -> tuple[ConnectedSourceDocument, ...]:
        tool_name = self._resolve_tool_name(self.config.query_tool_name, "search")
        result = self._request(
            "tools/call",
            {
                "name": tool_name,
                "arguments": self._profile_search_arguments(query),
            },
        )
        payload = _extract_result_payload(result)
        records = [record for record in _extract_records(payload) if self._record_allowed(record)]
        documents: list[ConnectedSourceDocument] = []
        fetch_tool_name = self._resolve_tool_name(self.config.fetch_tool_name, "fetch", required=False)
        fetch_count = self.config.enrich_limit if self.config.enrich_results and fetch_tool_name else 0
        for index, record in enumerate(records[: self.config.result_limit]):
            score = _score_from_record(record, self.config.score_fields)
            if score is not None and score < self.config.min_score:
                continue
            fetch_payload: Any = None
            identifier = _record_identifier(record)
            if identifier and index < fetch_count:
                try:
                    fetch_result = self._request(
                        "tools/call",
                        {
                            "name": fetch_tool_name,
                            "arguments": {self._fetch_id_arg(): identifier},
                        },
                    )
                    fetch_payload = _extract_result_payload(fetch_result)
                except RemoteMCPConnectedSourceError:
                    fetch_payload = None
            document = self._document_from_profile_record(record, fetch_payload, index=index, tool_name=tool_name, fetch_tool_name=fetch_tool_name)
            if document is not None:
                documents.append(document)
        return tuple(documents)

    def _profile_search_arguments(self, query: str) -> dict[str, Any]:
        arguments: dict[str, Any] = dict(self.config.static_tool_arguments)
        provider = self._provider_key()
        if provider == "atlassian_jira":
            arguments["jql"] = _jira_jql(query, self.config.scope)
        elif provider == "atlassian_confluence":
            arguments["cql"] = _confluence_cql(query, self.config.scope)
        else:
            profile = self._provider_profile() or {}
            arguments[str(profile.get("search_arg") or self.config.query_argument_name or "query")] = query
            if self.config.scope:
                arguments.setdefault("scope", self.config.scope)
        if self.config.limit_argument_name:
            arguments[self.config.limit_argument_name] = self.config.result_limit
        return arguments

    def _record_allowed(self, record: Any) -> bool:
        if not isinstance(record, Mapping):
            return True
        record_type = _record_type(self._provider_key(), record)
        if not record_type:
            return True
        feature_key = _feature_key_for_record_type(record_type)
        if feature_key:
            return bool(self.config.features.get(feature_key, True))
        return True

    def _document_from_profile_record(
        self,
        record: Any,
        fetch_payload: Any,
        *,
        index: int,
        tool_name: str,
        fetch_tool_name: str,
    ) -> ConnectedSourceDocument | None:
        if isinstance(record, Mapping):
            record_type = _record_type(self._provider_key(), record) or "unknown"
            title = _first_field(record, self.config.title_fields) or _first_field(record, ("object", "type")) or f"{self.config.name} result {index + 1}"
            identifier = _canonical_record_identifier(self.config.provider, record, title=str(title)) or str(index + 1)
            search_content = _first_field(record, self.config.content_fields)
            fetched_content = _payload_text(fetch_payload) if fetch_payload is not None else ""
            content = fetched_content or search_content or json.dumps(record, sort_keys=True)
            metadata = {
                "adapter": "remote_mcp",
                "source_key": self.config.source_key,
                "provider": self.config.provider,
                "mcp_source": self.config.name,
                "mcp_tool": tool_name,
                "scope": self.config.scope,
                "record_type": record_type,
                "enriched": "true" if fetched_content else "false",
            }
            if self.config.provider == "notion":
                metadata["notion_type"] = record_type
            if fetched_content and fetch_tool_name:
                metadata["mcp_fetch_tool"] = fetch_tool_name
            for key in ("url", "public_url", "id", "object", "type", "last_edited_time", "created_time", "key", "channel", "user", "ts", "thread_ts", "mime_type"):
                value = record.get(key)
                if value is not None and not isinstance(value, (Mapping, list, tuple)):
                    metadata[key] = str(value)
            return ConnectedSourceDocument(
                source_category=self.config.source_category,
                source_id=f"remote-mcp:{self.config.provider}:{self.config.name}:{identifier}",
                title=str(title),
                content=str(content),
                metadata=metadata,
                source_key=self.config.source_key,
            )
        if isinstance(record, str) and record.strip():
            return ConnectedSourceDocument(
                source_category=self.config.source_category,
                source_id=f"remote-mcp:{self.config.provider}:{self.config.name}:{index + 1}",
                title=f"{self.config.name} result {index + 1}",
                content=record.strip(),
                metadata={
                    "adapter": "remote_mcp",
                    "source_key": self.config.source_key,
                    "provider": self.config.provider,
                    "mcp_source": self.config.name,
                    "mcp_tool": tool_name,
                    "scope": self.config.scope,
                    "record_type": "unknown",
                    "enriched": "false",
                },
                source_key=self.config.source_key,
            )
        return None

    def _tool_arguments(self, query: str) -> dict[str, Any]:
        arguments: dict[str, Any] = dict(self.config.static_tool_arguments)
        query_text = query
        if self.config.provider == "github":
            query_text = self._github_query(query)
            self._apply_github_scope(arguments)
            if self.config.query_tool_name == "search_issues":
                arguments.setdefault("mode", "hybrid")
        elif self.config.scope:
            arguments.setdefault("scope", self.config.scope)
        arguments[self.config.query_argument_name] = query_text
        if self.config.limit_argument_name:
            arguments[self.config.limit_argument_name] = self.config.result_limit
        return arguments

    def _apply_github_scope(self, arguments: dict[str, Any]) -> None:
        scope = self.config.scope.strip().strip("/")
        if not scope:
            return
        if "/" in scope:
            owner, repo = scope.split("/", 1)
            if owner.strip():
                arguments.setdefault("owner", owner.strip())
            if repo.strip():
                arguments.setdefault("repo", repo.strip())
        else:
            arguments.setdefault("owner", scope)

    def _github_query(self, query: str) -> str:
        text = query.strip()
        if self.config.query_tool_name == "search_issues" and "is:issue" not in text and "is:pull-request" not in text and "is:pr" not in text:
            return f"{text} is:issue".strip()
        return text

    def list_tools(self) -> tuple[Mapping[str, Any], ...]:
        result = self._request("tools/list", {})
        tools = result.get("tools", ())
        if not isinstance(tools, list):
            return ()
        return tuple(tool for tool in tools if isinstance(tool, Mapping))

    def _provider_key(self) -> str:
        if self.config.provider == "atlassian" and self.config.source_category.value == "issue_tracker":
            return "atlassian_jira"
        if self.config.provider == "atlassian" and self.config.source_category.value == "documentation":
            return "atlassian_confluence"
        return self.config.provider

    def _provider_profile(self) -> Mapping[str, Any] | None:
        return PROVIDER_PROFILES.get(self._provider_key())

    def _uses_provider_profile(self) -> bool:
        profile = self._provider_profile()
        if not profile:
            return False
        if self.config.provider != "notion":
            return True
        configured = self.config.query_tool_name.strip()
        return not configured or configured in set(str(tool) for tool in profile.get("search_tools", ()))

    def _fetch_id_arg(self) -> str:
        profile = self._provider_profile() or {}
        return str(profile.get("fetch_id_arg") or "id")

    def _resolve_tool_name(self, configured: str, purpose: str, *, required: bool = True) -> str:
        configured = configured.strip()
        if configured:
            return configured
        profile = self._provider_profile()
        if not profile:
            if required:
                raise RemoteMCPConnectedSourceError("Remote MCP query tool name is required.")
            return ""
        candidate_key = "fetch_tools" if purpose == "fetch" else "search_tools"
        candidates = tuple(str(candidate) for candidate in profile.get(candidate_key, ()) if str(candidate).strip())
        tools = self.list_tools()
        chosen = _choose_tool(tools, candidates, purpose)
        if chosen:
            return chosen
        if required:
            raise RemoteMCPConnectedSourceError(f"Could not find a {purpose} tool for {self.config.provider} from tools/list.")
        return ""

    def _request(self, method: str, params: Mapping[str, Any]) -> Mapping[str, Any]:
        try:
            return self._send_request(method, params)
        except RemoteMCPConnectedSourceError as exc:
            if self._session_id or "session ID" not in str(exc):
                raise
            self._initialize_session()
            return self._send_request(method, params)

    def _send_request(self, method: str, params: Mapping[str, Any]) -> Mapping[str, Any]:
        request_id = self._next_id
        self._next_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": dict(params),
        }
        request = urllib.request.Request(
            self.config.endpoint_url,
            data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            raise RemoteMCPConnectedSourceError(f"Remote MCP HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RemoteMCPConnectedSourceError(f"Remote MCP request failed: {exc.reason}") from exc
        except TimeoutError as exc:
            raise RemoteMCPConnectedSourceError("Remote MCP request timed out.") from exc
        raw = _json_from_sse(raw)
        try:
            message = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RemoteMCPConnectedSourceError("Remote MCP returned invalid JSON.") from exc
        if not isinstance(message, Mapping):
            raise RemoteMCPConnectedSourceError("Remote MCP returned a non-object response.")
        error = message.get("error")
        if isinstance(error, Mapping):
            raise RemoteMCPConnectedSourceError(str(error.get("message") or "Remote MCP request failed."))
        result = message.get("result")
        if not isinstance(result, Mapping):
            raise RemoteMCPConnectedSourceError(f"Remote MCP tool {self.config.query_tool_name!r} returned a non-object result.")
        return result

    def _initialize_session(self) -> None:
        result, session_id = self._send_initialize()
        if not isinstance(result, Mapping):
            raise RemoteMCPConnectedSourceError("Remote MCP initialize returned a non-object result.")
        if session_id:
            self._session_id = session_id
        self._send_initialized_notification()

    def _send_initialize(self) -> tuple[Mapping[str, Any], str]:
        request_id = self._next_id
        self._next_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "guided-intelligence-retrieval", "version": "1"},
            },
        }
        request = urllib.request.Request(
            self.config.endpoint_url,
            data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            headers=self._headers(include_session=False),
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                session_id = response.headers.get("Mcp-Session-Id", "") or response.headers.get("MCP-Session-Id", "")
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            raise RemoteMCPConnectedSourceError(f"Remote MCP initialize HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RemoteMCPConnectedSourceError(f"Remote MCP initialize failed: {exc.reason}") from exc
        raw = _json_from_sse(raw)
        try:
            message = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RemoteMCPConnectedSourceError("Remote MCP initialize returned invalid JSON.") from exc
        if not isinstance(message, Mapping):
            raise RemoteMCPConnectedSourceError("Remote MCP initialize returned a non-object response.")
        error = message.get("error")
        if isinstance(error, Mapping):
            raise RemoteMCPConnectedSourceError(str(error.get("message") or "Remote MCP initialize failed."))
        result = message.get("result")
        if not isinstance(result, Mapping):
            raise RemoteMCPConnectedSourceError("Remote MCP initialize returned a non-object result.")
        return result, session_id

    def _send_initialized_notification(self) -> None:
        payload = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        }
        request = urllib.request.Request(
            self.config.endpoint_url,
            data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                response.read()
        except urllib.error.HTTPError:
            return
        except (urllib.error.URLError, TimeoutError):
            return

    def _headers(self, *, include_session: bool = True) -> dict[str, str]:
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "User-Agent": "guided-intelligence-retrieval",
            **dict(self.config.headers),
        }
        if include_session and self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        if self.config.auth_type == "oauth" and self.config.oauth_access_token:
            headers["Authorization"] = f"Bearer {self.config.oauth_access_token}"
        elif self.config.auth_type == "bearer" and self.config.bearer_token:
            headers["Authorization"] = f"Bearer {self.config.bearer_token}"
        elif self.config.auth_type == "api_key" and self.config.api_key:
            headers[self.config.api_key_header or "X-API-Key"] = self.config.api_key
        return headers

    def _documents_from_tool_result(self, result: Mapping[str, Any], *, tool_name: str | None = None) -> tuple[ConnectedSourceDocument, ...]:
        payload = _extract_result_payload(result)
        records = _extract_records(payload)
        documents: list[ConnectedSourceDocument] = []
        for index, record in enumerate(records):
            score = _score_from_record(record, self.config.score_fields)
            if score is not None and score < self.config.min_score:
                continue
            document = self._document_from_record(record, index=index, tool_name=tool_name or self.config.query_tool_name)
            if document is not None:
                documents.append(document)
        return tuple(documents)

    def _document_from_record(self, record: Any, *, index: int, tool_name: str) -> ConnectedSourceDocument | None:
        if isinstance(record, Mapping):
            title = _first_field(record, self.config.title_fields) or f"{self.config.name} result {index + 1}"
            content = _first_field(record, self.config.content_fields)
            if not content:
                content = json.dumps(record, sort_keys=True)
            raw_source_id = _first_field(record, self.config.id_fields) or str(index + 1)
            metadata = {
                "adapter": "remote_mcp",
                "source_key": self.config.source_key,
                "provider": self.config.provider,
                "mcp_source": self.config.name,
                "mcp_tool": tool_name,
                "scope": self.config.scope,
            }
            score = _score_from_record(record, self.config.score_fields)
            if score is not None:
                metadata["score"] = f"{score:.6f}"
            for key in ("url", "html_url", "state", "author", "repository", "number", "key", "updated_at"):
                value = record.get(key)
                if value is not None and not isinstance(value, (Mapping, list, tuple)):
                    metadata[key] = str(value)
            return ConnectedSourceDocument(
                source_category=self.config.source_category,
                source_id=f"remote-mcp:{self.config.provider}:{self.config.name}:{raw_source_id}",
                title=str(title),
                content=str(content),
                metadata=metadata,
                source_key=self.config.source_key,
            )
        if isinstance(record, str) and record.strip():
            return ConnectedSourceDocument(
                source_category=self.config.source_category,
                source_id=f"remote-mcp:{self.config.provider}:{self.config.name}:{index + 1}",
                title=f"{self.config.name} result {index + 1}",
                content=record.strip(),
                metadata={
                    "adapter": "remote_mcp",
                    "source_key": self.config.source_key,
                    "provider": self.config.provider,
                    "mcp_source": self.config.name,
                    "mcp_tool": tool_name,
                    "scope": self.config.scope,
                },
                source_key=self.config.source_key,
            )
        return None


__all__ = ["RemoteMCPConnectedSourceAdapter", "RemoteMCPConnectedSourceError"]


def _json_from_sse(raw: str) -> str:
    text = raw.strip()
    if not text:
        return raw
    if text.startswith("{") or text.startswith("["):
        return text
    data_lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("data:"):
            value = stripped[5:].strip()
            if value and value != "[DONE]":
                data_lines.append(value)
    if not data_lines:
        return raw
    return "\n".join(data_lines)


def _score_from_record(record: Any, fields: tuple[str, ...]) -> float | None:
    if not isinstance(record, Mapping):
        return None
    for field in fields:
        value = record.get(field)
        if value is None or isinstance(value, (Mapping, list, tuple)):
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _notion_record_type(record: Mapping[str, Any]) -> str:
    for field in ("object", "type", "entity_type", "result_type"):
        value = record.get(field)
        if value is None or isinstance(value, (Mapping, list, tuple)):
            continue
        text = str(value).strip().lower().replace("-", "_").replace(" ", "_")
        if text:
            if text == "data_source" or text == "datasource":
                return "data_source"
            return text
    url = str(record.get("url") or record.get("public_url") or "").lower()
    if "collection://" in url:
        return "data_source"
    return ""


def _record_type(provider: str, record: Mapping[str, Any]) -> str:
    if provider == "notion":
        return _notion_record_type(record)
    for field in ("object", "type", "entity_type", "result_type", "kind"):
        value = record.get(field)
        if value is None or isinstance(value, (Mapping, list, tuple)):
            continue
        text = str(value).strip().lower().replace("-", "_").replace(" ", "_")
        if text:
            return text
    if provider == "slack":
        if record.get("thread_ts"):
            return "thread"
        if record.get("channel") or record.get("ts"):
            return "message"
        if record.get("mime_type") or record.get("filetype"):
            return "file"
    if provider == "google_drive":
        mime_type = str(record.get("mimeType") or record.get("mime_type") or "").lower()
        if "spreadsheet" in mime_type:
            return "sheet"
        if "presentation" in mime_type:
            return "slide"
        if "folder" in mime_type:
            return "folder"
        return "doc" if mime_type else ""
    return ""


def _feature_key_for_record_type(record_type: str) -> str:
    aliases = {
        "page": "pages",
        "database": "databases",
        "data_source": "data_sources",
        "comment": "comments",
        "discussion": "comments",
        "issue": "issues",
        "project": "projects",
        "message": "messages",
        "file": "files",
        "channel": "channels",
        "thread": "threads",
        "user": "users",
        "story": "stories",
        "epic": "epics",
        "doc": "docs",
        "document": "docs",
        "sheet": "sheets",
        "spreadsheet": "sheets",
        "slide": "slides",
        "presentation": "slides",
        "folder": "folders",
        "linked_page": "linked_pages",
        "space": "spaces",
    }
    return aliases.get(record_type, f"{record_type}s")


def _notion_identifier(record: Any) -> str:
    if not isinstance(record, Mapping):
        return ""
    for field in ("id", "page_id", "database_id", "data_source_id", "source_id", "url", "public_url"):
        value = record.get(field)
        if value is None or isinstance(value, (Mapping, list, tuple)):
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _record_identifier(record: Any) -> str:
    if not isinstance(record, Mapping):
        return ""
    for field in (
        "url",
        "html_url",
        "public_url",
        "id",
        "key",
        "issueIdOrKey",
        "pageId",
        "page_id",
        "database_id",
        "data_source_id",
        "source_id",
        "thread_ts",
        "ts",
    ):
        value = record.get(field)
        if value is None or isinstance(value, (Mapping, list, tuple)):
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _canonical_record_identifier(provider: str, record: Any, *, title: str = "") -> str:
    if provider == "notion":
        slug = _notion_title_slug(title)
        if slug:
            return slug
    identifier = _notion_identifier(record) if provider == "notion" else _record_identifier(record)
    if provider != "notion" or not identifier:
        return identifier
    return _canonical_notion_identifier(identifier)


def _notion_title_slug(title: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", title.strip()).strip("-").lower()
    return normalized[:120]


def _canonical_notion_identifier(identifier: str) -> str:
    parsed = urllib.parse.urlsplit(identifier)
    if not parsed.scheme or not parsed.netloc:
        return identifier
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    filtered_query = tuple((key, value) for key, value in query if key != "pvs")
    if len(filtered_query) == len(query):
        return identifier
    return urllib.parse.urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            urllib.parse.urlencode(filtered_query),
            parsed.fragment,
        )
    )


def _payload_text(payload: Any) -> str:
    if payload is None:
        return ""
    if isinstance(payload, str):
        return payload.strip()
    if isinstance(payload, Mapping):
        for field in ("markdown", "content", "text", "body", "description", "summary"):
            value = payload.get(field)
            if value is None or isinstance(value, (Mapping, list, tuple)):
                continue
            text = str(value).strip()
            if text:
                return text
        records = _extract_records(payload)
        if len(records) == 1 and records[0] is not payload:
            return _payload_text(records[0])
        return json.dumps(payload, sort_keys=True)
    if isinstance(payload, list):
        parts = [_payload_text(item) for item in payload]
        return "\n\n".join(part for part in parts if part)
    return str(payload).strip()


def _choose_tool(tools: tuple[Mapping[str, Any], ...], candidates: tuple[str, ...], purpose: str) -> str:
    names = [str(tool.get("name") or "").strip() for tool in tools if str(tool.get("name") or "").strip()]
    lowered = {name.lower(): name for name in names}
    for candidate in candidates:
        exact = lowered.get(candidate.lower())
        if exact:
            return exact
    candidate_tokens = tuple(_tool_tokens(candidate) for candidate in candidates)
    best_name = ""
    best_score = 0
    purpose_tokens = {"search"} if purpose == "search" else {"get", "read", "fetch", "retrieve"}
    for name in names:
        tokens = _tool_tokens(name)
        score = 0
        if tokens & purpose_tokens:
            score += 3
        for candidate in candidate_tokens:
            score = max(score, len(tokens & candidate))
        if score > best_score:
            best_name = name
            best_score = score
    return best_name if best_score > 0 else ""


def _tool_tokens(value: str) -> set[str]:
    normalized = value.replace("-", "_")
    parts = []
    current = ""
    for char in normalized:
        if char == "_" or char == " ":
            if current:
                parts.append(current.lower())
                current = ""
            continue
        if char.isupper() and current:
            parts.append(current.lower())
            current = char
            continue
        current += char
    if current:
        parts.append(current.lower())
    return set(parts)


def _jira_jql(query: str, scope: str) -> str:
    clauses = [f'text ~ "{_escape_query(query)}"']
    if scope.strip():
        clauses.insert(0, f'project = "{_escape_query(scope.strip())}"')
    return " AND ".join(clauses) + " ORDER BY updated DESC"


def _confluence_cql(query: str, scope: str) -> str:
    clauses = [f'text ~ "{_escape_query(query)}"']
    if scope.strip():
        clauses.insert(0, f'space = "{_escape_query(scope.strip())}"')
    return " AND ".join(clauses) + " ORDER BY lastmodified DESC"


def _escape_query(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').strip()
