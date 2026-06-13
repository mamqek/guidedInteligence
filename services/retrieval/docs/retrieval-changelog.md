# Retrieval Changelog

## Sources Used During This Retrieval Rework

- OrcaLoca: An LLM Agent Framework for Software Issue Localization  
  https://arxiv.org/abs/2502.00350  
  Used for action decomposition, priority scheduling, and pruning after broader exploration.
- CoSIL: Software Issue Localization via LLM-Driven Code Repository Graph Searching  
  https://arxiv.org/abs/2503.22424  
  Used for broad file-level exploration followed by deeper function/snippet analysis with graph-guided search.
- Question Decomposition for Retrieval-Augmented Generation  
  https://arxiv.org/abs/2507.00355  
  Used for per-subquery retrieval, then merge/rerank instead of a single flat candidate pool.
- LocAgent: Graph-Guided LLM Agents for Code Localization  
  https://aclanthology.org/2025.acl-long.426/  
  Used for graph-guided multi-granularity code localization ideas.
- GraphLocator: Graph-guided Causal Reasoning for Issue Localization  
  https://arxiv.org/abs/2512.22469  
  Used for graph-guided expansion from symptom/support files toward likely owner files.
- RepoCoder: Repository-Level Code Completion Through Iterative Retrieval and Generation  
  https://aclanthology.org/2023.emnlp-main.151/  
  Used for the idea that first-pass retrieved code should seed a second retrieval pass with code-native terms.
- On The Importance of Reasoning for Context Retrieval in Repository-Level Code Editing  
  https://arxiv.org/abs/2406.04464  
  Used for the decision to keep deterministic/tool-based sufficiency checks instead of trusting LLM judgment alone.
- SweRank: Software Issue Localization with Code Ranking  
  https://arxiv.org/abs/2505.07849  
  Used for retrieve-then-rerank framing instead of trusting first-pass retrieval alone.
- SaraCoder: Orchestrating Semantic and Structural Cues for Profit-Oriented Repository-Level Code Completion  
  https://arxiv.org/abs/2508.10068  
  Used for diversity-aware reranking so redundant nearby files do not monopolize results.
- GraphER: An Efficient Graph-Based Enrichment and Reranking Method for Retrieval-Augmented Generation  
  https://arxiv.org/abs/2603.24925  
  Used for the idea that graph structure is most helpful as reranking/enrichment after candidate generation.
- Qdrant Documentation  
  https://qdrant.tech/documentation/  
  Used for collection setup, metadata filtering, and search behavior.
- Qdrant Hybrid Search / Query API  
  https://qdrant.tech/articles/hybrid-search/  
  Used for dense+sparse hybrid retrieval design.
- Qdrant Hybrid Search Tutorial  
  https://qdrant.tech/documentation/tutorials/hybrid-search-fastembed/  
  Used for practical hybrid search structure and fusion concepts.
- FAISS official repository  
  https://github.com/facebookresearch/faiss  
  Used during evaluation of local dense retrieval vs Qdrant-backed hybrid retrieval.
- Analytics Vidhya, "Choosing the Right Vector Database for RAG and AI Applications"  
  https://www.analyticsvidhya.com/blog/2026/06/vector-database-comparison/  
  Used for the distinction between fast vector search, filtering, and the cost/quality trade-offs of vector database infrastructure.
- Outcome School, "How does a Reranker work?"  
  https://outcomeschool.com/blog/how-does-a-reranker-work  
  Used for the retrieve-then-rerank framing: broad retrieval first, then a more precise relevance pass over a smaller candidate set.
- Pinecone, "Rerankers and Two-Stage Retrieval"  
  https://www.pinecone.io/learn/series/rag/rerankers/  
  Used for the two-stage retrieval principle: retrieve broadly with a cheaper first-stage system, then rerank only a narrowed candidate set.
- MongoDB, "What are Rerankers?"  
  https://www.mongodb.com/resources/basics/artificial-intelligence/reranking-models  
  Used for the explicit cost warning that rerankers process query-document pairs at query time, so candidate count directly drives latency and token cost.

## 2026-06-13

### Changed

- Added an owner-artifact planning split to Step 2:
  - `surface_context_terms` describe the visible API/directive/error surface,
  - `owner_artifact_terms` describe the deeper rule/parser/validator/emitter/resolver artifact,
  - `owner_subqueries` are preferred for owner search,
  - `support_subqueries` remain bridge/context searches.
- Added generic owner-artifact normalization:
  - phrases like `expression parsing` and `Error parsing expression` can derive `expression parser`,
  - owner path matching now tolerates compact/stemmed file names such as `exp-parser.js` for `expression parser`.
- Added JS/TS relationship expansion:
  - explicit `import`, `export ... from`, `require(...)`, and triple-slash references are scanned,
  - extensionless local references resolve to source files using the importing file's extension first, then common TS/JS/JSON extensions.
- Added a final evidence handoff guard:
  - line-level refs accepted by the latest synthesis decision can be materialized into final evidence when they were accepted by the assessor but missed by bucket selection.

### Verification

- Corrected Vue baseline before this owner-artifact pass:
  - `C:\Programming\guidedInteligence_testcases\vuejs-vue-242\runs\run-20260612T221251Z`
  - oracle files: `src/exp-parser.js`, `test/unit/specs/exp-parser.js`
  - retrieved files: `src/directives/on.js`, `src/text-parser.js`, `src/directive.js`, `src/compiler.js`
  - `overlap_count=0`
  - `coverage_status=partial`
  - `sufficient=False`
  - retrieval tokens: `55638`
- Intermediate Vue owner-artifact runs:
  - `run-20260613T083214Z`: `overlap_count=0`, retrieval tokens `62950`
  - `run-20260613T083720Z`: `overlap_count=0`, retrieval tokens `67826`
  - `run-20260613T084210Z`: internally accepted `src/exp-parser.js:L73-L152`, but final evidence still dropped it; retrieval tokens `51306`
- Final Vue run after accepted-line-ref evidence handoff:
  - `C:\Programming\guidedInteligence_testcases\vuejs-vue-242\runs\run-20260613T084723Z`
  - retrieved files: `src/directives/model.js`, `src/text-parser.js`, `src/emitter.js`, `src/exp-parser.js`, `src/directives/index.js`
  - `overlap_files=["src/exp-parser.js"]`
  - `overlap_count=1`
  - `coverage_status=partial`
  - `sufficient=False`
  - retrieval tokens: `71087`
- TypeScript guard run:
  - `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260613T085108Z`
  - retrieved files: `src/compiler/types.ts`, `src/compiler/scanner.ts`, `src/compiler/diagnosticMessages.json`, `src/compiler/emitter.ts`, `src/compiler/parser.ts`
  - `overlap_count=0`
  - `coverage_status=partial`
  - `sufficient=False`
  - retrieval tokens: `54862`

### Conclusion

- The owner-artifact split plus relationship expansion is directionally useful: the corrected Vue case now reaches and returns the true owner file `src/exp-parser.js`.
- It is not sufficient yet: Vue remains `partial / sufficient=False`, and token cost increased versus the corrected baseline.
- The next fix should reduce surface-role noise after owner-artifact evidence appears, especially noisy `model.js`/`emitter.js` evidence that competes with `exp-parser.js`.

### Changed: Lower-Cost Role Retrieval Restructure

- Intended stage boundary:
  - keep the Step 2 retrieval plan LLM,
  - replace per-role helper-query LLM calls with deterministic role/query packages,
  - replace owner-declaration selector LLM calls with deterministic declaration and lexical span refinement,
  - keep one compact late assessor as the only LLM gate after candidate gathering,
  - let accepted full-file owner artifacts trigger path-scoped local recovery rather than broad follow-up search.
- Expected quality impact:
  - preserve owner-file discovery for Vue (`src/exp-parser.js`),
  - preserve the previously strong TypeScript abstract-class result,
  - reduce noisy surface evidence by making late synthesis see snippets rather than redundant file artifacts.
- Expected token impact:
  - remove helper-query and owner-declaration selector prompt volume,
  - reduce late-assessor prompt size with a compact retrieval intent,
  - target retrieval usage closer to focused manual inspection than the previous 55k-71k runs.
- Known regression risks:
  - deterministic declaration selection can miss cases where only an LLM recognizes the owner declaration,
  - late-assessor decisions can still over-prioritize surface roles,
  - Vue sufficiency remains unstable when diagnostic evidence is found but labeled secondary.
- Comparison method:
  - reran the real `testing\codeRepoQA\run_case.py run-case` pipeline for Vue issue 242 and TypeScript issue 6 after each behavior slice,
  - compared `coverage_status`, `sufficient`, retrieved source files, retrieval LLM call counts, and total retrieval tokens from actual trace usage.

### Verification: Lower-Cost Role Retrieval Restructure

- Deterministic helper-query package:
  - Vue run: `C:\Programming\guidedInteligence_testcases\vuejs-vue-242\runs\run-20260613T093028Z-det-helper`
    - retrieved files: `src/directives/model.js`, `src/text-parser.js`, `src/emitter.js`
    - `coverage_status=partial`, `sufficient=False`
    - retrieval LLM calls/tokens: `23 / 39162`
  - TypeScript run: `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260613T093317Z-det-helper`
    - retrieved files: `src/compiler/types.ts`, `src/compiler/scanner.ts`, `src/compiler/checker.ts`, `src/compiler/diagnosticMessages.json`, `src/compiler/emitter.ts`, `src/compiler/parser.ts`
    - `coverage_status=partial`, `sufficient=False`
    - retrieval LLM calls/tokens: `14 / 46296`
- Snippet-grounded synthesis input:
  - Vue run: `C:\Programming\guidedInteligence_testcases\vuejs-vue-242\runs\run-20260613T093931Z-det-helper-grounded-synth`
    - retrieved files: `src/directives/model.js`, `src/text-parser.js`, `src/directive.js`, `src/emitter.js`
    - `coverage_status=partial`, `sufficient=False`
    - retrieval LLM calls/tokens: `22 / 38473`
  - TypeScript run: `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260613T094427Z-det-helper-grounded-synth`
    - retrieved files: `src/compiler/types.ts`, `src/compiler/scanner.ts`, `src/compiler/checker.ts`, `src/compiler/diagnosticMessages.json`, `src/compiler/emitter.ts`, `src/compiler/parser.ts`
    - `coverage_status=partial`, `sufficient=False`
    - retrieval LLM calls/tokens: `6 / 23575`
- Path-scoped late recovery for accepted file/artifact candidates:
  - Vue run: `C:\Programming\guidedInteligence_testcases\vuejs-vue-242\runs\run-20260613T102835Z-det-helper-file-recovery`
    - retrieved files: `src/directives/model.js`, `src/text-parser.js`, `src/directive.js`, `src/emitter.js`, `src/exp-parser.js`
    - `coverage_status=partial`, `sufficient=False`
    - retrieval LLM calls/tokens: `17 / 43343`
  - TypeScript run: `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260613T103438Z-det-helper-file-recovery`
    - retrieved files: `src/compiler/types.ts`, `src/compiler/scanner.ts`, `src/compiler/checker.ts`, `src/compiler/diagnosticMessages.json`, `src/compiler/emitter.ts`, `src/compiler/parser.ts`
    - `coverage_status=partial`, `sufficient=False`
    - retrieval LLM calls/tokens: `6 / 23745`
- Compact late-assessor intent:
  - Vue run: `C:\Programming\guidedInteligence_testcases\vuejs-vue-242\runs\run-20260613T104358Z-compact-assessor`
    - retrieved files: `src/directives/model.js`, `src/exp-parser.js`, `src/emitter.js`, `src/text-parser.js`
    - `coverage_status=partial`, `sufficient=False`
    - retrieval LLM calls/tokens: `12 / 25634`
  - TypeScript run: `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260613T105041Z-compact-assessor`
    - retrieved files: `src/compiler/types.ts`, `src/compiler/scanner.ts`, `src/compiler/checker.ts`, `src/compiler/diagnosticMessages.json`, `src/compiler/emitter.ts`, `src/compiler/parser.ts`
    - `coverage_status=partial`, `sufficient=False`
    - retrieval LLM calls/tokens: `7 / 22162`
- Deterministic-only declaration selection:
  - Vue run: `C:\Programming\guidedInteligence_testcases\vuejs-vue-242\runs\run-20260613T111911Z-det-decls`
    - retrieved files: `src/directives/model.js`, `src/text-parser.js`, `src/emitter.js`
    - `coverage_status=partial`, `sufficient=False`
    - retrieval LLM calls/tokens: `3 / 16444`
  - TypeScript run: `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260613T113138Z-det-decls`
    - retrieved files: `src/compiler/types.ts`, `src/compiler/scanner.ts`, `src/compiler/checker.ts`, `src/compiler/diagnosticMessages.json`, `src/compiler/emitter.ts`, `src/compiler/parser.ts`
    - `coverage_status=strong`, `sufficient=True`
    - retrieval LLM calls/tokens: `3 / 14709`
- Clearing `file_candidate` metadata from materialized spans:
  - Vue run: `C:\Programming\guidedInteligence_testcases\vuejs-vue-242\runs\run-20260613T210112Z-span-metadata-fix`
    - retrieved files: `src/directives/model.js`, `src/text-parser.js`, `src/exp-parser.js`, `src/emitter.js`, `src/directive.js`
    - `coverage_status=partial`, `sufficient=False`
    - retrieval LLM calls/tokens: `3 / 15780`
  - TypeScript run: `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260613T210938Z-span-metadata-fix`
    - retrieved files: `src/compiler/types.ts`, `src/compiler/scanner.ts`, `src/compiler/checker.ts`, `src/compiler/diagnosticMessages.json`, `src/compiler/emitter.ts`, `src/compiler/parser.ts`
    - `coverage_status=partial`, `sufficient=False`
    - retrieval LLM calls/tokens: `3 / 14389`
- Assessor-accepted required-role snippets can satisfy the deterministic gate:
  - Vue run: `C:\Programming\guidedInteligence_testcases\vuejs-vue-242\runs\run-20260613T211351Z-assessor-strong-gate`
    - retrieved files: `src/directives/model.js`, `src/text-parser.js`, `src/exp-parser.js`, `src/emitter.js`, `src/deps-parser.js`, `src/directive.js`
    - `coverage_status=partial`, `sufficient=False`
    - retrieval LLM calls/tokens: `4 / 25504`
  - TypeScript run: `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260613T211914Z-assessor-strong-gate`
    - retrieved files: `src/compiler/types.ts`, `src/compiler/scanner.ts`, `src/compiler/checker.ts`, `src/compiler/diagnosticMessages.json`, `src/compiler/emitter.ts`, `src/compiler/parser.ts`
    - `coverage_status=strong`, `sufficient=True`
    - retrieval LLM calls/tokens: `3 / 14284`
- Rejected experiment: pre-assessment materialization of accepted full-file candidates into local spans:
  - Vue run: `C:\Programming\guidedInteligence_testcases\vuejs-vue-242\runs\run-20260613T215553Z-assessment-spans`
    - retrieved files: `src/directives/model.js`, `src/text-parser.js`, `src/emitter.js`, `src/compiler.js`, `src/directive.js`, `src/exp-parser.js`, `src/filters.js`, `src/deps-parser.js`
    - `coverage_status=partial`, `sufficient=False`
    - retrieval LLM calls/tokens: `4 / 26030`
  - TypeScript run: `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260613T215857Z-assessment-spans`
    - retrieved files: `src/compiler/types.ts`, `src/compiler/scanner.ts`, `src/compiler/checker.ts`, `src/compiler/diagnosticMessages.json`, `src/compiler/emitter.ts`, `src/compiler/parser.ts`
    - `coverage_status=strong`, `sufficient=True`
    - retrieval LLM calls/tokens: `3 / 14421`
  - conclusion: this experiment was reverted because it made Vue noisier without improving sufficiency.

### Conclusion: Lower-Cost Role Retrieval Restructure

- Kept the low-cost structure through the assessor-strong-gate slice.
- Compared to the high-token 2026-06-13 baseline:
  - Vue: `71087 -> 25504` retrieval tokens while still returning `src/exp-parser.js`; quality remains `partial / sufficient=False`.
  - TypeScript: `54862 -> 14284` retrieval tokens and improves to `strong / sufficient=True`.
- The remaining Vue issue is not broad retrieval volume; the owner file is present. The remaining failure is ranking/sufficiency judgment around the exact directive validation and diagnostics evidence.

## 2026-06-12

### Changed

- Fixed CodeRepoQA verification for cases whose fixing commit is present in issue `events` but not in `fixed_by`.
  - `testing/codeRepoQA/run_case.py` now:
    - still prefers `fixed_by` when present,
    - keeps timestamp-based snapshot resolution when that snapshot is an ancestor of the referenced event commit,
    - falls back to the referenced event commit's parent when no coherent timestamp snapshot exists,
    - builds oracle files from that event commit only when the resolver used `event_commit_parent`.
  - This preserves the TypeScript snapshot path while correcting the Vue issue 242 snapshot/oracle.
- Replaced per-candidate snippet refinement with grouped `(role, file)` refinement in:
  - `services/retrieval/pipeline/refinement.py`
  - `services/retrieval/workspace.py`
- The snippet stage now:
  - accumulates file-local evidence across follow-up hits,
  - builds one compact declaration shortlist per grouped role/file pass,
  - runs owner-declaration selection once per grouped pass,
  - expands declaration and lexical spans locally before validation.
- Tightened grouped declaration extraction and scoring:
  - only real declaration-shaped lines are considered in `.ts/.js` files,
  - `.json` files no longer fabricate declaration candidates,
  - role-shaped names are favored more strongly during grouped shortlist scoring,
  - raw support snippets are no longer carried through unless they stay close to shortlisted declarations.

### Added

- Added `services/retrieval/docs/decisions/grouped_role_file_refinement_pipeline.md` to document:
  - the token/quality problem in the old snippet stage,
  - the grouped role-file refinement design,
  - how iterative mutation is preserved without repeated full declaration prompts.

### Verification

- TypeScript grouped-refinement verification run:
  - `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260612T020815Z`
  - model: `gpt-4.1-mini-2025-04-14`
  - retrieval result: `coverage_status=strong`, `sufficient=True`, `evidence_count=9`
  - retrieval LLM calls: `13`
  - owner-declaration selector calls: `5`
  - retrieval tokens:
    - `prompt_tokens=30270`
    - `completion_tokens=2046`
    - `total_tokens=32316`
  - compared to the previous current version (`run-20260611T142742Z`):
    - `total_tokens=62007 -> 32316`
    - token delta: `-29691`
- TypeScript grouped-refinement repeat runs after the stabilization pass:
  - `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260612T172412Z`
  - `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260612T172630Z`
  - both runs: `coverage_status=strong`, `sufficient=True`, `evidence_count=9`
  - retrieval tokens:
    - `29148`
    - `29004`
  - owner-declaration selector calls:
    - `3`
    - `3`
  - compared to the previous current version (`run-20260611T142742Z`):
    - token deltas: `-32859`, `-33003`
- Experiment: deterministic path-only owner resolution before grouped snippet refinement.
  - attempted shape:
    - rerank required-role buckets by scored owner paths before `_refine_selected_role_buckets(...)`,
    - pick `1-2` owner files per role from the evaluated path pool,
    - seed grouped snippet refinement only from those routed owner files.
  - Vue comparison:
    - baseline: `C:\Programming\guidedInteligence_testcases\vuejs-vue-242\runs\run-20260612T190155Z`
    - experimental: `C:\Programming\guidedInteligence_testcases\vuejs-vue-242\runs\run-20260612T190622Z`
    - result:
      - `coverage_status` stayed `partial`
      - `sufficient` stayed `False`
      - retrieval tokens dropped: `66463 -> 57830`
      - owner-routing fired for all five required roles, but still misrouted role ownership
  - TypeScript regression check:
    - experimental run: `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260612T191029Z`
    - result:
      - `coverage_status=partial`
      - `sufficient=False`
      - retrieval tokens dropped further to `27045`
  - conclusion:
    - cheap path-only owner routing is not safe enough to keep,
    - it can lower token cost, but without function/declaration-level ownership evidence it redirects stable cases onto the wrong files,

    - the live hook was reverted.
- Experiment: declaration-level owner boost during responsibility reranking.
  - attempted shape:
    - extract real declarations from evaluated candidate files,
    - score declaration names and previews against the role and issue terms,
    - add a responsibility-rerank bonus instead of hard-filtering files,
    - let grouped snippet refinement continue from the newly ordered bucket.
  - Vue comparisons:
    - baseline: `C:\Programming\guidedInteligence_testcases\vuejs-vue-242\runs\run-20260612T190155Z`
      - `coverage_status=partial`
      - `sufficient=False`
      - retrieval tokens: `66463`
    - first declaration-boost run: `C:\Programming\guidedInteligence_testcases\vuejs-vue-242\runs\run-20260612T210721Z`
      - `coverage_status=partial`
      - `sufficient=False`
      - retrieval tokens: `66808`
    - tightened declaration-boost run: `C:\Programming\guidedInteligence_testcases\vuejs-vue-242\runs\run-20260612T211138Z`
      - `coverage_status=partial`
      - `sufficient=False`
      - retrieval tokens: `68764`
  - conclusion:
    - declaration-level evidence is the right kind of signal, but a deterministic boost alone is too noisy,
    - body-term matches still over-promote adjacent helpers such as DOM/component utilities,
    - token cost rose without improving sufficiency,
    - the live behavior was disabled.
- Corrected Vue verification rerun after the event-commit oracle fix:
  - run: `C:\Programming\guidedInteligence_testcases\vuejs-vue-242\runs\run-20260612T221251Z`
  - resolution:
    - `strategy=event_commit_parent`
    - `repo_pre_commit=bab4829f0079f0fd6f95eb1700c2e277429495e8`
    - event commit: `e422d959452332862a3ea9d70c58bccc475daccb`
  - oracle files:
    - `src/exp-parser.js`
    - `test/unit/specs/exp-parser.js`
  - retrieved source files:
    - `src/directives/on.js`
    - `src/text-parser.js`
    - `src/directive.js`
    - `src/compiler.js`
  - result:
    - `coverage_status=partial`
    - `sufficient=False`
    - `overlap_count=0`
    - retrieval tokens: `55638`
  - conclusion:
    - previous Vue analysis used the wrong snapshot/oracle,
    - the real Vue failure is missing `src/exp-parser.js` as final evidence,
    - previous codegen/html-parser owner-routing experiments should not be retried as-is.
- TypeScript guard rerun after the verification fix:
  - run: `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260612T221554Z`
  - resolution stayed timestamp-based:
    - `strategy=latest_commit_before_created_at`
    - `repo_pre_commit=455364cf5a2e4f9cece69599475677bb41e2ac36`
  - oracle stayed comment-derived rather than event-commit-derived:
    - `event_commit=False`
    - `oracle_file_count=4`
  - result:
    - `coverage_status=partial`
    - `sufficient=False`
    - retrieval tokens: `53796`
  - conclusion:
    - the verification fix did not move the TypeScript snapshot/oracle onto the event commit,
    - the retrieval result itself remains run-unstable and should be treated separately from this verification fix.

## 2026-06-11

### Added

- Added `services/retrieval/corrected_retrieval_pipeline.md` as a cleaned-up description of the intended retrieval shape: owner-first, snippet-grounded, support-later.
- Added `services/retrieval/corrected_retrieval_pipeline_mapping.md` to map that corrected pipeline back onto the current code paths and current stage boundaries.
- Added LLM-assisted owner-declaration selection inside winning files:
  - `services/retrieval/workspace_llm.py::select_owner_declarations_with_llm(...)`
  - `services/retrieval/pipeline/snippet_level.py::declaration_candidates_for_llm(...)`
  - `services/retrieval/workspace.py::_select_owner_declaration_candidate(...)`

### Changed

- Tightened required-role refinement to behave more like the intended owner-first pipeline instead of broadening all roles equally from the start:
  - required roles are now ranked into focused owner candidates first,
  - supporting expansion is deferred until focused owner grounding is confirmed,
  - weak required buckets are recovered before broad support expansion continues.
- Changed late snippet recovery to search inside accepted owner files first before spending the initial refinement budget on broad global snippet recovery.
- Preserved direct owner snippet candidates during file preparation instead of collapsing them back into file-only state before later refinement.
- Refined owner-file local span selection so deterministic lexical windows now compete with an LLM-picked declaration candidate inside the same file, instead of relying only on broad window scoring.
- Removed one incorrect special case where `validation_checking` reference expansion was allowed to draw from all prepared buckets rather than its own bucket.
- Reduced hardcoded retrieval bias in role-completion scoring:
  - removed the local compiler-shaped keyword/path tables from `services/retrieval/role_completion/scoring.py`,
  - switched that scorer to shared role semantics from `services/retrieval/role_specs.py` instead of per-file TypeScript-specific string lists.
- Improved in-file scoring to weight prompt-specific terms more heavily than generic role vocabulary when choosing a span inside a selected owner file.

### Verification

- Final verified TypeScript case run after the owner-first/snippet-grounding changes:
  - `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260610T232007Z`
  - `coverage_status=strong`
  - `sufficient=True`
  - `evidence_count=8`
- Final required-role evidence in that run:
  - `representation`: `src/compiler/types.ts:L754-L833`, `src/compiler/types.ts:L676-L755`
  - `input_parsing`: `src/compiler/parser.ts:L2174-L2253`
  - `validation_checking`: `src/compiler/checker.ts:L4340-L4419`
  - `diagnostics`: `src/compiler/diagnosticMessages.json:L961-L1040`, `src/compiler/diagnosticMessages.json:L993-L1072`
  - `behavior_output`: `src/compiler/emitter.ts:L529-L608`, `src/compiler/emitter.ts:L518-L597`
- Token usage from the successful retrieval trace with direct OpenAI `gpt-4.1-mini`:
  - `prompt_tokens=34030`
  - `completion_tokens=3368`
  - `total_tokens=37398`

### Cost Tracking

- Current TypeScript retrieval baseline before the new cost-cutting experiments:
  - run: `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260611T084358Z`
  - model: `gpt-4.1-mini-2025-04-14`
  - retrieval result: `coverage_status=strong`, `sufficient=True`, `evidence_count=9`
  - retrieval LLM calls: `72`
  - retrieval tokens:
    - `prompt_tokens=249155`
    - `completion_tokens=6394`
    - `total_tokens=255549`

### Experiment Log

- Experiment 1: cache repeated owner-declaration selections within a single retrieval run.
  - code change:
    - `services/retrieval/workspace.py`
    - added a strict per-run cache for `_select_owner_declaration_candidate(...)`, keyed by the exact LLM selector payload
  - verification run:
    - `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260611T092300Z`
  - measured effect:
    - retrieval LLM calls: `72 -> 57`
    - retrieval tokens: `255549 -> 204113`
    - token delta: `-51436` total retrieval tokens
    - cache hits observed: `32`
  - result quality impact:
    - retrieval result regressed from `coverage_status=strong`, `sufficient=True`
    - to `coverage_status=partial`, `sufficient=False`
  - observed drift:
    - `validation_checking` widened from `src/compiler/checker.ts:L4981-L5060` to `src/compiler/checker.ts:L4355-L4434`
    - `behavior_output` widened from `src/compiler/emitter.ts:L518-L597` to `src/compiler/emitter.ts:L2024-L2103`
    - the cache saved cost, but it also locked repeated in-file declaration picks early enough that later retries no longer had a chance to recover to the tighter snippet choices
- Experiment 2: skip the second late LLM bucket assessment when post-recovery deterministic coverage looked sufficient.
  - code change:
    - `services/retrieval/workspace.py`
    - tried short-circuiting the second `_synthesize_role_buckets(...)` call after weak-role recovery
  - verification run:
    - `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260611T093522Z`
  - measured effect:
    - retrieval LLM role-bucket assessments: `2 -> 3`
    - retrieval tokens: `255549 -> 260590`
    - token delta: `+5041` total retrieval tokens
  - result quality impact:
    - retrieval result regressed from `coverage_status=strong`, `sufficient=True`
    - to `coverage_status=partial`, `sufficient=False`
  - conclusion:
    - this shortcut did not trigger on the intended path because post-recovery deterministic coverage still was not satisfied
    - the run instead drifted into an extra late assessment and ended worse, so this experiment was reverted
- Experiment 3: exact helper-query reuse inside a single run.
  - code change:
    - `services/retrieval/workspace.py`
    - tried caching `generate_role_helper_queries_with_llm(...)` results by exact `(role, query, retrieval-plan payload)` identity
  - verification run:
    - first attempt failed with an OpenAI read timeout and correctly surfaced the runtime error with no fallback
    - successful retry: `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260611T095113Z`
  - measured effect:
    - helper-query cache hits observed: `0`
    - helper-query LLM calls stayed at `5`
    - retrieval result on the retry was `coverage_status=partial`, `sufficient=False`
  - conclusion:
    - on this case, helper-query generation already happens only once per required role, so exact reuse does not activate
    - this experiment does not reduce cost on the current TypeScript path and was reverted
- Experiment 4: shrink owner-declaration LLM shortlist from `18` candidates to `12`.
  - code change:
    - `services/retrieval/pipeline/snippet_level.py`
    - reduced `declaration_candidates_for_llm(..., limit=18)` to `limit=12`
  - verification run:
    - `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260611T100117Z`
  - measured effect:
    - owner-declaration candidate payload: `18 -> 12` per call
    - owner-declaration LLM calls: `64 -> 96`
    - owner-declaration retrieval tokens: `232642 -> 248175`
    - total retrieval tokens: `255549 -> 271705`
  - result quality impact:
    - retrieval result regressed from `coverage_status=strong`, `sufficient=True`
    - to `coverage_status=partial`, `sufficient=False`
  - observed drift:
    - `validation_checking` widened from `src/compiler/checker.ts:L4981-L5060` to `src/compiler/checker.ts:L4355-L4434`
    - `input_parsing` shifted from `src/compiler/parser.ts:L2174-L2253` to `src/compiler/parser.ts:L1928-L2007`
    - `diagnostics` shifted from `src/compiler/diagnosticMessages.json:L969-L1048` and `L989-L1068`
      to `L958-L1037` and `L966-L1045`
  - conclusion:
    - shrinking the shortlist reduced per-call payload but changed the retrieval path enough to trigger more owner-declaration selection calls overall
    - net cost increased and result quality fell, so this experiment was reverted
- Experiment 5: remove explanation text from owner-declaration selection responses and return ids only.
  - code change:
    - `services/retrieval/workspace_llm.py`
    - changed `workspace_owner_declaration_selection` schema from `{id, reason}` to `{id}` only
  - verification run:
    - first attempt failed with an OpenAI read timeout and correctly surfaced the runtime error with no fallback
    - successful retry: `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260611T102023Z`
  - measured effect:
    - owner-declaration completion tokens: `4743 -> 1440`
    - owner-declaration total tokens: `232642 -> 284715`
    - owner-declaration calls: `64 -> 80`
    - total retrieval tokens: `255549 -> 307215`
  - result quality impact:
    - retrieval result regressed from `coverage_status=strong`, `sufficient=True`
    - to `coverage_status=partial`, `sufficient=False`
  - observed drift:
    - `validation_checking` disappeared from final evidence
    - `representation` drifted to `src/compiler/types.ts:L754-L833`
    - `behavior_output` drifted to `src/compiler/emitter.ts:L2077-L2156` and `L2024-L2103`
  - conclusion:
    - even though completion text became cheaper, changing the response contract altered model behavior enough to increase owner-selection retries and worsen final evidence
    - this experiment was reverted
- Experiment 6: skip owner-declaration LLM selection for `behavior_output` and rely on lexical in-file refinement only.
  - code change:
    - `services/retrieval/workspace.py`
    - bypassed `_select_owner_declaration_candidate(...)` for `behavior_output` only
  - motivation:
    - in the strong baseline run, `behavior_output` was the only role where the top lexical declaration matched the LLM first choice in all `16/16` observed calls
  - verification run:
    - `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260611T102907Z`
  - measured effect:
    - skipped owner-selection calls: `16`
    - but owner-declaration LLM calls overall still rose: `64 -> 144`
    - owner-declaration total tokens: `232642 -> 365835`
    - total retrieval tokens: `255549 -> 403528`
  - result quality impact:
    - retrieval result regressed from `coverage_status=strong`, `sufficient=True`
    - to `coverage_status=partial`, `sufficient=False`
  - observed drift:
    - `validation_checking` widened from `src/compiler/checker.ts:L4981-L5060` to `src/compiler/checker.ts:L4355-L4434`
    - `representation` drifted to `src/compiler/types.ts:L754-L833` and `L715-L794`
    - `behavior_output` drifted to broader emitter spans `src/compiler/emitter.ts:L2077-L2156` and `L2026-L2105`
  - conclusion:
    - local lexical agreement on a single role was not enough; removing LLM selection there changed later recovery behavior and made the whole run much more expensive
    - this experiment was reverted

### Structural Conclusion After Experiments 1-6

- The dominant cost remains `workspace_owner_declaration_selection`.
- The repeated experiments show that this stage is path-sensitive: even small local contract or gating changes cause different later refinement loops and often increase total owner-selection calls instead of reducing them.
- A final baseline analysis before further edits showed:
  - exact duplicate owner-selection request shapes do exist, but caching them earlier already harmed recovery quality
  - lexical top-1 agreement with the LLM is weak for most roles:
    - `behavior_output`: lexical top-1 matched the LLM first choice in `16/16` calls
    - `diagnostics`: `10/16`
    - `input_parsing`: `0/16`
    - `representation`: `0/16`
  - lexical and LLM spans almost never coincide directly in the strong run, so a broader lexical prefilter is not justified as a safe micro-optimization
- Practical conclusion:
  - no further small local token-cutting tweak is currently justified by the measured signal
  - the next meaningful reduction in cost requires a larger redesign of repeated owner-file refinement rounds rather than another isolated patch around the current selector

### Structural Redesign Direction

- The measured system flaw is that the current pipeline invokes the expensive owner-declaration selector as a repeated per-candidate operation.
- This violates the two-stage retrieval pattern from the reranking references:
  - the cheap first stage should gather and narrow candidates,
  - the expensive relevance model should run only after candidates are grouped and reduced,
  - reranker cost grows with query-candidate pairs, so repeated per-candidate reranking is the wrong cost shape.
- The redesign target should be:
  - group candidates by `(role, owner_file)` before owner-declaration selection,
  - produce one compact declaration candidate set per role/file,
  - run the LLM selector once per role/file/round rather than once per retrieved candidate,
  - feed selected declaration spans back into the existing role bucket scoring,
  - preserve a deterministic lexical fallback only as first-stage narrowing, not as a replacement for ambiguous reranking.
- This is larger than the previous micro-experiments because it changes where the reranking boundary lives: from candidate-level reranking to grouped role/file reranking.

- Experiment 7: lexical-first owner refinement for high-confidence `input_parsing`.
  - code change:
    - `services/retrieval/workspace.py`
    - moved local lexical span selection before owner-declaration LLM selection
    - skipped the owner-declaration LLM only when `role == "input_parsing"` and lexical score was at least `50.0`
  - motivation:
    - in the strong baseline trace, all `input_parsing` local spans scored above `50`
    - the lexical parser span matched the final accepted parser evidence better than the declaration selector's preferred parser declarations
  - verification run:
    - first attempt failed with an OpenAI read timeout and correctly surfaced the runtime error with no fallback
    - successful retry: `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260611T111834Z`
  - measured effect:
    - skipped owner-selection calls: `32`
    - owner-declaration total tokens: `232642 -> 215234`
    - total retrieval tokens: `255549 -> 239345`
    - token delta: `-16204` total retrieval tokens
  - result quality impact:
    - retrieval result regressed from `coverage_status=strong`, `sufficient=True`
    - to `coverage_status=partial`, `sufficient=False`
  - observed drift:
    - `validation_checking` widened from `src/compiler/checker.ts:L4981-L5060` to `src/compiler/checker.ts:L4355-L4434`
    - `behavior_output` drifted to broader emitter spans `src/compiler/emitter.ts:L2077-L2156` and `L2087-L2166`
  - conclusion:
    - this was the first redesign slice that reduced total retrieval cost materially
    - it still failed the quality gate, showing that local role-specific lexical gating cannot be applied independently without changing later recovery behavior
    - this experiment was reverted
- Experiment 8: scoped owner-declaration selector cache inside one follow-up batch.
  - code change:
    - `services/retrieval/workspace.py`
    - added a cache local to `_run_role_followup_pipeline(...)`, keyed by the exact owner-declaration selector payload
    - the cache reset on every follow-up batch and did not apply to the whole retrieval run
  - motivation:
    - this tested the structural reranking idea from the references more conservatively than Experiment 1:
      - avoid repeated expensive selector calls only inside one grouped follow-up pass
      - do not freeze choices across later recovery rounds
  - verification run:
    - `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260611T113147Z`
  - measured effect:
    - scoped selector cache hits observed: `15`
    - retrieval LLM calls: `72 -> 57`
    - owner-declaration selector calls: `64 -> 49`
    - owner-declaration total tokens: `232642 -> 179249`
    - total retrieval tokens: `255549 -> 201980`
    - token delta: `-53569` total retrieval tokens
  - result quality impact:
    - retrieval result regressed from `coverage_status=strong`, `sufficient=True`
    - to `coverage_status=partial`, `sufficient=False`
  - observed drift:
    - `validation_checking` widened from `src/compiler/checker.ts:L4981-L5060` to `src/compiler/checker.ts:L4355-L4434`
    - final evidence count dropped from `9` to `8`
    - one diagnostics evidence item disappeared
  - conclusion:
    - even a follow-up-local exact cache materially reduces token cost
    - it still changes the final accepted evidence enough to fail sufficiency
    - repeated selector calls are not merely duplicate waste in the current design; they also act as stochastic recovery opportunities
    - this experiment was reverted
- Experiment 9: reuse the first owner-declaration selection for the same file for the rest of the retrieval run.
  - code change:
    - `services/retrieval/pipeline/refinement.py`
    - `services/retrieval/workspace.py`
  - motivation:
    - stop asking the owner-declaration selector more than once for the same file, regardless of later refinement retries
    - test the stronger claim that repeated declaration choice on the same file is pure waste
  - verification run:
    - `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260611T142742Z`
  - measured effect:
    - retrieval LLM calls: `72 -> 20`
    - owner-declaration selector calls: `64 -> 8`
    - owner-declaration same-file cache hits observed: `184`
    - owner-declaration same-file cache misses observed: `8`
    - retrieval tokens:
      - `prompt_tokens=249155 -> 58437`
      - `completion_tokens=6394 -> 3570`
      - `total_tokens=255549 -> 62007`
    - token delta: `-193542` total retrieval tokens
  - result quality impact:
    - retrieval result regressed from `coverage_status=strong`, `sufficient=True`
    - to `coverage_status=partial`, `sufficient=False`
  - observed drift:
    - `validation_checking` widened from `src/compiler/checker.ts:L4981-L5060` to `src/compiler/checker.ts:L4355-L4434`
    - `input_parsing` drifted to weaker spans in both `scanner.ts` and `parser.ts`
    - `behavior_output` drifted from `src/compiler/emitter.ts:L518-L597` to broader emitter spans `L1216-L1295` and `L2054-L2133`
  - conclusion:
    - same-file declaration re-selection is not behaving like redundant waste in the current pipeline
    - freezing the first declaration choice per file collapses token cost dramatically, but it also removes later recovery behavior and fails the quality gate
    - this experiment should not be kept in the current retrieval shape

## 2026-06-08

### Added

- Added a grouped retrieval pipeline package under `services/retrieval/pipeline/`:
  - `constants.py`,
  - `models.py`,
  - `file_level.py`,
  - `snippet_level.py`.

### Changed

- Split shared retrieval state models out of `workspace.py` into `services/retrieval/pipeline/models.py`.
- Split file-level retrieval helpers out of `workspace.py` into `services/retrieval/pipeline/file_level.py`.
- Split snippet-level refinement and snippet-quality helpers out of `workspace.py` into `services/retrieval/pipeline/snippet_level.py`.
- Reduced `services/retrieval/workspace.py` from `4112` lines to `3020` lines by moving the reusable helper families into the new package.
- Renamed the old post-owner `retarget/rescue` method family to cleaner follow-up terminology:
  - `_retarget_role_buckets(...)` -> `_refine_selected_role_buckets(...)`,
  - `_retarget_role_bucket(...)` -> `_refine_selected_role_bucket(...)`,
  - `_retarget_role_rescue_specs(...)` -> `_build_snippet_followup_specs(...)`,
  - `_late_role_rescue_specs(...)` -> `_build_late_recovery_followup_specs(...)`,
  - `_run_role_rescue_pipeline(...)` -> `_run_role_followup_pipeline(...)`.
- Renamed follow-up trace events from `role_rescue_*` to `role_followup_*` to match the new naming.

### Verification

- `python -m py_compile services\retrieval\workspace.py services\retrieval\pipeline\models.py services\retrieval\pipeline\file_level.py services\retrieval\pipeline\snippet_level.py services\retrieval\responsibility.py` passed after the split.
- TypeScript verification run `run-20260608T-pipeline-split-3` completed with `coverage_status=strong` and `sufficient=True`.
- Required-role evidence remained architecture-faithful after the file split:
  - `representation`: `src/compiler/types.ts:L220-L299`,
  - `input_parsing`: `src/compiler/parser.ts:L2319-L2398`,
  - `validation_checking`: `src/compiler/checker.ts:L4984-L5063`,
  - `diagnostics`: `src/compiler/diagnosticMessages.json:L399-L478`,
  - `behavior_output`: `src/compiler/emitter.ts:L1281-L1360`.

## 2026-06-07

### Added

- Added `services/retrieval/file_first_role_resolution_pipeline.md` to document the intended file-first retrieval pipeline.
- Added explicit loop safeguards for repeatable file-role resolution:
  - max one file-resolution round in v1,
  - bounded path-diverse alternates,
  - no repeated assignment states,
  - monotonic-progress requirement,
  - failed-file memory,
  - single-pass conflict repair,
  - role-owner gating before snippet selection,
  - no broad snippet retry before file-role re-resolution.
- Added retry scenarios for:
  - next-best file fallback,
  - cross-role reassignment,
  - weak-role re-resolution,
  - redundancy correction,
  - owner-over-helper retry,
  - snippet-failure-triggered retry,
  - graph-neighborhood retry,
  - role-conflict retry.
- Added trace events for bounded file-role resolution rounds:
  - `file_role_resolution_round_started`,
  - `file_role_resolution_round_completed`.

### Changed

- Refactored first-pass source retrieval to treat Qdrant chunks as file-entry signals rather than immediate snippet evidence.
- Collapsed Qdrant chunk hits into file candidates before responsibility scoring and role ownership selection.
- Reintroduced snippet retargeting only after file-level owner selection, keeping snippet selection downstream of file-role resolution.
- Added role-owner path gating so owner files block adjacent/helper files from satisfying the wrong role:
  - `checker.ts` blocks emitter/parser-style evidence for `validation_checking`,
  - `emitter.ts` blocks parser/service-style evidence for `behavior_output`,
  - `parser.ts` blocks emitter/service-style evidence for `input_parsing`.
- Added cross-role owner-path downvotes in `profile_candidate(...)` so files that look like another role's owner are less likely to satisfy the current role.
- Made role rescue pass focused retarget queries into local in-file refinement, not only into Qdrant snippet search.
- Dropped redundant `FILE` candidates from late feedback, final coverage checks, and final evidence when concrete snippets exist for the same role/path.
- Tightened role-specific snippet targeting around semantic declaration bodies:
  - `NodeFlags` / AST node representation in `types.ts`,
  - modifier parsing in `parser.ts`,
  - `checkClassDeclaration` in `checker.ts`,
  - class/member emission in `emitter.ts`.

### Verification

- `python -m py_compile services\retrieval\workspace.py services\retrieval\responsibility.py` passed after the refactor.
- TypeScript run `run-20260607T-file-first-8` completed with `coverage_status=strong` and `sufficient=True`.
- Final required-role evidence in that run:
  - `representation`: `src/compiler/types.ts:L220-L299`,
  - `input_parsing`: `src/compiler/parser.ts:L2319-L2398`,
  - `validation_checking`: `src/compiler/checker.ts:L4984-L5063`,
  - `diagnostics`: `src/compiler/diagnosticMessages.json:L397-L476`,
  - `behavior_output`: `src/compiler/emitter.ts:L1281-L1360`.
- The previous recurring misalignment was removed in the final run:
  - no `parser.ts` evidence satisfied `behavior_output`,
  - no `emitter.ts` evidence satisfied `validation_checking`,
  - `checker.ts` was selected for `validation_checking`,
  - required final evidence no longer contained `FILE` placeholders.

## 2026-06-06

### Added

- Added Qdrant search-result breakdown logging so retrieval traces can distinguish:
  - sparse-only top hits,
  - dense-only top hits,
  - final hybrid top hits.
- Added snapshot-scoped testcase setup and reuse flow for multi-repo evaluation cases beyond the original TypeScript benchmark.

### Changed

- Switched Qdrant cache flushing to persist partial embedding progress more aggressively during long UVA embedding runs.
- Extended evaluation and inspection workflow to compare cross-repo behavior on:
  - TypeScript abstract class support,
  - Vue directive validation,
  - pandas datetime64 integration.

### Verification

- `python -m unittest tests.test_workspace_retrieval tests.test_coderepoqa_retrieval` passed after the Qdrant breakdown change.
- Breakdown inspection confirmed that some missing-owner files, especially `checker.ts`, were often absent even before hybrid fusion, not merely lost during reranking.

## 2026-06-05

### Added

- Added late weak-role rescue seeding that prioritizes:
  - late follow-up queries first,
  - strong cross-role anchors second,
  - generic fallback snippet queries last.
- Added a reusable `role rescue` pipeline that unifies:
  - in-file retargeting,
  - late weak-role recovery.
- Added role-rescue trace events such as:
  - `role_rescue_started`,
  - `role_rescue_candidates_retrieved`,
  - `role_rescue_candidate_verified`,
  - `role_rescue_completed`.

### Changed

- Late weak-role rescue now performs broad Qdrant search for late follow-up and anchor-derived rescue queries instead of centering recovery on weak current candidates.
- CGC is now used as a verifier around shortlisted rescue candidates rather than as a broad rescue-search driver.
- Late weak-role recovery now avoids expensive CGC expansion for obviously weak supporting buckets and focuses only on stronger required-role anchors.
- Weak-role replacement became stricter so enforcement-heavy rescue hits can replace binder/types-style provisional snippets more decisively.

### Verification

- `python -m unittest tests.test_workspace_retrieval tests.test_coderepoqa_retrieval` passed after the rescue-pipeline refactor.
- TypeScript rescue traces showed improved parser retargeting, but `validation_checking` still struggled to pivot from adjacent files to `checker.ts`.

## 2026-06-04

### Added

- Added mandatory local Qdrant-backed hybrid retrieval as the active source-code backend.
- Added UVA-proxy embedding support with `text-embedding-3-large`.
- Added local Qdrant Docker setup and operational docs in:
  - `docker-compose.qdrant.yml`,
  - `services/retrieval/qdrant_hybrid_design.md`.
- Added hard-required indexing control through `RETRIEVAL_ENABLE_INDEXING`.
- Added local embedding cache persistence, chunk-signature reuse, and Qdrant sync-manifest reuse across runs.
- Added bounded embedding concurrency and embedding batch-size controls for the UVA embedding endpoint.
- Added declaration-aware chunking to reduce oversize embedding inputs and improve coherence of retrievable spans.
- Added role-status-aware retrieval state:
  - `retrieved_candidates`,
  - `accepted_candidates`,
  - `satisfying_refs`,
  - `role_status`.
- Added late-assessment-driven downgrade so accepted snippets no longer automatically imply that a role is satisfied.
- Added one bounded Qdrant recovery pass for weak required roles.

### Changed

- Replaced the old BM25-first active retrieval backend with Qdrant hybrid retrieval while keeping CGC as a separate structural layer.
- Reused existing CGC and Qdrant index state when chunk signatures matched instead of rebuilding every run.
- Reduced fresh indexing cost by:
  - skipping obvious garbage/generated content,
  - reusing cached embeddings,
  - using bounded in-flight embedding requests,
  - tuning embedding batch sizes empirically against the UVA proxy.
- Final evidence selection now uses `satisfying_refs` rather than every accepted candidate.
- Noise snippets from late LLM assessment are explicitly excluded from satisfying a role.

### Removed

- Removed fallback logic from the active retrieval path: Qdrant became a hard requirement for source-code retrieval.

### Verification

- `python -m unittest tests.test_workspace_retrieval tests.test_coderepoqa_retrieval` passed repeatedly during the Qdrant migration and role-status alignment work.
- Empirical embedding throughput checks showed that larger batches materially improved cold-index speed on the UVA endpoint, while warm-cache/index-reuse runs became practical.
- Multi-repo evaluation was exercised on:
  - TypeScript,
  - Vue,
  - pandas,
  with cached index reuse and role-aware traces.

## 2026-06-07

### Added

- Added general local in-file refinement after file selection. The scorer uses the selected file path, retrieval role, role query, helper queries, retrieval terms, prompt evidence, and declaration anchors to choose a better span inside large files.
- Added `local_in_file_refinement` as a retrieval path for spans selected by deterministic in-file scoring.
- Added salient excerpt generation for late LLM assessment so long spans are compacted around relevant declarations instead of blindly truncating from the first line.
- Added `RETRIEVAL_LLM_CONTINUITY_ENABLED` in `.env` and `.env.example`.
- Added experimental process-local LLM continuity for Chat Completions-compatible APIs. When enabled, the next LLM call receives only the previous compact JSON retrieval result as orientation, not full file content.
- Added role-scoped handling for trusted Obsidian file hints. Note-derived file hints are now kept in retrieval-plan metadata and applied only to matching roles, instead of being promoted to global confirmed file hints.
- Added focused regression coverage for:
  - continuity env parsing,
  - local in-file refinement preferring role-specific declaration spans,
  - Obsidian checker hints helping `validation_checking` without globally narrowing unrelated roles,
  - existing CodeRepoQA retrieval expectations.

### Changed

- Direct owner file fallback now delegates span choice to the same general in-file scorer before falling back to the older broad window logic.
- In-file refinement now lets deterministic local file scoring compete with Qdrant in-file snippet refinement.
- Late assessment sees declaration-centered excerpts for retrieved candidates, improving judgment on spans where the useful function starts after a few setup lines.
- Obsidian is now treated as an additive source of truth. If notes only point to `src/compiler/checker.ts`, parser/emitter/diagnostic role retrieval still runs against the normal code pipeline.

### Removed

- No retrieval subsystem was removed. The older broad direct-owner window selection remains as fallback only; it is no longer the primary span choice when the local in-file scorer can identify a stronger window.

### Verification

- `python -m unittest tests.test_workspace_retrieval tests.test_coderepoqa_retrieval` passed.
- Role-scoped Obsidian regression tests passed:
  - `python -m unittest tests.test_workspace_retrieval.WorkspaceRetrievalStageTests.test_obsidian_source_truth_guides_retrieval_to_checker tests.test_workspace_retrieval.WorkspaceRetrievalStageTests.test_obsidian_file_hints_are_role_scoped_not_global_narrowing`
- Full retrieval test set passed after the role-scoped hint change:
  - `python -m unittest tests.test_workspace_retrieval tests.test_coderepoqa_retrieval`
- Obsidian role-scoped TypeScript case run:
  - default Qdrant collection was stale on this machine (`1128` points for a `20653` document BM25 index), so verification used a fresh temporary collection.
  - two attempts hit upstream LLM proxy HTTP 500s during late synthesis; retry succeeded at `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260607T-obsidian-role-scoped-fresh-env-retry2`.
  - retrieval plan had `confirmed_file_hints: []` and metadata `trusted_local_note_file_hints: ["src/compiler/checker.ts"]`.
  - role buckets were not globally narrowed: `input_parsing` retrieved parser spans and `behavior_output` retrieved emitter/tc spans.
  - final selected evidence was still partial: representation (`types.ts`), validation checking (`checker.ts`), and diagnostics (`diagnosticMessages.json`) were selected; input parsing and behavior output remained missing after late assessment.
- Continuity-off TypeScript case run:
  - `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260607T-continuity-off-refined-salient`
  - selected `src/compiler/checker.ts:L4979-L5058`
  - retrieval path `local_in_file_refinement`
  - late assessment marked the snippet `core` for `validation_checking`.
- Continuity-on TypeScript case run:
  - first final attempt hit an upstream proxy HTTP 500 from the LLM provider.
  - retry succeeded at `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260607T-continuity-on-refined-salient-retry`
  - selected `src/compiler/checker.ts:L4992-L5071`
  - retrieval path `local_in_file_refinement`
  - late assessment marked the snippet `core` for `validation_checking`.
- Final `.env` state has `RETRIEVAL_LLM_CONTINUITY_ENABLED=false`.
