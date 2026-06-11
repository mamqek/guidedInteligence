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
