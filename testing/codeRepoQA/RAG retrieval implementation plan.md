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

The implementation should prove that the system can load a historical issue, build a controlled retrieval intent, retrieve pre-resolution code evidence, validate source visibility, and emit a structured context package that maps to the expanded `EXPLANATION` response contract.

## Target Retrieval Flow

Use a staged flow with a few sequential gates and a simple first implementation. Do not build a fully parallel or agentic retriever yet.

```text
policy + visibility gate
-> prompt parsing / bounded query decomposition
-> connector enrichment if explicitly referenced and allowed
-> wiki orientation
-> code graph expansion
-> BM25 exact chunk retrieval
-> simple fusion + reranking
-> evidence validation / gap check
-> structured context package
```

The main design rule is:

```text
Prompt splitting must not cause the full retrieval pipeline to run repeatedly.
```

Decomposition should create one bounded `RetrievalIntent` containing entities, source hints, and at most five subqueries. Each retrieval source then handles that one bundle once, with caps and deduplication.

The intended role of each context source is:

- Connectors provide external artifact truth, such as local CodeRepoQA JSON, GitHub issues, Shortcut tickets, or Slack threads.
- The markdown wiki provides architecture orientation and subsystem hints.
- The code graph identifies likely files, symbols, and neighborhoods.
- BM25 retrieves exact source chunks from indexed files.
- Dense retrieval, parallel fan-out, and LLM reranking are later upgrades.

## Key Internal Data Shapes

Keep these outside `core` initially, under `services/retrieval` or `services/retrieval/experiments`, so the policy core stays stable.

### `RetrievalIntent`

Structured output from prompt parsing and bounded decomposition.

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

Stage 1 must expose only the initial issue body. Later comments, labels, PR links, and hidden resolution context remain evaluator-only.

### `IndexedChunk`

Offline-indexed searchable unit from source code or wiki markdown.

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

### `GraphCandidate`

File or symbol candidate found by the prebuilt graph index.

```python
@dataclass(frozen=True)
class GraphCandidate:
    candidate_id: str
    path: str
    symbol: str | None
    relationship_reason: str
    confidence: float
    metadata: Mapping[str, str]
```

V1 graph indexing should stay simple: definitions, class/function names, imports, exports, inheritance terms, and file-level relationships. Full dataflow and MCP integration are later work.

### `RetrievalCandidate`

Unified candidate from connector, wiki, graph, BM25, or later dense retrieval.

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

The `retrieval_path` should identify where the candidate came from, such as `connector`, `wiki`, `graph`, `bm25`, or later `dense`.

### `ContextPackage`

Response-ready package that maps directly to the expanded `EXPLANATION` contract.

```python
@dataclass(frozen=True)
class ContextPackage:
    conversation_id: str
    case_id: str
    confirmed_from_evidence: tuple[str, ...]
    hypotheses_to_investigate: tuple[str, ...]
    evidence_items: tuple[EvidenceItem, ...]
    missing_context: tuple[str, ...]
    retrieval_trace: tuple[Mapping[str, str], ...]
```

The response builder should be able to use this package without reconstructing retrieval decisions.

## Implementation Tasks

### 1. Offline Case And Snapshot Preparation

Implement a local case loader for `testing/codeRepoQA/6.json`.

Required behavior:

- Read CodeRepoQA issue JSON from disk.
- Build `case_id`, for example `microsoft-TypeScript-6`.
- Extract visible Stage 1 fields: repo owner/name, issue number, title, created date, initial body.
- Extract hidden fields into a separate object but never pass them into Stage 1 retrieval.
- Require a configured `repo-pre` path and commit before retrieval starts.
- Store case metadata with `snapshot="pre_resolution"` and `visibility="visible_initial"`.

Suggested files:

```text
testing/codeRepoQA/run_case.py
services/retrieval/cases.py
```

Acceptance criteria:

- Loading `6.json` produces separate visible and hidden structures.
- Stage 1 visible context does not contain `comments_details`, `cite`, `cited_by`, `fixed_by`, or labels.
- Missing `repo-pre` configuration fails with a clear message instead of cloning during conversation time.

### 2. Prompt Parsing And Bounded Query Decomposition

Implement deterministic parsing first. Do not use an LLM splitter in v1.

Required behavior:

- Extract repo references, issue number, title terms, quoted identifiers, fenced code identifiers, and likely source categories.
- Produce one `RetrievalIntent` for the whole retrieval run.
- Generate at most five subqueries.
- Collapse duplicate terms across subqueries.
- Add `metadata["decomposition_strategy"] = "deterministic_v1"`.

Cost control:

- No subquery should trigger a full independent retrieval pipeline.
- BM25 and graph expansion should receive the whole `RetrievalIntent` once.
- Per-subquery result caps are allowed inside each retriever, but final candidates must be deduplicated globally.

Acceptance criteria:

- TypeScript #6 produces no more than five subqueries.
- The intent includes entities such as `abstract`, `class`, `Base`, `Derived1`, `Derived2`, `getThing`, `super`, and `new`.
- The intent includes `SourceCategory.ISSUE_TRACKER` and `SourceCategory.SOURCE_CODE` as source hints for Stage 1.

### 3. Policy And Connector Enrichment Gate

Implement connector enrichment as an explicit policy-gated step.

Required behavior:

- Check `SourcePolicy` before any connector artifact is used.
- Check evaluation visibility before exposing connector fields.
- Implement `LocalCodeRepoQAConnector` first.
- Leave GitHub, Shortcut, and Slack as future adapters behind the same interface.
- Connector enrichment runs only when the case loader provides an artifact or the prompt contains a resolvable reference.

Stage 1 rule:

```text
Local CodeRepoQA / GitHub issue context means initial issue body only.
```

Acceptance criteria:

- Stage 1 connector artifact contains title and initial issue body only.
- Hidden issue comments and PR links are rejected or omitted before retrieval.
- Connector decisions are recorded in the retrieval trace.

### 4. Markdown Wiki Orientation

Add a lightweight markdown wiki layer for codebase architecture summaries.

Required behavior:

- Index manually authored or generated markdown files into `IndexedChunk` objects.
- Search wiki chunks using the `RetrievalIntent`.
- Return only short orientation chunks, capped to two or three.
- Use wiki results to produce subsystem hints for graph and BM25.
- Treat wiki chunks as orientation, not final proof.

Suggested content for a TypeScript wiki entry:

```text
The compiler parser recognizes syntax and modifiers.
The binder creates symbols.
The checker enforces type rules and diagnostics.
Conformance tests cover accepted and rejected language behavior.
```

Acceptance criteria:

- Wiki orientation can suggest likely subsystems without needing model calls.
- Context packages distinguish wiki orientation from source-code evidence.
- Missing wiki files do not fail retrieval; the system logs `wiki_unavailable` and continues.

### 5. Offline Code Graph Index

Build a simple graph index before conversation time.

Required behavior:

- Index files, top-level symbols, class names, function names, imports, exports, and inheritance-like terms.
- Store graph data in a local serialized format under the case index directory.
- Use wiki hints and intent entities to identify candidate files and symbols.
- Emit `GraphCandidate` values with relationship reasons.

Do not implement full dataflow in v1. Do not require CodeGraphContext or MCP for the first version.

Acceptance criteria:

- Graph expansion returns candidate files/symbols for relevant issue terms when available.
- Each graph candidate includes path, optional symbol, relationship reason, and confidence.
- If graph index is missing, retrieval can fall back to repo-wide BM25 with a logged warning.

### 6. BM25 Sparse Retrieval

Implement the first real source-code retriever with BM25 over pre-indexed chunks.

Required behavior:

- Build BM25 over `IndexedChunk` text from `repo-pre`.
- Search graph-identified files first.
- If candidate-file search is weak, run a repo-wide fallback.
- Use the full `RetrievalIntent` once, with internal per-subquery caps.
- Deduplicate by `path`, `line_start`, and `line_end`.
- Prefer exact identifiers, diagnostics, syntax terms, and file names.

Cost control:

- Cap BM25 candidates before fusion, for example 40 total.
- Cap per-subquery results, for example 8.
- Avoid scanning files at conversation time when a chunk index already exists.

Acceptance criteria:

- Retrieval returns concrete chunks with path, line range, commit, and snapshot metadata.
- TypeScript #6 searches for terms related to abstract classes without using hidden comments or PRs.
- BM25 can run without dense embeddings or model calls.

### 7. Fusion, Reranking, And Cost Control

Start with deterministic scoring. Do not add LLM reranking yet.

Required behavior:

- Normalize connector, wiki, graph, and BM25 outputs into `RetrievalCandidate`.
- Score candidates using a weighted formula.
- Keep the final evidence budget small, for example 8 to 12 chunks.
- Deduplicate near-identical snippets and overlapping line ranges.
- Prefer source-code evidence over wiki orientation for confirmed claims.

Suggested scoring signals:

```text
+ exact entity match
+ source allowed by active SourcePolicy
+ graph candidate file match
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

### 8. Evidence Validation And Gap Check

Validate evidence before building context.

Required behavior:

- Reject candidates outside `SourcePolicy`.
- Reject candidates with hidden or post-resolution visibility in Stage 1.
- Reject candidates from the wrong snapshot or missing commit metadata.
- Check whether each important subquery has at least one supporting candidate.
- Allow one bounded retry with narrowed terms if coverage is weak.
- Emit missing-context notes instead of inventing evidence.

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
- Missing areas become `missing_context`, not unsupported claims.

### 9. Context Package And Logging

Build a structured context package and write replayable logs.

Required behavior:

- Produce a `ContextPackage` after validation.
- Separate `confirmed_from_evidence` from `hypotheses_to_investigate`.
- Include selected `EvidenceItem` values.
- Include missing-context notes.
- Store retrieval trace JSONL under the case run folder.

Recommended log events:

```text
retrieval_intent_created
connector_decision
wiki_orientation_selected
graph_candidates_selected
bm25_candidates_selected
candidate_rejected
evidence_selected
gap_check_completed
context_package_created
```

Acceptance criteria:

- Logs are append-only JSONL.
- A later evaluator can inspect the intent, candidate sources, selected evidence, and rejected evidence.
- The context package maps cleanly to `summary`, `evidence`, `reasoning_path`, `confirmed_from_evidence`, `hypotheses_to_investigate`, and `knowledge_check_question`.

### 10. Local Harness Integration

Add a local harness that runs Stage 1 retrieval for TypeScript #6 without Open SWE.

Required flow:

```text
load CodeRepoQA case
-> require repo-pre path and commit
-> create Stage 1 SourcePolicy
-> create ConversationState
-> call V1PolicyEngine.decide
-> build RetrievalIntent
-> run connector/wiki/graph/BM25 retrieval
-> validate evidence
-> build ContextPackage
-> write trace artifacts
```

The harness should stop before full model-based response generation unless a simple response builder already exists.

Suggested outputs:

```text
testing/codeRepoQA/runs/microsoft-TypeScript-6/run-001/retrieval-intent.json
testing/codeRepoQA/runs/microsoft-TypeScript-6/run-001/context-package.json
testing/codeRepoQA/runs/microsoft-TypeScript-6/run-001/retrieval-trace.jsonl
```

Acceptance criteria:

- The harness runs locally without Open SWE.
- The harness does not clone or index during the conversation step.
- The run produces selected evidence and trace artifacts for Stage 1.

## Verification Plan

Do not test the whole system end-to-end yet. Add focused checks around the retrieval pieces.

- Parser check: TypeScript #6 issue body produces bounded subqueries and entities.
- Policy check: Stage 1 rejects PR/comment/post-fix artifacts.
- Index check: prebuilt chunks include path, line range, commit, and snapshot metadata.
- Retrieval check: BM25 returns concrete pre-resolution code chunks for issue terms.
- Evidence check: selected `EvidenceItem` values include source policy, snapshot, commit, and retrieval reason.
- Cost check: decomposition caps subqueries and final evidence count.

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

## Assumptions

- The plan document path is `testing/codeRepoQA/RAG retrieval implementation plan.md`.
- The first implementation target is TypeScript issue #6.
- Indexing happens offline before conversation time.
- Query decomposition is deterministic and bounded.
- A single `RetrievalIntent` drives the whole retrieval run.
- The active `SourcePolicy` and evaluation visibility rules control every context source before it reaches retrieval or response generation.
