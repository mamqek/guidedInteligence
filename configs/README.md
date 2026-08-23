# Run Configs

Centralized run profiles live here. Keep reusable execution policy in these files; pass case-specific
paths at the command line unless a batch profile intentionally lists cases.

## Web UI

Web UI profiles are workspace config templates. Apply one to the selected workspace, then start the
server.

```powershell
npm run config:web:workspace
npm run retrieval:server
```

```powershell
npm run config:web:agentic
npm run retrieval:server
```

`config:web:agentic` keeps the native Qdrant + CodeGraph prefix, then replaces owner comparison,
qualification, controller rounds, recovery/island stages, and final evidence selection with the bounded
seeded-agent loop. Initial retrieval results are hints: the agent can inspect graph neighbors and search or
open other allowed repository paths. Dense+sparse Qdrant search remains enabled by default.

```powershell
npm run config:web:codex
npm run retrieval:server
```

`config:web:codex` uses the restored `efficient` prompt contract. The explicit Codex prompt-profile commands are:

```powershell
npm run config:web:codex:efficient
npm run config:web:codex:responsibility-complete
```

The prompt and strict output schema for each profile live together under
`services/retrieval/codex/profiles/<profile>/`. The responsibility-complete profile is the slower,
quality-oriented experiment; it is never selected implicitly.

The selected workspace remains the server `--workspace-root` or the current directory. Do not create
one web config per workspace unless the workspace itself needs different persistent settings.

## Testing

Testing profiles set benchmark policy: retrieval mode, model, timeout, shared repo root, and index
behavior. The testcase path normally stays in the command:

```powershell
npm run coderepoqa:evaluate:workspace -- --issue-json testing/codeRepoQA/corpus/cases/microsoft-TypeScript-35468/issue.json
```

```powershell
npm run coderepoqa:evaluate:agentic -- --issue-json testing/codeRepoQA/corpus/cases/microsoft-TypeScript-35468/issue.json
```

The checked-in agentic test profile explicitly uses Codex CLI for JSON decisions and sparse Qdrant search
because the current development API account cannot serve LLM or embedding requests. This is an environment
profile, not the production default; `configs/web-ui/agentic.json` keeps dense retrieval enabled.

```powershell
npm run coderepoqa:evaluate:codex -- --issue-json testing/codeRepoQA/corpus/cases/microsoft-TypeScript-35468/issue.json
```

`coderepoqa:evaluate:codex` uses the `efficient` profile. Explicit profile commands are:

```powershell
npm run coderepoqa:evaluate:codex:efficient -- --issue-json <case issue.json>
npm run coderepoqa:evaluate:codex:responsibility-complete -- --issue-json <case issue.json>
```

For repeated cases, use the matching `coderepoqa:batch:codex:efficient` or
`coderepoqa:batch:codex:responsibility-complete` command and pass repeated `--issue-json` values.

Batch profiles can list cases, or the command can pass repeated `--issue-json` values:

```powershell
npm run coderepoqa:batch:codex
```

This keeps benchmark settings centralized without creating a separate profile for every testcase.
