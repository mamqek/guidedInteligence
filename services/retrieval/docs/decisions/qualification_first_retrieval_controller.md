# Qualification-First Native Retrieval Controller

## Status and scope

Status: Step 1 implemented and validated on 2026-08-14. Steps 2 and 3 remain planned.

Design baseline: branch `one_more_time`, commit `10fc171daf1a8e9d0379600ce9914d6045d826d6`, reviewed on 2026-08-14.

This document specifies the next workspace native-retrieval redesign. It is intentionally implementation-oriented: every proposed boundary is mapped to current code, unsupported assumptions are called out, and the migration is divided into separately measurable steps.

The redesign is limited to repository evidence retrieval and the evidence supplied to the final evidence-selection LLM. It does not redesign intent classification, response composition, teaching questions, or prose explanation generation. Real comparisons must run the normal pipeline with final evidence selection enabled and `--skip-response-generation`, so retrieval and the evidence-selection payload are measured without paying for the later explanation call.

The central change is:

```text
Current
  broad retrieval
  -> immediate GroundedCandidate creation
  -> broad bidirectional graph expansion and recovery passes
  -> mechanism-flow construction over the enlarged inventory
  -> final LLM tries to find a small truthful subset

Replacement
  broad but cheap discovery
  -> role-neutral DiscoveryObservations
  -> bounded progressive source disclosure
  -> explicit qualification
  -> several independent root hypotheses
  -> coverage-driven controller loop
  -> narrow, capability-checked actions
  -> small grounded evidence inventory
  -> final evidence selection
```

## Step 1 implementation outcome

Step 1 replaced the production retrieval entry point cleanly; there is no runtime feature flag, legacy fallback, or parallel old scheduler. [`retrieval.py`](../../workspace/pipeline/execution_flow/retrieval.py) calls [`qualification_first_retrieval.py`](../../workspace/pipeline/execution_flow/qualification_first_retrieval.py). The older [`obligation_retrieval.py`](../../workspace/pipeline/execution_flow/obligation_retrieval.py) remains only as a temporary host for stable data models and final consolidation helpers that Step 2 will separate.

The new stage boundaries are implemented in separate files:

- [`discovery_observations.py`](../../workspace/pipeline/execution_flow/discovery_observations.py): role-neutral observation construction, entity/range aggregation, deduplication, and the initial 24-item guardrail plus deferred pool.
- [`source_disclosure.py`](../../workspace/pipeline/execution_flow/source_disclosure.py): adaptive full/preview/fold/skeleton disclosure with durable source handles.
- [`evidence_qualification.py`](../../workspace/pipeline/execution_flow/evidence_qualification.py): one atomic, schema-constrained classification per observation ID. The object-keyed schema prevents duplicate or missing IDs; the atomic enum prevents invalid disposition/support pairs.
- [`evidence_islands.py`](../../workspace/pipeline/execution_flow/evidence_islands.py): closed-set graph grouping and the bounded active-root beam.
- [`coverage_evaluation.py`](../../workspace/pipeline/execution_flow/coverage_evaluation.py): direct-evidence-only obligation coverage assessment.
- [`retrieval_actions.py`](../../workspace/pipeline/execution_flow/retrieval_actions.py): typed, executable actions for deferred inspection, path-local search, exact new-island search, and directional capability-checked traversal.
- [`retrieval_controller.py`](../../workspace/pipeline/execution_flow/retrieval_controller.py): the inspect/qualify/evaluate/act loop, cross-round effect deduplication, and stop policy.

Implementation details established by failed intermediate runs:

1. A strong repeated hit rejected as evidence may still receive one bounded path-local refinement. Rejection blocks evidence admission and graph expansion; it does not erase a credible navigation hypothesis.
2. Path-local refinement uses the original user request rather than an invented global rewrite. Exact/private identifiers learned from qualified source are separate sparse/exact anchors.
3. Two actions in one round cannot refine the same path. After the first round, one slot prefers a specific exact-symbol follow-up or a capability-checked directional expansion. Identical path searches, exact-anchor sets, and relationship effects deduplicate across obligations and rounds.
4. The normal controller budget remains three rounds. A fourth round is permitted only when round 3 executes a private-identifier exact search (for example `_maybe_match_name`) and that search produces evidence or navigation gain. This was required to qualify the exact owner and then traverse its callers in pandas; a global fourth round increased TypeScript noise and was rejected.
5. Navigation promotions are included in the bounded final-reranker pool with `qualified_navigation_evidence` provenance but are excluded from coverage proof. The final payload includes `retrieval_origin` and `discovery_island_id`.
6. The final selector cannot erase all qualified context from the strongest six candidate islands. One candidate per protected island is retained after reranking, still under the existing 14-item evidence cap. This is an explicit diversity invariant, not a legacy recovery search.
7. Qdrant dense and sparse queries are now separate inputs. Cache persistence flushes in batches of 64 rather than rewriting the multi-gigabyte cache for each inserted embedding; a final flush is still mandatory.
8. CodeGraph now exposes closed-set relationships, file outlines, directional edge capabilities, and depth-one limited relationship expansion. The controller requests only represented edge kinds and returned nodes always re-enter observation qualification.

The final accepted real runs all used the standard workspace pipeline with final evidence selection enabled and `--skip-response-generation`:

| Case | Run | Status | Raw | Qualified observations | Final-reranker candidates | Selected | Tools | Rounds | Retrieval LLM tokens | Oracle overlap |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| TypeScript 35468 | `run-20260814T060345Z` | partial/false | 73 | 39 | 19 | 13 | 30 | 3 | 70,118 | 3 (3 implementation) |
| TypeScript 35468 | `run-20260814T060815Z` | partial/false | 74 | 36 | 21 | 10 | 25 | 3 | 62,306 | 2 (2 implementation) |
| pandas 10068 | `run-20260814T061200Z` | partial/false | 97 | 40 | 15 | 8 | 50 | 4 | 92,898 | 2 (1 implementation) |
| pandas 10068 | `run-20260814T061451Z` | partial/false | 101 | 44 | 13 | 8 | 58 | 4 | 91,456 | 2 (1 implementation) |
| Vue 10803 | `run-20260814T061744Z` | partial/false | 73 | 27 | 3 | 3 | 15 | 1 | 32,771 | 2 (1 implementation) |
| Vue 10803 | `run-20260814T061911Z` | partial/false | 72 | 34 | 9 | 5 | 25 | 3 | 56,898 | 2 (1 implementation) |

“Retrieval LLM tokens” above is qualification plus coverage evaluation plus final evidence selection. Response-generation tokens are absent. TypeScript retained both the builder/state and watch/test islands in both accepted runs. pandas retained `pandas/core/series.py`, `pandas/core/ops.py`, `pandas/core/common.py`, and the regression test in both runs. Vue retained `src/platforms/web/server/modules/dom-props.js` and its SSR test in both runs.

The comparable legacy TypeScript runs `run-20260813T194329Z` and `run-20260813T194645Z` used 659/652 candidates, 97/99 tools, and 235,871/218,423 final-selection tokens for two Oracle overlaps. Step 1 uses 19/21 candidates, 30/25 tools, and 15,302/12,517 final-selection tokens while retaining three/two Oracle overlaps. Total Step 1 retrieval LLM usage is higher than final-selection usage alone because qualification and coverage are now separately measured; no comparison should mix those quantities.

All accepted runs remain `partial/false`. That is deliberate rather than a regression hidden by fallback: the bounded evidence did not establish every required causal transition, so the pipeline did not claim sufficiency.

This is an orchestration replacement, not a requirement to replace Qdrant, BM25, CodeGraph, AST localization, exact-anchor grounding, provenance recording, or final evidence selection. Existing helpers should be reused where their behavior fits the new boundary. Faulty scheduling and admission behavior must be removed rather than preserved as a fallback.

## Decision summary

The implementation must preserve these invariants:

1. A retrieval hit is a navigation observation, not evidence.
2. Rank, exactness, recurrence, and graph activity decide inspection order only. None independently admits evidence. Artifact role is recorded for audit but is not an initial ranking or admission signal.
3. Actual bounded source content must be inspected before a hit can become an active root or evidence candidate.
4. A request may require several disconnected evidence islands. Selecting one credible root must not suppress independent roots.
5. Artifact role is recorded but is not an early eligibility filter, quota, or global penalty. Test and helper files can be required evidence.
6. Obligations are coverage questions and action-scheduling inputs after source qualification. They do not own separate ever-growing candidate buckets.
7. Graph information may rerank the closed observation set without adding nodes. Open-set graph retrieval is allowed only through an explicit controller action from a qualified root.
8. Every result introduced by graph expansion or a new-island search re-enters as a `DiscoveryObservation` and passes through the same disclosure and qualification boundary.
9. The controller chooses only from actions that code has already proved executable with the available handles and tool capabilities. An LLM may select an action ID; it may not invent tool names, relationships, paths, symbols, or directions.
10. No deterministic or legacy fallback substitutes for a failed LLM-backed qualification, coverage, or action-selection stage. Failure is explicit.
11. Every state transition is traceable: inputs, output IDs, disposition changes, selected action, tool arguments, result counts, budgets, and stop reason.
12. The first behavioral comparison leaves current initial query generation and the index unchanged. Admission order is the sole main variable.

## Why the current orchestration must change

The main implementation is [`obligation_retrieval.py`](../../workspace/pipeline/execution_flow/obligation_retrieval.py), currently 5,812 lines. `run_obligation_retrieval()` already performs useful work that should survive:

- `_ground_request_anchors()` confirms paths, exact symbols, literals, identifiers, and error anchors.
- `_obligation_query()` and `_obligation_stage_query_text()` construct the current per-obligation Qdrant queries.
- `qdrant_hybrid_search` returns dense, sparse, and hybrid results with complete chunk text and provenance.
- `structural_resolve_ranges` maps semantic ranges to enclosing CodeGraph nodes.
- `_candidate_from_node()` and `_source_text_for_range()` localize exact source.
- `CandidateFacts`, candidate IDs, promotion provenance, and trace records provide useful audit data.
- `_consolidate_obligation_evidence()` performs the final request-level evidence decision.

The failure is the order beginning around `run_obligation_retrieval()` lines 371-713:

1. Exact and semantic results become `GroundedCandidate`s immediately. Semantic results are allowed without obligation overlap.
2. `_focused_seed_ids()` selects up to four candidates per required obligation.
3. `structural_expand_nodes` expands every selected seed in both graph directions, with depth one and up to 80 nodes.
4. The result can produce up to 48 frontier files, qualified-reference discovery, file-neighbor discovery, and another Qdrant search.
5. `_expand_grounded_candidate_graph()` then performs as many as three more expansion rounds.
6. Focused semantic bridge, semantic-root neighbors, neighbor grounding, endpoint recovery, exact-callee recovery, and factory-handoff recovery run sequentially.
7. Mechanism flow construction may consider up to 128 seeds and 1,024 flow candidates.
8. `MAX_EXPLANATION_INPUT_CHARS` is currently `None`.

This means the graph and recovery machinery amplify the quality of an unqualified initial hit. A terminology-adjacent seed can create a structurally correct but irrelevant neighborhood.

The measured history rules out several simpler fixes:

- The first connected-obligation Vue run produced 427 preselection candidates: [`graph-connected-obligation-retrieval.md`](../graph-connected-obligation-retrieval.md).
- Recent TypeScript consolidation requests reached 470,410 and 586,757 serialized characters while still failing to retain all required files: [`retrieval-changelog.md`](../retrieval-changelog.md).
- Late file triage saw 176-226 candidates, consumed roughly 90k additional tokens, and could not recover files already lost upstream: [`candidate-file-triage.md`](../candidate-file-triage.md).
- Lexical-first and path-only owner routing reduced cost but regressed quality: [`reranking_redesign_summary.md`](reranking_redesign_summary.md).
- A deterministic plus generated second query strand added calls and did not recover the missing owners: [`stable-obligation-query-strand.md`](../stable-obligation-query-strand.md).
- No single offline feature safely separated Oracle from non-Oracle files. Relevant owners could have weak hybrid rank, high graph fanout, or no direct semantic hit: [`offline-shortlist-signal-audit.md`](../offline-shortlist-signal-audit.md).
- An implementation-only 24-file pool was invalid because TypeScript's `watchMode.ts` and `tscWatch/helpers.ts` are test-role Oracle files: [`protected-owner-file-pool.md`](../protected-owner-file-pool.md).

The redesign therefore moves source qualification before open-set graph expansion. It does not add another late pruning layer.

## Verified current capabilities and hard limits

The controller must not schedule operations merely because their names sound available. The following table is the implementation contract as of the baseline commit.

| Capability | What exists now | What must not be inferred |
|---|---|---|
| Exact anchors | `_ground_request_anchors()` resolves repository paths, exact CodeGraph symbols, exact index literals/identifiers, and dominant error-message matches. | Confirmation proves presence, not behavioral relevance or ownership. |
| Hybrid retrieval | [`QdrantHybridSearchTool`](../../workspace/tools/qdrant.py) returns hybrid results plus dense/sparse breakdown, paths, ranges, text, scores, matched terms, and file role. | A high dense, sparse, or fused rank is not evidence admission. |
| BM25 | [`bm25.py`](../../workspace/bm25.py) tokenizes one flat document string containing path, basename, and chunk text. Symbol names are metadata but not separately weighted fields. | This is not BM25F and cannot independently weight filename, definition, and body fields. |
| Exact symbol lookup | `structural_find_exact_symbol` returns CodeGraph nodes/files for an exact name. | A same-name result is not necessarily the requested entity; overloaded/common names remain ambiguous. |
| Range localization | `structural_resolve_ranges` returns non-file/non-import nodes overlapping a source range. | Overlap does not prove that the enclosing node owns the matched behavior. |
| Broad graph expansion | `structural_expand_nodes` uses both incoming and outgoing edges and accepts depth and total limit. | It has no direction filter and no relationship-kind filter. It cannot execute a request such as “only callers through calls edges.” |
| Caller/callee lookup | `structural_callers` and `structural_callees` accept a file and line, find overlapping nodes, and return unique related files. | They do not currently return qualified related entities or the exact connecting edges. The Python wrapper also hard-codes a limit of 50. |
| File neighbors | `structural_file_neighbors` aggregates incoming/outgoing graph edges and dependencies with fixed weights. | Its score is broad structural proximity, not causal direction, relevance, or proof of a missing obligation. |
| Qualified references | `structural_qualified_references` scans `Owner.member(...)`-like expressions and resolves matching CodeGraph members. | It is a TypeScript/JavaScript-oriented regex heuristic, requires an uppercase qualifier, and does not cover dynamic dispatch, aliases, plain function calls, or every language. |
| File relationship | `structural_relationship` checks direct graph edges and file dependencies between two known files. | Absence means only “not represented by this graph query,” not “no runtime or conceptual relationship exists.” |
| Source opening | [`OpenFileTool`](../../workspace/tools/local.py) opens indexed chunks for a known path and line window, up to 120 requested lines and four returned chunks. | It is not an arbitrary full-file reader or a symbol-outline generator. |
| AST localization | [`source_ast.mjs`](../../codegraph/source_ast.mjs) uses the TypeScript compiler API to localize a file-owned call edge to a named executable. | It supports TS/JS-family files only and one specialized call-localization problem. It is not a repository-wide, multi-language skeleton service. |
| Chunk structure | `_structure_aware_spans()` and `_extract_chunk_symbols()` in `bm25.py` use structural heuristics and declaration regexes. | They are not a complete AST and cannot prove imports, ownership, signatures, or call resolution across all indexed languages. |

These limits change the expansion design. Precise directional expansion is not implementable with the current Python tool contract alone. The first implementation must extend the CodeGraph bridge before enabling such controller actions.

## Target components and file ownership

New stages and new state objects must be implemented in separate modules from their first introduction. Do not add them to `obligation_retrieval.py` and plan to extract them later.

The initial target layout is:

```text
services/retrieval/workspace/pipeline/execution_flow/
  obligation_retrieval.py          # temporary facade and old-helper host during Step 1
  discovery_observations.py        # observation model, normalization, aggregation, guardrail
  source_disclosure.py             # fold/preview/full disclosure and stable source handles
  evidence_qualification.py        # qualification schema, prompt, validation, disposition changes
  evidence_islands.py              # closed-set relationships, components, diverse root beam
  coverage_evaluation.py           # obligation coverage over qualified grounded content
  retrieval_actions.py             # typed allowed actions and tool execution adapters
  retrieval_controller.py          # bounded state machine only

services/retrieval/workspace/prompts/
  evidence_qualification.md
  retrieval_coverage.md
```

Step 2 later finishes decomposing the remaining existing functionality:

```text
  request_grounding.py             # existing anchor confirmation and exact prompt seeds
  candidate_grounding.py           # source range -> GroundedCandidate and deterministic facts
  relationship_evidence.py         # normalized exact/source-derived candidate relationships
  mechanism_flows.py               # bounded flow construction over promoted candidates only
  final_evidence_selection.py      # consolidation payload, schema, response validation
```

The modules are separated by stage ownership, not by arbitrary line count. In particular:

- `DiscoveryObservation` and its deduplication, entity/file aggregation, recurrence calculation, and initial role-neutral guardrail belong together in `discovery_observations.py`. This processing occurs once at the discovery boundary and is not a generic utility.
- Progressive source rendering belongs in `source_disclosure.py`; it must not be mixed with semantic qualification.
- Qualification rules and the LLM contract belong in `evidence_qualification.py`; graph scores and controller scheduling must not be placed there.
- The loop belongs in `retrieval_controller.py`; it calls components and owns budgets/state transitions but contains no Qdrant, CodeGraph, parsing, ranking, or LLM prompt implementation.
- Existing CodeGraph transport wrappers remain cohesively in `workspace/tools/codegraph.py`, while the JavaScript bridge operations remain in `codegraph/workspace_graph.mjs`. A tool adapter is not a retrieval stage and does not need one file per tool.

Tests must mirror these boundaries. The 2,285-line [`tests/test_obligation_retrieval.py`](../../../../tests/test_obligation_retrieval.py) should be split during Step 2 into focused test modules for observations, disclosure, qualification, islands, coverage, actions, controller behavior, grounding, mechanism flows, and final selection.

## Stage 1: Role-neutral discovery observations

### Data model

`discovery_observations.py` owns immutable records similar to:

```python
@dataclass(frozen=True)
class DiscoveryProvenance:
    retriever: str                 # exact_anchor, qdrant_hybrid, qdrant_dense, qdrant_sparse, graph_action
    query_id: str                  # stable request-local ID, not raw generated prose as identity
    obligation_ids: tuple[str, ...]
    ranks: tuple[int, ...]
    scores: tuple[float, ...]
    matched_terms: tuple[str, ...]

@dataclass(frozen=True)
class SourceHandle:
    path: str
    line_start: int
    line_end: int
    node_id: str = ""
    symbol: str = ""
    full_line_start: int = 0
    full_line_end: int = 0
    language: str = ""
    adapter: str = ""                 # codegraph_node, indexed_chunk, exact_path, or later adapter ID

@dataclass(frozen=True)
class DiscoveryObservation:
    id: str
    handle: SourceHandle
    observed_text: str
    provenance: tuple[DiscoveryProvenance, ...]
    exact_anchor_matches: tuple[str, ...]
    artifact_role: str
    recurrence: int
    disclosure_status: str         # undisclosed, fold, preview, full, unavailable
    parent_observation_ids: tuple[str, ...]
```

The stable ID must derive from normalized path plus the narrowest available entity identity or range. It must not derive from list position, score, or obligation order.

`SourceHandle` is required on folds, skeletons, previews, and full source alike. A later stage must always be able to request the complete entity or a narrower range without parsing display text. Skeleton entries must therefore retain path, exact node ID when available, displayed range, full owner range, symbol, and language/adapter metadata.

### Creation and aggregation

The current initial Qdrant loop, exact prompt seeds, anchor nodes, and `structural_resolve_ranges` call remain in place for the first comparison. Their output changes destination:

- Replace initial calls to `_candidate_from_node()` and `_append_semantic_candidates()` with observation factories.
- Preserve raw hybrid results and dense/sparse breakdown. The current Qdrant payload already exposes these channels.
- Resolve ranges in the existing grouped call, then attach the narrowest overlapping CodeGraph entity as a handle where one exists.
- When CodeGraph returns no enclosing entity, retain the semantic chunk range as a valid source handle. Do not invent an entity.
- Aggregate repeated chunks by exact entity identity first; otherwise aggregate overlapping ranges in the same file only when the overlap is substantial and the text represents the same indexed region.
- Merge provenance instead of keeping one copy per obligation.
- Compute recurrence from independent retrieval views, not from duplicated dense/sparse/hybrid copies of the same query.
- Retain file/entity diversity when applying the observation guardrail.

The first guardrail is a configurable maximum of 24 aggregated file/entity observations, with a target observed range of roughly 12-24. This is a survival budget, not an evidence budget. It is based on the measured top-12-per-obligation union producing 12-22 source-owner files across the offline runs. It must be role-neutral: `artifact_role` is logged but cannot exclude, penalize, reserve, or quota observations in this step.

If more than 24 observations survive, the deterministic reducer applies this order:

1. Preserve every exact, repository-confirmed prompt anchor with a usable source handle, subject to a separate small safety cap for extremely common anchors.
2. Give each independent query/obligation view an opportunity to contribute its strongest not-yet-represented entity.
3. Prefer a new file/entity over another chunk from an already represented entity.
4. Use recurrence and best retrieval position only as ordering signals.
5. Do not use graph fanout, artifact role, inferred responsibility, or a global lexical threshold as eligibility gates.

Every excluded raw hit remains present in the trace with a deterministic reason such as `merged_same_entity`, `merged_overlapping_range`, or `outside_observation_guardrail`. It is not retained in a hidden runtime fallback pool.

### Why query generation is unchanged here

The current initial query behavior is deliberately frozen during the first behavioral comparison. [`stable-obligation-query-strand.md`](../stable-obligation-query-strand.md) already shows that introducing a second query strand did not solve owner recovery. Changing query construction together with admission order would make any improvement impossible to attribute.

The raw intent object is not serialized into one invented embedding query. Its fields continue to feed the current per-obligation query logic. A channel-specific structured-query redesign is retained under Future Experiments.

## Stage 2: Progressive source disclosure

`source_disclosure.py` converts an observation into a bounded `DisclosureCard`. Disclosure is deterministic; semantic relevance is not decided here.

```python
@dataclass(frozen=True)
class OutlineEntry:
    node_id: str
    kind: str
    name: str
    qualified_name: str
    line_start: int
    line_end: int

@dataclass(frozen=True)
class DisclosureCard:
    observation_id: str
    handle: SourceHandle
    mode: str                       # fold, preview, full
    source_text: str
    outline_entries: tuple[OutlineEntry, ...]
    provenance_summary: Mapping[str, object]
    truncation_reason: str
```

Initial disclosure policy:

1. Exact, unambiguous function/method with a known complete range of at most 120 lines: read the full range.
2. Exact function/method over 120 lines: include its signature/opening, the matched local window, and retain the full range in `SourceHandle` for later paging.
3. Small class/file/entity of at most 100 lines: read the complete range.
4. Large class/file: include a structural outline plus the matching enclosing entity and a short local excerpt.
5. More than three same-name exact matches: fold first; do not fetch every full body.
6. Raw semantic range with no entity: include the complete retrieved chunk and its exact path/range. It may be qualified, but no ownership claim is attached.
7. Unreadable or unindexed source: emit `disclosure_status=unavailable`; do not silently replace it with a different chunk.

This is adapted from LocAgent's actual behavior: exact entity IDs receive complete content; up to three name matches receive previews; function previews contain full function code; small classes/files are full while large ones become skeletons; ambiguous larger result sets are folded. See [LocAgent entity search at pinned commit](https://github.com/gersteinlab/LocAgent/blob/4935b557326c154bad8e8dcf3747cc8d32d1f387/plugins/location_tools/repo_ops/repo_ops.py#L273) and [LocAgent result formatting](https://github.com/gersteinlab/LocAgent/blob/4935b557326c154bad8e8dcf3747cc8d32d1f387/plugins/location_tools/utils/result_format.py#L93).

### Required CodeGraph outline extension

The current workspace adapter has no tool that lists the structural outline of one file. Implement:

```text
tool: structural_file_outline
arguments:
  path: repository-relative path
  max_entries: bounded integer
result:
  nodes: [{id, kind, name, qualified_name, path, line_start, line_end, language}]
```

The JavaScript implementation can use the already available `codegraph.getNodesInFile(path)`, exclude raw `file` and `import` nodes from executable entries, sort by source range, and return metadata only. Python can read one or two declaration lines for displayed outline entries using the same repository-safe source reading logic currently embedded in `_source_text_for_range()`.

This is not a claim that CodeGraph provides a complete AST for every language. If it yields no usable nodes, the disclosure card uses the original semantic chunk and exact range. It must say `outline_unavailable`; it must not manufacture a regex skeleton and label it structural.

The existing TypeScript compiler adapter in `source_ast.mjs` remains specialized call localization. Generalizing it to all skeletons is not part of the first slice.

## Stage 3: Explicit evidence qualification

`evidence_qualification.py` is the definitive relevance/admission boundary. It receives the user request, bounded disclosure cards, and confirmed exact anchors. Artifact role is visible context only.

The strict output for every reviewed observation is:

```python
@dataclass(frozen=True)
class QualificationDecision:
    observation_id: str
    disposition: str       # promote, defer, reject
    support_level: str     # direct_evidence, navigation_only, insufficient
    reason: str
    visible_support: tuple[str, ...]
    missing_information: tuple[str, ...]
```

Semantics:

- `promote + direct_evidence`: visible source directly establishes a relevant fact. It may become a `GroundedCandidate` and an active root.
- `promote + navigation_only`: visible source is specifically related enough to justify one bounded follow-up, but it is not supplied as final evidence yet.
- `defer`: relevance remains plausible but is not strong enough to spend an active-root/action slot now.
- `reject`: visible source shows a clear mismatch, redundant generated copy, or unrelated use of the terminology.

Only a strict, source-referenced decision may promote. Scores cannot be mentioned as proof. Exact matches increase inspection priority but do not force promotion. Graph fanout is excluded from the qualification prompt. Test role cannot be used as a positive or negative decision by itself.

The valid disposition/support combinations are deliberately closed:

| Disposition | Support level | Meaning |
|---|---|---|
| `promote` | `direct_evidence` | Visible source establishes a relevant fact and may enter grounded evidence. |
| `promote` | `navigation_only` | Visible source justifies a bounded follow-up but cannot enter final evidence yet. |
| `defer` | `navigation_only` | A specific follow-up is plausible, but it is lower priority than active roots. |
| `defer` | `insufficient` | The card is plausibly related but needs fuller disclosure or another exact handle. |
| `reject` | `insufficient` | Visible source is irrelevant, redundant, or too ambiguous to retain. |

Every other combination is a schema/validation failure. In particular, `defer + direct_evidence` and `reject + direct_evidence` are contradictory and must not be normalized silently.

The qualification call must be bounded before serialization. The initial proposal is no more than 24 cards and 40,000 serialized characters, with each card carrying one display representation rather than repeated per-obligation copies. These are experimental guardrails and must be recorded in the trace.

If the qualification LLM fails, times out, omits an observation, duplicates a decision, returns an unknown ID, or returns an invalid disposition/support combination, the retrieval stage fails explicitly. There is no “keep everything,” deterministic semantic surrogate, or call to the old broad expansion path.

This is materially different from the removed candidate-file triage experiment. That experiment reviewed 176-226 already-expanded candidates in 296k-310k-character cards after relevant roots had already been lost. This qualification happens before graph expansion over the aggregated initial observation pool.

## Stage 4: Evidence islands and active root beam

`evidence_islands.py` creates provisional connected components only from relationships proved among already qualified observations. It does not perform open-set expansion.

### Required closed-set relationship operation

Add a CodeGraph bridge operation and tool:

```text
tool: structural_relationships_within_nodes
arguments:
  node_ids: qualified observation node IDs, capped at 80
  edge_kinds: optional allowlist
result:
  nodes: only requested nodes that exist
  edges: graph edges whose source and target are both in node_ids
```

The implementation is straightforward with current `getIncomingEdges()` and `getOutgoingEdges()` APIs. It must never return a node outside the requested set. This gives Aider-style closed-set graph ranking and component formation without turning neighbors into candidates. Aider similarly uses definition/reference relationships and personalized PageRank to choose which existing repo-map entries fit a token budget rather than treating every neighbor as evidence: [Aider repository-map documentation](https://aider.chat/docs/repomap.html) and [implementation](https://github.com/Aider-AI/aider/blob/main/aider/repomap.py#L339).

Component rules:

- Exact closed-set CodeGraph edges connect two observations.
- Same exact node/entity merges observations before this stage.
- Directory similarity, shared vocabulary, artifact role, and Qdrant score do not prove a component. They may be logged as weak descriptors only.
- An observation without a proved edge is a singleton island.
- Absence of a graph edge never rejects or merges an observation.

Root selection keeps two to four active hypotheses, initially four when available:

1. Consider only `promote` decisions.
2. Select the strongest source-qualified root from distinct components before selecting a second root from any component.
3. Within a component, use direct-evidence status, qualification reason, independent retrieval recurrence, and exact-anchor confirmation as ordering information.
4. Do not let an implementation/test role distinction determine slots.
5. Non-selected promoted and deferred observations remain explicitly inactive/deferred, not discarded and not secretly expanded.

The TypeScript 35468 target state is at least two independently surviving islands: the builder/builder-state side and the watch/helper side. It is acceptable for one root to lead to multiple final files. A root is a credible starting point, not “the one owner file.”

Agentless is inspiration only for staged disclosure. Its first localization prompt sends the issue plus repository structure to an LLM and asks for up to five files, after which compressed file skeletons and line localization narrow the result: [Agentless localization prompt](https://github.com/OpenAutoCoder/Agentless/blob/5ce5888b9f149beaace393957a55ea8ee46c9f71/agentless/fl/FL.py#L25). Its literal top-file and test-filtering assumptions are not copied because this system must support multi-island explanations and test/helper evidence.

## Stage 5: Coverage evaluation

`coverage_evaluation.py` evaluates the current grounded evidence against obligations after qualification. It does not retrieve anything.

```python
@dataclass(frozen=True)
class ObligationCoverage:
    obligation_id: str
    status: str                # covered, partial, missing, contradictory, external
    supporting_candidate_ids: tuple[str, ...]
    missing_claim: str
    suggested_need: str        # trigger, downstream, implementation, state, registration, contract, new_island, unknown
```

Coverage rules:

- Every `covered` or `partial` result cites visible promoted `GroundedCandidate` IDs.
- A `navigation_only` root cannot by itself mark an obligation covered.
- Obligations remain many-to-many with evidence; there are no per-obligation candidate buckets or evidence quotas.
- `suggested_need` describes missing information, not a tool call.
- Required/optional/`one_of` semantics must come from the existing intent contract where available. Do not invent a universal requirement that every explanation needs trigger, owner, state, test, and effect.
- Artifact role is not substituted for evidence semantics. A test can establish a contract or trigger; an implementation file can also establish a contract.
- Coverage failure is honest. It does not automatically launch all recovery families.

The implementation may adapt parts of the existing consolidation validation that maps candidate IDs to obligations, but it needs a smaller dedicated prompt and schema. `_consolidate_obligation_evidence()` should remain the final selector until Step 2 extraction; it must not be called once per controller round.

The repository's earlier evidence-plan work warns that objective vocabulary can anchor retrieval even when called advisory: [`evidence_plan_deferred_design.md`](../../../../docs/evidence_plan_deferred_design.md). Therefore obligations influence action scheduling only after roots are source-qualified. They do not suppress initial observations.

## Stage 6: Capability-checked retrieval actions

The previous high-level proposal—“missing trigger means traverse callers”—was too broad for the current tools. A missing trigger does not prove that a caller edge exists, that CodeGraph resolved the root precisely, or that a caller is the correct next evidence. The controller must use an allowed-action catalogue constructed from actual handles and tool capabilities.

`retrieval_actions.py` owns typed actions:

```python
@dataclass(frozen=True)
class InspectDeferredObservation:
    id: str
    observation_id: str
    requested_range: tuple[int, int]
    reason: str

@dataclass(frozen=True)
class ExpandRelationship:
    id: str
    root_observation_id: str
    root_node_id: str
    direction: str             # incoming or outgoing
    edge_kinds: tuple[str, ...]
    need: str
    max_results: int

@dataclass(frozen=True)
class SearchNewIsland:
    id: str
    obligation_id: str
    dense_query: str
    sparse_anchors: tuple[str, ...]
    exact_symbol_anchors: tuple[str, ...]
    exact_path_anchors: tuple[str, ...]
    result_limit: int

@dataclass(frozen=True)
class StopRetrieval:
    id: str
    reason_code: str
```

### Required directional CodeGraph extension

Add one explicit operation rather than pretending `structural_expand_nodes` is directional:

```text
tool: structural_expand_relationships
arguments:
  node_ids: [qualified root node IDs]
  direction: incoming | outgoing
  edge_kinds: non-empty allowlist from known CodeGraph kinds
  depth: 1 in the first implementation
  limit: small bounded integer, initially 3 per action
result:
  seed_node_ids
  nodes
  edges with exact source/target/kind/provenance
```

Action enumeration also needs a non-expanding batched preflight operation:

```text
tool: structural_edge_capabilities
arguments:
  node_ids: qualified root node IDs, capped at 16
result:
  nodes: [{node_id, incoming: [{kind, count}], outgoing: [{kind, count}]}]
```

This operation calls `getIncomingEdges()` and `getOutgoingEdges()` but returns only edge-kind counts, never endpoint nodes. It proves which directional relationship families are represented around each exact root without introducing candidates. The controller performs it once when the active-root set changes and caches the result for that root set. An empty capability result is valid and means no structural action is enumerated for that direction/kind.

Implementation details:

- Use only `getIncomingEdges()` for incoming and `getOutgoingEdges()` for outgoing.
- Filter edge kinds before adding an endpoint.
- Depth remains exactly one in the first experiment. Multi-hop traversal is performed, if needed, through a later controller round after the new endpoint is qualified.
- Return exact entity payloads and connecting edges, not only file paths.
- Deduplicate endpoint node IDs and preserve all qualifying edge provenance.
- Never call broad `structural_expand_nodes` from the new controller.

Actions can be enumerated only when:

- the root has an exact CodeGraph `node_id`;
- the missing-information category has a configured mapping to a relationship direction/kind;
- the cached `structural_edge_capabilities` result proves the requested relationship kind and direction are represented around the exact root;
- the same action fingerprint has not already run for that root;
- remaining round/tool budgets permit it.

The initial conservative mapping is:

| Missing information | Allowed action only when | Direction/kinds |
|---|---|---|
| Upstream trigger/caller | Root is a callable entity and CodeGraph has an exact node ID. | Incoming `calls` only. |
| Downstream behavior/effect | Root is callable and the question requires what it invokes. | Outgoing `calls`, optionally `instantiates` in a separately selected action. |
| Interface implementation | Root is an interface/class/member with an exact node. | Direction and `implements`/`overrides`/`extends` chosen from relationships actually present around the root; if presence cannot be cheaply established, do not enumerate the action. |
| Imported dependency | Visible source contains a concrete imported identifier/path and CodeGraph represents it. | Outgoing `imports` or exact path/symbol search; never “all dependencies.” |
| State producer/consumer | A promoted source range visibly reads or writes a distinctive field and dispersion checks show it is not generic. | No graph action in the first slice unless an exact `state_write_read` relationship already exists. Otherwise schedule an exact/sparse new-island search for the field. |
| Registration/callback | Visible source contains the concrete registry key, callback name, or factory member. | Exact symbol/literal search first. A generic “registered_callback” graph action is not assumed available. |
| Test/contract | Visible behavior symbol or exact literal is available. | New-island exact/sparse search; no blanket test-neighbor traversal. |

If the capability preconditions are not met, the action is not offered. The system records `action_unavailable` with the missing capability. It must not substitute broad bidirectional expansion.

LocAgent exposes direction, depth, node-type, and edge-type filters to its graph-navigation tool rather than hiding them in unrestricted expansion: [LocAgent structure tools](https://github.com/gersteinlab/LocAgent/blob/4935b557326c154bad8e8dcf3747cc8d32d1f387/util/runtime/structure_tools.py). The workspace adapter must reach a comparable explicit contract before claiming precise graph control.

### Action result admission

Every returned endpoint becomes a new `DiscoveryObservation` with:

- parent root ID;
- exact action ID;
- direction and edge kind;
- exact source/target edge provenance;
- source handle but no evidence status.

The endpoint is disclosed and qualified before it can become an active root or `GroundedCandidate`. If no result is promoted and coverage does not improve, the action family is exhausted for that root.

## Stage 7: Independent new-island search

`SearchNewIsland` is an explicit primary action, not a fallback. It is appropriate when coverage remains missing and no active root has a supported structural action that could answer the gap.

Its query inputs are channel-separated:

- dense query: the unresolved obligation description unchanged;
- sparse terms: exact identifiers, literals, configuration keys, and symbols learned from already disclosed source;
- exact structural queries: known symbol/path handles;
- optional path restrictions: only explicit user paths or a path proved by a promoted source reference;
- no requirement that results connect to current islands;
- no model-invented global “better query.”

The first implementation can continue using `qdrant_hybrid_search` with the unchanged obligation description while passing exact anchors through the existing mechanisms. It should not concatenate every discovered term into the dense query. Returned hits are aggregated into observations and pass through disclosure and qualification.

This action is required for disconnected evidence such as the TypeScript builder and watch/helper islands. Lack of a CodeGraph path is not evidence that the second island is irrelevant.

## Stage 8: Bounded controller loop

`retrieval_controller.py` owns only the state machine:

```text
qualify initial observations
build islands and select active roots
evaluate coverage

for each bounded round:
  enumerate executable action IDs
  choose at most two actions
  execute actions
  create observations
  disclose and qualify new observations
  rebuild islands/active roots
  reevaluate coverage
  compute evidence and coverage gain
  stop or continue
```

Use three rounds as the normal ceiling and `WorkspaceRetrievalConfig.max_exploration_rounds=4` as the hard ceiling. Round 4 is executable only after a productive private-identifier exact search in round 3. Use `max_controller_actions_per_round=2` rather than the older `max_tool_calls_per_round=5`, whose meaning belongs to older exploration behavior.

The first implementation uses a deterministic scheduler over the enumerated action IDs. This keeps action policy auditable and avoids introducing a third LLM decision while measuring the new admission order. It applies this stable priority:

1. Inspect a deferred observation when it is already tied to the exact missing claim and needs only fuller source disclosure.
2. Select a capability-checked relationship action tied to the missing claim, alternating across evidence islands before selecting a second action from one island.
3. Select a new-island search when no existing root has an executable structural action for the gap.
4. Break remaining ties by required-obligation contract order, stable island ID, stable root ID, and stable action ID.

The scheduler selects at most two actions and records the rule that selected each one. It never supplies or modifies raw tool arguments; those are fixed inside the validated action object.

There are two defensible later variants if this deterministic mapping proves too rigid:

- A compact LLM may choose only from enumerated action IDs using current coverage, root cards, prior outcomes, and remaining budgets. Unknown IDs or changed preconditions fail validation.
- A learned policy may rank the same closed action catalogue after sufficient labeled traces exist.

Neither variant belongs in Step 1. They must be isolated experiments because they add another source of run-to-run behavior.

AutoCodeRover provides the relevant control pattern: it repeatedly analyzes collected context and chooses concrete search APIs, while its search backend limits displayed results to three: [agent loop](https://github.com/AutoCodeRoverSG/auto-code-rover/blob/585d3e639aeda58ef0b6a151dd1cc2721a94d267/app/agents/agent_search.py#L80) and [result limit](https://github.com/AutoCodeRoverSG/auto-code-rover/blob/585d3e639aeda58ef0b6a151dd1cc2721a94d267/app/search/search_backend.py#L20). Cody likewise performs a bounded context review loop, defaults to two iterations, and can replace its active context with the reviewed subset before another iteration: [Deep Cody review loop](https://github.com/sourcegraph/cody-public-snapshot/blob/8e20ac6c1460c08b0db581c0204658112a246eda/vscode/src/chat/agentic/DeepCody.ts#L113) and [reflection](https://github.com/sourcegraph/cody-public-snapshot/blob/8e20ac6c1460c08b0db581c0204658112a246eda/vscode/src/chat/agentic/DeepCody.ts#L283).

### Stop conditions

Stop with an explicit reason when any condition holds:

- all required/`one_of` coverage is satisfied;
- no executable actions remain;
- the round limit is reached;
- the tool/action budget is exhausted;
- a round produces no newly promoted observation and no coverage improvement;
- all remaining gaps require evidence outside repository scope;
- a required LLM/tool stage fails.

Evidence gain means a new stable grounded candidate ID or an existing obligation moving from `missing` to `partial/covered` with cited support. More observations, more edges, or more files do not count as gain.

The repository already proposed an adaptive outer loop in [`workspace retrieval intent and adaptive loop research.md`](../../../../testing/codeRepoQA/workspace%20retrieval%20intent%20and%20adaptive%20loop%20research.md). The difference now is that the loop replaces the fixed expansion/recovery scheduler and is constrained by source-qualified roots and executable action IDs.

## Stage 9: Final evidence and mechanism construction

Only `promote + direct_evidence` items and later action results that pass the same test become final-selection candidates. Navigation-only roots are excluded unless a later disclosure/qualification upgrades them.

Before final selection:

- deduplicate exact candidate identities across obligations;
- preserve many-to-many obligation provenance;
- build relationships only among promoted candidate IDs;
- add a connector only through an explicit, qualified controller action;
- do not construct flows over every observation or deferred hypothesis;
- reintroduce an aggregate serialized-character budget, initially 30k-50k, and record actual size before the LLM call.

The existing `_select_mechanism_flows()` may be reused only after changing its input boundary from all expanded candidates to the promoted evidence set. Existing exact CodeGraph edges, file-call localization, resource references, and conservative source-derived relationships remain useful. The current maximums of 128 seeds and 1,024 flows are not appropriate for the new bounded evidence set and should be removed or reduced after measurement.

The older [`LLM_EVIDENCE_GRAPH_TOKEN_PLAN.md`](../../../../LLM_EVIDENCE_GRAPH_TOKEN_PLAN.md) already places graph enrichment after selected evidence and permits honestly disconnected nodes. That order should be restored: the graph communicates selected evidence; it does not create hundreds of evidence candidates.

`_consolidate_obligation_evidence()` remains the final evidence-selection LLM in Step 1. Its payload construction must be changed to accept the promoted candidate set and bounded relationships. Later Step 2 moves it into `final_evidence_selection.py` without changing behavior.

## Failure behavior and observability

There is one runtime path. The old fixed graph/recovery schedule must not remain as a fallback behind a feature flag. Baseline comparison uses the parent commit/run artifacts, not a second production implementation.

Required trace events:

| Event | Required fields |
|---|---|
| `discovery_observations_created` | raw result count, aggregated count, stable observation IDs, provenance, guardrail reasons |
| `disclosure_cards_created` | observation ID, mode, source handle, displayed/full ranges, chars, truncation reason |
| `qualification_requested` | card IDs, serialized chars, model/prompt ID, budget |
| `qualification_decisions_created` | every observation ID, disposition, support level, visible support, missing information |
| `closed_set_relationships_created` | requested node IDs, returned in-set edges, component IDs |
| `active_roots_selected` | island IDs, selected and inactive promoted roots, reasons |
| `coverage_evaluated` | each obligation status, cited candidate IDs, missing claim/need |
| `controller_round_started` | round, budgets, root IDs, coverage snapshot |
| `controller_actions_enumerated` | allowed action IDs plus preconditions; unavailable actions plus exact reason |
| `controller_actions_selected` | selected IDs and validated reason |
| `controller_action_executed` | exact tool request, status, endpoint observation IDs, elapsed time |
| `controller_round_completed` | new observations, promotions, coverage changes, evidence-gain boolean |
| `retrieval_controller_stopped` | one explicit stop code and final budgets |
| `final_candidate_pool_created` | candidate IDs, files, islands, relationships, serialized chars |

Existing `RetrievalTrace.record_tool()` already records complete tool requests and observations. New stage events use stable IDs so a run can reconstruct exactly how each result changed state.

Explicit failure codes should distinguish at least:

- `qualification_llm_failed`;
- `qualification_response_invalid`;
- `coverage_llm_failed`;
- `coverage_response_invalid`;
- `required_tool_failed`;
- `source_disclosure_unavailable` when it prevents any root qualification;
- `controller_budget_exhausted`;
- `no_executable_action`;
- `no_evidence_gain`.

No exception path invokes old expansion, converts every observation to a candidate, or fabricates coverage.

## Implementation sequence

### Step 1: Replace admission and orchestration with minimal unrelated movement

Goal: measure qualification-before-expansion without simultaneously reorganizing every old helper.

1. Add `discovery_observations.py`, its models, aggregation, role-neutral guardrail, trace serialization, and focused unit tests.
2. Add `structural_file_outline`, `structural_relationships_within_nodes`, `structural_edge_capabilities`, and `structural_expand_relationships` to the CodeGraph bridge/tool contracts with integration tests. Do not expose directional controller actions until these tests prove closed-set behavior, non-expanding capability inspection, direction, and edge filtering.
3. Add `source_disclosure.py` and test fold/preview/full behavior, stable source handles, full-range preservation, unreadable source, missing outline, and large-owner paging.
4. Add `evidence_qualification.py`, its prompt/schema, strict response validation, and explicit failure tests.
5. Add `evidence_islands.py` and test closed-set-only components, singleton disconnected roots, component-diverse selection, role neutrality, and no neighbor introduction.
6. Add `coverage_evaluation.py` and test cited coverage, navigation-only exclusion, many-to-many evidence, missing/contradictory states, and invalid responses.
7. Add `retrieval_actions.py` and test capability-based action enumeration, exact direction/kind filtering, repeated-action suppression, result-to-observation conversion, and unavailable-action logging.
8. Add `retrieval_controller.py` and test sufficient stop, no-action stop, no-gain stop, maximum rounds, maximum actions, new-island action, multiple active islands, and explicit stage failure.
9. Modify `run_obligation_retrieval()` to:
   - keep existing anchor grounding and initial Qdrant queries;
   - produce observations rather than initial `GroundedCandidate`s;
   - call disclosure, qualification, islands, coverage, and controller;
   - convert only direct-evidence promotions to `GroundedCandidate`s;
   - build bounded relationships/flows over promoted candidates;
   - call existing final consolidation.
10. Remove unconditional calls from the runtime order to `_expand_grounded_candidate_graph()`, `_run_focused_semantic_bridge()`, `_semantic_root_file_neighbors()`, `_ground_semantic_root_neighbors()`, `_recover_connected_semantic_endpoints()`, `_recover_prompt_relevant_exact_callees()`, and `_recover_factory_handoffs()`. Keep a helper only if it is called through a typed action or later final relationship construction; otherwise delete it after tests are migrated.
11. Reintroduce a final-selection serialization budget and trace its use.
12. Run unit/integration tests, then the real retrieval comparisons below.

Do not implement BM25F, rewrite queries, replace the embedding model, add a cross-encoder, or generalize every AST language adapter in Step 1.

### Step 2: Complete modular extraction after behavior is accepted

Goal: remove the giant-file architecture without mixing a mass code move into the initial quality comparison.

1. Move anchor confirmation and exact prompt seed helpers into `request_grounding.py`.
2. Move `GroundedCandidate`, `CandidateFacts`, range-to-source conversion, deterministic source facts, candidate identity, merge, and deduplication into `candidate_grounding.py`.
3. Move normalized CodeGraph/source relationship creation into `relationship_evidence.py`.
4. Move mechanism path selection and its budgets into `mechanism_flows.py`.
5. Move final consolidation payload/schema/validation into `final_evidence_selection.py`.
6. Reduce `obligation_retrieval.py` to a readable facade that wires stages and builds `RetrievalResult`; it must not regain policy helpers.
7. Split `tests/test_obligation_retrieval.py` along the same ownership boundaries. Move tests without weakening assertions or deleting historical regression cases that remain applicable.
8. Remove constants that belong to retired broad expansion. Put active budgets in `WorkspaceRetrievalConfig` and reusable profile configuration rather than scattering module constants.
9. Update docstrings and the retrieval changelog with the final file map and measured run IDs.

This is a mechanical/ownership phase. If behavior changes while extracting, isolate and measure that change separately.

### Step 3: Evaluate future retrieval improvements separately

Only after the new order is stable should the Future Experiments below be attempted, one at a time with the same real-run gates.

## Real comparison plan

Use the standard CodeRepoQA workspace profile and pass `--skip-response-generation`. Keep final evidence selection enabled; do not pass `--skip-final-evidence-selection` for the main comparison.

Run twice each:

- `microsoft-TypeScript-35468`;
- `vuejs-vue-10803`;
- `pandas-dev-pandas-10068`.

Treat TypeScript `401.json` as a separate case. It is not the disconnected TypeScript 35468 benchmark and must not be used as a substitute.

Record for each run:

- run ID, commit, configuration, snapshot, Qdrant rebuild/reuse state;
- raw hits by exact/dense/sparse/hybrid channel;
- aggregated observation count and unique paths/entities;
- guardrail exclusions and reasons;
- disclosure modes, characters, and source handles;
- promote/defer/reject counts and reasons;
- active roots and independent island count;
- coverage after initial qualification and each round;
- all enumerated, unavailable, selected, and executed actions;
- graph endpoints returned and subsequently promoted/rejected;
- new-island searches and their results;
- final candidate IDs/files/islands;
- Oracle survival at raw observation, guardrail, qualification, active-root, and final-selection boundaries;
- final consolidation serialized characters and LLM tokens;
- total retrieval LLM tokens, tool calls, and elapsed time;
- `coverage_status` and `sufficient`.

Primary acceptance conditions:

1. TypeScript retains both the builder and watch/helper islands through qualification in both runs. A single disconnected island is a regression even if token usage falls.
2. Candidate and consolidation payload volume falls materially from the roughly 200-candidate and 470k-586k-character recent TypeScript behavior.
3. Vue and pandas owner survival does not regress across their two repeats.
4. No run reaches the final selector through a hidden fallback or old expansion scheduler.
5. Trace events can reconstruct why every final candidate was introduced and promoted.
6. Actual retrieval tokens are reported; response-generation tokens are absent because response generation was skipped.

If two real comparisons lose an evidence island or destabilize owner survival, revise or revert the qualification/beam policy. Do not add a late broad recovery cascade to hide the failure.

## Retrieval terminology

Use these terms consistently in traces, evaluation notes, and future implementation work:

- **Discovered:** Qdrant, exact search, CodeGraph, or another retriever returned a source location. Discovery is a navigation observation, not a relevance or truth decision.
- **Initial observation:** A discovered location survived aggregation into the bounded first qualification pool (24 in Step 1).
- **Deferred observation:** A discovered location remained outside the initial pool but was retained as a stable handle for a possible later inspection action.
- **Qualified:** Bounded disclosed source for an observation was inspected by the qualification LLM and received an explicit disposition/support decision.
- **Promoted:** Qualification retained an observation as either direct evidence or navigation-only context. Promotion is request-relative and fallible; it is not an Oracle or correctness label.
- **Navigation candidate:** The visible source is useful for locating better evidence but does not itself establish an obligation. It may enter final reranking but must not count as coverage proof.
- **Direct-evidence candidate:** The visible source directly supports at least one requested claim according to qualification. It may contribute to coverage, but later comparison can still reject it as redundant, generic, or contradictory.
- **Active root:** A promoted observation currently admitted to the bounded root beam and therefore eligible to originate structural or path-local follow-up actions.
- **Refined:** A controller action retrieved a more appropriate range or owner within an already identified file; the returned observation must be disclosed and qualified again.
- **Selected:** Final evidence consolidation retained a candidate for answer generation after comparing support, obligation coverage, causal role, relationships, redundancy, and contradictions.

These are pipeline states, not ground-truth classes. Evaluation must separately measure Oracle survival and semantic precision at every boundary.

Operational caution: `qualified` means inspected, not relevant; `promoted` means plausibly useful, not correct; `direct_evidence` is a fallible request-relative LLM judgment; `active root` is a scheduling choice, not necessarily the most likely owner; and `selected` reduces noise but does not guarantee that every retained item is useful. Logs and evaluation must not present these states as confidence or Oracle labels.

Bounded disclosure has an unavoidable context trade-off. For an oversized owner, the matched range is the strongest available local lead, but a bounded window can omit earlier state that later proves necessary. The first implementation should preserve the stable owner handle, signature, range, and truncation reason so a later controller action can request more context; it should not add speculative logic that tries to predict every omitted dependency. This limitation must be visible in traces and evaluation rather than described as certain source understanding.

## Open empirical research questions

These questions are intentionally separated from implementation requirements. They should remain visible in experiment notes and may be used directly when framing the later thesis evaluation:

1. What role-neutral observation-pool size best preserves distinct Oracle evidence islands while minimizing qualification cost? The initial hypothesis is a maximum of 24 aggregated file/entity observations, but 12, 18, 24, and adaptive limits should be compared.
2. How much disclosed source context does reliable pre-expansion qualification require? The initial 40,000-character request budget should be compared against smaller budgets, per-card caps, and progressive follow-up disclosure.
3. What controller breadth and depth are sufficient for multi-island evidence retrieval? Two actions and three rounds were sufficient for TypeScript and Vue but not consistently for pandas: resolving `_maybe_match_name`, qualifying it, and then traversing callers required a fourth round. The implemented policy therefore uses three normal rounds plus one conditional exact-owner follow-up. Future experiments should compare this adaptive rule with fixed three/four-round policies and measure marginal evidence gain per round.
4. How consistently does source qualification preserve every Oracle evidence island across repositories, repeated runs, artifact roles, and disconnected ownership structures?
5. Does qualification-before-expansion materially reduce candidates, serialized context, retrieval tokens, and tool calls without reducing Oracle survival, coverage, or sufficiency stability?

Each experiment should treat these as measurement questions, not assumptions. Record the tested value, repeated-run variance, Oracle survival boundary, token impact, and any failure mode that explains the result.

## Future experiments

These ideas are deliberately recorded here so they are not forgotten, but they are not part of Step 1.

### Bounded file-handoff completion and contextual disclosure

The accepted TypeScript 35468 traces expose two separate losses that should be tested without restoring broad graph expansion:

- `run-20260814T060815Z` admitted `src/compiler/builder.ts` as a navigation candidate from lines 81-85, but that five-line card ended after a comment and immediately before the `BuilderProgramState` declaration. A universal larger minimum snippet would waste context on already complete small functions. Instead, test a simple owner-bounded disclosure policy. Resolve the outer callable owner as the clipping boundary when the match is in a function, while retaining a complete smaller nested owner when it fits. Disclose a complete function/method/declaration when it fits; otherwise include the outer-owner signature and a bounded local window around the match without crossing that owner boundary. A leading documentation comment should travel with the declaration it documents. An internal comment uses the same local-window rule. For a class match, disclose the class skeleton plus the matching member rather than the complete class. Preserve the complete owner handle for later refinement and label any non-structural fallback explicitly. Avoid additional nesting/comment corner cases until traces demonstrate a repeated failure.

The disclosure budget must be derived from the real qualification payload budget rather than configured independently. Compute available card content as `max_qualification_input_chars` minus the serialized request, schema/base metadata, per-card metadata, and a serialization/safety reserve. Divide that content capacity across the actual card count, render complete smaller owners first, and redistribute their unused shares among oversized cards. A changed global budget or observation count must therefore change card capacity automatically. Truncation accumulates complete source lines only; if the next line would exceed the allocated characters, omit that complete line and record the omission rather than slicing it. A single oversized/minified line receives an explicit omitted-line marker plus its stable handle. Trace the global capacity, initial and redistributed per-card allocation, used characters, owner identity/range, disclosure mode, and truncation reason.
- Both accepted runs retained useful `src/testRunner/unittests/tsbuild/watchMode.ts` context, while `src/testRunner/unittests/tscWatch/helpers.ts` either produced an irrelevant initial range and an uninspected deferred range (`run-20260814T060345Z`) or produced no discovery observation (`run-20260814T060815Z`). The prepared CodeGraph contains direct `calls` edges from the `watchMode.ts` file node to `verifyTscWatch` in `helpers.ts`, but the relevant diagnostic-baselining logic is owned by `baselineProgram` rather than by `verifyTscWatch` itself.

Test this bounded action sequence:

```text
qualified watchMode.ts file/range
  -> resolve or attach its CodeGraph file node
  -> one outgoing calls handoff to verifyTscWatch in helpers.ts
  -> qualify the endpoint as navigation
  -> one path-local search inside helpers.ts using the unresolved obligation
  -> disclose and qualify baselineProgram or another returned owner
  -> stop the strand if direct evidence, navigation, or coverage does not improve
```

This is not permission for fixed depth-five traversal. In the prepared snapshot, `baselineProgram` is five call edges downstream from the `watchMode.ts` file node; recursively materializing every intermediate neighbor would recreate the fanout problem. The cross-file edge should identify the target file, after which path-local retrieval should localize the relevant owner inside that file.

Do not reserve actions for hardcoded names such as "builder" or "watch." A future scheduler may preserve at most a small number of highest-priority, semantically distinct file/subsystem islands after qualification, but grouping and priority must come from runtime evidence. The current `EvidenceIsland` components are too fragmented to use directly: the accepted TypeScript runs produced 14 and 20 internal graph islands for only 19 and 21 candidates. Before enabling completion, compare file-level or subsystem-level grouping and require action accounting per retained island. The first experiment should keep the global observation cap and relationship result limit unchanged.

Current `EvidenceIsland` means only a connected component over promoted observations whose exact CodeGraph node IDs have an edge between them. Range-only observations have no node ID and therefore become singleton components. Two observations in one file remain separate unless their exact nodes are connected; two observations in different files may join when their exact nodes are connected. During the experiment, rename this graph-only object and trace event to `StructuralComponent`. Reuse the preferred `EvidenceIsland` term for the semantic, actionable unit: a bounded group of qualified observations that plausibly participates in one mechanism or unresolved explanatory strand and can receive controller actions together.

If this experiment is accepted, update the retrieval terminology dictionary, schemas, trace event names, evaluation readers, and documentation atomically: the old graph-connected `EvidenceIsland` becomes `StructuralComponent`, and only the new semantic/actionable object keeps the name `EvidenceIsland`. Do not leave both meanings active or rely on readers to infer which one a run used.

Implement the future semantic-island experiment with two separate ownership files: `structural_components.py` for graph-only components and `evidence_islands.py` for an explicit `EvidenceIsland` record containing stable ID, member observation IDs, normalized files, enclosing owners, obligation IDs, qualification support, exact anchors, action provenance, structural components, unresolved needs, rank features, and prior action/evidence gain. Construct semantic islands after qualification and structural-component creation:

1. Resolve range-only observations to an enclosing owner or file node where possible; do not invent an AST identity when resolution fails.
2. Union observations when they share an enclosing owner, came from the same bounded action handoff, or have a represented structural edge and overlap in unresolved obligations.
3. Within one file, union separate owners only when obligation overlap plus call/reference/action provenance supports one mechanism; same-file membership alone is insufficient.
4. Across files, require a represented relationship or an explicit independent-search/action provenance. Similar vocabulary alone is insufficient.
5. Rank islands from qualification support, unresolved-obligation fit, exact anchors, recurrence, retrieval rank, and evidence/coverage gain. Penalize ambiguity, repeated declaration-only representations, and redundancy, but do not apply a global test-role penalty.
6. Retain a configurable small beam (initially compare 2, 3, and 4), preserving obligation and subsystem diversity. Give at most one action slot to a retained island per round before unused slots return to the global catalogue.
7. Generate actions only after island formation, attach every action to an island ID, and first choose among islands rather than sorting one flat 70-108-action list. Within a chosen island, prefer an untried action whose relationship/direction or path-local target addresses its highest-priority unresolved need. Log all island and action scores plus the exact reason each of the two execution slots was assigned.
8. Keep backend-owned arguments and action-effect deduplication. If an LLM selector is tested, it may choose only among the reduced known island/action IDs and must report why one island received or lost a slot.

The final evidence LLM must not create these islands because it runs after retrieval. The experiment should compare deterministic semantic-island grouping with the bounded known-ID LLM selector independently. This experiment directly addresses the current action-selection failure: a two-action cap is defensible only after the flat catalogue has been reduced to a few credible, diverse islands; raising the cap while preserving the current first-ranked-action scheduler is not the experiment.

### Channel-specific structured query redesign

The first implementation deliberately preserves `_obligation_stage_query_text()` and `_obligation_query()`. A later experiment may stop converting all available intent information into one string and instead route the existing `IntentContext` fields by capability:

- raw request or unchanged obligation description to dense embedding;
- exact identifiers/literals/config keys to sparse retrieval;
- confirmed paths and symbols to structural/exact retrieval;
- source category and artifact role to metadata only when the request explicitly justifies a restriction;
- learned terms from promoted source to explicit new-island searches.

The experiment must not ask an LLM to invent one global rewritten query. It should compare channel-specific structured inputs against the unchanged current queries after the admission-order redesign is stable. [`stable-obligation-query-strand.md`](../stable-obligation-query-strand.md) is the negative baseline: adding another deterministic query strand did not recover owners.

### Flat action scheduler audit

The current deterministic scheduler is preferable to arbitrary first-come-first-served execution, but it still chooses two actions from catalogues that reached roughly 70-108 possibilities using coarse priority features and a semantically meaningless stable-hash tie-breaker. Record this as a separate scheduling problem even if semantic evidence islands reduce its severity. After island formation is available, compare whether the existing ordering repeatedly starves actions that produce distinct evidence or coverage gain. Do not prescribe a learned solution yet; first measure which generated actions lost a slot, their island and unresolved need, the selected alternatives, and the marginal gain of each executed action.

### Learned or LLM controller action selection

Step 1 deliberately uses a deterministic policy over an executable action catalogue. If traces show repeated cases where several valid actions exist and the fixed ordering consistently spends the budget on the wrong one, compare a compact LLM selector that may return only known action IDs. Tool arguments remain backend-owned. Measure action utility, evidence gain, tokens, stability, and invalid decisions against the deterministic scheduler; do not combine this experiment with query or ranking changes.

### Multi-language outline and source-fact adapters

Step 1 uses CodeGraph file nodes plus exact source ranges for outlines and keeps the TypeScript compiler adapter specialized. If real runs show that missing outlines prevent qualification in Python, Java, Go, or other important repositories, evaluate a multi-language tree-sitter outline service.

Variants:

- extend CodeGraph output if its internal parsers already expose sufficient node kinds/ranges;
- add a tree-sitter-based outline adapter with one normalized output contract;
- add language-specific compiler adapters only for unsupported high-value cases.

Do not label regex declarations as AST output. Any new third-party runtime import must update the correct direct dependency manifest in the same change.

### Field-aware BM25F and line scoring

Current BM25 uses one flattened document text:

```text
path
basename
chunk body
```

The index stores symbol metadata, but sparse scoring does not assign separate field weights. Sourcegraph's BM25F implementation ranks files using separately weighted filename, symbol-definition, and content fields, then performs line-level BM25F with symbol-span boosts before a semantic reranker: [Keeping it boring (and relevant) with BM25F](https://sourcegraph.com/blog/keeping-it-boring-and-relevant-with-bm25f).

A future experiment should:

1. Extend indexed documents with explicit normalized fields: full path, basename, definition symbols, reference symbols where available, and body text.
2. Implement or adopt BM25F scoring with configurable field weights and length normalization.
3. Keep artifact role separate from lexical relevance; do not encode a global test penalty.
4. Use BM25F only to order discovery observations. It must not bypass source qualification.
5. Compare current flat BM25 versus BM25F with all later stages unchanged.
6. Record raw-channel owner recall, observation guardrail survival, qualification survival, tokens, and latency.

This could improve inspection order for filenames and definitions, but it cannot by itself solve disconnected evidence, semantic ambiguity, or admission. It is therefore a later isolated experiment.

### Dedicated second-stage code reranker

After source qualification is stable, a compact cross-encoder or LLM reranker could order disclosure cards before qualification. It must not make final admission decisions, and it should be tested only if qualification payloads remain too large. Sourcegraph's two-stage retrieval design is inspiration, not evidence that a particular reranker will improve these benchmarks.

### Repository-evidenced generated-artifact classification

Generated-artifact handling must be consistent across initial indexes and observations introduced later by CodeGraph actions. The current path/name rules catch conventional build, snapshot, baseline, and `.generated.*` artifacts, but they do not prove that every declaration under `lib/` or every `.d.ts` file is generated. Those broad rules would be unsafe: repositories commonly use `lib/` for maintained source, and handwritten declarations can be the primary API or type contract.

The prepared TypeScript repository provides narrower evidence: its Gulp build creates `lib/typescript.d.ts`, `lib/typescriptServices.d.ts`, and `lib/tsserverlibrary.d.ts`, while `scripts/produceLKG.ts` copies those outputs into `lib/`. Treat this as repository-specific build provenance, not a universal directory convention. A future isolated experiment should:

1. Apply the same artifact classifier to Qdrant/BM25 discovery and CodeGraph-introduced observations.
2. Accept explicit repository exclusion patterns and, where cheaply available, build-manifest or build-script provenance for known output paths.
3. Keep source-authored declarations eligible and prefer a source implementation when a generated/output declaration duplicates it; retain a declaration when the request is specifically about the public or type contract.
4. Log the exact classification signals and whether the item was excluded, deprioritized, or retained. Do not silently infer generated status from an extension or directory alone.
5. Treat an enormous/minified-line statistic only as a weak logged likelihood signal. Legitimate source can contain long strings, regular expressions, embedded data, SQL, or fixtures, while generated source can be normally formatted. A long line must never independently exclude a file.
6. Compare declaration/API Oracle survival, generated-duplicate volume, action slots consumed, and qualification tokens with all later stages unchanged.

### File-level trace evidence when exact localization is unjustified

Some relevant files are structural participants even when the pre-fix request and available source do not justify one exact explanatory snippet. TypeScript 35468 is a concrete example: `watchMode.ts` calls the shared test harness in `tscWatch/helpers.ts`, while the fixing PR changes a narrow `file.path` to `file.resolvedPath` check inside `baselineProgram`. Requiring retrieval to predict that exact changed line from the issue text is closer to patch localization than explanation-oriented evidence collection.

Test a separate `FileTraceEvidence` navigation type rather than mislabeling a file as direct source evidence. It should contain the normalized file path, source observation/evidence island, represented relationship and direction, unresolved obligation, and a concise reason the file remains structurally relevant. It must:

- require a qualified source plus a represented structural or explicit action-provenance handoff;
- never establish line-level claims or obligation coverage by itself;
- remain distinct from source snippets in final serialization and UI rendering;
- be deduplicated by file/evidence-island pair and tightly capped (compare one and two traces);
- be eligible for optional later path-local refinement;
- be evaluated separately as file recall, not counted as snippet precision or used to inflate Oracle evidence scores.

The final explanation may use a file trace only to state that the file is a likely structural participant whose exact relevant owner remains unresolved. It must not infer the eventual patch or claim behavior absent inspected source.

### Necessary-contribution filtering in final evidence selection

The accepted runs show that final consolidation can retain generic filesystem plumbing, declaration duplicates, or broad server context that is topically related but does not add a necessary explanatory claim or structural trace. Test a final-selection contract that requires every retained item to identify one distinct contribution: direct support for an unresolved obligation, a causal/structural link between retained evidence, a non-redundant public contract, a contradiction, or an explicitly typed `FileTraceEvidence`. Topical similarity alone is insufficient.

Keep this experiment separate from discovery, disclosure, and island scheduling so its effect is attributable. The selector should return a contribution type and short request-relative reason for every retained candidate, identify the candidate or claim it would duplicate, and reject generic context whose removal changes no supported claim or trace. Evaluate semantic precision manually on repeated TypeScript, Vue, and pandas runs, alongside Oracle survival, unique selected files/snippets, retained contribution types, consolidation characters, and final-selection tokens. Do not require a candidate to predict the eventual patch, and do not let this stage conceal an upstream discovery loss.

Measure separately:

1. comment-only/declaration-boundary cards repaired before qualification;
2. target files reached by a single structural handoff;
3. owners recovered by the subsequent path-local search;
4. candidate snippets and unique files before and after completion;
5. structural-component versus semantic evidence-island counts;
6. Oracle survival at discovery, qualification, candidate, and final-selection boundaries;
7. marginal qualification, coverage, and final-selection tokens.

### Disclosure and qualification caching

Stable source handles allow caching disclosure cards by repository snapshot, path/range/node ID, and content hash. Qualification results additionally depend on the user request and prompt/schema version. Cache only exact identities; do not reuse semantic decisions across different requests.

## External implementation references

These links were rechecked while preparing this plan. External behavior is cited only where it directly informs a boundary above.

- [Agentless `FL.py`, pinned](https://github.com/OpenAutoCoder/Agentless/blob/5ce5888b9f149beaace393957a55ea8ee46c9f71/agentless/fl/FL.py): repository-structure file localization followed by compressed source localization.
- [Agentless `localize.py`, pinned](https://github.com/OpenAutoCoder/Agentless/blob/5ce5888b9f149beaace393957a55ea8ee46c9f71/agentless/fl/localize.py): top-file orchestration and test filtering that must not be copied literally.
- [LocAgent repository operations, pinned](https://github.com/gersteinlab/LocAgent/blob/4935b557326c154bad8e8dcf3747cc8d32d1f387/plugins/location_tools/repo_ops/repo_ops.py): exact/entity/BM25 search and adaptive fold/preview behavior.
- [LocAgent result formatting, pinned](https://github.com/gersteinlab/LocAgent/blob/4935b557326c154bad8e8dcf3747cc8d32d1f387/plugins/location_tools/utils/result_format.py): complete, preview, skeleton, and snippet disclosure.
- [LocAgent structure tools, pinned](https://github.com/gersteinlab/LocAgent/blob/4935b557326c154bad8e8dcf3747cc8d32d1f387/util/runtime/structure_tools.py): explicit graph direction/depth/type filters.
- [AutoCodeRover search agent, pinned](https://github.com/AutoCodeRoverSG/auto-code-rover/blob/585d3e639aeda58ef0b6a151dd1cc2721a94d267/app/agents/agent_search.py): iterative context analysis and concrete search actions.
- [AutoCodeRover search backend, pinned](https://github.com/AutoCodeRoverSG/auto-code-rover/blob/585d3e639aeda58ef0b6a151dd1cc2721a94d267/app/search/search_backend.py): bounded displayed search results.
- [Cody `ContextRetriever`, pinned](https://github.com/sourcegraph/cody-public-snapshot/blob/8e20ac6c1460c08b0db581c0204658112a246eda/vscode/src/chat/chat-view/ContextRetriever.ts): multi-source retrieval and query-rewrite implementation.
- [Cody `DeepCody`, pinned](https://github.com/sourcegraph/cody-public-snapshot/blob/8e20ac6c1460c08b0db581c0204658112a246eda/vscode/src/chat/agentic/DeepCody.ts): bounded review loop and context replacement before later retrieval.
- [Aider repository map](https://aider.chat/docs/repomap.html) and [implementation](https://github.com/Aider-AI/aider/blob/main/aider/repomap.py): graph-ranked symbol skeletons under a token budget.
- [Sourcegraph BM25F article](https://sourcegraph.com/blog/keeping-it-boring-and-relevant-with-bm25f): field-aware file/line lexical ranking and two-stage retrieval.

## Final implementation rule

The redesign succeeds only if it makes uncertainty explicit and keeps each decision reversible until source content supports promotion. It must not replace broad graph explosion with an equally brittle lexical, path, role, or score gate. Search systems decide what is worth inspecting; bounded source qualification decides what is credible; the controller decides the next executable question; final evidence selection decides what the answer actually needs.
