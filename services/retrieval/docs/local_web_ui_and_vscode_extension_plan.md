# Local Web UI Product Plan

## Decision

The final user-facing product for Guided Intelligence retrieval should be a local web UI backed by a local Python service.

The product direction is an **Onyx-inspired chat + retrieval dashboard**:

- chat-style prompt and run interface,
- source/category filters per run,
- connection setup and status screens,
- evidence and citation inspection,
- role-bucket and sufficiency visibility,
- trace and run comparison tools.

There is no VS Code extension roadmap for this plan. The local web UI is the product surface.

## Onyx References

Onyx is a UX and product reference only. This plan does not require forking Onyx or copying Onyx code.

References to keep in mind:

- Onyx connector setup and status UX: https://docs.onyx.app/admins/connectors/overview
- Onyx connector concept: https://docs.onyx.app/overview/core_features/connectors
- Onyx chat UI: https://docs.onyx.app/overview/core_features/chat
- Onyx GitHub connector behavior: https://docs.onyx.app/admins/connectors/official/github
- Onyx agents page as a non-goal reference: https://docs.onyx.app/overview/core_features/agents

## Why This Product Shape

Existing RAG products provide strong connector and chat UX, but this project is not a generic document chat system.

Guided Intelligence should remain centered on:

- code-aware retrieval orchestration,
- role-specific evidence buckets,
- source policy,
- coverage and sufficiency checks,
- line-range code evidence,
- explicit traceability,
- explanation generation grounded in selected evidence.

The web UI should borrow Onyx-style usability for setup and interaction while keeping the retrieval pipeline as the authoritative centerpiece.

## Target Architecture

```text
Browser UI
  -> local HTTP API
  -> Python orchestration/retrieval service
  -> CGC + Qdrant + LLM stages
  -> MCP preset sources
  -> run artifacts and trace viewer
```

The Python service owns retrieval behavior and live runtime config. The frontend edits config through service endpoints; the service validates, persists non-secret config, updates in-memory state, and applies changes to the next run.

## Frontend Direction

Use:

```text
Vite + React + TypeScript
```

Likely supporting libraries:

- TanStack Query for config, run, trace, and connection requests,
- a small component library or local components for forms, tabs, tables, and panels,
- plain CSS/Tailwind depending on existing project preference at implementation time.

Do not use Next.js for v1. This is a local dashboard, and the Python service is the backend.

## Local Service Responsibilities

The local Python service should expose a stable API for the UI and keep the current retrieval rules intact.

Responsibilities:

- discover and validate workspace configuration,
- own active runtime config,
- apply config changes without restart when possible,
- start retrieval runs,
- stream or poll run progress,
- expose run results and trace events,
- test MCP/source connections,
- save non-secret project config,
- read secrets from `.env`, environment variables, or a local secret store,
- preserve the LLM failure policy: no silent fallback when an LLM-backed stage is required.

Suggested API:

```text
GET  /health
GET  /workspaces/current
POST /workspaces/open
GET  /config
PUT  /config
POST /config/reload
GET  /connections
POST /connections
POST /connections/test
POST /retrieve
GET  /runs
GET  /runs/{run_id}
GET  /runs/{run_id}/trace
GET  /runs/{run_id}/artifacts/{name}
POST /runs/{run_id}/cancel
```

## Configuration Model

Non-secret project config should live at:

```text
.guided-intelligence/config.json
```

Secrets should not be committed. They should live in:

- `.env`,
- environment variables,
- OS keychain or another local secret store.

Config changes should apply immediately for:

- enabled source categories,
- MCP source configs,
- result limits,
- query tool names,
- local note paths,
- source policy defaults,
- model settings when credentials are valid.

Explicit actions may still be required for:

- rebuilding indexes,
- switching workspace root,
- changing server port,
- changing Python environment,
- restarting Qdrant,
- installing missing MCP server dependencies.

## Web UI Features

### 1. Workspace Setup

Purpose:

- connect the tool to any local codebase,
- show readiness before a run,
- prevent silent expensive operations.

Show:

- workspace root,
- Git repository status,
- `.env` retrieval config status,
- LLM config status,
- embedding config status,
- Qdrant status,
- CGC status,
- local index status,
- last successful run.

Actions:

- choose workspace,
- initialize local config,
- validate environment,
- rebuild indexes,
- open config file,
- open run directory.

### 2. Connections View

Use Onyx-style connector tiles and status flows, adapted to our MCP-first source model.

Connection groups:

```text
Source Code        Built in
Documentation      Built in
GitHub Issues      MCP preset
GitHub PRs         MCP preset
Local Notes        Obsidian
NotebookLM         Attached snippets / future adapter
Custom MCP         User-defined
```

Each connection should support:

- enable / disable,
- configure,
- test connection,
- show status,
- show last error,
- remove.

MCP connection fields map to `MCPConnectedSourceConfig`:

```text
name
source_category
command
args
cwd
query_tool_name
query_argument_name
limit_argument_name
result_limit
timeout_seconds
static_tool_arguments
id_fields
title_fields
content_fields
```

Preset connections:

- GitHub issues,
- GitHub pull requests,
- project documentation MCP server,
- custom MCP.

Do not implement native sync connectors in v1. Use MCP presets and explicit connected-source documents.

### 3. Chat + Retrieval Screen

The main entrypoint should feel like a focused chat interface, but the result is a retrieval/explanation run, not generic chat.

Inputs:

- prompt/question,
- allowed source categories,
- optional run label,
- source preset/profile,
- indexing toggle when relevant,
- connected-source toggle when relevant.

Output summary:

- run ID,
- coverage status,
- sufficient,
- selected evidence count,
- retrieval token total when available,
- source categories queried,
- connected MCP sources queried,
- failures or fallbacks.

The UI should keep the user aware that the answer is grounded in selected evidence and source policy.

The first response should use the guided explanation turn model:

- show the grounded explanation,
- show up to three understanding-check questions in one shared box,
- put an inline textarea under each question,
- put a click-to-reveal hint under each textarea,
- submit all answers together,
- block another prompt in the same run until the questions are answered.

Question 1 should come from the main retrieved role. Secondary questions should identify whether they came from supporting-role, verification, caller-flow, diagnostic, or test evidence.

### 4. Evidence Panel

Evidence should be first-class, not hidden behind citations.

Evidence cards should show:

- source category,
- source ID,
- path or external URL,
- line range when available,
- role / coverage area,
- retrieval path,
- snippet,
- rank,
- selection reason when available.

For source-code evidence:

- show file path and line range,
- copy source ref,
- open file location through a local file link or service endpoint,
- show nearby context if available.

For external evidence:

- show normalized connected-source content,
- show URL when metadata has one,
- show originating adapter, MCP source, and MCP tool.

### 5. Role Bucket and Sufficiency View

This is the main product difference from generic RAG tools.

Show:

- required roles,
- supporting roles,
- role status,
- accepted refs,
- rejected refs,
- satisfying refs,
- missing reason,
- snippet assessment,
- deterministic coverage gate,
- final `coverage_status`,
- final `sufficient`.

This view should make it obvious why a run is strong, partial, missing, or failed.

### 6. Trace Inspector

The trace inspector should replace manual JSONL reading for normal debugging.

Group events by:

- setup / indexing,
- connected source search,
- Step 2 planning,
- CGC narrowing,
- Qdrant search,
- role buckets,
- refinement,
- synthesis,
- evidence selection,
- failures.

Controls:

- filter by event type,
- filter by role,
- filter by source category,
- filter by tool name,
- expand raw payload,
- copy event JSON.

Important summaries:

- required roles and status,
- accepted / rejected refs,
- missing roles,
- follow-up queries,
- connected MCP source refs,
- token usage events.

### 7. Run History and Comparison

Run history should support retrieval development and benchmark-style comparison.

Run list fields:

- run ID,
- timestamp,
- workspace,
- prompt,
- coverage status,
- sufficient,
- selected files,
- retrieval token total,
- source categories used.

Comparison fields:

- evidence added / removed,
- coverage status change,
- sufficiency change,
- token delta,
- source category changes,
- notable trace differences.

The first version can compare two local runs. CodeRepoQA benchmark integration can come later.

### 8. Settings and Health

Use an Onyx-style settings/admin feel, but local and single-user.

Sections:

- model/LLM config,
- embedding config,
- Qdrant config,
- CGC config,
- indexing status,
- source policy defaults,
- run artifact location,
- environment validation,
- raw config editor.

The settings screen should validate before saving and redact secrets.

## Onyx Features To Keep, Adapt, Or Drop

### Keep / Adapt

- connector tiles and setup flow,
- credential/config/test/status screens,
- GitHub issue/PR source concept through MCP presets,
- chat input as the main user entrypoint,
- source filters per run,
- run history and query history concept,
- settings/health page for model, Qdrant, CGC, and indexing status.

### Make Unique To Guided Intelligence

- role buckets,
- coverage/sufficiency status,
- selected/rejected evidence,
- retrieval token totals,
- trace event explorer,
- code line-range evidence as first-class output,
- source policy and LLM failure policy visibility.

### Drop For V1

- VS Code extension,
- full Onyx-style agent builder,
- multi-user/admin permissions,
- enterprise access sync,
- generic organization analytics,
- native sync connectors beyond MCP presets,
- hosted deployment.

## Agent / Persona Stance

Do not implement a full Onyx-style agent builder in v1.

The product should have one guided explanation/retrieval workflow. Later, it may add lightweight saved profiles for:

- source selections,
- model settings,
- explanation style,
- benchmark mode,
- connected-source presets.

These profiles should not become arbitrary autonomous agents in v1.

## MVP Order

1. Local service API.
2. Chat + retrieval screen.
3. Evidence panel.
4. Trace inspector.
5. MCP connections screen.
6. GitHub MCP preset.
7. Run history and comparison.
8. Config/settings UI.

## Non-Goals For V1

- no VS Code extension,
- no hosted multi-user service,
- no full agent/persona builder,
- no enterprise permission sync,
- no generic organization analytics,
- no native connector sync framework beyond MCP presets,
- no silent background LLM runs,
- no automatic secrets committed to the repo,
- no replacing the CLI/benchmark runner,
- no indexing arbitrary external MCP documents into Qdrant until quality and token behavior are measured.

## Open Questions For The Implementation Phase

- Should the local service use FastAPI or the standard library?
- Should the UI use Tailwind, a component library, or local CSS?
- Should config be JSON only, or should TOML remain supported for advanced users?
- Should run progress use polling first or streaming from the start?
- Should run artifacts default to `.guided-intelligence/runs` or reuse the configured run directory?
- What local secret store should be supported first beyond `.env`?

## Recommended Next Step

Implement the local Python service first with a minimal API:

```text
GET  /health
GET  /config
PUT  /config
POST /retrieve
GET  /runs/{run_id}
GET  /runs/{run_id}/trace
POST /connections/test
```

Then build the React UI against that API. The first frontend should prioritize one high-quality flow:

```text
configure workspace -> run retrieval from chat prompt -> inspect evidence -> inspect trace
```

## First Implementation Slice

The first local web slice is implemented as:

```text
services/retrieval/server.py
ui/
```

Run the API:

```bash
npm run retrieval:server
```

Run the web UI:

```bash
npm run web:dev
```

Build the web UI:

```bash
npm run web:build
```

Current implemented API surface:

```text
GET  /health
GET  /config
PUT  /config
GET  /connections
POST /connections/test
POST /retrieve
GET  /runs
GET  /runs/{run_id}
GET  /runs/{run_id}/trace
POST /workspaces/open
```

Current implemented UI surface:

- chat + retrieval run form,
- source-category filters,
- health/status strip,
- connection tiles,
- run history,
- evidence panel,
- trace inspector,
- settings summary.

The `/retrieve` endpoint runs the existing `ControlLayer` and `WorkspaceRetrievalStage`, writes run artifacts under `.guided-intelligence/runs`, and returns a run summary. It will fail explicitly if required LLM, embedding, Qdrant, or CGC configuration is missing.
