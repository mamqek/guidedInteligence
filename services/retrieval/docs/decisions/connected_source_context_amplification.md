# Connected Source Context Amplification

## Purpose

This note plans how connected sources should support retrieval beyond simply becoming extra evidence
candidates.

The main goal is to use GitHub, Notion, Shortcut, Jira, Obsidian, Slack, Google Drive, and similar
text sources as live context that helps the system understand the user prompt, generate better
code-search queries, and support the final explanation with non-code evidence when useful.

## Current Behavior

Connected sources are currently retrieved early and normalized into `ConnectedSourceDocument` records.

They can:

- be fetched from enabled connectors during a run,
- be score-filtered or enriched by the connector adapter,
- be passed into retrieval planning,
- be selected directly as final evidence,
- appear in traces and `evidence-items.json` when selected.

They do not yet consistently act as a structured query-planning layer. The system does not explicitly
turn connected-source results into file hints, feature names, product terms, issue IDs, acceptance
criteria, or likely code areas before code retrieval.

## Decision

Proceed first with a bounded LangGraph connected-source controller and lightweight reranking.

The controller should be a retrieval-only stage inside the existing API pipeline. It should not own
the whole retrieval system and should not generate the final answer.

Use Haystack only as a measured prototype if current ranking remains weak. Use HippoRAG later only if
measured failures show that live retrieval plus a connected-source cache cannot connect fragmented
project context well enough.

## Intended Retrieval Shape

Connected sources should become a live context amplification layer before code retrieval. The first
implementation should not require a prebuilt connected-source cache.

```text
user prompt
  -> prompt anchors and initial intent
  -> bounded LangGraph connected-source controller
      -> plan provider-specific live queries
      -> call selected connectors
      -> rerank and filter connected results
      -> emit structured code-retrieval hints
  -> improved code retrieval plan and subqueries
  -> code retrieval
  -> final evidence selection
  -> answer with code evidence plus selected connected-source support
```

The connected-source controller should not replace code retrieval. It should make code retrieval more
aligned and keep connected-source evidence available for final citation when useful.

Examples:

- A GitHub issue can reveal the feature name, bug reproduction, labels, or files mentioned by
  maintainers.
- A Shortcut story can reveal product intent and acceptance criteria.
- A Notion page can explain the architecture or terminology behind the prompt.
- An Obsidian note can point to local design history or module names.
- Slack can reveal informal decisions or recent context.
- Google Drive or Confluence can provide product docs that explain why code behavior matters.

## LangGraph Controller Contract

Use LangGraph as a bounded, retrieval-only controller for live connected sources.

The controller must return a structured result:

- connector queries issued per `source_key`,
- normalized connected documents that survived filtering,
- mentioned files, paths, modules, packages, commands, classes, functions, and symbols,
- product terms, feature names, issue keys, PR numbers, and URLs,
- user-facing behavior, acceptance criteria, errors, stack traces, logs, or reproduction steps,
- likely code areas and suggested code-search subqueries,
- source provenance for each signal,
- skipped sources with reasons,
- uncertainty or conflict notes when sources disagree.

The output should be compact. It should guide code retrieval, not become a large context dump.

The graph should be bounded:

- maximum one planning step for the first version,
- maximum one live query per selected source for the first version,
- configurable total connector-call limit,
- no final-answer generation,
- explicit timeout and per-provider failure isolation,
- deterministic fallback behavior when a provider fails: keep the run going and record the failure.

Preferred node shape:

```text
PromptAnalysisNode
  -> ConnectorQueryPlanningNode
  -> LiveConnectorCallNode
  -> ConnectedResultRerankNode
  -> CodeRetrievalHintNode
```

The graph output should feed the existing retrieval planner through a typed boundary such as:

```python
ConnectedSourceContextStage.run(...) -> ConnectedSourceContextResult
```

This boundary matters more than LangGraph itself. It lets us keep the current API, code retrieval,
snippet selection, evidence selection, and response-generation payload intact.

## Explicit Incorporation Decisions

The implementation order is fixed as follows:

```text
deterministic prompt evidence
  -> bounded LangGraph connected-source stage
  -> repository context seeded by prompt evidence plus graph hints
  -> existing Step 2 LLM retrieval planner
  -> existing code retrieval and snippet selection
  -> explicit connected-document evidence selection
  -> response generation
```

The graph does not add a second general-purpose prompt-analysis LLM. It consumes the existing
deterministic prompt evidence so prompt parsing has one owner. The graph's LLM work is limited to
provider query planning and one structured result-analysis pass.

`source_code` and `repo_docs` remain downstream retrieval targets and are not called by the
connected-source graph. The first graph implementation can call live or contextual sources such as
GitHub, Notion, Shortcut, Jira, Confluence, Linear, Slack, Google Drive, Obsidian/local notes, and
NotebookLM when they are configured, enabled, and selected for the run.

The existing synchronous server API remains unchanged. The graph is invoked synchronously from the
retrieval worker, while independent provider calls fan out concurrently inside a bounded connector
node. The first version has:

- one query plan per selected connected source,
- one initial search call per selected connected source,
- no recursive agent loop,
- no LangGraph checkpoint store,
- a configurable total call budget,
- per-provider timeouts and a total connected-stage deadline.

LangGraph is justified here by typed state, conditional provider routing, parallel fan-out, and a
clear future boundary for one bounded follow-up query. If the implementation becomes a permanently
linear sequence without conditional routing, it should be simplified rather than retaining
LangGraph only as ceremony.

### Graph State

The graph state must contain only serializable retrieval data:

- raw prompt and conversation identifiers,
- deterministic prompt anchors and file/symbol hints,
- selected connected `source_key` values,
- provider query plans,
- normalized connector documents,
- provider failures and skipped-source reasons,
- reranking and extraction result,
- timing and token-use metadata.

OAuth tokens, API keys, MCP sessions, adapter instances, and file handles must not be copied into
graph state. Existing connector adapters remain responsible for transport and authentication.

### Typed Result

`ConnectedSourceContextResult` must separate these concerns:

- `queries`: the query issued for each `source_key`,
- `documents`: normalized documents returned by connectors,
- `ranked_documents`: relevance decisions with score, reason, and `source_id`,
- `selected_context_ids`: documents allowed to influence code retrieval,
- `selected_evidence_ids`: documents eligible for final evidence,
- `retrieval_terms`: compact feature, product, behavior, and error terms,
- `file_hints`: mentioned or inferred repository-relative paths,
- `symbol_hints`: classes, functions, methods, commands, and package names,
- `suggested_subqueries`: natural code-search questions rather than keyword piles,
- `facts`: contextual claims with supporting `source_id` values,
- `conflicts`: incompatible or stale claims that must not silently guide retrieval,
- `failures` and `skipped_sources`: explicit provider outcomes,
- `usage`: graph LLM token accounting and connector timing.

Every extracted signal must preserve source provenance. Signals without a supporting `source_id`
must not be accepted as connected-source guidance.

### Reranking And Extraction

Provider scores are optional and are not comparable across providers. They may be supplied to the
result-analysis node as metadata, but they are not the final cross-provider rank.

The first version uses one bounded structured LLM call over the normalized candidate set to:

1. reject irrelevant or merely lexical matches,
2. rank the surviving documents against the user's actual information need,
3. extract compact code-retrieval hints,
4. identify which documents are suitable as contextual evidence,
5. record conflicts or uncertainty.

The candidate input is capped by both per-source and global document/character limits. The LLM must
return document IDs from the supplied candidate set; invented IDs or unsupported signals fail
validation. There is no hardcoded semantic reranker standing in for a failed LLM call.

### Evidence Selection

Connected-document evidence selection must use explicit `selected_evidence_ids`. Broad
`SourceCategory` priorities must not append every document from a category after graph filtering.

Documents rejected by the graph:

- do not influence repository context or code subqueries,
- are not appended to final evidence,
- remain visible only in traces as rejected connector candidates.

Documents selected for context may influence code retrieval without automatically becoming final
evidence. Documents selected as evidence remain subject to the global evidence limit and retain
`retrieval_path=connected_source`, `source_key`, provider, and original source ID metadata.

### Failure Semantics

- One provider search or fetch failure is isolated, traced, and does not fail unrelated retrieval.
- If every selected connected provider fails, code retrieval continues without connected context and
  records that the connected stage produced no context.
- Query-planning or result-analysis LLM failure fails the retrieval run explicitly when that LLM node
  was required. It must not be replaced by a deterministic semantic surrogate.
- Empty or irrelevant provider results are successful empty outcomes, not failures.
- Remote content is untrusted data. It is delimited as source material, cannot issue instructions to
  the graph, and can influence output only through the validated structured schema.

### Dependency And Packaging

LangGraph is installed in the repository-local `.venv` and pinned in a repository Python dependency
manifest. A clean environment must be able to install the same graph runtime without relying on a
global Python installation.

## Connector Structure

The connector model should be provider/source-key native. Avoid broad source-category routing such as
`issue_tracker` or `documentation` for live execution decisions.

Each runnable source should have a stable `source_key` and provider-specific adapter:

- `github_issues`
- `github_pull_requests`
- `notion`
- `shortcut`
- `jira`
- `confluence`
- `linear`
- `slack`
- `google_drive`
- `local_notes`
- `notebooklm`
- `repo_docs`
- `source_code`

LangGraph should call sources by `source_key`, not by shared category. If the current connector
structure forces category-to-provider mappings, prefer rewriting that part cleanly rather than
preserving confusing mappings. `SourceCategory` can remain as legacy/internal evidence metadata, but
it should not decide which live provider runs.

The controller should receive only sources that pass both layers:

1. enabled in Connections,
2. checked in the current run panel.

## Integration With Prompt Processing

The early prompt-processing stage should combine:

- direct prompt anchors,
- conversation state,
- connected-source controller signals,
- source-specific metadata such as issue labels, PR state, Notion parent page, Shortcut workflow
  state, or Slack channel.

Then code retrieval should use this combined context to produce better role/subquery plans.

Expected effects:

- fewer generic code searches,
- better first-pass file narrowing,
- more useful follow-up queries,
- final explanations that can cite both implementation evidence and product/decision evidence.

## Evidence Boundary

Connected-source context should influence search, but final answers must still show where evidence
came from.

For code questions:

- code evidence remains required for implementation claims,
- connected-source evidence can explain intent, history, constraints, and why the code matters,
- selected connected-source snippets should be kept as explicit evidence with
  `retrieval_path=connected_source`.

Unselected connected-source results should not enter the final answer prompt except through compact
structured signals used to guide retrieval.

## Reranking

Connected-source results should be reranked before becoming code-retrieval hints or final evidence
candidates.

Initial reranking can stay simple:

- exact anchor matches from the prompt,
- source-key priority based on prompt intent,
- recency when timestamps exist,
- provider score when available,
- overlap with code symbols, files, issue IDs, and feature terms.

This first reranker is not expected to be excellent. It is a measured baseline. If hardcoded role terms
or simple overlap rules are unstable, replace this node with a model-based reranker or a framework
component behind the same `ConnectedResultRerankNode` boundary.

## Haystack Question

Haystack may be useful if we want a retrieval-component framework with rankers, document stores, and
pipeline nodes. It should not be assumed better than the current pipeline without measurement.

Do not rewrite the whole retrieval pipeline into Haystack only because it has reranking components.
Concrete proof required before centralizing retrieval around Haystack:

- same benchmark prompts run through the current pipeline and the Haystack prototype,
- better first-pass file narrowing,
- equal or better `coverage_status` and `sufficient`,
- stable final evidence quality,
- acceptable latency and retrieval-token cost,
- clear reduction in custom ranking code or trace complexity.

Haystack is a reasonable experiment behind the same connected-source stage boundary. It is not the
current preferred central architecture because our pipeline already has product-specific pieces:
workspace source selection, MCP auth/config, code evidence rules, explanation payload shaping, and
retrieval traces.

## HippoRAG And Cache-Based Graph Retrieval

HippoRAG could be useful later, but it belongs after a normalized connected-source cache exists.

The problem HippoRAG may solve is not provider access. MCP already handles provider access. HippoRAG
may help connect fragmented text across sources:

```text
Shortcut story -> GitHub PR -> Notion decision -> Slack discussion -> code file
```

This is valuable when simple keyword/hybrid search misses relationships because each source uses
different wording.

Do not put HippoRAG directly in the live connector path first. Instead:

1. Build the live LangGraph connected-source controller.
2. Measure whether live controller signals improve code retrieval.
3. Add a normalized connected-source cache only for sources where repetition, latency, or cross-source
   relationship discovery justifies it.
4. If live retrieval plus structured signals still misses cross-source links, build a HippoRAG-backed
   graph over cached connected documents.

Preferred future shape:

```text
MCP live connectors
  -> normalized connected documents
  -> bounded LangGraph connected-source controller
  -> structured code-retrieval hints
  -> optional connected-source cache
  -> optional HippoRAG graph over cached text
  -> code retrieval planning
```

## Research References

These references inform the design, but they are not direct implementation dependencies.

- FLARE / Active RAG: https://arxiv.org/abs/2305.06983
  - Relevant idea: retrieve during generation based on what the model needs next.
  - Useful phrase: active RAG decides "when and what to retrieve".
- Iter-RetGen: https://arxiv.org/abs/2305.15294
  - Relevant idea: use generated intermediate output to drive the next retrieval step.
  - Useful phrase: retrieved knowledge helps generate a better output in the next iteration.
- Adaptive RAG / RAGate: https://arxiv.org/abs/2407.21712
  - Relevant idea: predict whether retrieval is needed instead of always retrieving.
  - Useful phrase: generation confidence correlates with relevance of augmented knowledge.
- KiRAG: https://arxiv.org/abs/2502.18397
  - Relevant idea: iterative RAG should adapt to evolving information needs.
- HippoRAG: https://arxiv.org/abs/2405.14831
  - Relevant idea: use LLM-extracted knowledge graphs and Personalized PageRank for multi-hop
    retrieval over an indexed corpus.
- HippoRAG 2: https://arxiv.org/abs/2502.14802
  - Relevant idea: query-to-triple and LLM filtering can improve graph retrieval, but the method
    still assumes an offline graph/index.
- GraphRAG: https://arxiv.org/html/2404.16130
  - Relevant idea: graph indexing and community summaries help with global corpus questions, but
    require batch indexing.
- RAPTOR: https://arxiv.org/abs/2401.18059
  - Relevant idea: recursively cluster and summarize chunks to retrieve at multiple abstraction
    levels over a stable corpus.

## Expected Quality Impact

Positive impact:

- better alignment between user prompt and code retrieval,
- more grounded explanations of intent and design context,
- improved handling of prompts that mention product terms instead of code symbols,
- stronger answers for "why was this built" or "what does this ticket mean in code" questions.

Regression risks:

- noisy connected-source text could steer code retrieval away from the right files,
- too many connected documents or graph loops could increase tokens and planning latency,
- stale external context could conflict with current code,
- provider search can return irrelevant results if the prompt is broad,
- agentic planning can become unstable if prompts and output schemas are loose.

Mitigations:

- keep connector and graph-step limits small,
- emit compact structured signals,
- preserve source provenance,
- prefer exact anchors and recent/project-scoped items,
- require code evidence for code-behavior claims,
- trace called sources, skipped sources, and reranking decisions.

## Implementation Plan

1. Add a `ConnectedSourceContextStage` boundary after deterministic prompt evidence and before
   repository-context construction.
2. Implement a bounded LangGraph graph with provider/source-key native routing and concurrent calls
   through the existing connector adapters.
3. Replace raw connected-document injection into Step 2 with validated structured hints plus only the
   selected compact document excerpts.
4. Seed repository-context construction with graph terms, file hints, symbols, and suggested
   subqueries.
5. Replace category-based connected evidence appending with explicit selected document IDs.
6. Update traces to record queries, called and skipped sources, provider failures, candidate and
   selected IDs, extracted signals, conflicts, LLM usage, and which signals influenced code queries.
7. Keep the architecture provider-agnostic for every configured connector. Restrict the first real
   external-source evaluation to GitHub issues, GitHub pull requests, and Obsidian because those are
   the writable test sources currently available.
8. Add a normalized connected-source cache only after live retrieval is useful but repetitive or too
   slow.
9. Revisit HippoRAG only after cache and live-controller metrics show that cross-source relationships
   are still being missed.

## Initial Experiment Matrix

Use the Microsoft TypeScript CodeRepoQA case as the first measured benchmark.

1. Run with code/default local retrieval only to prove that the new stage is inert when no connected
   source is selected.
2. Enable GitHub and Obsidian with unhelpful or only broadly related text and verify that the graph
   rejects it instead of steering code retrieval.
3. Add natural, human-readable GitHub issue/PR and Obsidian notes that contain general architectural
   context without directly naming the answer files or presenting keyword lists.
4. Repeat with several variants: product terminology, behavior/reproduction context, implementation
   history, and a partially misleading or stale hint.
5. Compare selected connected IDs, generated retrieval terms/subqueries, first-pass files, final code
   evidence, `coverage_status`, `sufficient`, retrieval tokens, connected-stage tokens, and latency.

Experimental source text must read like material written for another human. Do not seed keyword
lists, exact expected answer paths, or artificial instructions to the retriever.

## Measurement Plan

Compare real runs before and after the LangGraph controller.

Track:

- retrieval token totals,
- number and quality of first-pass code files,
- whether connected-source evidence was selected,
- whether code evidence still satisfies required coverage,
- final answer sufficiency,
- called sources and skipped-source reasons,
- cases where connected-source hints improved or harmed retrieval.

Benchmark prompts should include:

- prompt mentions only a product feature name,
- prompt references a GitHub/Shortcut issue,
- prompt asks why a code path exists,
- prompt needs a Notion/Obsidian decision plus code evidence,
- prompt has noisy or irrelevant connected-source matches.

## Non-Goals

- Do not crawl all provider data during a request.
- Do not let connected-source text replace code evidence for code claims.
- Do not require HippoRAG for the first version.
- Do not require Haystack for the first version.
- Do not let LangGraph generate the final answer.
- Do not pass large raw connector payloads directly into final answer generation.
- Do not hide source provenance inside a summary.

## Implementation Status

Implemented as a bounded LangGraph stage in `services/retrieval/connected_context.py`.

The graph has three stage boundaries:

1. plan provider-specific searches from the prompt and deterministic prompt evidence,
2. call enabled connector adapters concurrently with global source, call, result, character, and
   timeout limits,
3. classify normalized results and emit validated retrieval signals plus explicit context/evidence
   document IDs.

The graph is request-local and has no checkpoint or persistent agent memory. An empty connected-source
set is inert and makes no graph LLM call. Provider failures are isolated, while graph LLM failures are
surfaced explicitly in accordance with the repository LLM failure policy. Only IDs returned by a
connector can be selected. Terminology-only, uncertain, stale, or low-confidence results cannot steer
code retrieval or become evidence. At most four documents can affect context and at most two can become
final connected evidence.

The implementation remains provider-independent. The first live evaluation exercised GitHub issues,
GitHub pull requests, and local Obsidian notes; all other configured connectors enter through the same
`ConnectedSourceHandle` boundary.

## Measured TypeScript Experiment

Benchmark prompt: `Explain where abstract class parsing and validation happen.`

Workspace: Microsoft TypeScript CodeRepoQA snapshot
`C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\s\455364cf5a2e`.

All successful comparison runs finished with `coverage_status=strong` and `sufficient=true`. Retrieval
tokens are the sum of real LLM usage recorded in `retrieval-trace.jsonl`.

| Case | Run ID | Connected selection | Retrieval tokens | Graph tokens | Final evidence |
| --- | --- | --- | ---: | ---: | ---: |
| Baseline 1 | `run-20260620T194600Z-87c934b6` | none; stage inert | 11,452 | 0 | 10 |
| Baseline 2 | `run-20260620T195057Z-0c1b15b4` | none; stage inert | 11,470 | 0 | 10 |
| Irrelevant sources, corrected gate | `run-20260620T195721Z-8ad9b1a0` | none | 14,011 | 2,151 | 10 |
| Helpful Obsidian note | `run-20260620T200036Z-2b26f442` | Obsidian | 14,538 | 2,064 | 11 |
| Helpful GitHub issue | `run-20260620T201944Z-aedc6d1e` | issue | 14,533 | 2,058 | 11 |
| PR title lacked search overlap | `run-20260620T202316Z-62dc60bf` | none | 14,178 | 2,170 | 10 |
| Helpful GitHub PR after natural title edit | `run-20260620T202607Z-7e793a03` | PR | 14,848 | 2,442 | 11 |
| Stale/conflicting note, corrected gate | `run-20260620T204228Z-b6abc84f` | none | 13,995 | 2,510 | 10 |
| Combined helpful sources, final caps | `run-20260620T205158Z-4d193726` | issue + PR evidence; all three for context | 15,439 | 2,600 | 12 |

The same five code paths survived every successful comparison:

- `src/compiler/checker.ts`
- `src/compiler/diagnosticMessages.json`
- `src/compiler/emitter.ts`
- `src/compiler/parser.ts`
- `src/compiler/types.ts`

The connected context made Step 2's plan more specific about modifier recognition, semantic legality,
instantiation, and unresolved inherited members. It did not improve the final code-file set for this
already code-specific prompt. Compared with the two-run baseline average of 11,461 retrieval tokens, a
single useful source cost about 27% more retrieval tokens; the final combined run cost about 35% more.
That makes querying every connector unjustified when the prompt already gives strong code terminology.

## Failed Iterations And Corrections

- `run-20260620T195407Z-6ee8d055` initially accepted a generic GitHub issue and an Obsidian note that
  merely shared terminology. This led to the contribution-type and code-signal gate.
- `run-20260620T200440Z-0c8a63bc` failed during graph result analysis because the LLM request timed out.
  The run failed explicitly; no deterministic substitute was used. The retry succeeded.
- `run-20260620T202931Z-607b47f1` initially accepted a stale Obsidian statement alongside a PR. This led
  to the currentness and confidence gate; the corrected conflict run selected neither source.
- The initial PR title did not match GitHub's generated AND query. A natural title containing the actual
  subject made it discoverable without adding answer paths, function names, or keyword lists.

## Hint Findings

Useful connected-source text is ordinary prose that adds one or more of:

- an observable behavior or reproduction condition,
- a responsibility or phase boundary,
- design rationale or implementation history,
- a distinction between similarly named concepts,
- current project intent with clear confidence and recency.

Weak or unsafe text includes terminology-only notes, keyword piles, unqualified stale claims, and titles
with no vocabulary overlap with provider search. Exact file paths and function names are not required;
the helpful fixtures used conversational descriptions. The most important next optimization is an
adaptive pre-query gate so already-specific prompts do not pay roughly 2,000-2,600 graph tokens merely
to reject connected results.
