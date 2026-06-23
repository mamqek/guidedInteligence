from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from services.retrieval.config import ConnectedSourceDocument, MCPConnectedSourceConfig
from services.retrieval.workspace.mcp.stdio_client import MCPStdioClient, MCPStdioError


class MCPConnectedSourceError(RuntimeError):
    """Raised when an MCP connected source cannot return usable documents."""


class MCPConnectedSourceAdapter:
    """Query one MCP tool and normalize its result into connected documents."""

    def __init__(self, config: MCPConnectedSourceConfig) -> None:
        self.config = config

    def search(self, query: str) -> tuple[ConnectedSourceDocument, ...]:
        arguments: dict[str, Any] = dict(self.config.static_tool_arguments)
        arguments[self.config.query_argument_name] = query
        if self.config.limit_argument_name:
            arguments[self.config.limit_argument_name] = self.config.result_limit
        try:
            with MCPStdioClient(
                command=self.config.command,
                args=self.config.args,
                env=self.config.env,
                cwd=self.config.cwd,
                timeout_seconds=self.config.timeout_seconds,
            ) as client:
                result = client.call_tool(self.config.query_tool_name, arguments)
        except MCPStdioError as exc:
            raise MCPConnectedSourceError(str(exc)) from exc

        documents = self._documents_from_tool_result(result)
        return documents[: self.config.result_limit]

    def _documents_from_tool_result(self, result: Mapping[str, Any]) -> tuple[ConnectedSourceDocument, ...]:
        payload = _extract_result_payload(result)
        records = _extract_records(payload)
        documents: list[ConnectedSourceDocument] = []
        for index, record in enumerate(records):
            document = self._document_from_record(record, index=index)
            if document is not None:
                documents.append(document)
        return tuple(documents)

    def _document_from_record(self, record: Any, *, index: int) -> ConnectedSourceDocument | None:
        if isinstance(record, Mapping):
            title = _first_field(record, self.config.title_fields) or f"{self.config.name} result {index + 1}"
            content = _first_field(record, self.config.content_fields)
            if not content:
                content = json.dumps(record, sort_keys=True)
            raw_source_id = _first_field(record, self.config.id_fields) or str(index + 1)
            metadata = {
                "adapter": "mcp",
                "source_key": self.config.source_key,
                "mcp_source": self.config.name,
                "mcp_tool": self.config.query_tool_name,
            }
            for key in ("url", "html_url", "state", "author", "repository", "number"):
                value = record.get(key)
                if value is not None and not isinstance(value, (Mapping, list, tuple)):
                    metadata[key] = str(value)
            return ConnectedSourceDocument(
                source_category=self.config.source_category,
                source_id=f"mcp:{self.config.name}:{raw_source_id}",
                title=str(title),
                content=str(content),
                metadata=metadata,
                source_key=self.config.source_key,
            )
        if isinstance(record, str) and record.strip():
            return ConnectedSourceDocument(
                source_category=self.config.source_category,
                source_id=f"mcp:{self.config.name}:{index + 1}",
                title=f"{self.config.name} result {index + 1}",
                content=record.strip(),
                metadata={
                    "adapter": "mcp",
                    "source_key": self.config.source_key,
                    "mcp_source": self.config.name,
                    "mcp_tool": self.config.query_tool_name,
                },
                source_key=self.config.source_key,
            )
        return None


def _extract_result_payload(result: Mapping[str, Any]) -> Any:
    structured = result.get("structuredContent")
    if structured is not None:
        return structured
    content = result.get("content")
    if isinstance(content, Sequence) and not isinstance(content, (str, bytes)):
        text_parts: list[str] = []
        for item in content:
            if not isinstance(item, Mapping):
                continue
            if item.get("type") == "text" and item.get("text") is not None:
                text_parts.append(str(item.get("text")))
        combined = "\n".join(text_parts).strip()
        if combined:
            return _parse_json_or_text(combined)
    return result


def _extract_records(payload: Any) -> tuple[Any, ...]:
    if isinstance(payload, list):
        return tuple(payload)
    if isinstance(payload, Mapping):
        for key in ("results", "items", "issues", "pull_requests", "documents", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return tuple(value)
        if "total_count" in payload and not any(
            key in payload
            for key in ("id", "number", "key", "title", "name", "summary", "body", "content", "text")
        ):
            return ()
        return (payload,)
    if isinstance(payload, str):
        parsed = _parse_json_or_text(payload)
        if parsed is payload:
            return (payload,)
        return _extract_records(parsed)
    return ()


def _parse_json_or_text(value: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _first_field(record: Mapping[str, Any], fields: Sequence[str]) -> str:
    for field in fields:
        value = record.get(field)
        if value is None:
            continue
        if isinstance(value, (Mapping, list, tuple)):
            continue
        text = str(value).strip()
        if text:
            return text
    return ""
