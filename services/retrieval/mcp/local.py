from __future__ import annotations

from services.retrieval.mcp.adapters import MCPConnectedSourceAdapter, MCPConnectedSourceError


class LocalMCPConnectedSourceAdapter(MCPConnectedSourceAdapter):
    """Local stdio MCP adapter.

    This class exists to keep local-command MCP separate from hosted remote MCP
    at the transport boundary. It intentionally only uses stdio command config.
    """


__all__ = ["LocalMCPConnectedSourceAdapter", "MCPConnectedSourceError"]
