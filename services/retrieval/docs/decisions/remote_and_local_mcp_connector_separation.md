# Remote And Local MCP Connector Separation

## Decision

Hosted SaaS connectors and local/private connectors must be configured and executed as separate connector types.

Remote MCP is the default shape for hosted providers that operate their own MCP endpoint and authentication flow. Local MCP remains an advanced integration path for local tools, private scripts, self-hosted services, and providers without a hosted MCP endpoint.

There must be no silent fallback between them. If a remote MCP connector fails, retrieval logs the remote failure and continues with other enabled sources. It must not try to start a local command. If a local MCP connector fails, retrieval logs the local failure and must not try a hosted provider endpoint.

Both paths normalize into the same retrieval contract:

```text
remote MCP provider OR local MCP command OR direct source adapter
  -> ConnectedSourceDocument
  -> connected-source evidence candidates
  -> existing retrieval planner and evidence selection
```

## Provider Direction

The initial hosted provider list is:

| Provider | Preferred connector | Expected workspace scope | Typical retrieval categories |
| --- | --- | --- | --- |
| GitHub | Remote MCP when available; built-in GitHub API remains a simple first-party path | repository or organization | issues, pull requests |
| Notion | Remote MCP | workspace, page, database | documentation, local/project notes |
| Atlassian Jira | Remote MCP through Atlassian/Rovo MCP | site, project | issue tracker |
| Atlassian Confluence | Remote MCP through Atlassian/Rovo MCP | site, space | documentation |
| Atlassian Compass | Remote MCP through Atlassian/Rovo MCP | site/component catalog | documentation, ownership context |
| Shortcut | Remote MCP | workspace/team/project | issue tracker, planning docs |
| Linear | Remote MCP if available | workspace/team/project | issue tracker |
| Slack | Remote MCP if available | workspace/channel | project discussion, decision context |
| Google Drive | Remote MCP if available | drive/folder/file scope | documentation |

Known hosted endpoint defaults should be prefilled but editable:

- GitHub: `https://api.githubcopilot.com/mcp/`
- Notion: `https://mcp.notion.com/mcp`
- Atlassian Jira/Confluence/Compass: `https://mcp.atlassian.com/v1/mcp/authv2`
- Shortcut: `https://mcp.shortcut.com/mcp`
- Linear: `https://mcp.linear.app/sse`
- Slack: `https://mcp.slack.com/mcp`
- Google Drive: `https://drivemcp.googleapis.com/mcp/v1`

Do not treat a missing or changed endpoint as a reason to fall back to local MCP. The user should correct the hosted endpoint or configure a separate local MCP connector explicitly.

Provider support should be product-level in the UI. Users should not need to understand command names, stdio transport, raw tool names, or MCP JSON-RPC details to enable hosted connectors.

## Remote MCP

Remote MCP connectors represent hosted provider endpoints.

They should store:

- provider name,
- display name,
- enabled flag,
- source category,
- remote MCP endpoint URL,
- OAuth/connect URL when provided by the provider,
- optional OAuth/session access token when the provider login flow returns one outside this app,
- optional bearer token when the provider supports token auth,
- optional API-key header name and API key when the provider supports header credentials,
- selected workspace scope such as repository, Jira project, Notion database, Slack channel, or Drive folder,
- enabled feature toggles such as issues, pull requests, pages, documents, messages, comments, or reviews,
- query tool mapping when automatic tool discovery is not enough.

Remote MCP failure behavior:

- do not start a local MCP command,
- do not switch to direct API unless the connector is explicitly configured as that direct adapter,
- record the provider, endpoint, source category, and error in retrieval trace,
- continue with other enabled source categories.

## Local MCP

Local MCP connectors represent a command that runs on the user machine and communicates over stdio.

They should store:

- command,
- args,
- cwd,
- env,
- source category,
- query tool mapping,
- result normalization fields.

Local MCP is appropriate for:

- Obsidian/local tools,
- private internal tools,
- local databases,
- company scripts,
- self-hosted services,
- offline or localhost-only workflows,
- providers without hosted MCP.

Local MCP failure behavior:

- do not call a remote MCP endpoint,
- do not switch to a hosted provider connector,
- record command, source name, source category, and error in retrieval trace,
- continue with other enabled source categories.

## Evidence Boundary

Remote and local MCP are source-access details only. They must not change retrieval’s evidence boundary.

Every connector must normalize into `ConnectedSourceDocument` before entering retrieval planning. The planner should not know whether a document came from hosted MCP, local MCP, GitHub API, Obsidian search, or an attached document.

Connected-source evidence can guide code retrieval, explain product intent, and provide decision context. It must not replace source-code evidence when an answer requires code grounding.

## UI Shape

The Connections UI should present hosted connectors as product-level cards:

- GitHub,
- Notion,
- Jira / Atlassian,
- Shortcut,
- Linear,
- Slack,
- Google Drive.

Each card should expose:

- enabled checkbox,
- connect with OAuth button when an OAuth URL is configured,
- optional token/API key field when direct credentials are allowed,
- scope field such as repository/project/workspace/folder/channel,
- feature toggles for the source types that provider can return,
- test connection button.

Advanced local MCP configuration should stay separate from hosted connector cards. It should not appear as the default GitHub/Notion/Jira/Shortcut setup path.

## Retrieval Integration

Retrieval should collect connected-source documents in this order:

1. Direct in-memory attached connected documents.
2. Built-in local adapters such as Obsidian.
3. Built-in direct provider adapters explicitly configured as direct adapters, such as the current simple GitHub API path.
4. Remote MCP connectors.
5. Local MCP connectors.

The ordering is not a fallback chain. It is only a source collection order. A failing connector does not cause another connector type to impersonate it.

All successful connector results are merged as `ConnectedSourceDocument` records and weighted by the existing connected-source evidence logic.

## Implementation Notes

Remote and local MCP handlers should live in different files:

- `services/retrieval/mcp/remote.py`
- `services/retrieval/mcp/local.py`

Shared normalization code can stay in a common module, but transport, auth, and failure handling should be separate.

The initial remote MCP implementation supports:

- HTTP JSON-RPC tool calls to a configured endpoint,
- bearer-token headers,
- OAuth/session access-token headers,
- API-key headers,
- static headers,
- tool call normalization into `ConnectedSourceDocument`,
- explicit failure without local fallback.

Full OAuth callback handling can be added after the remote transport is in place. Until then, UI exposes provider OAuth/connect URLs plus explicit OAuth/session, bearer-token, and API-key credential fields so the connection model is visible without pretending local command MCP is equivalent.
