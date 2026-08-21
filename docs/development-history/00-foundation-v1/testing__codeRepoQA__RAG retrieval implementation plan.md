# CodeRepoQA RAG Retrieval Implementation Plan

## Purpose

This plan makes local RAG the next implementation focus for CodeRepoQA evaluation. Open SWE stays deferred until the repository can produce useful, traceable retrieval evidence locally.

The first target is Stage 1 `EXPLAIN` for a CodeRepoQA historical issue:

```text
allowed input:
- initial issue body
- repo-pre source code

not allowed:
- later issue comments
- linked pull requests
- diffs
- post-resolution code
- hidden evaluator dossier
```

The implementation should prove that the system can load a historical issue, split visible case data from hidden evaluator data, build a controlled retrieval intent, retrieve pre-resolution code evidence, validate evidence metadata, and emit replayable evidence and trace artifacts that can feed the expanded `EXPLANATION` response contract.

## Target Retrieval Flow

Use a staged flow with a few sequential gates and a simple first implementation. Do not build a fully parallel or agentic retriever yet.

First runnable flow:

```text
policy + visible case split
-> prompt parsing / bounded query decomposition
-> connector enrichment if explicitly referenced and allowed
-> BM25 exact chunk retrieval over the full prebuilt repo-pre index
-> simple deterministic ranking
-> evidence validation / gap check
-> selected EvidenceItem values + retrieval trace
```

The main design rule is:

```text
Prompt splitting must not cause the full retrieval pipeline to run repeatedly.
```

The public retrieval API must remain the existing repo contract:

```text
RetrievalService.plan(state, decision) -> RetrievalPlan
RetrievalService.retrieve(plan) -> Sequence[EvidenceItem]
```

`RetrievalIntent` is an internal planning object used by the CodeRepoQA retrieval implementation. It must not become a second public retrieval API. `CodeRepoQARetrievalService.plan(...)` should build one bounded `RetrievalIntent` containing entities, source hints, and at most five subqueries, then attach it to the returned `RetrievalPlan` either through typed evaluation metadata or a narrow `CodeRepoQARetrievalPlan` extension. `CodeRepoQARetrievalService.retrieve(plan)` is the only method that may execute local visible-case connector enrichment, BM25 search, ranking, and validation steps.

Each retrieval source then handles that one internal bundle once, with caps and deduplication.

The intended call shape is:

```text
ConversationState
-> V1PolicyEngine.decide(state)
-> OrchestratorDecision
-> CodeRepoQARetrievalService.plan(state, decision)
   -> builds RetrievalIntent internally
   -> returns RetrievalPlan
-> CodeRepoQARetrievalService.retrieve(plan)
   -> runs local visible-case connector enrichment and BM25 internally
   -> returns EvidenceItem values
-> retrieval trace records gaps, rejected candidates, and coverage
```

The intended role of each context source is:

- Local visible-case connector enrichment provides the allowed issue title and initial body.
- BM25 retrieves exact source chunks from the full prebuilt repo-pre index.
- Markdown wiki orientation, symbol/file metadata boosts, live connectors, dense retrieval, parallel fan-out, LLM reranking, and response generation are later extensions.

## First Runnable Slice

The first implementation target is a local retrieval test, not a complete assistant response.

Goal:

```text
Run TypeScript #6 Stage 1 retrieval locally and produce replayable trace artifacts.
```

Included:

- Load `testing/codeRepoQA/6.json`.
- Build `VisibleCodeRepoQACase` and `HiddenCodeRepoQACase`.
- Resolve `RunConfig` to `SourcePolicy(ISSUE_TRACKER, SOURCE_CODE)`.
- Create `ConversationState`.
- Call `V1PolicyEngine(source_policy=resolved_policy).decide(state)`.
- Run `prepare-index` to chunk `repo-pre` and build a BM25 index.
- Run `run-case` to build the internal `RetrievalIntent`, query the prebuilt BM25 index, validate evidence metadata, and return `EvidenceItem` values.
- Write `retrieval-intent.json`, `evidence-items.json`, and `retrieval-trace.jsonl`.

Excluded from the first runnable slice:

- Markdown wiki orientation.
- Symbol/file metadata boosts.
- Connector adapters beyond the local visible CodeRepoQA case.
- Response generation.
- Full `confirmed_from_evidence` / `hypotheses_to_investigate` response construction.
- Dense retrieval, LLM reranking, Open SWE, LangGraph, and live external connectors.

These exclusions should not be planned in implementation detail yet. After the first runnable retrieval test produces traces, create a new document for whichever extension is next, based on observed retrieval misses, trace quality, and implementation friction.

## Key Internal Data Shapes

Keep these outside `core` initially, under `services/retrieval` or `services/retrieval/experiments`, so the policy core stays stable.

### Run Configuration Controller

Add a small run-configuration layer above `V1PolicyEngine` so evaluation runs do not rely on the broad default source policy from `core/source_policy.py`.

The code-defined `SourceCategory` enum remains the closed vocabulary of allowed category names. Configuration may choose only from those code-defined categories; it must not invent new category strings. Unknown configured categories should fail fast before any policy or retrieval step runs.

For CodeRepoQA Stage 1, the run configuration must use exactly:

```python
SourcePolicy(
    allowed_categories=(
        SourceCategory.ISSUE_TRACKER,
        SourceCategory.SOURCE_CODE,
    ),
    policy_name="coderepoqa_explain_initial",
)
```

This is intentionally narrower than `DEFAULT_SOURCE_POLICY`, which also allows `DOCUMENTATION` and `PULL_REQUEST`. Stage 1 is testing pre-resolution reasoning from only the initial issue and `repo-pre` source code, so pull requests are hidden evaluator material and documentation/wiki content is not allowed as user-visible evidence unless a later explicit policy permits pre-resolution documentation.

Suggested configuration shapes:

```python
@dataclass(frozen=True)
class RunSourceConfig:
    policy_name: str
    allowed_categories: tuple[SourceCategory, ...]
    visibility_scope: str
    snapshot_scope: str
    allow_generated_orientation: bool = False


@dataclass(frozen=True)
class RunConfig:
    run_id: str
    case_id: str
    stage: ResponseStage
    source_config: RunSourceConfig
    retrieval_config: Mapping[str, str]
    logging_config: Mapping[str, str]


class RunConfigController:
    def source_policy_for(self, config: RunConfig) -> SourcePolicy:
        ...
```

Responsibilities:

- `RunSourceConfig` is the run-controlled source setting: category allowlist, visibility scope, snapshot scope, and whether generated orientation is allowed.
- `RunConfig` ties source settings to the case, stage, retrieval settings, and logging settings for one run.
- `RunConfigController` validates configured categories against `SourceCategory`, constructs the `SourcePolicy`, and exposes visibility/snapshot settings to the case loader and retrieval service.
- `SourcePolicy` remains the core category allowlist consumed by `V1PolicyEngine`.
- Evaluation visibility remains outside `core`. For v1, enforce it by splitting the CodeRepoQA case into visible and hidden data before retrieval starts, then validating evidence metadata after retrieval.

The controller should be the single place where CodeRepoQA Stage 1 says:

```text
source categories = ISSUE_TRACKER, SOURCE_CODE
visibility scope = visible_initial
snapshot scope = pre_resolution
pull requests = disallowed
documentation/wiki = not user-visible evidence
```

Do not add a separate visibility-rule engine in v1. If an artifact is not in the visible case object or the configured `repo-pre` snapshot, it cannot be retrieved during Stage 1.

### Public Retrieval Boundary

The existing retrieval service contract is the boundary that orchestration and future runtime integrations should call.

```python
class RetrievalService(Protocol):
    def plan(self, state: ConversationState, decision: OrchestratorDecision) -> RetrievalPlan:
        ...

    def retrieve(self, plan: RetrievalPlan) -> Sequence[EvidenceItem]:
        ...
```

Responsibilities:

- `ConversationState` is policy-facing interaction state: current user input, stage, history, and already attached evidence.
- `V1PolicyEngine.decide(...)` owns stage policy, retrieval permission, response template selection, and allowed source categories.
- `OrchestratorDecision` carries that policy result downstream. Retrieval code must obey it and must not reinterpret source policy.
- `RetrievalService.plan(...)` is the only public planning entrypoint. For CodeRepoQA, this is where visible case metadata, snapshot metadata, and deterministic query decomposition are combined.
- `RetrievalPlan` is the public retrieval plan returned by `plan(...)`. It should include ordered allowed sources, a coarse query string for the existing contract, and enough metadata to replay the run.
- `RetrievalIntent` is private to the CodeRepoQA retrieval implementation. It structures entities, subqueries, source hints, and temporal scope for internal retrievers.
- `RetrievalService.retrieve(...)` is the only public execution entrypoint. It consumes a `RetrievalPlan`, reads the internal intent from metadata or a typed extension, runs retrievers, validates evidence, and returns `EvidenceItem` values.
- `EvidenceItem` is the stable downstream evidence type. Response builders and policy tests should not need to know whether evidence came from BM25, symbol metadata boosts, or connector enrichment.
- Retrieval trace artifacts are append-only evaluation records built around `RetrievalPlan`, internal intent, candidates, selected `EvidenceItem` values, rejections, and gap checks. They must not replace `EvidenceItem` or `ResponseContract`.

Do not add direct orchestration calls such as:

```text
build RetrievalIntent -> run BM25 -> build response-shaped context object
```

That path bypasses `RetrievalService` and creates a parallel retrieval API.

### `RetrievalIntent`

Structured output from prompt parsing and bounded decomposition. This object is internal to the CodeRepoQA retrieval service.

```python
@dataclass(frozen=True)
class RetrievalIntent:
    conversation_id: str
    case_id: str
    task_type: str
    raw_prompt: str
    entities: tuple[str, ...]
    subqueries: tuple[str, ...]
    source_hints: tuple[SourceCategory, ...]
    temporal_scope: str
    connector_refs: tuple[str, ...]
    metadata: Mapping[str, str]
```

For TypeScript issue #6, the expected `subqueries` should be capped to these themes:

- parser and modifier handling
- class declaration representation
- constructor / `new` checks
- inheritance and subclass checking
- diagnostics and conformance tests

### Visible And Hidden Case Data

Use simple typed case shapes to enforce visibility by construction.

```python
@dataclass(frozen=True)
class VisibleCodeRepoQACase:
    case_id: str
    repo_owner: str
    repo_name: str
    issue_number: int
    title: str
    created_at: str
    initial_body: str
    repo_pre_path: str
    repo_pre_commit: str


@dataclass(frozen=True)
class HiddenCodeRepoQACase:
    case_id: str
    hidden_fields: Mapping[str, object]
```

Responsibilities:

- `VisibleCodeRepoQACase` is the only case object passed to `ConversationState`, `CodeRepoQARetrievalService.plan(...)`, and `CodeRepoQARetrievalService.retrieve(...)` during Stage 1.
- `HiddenCodeRepoQACase` is evaluator-only and must not be passed to Stage 1 retrieval or response generation.
- The case loader owns the split. It should not rely on later retrievers to remember which issue JSON fields are hidden.
- Evidence validation still checks `visibility`, `snapshot`, and `commit` metadata as a second safety check, but the main visibility boundary is the visible/hidden case split.

### `ConnectorArtifact`

Normalized external context from local CodeRepoQA data or future live connectors.

```python
@dataclass(frozen=True)
class ConnectorArtifact:
    artifact_id: str
    source_category: SourceCategory
    visibility: str
    policy_name: str
    title: str
    body: str
    metadata: Mapping[str, str]
```

Stage 1 connector artifacts must be built only from `VisibleCodeRepoQACase`. Later comments, labels, PR links, and hidden resolution context remain evaluator-only in `HiddenCodeRepoQACase`.

### `IndexedChunk`

Offline-indexed searchable unit from source code. The first runnable slice should keep chunking simple: path, line range, snapshot, commit, text, and minimal metadata needed for replay.

```python
@dataclass(frozen=True)
class IndexedChunk:
    chunk_id: str
    source_category: SourceCategory
    snapshot: str
    commit: str
    path: str
    line_start: int | None
    line_end: int | None
    text: str
    symbols: tuple[str, ...]
    metadata: Mapping[str, str]
```

Chunks must be built before conversation time. The harness should fail fast if the required index is missing.

The searchable BM25 document for the first runnable slice should include:

```text
path
file basename
code text
```

Do not stuff generated summaries, full AST dumps, all imports, broad neighboring-file content, or speculative subsystem labels into v0 chunks. Start with code text and path data; add richer metadata only after traces show that plain BM25 is missing important evidence.

### Offline Symbol/File Metadata

Deferred extension. Do not build this in the first runnable slice.

Later, if plain BM25 traces show systematic misses, build lightweight symbol/file metadata during `prepare-index` and attach it to `IndexedChunk` values. This should enrich ranking and logs, not become a hard retrieval filter.

```python
@dataclass(frozen=True)
class SymbolFileMetadata:
    path: str
    symbols: tuple[str, ...]
    imports: tuple[str, ...]
    exports: tuple[str, ...]
    inheritance_terms: tuple[str, ...]
    subsystem_hint: str | None
    metadata: Mapping[str, str]
```

Responsibilities:

- Enrich chunks and BM25 documents with cheap structural signals.
- Provide deterministic ranking boosts for path, symbol, and subsystem matches.
- Avoid narrowing BM25 to only graph-selected files in v1.

Full graph expansion, dataflow, and CodeGraphContext MCP integration are later work.

### `RetrievalCandidate`

Unified candidate from local visible-case connector enrichment or BM25 in the first runnable slice. Optional wiki orientation, dense retrieval, and symbol/file metadata boosts are later extensions. Symbol/file metadata boosts are ranking internals, not separate candidate sources.

```python
@dataclass(frozen=True)
class RetrievalCandidate:
    candidate_id: str
    source_category: SourceCategory
    retrieval_path: str
    text: str
    score: float
    path: str | None
    line_range: str | None
    metadata: Mapping[str, str]
```

The `retrieval_path` should identify where the candidate came from. In the first runnable slice this should be `connector` or `bm25`. Later values may include `wiki` or `dense`.

If symbol/file boosts are added later, ranking internals such as path, symbol, or subsystem boosts should be logged only in `metadata`, for example:

```json
{
  "retrieval_path": "bm25",
  "metadata": {
    "base_bm25_score": "12.4",
    "boosts_applied": "path_match,symbol_match",
    "final_score": "14.4"
  }
}
```

Do not expose boosts as public evidence sources. They explain why a BM25 candidate ranked higher; they do not create evidence by themselves.

### Response Contract Inputs

Deferred for response generation. Do not add a first-class `ContextPackage` in v1. When response generation is added, the response layer should use the existing contracts:

```text
OrchestratorDecision
+ ResponseContract from contract_for_decision(decision)
+ selected EvidenceItem values
+ retrieval trace / gap-check records
-> ResponsePayload
```

Responsibilities:

- `ResponseContract` defines required output sections for the selected stage, such as `summary`, `evidence`, `reasoning_path`, `confirmed_from_evidence`, `hypotheses_to_investigate`, and `knowledge_check_question`.
- `ResponseBuilder` fills those sections from selected `EvidenceItem` values and retrieval trace records.
- `confirmed_from_evidence` is derived only from strong selected `EvidenceItem` values whose metadata identifies source policy, snapshot, visibility, retrieval reason, and line/path provenance.
- `hypotheses_to_investigate` is derived from important issue requirements or subqueries that have weak, indirect, or partial evidence.
- `missing_context` is not a response contract section in v1. The retrieval service records missing or weak coverage in `retrieval-trace.jsonl`; the response builder may mention it under `hypotheses_to_investigate` or uncertainty language if needed.
- `evidence_items` remain `EvidenceItem` values. There is no separate response-shaped evidence container.

Retrieval must not overclaim. It may emit evidence snippets, retrieval reasons, coverage areas, evidence strength, rejection reasons, and gap records. It must not write final explanatory claims such as "the compiler must change X" or "this is confirmed behavior" unless that text is a deterministic label tied directly to selected evidence metadata. Turning evidence into `confirmed_from_evidence` and `hypotheses_to_investigate` belongs to the response builder.

## Implementation Tasks

### 1. Offline Case And Snapshot Preparation

Implement a local case loader for `testing/codeRepoQA/6.json`.

Required behavior:

- Read CodeRepoQA issue JSON from disk.
- Build `case_id`, for example `microsoft-TypeScript-6`.
- Build `VisibleCodeRepoQACase` with only repo owner/name, issue number, title, created date, initial body, `repo-pre` path, and `repo-pre` commit.
- Build `HiddenCodeRepoQACase` with all hidden evaluator fields, but never pass it into Stage 1 retrieval.
- Require a configured `repo-pre` path and commit before retrieval starts.
- Store evidence metadata later with `snapshot="pre_resolution"` and `visibility="visible_initial"`.

Suggested files:

```text
testing/codeRepoQA/run_case.py
services/retrieval/cases.py
```

Acceptance criteria:

- Loading `6.json` produces `VisibleCodeRepoQACase` and `HiddenCodeRepoQACase`.
- Stage 1 visible context does not contain `comments_details`, `cite`, `cited_by`, `fixed_by`, or labels.
- Stage 1 retrieval receives only `VisibleCodeRepoQACase`, never the raw issue JSON or `HiddenCodeRepoQACase`.
- Missing `repo-pre` configuration fails with a clear message instead of cloning during conversation time.

### 1A. Run Configuration And Source Policy Resolution

Implement a run configuration controller for CodeRepoQA evaluation settings.

Required behavior:

- Load or construct one `RunConfig` for the Stage 1 TypeScript #6 run.
- Validate that every configured source category is a real `SourceCategory`.
- Resolve the Stage 1 `SourcePolicy` from `RunConfig.source_config`.
- For CodeRepoQA Stage 1, allow only `SourceCategory.ISSUE_TRACKER` and `SourceCategory.SOURCE_CODE`.
- Carry `visibility_scope="visible_initial"` and `snapshot_scope="pre_resolution"` into retrieval metadata for validation and logging.
- Fail fast if a run accidentally tries to use `DEFAULT_SOURCE_POLICY` for CodeRepoQA Stage 1.

Suggested files:

```text
testing/codeRepoQA/run_config.py
services/retrieval/config.py
```

Acceptance criteria:

- Stage 1 config resolves to policy name `coderepoqa_explain_initial`.
- Stage 1 config resolves to exactly `(SourceCategory.ISSUE_TRACKER, SourceCategory.SOURCE_CODE)`.
- Unknown category strings are rejected before `V1PolicyEngine.decide(...)`.
- The resolved policy is passed into `V1PolicyEngine(source_policy=...)`.

### 2. Prompt Parsing And Bounded Query Decomposition

Implement deterministic parsing first. Do not use an LLM splitter in v1.

This work belongs inside `CodeRepoQARetrievalService.plan(state, decision)`, not in the harness as a separate top-level call. The harness should call the retrieval service; the service should create and store the internal intent.

Required behavior:

- Extract repo references, issue number, title terms, quoted identifiers, fenced code identifiers, and likely source categories.
- Produce one internal `RetrievalIntent` for the whole retrieval run during `RetrievalService.plan(...)`.
- Return a `RetrievalPlan` that carries the internal intent through typed metadata or a narrow CodeRepoQA-specific plan extension.
- Generate at most five subqueries.
- Collapse duplicate terms across subqueries.
- Add `metadata["decomposition_strategy"] = "deterministic_v1"`.

Cost control:

- No subquery should trigger a full independent retrieval pipeline.
- BM25 search should receive the whole `RetrievalIntent` once from `RetrievalService.retrieve(plan)`.
- Per-subquery result caps are allowed inside each retriever, but final candidates must be deduplicated globally.
- The harness must not call BM25 or connector logic directly.

Acceptance criteria:

- TypeScript #6 produces no more than five subqueries.
- The intent includes entities such as `abstract`, `class`, `Base`, `Derived1`, `Derived2`, `getThing`, `super`, and `new`.
- The intent includes `SourceCategory.ISSUE_TRACKER` and `SourceCategory.SOURCE_CODE` as source hints for Stage 1.
- The trace contains both the public `RetrievalPlan` and the serialized internal `RetrievalIntent`.

### 3. Policy And Connector Enrichment Gate

Implement connector enrichment as an explicit policy-gated step.

Required behavior:

- Check `SourcePolicy` before any connector artifact is used.
- Build connector artifacts only from `VisibleCodeRepoQACase` during Stage 1.
- Implement `LocalCodeRepoQAConnector` first.
- Leave GitHub, Shortcut, and Slack as future adapters behind the same interface.
- Connector enrichment runs only when the case loader provides an artifact or the prompt contains a resolvable reference.

Stage 1 rule:

```text
Allowed SourceCategory values are ISSUE_TRACKER and SOURCE_CODE only.
Local CodeRepoQA / GitHub issue context means initial issue body only.
Pull requests and later issue comments are hidden evaluator material.
```

Acceptance criteria:

- Stage 1 connector artifact contains title and initial issue body only.
- Hidden issue comments and PR links are rejected or omitted before retrieval.
- Connector decisions are recorded in the retrieval trace.

### 4. Offline Index Preparation

Build the source index before conversation time.

The first runnable indexer should produce source chunks and a BM25 index over the full `repo-pre` snapshot. Do not build symbol/file metadata boosts in the first runnable slice.

Required command shape:

```text
prepare-index
  input: repo-pre path, repo-pre commit, case_id
  output: IndexedChunk[] + BM25 index

run-case
  input: visible case, resolved SourcePolicy, prebuilt index path
  output: EvidenceItem[] + retrieval trace
```

Required behavior:

- Chunk source files from `repo-pre` into `IndexedChunk` objects with path, line range, snapshot, and commit metadata.
- Build BM25 over chunk document text containing path, file basename, and code text.
- Store the chunk index and BM25 index under the case index directory.
- Ensure `run-case` loads prebuilt index artifacts only.

Do not implement graph-first retrieval, symbol/file metadata boosts, full dataflow, or CodeGraphContext/MCP in the first runnable slice.

Acceptance criteria:

- `prepare-index` creates chunks and a BM25 index before `run-case`.
- `run-case` fails fast if the required BM25 index is missing.
- Chunks are BM25-searchable by code text and path.
- No v1 retrieval step restricts BM25 to only graph-selected files.

### 5. BM25 Sparse Retrieval

Implement the first real source-code retriever with BM25 over the full prebuilt chunk index.

BM25 is the first real source-code evidence retriever. It should run inside `RetrievalService.retrieve(plan)` and return `RetrievalCandidate` values that can later be validated and converted into `EvidenceItem` objects.

Required behavior:

- Load the prebuilt BM25 index for `repo-pre`.
- Search all chunks in the BM25 index.
- Use the full `RetrievalIntent` once, with internal per-subquery caps.
- Deduplicate by `path`, `line_start`, and `line_end`.
- Prefer exact identifiers, diagnostics, syntax terms, and file names.

Cost control:

- Cap BM25 candidates before fusion, for example 40 total.
- Cap per-subquery results, for example 8.
- Do not build chunks or BM25 indexes during `run-case`.

Acceptance criteria:

- Retrieval returns concrete chunks with path, line range, commit, and snapshot metadata.
- TypeScript #6 searches for terms related to abstract classes without using hidden comments or PRs.
- BM25 can run without dense embeddings or model calls.
- BM25 searches the full prebuilt index.

### 6. Ranking And Cost Control

Start with deterministic scoring. Do not add LLM reranking yet.

Required behavior:

- Normalize local visible-case connector and BM25 outputs into `RetrievalCandidate`.
- Score candidates using a weighted formula.
- Keep the final evidence budget small, for example 8 to 12 chunks.
- Deduplicate near-identical snippets and overlapping line ranges.
- Prefer source-code evidence over issue-body connector context for source-code claims.

Suggested scoring signals:

```text
+ exact entity match
+ source allowed by active SourcePolicy
+ subquery coverage
+ source-code category for confirmed evidence
-- duplicate or near-duplicate chunk
-- hidden or wrong visibility
-- missing snapshot metadata
```

Later upgrades:

- reciprocal-rank fusion
- dense semantic retrieval
- parallel retriever fan-out
- CodeRAG-style BestFit reranking
- distilled local reranker

Acceptance criteria:

- Final selected evidence is capped.
- Ranking is deterministic for the same index and intent.
- Ranking logs explain why each selected item was kept.

### 7. Evidence Validation And Gap Check

Validate evidence before returning public evidence.

Validation is the last internal step of `RetrievalService.retrieve(plan)`. Only candidates that pass source-policy, visibility, snapshot, and metadata checks should become public `EvidenceItem` values.

Gap checking must be deterministic in v1. Do not use an LLM to decide whether evidence is confirmed, weak, or missing.

Use the coverage areas from `RetrievalIntent.subqueries` as the checklist. For TypeScript #6, that means checking coverage for parser/modifier handling, class representation, constructor/new checks, inheritance/subclass checks, and diagnostics/tests.

Suggested deterministic coverage rules:

```text
strong coverage:
  at least one valid selected EvidenceItem for the coverage area
  + correct SourcePolicy
  + visibility="visible_initial"
  + snapshot="pre_resolution"
  + commit metadata present
  + concrete path and line_range
  + exact or high-confidence term/entity match

weak coverage:
  candidates exist, but evidence is indirect, low-scoring,
  missing line metadata, or only partially matches the area

missing coverage:
  no valid selected EvidenceItem remains for the coverage area after validation
  and the one bounded retry, if used, does not recover evidence
```

Trace behavior:

```text
strong coverage -> selected EvidenceItem can later support confirmed_from_evidence
weak coverage   -> gap_check_completed with status="weak"; response builder may use it as a hypothesis
missing coverage -> gap_check_completed with status="missing"; do not invent evidence
```

Retrieval trace records should stay descriptive, not explanatory. Good trace fields include `coverage_area`, `matched_terms`, `retrieval_reason`, `evidence_strength`, `rejection_reason`, and `gap_status`. Avoid response-like claims in retrieval output; the response builder is responsible for turning these signals into user-facing explanation sections.

Required behavior:

- Reject candidates outside `SourcePolicy`.
- Reject candidates with hidden or post-resolution visibility in Stage 1.
- Reject candidates from the wrong snapshot or missing commit metadata.
- Check whether each important subquery has at least one supporting candidate.
- Allow one bounded retry with narrowed terms if coverage is weak.
- Emit gap-check trace records instead of inventing evidence.

Conversion to `EvidenceItem` must include metadata:

```json
{
  "case_id": "microsoft-TypeScript-6",
  "snapshot": "pre_resolution",
  "commit": "<sha>",
  "path": "src/compiler/checker.ts",
  "line_range": "Lx-Ly",
  "visibility": "visible_initial",
  "source_policy": "coderepoqa_explain_initial",
  "retrieval_reason": "Candidate matched constructor/new checks for abstract class behavior."
}
```

Acceptance criteria:

- Invalid candidates are logged with rejection reasons.
- Valid evidence carries enough metadata for replay and leakage checks.
- Missing or weakly covered areas become `gap_check_completed` trace records, not unsupported claims.

### 8. Evidence Trace And Response Contract Handoff

Write replayable retrieval logs and define the handoff to the response contract.

Do not build a response-shaped `ContextPackage` in v1. After `RetrievalService.retrieve(plan)` returns selected `EvidenceItem` values, the harness should write trace artifacts and, only if response generation is enabled, pass `decision`, `EvidenceItem` values, and trace/gap records to the response builder.

Required behavior:

- Return selected `EvidenceItem` values from `RetrievalService.retrieve(plan)`.
- Record rejected candidates, selected evidence, and gap checks in retrieval trace JSONL.
- Record enough per-evidence metadata for a later response builder to distinguish strong evidence from weak or indirect evidence.
- Do not call `contract_for_decision(decision)` or a response builder in the first runnable slice.
- Store retrieval trace JSONL under the case run folder.

First runnable log events:

```text
retrieval_intent_created
connector_decision
bm25_candidates_selected
candidate_rejected
evidence_selected
gap_check_completed
```

Acceptance criteria:

- Logs are append-only JSONL.
- A later evaluator can inspect the intent, candidate sources, selected evidence, and rejected evidence.
- `EvidenceItem` values and trace records provide enough information for a later response builder to satisfy `summary`, `evidence`, `reasoning_path`, `confirmed_from_evidence`, `hypotheses_to_investigate`, and `knowledge_check_question`.
- No `ContextPackage` class is required for v1.

### 9. Local Harness Integration

Add a local harness that runs Stage 1 retrieval for TypeScript #6 without Open SWE.

Required flow:

```text
load CodeRepoQA case
-> require repo-pre path and commit
-> load Stage 1 RunConfig
-> RunConfigController validates configured SourceCategory values
-> RunConfigController resolves Stage 1 SourcePolicy
-> create ConversationState
-> call V1PolicyEngine(source_policy=resolved_policy).decide
-> call CodeRepoQARetrievalService.plan(state, decision)
   -> internally build RetrievalIntent
   -> return RetrievalPlan
-> call CodeRepoQARetrievalService.retrieve(plan)
   -> internally run local visible-case connector enrichment and BM25 retrieval
   -> internally validate evidence
   -> return EvidenceItem values
-> write EvidenceItem output and retrieval trace artifacts
-> write trace artifacts
```

The first runnable harness stops before response generation.

Suggested outputs:

```text
testing/codeRepoQA/runs/microsoft-TypeScript-6/run-001/retrieval-intent.json
testing/codeRepoQA/runs/microsoft-TypeScript-6/run-001/evidence-items.json
testing/codeRepoQA/runs/microsoft-TypeScript-6/run-001/retrieval-trace.jsonl
```

Acceptance criteria:

- The harness runs locally without Open SWE.
- The harness does not clone or index during the conversation step.
- The run produces selected evidence and trace artifacts for Stage 1.
- The harness never calls internal retrievers directly; it only calls `plan(...)` and `retrieve(...)`.
- The harness never uses `DEFAULT_SOURCE_POLICY` for CodeRepoQA Stage 1.
- The trace records the resolved run config, policy name, allowed categories, visibility scope, and snapshot scope.

## Verification Plan

Do not test the whole system end-to-end yet. Add focused checks around the retrieval pieces.

- Parser check: TypeScript #6 issue body produces bounded subqueries and entities.
- Config check: CodeRepoQA Stage 1 resolves to `ISSUE_TRACKER` and `SOURCE_CODE` only.
- Policy check: Stage 1 rejects PR/comment/post-fix artifacts.
- Index check: prebuilt chunks include path, line range, commit, and snapshot metadata.
- Retrieval check: BM25 returns concrete pre-resolution code chunks for issue terms.
- Evidence check: selected `EvidenceItem` values include source policy, snapshot, commit, and retrieval reason.
- Cost check: decomposition caps subqueries and final evidence count.

## Later Extension Backlog

Do not implement these in the first runnable slice. After the local BM25 retrieval test produces real traces, create a separate follow-up design document for whichever extension is next. That follow-up document should use implementation results to justify why the extension is needed and how it should be added.

### Markdown Wiki Orientation

Purpose:

- Provide architecture orientation and subsystem hints when raw BM25 source chunks are too low-level.
- Help explain where parser, checker, binder, and tests fit in the repository.

Use only if traces show that BM25 finds code snippets but the system lacks enough orientation to organize them. For CodeRepoQA Stage 1, wiki content must not become user-visible evidence unless a later explicit policy allows `SourceCategory.DOCUMENTATION` from a pre-resolution source.

Existing guardrails:

- Wiki is optional and internal.
- Wiki must obey `decision.allowed_sources`.
- If documentation is not allowed, wiki chunks are skipped or logged as non-evidence orientation only.
- Source-code evidence remains preferred for confirmed claims.

### Symbol/File Metadata Boosts

Purpose:

- Improve BM25 ranking using cheap structural metadata such as path, file basename, symbol names, and subsystem hints.
- Help exact retrieval without narrowing the search space.

Use only if plain BM25 retrieves too many irrelevant chunks or misses obvious code because issue wording does not appear directly in source text.

Existing guardrails:

- Metadata boosts are ranking internals, not public evidence sources.
- `retrieval_path` remains `bm25`; boosts are logged in candidate metadata only.
- Metadata must never filter files out in v1-style retrieval.
- Avoid large generated summaries, full AST dumps, broad neighboring-file content, or speculative labels.

### Connector Adapters Beyond Local Visible Case

Purpose:

- Add future live or external artifact sources such as GitHub, Shortcut, or Slack.

Use only after local CodeRepoQA retrieval is stable. Stage 1 should continue using only `VisibleCodeRepoQACase` and local `repo-pre` source code.

Existing guardrails:

- The first runnable connector behavior is just local visible-case enrichment from title and initial issue body.
- Future connectors must pass through `RetrievalService.plan(...)` and `retrieve(...)`.
- Future connectors must obey `SourcePolicy` and the visible/hidden case boundary.

### Response Generation

Purpose:

- Convert `OrchestratorDecision`, `ResponseContract`, selected `EvidenceItem` values, and retrieval trace records into a `ResponsePayload`.

Use only after retrieval trace quality is good enough to support response construction. Until then, the first runnable test stops at evidence and trace artifacts.

Existing guardrails:

- `contract_for_decision(decision)` defines required response sections.
- Retrieval does not write final explanatory claims.
- `EvidenceItem` values and trace records are the response builder inputs.
- Do not introduce `ContextPackage` as a second response contract.

### Full Confirmed/Hypothesis Response Construction

Purpose:

- Fill `confirmed_from_evidence` and `hypotheses_to_investigate` sections in the expanded `EXPLANATION` contract.

Use only after retrieval has enough metadata and gap records to support this distinction. The first runnable slice records deterministic evidence strength and gap statuses, but does not need to produce a full user-facing explanation.

Existing guardrails:

- Strong coverage can later support `confirmed_from_evidence`.
- Weak or missing coverage can later support `hypotheses_to_investigate` or uncertainty language.
- Gap checking remains deterministic in v1; do not use an LLM to decide whether evidence is allowed, confirmed, weak, or missing.

## Deferred Work

These are intentionally not part of the first usable local loop:

- Open SWE or LangGraph integration.
- Live GitHub, Shortcut, or Slack connector calls.
- Dense vector retrieval.
- Reciprocal-rank fusion.
- LLM reranking.
- CodeRAG BestFit reranking.
- Full dataflow retrieval.
- CodeGraphContext MCP integration.
- Parallel retriever fan-out.
- Model-based response generation.

Add these only after the local Stage 1 retrieval harness produces useful evidence and replayable traces.

## Post-v1 Implementation Note

The runnable retrieval slice now includes an optional API-backed LLM intent planner. This intentionally moves beyond the original v1 constraint that query decomposition must be deterministic only.

Guardrails kept from the original plan:

- LLM intent planning is disabled by default.
- The LLM receives only visible issue text and a compact repo sketch derived from local `repo-pre` index metadata.
- The LLM does not receive chunk text, hidden issue fields, live GitHub data, or post-resolution artifacts.
- BM25 retrieval, evidence validation, file ranking, and final evidence selection remain local and deterministic.
- Invalid or failed LLM responses fall back to the deterministic intent planner and are recorded in trace metadata.

## Assumptions

- The plan document path is `testing/codeRepoQA/RAG retrieval implementation plan.md`.
- The first implementation target is TypeScript issue #6.
- Indexing happens offline before conversation time.
- Query decomposition is bounded. It is deterministic by default, with an optional API-backed LLM planner available only through run configuration.
- A single internal `RetrievalIntent` drives the whole retrieval run inside `CodeRepoQARetrievalService`.
- The public retrieval boundary remains `RetrievalService.plan(...)` followed by `RetrievalService.retrieve(...)`.
- CodeRepoQA Stage 1 uses a resolved run configuration, not `DEFAULT_SOURCE_POLICY`.
- CodeRepoQA Stage 1 allowed categories are exactly `SourceCategory.ISSUE_TRACKER` and `SourceCategory.SOURCE_CODE`.
- The active `SourcePolicy`, visible/hidden case split, and evidence metadata validation control every context source before it reaches retrieval or response generation.
