# Retrieval Changelog

## 2026-08-11

### Direction-Neutral Provenance And Protected Owner Pool

- Productive one-hop callers and callees now receive equal structural provenance strength. Edge direction remains visible to final responsibility assessment but no longer acts as a universal downstream-is-better prior. This direction change is independent and remains enabled even if the pool is later removed, per explicit user instruction.
- Added a request-level protected pool containing `implementation` files from the top 12 hybrid results of any initial repository obligation, capped at 24. Protected files retain a grounded candidate despite weak generated-proposition overlap. One representative per protected file is allocated before the remaining positions are filled from the existing connected-component shortlist; the total TypeScript final request remained 24 candidates.
- `run-20260811T173906Z`: 19 protected files; `builder.ts` entered the pool and final request as exact `isChangedSignagure`, was selected, and produced one implementation Oracle overlap. Result was `partial/false`, retrieval LLM usage was 15,257 tokens, and index reuse reported `rebuilt=false`.
- Unchanged repeat `run-20260811T174132Z`: the 24-file pool contained both builder files and both reached the final request; `builderState.ts:updateExportedModules` was selected, again producing one implementation Oracle overlap. Result was `partial/false`, retrieval LLM usage was 19,037 tokens, and index reuse reported `rebuilt=false`.
- This improves the immediately preceding backend-scope-only pair from zero/zero to one/one Oracle overlap, so the pool remains enabled. It does not yet stabilize which builder owner is selected and increased retrieval tokens by 4,799/7,420 relative to that pair. Focused verification covers direction parity, deterministic pool construction, request-level representative allocation, and the unchanged global candidate bound.

### Matched Candidate-Survival Audit

- Extended the eight-run offline audit from aggregate feature means to a same-run candidate survival test. Without using Oracle labels in the policy, the union of `implementation` files appearing within the top 12 hybrid results of any initial obligation retained every causal source-owner Oracle file in all eight runs.
- The protected pool contained only 12-22 files per run: `src/exp-parser.js`, Vue's server `dom-props.js`, both TypeScript builder files, and `pandas/core/series.py` all survived in both repetitions. Test Oracle files are intentionally outside this owner guarantee because they validate behavior rather than own the mutation mechanism.
- The remaining loss is caused by allocating four nodes from one winning connected component per obligation. Newer TypeScript traces show builder and builder-state functions directly adjacent to semantic seeds, frequently as upstream callers. The current provenance order favors visible downstream `graph_direct_target` nodes over upstream `graph_neighbor` owners, so edge orientation and component size can erase the causal owner before the LLM sees it.
- The next implementation experiment should therefore protect the measured request-level file pool before component ranking, allocate one exact executable representative per protected file within a 24-file cap, and only then ask for a joint producer/state-owner/consumer selection. This changes survival/allocation, not evidence acceptance. The reproducible table is in `offline-shortlist-signal-audit.md`.

### Stable Obligation Query Strand Experiment

- Restored and retained generic backend-owned repository scope, then tested an additional deterministic Qdrant strand per repository obligation. The stable query used fixed stage purpose, the deterministic issue title/request subject, and explicit prompt paths/symbols; generated propositions remained a separate strand. Results were interleaved into the unchanged 12-candidate initial pool.
- `run-20260811T165608Z` and `run-20260811T165945Z` each emitted six stable plus six generated searches and reused the 20,146-document index with `rebuilt=false`. All six stable queries were byte-identical across runs; none of the six generated queries were identical.
- Both runs were `partial/false`, had zero implementation Oracle overlap, and omitted both builder files from the connected shortlist. The first run saw `builderState.ts` in one generated result list; the second saw neither owner in any initial result list. Retrieval LLM usage was 18,236 and 16,735 tokens.
- The deterministic strand was removed because its broad stage/title wording favored `tsbuildPublic.ts`, server, and test neighborhoods while adding six Qdrant calls and increasing cost. Backend-owned repository scope remains enabled; only the ineffective additive query strand was reverted. Full framework and measurements are in `stable-obligation-query-strand.md`.

### Backend-Owned Repository Scope Experiment

- Tested making repository-stage scope backend-owned so all six TypeScript explain stages entered repository retrieval even when the stage-requirement LLM labeled a boundary `external`. The change was confined to obligation construction; query generation, Qdrant fusion, graph traversal, shortlisting, and final selection were unchanged.
- `run-20260811T164149Z` and `run-20260811T164430Z` both executed six repository obligations and six initial Qdrant queries, reused the prepared index with `rebuilt=false`, and ended `partial/false`. Retrieval token totals were 10,458 and 11,617.
- Neither run put `src/compiler/builder.ts` or `src/compiler/builderState.ts` in the deterministic shortlist, and both had zero implementation Oracle overlap. This regressed from the historical TypeScript pair's 0/1 overlap to 0/0.
- Stable obligation count did not stabilize the generated propositions: all six paired queries differed, with mean token Jaccard 0.409. Adding more variable proposition queries therefore increased search scope without recovering the owner files.
- The scope rule was initially reverted under the isolated quality gate, then restored and retained at the user's direction because stable backend-owned stage count is useful independently and contains no testcase-specific logic. A separately measured deterministic query-strand follow-up was unsuccessful and removed. Full boundary, risk, comparison, and decision details are in `backend-owned-repository-scope.md`.

### Offline Candidate-Signal Audit

- Added `testing/codeRepoQA/analyze_shortlist_signals.py` and replayed the eight saved difficult-run traces without rerunning indexing, retrieval, or LLM stages. The audit reconstructs file/obligation signals from Qdrant hybrid/dense/sparse results and CodeGraph nodes/edges; historical traces do not preserve enough state for byte-identical shortlist replay.
- The supposedly stable intent boundary still varied after intent selection. Every paired initial query changed (mean token Jaccard 0.418-0.537). In the TypeScript pair, `explain_resulting_effect` and `explain_why` changed from external to repository evidence, producing four versus six repository queries.
- Oracle files had stronger aggregate recurrence, semantic/graph corroboration, query/symbol overlap, and bidirectional productive-edge activity, but no individual signal or tested file-level policy was stable. Chain ranking had the best mean recall@10 at 0.844 but missed all TypeScript Oracle files in the first run's top ten.
- The next design order is therefore: stabilize repository-stage scope and add a deterministic base-query strand; create a bounded lossless file pool across obligations and retrieval channels; then select exact producer/mutation-owner/consumer nodes jointly. No retrieval behavior was changed from this audit.
- Full per-run features, Oracle diagnostics, counterfactual ranks, and evaluation constraints are recorded in `offline-shortlist-signal-audit.md`.

### Responsibility-Aware Shortlist Experiment

- Combined the eight valid repeated regression runs in `responsibility-aware-shortlisting.md`. The common owner signal is independent semantic/exact plus productive structural corroboration; broad component size alone did not distinguish owners from repeated generic matches.
- Tested component diversification, semantic/structural corroboration, executable responsibility scoring, dense/sparse single-channel recovery, and executable outbound-reference ownership at the completed-graph -> bounded-shortlist boundary. The four-candidate-per-obligation final prompt cap was unchanged.
- The probes did not stabilize the owner set. `run-20260811T142238Z` selected both builder files, while its unchanged repeat `run-20260811T142519Z` lost them. `run-20260811T144216Z` selected only `builderState.ts`; `run-20260811T144544Z` selected only `builder.ts`; `run-20260811T145056Z` and `run-20260811T145506Z` selected neither. All remained `partial/false`.
- Added `obligation_candidate_shortlists_created` trace output. In audited `run-20260811T145757Z`, exact `builderState.ts:updateExportedModules` reached the deterministic shortlist and final request but the LLM rejected it. This separates final-assessment rejection from the earlier shortlist-discard failures.
- The final comparison `run-20260811T145506Z` / `run-20260811T145757Z` had zero Oracle overlap, used 13,338 / 11,109 retrieval tokens, remained `partial/false`, and reused the warm indexes with `index_rebuilt=false`. The responsibility-ranking behavior was reverted; no unstable retrieval behavior from the experiment remains enabled.
- Conclusion: independent corroboration is useful but not sufficient because generic high-fanout paths can also be corroborated. The next design must rank a concrete producer -> state mutation owner -> consumer chain jointly instead of using isolated lexical, component-breadth, or edge-direction surrogates.
- Fixed fresh prepared-index reuse by writing `bm25-scope-manifest.json` in `prepare_index`. Per-snapshot indexes and repository-scoped Qdrant collections already isolate test cases; warm CodeGraph synchronization remains a validity check rather than a rebuild.
- Final focused verification after reverting the failed ranking experiment: 68 obligation, index-setup, and CodeRepoQA harness tests passed.

### Repeated Regression Matrix After Range Grounding And Focused Bridge

- Repeated four previously difficult native-retrieval cases twice each. These runs test the current code without another retrieval behavior change.
- `vuejs-vue-242`, whose prior `run-20260811T084114Z` had zero Oracle overlap, recovered `src/exp-parser.js:L93-L101` from the exact reported parser error in both repeats: `run-20260811T122541Z` and `run-20260811T122658Z`. Both had one implementation Oracle overlap and no rebuilt index, but both remained `partial/false` because five required transitions were unresolved. Runtime was 71.7s and 70.4s; retrieval LLM usage was 11,592 and 18,220 tokens.
- `vuejs-vue-10803`, whose historical zero-evidence run `run-20260707T160415Z` failed during Qdrant synchronization, now completed twice with evidence. `run-20260811T130723Z` selected exact `renderDOMProps`, `setText`, and `renderNode` ranges with one Oracle overlap, but remained `partial/false` because the final causal explanation was unresolved. The unchanged `run-20260811T130901Z` regressed to zero Oracle overlap and selected unrelated SSR attribute/bundle-renderer/compiler evidence. Runtime was 92.6s and 81.8s; retrieval LLM usage was 15,638 and 16,191 tokens. The focused bridge therefore works when it starts from the correct endpoint, but endpoint/core selection is not stable.
- `microsoft-TypeScript-35468` required the previously documented user-selected exclusions `lib` and `tests/cases`; a default-scope attempt `run-20260811T122814Z` spent 988.8s rebuilding and ended with `qdrant_index_sync_failed`, so it is excluded from retrieval-quality comparison. Valid runs `run-20260811T125639Z` and `run-20260811T130428Z` were both `partial/false`. The first had zero Oracle overlap; the second retained only `src/testRunner/unittests/tsbuild/watchMode.ts`, with one overlap. Neither selected `src/compiler/builder.ts` nor `src/compiler/builderState.ts`. Both files appeared repeatedly in Qdrant and CodeGraph trace events, but neither appeared in the final evidence-selection LLM request, proving that the remaining loss occurs in connected-shortlist construction rather than the removed 25% graph-overlap gate or final LLM rejection. Runtime was 462.1s with a scoped rebuild and 167.1s warm; retrieval LLM usage was 13,753 and 20,092 tokens.
- `pandas-dev-pandas-10068` was used as a cross-repository range-grounding control. `run-20260811T131029Z` selected exact `Series::_binop` plus its implementation/test context and had two Oracle overlaps. The unchanged `run-20260811T131236Z` regressed to zero Oracle overlap and selected sparse-series arithmetic instead. Both were `partial/false`; runtime was 113.4s and 111.2s, and retrieval LLM usage was 20,607 and 23,801 tokens.
- Conclusion: exact error seeding and full-range CodeGraph localization solve their targeted failures when the right candidate enters the retained graph, but overall final evidence is not stable. The next defect is the deterministic shortlist between graph discovery and final LLM selection: it can discard directly discovered owner nodes while retaining much larger, less relevant connected subgraphs. No sufficiency or stability claim is made from this matrix.

### Corpus-Distributed Prompt Anchors

- Replaced standalone Qdrant confirmation searches for every extracted identifier with exact corpus inspection against the existing BM25 index. Identifiers occurring in at most four repository paths retain exact grounding locations; more dispersed identifiers are marked `repository_common`, remain available inside obligation queries, and cannot independently restrict discovery to arbitrary matching files.
- Distribution uses distinct repository paths rather than raw chunk count. The first Vue probe showed that overlapping chunks can make a helper repeated inside one file look globally generic; the corrected rule preserves `renderVmWithOptions` as an exact anchor while classifying dispersed terms such as `SSR`, `textarea`, `domProps`, and `value` as common context.
- Vue `run-20260811T073815Z` was the initial chunk-sensitive probe. It reduced Qdrant calls to six but incorrectly classified the single-file helper as common. Vue `run-20260811T074130Z` used the path-distribution rule, made six Qdrant calls instead of the prior 15, made 34 total tool calls, recovered both Oracle files, selected five evidence items, and correctly reported `index_rebuilt=false`.
- The final rerun remained `partial/false`: it retained `renderDOMProps`, `setText`, and the SSR test but did not establish the later `VNode.text` serialization transition. The anchor change therefore reduces semantic noise and calls without claiming to solve focused continuation.
- The final-selection payload still contained 133 candidate-graph entries and used 15,468 tokens. Candidate shortlist quality and the missing serializer bridge remain separate unresolved problems.
- Verification: 57 focused retrieval/index tests passed. The anchor distribution test verifies that samples remain bounded while frequency counts cover all matching chunks and paths.

### Candidate-Signal Audit Across Repositories

- Audited the current 25% obligation-term overlap gate and structural score bonuses against TypeScript history plus fresh Vue and pandas native runs. No ranking behavior was changed in this audit.
- `pandas-dev-pandas-10068` run `run-20260811T080110Z` was `strong/true`, selected seven snippets across three source files, and recovered the sole implementation Oracle `pandas/core/series.py`. It also admitted several `pandas/core/index.py` candidates because generic obligation words such as `index`, `name`, and `result` satisfied lexical overlap. The preselection graph reached 468 entries and final selection used 25,400 tokens. This shows the overlap gate can retain the owner but is not selective against connected vocabulary noise.
- `vuejs-vue-242` run `run-20260811T075831Z` was `partial/false`, selected four files, and missed the changed owner `src/exp-parser.js`. That file appeared only in Qdrant's sparse breakdown and was omitted from the hybrid final results, so it never reached graph-overlap filtering. The selected `src/text-parser.js` was lexically plausible but implemented a different parser. This failure belongs to initial seed fusion, not the graph gate.
- The first pandas attempt `run-20260811T075710Z` failed explicitly during Qdrant synchronization on a transient embeddings TPM 429. An unchanged rerun succeeded; no fallback was added.
- Combined with prior TypeScript measurements, the audit does not support keeping a fixed text-overlap threshold as a graph eligibility rule. Exact productive relationships are useful provenance, but broad lexical overlap, evidence-role bonuses, and normalized upstream score labeled as `source_confidence` are not calibrated evidence quality measures.

### Graph-First Expansion And Final-Only LLM Selection

- Removed the obligation-local refinement Qdrant pass, shared/global frontier Qdrant pass, intermediate consolidation, Qdrant recovery, recovery consolidation, and deterministic post-selection evidence appenders. None remain as fallback paths.
- Workspace retrieval now runs one Qdrant seed search per obligation, maps results to CodeGraph, expands newly grounded exact nodes for at most three rounds, and invokes path-scoped Qdrant only when CodeGraph supplies no usable exact range.
- Every grounded candidate remains available until traversal stops. One final LLM call chooses the user-visible evidence; its rejection cannot alter prior graph traversal.
- Reusing the same candidate node across multiple obligations no longer proves a required transition. Sufficiency requires progress between distinct evidence through a graph edge, supported semantic handoff, resource reference, or explicit boundary result.
- Vue `run-20260811T040621Z` exposed an over-broad first attempt with 427 pre-selection candidates. The general expansion rule was tightened to visible direct continuations or obligation-relevant executable nodes.
- Vue `run-20260811T040832Z` and `run-20260811T042558Z` then recovered both Oracle files and retained `renderDOMProps` plus `setText`, with 47-48 tool calls, no frontier Qdrant calls, and one final LLM call.
- Vue `run-20260811T042943Z` exposed a false `strong/true` result caused by shared-node transition support. After removing that support path, final `run-20260811T043219Z` was correctly `partial/false`, selected both Oracle files, ranked `dom-props.js` first, used 50 tool calls and 13,486 final-selection tokens, and left the missing serializer transition explicit.
- The TypeScript comparison `run-20260811T041029Z` did not reach retrieval because the shared Qdrant collection had been replaced by Vue and spent the 15-minute budget rebuilding TypeScript embeddings. It is excluded from quality comparison.
- Verification: all 223 repository tests passed after the final transition rule; Python compilation and `git diff --check` also passed.

### Stable Request Analysis Contract - TypeScript Scoped Test

- Reworked request analysis into two bounded structured calls for single-intent requests: fixed binary intent decisions followed by one proposition per stage from the selected intent contracts. Multi-intent requests use one additional narrow call that may group only compatible stages from different intents when the same repository evidence establishes both. Obligation IDs, ordering, dependencies, evidence roles, and repository-handoff requirements remain derived and validated in code.
- Intent selection now follows the requested outcome. A request to explain code context remains `explain` even when its issue text contains expected and actual behavior; `debug` is selected only when diagnosis is independently requested.
- Exact prompt paths are parsed deterministically and are not rebound to similarly named repository paths. Symbol extraction is deliberately conservative and retains explicit named types and callable identifiers instead of arbitrary noun phrases.
- Five independent classifier-only attempts on `microsoft-TypeScript-35468` all selected only `explain`, produced the same six-stage obligation topology, retained the same three literal paths, and extracted only the `Session` symbol. Search-term and proposition wording varied without changing the retrieval contract.
- The second structured call classifies only supplied symbol candidates as `primary`, `supporting`, or `ignore`; it cannot invent symbols or alter intent/stage topology. Primary and supporting symbols are now retained separately. Native structural grounding uses only primary symbols, while supporting symbols may enrich semantic queries without becoming equivalent graph anchors. Vue probes consistently ignored the generic `toContain` assertion and classified the reporter's `isNaN` workaround as supporting.
- Stage propositions are directly required to remain proportionate to the requested change; the unused `full/minimal` label was removed. Formatting-only Pandas cases retained five distinct change stages while limiting affected paths and validation to edited locations and unchanged behavior.
- Every stage declares an evidence boundary: `prompt`, `local`, `local_to_external_handoff`, or `external`. The native provider does not search the current repository for external internals. Five `pandas-dev-pandas-9219` probes consistently traced pandas through its local HDF handoff and left PyTables internals external.
- Cross-intent grouping was split from the already broad stage/symbol call after that combined call inconsistently left all 12 `explain + use` stages separate. The dedicated grouping schema permits only earlier stages from another intent whose deterministic role, source, and generated boundary are compatible. It cannot merge same-intent stages or emit an impossible prompt-to-repository group.
- Three post-repair `microsoft-TypeScript-8305` probes all selected `explain + use`, preserved all 12 contract stages exactly once, and reduced them to 7-8 evidence groups. The groups consistently joined invocation with trigger and result with resulting effect; remaining variation concerned compatible setup/constraint placement rather than missing stages.
- A final ten-case classifier-only breadth run succeeded on nine cases immediately and preserved exact stage coverage with no same-intent merges in every success. `pandas-dev-pandas-36617` received an empty/non-JSON model response and failed explicitly; an unchanged retry succeeded with the correct `change` intent and five obligations. No fallback or retry path was added to production.
- This work was intentionally scoped before Qdrant and CodeGraph. It used no retrieval index and therefore produced no retrieval token or evidence-quality measurement. Remaining risk is first-call intent overlap on genuinely ambiguous direct prompts; the downstream grouping call now prevents that overlap from automatically duplicating retrieval work.
- Verification: 93 intent and retrieval-focused tests passed; Python compilation and whitespace checks passed.

### Goal-Directed Core Path Experiment - Reverted

- Experimented with outgoing-only CodeGraph path search between evidence cores, up to three incremental continuation rounds, and one globally bounded Qdrant semantic bridge. The intended stage boundary was accepted core evidence -> directional structural path -> one semantic bridge only for a missing graph edge -> incremental consolidation.
- `run-20260811T014818Z` was `partial/false`, retained one oracle overlap, made 75 retrieval tool calls, and used 21,321 consolidation tokens. Directional search worked mechanically, but initial consolidation selected benchmark/test cores and spent the semantic bridge from `createRenderer` rather than the `renderDOMProps`/`setText` endpoint.
- Repair 1 preserved high-ranked pre-consolidation cores for path search. `run-20260811T015136Z` was `partial/false`, retained `renderDOMProps` at rank 1 and one oracle overlap, made 66 tool calls, and used 16,614 consolidation tokens. It exposed that consolidation returned `status: unresolved` while supplying an intermediate candidate ID, but the backend treated that ID as full obligation support and therefore did not continue from `setText`.
- Repair 2 separated unresolved intermediate nodes from fully supported evidence and allowed incremental continuation. `run-20260811T015635Z` was `partial/false`, had zero oracle overlap, made 91 tool calls, and used 34,804 consolidation tokens across four calls. Request-analysis variation supplied benchmark/test endpoints, and all three structural rounds repeatedly followed those weak cores; the single semantic bridge could not recover the owner path.
- Result: the experiment regressed or destabilized evidence quality in two post-change comparisons and was removed completely. No directed-path tool, intermediate-support path, multi-round controller, semantic-bridge branch, or experiment-only test remains in production.
- The reusable conclusion is narrower: goal-directed traversal must operate on a stable, provider-independent core graph assembled before LLM consolidation. A future attempt must first prevent request-analysis variation or evidence-role wording from determining the core nodes; otherwise directional traversal merely follows an unstable starting choice more efficiently.

### Generated-Artifact Exclusion And Exact Structural Ranges

- Removed the temporary Obsidian path note and reindexed the vault before comparison runs. The retained connected-source integration remains generic; no Vue-specific navigation context is present.
- The existing `file_role()` classification now excludes generated/baseline artifacts before BM25/Qdrant indexing, exact-symbol ambiguity, structural candidate creation, semantic candidate creation, and final candidate safety filtering. Generated candidates are no longer retained as discovery hints.
- Direct productive CodeGraph targets whose symbols are visibly invoked by the current seed are retained without requiring their symbol names to overlap the broader obligation prose. Their exact ranges are included in the focused Qdrant frontier.
- Qdrant now injects chunks overlapping CodeGraph-preferred ranges from the local index before per-path truncation. This prevents semantic ranking from substituting another function range when CodeGraph has already supplied an exact target.
- Vue `run-20260811T005031Z` established the no-note baseline: `dom-props.js:L8-L45` was selected, but the exact `setText` edge was discarded before Qdrant. Vue `run-20260811T005449Z` retained `setText:L46-L50` as a preferred range, exposing that same-file targets were absent from the path frontier. After correcting that and rebuilding the prepared index, `run-20260811T010120Z` returned the exact `setText:L46-L50` Qdrant chunk without connected-source guidance.
- The last run remained `partial/false`: several structurally preferred ranges were treated equally, and the four-candidate consolidation cap did not review `setText`. Exact structural discovery and snippet retention now work; ordering the most relevant structural candidates before consolidation remains unresolved.
- Same-file traversal now distinguishes plain co-location from a concrete productive edge. A direct target is eligible only when CodeGraph supplies a productive relationship and the target symbol is visibly invoked by the selected seed. Its priority uses the immediate call-site branch rather than the whole file, and one consolidation slot is reserved for verified direct-target provenance. Plain `same_file` remains non-causal and receives no corresponding priority.
- Vue `run-20260811T012259Z` completed in 92.5 seconds as `partial/false`, used 80 tool calls and 22,087 consolidation tokens. Without the deleted note, `setText` appeared in both consolidation calls and final evidence retained `dom-props.js:L1-L50`, covering `renderDOMProps`, its call, and the `setText` definition. The later `renderNode` consumer was not selected, so continuation beyond the produced text VNode remains unresolved.
- Across the final run, selected generated evidence was zero and the deleted Obsidian note appeared zero times. Raw CodeGraph observations may still mention generated nodes, but they are filtered before candidate/frontier use.
- Verification: 66 focused tests passed; Python compilation and whitespace checks passed.

### Obsidian-Guided Intermediate Path Experiment

- Temporarily added an Obsidian architecture note describing how to continue from a verified implementation owner through direct call targets, produced state, and the consumer that establishes the final effect. The note was removed after the experiment above.
- Restored the missing production connection between the configured Obsidian vault and the `local_notes` connected-source handle. Previously, CodeRepoQA allowed local notes but the assembly read only explicit `local_note_paths`, which the test configuration did not provide.
- Connected-context file hints now qualify exact CodeGraph symbol matches and become preferred Qdrant paths. Retrieval terms and suggested subqueries from accepted notes are included in obligation queries. This disambiguates canonical source nodes from generated-bundle duplicates without accepting the note as code evidence.
- Before consuming file hints, Vue `run-20260811T000831Z` accepted the note and extracted the correct files/symbols, but all three symbols remained ambiguous against `build.dev.js`; final evidence still omitted `setText` and the correct `renderNode` range.
- After the integration, Vue `run-20260811T001248Z` grounded `renderDOMProps` at `dom-props.js:L8`, `setText` at `dom-props.js:L46`, and `renderNode` at `render.js:L74`. Final evidence contained the exact ranges at ranks 1, 2, and 7 respectively. The note remained context-only (`evidence_use=false`).
- The run remained partial/insufficient because consolidation mapped the three nodes to different obligations and did not assess the complete `renderDOMProps -> setText -> renderNode` chain as one support path. Navigation is therefore verified; cross-obligation path consolidation remains the next problem.
- Cost: 21,799 evidence-assessment tokens plus 5,494 connected-context tokens, compared with 19,117 assessment tokens in the prior no-note Vue run. The quality gain is the exact missing code path, at an 8,176-token combined increase.
- Verification: 112 retrieval-focused tests passed; Python compilation and whitespace checks passed.

## 2026-08-10

### Stable Recovery Review Ledger

- Recovery candidates now use stable identities based on obligation plus CodeGraph node ID or exact source range. Candidate order and regenerated list positions no longer create fresh identities for the same evidence.
- The focused recovery assessment excludes candidates already reviewed with unchanged source paths, relationship types, and covered concepts. A candidate is reconsidered only when later CodeGraph traversal adds materially different provenance.
- Recovery receives only new or enriched candidates and the prior unresolved reason, and is capped at two candidates per unresolved obligation. Unresolved output states only what retrieval failed to establish and may not claim repository-wide absence without explicit proof.
- TypeScript `run-20260810T203435Z` selected `builderState.ts` rank 1 and `builder.ts` rank 2, skipped one unchanged candidate, reconsidered two with new graph context, and used 26,810 assessment tokens versus 30,570 in `run-20260810T193146Z`.
- Vue `run-20260810T203913Z` selected the SSR DOM-props owner at rank 2, skipped 11 unchanged candidates, and used 19,117 assessment tokens. It found `src/server/render.js` but selected the wrong function range, so the final conversion remained honestly unresolved.
- Two endpoint-focused designs were tested and removed rather than retained as fallbacks. The initial probes (`run-20260810T202123Z`, `run-20260810T202455Z`) either expanded through the test harness or followed the client runtime. A bounded symbol-focused/multi-round variant also failed twice (`run-20260810T204850Z`, `run-20260810T205042Z`); the latter used 34,378 assessment tokens and 130 tool calls while still missing the SSR serialization path.
- Verification: 100 retrieval-focused tests passed after the failed endpoint code was removed; Python compilation, Node syntax, and whitespace checks also passed.

### Shared CodeGraph Frontier And Evidence-Backed Obligation Loop

- Replaced obligation-isolated role-filtered discovery with role-neutral semantic seeds, balanced global CodeGraph expansion, graph-aware Qdrant ranking, structured evidence consolidation, and one focused recovery round for unresolved obligations.
- CodeGraph file-neighbor scoring now saturates repeated edge counts, rewards distinct supporting source files, and preserves source-path and relationship provenance. This prevents high-fan-out utility files from receiving unbounded scores while retaining converging structural evidence.
- Qdrant receives graph-ranked preferred paths and exact ranges but remains a ranker, not proof. File roles no longer filter discovery or dependency traversal; tests/configuration can seed the graph, while final evidence consolidation applies their proof limitations.
- Consolidation accepts at most two complementary snippets per obligation, requires concrete candidate IDs, rejects generic semantic matches, and emits evidence-backed concepts. Invalid IDs are logged and ignored rather than crashing the run. Concepts may cite only accepted candidates for their mapped obligation.
- If consolidation leaves an obligation unresolved, one bounded recovery round expands exact CodeGraph nodes and file neighbors from the closest accepted/rejected evidence, reranks only that frontier with the unresolved reason, and reassesses it. There is no legacy hidden fallback path.
- Required intent stages now have an explicit `core_stage_coverage` map in obligation-repair output. Code validates the model's obligation IDs and applies that mapping before stage validation, preventing repaired plans from silently omitting cause/evidence stages.
- Final evidence includes one best available candidate for each unresolved required obligation while capacity remains. These candidates expose useful partial context without changing the obligation to supported or making the result sufficient; the previous arbitrary four-obligation cap was removed.
- Connected-support closure follows a bounded chain of direct graph connectors. If consolidation accepts nothing, graph-grounded partial evidence remains visible instead of returning an empty result, while coverage stays partial/insufficient.
- Common built bundles (`bundle.js`, `build.dev.js`, `build.prod.js`, and `dist/`) are classified as generated. Generated artifacts remain usable as traversal hints but cannot become final implementation evidence; deterministic current classification overrides stale role metadata in an existing Qdrant cache.
- Invalid setup run `run-20260810T174658Z` accidentally omitted the intended TypeScript exclusions and began rebuilding 94,284 chunks; it was terminated and excluded from comparison. Real TypeScript comparisons used `--exclude-path lib --exclude-path tests/cases` and a 20,146-document index.
- `run-20260810T175609Z` and `run-20260810T180350Z` established the pre-consolidation baseline: partial/insufficient, 9–10 selected items, two implementation overlaps, but substantial unrelated evidence and candidate-exists support.
- `run-20260810T181345Z` proved the first consolidation gate reduced ten files to four and removed generic parser/system/server candidates, but rejected complementary `builderState.ts` evidence. `run-20260810T181712Z` exposed request-analysis variability and zero Oracle overlap, motivating the shared global frontier.
- Stable TypeScript results:
  - `run-20260810T182931Z`: partial/insufficient, selected 4, `builder.ts` rank 3 and `builderState.ts` rank 4, 88 tool calls, 125 seconds, 23,466 consolidation tokens and 33,282 total request-analysis/retrieval LLM tokens;
  - `run-20260810T183155Z`: partial/insufficient, selected 4, `builderState.ts` rank 1 and `builder.ts` rank 2, 90 tool calls, 134 seconds, 28,893 consolidation tokens and 38,327 total request-analysis/retrieval LLM tokens.
- Vue regression and correction:
  - `run-20260810T183431Z` exposed a generated `build.dev.js` bundle bypassing post-recovery provenance ranking;
  - `run-20260810T184239Z` selected `src/platforms/web/server/modules/dom-props.js` at rank 1 plus `test/ssr/ssr-string.spec.js`, with no generated bundle in final evidence; 105 tool calls, 106 seconds, 26,342 consolidation tokens and 36,104 total request-analysis/retrieval LLM tokens.
- Final-code measurements after focused recovery, connected-support closure, structured core-stage repair, and unresolved-evidence presentation:
  - TypeScript `run-20260810T191746Z` and `run-20260810T192014Z` both recovered `builder.ts` and `builderState.ts`, establishing repeat stability before the final presentation-only change;
  - TypeScript `run-20260810T193146Z` selected `builderState.ts` rank 1, `builder.ts` rank 2, and the watch-mode test rank 8; partial/insufficient, 11 evidence items, 96 tool calls, 123 seconds, 30,570 consolidation tokens and 41,563 total request-analysis/retrieval LLM tokens;
  - Vue `run-20260810T193001Z` selected `dom-props.js` rank 1 and `ssr-string.spec.js` rank 2, with no generated bundles; partial/insufficient, 8 evidence items, 93 tool calls, 85 seconds, 16,154 consolidation tokens and 25,623 total request-analysis/retrieval LLM tokens.
- All final runs remained honestly partial where the pre-fix snapshot could not prove the issue-specific final handoff or fixed behavior. The owner and regression evidence improved without converting unresolved transitions into unsupported sufficiency.
- Remaining cost/risk: consolidation plus focused recovery still consumes 16k-31k retrieval LLM tokens on these cases, and partial results can retain secondary connected utility files. Token reduction and tighter final presentation should be measured as separate changes, not folded into the structural retrieval behavior.
- Verification: 94 retrieval-focused tests passed, Python/Node syntax checks passed, and `git diff --check` passed.

## 2026-08-06

### Ordering-Bias Neutralization Experiments

- Experiment A boundary: change only the model-facing order of valid Codex organizer candidates; candidate generation, validity checks, CodeGraph input, selection bounds, semantic prompt, and explanation stage input remain unchanged.
- Experiment A method: use a prompt-seeded stable hash permutation so retries are reproducible but Codex rank is not exposed as list position; preserve original candidate order in diagnostics and record the model-facing permutation.
- Experiment A expected quality impact: reduce primacy toward early Codex candidates while retaining semantic facets and graph cohesion as selection signals.
- Experiment A expected token impact: effectively neutral; the same candidates and compact fields enter the same organizer call.
- Experiment A risks: Codex rank may contain useful relevance information, and neutralization may replace a helpful prior with arbitrary positional exposure.
- Experiment B boundary: change only multi-intent model-facing stage order; retrieval and organizer ordering remain unchanged.
- Experiment B method: flatten stage definitions, remove grouped stage arrays from model-facing contracts, apply a prompt-seeded stable permutation to stage IDs and response-schema enums, and continue validating the output against the exact canonical stage set. Single-intent contract order remains unchanged.
- Experiment B expected quality impact: make the model choose narrative order from stage meaning rather than copying concatenated intent blocks.
- Experiment B expected token impact: effectively neutral; stage definitions are reorganized rather than expanded.
- Experiment B risks: removing the helpful within-intent order prior can yield unstable or less coherent flows; answer/story flow still share the resulting order.
- Comparison: run each flag separately on the same repository prompt; compare repairs, coverage, sufficiency, selected original positions, facet representation, final stage order, repetition, and real token usage against recent organizer baselines.
- Experiment A real runs:
  - `run-20260806T213148Z-82567f6d` returned 14 candidates and selected 13, remained `strong` and `sufficient=true`, covered all four facets, used zero organizer/explanation repairs, and selected four candidates originally positioned after 10; organizer/API totals were 9,178/18,505 tokens;
  - `run-20260806T215430Z-77b1072e` returned 12 candidates and selected 8, remained `strong` and `sufficient=true`, covered all four facets, used zero repairs, and split selected model positions evenly across the first and second halves; organizer/API totals were 8,617/16,702 tokens;
  - preserved-candidate replay of the exact 18 candidates from `run-20260806T205826Z-6ac86299` selected 10 instead of the baseline 11 with seven items overlapping, covered all four facets without repair, and selected original positions spanning 3 through 17; it dropped two meta/design items while retaining direct explanation and question implementation evidence and used 12,068 organizer tokens;
  - conclusion: candidate neutralization removes Codex rank from model-facing position without observable facet, grounding, stability, or token regression on these comparisons; it now defaults to enabled while preserving an explicit off-switch.
- Experiment B real runs:
  - `run-20260806T214003Z-67d9c0ee` initially returned a non-canonical explanation-first flow, but invalid question prerequisites survived one repair and correctly failed the response; the repair payload was then fixed to preserve neutralized stage input and repeat exact prerequisite contracts;
  - clean repeats `run-20260806T214552Z-2ba74ca6` and `run-20260806T215000Z-fe14bf65` both remained `strong` and `sufficient=true`, used zero organizer and explanation repairs, and generated two valid questions, but both reconstructed the exact canonical `explore` block followed by the exact canonical `explain` block from the same shuffled stage input;
  - their total API usage was 20,362 and 17,679 tokens respectively;
  - conclusion: serial-order anchoring was not the only cause of block composition; stage names, purposes, and intent grouping provide enough semantic structure for the model to reconstruct the canonical blocks. The stage neutralization flag remains disabled because it adds machinery without reliably changing narrative composition.

### Adaptive Understanding Checks Required For Every Guided Explanation

- Explanation generation now requires an adaptive set of one to three grounded understanding checks instead of accepting zero or limiting output to one.
- The generator chooses the smallest sufficient set: one by default, adding another only for an independently important reasoning transition with materially different semantics. Each check records one `reasoning_focus` and a `selection_reason` so the decision is inspectable.
- Deterministic validation rejects empty or oversized sets, duplicate IDs, normalized question text or reasoning focuses, repeated intent/target/evidence signatures, additional checks that introduce neither a new target nor new evidence, invalid intent contracts, and question evidence unrelated to the target/prerequisite stage cluster.
- Question validation uses the existing single explanation-repair attempt; a second invalid response fails explicitly and never falls back to an omitted or hard-coded question.
- The existing UI, batch answer evaluator, and comprehension follow-up already consume arrays and require evaluation coverage for every question ID, so no parallel question-specific LLM stage was added.
- Live comparison prompt: `Where is intent classification handled, and how does it flow into retrieval, explanation structure, and question generation?`;
  - initial `v3` run `run-20260806T205102Z-c3e1d02d` proved the minimum-one contract but returned one overly broad check whose expected answer crossed several component handoffs;
  - `v4` therefore added auditable `reasoning_focus` and `selection_reason` fields and permits broad stage overlap only when a later check introduces a new target or evidence reference;
  - fresh `v4` run `run-20260806T205826Z-6ac86299` completed `strong` and `sufficient=true`, organized 18 valid candidates into 11 selected items with zero organizer repairs, and generated two distinct checks with zero explanation repairs;
  - the two checks separately assess classification invocation and the downstream retrieval/explanation handoff, use different target-stage pairs and evidence clusters, and were produced inside the existing explanation call.

### Central Task Intents Passed To Retrieval Without An Evidence Plan

- Stage boundary:
  - task-intent classification now runs once in `core/control_layer.py` before retrieval;
  - retrieval receives only selected intent labels, neutral descriptions, specificity, and literal targets through `IntentContext`;
  - response stages, question contracts, evidence expectations, and stop conditions remain post-retrieval generation/evaluation concerns;
  - the optional intent sufficiency evaluator is observational, disabled by default, and does not control retrieval or generation.
- Expected quality impact:
  - retrieval can distinguish requested outcomes such as exploration and explanation without being anchored to intent-derived file roles or evidence keywords;
  - one central registry now drives explanation stages and question prerequisites;
  - native workspace retrieval no longer performs its own `primary_intent`/`secondary_intents` classification and instead consumes the central context.
- Expected token impact:
  - retrieval prompts gain a small intent-context object;
  - structured API generation can be larger for combined intents because every selected contract stage remains present;
  - the API generation budget was raised from 800 tokens/30 seconds to 4,000 tokens/120 seconds to avoid truncating valid multi-stage JSON.
- Known regression risks:
  - neutral descriptions may still bias retrieval more than labels alone;
  - combined intent contracts can produce repetitive prose if the generator concatenates intent blocks;
  - strict flow validation may require one repair call or explicitly fail when the model drops, duplicates, or invents stages.
- Comparison method:
  - used the same prompt and source policy for two real web-pipeline runs with Codex retrieval (`gpt-5.4-mini`, efficient profile) and OpenAI-compatible API generation (`gpt-5.4-mini`);
  - inspected classification, retrieval-plan context, selected files, answer/story stage order, repair count, generated question, sufficiency, and real token usage.
- Compatibility finding and fix:
  - `run-20260806T013444Z-0772ab72` failed before retrieval because OpenAI's strict response schema does not permit `uniqueItems`;
  - uniqueness is now enforced by deterministic parsing, and the unsupported schema keyword was removed.
- Successful run before removing the duplicate native intent classifier:
  - run: `.guided-intelligence/runs/run-20260806T013601Z-5123f865`;
  - `coverage_status=strong`, `sufficient=true`, 10 selected evidence items, zero flow repairs;
  - intents: `explore + explain`; one validated understanding question;
  - Codex retrieval tokens: 1,082,106 input plus output, of which 122,618 were uncached input plus output;
  - API tokens: 17,505 total (13,788 prompt, 3,717 completion);
  - quality issue: Codex correctly exposed that native workspace retrieval still had a competing legacy intent classifier.
- Successful run after cleanup:
  - run: `.guided-intelligence/runs/run-20260806T014602Z-8f534439`;
  - `coverage_status=strong`, `sufficient=true`, 10 selected evidence items, zero flow repairs;
  - intents: `explore + explain`; answer and story flows used the same exact 11-stage order; one validated `why` question;
  - Codex retrieval tokens: 1,219,202 input plus output, of which 120,450 were uncached input plus output;
  - API tokens: 14,932 total (11,684 prompt, 3,248 completion);
  - quality improvement: the answer identified one central classification owner and showed native retrieval consuming, rather than recreating, task intent;
  - remaining presentation issue: the model preserved all stages but concatenated the intent blocks and repeated facts, so the generic composition prompt was tightened to interleave multi-intent stages and cap each stage at two sentences.
- Stability result:
  - both completed runs had strong coverage, were sufficient, produced ten selected evidence items, and passed flow validation without repair;
  - uncached Codex usage was similar across the two runs, while API usage decreased in the second run;
  - no retrieval behavior was reverted because the quality signal was stable and the duplicate intent-system defect was removed.
- Final naming cleanup:
  - a third run (`run-20260806T015321Z-c0f4cc50`) remained `strong` and `sufficient=true`, selected 10 items, and passed flow validation without repair; Codex used 1,370,066 retrieval tokens (124,370 uncached) and API stages used 12,857 tokens, but Codex understandably treated policy's old `UserIntent`/`classify_intent` names as another intent owner;
  - the policy-only concept is now named `AssistanceRequestType`, its state/result field is `assistance_request`, and its deterministic helper is `_classify_assistance_request`;
  - policy behavior is unchanged, while semantic task intent now has one unambiguous owner under `services/intent/`.
- Codex evidence-cutoff diagnosis:
  - the raw output for `run-20260806T015321Z-c0f4cc50` contained 25 evidence entries, including six classified by Codex as `question generation` evidence;
  - replaying the provider's path, line, snippet, and duplicate checks against the complete raw payload found all 25 entries valid and unique: no invalid mappings, paths, line ranges, empty snippets, or duplicate source references;
  - `services/retrieval/codex/provider.py::_evidence_from_payload` stops after the first 10 valid entries, so 15 valid entries were discarded solely by the hard-coded limit;
  - the retained ten covered intent classification seven times, retrieval twice, and explanation structure once; the first question-generation entry was position 11, so none reached explanation generation;
  - current Codex tracing records only the post-cutoff `selected_count=10`; the raw JSON preserves all entries, but there is no explicit raw, valid-before-limit, duplicate, invalid, or limit-dropped count;
  - native workspace retrieval uses a different role-balanced final selector with `MAX_EVIDENCE_ITEMS=12`; inspection of 20 available native run artifacts found three runs above ten evidence items (11, 11, and 12), confirming that the Codex and native caps/stages are not shared;
  - Codex `coverage_status=strong` currently means usable non-generated source evidence exists, and `sufficient=bool(evidence)`; neither value proves semantic coverage of every explicit clause in the user request.
- Follow-up design direction:
  - instrument Codex conversion with raw, valid, invalid, duplicate, retained, and dropped counts before changing selection behavior;
  - replace first-N truncation with bounded coverage-aware selection over the already returned `coverage_area` values, then fill remaining slots by Codex order;
  - use one explicit configurable evidence budget across providers where practical, while preserving each provider's different candidate-generation and validation stages;
  - do not treat this post-retrieval selection improvement as an intent-derived Evidence Plan.
- Read-only CodeGraph cohesion experiment over all 25 pre-cutoff entries:
  - replayed the raw evidence ranges from `run-20260806T015321Z-c0f4cc50` through the current selected-evidence CodeGraph bridge; the synchronized index resolved named nodes for 23/25 entries and returned 25 direct structural edges;
  - the two unresolved entries were Markdown prompt ranges, which CodeGraph does not represent as source symbols;
  - manually audited labels were 20 accurate, two relevant-but-imprecise, and three conceptually misleading historical policy-intent entries;
  - accurate entries averaged 2.00 direct neighbors and 1.15 same-coverage neighbors; misleading entries averaged 1.67 and 1.00; imprecise entries averaged 2.50 and 1.00;
  - the signal did not cleanly separate quality: the two imprecise entries were not peripheral, and two misleading policy entries formed a structurally valid subgraph connected to orchestration;
  - seven accurate entries were structurally isolated, including prompt, schema, and planner artifacts, so low degree cannot safely mean irrelevant;
  - conclusion: use CodeGraph as a soft cohesion/diversity feature for grouping and tie-breaking, never as a discard rule or as proof that a `coverage_area` label is semantically correct;
  - preserve structurally isolated evidence when it contributes a distinct coverage area, and require a separate semantic judgment before presenting an item as adjacent, confusable, or explicitly out of scope.
- Failed Experiment A: remove independent post-retrieval evidence truncation:
  - stage boundary: temporarily used one 25-item budget in Codex payload conversion, comprehension planning, evidence graphing, and explanation generation; intent composition, concept heuristics, graph semantics, prompts, and validation were unchanged;
  - comparison baseline: `run-20260806T015321Z-c0f4cc50` returned 25 raw items but retained/generated from 10, used 9 references, completed its graph, consumed 12,857 API tokens, and omitted direct question-generation implementation evidence;
  - all-evidence run `run-20260806T161759Z-49350b57` returned and retained 17 items across all four requested areas, used 16 references, and reduced uncached Codex input-plus-output from 124,370 to 113,978 despite unrelated gross cache variance;
  - that run increased API usage to 22,634 tokens, changed the stage order from `explore -> explain` to `explain -> explore` without interleaving, and produced a more complete retrieval/explanation/question path;
  - quality regression: several explore stages described the intent contract itself instead of performing repository exploration, showing that unrestricted relevant evidence can let meta-contract snippets dominate stage assignment;
  - graph regression: the 17-item semantic graph failed because three prompt/contract items were neither accepted into the connected component nor reported as disconnected; explanation generation still completed because the graph is observational in the current response path;
  - repeat run `run-20260806T162541Z-9df15dbd` returned exactly 10 balanced items, so the raised limit had no effect; it used all 10 references, completed its graph, consumed 17,580 API tokens and 71,655 uncached Codex input-plus-output, but retained concatenated `explore -> explain` ordering and repeated facts across the blocks;
  - conclusion: passing every returned item did improve breadth when Codex returned more than ten, but quality and graph stability were not reliable; the shared 25-item budget was reverted;
  - next comparison should keep a bounded generation budget and test coverage-aware selection separately from stage-order and CodeGraph-input changes.

### Codex Evidence Organizer (Enabled By Default After Experimental Confirmation)

- Intended stage boundary:
  - Codex candidate generation and schema/path/range validation remain the retrieval provider's responsibility;
  - when `experiments.codex_evidence_organizer_enabled=true`, as many as 40 valid Codex candidates reach one post-retrieval organizer before explanation generation;
  - the organizer combines prompt-derived semantic facets with deterministic CodeGraph edges, replaces `RetrievalResult.evidence` with an adaptive 8-16 item set, and stores complete selection diagnostics;
  - native workspace retrieval, native graph behavior, and intent-stage ordering are unchanged.
- Expected quality impact:
  - remove first-10 position bias while preserving a bounded generation context;
  - retain direct support for classification, retrieval, explanation structure, and question generation when Codex returned it;
  - prefer structurally coherent evidence after semantic fit without discarding isolated evidence that contributes a distinct facet.
- Expected token impact:
  - one existing semantic graph LLM call now also performs organization; no separate semantic-matching call was added;
  - compact snippets and short model-facing candidate IDs limit organizer input, while explanation generation receives only selected evidence;
  - organizer-specific usage is stored under `retrieval_summary.evidence_organization.token_usage` and remains included in normal run-wide API totals.
- Known regression risks:
  - semantic facet selection can still vary between model calls;
  - hard 8-item minimum can retain supporting evidence for narrow prompts;
  - graph components that have no accepted path to the root are deterministically reported as disconnected rather than connected speculatively;
  - stage-order concatenation remains a known presentation issue and is intentionally deferred.
- Validation and failure behavior:
  - every candidate is schema-required exactly once in the assessment map;
  - selected references must be unique, stay within adaptive bounds, and may only have `core` or `supporting` status;
  - every covered or partial facet must retain at least one selected supporting reference;
  - one repair call is allowed for semantically invalid output; a second invalid result fails explicitly with no first-N, all-evidence, or graph-only selection fallback;
  - raw `codex-evidence.json` stays unchanged, while `evidence-items.json` and explanation generation contain only selected evidence.
- Fresh-run limitation:
  - `run-20260806T165811Z-4032dba1` retrieved 10 valid Codex candidates and correctly failed after one organizer repair under the earlier graph contract; that failure led to deterministic disconnected-component reporting and a stronger repair contract;
  - fresh reruns `run-20260806T170854Z-98c584df` and `run-20260806T171003Z-3b67e2e7` stopped before retrieval because the Codex CLI account reported its usage limit, with the next availability date shown as 2026-08-11;
  - therefore the initial implementation handoff could not include two fresh Codex outputs; preserved raw-artifact replays were used until the CLI became available again.
- Exact-prompt preserved-artifact comparisons on the final implementation:
  - prompt: `Where is intent classification handled, and how does it flow into retrieval, explanation structure, and question generation?`;
  - `replay-organizer-20260806-baseline25-v6` replayed the untouched 25-candidate raw artifact from `run-20260806T015321Z-c0f4cc50`: all 25 were valid and visible before organization, 8 were selected, 17 excluded, all four facets covered, graph complete, zero repair calls, `coverage_status=strong`, `sufficient=true`, one grounded question, and no citation outside the selected set;
  - that 25-candidate replay used 15,618 organizer tokens and 21,480 API tokens across organization plus explanation, below the 22,634-token all-evidence regression;
  - `replay-organizer-20260806-baseline17-v3` replayed the untouched 17-candidate raw artifact from `run-20260806T161759Z-49350b57`: all 17 were valid and visible, 8 were selected, 9 excluded, all four facets covered, graph complete, zero repairs, `coverage_status=strong`, `sufficient=true`, one grounded question, and no citation outside the selected set;
  - that 17-candidate replay used 10,017 organizer tokens and 15,724 API tokens across organization plus explanation;
  - both generation payloads exposed only `task_goal`, `answer_scope`, and `coverage_gaps` from the stored comprehension plan; legacy grounded/bridge/capsule concept metadata was absent from initial generation.
- Fresh exact-prompt end-to-end confirmations after Codex became available again:
  - `run-20260806T182453Z-4da8db99` returned 19 raw and schema-valid candidates, selected 9, excluded 10, covered all four prompt-derived facets, completed the graph with zero organizer repairs, remained `coverage_status=strong` and `sufficient=true`, generated one grounded question, and cited no excluded evidence;
  - that run used 1,389,404 gross Codex input-plus-output tokens (115,548 uncached), 12,106 organizer tokens, and 18,479 API tokens across organization plus explanation;
  - `run-20260806T183130Z-494af1b2` returned 21 raw and schema-valid candidates, selected 9, excluded 12, covered all four facets, completed the graph with zero repairs, remained `coverage_status=strong` and `sufficient=true`, generated one grounded question, and cited no excluded evidence;
  - that run used 1,372,710 gross Codex input-plus-output tokens (134,182 uncached), 12,016 organizer tokens, and 17,894 API tokens across organization plus explanation;
  - fresh graph-confirmation run `run-20260806T201935Z-e9304821` returned 19 valid candidates, selected 9 (`6 core`, `3 supporting`), excluded 10 (`8 supporting`, `2 adjacent`), completed without organizer repair, and remained `coverage_status=strong` and `sufficient=true`;
  - its all-candidate graph retained 19 distinct relationships connecting 14/19 candidates, while the selected graph retained 8 relationships connecting all 9 selected candidates; the remaining five candidates are explicitly visible as structurally isolated rather than silently omitted;
  - the explanation cited all 9 selected references and no excluded reference; Codex used 2,119,496 gross input-plus-output tokens (120,648 uncached), the organizer used 11,590 API tokens, and organization plus explanation used 18,958 API tokens total;
  - all three fresh runs stayed below the 22,634-token all-evidence API regression, selected direct evidence for classification, retrieval, explanation structure, and question generation, and avoided meta-contract dominance in the generated repository explanation;
  - selection was stable at 9 items despite Codex returning 19 to 21 candidates, and none used the repair path or a hidden fallback.
- Decision:
  - the bounded organizer passes both preserved-candidate and fresh end-to-end quality, grounding, stability, and token checks;
  - `experiments.codex_evidence_organizer_enabled` now defaults to `true` in runtime configuration and every checked-in web profile, while remaining available as an explicit diagnostic off-switch;
  - disabling it preserves the legacy first-10 Codex path for controlled comparisons only; organizer failure while enabled still fails explicitly and never falls back to that path.

## 2026-08-05

### Verified: CodeGraph Replacement On Historical CGC Timeout Case

- Purpose:
  - run a case that previously exceeded the interactive structural-indexing boundary;
  - inspect whether the current CodeGraph-backed native retriever improves both runtime and selected evidence quality.
- Selected case:
  - `microsoft-TypeScript-46770`;
  - historical workspace/native run `run-20260623T104115Z` failed before useful retrieval because CGC timed out after 600 seconds.
- Historical baseline:
  - run: `testing/codeRepoQA/batch-runs/002-20260623T102552Z/microsoft-TypeScript-46770/workspace/run-20260623T104115Z`;
  - `coverage_status=failed`;
  - `sufficient=false`;
  - `failure_reason=cgc_index_timeout`;
  - retrieved 0 source files;
  - oracle overlap `0/5`;
  - implementation overlap `0`;
  - no top-k oracle hit.
- Current CodeGraph workspace run:
  - command: `npm.cmd run coderepoqa:evaluate:workspace -- --issue-json testing/codeRepoQA/corpus/cases/microsoft-TypeScript-46770/issue.json`;
  - run: `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-46770\runs\run-20260805T021431Z`;
  - completed end to end in about 155 seconds;
  - `coverage_status=partial`;
  - `sufficient=false`;
  - retrieved 4 source files:
    - `src/compiler/checker.ts`,
    - `src/compiler/diagnosticMessages.json`,
    - `src/compiler/moduleNameResolver.ts`,
    - `src/compiler/transformers/declarations/diagnostics.ts`;
  - oracle overlap `1/5`;
  - implementation overlap `1`;
  - implementation owner `src/compiler/moduleNameResolver.ts` ranked third and was found within top 5.
- Runtime and trace notes:
  - CodeGraph structural index stage took 13,448 ms;
  - CodeGraph reported 221 discovered files, 220 indexed files, 14,993 nodes, and 77,594 edges;
  - CodeGraph skipped `src/compiler/checker.ts` with a `size_exceeded` warning because the file exceeded the 1 MB index threshold, but retrieval still selected checker snippets through Qdrant/local refinement;
  - BM25/Qdrant index stage took 13,963 ms;
  - retrieval made 215 tool calls;
  - retrieval LLM tokens: 11,704 total.
- Result:
  - the CGC timeout failure is resolved for this case;
  - native retrieval now reaches the key implementation owner where the old workspace path retrieved nothing;
  - final sufficiency is still partial because the run does not retrieve the oracle test/baseline files and the deterministic gate reports `behavior_output:owner_layer_missing`;
  - current workspace config excludes `tests/cases` and `tests/baselines`, so several oracle files are unreachable in this run by policy rather than ranking alone.
- Retrieval-quality observations to revisit:
  - exact structural preplan only found `TypeScript -> src/compiler/moduleNameResolver.ts`; issue terms such as `ESM`, `TS2307`, `TS2349`, and `node_modules` had no exact CodeGraph symbol matches, which is expected but means Qdrant still carries most semantic discovery;
  - the final selected evidence overweights checker and diagnostic surfaces before the module-resolution owner, even though `moduleNameResolver.ts` is the implementation oracle;
  - this suggests a next retrieval improvement should bias final evidence toward the owner implementation once CodeGraph/Qdrant have identified it, and treat diagnostics/checker snippets as support unless the issue's failure is actually diagnostic ownership;
  - test/baseline exclusion policy should be reconsidered for CodeRepoQA cases where the prompt includes an explicit native repro path.

### Verified: CodeGraph Replacement On Historical Workspace Retrieval Failure

- Purpose:
  - recheck a historical native/workspace retrieval failure after the CGC-to-CodeGraph replacement;
  - use a real CodeRepoQA workspace run, not Codex retrieval and not an isolated unit harness;
  - compare whether the replacement improved retrieval quality, not only indexing speed.
- Selected case:
  - `vuejs-vue-10803`;
  - this case was previously documented as the cleaner native-retrieval quality signal because it was a narrow Vue SSR bug that did not fail only because of infrastructure timeout;
  - the issue explicitly mentions `test/ssr/ssr-string.spec.js` and the implementation owner is `src/platforms/web/server/modules/dom-props.js`.
- Historical baseline:
  - run: `testing/codeRepoQA/batch-runs/002-20260623T102552Z/vuejs-vue-10803/workspace/run-20260623T112023Z`;
  - `coverage_status=partial`;
  - `sufficient=false`;
  - oracle overlap `1/2`;
  - implementation owner `src/platforms/web/server/modules/dom-props.js` ranked second;
  - retrieved 6 source files;
  - made 513 tool calls;
  - retrieval LLM tokens: 24,239 total;
  - CGC structural index stage took 106,913 ms.
- Current CodeGraph workspace run:
  - command: `npm.cmd run coderepoqa:evaluate:workspace -- --issue-json testing/codeRepoQA/corpus/cases/vuejs-vue-10803/issue.json`;
  - run: `C:\Programming\guidedInteligence_testcases\vuejs-vue-10803\runs\run-20260805T005332Z`;
  - `coverage_status=partial`;
  - `sufficient=false`;
  - oracle overlap `1/2`;
  - implementation owner `src/platforms/web/server/modules/dom-props.js` ranked first;
  - retrieved 3 source files:
    - `src/platforms/web/server/modules/dom-props.js`,
    - `src/platforms/web/compiler/modules/model.js`,
    - `src/compiler/directives/model.js`;
  - made 342 tool calls;
  - retrieval LLM tokens: 12,968 total;
  - CodeGraph structural index stage took 1,982 ms;
  - BM25/Qdrant index stage took 1,074 ms.
- Result:
  - CodeGraph materially improved infrastructure cost and owner precision on this historical failure;
  - selected evidence was less noisy, and the implementation owner moved from rank 2 to rank 1;
  - retrieval still did not become sufficient because it missed the oracle repro/test file `test/ssr/ssr-string.spec.js`;
  - the remaining failure is therefore in planning, support-objective promotion, or final evidence selection, not in structural graph indexing alone.
- Follow-up implication:
  - the CodeGraph replacement should be treated as successful for replacing CGC's slow structural index path;
  - it should not be treated as a full native-retrieval quality fix;
  - future work on this case should focus on honoring explicit prompt file hints and retrieving/retaining verification repro evidence when the issue contains a concrete test path.

## 2026-08-04

### Changed: Replaced CGC With Project-Local CodeGraph

- Intended stage boundary:
  - CodeGraph owns exact symbol resolution, callers, callees, file dependencies, and verified source relationships;
  - Qdrant remains responsible for conceptual and natural-language retrieval;
  - the existing protocol bridge remains separate because transport/error-string relationships are not structural code-graph edges.
- Expected quality impact:
  - remove CGC content/name heuristics and raw Cypher string matching from relationship validation;
  - use graph node identity and file/line locations for call traversal;
  - report no structural relationship when CodeGraph has no edge instead of accepting generic uppercase names.
- Expected token impact:
  - no additional LLM calls or prompt fields;
  - structural indexing and queries are local and therefore add zero retrieval tokens.
- Known regression risks:
  - CodeGraph language support and cross-language resolution vary by ecosystem;
  - exact symbol lookup intentionally does not replace Qdrant concept search;
  - a first index can still be material on very large repositories, although incremental sync is much cheaper.
- Pre-change gate on native-retrieval timeout case `microsoft-TypeScript-46770`:
  - historical CGC run `run-20260623T104115Z` timed out at 600 seconds before retrieval;
  - project-local CodeGraph indexed the same snapshot successfully: 30,987 files, 279,591 nodes, and 523,919 edges;
  - CodeGraph indexing took 2m18s internally and 8m07s through the one-shot CLI, under the previous 10-minute failure boundary;
  - an unchanged incremental sync completed in 21.2 seconds end to end;
  - exact lookup and caller traversal resolved `createBuilderProgram` to `src/compiler/builder.ts` and its two public builder callers.
- Implementation verification:
  - production retrieval uses a long-lived embedded Node bridge during one run and closes it deterministically afterward;
  - indexing temporarily installs workspace exclusions and then restores an existing `codegraph.json` byte-for-byte, or removes the generated file when the workspace had none;
  - the CGC Python package, tools, command configuration, Kuzu paths, marker files, `.cgcignore`, server handling, UI estimates, and benchmark wiring were removed;
  - `tests.test_codegraph_tools` verifies indexing, exact-only lookup, source-location call traversal, and file relationships against a real temporary TypeScript repository;
  - `tests.test_codegraph_tools` plus `tests.test_workspace_retrieval` pass 65 tests with `ResourceWarning` promoted to an error;
  - `tests.test_retrieval_server` passes 37 tests and `npm run web:build` passes.
- Real native-retrieval verification on `microsoft-TypeScript-46770` after the replacement:
  - `run-20260804T223427Z`: `coverage_status=strong`, `sufficient=true`, 8 evidence items, structural sync 1.962s, 12,486 retrieval tokens, and the oracle implementation file ranked second;
  - `run-20260804T224122Z`: `coverage_status=partial`, `sufficient=false`, 4 evidence items, structural sync 2.002s, 11,694 retrieval tokens, and the oracle implementation file remained in the top five;
  - `run-20260804T224528Z`: `coverage_status=strong`, `sufficient=true`, 6 evidence items, structural sync 1.643s, 8,306 retrieval tokens, but the oracle implementation file was not selected;
  - all three runs produced the same exact structural narrowing result, including `TypeScript -> src/compiler/moduleNameResolver.ts`; the remaining coverage and selection variance comes from downstream LLM role planning and evidence selection, not from unstable CodeGraph output;
  - CodeGraph therefore resolves the historical indexing timeout and provides stable local graph operations, but this replacement does not by itself fix the native pipeline's existing LLM selection variance.

### Changed: Isolated Codex Retrieval From User MCP Configuration

- Codex retrieval invokes `codex exec --ignore-user-config` when `codex_ignore_user_config` is enabled.
- Saved authentication remains available, but global user MCP servers and other user configuration are not inherited by retrieval runs.
- CodeGraph MCP access used by the bounded experiment was temporary and is not part of the production retrieval path.

### Changed: Post-Retrieval Hybrid Evidence Graph

- Intended stage boundary:
  - normal Codex retrieval selects and describes evidence without generating graph nodes or edges,
  - a post-retrieval stage runs CodeGraph over only the selected evidence ranges and discovers exact source relationships,
  - exact source-to-document references are resolved locally, while one bounded LLM call supplies semantic, cross-language, transport, and Markdown relationships that static analysis cannot prove,
  - graph metadata remains in `retrieval_summary` and is not sent to explanation generation.
- Expected quality impact:
  - retain the coherent decision-to-UI flow of the earlier LLM-only graph,
  - keep exact CodeGraph and source-to-document relationships as the factual backbone instead of letting the semantic model omit them,
  - distinguish direct CodeGraph/document relationships from inferred semantic boundaries,
  - remove redundant cycles and shortcuts while requiring every selected item to be connected or explicitly reported as disconnected.
- Expected token impact:
  - Codex retrieval no longer spends tokens discovering and justifying the graph,
  - the isolated Next-check evidence set used 6,735 graph-stage input tokens and 943 output tokens, 7,678 total,
  - this is about 79% below the 36,716 uncached-token increase observed between the pre-graph baseline and accepted LLM-only graph run F; the later live-stage replay measured still lower usage.
- Known regression risks:
  - CodeGraph support varies by language and cannot prove HTTP, serialization, prompt-file, or frontend/backend boundaries,
  - inferred LLM edges remain semantic claims and must be labeled `inferred`,
  - a workspace without a CodeGraph index incurs local indexing before graph extraction,
  - graph failure is surfaced explicitly; it does not fall back to an ungrounded deterministic graph.
- Isolated comparison using the exact evidence from `run-20260804-evidence-graph-f`:
  - 10/10 selected nodes connected by 9 non-redundant edges,
  - CodeGraph supplied five exact call relationships,
  - local source inspection supplied the two exact Markdown prompt-file relationships,
  - the bounded LLM supplied the remaining semantic transport boundary and organized the final minimal flow.
- Verification:
  - live `/retrieve` run `run-20260804T155019Z-f3b0042a` completed with `coverage_status=strong`, `sufficient=true`, and 9 selected evidence items after the existing one-time explanation-timeout retry,
  - the final graph-stage replay on those exact 9 items connected 9/9 nodes with 8 edges and no disconnected artifacts; it used 5,432 input and 819 output tokens, 6,251 total,
  - the graph contained five direct CodeGraph/document/shared-field edges and three bounded inferred semantic edges for omitted prompt-response, repair-document, and backend-frontend boundaries,
  - `.venv\Scripts\python.exe -m unittest tests.test_codex_provider tests.test_evidence_graph tests.test_retrieval_server` passed 50 tests.
  - `npm run web:build` passed.
  - the broader `tests.test_policy` suite still contains legacy mocked responses without the required `story_flow` object and one stale prompt-text assertion; those pre-existing fixture failures were not bypassed by this change.

### Superseded: Codex Evidence Connection Graph (Historical LLM-Only Design)

- Intended stage boundary:
  - Codex retrieval assigns stable retrieval-local IDs to selected evidence and returns semantic connections between those selected items,
  - deterministic post-processing drops dangling, self-referential, and duplicate edges and remaps local IDs to persisted evidence source refs,
  - the connection graph remains in `retrieval_summary` and the run-detail API; it is not included in explanation-generation prompts or response metadata,
  - the frontend renders this retrieval-only object as an interactive evidence-flow graph.
- Expected quality impact:
  - expose cross-file data, control, configuration, validation, and rendering relationships that CGC/SCIP did not resolve reliably,
  - keep graph descriptions grounded and user-readable while allowing inferred edges only when an omitted boundary is stated,
  - preserve the existing explanation pipeline without making graph metadata part of its story or question generation.
- Expected token impact:
  - the connection schema itself is small, but end-to-end continuity can make Codex inspect bridge code that compact evidence retrieval previously skipped,
  - accepted runs used materially more retrieval tokens than the comparable pre-graph run, so this feature carries a measurable retrieval-cost regression.
- Known regression risks:
  - Codex can over-search to make a graph connected or broaden evidence ranges to capture a bridge,
  - semantic edges are model-produced claims rather than compiler-proven relationships,
  - a single end-to-end question can still produce disconnected components unless continuity is explicitly checked,
  - graph quality must not be treated as evidence that explanation quality improved, because the graph is intentionally excluded from explanation generation.
- Real-run comparison for the Next-check end-to-end prompt:
  - pre-graph `run-20260803T223100Z-b784110f`: `coverage_status=strong`, `sufficient=true`, 9 selected items, retrieval input plus output `223,809`, uncached input plus output `44,609`.
  - accepted graph run `run-20260804-evidence-graph-e`: `coverage_status=strong`, `sufficient=true`, 7/7 nodes connected by 6 edges, retrieval input plus output `1,211,380`, uncached input plus output `122,868`.
  - accepted graph run `run-20260804-evidence-graph-f`: `coverage_status=strong`, `sufficient=true`, 10/10 nodes connected by 9 edges, retrieval input plus output `781,229`, uncached input plus output `81,325`.
  - both accepted graphs formed one traversable decision-to-UI flow, used readable labels, and marked the omitted transport/return boundary as `inferred / medium` rather than direct.
  - orchestration traces for both accepted runs contained no `evidence_connections` or `source_evidence_id` fields in explanation-generation events.
- Verification:
  - `.venv\Scripts\python.exe -m unittest tests.test_codex_provider tests.test_retrieval_server` passed 48 tests.
  - `npm run web:build` passed.
  - live `/retrieve` runs E and F completed through the efficient Codex profile with `coverage_status=strong` and `sufficient=true`.
  - desktop and mobile browser checks confirmed 10 rendered nodes, 9 rendered edges, selectable edge details, no page-width overflow, and no browser console errors.

## 2026-07-12

### Changed: Adaptive Loop Support-Subquery Promotion

- Intended stage boundary:
  - keep Step2 as the planner that emits `support_subqueries`,
  - keep `adaptive_loop.py` responsible for promotion decisions,
  - fix `role_retrieval.py` so supporting-phase retrieval executes support-role queries instead of looking only at primary `llm_subqueries`.
- Expected quality impact:
  - promoted objectives such as `verification_repro -> tests` should now have a real chance to add evidence,
  - narrow defect runs should avoid the previous no-op promotion where a role was promoted but no tool calls were made,
  - the deterministic gate remains unchanged in this slice; objective-aware sufficiency is still a separate follow-up.
- Expected token impact:
  - promoted support rounds can now spend additional retrieval calls where previously they spent zero,
  - first-round token use is unchanged,
  - total tokens may increase when support evidence is actually retrieved, but the increase is tied to an explicit deferred-objective promotion.
- Known regression risks:
  - support subqueries may retrieve noisy test/config/doc artifacts if Step2 emits weak support queries,
  - support evidence may improve synthesis while the legacy deterministic gate still reports missing old required roles,
  - the no-op skip guard only skips roles with no executable planned query; it does not suppress an executed query that returns no useful evidence.
- Verification:
  - `.venv\Scripts\python.exe -m unittest tests.test_workspace_step2_objectives tests.test_coderepoqa_retrieval tests.test_workspace_retrieval` passed 85 tests immediately after the change.
  - `npm.cmd run coderepoqa:evaluate:workspace -- --issue-json testing/codeRepoQA/corpus/cases/vuejs-vue-10803/issue.json` failed before pipeline execution because npm invoked system `python`, which lacked `langgraph`.
  - subsequent direct `.venv\Scripts\python.exe` and `py -3.11` invocations became blocked by the Windows Python launcher/session state, so the real Vue rerun could not be completed in this turn.
- Follow-up runtime repair and real-run result:
  - repaired `.venv` by rebinding it from the stale WindowsApps Python target to `C:\Users\mukha\AppData\Local\Programs\Python\Python311\python.exe`,
  - changed Python-backed npm scripts to invoke `.venv\Scripts\python.exe` directly so the documented CodeRepoQA commands use the project environment,
  - reran the focused unit suite: `.venv\Scripts\python.exe -m unittest tests.test_workspace_step2_objectives tests.test_coderepoqa_retrieval tests.test_workspace_retrieval` passed 85 tests,
  - real Vue run `run-20260712T164219Z`: `coverage_status=partial`, `sufficient=false`, `overlap_count=0`, `implementation_overlap_count=0`, 2 retrieved source files, 226 tool calls, retrieval LLM tokens `12,439`, no promoted roles because `owner_grounded=false`,
  - real Vue run `run-20260712T164506Z`: `coverage_status=partial`, `sufficient=false`, `overlap_count=0`, `implementation_overlap_count=0`, 2 retrieved source files, 237 tool calls, retrieval LLM tokens `12,509`, no promoted roles because `owner_grounded=false`.
- Quality conclusion:
  - the Python/npm environment is fixed,
  - the support-subquery promotion fix is unit-covered but was not exercised in the Vue real runs because the loop stopped in owner-recovery mode before promotion,
  - current adaptive-loop behavior is not acceptable on the Vue benchmark: two real runs missed the oracle owner file, so the next retrieval change should target owner-grounding/recovery before treating support promotion as validated.

## 2026-06-24

### Changed: Workspace Step2 Objective Metadata And Narrow-Defect Role Selection

- Intended stage boundary:
  - Step2 now classifies `primary_intent`, `specificity`, active/deferred objectives, preferred relations, stop contract, expansion policy, and deterministic prompt signal flags,
  - Stage consumes the Step2 metadata only through a gated compatibility bridge, `objective_role_selection_enabled`,
  - the first enabled behavior is intentionally limited to `defect_localization:narrow`; other intents remain metadata-only.
- Expected quality impact:
  - narrow defect reports should prioritize implementation-owner evidence before broad role coverage,
  - expected-vs-actual output should route to behavior/output evidence, while diagnostics should require concrete error/warning/exception/traceback text,
  - support artifacts remain available through the compatibility bridge until a real deferred-objective promotion loop exists.
- Expected token impact:
  - fewer initial required roles for narrow defects should reduce tool calls and retrieval LLM tokens,
  - support-role savings are not fully realized yet because deferred support roles are still available as a safety net.
- Known regression risks:
  - over-narrowing required roles can miss owner files when the current Stage lacks a promote-on-failure loop,
  - prompt text such as `renderVmWithOptions` can still trigger broad config-like flags through simple lexical matching,
  - the current objective-to-legacy-role mapping is transitional and can duplicate old role semantics.
- Real-run comparison:
  - baseline `vuejs-vue-10803` workspace run `run-20260623T112023Z`: `coverage_status=partial`, `sufficient=false`, implementation overlap `1`, owner file `src/platforms/web/server/modules/dom-props.js` at rank 2, 6 retrieved source files, 513 tool calls, 8 role subqueries, retrieval LLM tokens `24,239`, uncached prompt plus completion `23,215`.
  - accepted objective-role run `run-20260624T013101Z`: `coverage_status=partial`, `sufficient=false`, implementation overlap `1`, owner file at rank 3, 5 retrieved source files, 394 tool calls, 5 role subqueries, retrieval LLM tokens `16,856`, uncached prompt plus completion `15,832`.
  - intermediate `run-20260624T012539Z` regressed because wrong-output text activated `diagnostic_surface`; this was fixed by separating `has_diagnostic_surface` from `has_output_symptom`.
  - stricter support-deferral run `run-20260624T013551Z` reduced retrieval LLM tokens to `12,705` but missed the oracle owner file; that Stage change was reverted.
- Quality conclusion:
  - keep the gated narrow-defect role selection because it preserved baseline overlap and sufficiency status while reducing tool calls by 23% and retrieval LLM tokens by 30% on the Vue case,
  - do not remove initial support-role availability yet; deferred-objective promotion needs an explicit Stage loop and success gate first.
- Verification:
  - `.venv\Scripts\python.exe -m unittest tests.test_workspace_step2_objectives tests.test_coderepoqa_retrieval` passed 13 tests.
  - `.venv\Scripts\python.exe -m py_compile services/retrieval/workspace/stage.py services/retrieval/workspace/step2/step2.py services/retrieval/workspace/step2/prompts.py tests/test_workspace_step2_objectives.py` passed.

## 2026-06-23

### Changed: Named Codex Prompt Profiles And Efficient Default

- Intended stage boundary:
  - move each Codex retrieval prompt and strict output schema out of Python into one self-contained profile directory under `services/retrieval/codex/profiles/`,
  - select the contract with `codex_prompt_profile` while keeping `codex` as one retrieval mode and leaving downstream explanation generation shared,
  - preserve schema-specific top-level and evidence fields generically so `services/retrieval/codex/provider.py` does not name or encode either profile's optional structure,
  - restore the original cheaper contract as the `efficient` default and retain the 2026-06-23 experiment as the opt-in `responsibility-complete` profile.
- Expected quality impact:
  - default Codex runs return to the previously measured compact evidence behavior,
  - the responsibility-complete owner/coverage metadata remains available for explicit quality experiments,
  - prompt experiments can now be compared without editing provider orchestration code.
- Expected token impact:
  - `efficient` matches the pre-experiment prompt and schema exactly and therefore restores the lower measured baseline behavior,
  - `responsibility-complete` retains the measured 100%-166% gross-token increase and 86%-126% retrieval-latency increase from the two-case experiment,
  - profile loading itself adds no model tokens.
- Known regression risks:
  - selecting the wrong profile in a centralized config can make benchmark results incomparable,
  - deleting or corrupting a profile file now fails Codex retrieval explicitly,
  - the efficient schema does not expose role, confidence, symbol, issue-analysis, or coverage-gap fields.
- Comparison and verification:
  - `efficient/prompt.md` reproduces the batch-002 `microsoft-TypeScript-45713` prompt after inserting the same issue packet,
  - `efficient/evidence.schema.json` is JSON-equivalent to that run's saved schema,
  - `responsibility-complete` preserves the exact prompt/schema contract used by `run-20260623T115317Z` and `run-20260623T115958Z`,
  - `.venv\Scripts\python.exe -m unittest tests.test_codex_provider tests.test_coderepoqa_retrieval tests.test_retrieval_server` passed 43 tests,
  - all profile and centralized config JSON files parsed successfully.
- Real efficient-profile verification:
  - `microsoft-TypeScript-45713` run `run-20260623T163652Z` loaded `efficient` from the new profile directory and recorded that name in run metadata and both Codex trace events,
  - retrieval completed in `164.836s`; full orchestration completed in `192.4s`,
  - `coverage_status=strong`, `sufficient=true`, with 5 evidence items across 3 files and 3 implementation-oracle overlaps at ranks 1-3,
  - gross tokens were `1,849,125` and uncached input plus output was `192,805`, illustrating normal Codex run-to-run cache variance even with the same prompt/schema contract.
- Usage:
  - existing `config:web:codex` and `coderepoqa:evaluate:codex` commands select `efficient`,
  - explicit `:efficient` and `:responsibility-complete` npm commands are available for web UI and testcase runs,
  - testcase run metadata and Codex retrieval traces now record `codex_prompt_profile`.

### Experiment: Responsibility-Complete Codex Evidence Prompt

- Intended stage boundary:
  - change only the Codex evidence-discovery prompt, its strict output schema, and direct schema-to-`EvidenceItem` metadata preservation,
  - leave workspace retrieval, orchestration, response generation, and understanding-check generation unchanged,
  - continue excluding verification data, oracle files, and post-resolution information from the Codex workspace and prompt.
- Expected quality impact:
  - rank likely implementation owners ahead of symptom surfaces and generic architectural files,
  - require a compact responsibility chain and make uncovered responsibilities explicit,
  - preserve symbol, role, relevance, and confidence metadata for downstream explanation generation and run inspection.
- Expected token impact:
  - the larger instructions and schema add a small fixed prompt/output cost,
  - the 2-6 evidence-item limit and anti-duplication rule should reduce broad file reading and repeated evidence,
  - success requires improved or stable oracle overlap without materially increasing gross or uncached Codex usage.
- Known regression risks:
  - responsibility-chain instructions may encourage unnecessary subsystem breadth,
  - strict role enums may force ambiguous evidence into an imperfect category,
  - implementation-owner bias may under-select tests that contain the only concrete reproduction,
  - prompt changes remain nondeterministic and require real-run comparison before broader adoption.
- Comparison plan:
  - rerun Codex mode for retrieval-grounded cases `microsoft-TypeScript-45713` and `microsoft-TypeScript-46770`,
  - compare against batch 002 Codex baselines using implementation overlap, top-k position, selected evidence count, elapsed time, gross tokens, and uncached tokens,
  - disable or revise the experiment if both cases regress in implementation overlap or if sufficiency becomes unstable.
- Real-run results:
  - `microsoft-TypeScript-45713` baseline `run-20260623T103650Z`: retrieval `203.619s`, full orchestration `228.129s`, `strong/sufficient=true`, 3 evidence items across 2 files, 2 implementation-oracle overlaps at ranks 1 and 2, gross tokens `1,537,434`, uncached tokens `79,258`.
  - `microsoft-TypeScript-45713` experiment `run-20260623T115317Z`: retrieval `378.561s`, full orchestration `401.190s`, `strong/sufficient=true`, 5 evidence items across 4 files, 3 implementation-oracle overlaps at ranks 1, 2, and 4, gross tokens `3,078,628`, uncached tokens `121,316`.
  - `microsoft-TypeScript-46770` baseline `run-20260623T105125Z`: retrieval `192.833s`, full orchestration `221.209s`, `strong/sufficient=true`, 6 evidence items across 3 files, one implementation-oracle overlap (`moduleNameResolver.ts`) at rank 3, gross tokens `1,463,271`, uncached tokens `93,671`.
  - `microsoft-TypeScript-46770` experiment `run-20260623T115958Z`: retrieval `435.558s`, full orchestration `473.295s`, `strong/sufficient=true`, 6 evidence items across 3 files, one implementation-oracle overlap (`moduleNameResolver.ts`) improved to rank 2, gross tokens `3,892,185`, uncached tokens `253,401`.
- Quality conclusion:
  - `45713` preserved the two core owner files and added the oracle watch-helper test path; its explicit coverage gaps correctly identified missing per-file aggregation state and a missing non-watch summary fixture.
  - `46770` moved beyond generic NodeNext architecture to the exact `loadModuleFromFile` branch that disables implicit extension lookup in ESM mode and added the closest repo-local test fixture.
  - retrieval quality therefore improved modestly without sufficiency regression, but retrieval latency increased by 86% and 126%, gross tokens increased by 100% and 166%, and uncached tokens increased by 53% and 171% respectively.
  - retain the prompt/schema as an experimental quality-oriented variant for now; it is not suitable as the default efficiency profile without a bounded-search follow-up.
- Verification:
  - `python -m py_compile services/retrieval/codex/provider.py tests/test_codex_provider.py`
  - `python -m unittest tests.test_codex_provider`
  - `.venv\Scripts\python.exe -m unittest tests.test_codex_provider tests.test_coderepoqa_retrieval` passed 11 tests.
  - both strict schemas were accepted by real `codex exec --output-schema` runs.

## 2026-06-22

### Added: Codex Evidence Provider Retrieval Mode

- Intended stage boundary:
  - add a workspace config switch, `retrieval.mode`, with `workspace` preserving the existing
    CGC/BM25/Qdrant path and `codex` delegating evidence discovery to `codex exec`,
  - keep Codex as an evidence provider only; response generation still consumes normal
    `EvidenceItem` records through the existing explanation framework,
  - run Codex in the currently selected workspace with read-only sandboxing and schema-constrained
    output.
- Expected quality impact:
  - avoids spending implementation effort on another code retrieval stack when Codex can already
    navigate the selected repository,
  - lets experiments focus on explanation structure, evidence transformation, and supportive data.
- Expected token impact:
  - local retrieval tokens from Step 2 and refinement are replaced by Codex usage,
  - Qdrant embedding/indexing work is skipped in `codex` mode,
  - total cost depends on the active Codex authentication path and selected model
    (`gpt-5.4-mini` by default).
- Known regression risks:
  - Codex evidence selection is less deterministic than the local retriever,
  - model availability depends on the active Codex/API entitlement,
  - broad prompts can make Codex inspect unrelated files or post-resolution corpus data,
  - line ranges returned by Codex can be stale if the workspace changes during a run.
- Comparison plan:
  - run the same CodeRepoQA prompt once with `retrieval.mode=workspace` and once with
    `retrieval.mode=codex`,
  - compare selected files, evidence line ranges, `coverage_status`, `sufficient`, response quality,
    and token/cost metadata,
  - record run IDs after the first real Codex-backed run.
- Verification so far:
  - `python -m py_compile services\retrieval\codex\provider.py services\retrieval\server.py services\retrieval\config.py`
  - `npm run web:build`
  - backend smoke check confirmed `codex` mode reports `index_status=codex_mode` and uses
    placeholder Qdrant/embedding config instead of local indexing.
- Measured Codex CLI run:
  - case: `microsoft-TypeScript-6307`,
  - model/auth: `gpt-5.4-mini` through the connected Codex subscription,
  - broad workspace attempt timed out before `turn.completed`, so no token total was recorded,
  - constrained run selected `issue.json` and `verification.json`; observed Codex usage from
    `turn.completed`: `90,193` input tokens, `59,392` cached input tokens, `3,606` output tokens,
    and `2,585` reasoning output tokens,
  - durable rerun that read the full issue JSON including comments recorded `182,189` input tokens,
    `153,088` cached input tokens, `2,675` output tokens, and `1,432` reasoning output tokens,
  - compared with the existing TypeScript 35468 workspace baseline average of `11,461` retrieval
    tokens, Codex agent retrieval is materially more token-expensive unless inputs are pre-filtered
    before handoff.

### Changed: CodeRepoQA Codex Retrieval Uses Sanitized Issue Packet

- Intended stage boundary:
  - keep CodeRepoQA prompt construction shared across retrieval modes via the visible-only
    `_user_prompt(title, initial_body)` packet,
  - select `workspace` or `codex` retrieval mode in the testcase runner config/CLI,
  - keep `verification.json`, oracle fields, raw `issue.json`, QA data, and run artifacts out of
    the Codex retrieval prompt and tell Codex not to inspect them,
  - keep Codex output schema-compatible with the existing `EvidenceItem` transformation.
- Expected quality impact:
  - Codex should behave more like the VS Code/codebase workflow: issue text plus source workspace,
    rather than raw corpus-file summarization,
  - evidence can plug into the existing explanation transformation without changing response
    generation.
- Expected token impact:
  - removes the raw issue JSON/comment metadata cost from Codex mode,
  - Codex still spends agent tokens on source search and file-window outputs,
  - targeted search/read rules should reduce generated/localization/baseline output volume.
- Known regression risks:
  - Codex may still run broad searches or read large files despite instructions,
  - source-only retrieval can miss verification-only test fixtures unless tests are explicitly
    needed and searched,
  - Codex usage numbers include full agent transcript/tool output and are not directly comparable
    to local retrieval LLM prompt totals; for pipeline-efficiency comparisons, use gross
    `input_tokens + output_tokens`, while cached/uncached splits are only billing or marginal-cost
    context.
- Real run comparison:
  - case: `microsoft-TypeScript-35468`, using the sanitized visible issue packet plus the selected
    TypeScript workspace; these are existing trace measurements, not a fresh rerun during this
    changelog edit,
  - `run-20260622T-codex-sanitized-02`: `coverage_status=strong`, `sufficient=true`, selected
    `watch.ts`, `program.ts`, `builderState.ts`, and `declarations.ts`; oracle overlap `1`
    implementation file (`builderState.ts`); usage `2,617,132` input, `2,523,648` cached input,
    `12,796` output, `6,720` reasoning output, `2,629,928` gross input plus output, and
    `106,280` uncached input plus output.
    Retrieval-stage elapsed time was `217.509s` (`3m38s`); full orchestration elapsed time was
    `240.151s` (`4m00s`).
  - `run-20260622T-codex-sanitized-03`: after adding explicit targeted-search/read and generated
    directory guards, `coverage_status=strong`, `sufficient=true`, selected `declarations.ts`,
    `builderState.ts`, `builder.ts`, `program.ts`, and `tsbuildPublic.ts`; oracle overlap `2`
    implementation files (`builderState.ts`, `builder.ts`); usage `1,210,174` input, `1,140,224`
    cached input, `11,630` output, `6,333` reasoning output, uncached input plus output
    `81,580`; gross input plus output for the direct retrieval-token comparison is `1,221,804`.
    Retrieval-stage elapsed time was `198.406s` (`3m18s`); full orchestration elapsed time was
    `225.423s` (`3m45s`).
- Quality notes:
  - the third run found the key builder files and produced an explanation with evidence refs and
    understanding checks,
  - the evidence is conceptually strong for the subsystem but still broader than the local retriever,
    which previously kept `builder.ts` at rank 5 while using far fewer retrieval tokens.
- Time notes:
  - Codex mode has no separate local index-build phase, but pays agent search/read time on each
    retrieval run,
  - use the exact per-run records above instead of comparing only the `3m18s-3m38s` span.

### Benchmark: Same-Case Workspace vs Codex Retrieval Records

- `microsoft-TypeScript-35468`:
  - Codex mode has no local index build.
  - Codex `run-20260622T-codex-sanitized-02`: retrieval/evidence discovery `217.509s`
    (`3m38s`), full orchestration `240.151s` (`4m00s`), gross input plus output `2,629,928`,
    uncached input plus output `106,280`.
  - Codex `run-20260622T-codex-sanitized-03`: retrieval/evidence discovery `198.406s`
    (`3m18s`), full orchestration `225.423s` (`3m45s`), gross input plus output `1,221,804`,
    uncached input plus output `81,580`.
  - Workspace `run-20260622T124352Z` with the existing index directory present: retrieval trace
    `149.854s` (`2m30s`), full orchestration `183.412s` (`3m03s`), retrieval LLM tokens `13,542`;
    trace events show CGC skipped the existing structural index, BM25 was reused, and workspace
    index reuse completed after `8.037s`.
  - Workspace first-run index prep for the same case remains separate: observed normal CGC indexing
    `1871.59s` (`31m12s`) and `SKIP_EXTERNAL_RESOLUTION=true` indexing `1070.79s` (`17m51s`);
    estimator output for the measured `207` graph-indexable file snapshot is normal `23m-42m` and
    skip-external `13m-24m`.
  - Short quality comparison: Codex run 03 had stronger oracle overlap (`2` implementation files)
    and `strong/sufficient=true`; the fresh workspace reuse run still found `builder.ts` in the top
    five but ended `partial/sufficient=false`, while prior workspace baselines were
    `strong/sufficient=true` with an average of `11,461` retrieval tokens.
- `microsoft-TypeScript-6307`:
  - Codex mode has no local index build.
  - Codex `run-20260622T130116Z`: retrieval/evidence discovery `90.071s` (`1m30s`), full
    orchestration `112.736s` (`1m53s`), gross input plus output `259,281`, uncached input plus
    output `28,369`.
  - Workspace first run `run-20260622T124840Z`: retrieval trace `548.390s` (`9m08s`), full
    orchestration `567.795s` (`9m28s`), retrieval LLM tokens `12,088`; observed index prep
    completed at `439.425s` (`7m19s`) from retrieval start.
  - Workspace prepared-index run `run-20260622T125817Z`: retrieval trace `127.620s` (`2m08s`), full
    orchestration `155.308s` (`2m35s`), retrieval LLM tokens `12,281`; trace events show index reuse
    completed after `2.740s`.
  - Short quality comparison: file overlap is not measurable for this question/usage case because
    its verification oracle intentionally lists no implementation, test, or documentation files;
    therefore both runs necessarily report `0` overlap. The workspace prepared run and Codex run
    both reported `strong/sufficient=true` based on their retrieved evidence, while quality should
    be judged here by agreement with the declaration-emit/public-API responsibility and hidden
    resolution rather than by file overlap.
- `microsoft-TypeScript-6`:
  - Codex mode has no local index build.
  - Codex `run-20260622T225727Z`: retrieval/evidence discovery `230.523s` (`3m51s`), full
    orchestration `270.608s` (`4m31s`), gross input plus output `1,784,170`, uncached input plus
    output `117,610`.
  - Workspace `run-20260622T230942Z`: retrieval trace `243.217s` (`4m03s`), full orchestration
    `276.302s` (`4m36s`), retrieval-stage LLM tokens `12,170` (`10,219` prompt, `1,951`
    completion, `2,304` cached prompt tokens). This comparison became valid only after fixing two
    local workspace regressions encountered during the rerun: the synthesis decision rename
    (`missing_areas` vs `missing_roles`) and a stale `_coverage_status(...)` call signature.
  - Short quality comparison: both runs ended `coverage_status=strong` and `sufficient=true`, and
    both reached implementation overlap `5`. Codex found a better pre-feature architecture path
    (`scanner.ts`, `utilities.ts`, `parser.ts`, `types.ts`, `checker.ts`), while workspace aligned
    more directly with the landed implementation oracle by surfacing `diagnosticMessages.json` and
    `declarationEmitter.ts` in the top five.
- Runner note:
  - `microsoft-TypeScript-6307` exposed a snapshot-resolution edge case where JSON null
    `commit_id` values became the string `"None"` and a missing historical event commit aborted the
    run; the runner now ignores null or locally unavailable event commits and falls back to the
    timestamp-based snapshot path.

### Changed: CGC 0.5.1 Upgrade And Complete-Index Guard

- Intended stage boundary:
  - keep CGC as the production structural backend after removing the experimental SCIP spike,
  - require a completed CGC marker before treating a repo-local Kuzu DB as reusable,
  - clean `cgc-kuzu`, `cgc-kuzu.wal`, and the completion marker when CodeRepoQA rebuilds indexes or CGC indexing fails.
- Expected quality impact:
  - avoids silently reusing timeout-created partial CGC databases,
  - makes failed structural indexing loud instead of letting later retrieval behave unpredictably.
- Expected token impact:
  - no retrieval-token increase on prepared indexes,
  - failed or missing CGC indexes now stop before expensive downstream retrieval instead of producing partial evidence from stale graph state.
- Known regression risks:
  - existing CGC databases created before this marker change must be rebuilt once,
  - clean full CGC indexing can still exceed the interactive timeout on moderately sized TypeScript snapshots.
- Measurement:
  - upgraded `codegraphcontext` from `0.4.11` to `0.5.1`,
  - active TypeScript snapshot with narrowed excludes still timed out after `600s` on clean CGC indexing:
    `run-20260622T000846Z`,
  - `SKIP_EXTERNAL_RESOLUTION=true` also timed out after `600s` with a clean Kuzu DB:
    `run-20260622T002314Z`,
  - a reuse run after a timeout-created partial DB completed but was not acceptable as a deterministic success:
    `run-20260622T003406Z`, `coverage_status=partial`, `sufficient=false`, oracle
    `src/compiler/builder.ts` at rank `5`.
- No-timeout follow-up measurement:
  - normal CGC completed indexing in `1871.59s` on the `microsoft-TypeScript-35468` snapshot after
    narrowed excludes:
    `run-20260622T012442Z`, retrieval `coverage_status=strong`, `sufficient=true`,
    oracle `src/compiler/builder.ts` at rank `5`, but explanation generation failed after retrieval
    because the model returned no valid understanding checks,
  - `SKIP_EXTERNAL_RESOLUTION=true` completed indexing in `1070.79s`:
    `run-20260622T020134Z`, retrieval `coverage_status=strong`, `sufficient=true`,
    oracle `src/compiler/builder.ts` at rank `5`, response generation succeeded,
  - this makes `SKIP_EXTERNAL_RESOLUTION` useful for elapsed time on this case, but still too slow
    for interactive indexing at about `18m`.
- Retrieval elapsed-time note:
  - the full CodeRepoQA retrieval trace for `run-20260622T012442Z` lasted `2099.987s`
    (`35m00s`) because it includes normal CGC indexing plus retrieval,
  - the full CodeRepoQA retrieval trace for `run-20260622T020134Z` lasted `1252.904s`
    (`20m53s`) because it includes `SKIP_EXTERNAL_RESOLUTION=true` CGC indexing plus retrieval,
  - these timings should not be compared as steady-state retrieval latency after an index is
    already prepared; they are first-run/index-build timings.
- Follow-up behavior:
  - index readiness now reports the CGC structural index as missing/stale unless `cgc-kuzu.complete.json` exists,
  - index estimates now include separate CGC structural time/risk fields in addition to BM25/Qdrant chunk estimates,
  - the CGC estimate is calibrated from the no-timeout TypeScript 35468 measurements and reports both
    normal CGC and `SKIP_EXTERNAL_RESOLUTION=true` ranges; for the measured `207` graph-indexable
    file snapshot it estimates normal `23m-42m` and skip-external `13m-24m`, covering the observed
    `31m` and `18m` runs.
- Workspace retrieval indexing estimate:
  - keep index preparation separate from retrieval-token comparisons: normal CGC indexing is
    estimated at `23m-42m` for the `microsoft-TypeScript-35468` snapshot after exclusions (`207`
    graph-indexable files), while `SKIP_EXTERNAL_RESOLUTION=true` is estimated at `13m-24m`,
  - observed index-build times were `1871.59s` (`31m12s`) and `1070.79s` (`17m51s`) respectively,
  - after the index exists, workspace retrieval should be measured separately from this upfront
    structural indexing cost.

## 2026-06-21

### Changed: CGC Ignore Handling For CodeRepoQA

- Intended stage boundary:
  - keep CodeRepoQA exclusions flowing through the same `.cgcignore` path used by normal workspace indexing,
  - apply repo-specific excludes before CGC graph indexing, BM25, and Qdrant indexing.
- Expected quality impact:
  - less noise from TypeScript fixture and generated-test folders,
  - more trustworthy CodeRepoQA runs because the test harness and UI use the same exclusion mechanism after config is passed in.
- Expected token impact:
  - lower indexing and retrieval token pressure for large repos by removing irrelevant candidate files before indexing.
- Known regression risks:
  - over-broad repo-specific excludes can hide useful test-only evidence,
  - the local CGC package patch is inside `.venv` and must be reapplied if the environment is rebuilt from scratch.
- Comparison method:
  - verify CGC discovery excludes configured subfolders on the active TypeScript snapshot,
  - verify an isolated CGC CLI index does not persist symbols from an ignored path.

### Verification: CGC Ignore Handling For CodeRepoQA

- Removed stale CGC DB directories/files from the main workspace, global CGC context, and testcase indexes.
- Confirmed only one `codegraphcontext` install is active: `.venv`, version `0.4.11`; no global Python import was found.
- Patched local CGC parser to strip a UTF-8 BOM before parsing `.cgcignore` patterns.
- Isolated CGC CLI proof:
  - `src/keep.ts` remained searchable,
  - `tests/cases/drop.ts` was not searchable after `.cgcignore` contained `tests/cases/`.
- Active TypeScript CodeRepoQA snapshot discovery:
  - first pass graph-indexable files: `537`,
  - final narrowed graph-indexable files: `207`,
  - final BM25/Qdrant document count: `13,378`,
  - `tests`, `lib`, `loc`, `scripts`, `src/testRunner`, `src/harness`, `src/lib`, and `src/loc`
    absent from CGC discovery.
- Clean rebuild attempts:
  - `run-20260621T152947Z`: failed on CGC timeout after `180s`,
  - `run-20260621T153424Z`: failed on CGC timeout after `600s`,
  - `run-20260621T154611Z`: failed on CGC timeout after `600s` with the narrowed exclude set.
- CGC timeout caveat:
  - despite the timeout, the produced repo-local Kuzu DB was queryable and found
    `createBuilderProgram` in `src/compiler/builder.ts`,
  - follow-up reuse run `run-20260621T155705Z` skipped the existing CGC DB, rebuilt BM25 and Qdrant,
    and completed retrieval with `coverage_status=strong`, `sufficient=true`.
- Successful reuse-run scorecard:
  - retrieved source files: `6`,
  - oracle overlap: `src/compiler/builder.ts` at rank `5`,
  - Qdrant collection:
    `guided_intelligence_retrieval_role_scoped__microsoft_typescript_35468__a27de1ce`,
  - Qdrant points: `13,378`.
- Automated tests:
  - `python -m py_compile services/retrieval/cgcignore.py services/retrieval/tools/cgc.py services/retrieval/server.py services/retrieval/workspace.py testing/codeRepoQA/run_case.py`
  - `python -m unittest tests.test_retrieval_server tests.test_workspace_retrieval`
  - 97 tests passed.
  - Later `python -m py_compile testing/codeRepoQA/run_case.py` passed after tightening TypeScript
    excludes and raising the CodeRepoQA CGC timeout to `600s`.

## 2026-06-20

### Added: Bounded LangGraph Connected-Source Context Stage

- Intended stage boundary:
  - run after deterministic prompt evidence and before Step 2 repository-context construction,
  - use enabled provider/source-key connector handles rather than source-category grouping,
  - let selected connected context refine code terms, files, symbols, and subqueries,
  - require explicit selected document IDs before connected text can become final evidence.
- Expected quality impact:
  - improve code retrieval for product-language prompts by translating live issue, PR, note, and
    management-tool context into compact code-retrieval signals,
  - reject irrelevant or stale provider text before it can steer code retrieval,
  - preserve code evidence as the authority for code-behavior claims.
- Expected token impact:
  - no added tokens when no connected source is selected,
  - approximately 2,000-2,600 graph tokens when live sources are queried in the measured TypeScript
    case,
  - selected connected excerpts can increase later Step 2 input in addition to graph tokens.
- Known regression risks:
  - broad provider searches can add latency and tokens even when all results are rejected,
  - provider AND-search behavior can miss relevant human text whose title has little prompt overlap,
  - stale or terminology-only text can misdirect code retrieval unless relevance, contribution,
    currentness, and confidence gates all hold,
  - graph LLM timeouts fail the stage explicitly rather than silently changing behavior.
- Comparison method:
  - two real no-source baselines,
  - irrelevant, helpful single-source, stale/conflicting, and combined-source TypeScript runs,
  - natural conversational fixtures in Obsidian, a GitHub issue, and a GitHub pull request,
  - compare run IDs, `coverage_status`, `sufficient`, retrieval tokens, graph tokens, connected IDs,
    and final code paths.

### Verification: Bounded LangGraph Connected-Source Context Stage

- Automated tests:
  - `python -m unittest tests.test_connected_context tests.test_mcp_connected_sources tests.test_retrieval_server tests.test_workspace_retrieval tests.test_coderepoqa_retrieval`
  - 129 tests passed.
- UI regression build:
  - `npm run web:build`
  - passed; this change has no new UI surface.
- No-source baselines:
  - `run-20260620T194600Z-87c934b6`: `strong`, `sufficient=true`, 11,452 retrieval tokens,
  - `run-20260620T195057Z-0c1b15b4`: `strong`, `sufficient=true`, 11,470 retrieval tokens,
  - no connected graph LLM calls or connected events in either run.
- Rejection checks:
  - `run-20260620T195721Z-8ad9b1a0`: irrelevant sources selected nothing; `strong`,
    `sufficient=true`, 14,011 retrieval tokens, 2,151 graph tokens,
  - `run-20260620T204228Z-b6abc84f`: stale/conflicting sources selected nothing; `strong`,
    `sufficient=true`, 13,995 retrieval tokens, 2,510 graph tokens.
- Helpful-source checks:
  - Obsidian `run-20260620T200036Z-2b26f442`: selected one note; 14,538 retrieval tokens,
  - GitHub issue `run-20260620T201944Z-aedc6d1e`: selected one issue; 14,533 retrieval tokens,
  - GitHub PR `run-20260620T202607Z-7e793a03`: selected one PR; 14,848 retrieval tokens,
  - combined final `run-20260620T205158Z-4d193726`: all three documents informed context, while
    the two-evidence cap retained the issue and PR; 15,439 retrieval tokens and 2,600 graph tokens.
- Failed experiments retained for diagnosis:
  - `run-20260620T195407Z-6ee8d055` exposed terminology-only over-selection and caused the
    contribution/code-signal gate,
  - `run-20260620T200440Z-0c8a63bc` failed explicitly on graph LLM timeout; retry succeeded,
  - `run-20260620T202931Z-607b47f1` exposed stale-context over-selection and caused the
    currentness/confidence gate.
- Quality conclusion:
  - all successful runs remained `coverage_status=strong` and `sufficient=true`,
  - all kept the same five final code paths: checker, diagnostics, emitter, parser, and types,
  - useful context improved query-plan specificity but not code-file recall for this explicit prompt,
  - a single useful source cost about 27% more retrieval tokens than baseline; combined sources cost
    about 35% more,
  - retain the bounded stage, but add an adaptive pre-query need gate before broadening evaluation.

## 2026-06-18

### Added: Protocol Relationship Graph Helper

- Intended stage boundary:
  - run after required-role recovery and before deterministic coverage/evidence selection,
  - keep relationship discovery in `services/retrieval/pipeline/protocol_graph.py`, separate from `workspace.py`,
  - extract concrete frontend API literals from accepted frontend candidates such as `requestJson<T>("/index/estimate")`, `fetch("/...")`, and `axios.get("/...")`,
  - rank extracted route literals against the target bucket query so issue-specific routes are tried before generic endpoints,
  - scan likely backend route/handler files for matching route string literals,
  - extract high-signal prompt/message literals such as `Error parsing expression` or `expects a method`,
  - scan likely diagnostics/parser/validator files for exact message fragments,
  - promote normal source-code `RetrievalCandidate` records with `retrieval_path=protocol_route_bridge` or `retrieval_path=protocol_message_bridge`.
- Expected quality impact:
  - improve UI-to-backend owner discovery when retrieval finds a frontend API wrapper but misses the server handler,
  - make string/protocol relationships visible even when CGC cannot infer the relationship from dynamic request wrappers or diagnostic string construction,
  - improve recovery for issue prompts whose exact error/warning text appears in parser, directive, checker, validator, or diagnostic files,
  - keep promotions explainable through exact literal/fragment matches instead of semantic guesswork.
- Expected token impact:
  - no extra LLM prompt tokens directly from the helper because it is deterministic,
  - possible indirect token increase when promoted relationship candidates give late synthesis/response generation more evidence to assess,
  - no embedding-token change because this uses local file scans over already-indexed workspace files.
- Known regression risks:
  - exact string matching will not resolve template-only routes or routes assembled entirely from variables,
  - diagnostic messages assembled from several string fragments can still be missed unless one stable fragment appears in the prompt,
  - broad API wrapper snippets can expose many routes; route ranking mitigates this but may still promote a nearby route group span,
  - message-literal scans are intentionally limited to diagnostics/parser/validator-like source paths to avoid turning every matching string into owner evidence.
- Comparison method:
  - focused unit coverage for typed frontend calls, backend route promotion, and prompt-message literal promotion,
  - real workspace pipeline runs against this repo with a UI `requestJson<IndexEstimate>("/index/estimate")` prompt,
  - real CodeRepoQA runs against TypeScript and Vue cases,
  - compare run IDs, coverage, sufficiency, selected evidence, protocol bridge events, tool calls, and observed OpenAI usage totals from trace `usage` fields.

### Verification: Protocol Relationship Graph Helper

- Focused tests:
  - `python -m unittest tests.test_workspace_retrieval.WorkspaceRetrievalStageTests.test_protocol_relationship_bridge_promotes_matching_backend_handler tests.test_workspace_retrieval.WorkspaceRetrievalStageTests.test_protocol_graph_discovers_ranked_route_relationship_candidate tests.test_workspace_retrieval.WorkspaceRetrievalStageTests.test_protocol_graph_discovers_prompt_message_literal_candidate`
  - passed.
- Compile check:
  - `python -m py_compile services\retrieval\workspace.py services\retrieval\pipeline\protocol_graph.py tests\test_workspace_retrieval.py`
  - passed.
- Broader test note:
  - `python -m unittest tests.test_workspace_retrieval` still has an unrelated pre-existing failure in `test_role_retarget_queries_add_role_specific_entrypoint_terms`; expected query string contains `parser syntax tokens ...`, current output contains `input parsing request handling ...`.
- Real run comparison:
  - Before typed-route support:
    - run ID: `run-20260618T113308Z-route-bridge`
    - `coverage_status=partial`, `sufficient=False`
    - selected refs did not include `services/retrieval/server.py`
    - selected count: 7, tool calls: 289
    - observed OpenAI usage from traces: 11,683 prompt + 3,268 completion = 14,951 total tokens
  - After typed-route extraction, before route ranking:
    - run ID: `run-20260618T113646Z-route-bridge-v2`
    - `coverage_status=partial`, `sufficient=False`
    - promoted `repo-pre:services/retrieval/server.py:L825-L852`
    - route list started with generic `/health`, while the promoted span still contained `/index/estimate`
    - selected count: 4, tool calls: 478
    - observed OpenAI usage from traces: 19,677 prompt + 4,262 completion = 23,939 total tokens
  - Final route-ranked run:
    - run ID: `run-20260618T114148Z-route-bridge-v3`
    - `coverage_status=partial`, `sufficient=False`
    - bridge event promoted `repo-pre:services/retrieval/server.py:L825-L864`
    - ranked routes started with `/index/estimate`, then `/index/prepare`
    - final response evidence included `ui/src/api.ts`, `services/retrieval/server.py`, and `ui/src/App.tsx`
    - selected count: 5, tool calls: 485
    - observed OpenAI usage from traces: 17,643 prompt + 4,147 completion = 21,790 total tokens
  - Final extracted-helper run:
    - run ID: `run-20260618T172205Z-protocol-graph-final`
    - `coverage_status=partial`, `sufficient=False`
    - protocol event promoted `repo-pre:services/retrieval/server.py:L825-L864`
    - routes started with `/index/estimate`, then `/index/prepare`
    - selected count: 5, tool calls: 314
    - observed OpenAI usage from traces: 18,319 prompt + 4,298 completion = 22,617 total tokens
- TypeScript CodeRepoQA measurement:
  - run ID: `run-20260618T180628Z-protocol-graph-final`
  - `coverage_status=partial`, `sufficient=False`
  - selected refs included `src/compiler/types.ts`, `scanner.ts`, `parser.ts`, `diagnosticMessages.json`, and `emitter.ts`
  - protocol helper detected abstract-related missing diagnostic terms such as `cannot invoke abstract members through super`, but promoted no refs because those diagnostics do not exist in the pre-fix snapshot
  - selected count: 10, tool calls: 260
  - observed OpenAI usage from traces: 17,968 prompt + 4,583 completion = 22,551 total tokens
- Vue CodeRepoQA measurement:
  - initial protocol-message run ID: `run-20260618T184200Z-protocol-graph-final`
    - detected terms including `Error parsing expression` and `expects a method`, but promoted no refs because exact refs were already present or recovered elsewhere by that point,
    - final refs were weak for the desired parser/diagnostic owner mix in that run.
  - after allowing message edges to reuse a path already accepted under another role:
    - run ID: `run-20260618T185039Z-protocol-message-final`
    - `coverage_status=partial`, `sufficient=False`
    - final refs included `src/exp-parser.js:L29-L108`, `src/exp-parser.js:L73-L152`, and `src/directive.js:L81-L160`
    - diagnostics bucket was weak with `src/exp-parser.js:L73-L152` and `src/directive.js:L121-L200`
    - protocol event still promoted no new refs in this run because normal recovery already had the diagnostic owner refs before the bridge, but the focused unit test proves the message edge can promote the same pattern when missing
    - selected count: 10, tool calls: 307
    - observed OpenAI usage from traces: 17,919 prompt + 4,716 completion = 22,635 total tokens
- Quality notes:
  - route edges fixed the specific self-repo miss: backend route evidence now survives to final evidence for the UI route prompt,
  - TypeScript shows the helper does not hallucinate nonexistent abstract diagnostics; this is a useful no-promotion result,
  - Vue shows the next useful edge family is diagnostic/message ownership and possibly expression grammar/data-shape relationships; the current message edge is safe but did not materially improve the final run when normal recovery already found `exp-parser.js`,
  - sufficiency stayed false in all measured runs because missing/weak roles remain outside what exact protocol-string edges can solve alone,
  - this should remain an enrichment/helper stage, not a replacement for CGC/Qdrant/role validation.

## 2026-06-15

### Added: MCP Connected Source Adapter

- Intended stage boundary:
  - add MCP as a query-time connected-source adapter before Step 2 planning,
  - normalize MCP tool results into existing `ConnectedSourceDocument` records,
  - pass bounded connected-source snippets into Step 2 planning,
  - allow policy-approved, prioritized connected documents to become final evidence with `retrieval_path=connected_source`,
  - keep source-code/document retrieval on the existing CGC + Qdrant path,
  - keep MCP sources disabled unless `WorkspaceRetrievalConfig.mcp_connected_sources` is explicitly configured,
  - map MCP results into existing source categories such as `issue_tracker`, `pull_request`, and `notebooklm` rather than adding a generic evidence category.
- Expected quality impact:
  - make issue/PR-like external context visible to the planner through a common connector layer,
  - preserve existing code retrieval quality when no MCP source is configured,
  - improve source extensibility for GitHub and future sources without coupling retrieval to one provider.
- Expected token impact:
  - no retrieval token change when no MCP source is configured,
  - small planner prompt increase when MCP documents are returned because connected-source IDs, titles, metadata, and bounded snippets become visible before Step 2,
  - no Qdrant embedding/token impact because MCP documents are not indexed in this first pass.
- Known regression risks:
  - MCP result normalization is schema-flexible but shallow, so provider-specific fields may need adapter-specific mappings later,
  - query-time MCP calls can add latency or fail independently of local retrieval,
  - connected documents can now become evidence, but they do not satisfy code-owner coverage gates; this avoids letting external discussion replace required source-code evidence.
- Comparison method:
  - focused unit tests use a fake stdio MCP server to verify JSON-RPC tool calls, normalization, source-policy filtering, registry queryability, and trace logging,
  - broader real pipeline token comparison is not meaningful yet because the adapter is disabled by default and no real GitHub MCP source is configured for the benchmark runs.

### Verification: MCP Connected Source Adapter

- Focused tests:
  - `python -m unittest tests.test_mcp_connected_sources`
  - passed with fake stdio MCP source returning an issue-like result.
- Compile check:
  - `python -m py_compile services\retrieval\config.py services\retrieval\workspace.py services\retrieval\step2\step2.py services\retrieval\mcp\stdio_client.py services\retrieval\mcp\adapters.py tests\test_mcp_connected_sources.py`
  - passed.
- Real retrieval-token measurement:
  - not run for this slice because no MCP source is configured by default, so existing benchmark pipeline behavior and retrieval token totals should remain unchanged.
  - when a real GitHub MCP source is configured, the next comparison should record the run ID, `coverage_status`, `sufficient`, retrieval token totals, returned MCP source refs, and any final-evidence changes.

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

### Changed: Compact Late Assessor With Deterministic Pre-Gate

- Intended stage boundary:
  - keep planner LLM unchanged,
  - allow the existing deterministic coverage gate to synthesize an accepted decision before calling the late assessor when all required roles are already locally strong,
  - reduce late-assessor payload size when the assessor is still needed,
  - preserve accepted full-file owner artifacts by allowing them to materialize into local spans even when the assessor also lists the file artifact as rejected.
- Expected quality impact:
  - preserve TypeScript `strong / sufficient=True`,
  - preserve Vue return of `src/exp-parser.js`,
  - avoid treating contradictory accepted/rejected file-level assessor output as a reason to drop concrete diagnostic spans.
- Expected token impact:
  - skip late-assessor calls in cases already proven by deterministic coverage,
  - reduce every remaining late-assessor prompt by sending fewer helper queries, refs, and shorter snippet previews.
- Known regression risks:
  - too-small assessor previews can hide the exact line that lets the assessor accept a role,
  - accepting file-level artifacts for span expansion can add secondary evidence that the assessor did not fully endorse,
  - the deterministic pre-gate may not fire often until earlier local role statuses become stronger before late assessment.
- Comparison method:
  - reran the real `run-case` pipeline once on Vue issue 242 and TypeScript issue 6 for each slice,
  - compared coverage, sufficiency, retrieved files, LLM calls, and retrieval tokens from trace usage.

### Verification: Compact Late Assessor With Deterministic Pre-Gate

- Deterministic pre-gate only:
  - Vue run: `C:\Programming\guidedInteligence_testcases\vuejs-vue-242\runs\run-20260614T090131Z-det-pre-gate`
    - retrieved files: `src/directives/model.js`, `src/text-parser.js`, `src/directive.js`, `src/exp-parser.js`, `src/emitter.js`
    - `coverage_status=partial`, `sufficient=False`
    - retrieval LLM calls/tokens: `3 / 16149`
    - `late_assessor_skipped` did not fire; token reduction came from the run path requiring fewer assessor passes than the previous kept Vue run.
  - TypeScript run: `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260614T090347Z-det-pre-gate`
    - retrieved files: `src/compiler/types.ts`, `src/compiler/scanner.ts`, `src/compiler/checker.ts`, `src/compiler/diagnosticMessages.json`, `src/compiler/emitter.ts`, `src/compiler/parser.ts`
    - `coverage_status=strong`, `sufficient=True`
    - retrieval LLM calls/tokens: `3 / 14553`
    - `late_assessor_skipped` did not fire.
- Compact assessor payload only:
  - Vue run: `C:\Programming\guidedInteligence_testcases\vuejs-vue-242\runs\run-20260614T090855Z-compact-assessor-payload`
    - retrieved files: `src/directives/model.js`, `src/text-parser.js`, `src/directive.js`, `src/emitter.js`
    - `coverage_status=partial`, `sufficient=False`
    - retrieval LLM calls/tokens: `4 / 20640`
    - regression: `src/exp-parser.js` was lost from final retrieved files.
  - TypeScript run: `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260614T091127Z-compact-assessor-payload`
    - retrieved files: `src/compiler/types.ts`, `src/compiler/scanner.ts`, `src/compiler/checker.ts`, `src/compiler/diagnosticMessages.json`, `src/compiler/emitter.ts`, `src/compiler/parser.ts`
    - `coverage_status=strong`, `sufficient=True`
    - retrieval LLM calls/tokens: `3 / 12115`
  - conclusion: compact payload alone was not kept without the accepted-file span fix because Vue lost owner diagnostic evidence.
- Compact assessor payload plus accepted-file span recovery:
  - Vue run: `C:\Programming\guidedInteligence_testcases\vuejs-vue-242\runs\run-20260614T091458Z-accepted-file-span-compact`
    - retrieved files: `src/directives/model.js`, `src/text-parser.js`, `src/exp-parser.js`, `src/emitter.js`, `src/directive.js`
    - `coverage_status=partial`, `sufficient=False`
    - retrieval LLM calls/tokens: `3 / 13790`
  - TypeScript run: `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260614T091654Z-accepted-file-span-compact`
    - retrieved files: `src/compiler/types.ts`, `src/compiler/scanner.ts`, `src/compiler/checker.ts`, `src/compiler/diagnosticMessages.json`, `src/compiler/emitter.ts`, `src/compiler/parser.ts`
    - `coverage_status=strong`, `sufficient=True`
    - retrieval LLM calls/tokens: `3 / 12075`

### Conclusion: Compact Late Assessor With Deterministic Pre-Gate

- Kept compact late-assessor payload plus accepted-file span recovery.
- Compared to the previous kept assessor-strong-gate slice:
  - Vue: `25504 -> 13790` retrieval tokens while preserving `src/exp-parser.js`; quality remains `partial / sufficient=False`.
  - TypeScript: `14284 -> 12075` retrieval tokens while preserving `strong / sufficient=True`.
- Compared to the high-token 2026-06-13 baseline:
  - Vue: `71087 -> 13790`.
  - TypeScript: `54862 -> 12075`.
- The deterministic pre-gate is present but did not fire in these two benchmark runs; the measured win came from smaller assessor payloads and preserving line-span recovery for accepted file artifacts.

### Changed: Required Evidence Guard For Final Explanations

- Intended stage boundary:
  - keep retrieval and final explanation generation separate,
  - identify high-priority final-answer evidence from selected evidence using generic local predicates,
  - pass those anchors to the explanation generator as `required_evidence`,
  - validate visible Markdown citation coverage after generation and append a short grounded note only when a required anchor is still not visibly cited.
- Expected quality impact:
  - keep the beginner-friendly narrative style of the explanation generator,
  - prevent exact diagnostic or direct error-path evidence from being retrieved but omitted from the final answer,
  - avoid redundant repair sections when an overlapping same-file citation already covers the required evidence.
- Expected token impact:
  - small response-generation prompt increase from the added `required_evidence` payload,
  - no intended retrieval token increase.
- Known regression risks:
  - if a required anchor is too broad, the visible repair section can make an otherwise smooth answer feel bolted on,
  - overlapping citation detection handles line ranges, but not semantic equivalence across different files.
- Comparison method:
  - reran the real `run-case` pipeline once on Vue issue 242 and TypeScript issue 6,
  - inspected final `response_payload.content` and `used_evidence_refs`,
  - confirmed Vue visibly cites `src/exp-parser.js` and TypeScript remains coherent without an unnecessary repair section.

### Verification: Required Evidence Guard For Final Explanations

- First required-evidence response guard:
  - Vue run: `C:\Programming\guidedInteligence_testcases\vuejs-vue-242\runs\run-20260614T183314Z-required-evidence-response`
    - `coverage_status=partial`, `sufficient=False`
    - final `used_evidence_refs` included `repo-pre:src/exp-parser.js:L73-L152`
    - final answer mentioned `exp-parser.js`, but visible citation handling still needed tightening.
  - TypeScript run: `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260614T183520Z-required-evidence-response`
    - `coverage_status=strong`, `sufficient=True`
    - regression: an unnecessary `Evidence Not To Miss` repair section was appended for an overlapping diagnostics range.
- Visible citation coverage guard:
  - Vue run: `C:\Programming\guidedInteligence_testcases\vuejs-vue-242\runs\run-20260614T183857Z-visible-required-evidence`
    - `coverage_status=partial`, `sufficient=False`
    - retrieval LLM calls/tokens: `3 / 13193`
    - final `used_evidence_refs`: `repo-pre:src/exp-parser.js:L73-L152`, `repo-pre:src/directive.js:L81-L160`
    - final answer visibly cites `src/exp-parser.js:L73-L152`, preserving the strongest diagnostic anchor.
  - TypeScript run: `C:\Programming\guidedInteligence_testcases\microsoft-TypeScript-6\runs\run-20260614T184102Z-visible-required-evidence`
    - `coverage_status=strong`, `sufficient=True`
    - retrieval LLM calls/tokens: `3 / 12005`
    - final answer remains a coherent beginner-friendly overview and no longer appends a redundant repair section.

### Conclusion: Required Evidence Guard For Final Explanations

- Kept the visible required-evidence guard.
- The Vue answer now uses and visibly cites `src/exp-parser.js:L73-L152`, which contains the reported `Error parsing expression` path.
- TypeScript remains `strong / sufficient=True` and keeps a normal narrative explanation without a forced addendum.

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
- Added the legacy retrieval LLM continuity flag in `.env` and `.env.example`.
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
- Final `.env` state had the legacy retrieval LLM continuity flag disabled.
# 2026-08-07 — Selected evidence connections in explanation and question generation

- Stage boundary: after evidence organization and before explanation generation, pass only graph connections whose source and target are both in the selected evidence set. The graph informs narrative links and question targets; it does not prove claims or force one question per cluster.
- Legacy comprehension cleanup: `ComprehensionPlan`, its role-based concepts, and its consecutive-concept dependency builder were deleted. Initial generation now uses the intent flow, selected evidence, and selected evidence connections directly; follow-up teaching uses the accepted answer/story flow, question targets, and actual evaluation gaps.
- Compatibility policy: there is no legacy `ComprehensionPlan` fallback or parallel compatibility branch. Runs missing the new accepted-flow data do not silently reconstruct the old role-based teaching model.
- Expected quality impact: questions can target real control/data/configuration links instead of inferring relationships from evidence order. Intent question stems now also carry short intent-specific purposes.
- Expected token impact: a small generation-prompt increase proportional to the number of selected edges. The main run-to-run token variance still comes from changing Codex candidates and organizer selections.
- Regression risks: inferred edges could over-influence prose, clusters could be mistaken for mandatory question counts, or broad stem descriptions could make questions repetitive. The prompt explicitly keeps inferred links non-authoritative and question count dynamic.
- Matching-prompt comparisons (`Where is intent classification handled, and how does it flow into retrieval, explanation structure, and question generation?`):
  - Pre-change `run-20260806T215430Z-77b1072e`: `coverage_status=strong`, `sufficient=true`, 12 candidates / 8 selected, 16,702 organizer+generation LLM tokens, 2 questions.
  - Graph-context `run-20260806T221144Z-68891821`: `coverage_status=strong`, `sufficient=true`, 15 candidates / 12 selected, 20,801 organizer+generation LLM tokens, 2 questions. The generator received 1 selected edge; the questions moved toward the classification-to-generation handoff and contract-aligned follow-up checks.
  - Graph + stem-purpose descriptions `run-20260806T221913Z-4ec3cadf`: `coverage_status=strong`, `sufficient=true`, 16 candidates / 10 selected, 20,785 organizer+generation LLM tokens, 2 questions. Questions separated the classification-to-retrieval handoff from the intent-flow effect on explanation and checks.
  - Final cleaned path `run-20260806T222636Z-965a3cbf`: `coverage_status=strong`, `sufficient=true`, 16 candidates / 12 selected, 21,218 organizer+generation LLM tokens, 2 questions, 8 selected edges supplied, and zero explanation or question repairs. The output asked separately about the classification-to-retrieval/explanation handoff and why follow-up questions remain aligned with classified intent. No legacy comprehension plan was present.
- Interpretation: both changed runs kept two questions. The graph-only run produced two questions from one passed edge, while the description run had two evidence components but one question crossed their boundary. Evidence clusters are useful context, but are not a reliable question-count formula.
- Progressive hints experiment:
  - Replaced the singular `hint` field with an exact `direction -> focus -> scaffold` ladder generated from the same question, expected points, stages, evidence, and graph context. No singular-hint compatibility fallback remains.
  - Added hint-only repair with its own prompt. A rejected ladder is replaced without regenerating the question or expected answer points; the UI reveals one hint at a time.
  - Live run `run-20260806T225055Z-7ffa037b`: `coverage_status=strong`, `sufficient=true`, 2 questions, 32,112 organizer+generation+repair LLM tokens, zero explanation repairs, zero hint repairs, and one question-only repair. The valid second question was preserved while only the rejected first question was regenerated. Both final ladders progressed from a reasoning operation to a concrete code relationship and then a partial causal scaffold without copying the expected points verbatim. The extra question-repair call accounted for 9,347 tokens, so this run should not be used as a clean estimate of the normal hint-ladder token increase.

# 2026-08-08 - Obligation-driven native retrieval

- Stage boundary: the global intent call now also extracts request anchors, conceptual search terms, and ordered evidence obligations before either retrieval provider runs. Native retrieval resolves those obligations through exact CodeGraph anchors, Qdrant discovery, graph traversal, and deterministic coverage checks.
- Removed the old native Step2 role planner, role buckets, path/keyword ownership heuristics, and their recovery loops. They are not retained as a fallback path.
- CodeGraph exact symbol matches are authoritative only when the repository contains one exact node. Missing or ambiguous names remain semantic discovery terms; the removed fuzzy symbol operation cannot establish graph identity.
- Qdrant searches each obligation independently across all file roles. Semantic candidates must match obligation-specific terms before they can support an obligation, and CodeGraph expansion starts only from grounded candidates.
- Expected quality impact: fewer support-file false positives, explicit unresolved obligations/transitions, and better implementation-owner discovery. Expected token impact: one shared request-analysis LLM call; native graph traversal itself adds no LLM tokens.
- Regression risks: request-analysis obligations and symbol fields vary between LLM runs; excluded test trees can leave validation obligations unresolved; CodeGraph may not connect protocol or cross-format boundaries.
- Vue verification:
  - Before exact-anchor enforcement, `run-20260807T221550Z` incorrectly returned `strong/true`, selected watcher/patch evidence, and had zero oracle overlap.
  - `run-20260807T222937Z` returned `strong/true`, selected only the server/runtime `dom-props.js` implementation pair, and found the oracle in the top five. `domProps`, `renderVmWithOptions`, `VTextarea`, and `VTextField` remained unresolved exact symbols and were used only for semantic discovery.
- TypeScript verification:
  - `run-20260807T223034Z` returned `partial/false`, selected `moduleNameResolver.ts` and `sys.ts`, and found an oracle implementation in the top five. `fs.statSync` remained unresolved as an exact symbol; missing graph transitions prevented a false `strong` result.
- Historical native failure comparison:
  - Old `microsoft-TypeScript-45713` workspace run `run-20260623T102628Z` ended `failed/false` after the CGC index timed out at 600 seconds; it selected zero files and had no oracle overlap.
  - Current run `run-20260807T224650Z` completed `partial/false`, selected nine files, and found both known implementation owners: `executeCommandLine.ts` at rank 5 and `watch.ts` at rank 7. Both counted as implementation overlaps, with an oracle hit in the top five.
  - CodeGraph indexing took 9.4 seconds and obligation retrieval took 23.1 seconds. The 667.5-second total remained poor because the cold BM25/Qdrant stage rebuilt and embedded 16,453 chunks in 582 seconds. Structural indexing is no longer the timeout source; cold semantic indexing is now the dominant cost.

## Focused obligation-loop experiment - reverted

- Experimented with one-gap-per-round CodeGraph expansion, relationship-type hints, Qdrant ranking inside the graph frontier, structured LLM concept consolidation, stable snippet IDs, strict transition support, and nonfatal logging of invalid consolidation references.
- The experiment retained conservative evidence selection so loop quality could be measured independently from evidence minimization.
- `vuejs-vue-10803` baseline `run-20260807T222937Z` was `strong/true`, selected the implementation owner at rank 1, and used the existing obligation-graph path.
- Initial experiment `run-20260807T234015Z` was `partial/false`, selected only the correct owner at rank 1, but supported only one of six required obligations. It used 9,648 retrieval-consolidation tokens across three calls.
- Repair 1 `run-20260807T234301Z` was `partial/false`, selected four snippets, moved the owner to rank 2, and supported three of five obligations. It used 16,023 retrieval-consolidation tokens across four calls and logged one invalid semantic-transition reference without failing the run.
- Repair 2 `run-20260807T234654Z` was `partial/false`, moved the owner to rank 3 behind `.circleci/config.yml` and `types/test/ssr-test.ts`, and still left two of five obligations unresolved. It used 16,708 retrieval-consolidation tokens across four calls.
- The strict handoff rule behaved honestly, and dependency concepts eventually recovered the local falsy-value mechanism. The blocking instability was earlier: request analysis varied required obligations between runs, initial consolidation accepted noisy orientation snippets, and one-gap scheduling repeatedly spent the three-round budget on obligations that the issue snapshot could not fully establish.
- Per the two-repair stopping rule, the behavior was reverted before relationship-filter A/B testing, concept-driven expansion, or evidence minimization. No focused-loop or concept-consolidation fallback remains in production.

## Repository grounding and evidence-role correction

- Stage boundary: keep global request analysis provider-independent, then verify every extracted anchor against the selected repository before native evidence retrieval. Confirmation is intentionally only `confirmed_in_repository` plus matching locations; it does not encode testcase-specific source categories.
- Obligations reference exact extracted anchors and declare a general evidence role: implementation, test, configuration, documentation, or any. Every anchor records only whether it was confirmed in the selected repository and its matching locations. Unconfirmed anchors remain visible context but do not disable an otherwise valid obligation.
- Qdrant queries will combine the obligation description with its confirmed anchors and relevant request search terms. Hybrid scores remain discovery signals; obligation-specific file roles affect ranking so tests can prove expected behavior without replacing runtime implementation evidence.
- CodeRepoQA will stop applying repository-specific blanket exclusions. It will use the tool's generic cache/build/generated exclusions so benchmark indexing represents a user opening the same repository. Tests remain indexed and carry their `test` role; generated/baseline artifacts remain dynamically skipped by the indexer.
- Expected quality impact: recover explicit tests and paths, prevent unavailable prompt entities from blocking local sufficiency, and demote configuration/type orientation for runtime-mechanism obligations.
- Expected cost impact: larger semantic and structural indexes, especially in test-heavy repositories. Warm reuse should amortize this; cold-index runtime and document counts must be recorded.
- Regression risks: the request-analysis model may omit anchor references or choose the wrong evidence role; broad test indexing may increase cold runtime; role weighting may suppress unconventional implementation layouts.
- Request-analysis validation now requires bounded snake-case obligation IDs, at least one required obligation, and an acyclic dependency order. Unknown or forward dependency IDs are discarded during normalization instead of aborting the request; valid references to earlier obligations remain.
- Qdrant semantic discovery is filtered by each obligation's declared evidence role. Tests therefore remain searchable for expected behavior and regression obligations without competing against runtime owners for implementation obligations.

### Verification

- `python -m unittest tests.test_intent tests.test_obligation_retrieval tests.test_codegraph_tools tests.test_coderepoqa_retrieval` passed with 30 tests.
- Cold-scope run `run-20260808T014626Z` indexed 5,449 documents instead of the previous 1,306-document test-excluded scope. It confirmed the repository-prefixed test path but exposed a malformed one-obligation analysis and selected only the test helper plus an SSR benchmark (`partial/false`).
- After removing anchor-confirmation as an obligation gate, `run-20260808T015101Z` recovered `src/platforms/web/server/modules/dom-props.js` at rank 3 and the SSR test at rank 1. No configuration file was selected, but two required transitions remained unresolved (`partial/false`).
- A repeat, `run-20260808T015306Z`, selected only test evidence. The cause was role-unfiltered Qdrant top-k results: test chunks occupied the returned candidate window before role weighting ran.
- After filtering Qdrant by the requested evidence role, `run-20260808T015546Z` recovered the server `dom-props.js` owner at rank 5 and the SSR test, with no configuration evidence selected (`partial/false`).
- One repeat failed before retrieval because the model emitted an unknown obligation dependency. Normalization was changed to drop only the invalid dependency rather than hard-fail the request.
- Final repeat `run-20260808T015929Z` recovered `src/platforms/web/server/modules/dom-props.js` at rank 1 and `test/ssr/ssr-string.spec.js` at rank 5. The selected set contained implementation and test evidence and no configuration files. It remained `partial/false` because the current one-round graph traversal could not prove two conceptual transitions.
- Cleanup verification `run-20260808T020302Z` returned `strong/true` with `src/platforms/web/server/modules/dom-props.js` at rank 1, but request analysis again collapsed the issue into one implementation obligation and therefore omitted the regression test. This confirms that repository indexing and role filtering work, while LLM obligation decomposition remains unstable across identical prompts.
- The previous `run-20260807T222937Z` reported `strong/true` with the owner at rank 1, but its request analysis contained only one broad obligation and selected only two implementation snippets. The new result has better issue coverage and more honest transition reporting, but the focused expansion/stopping redesign is still required before native retrieval can regain `strong/sufficient` without collapsing the request.
- Per the two-repair stopping rule, no additional prompt heuristic or testcase-specific obligation was added. The next redesign must make obligation structure enforceable rather than relying on prose instructions to make the model consistently decompose a flow.
- Retrieval-specific LLM token totals are not currently emitted by the native run artifacts. No additional retrieval LLM stage was added in this correction; the only LLM-backed retrieval input remains global request analysis.

## Obligation decomposition stabilization

- Stage boundary: global request analysis now assigns every evidence obligation to one or two selected intent-contract stages before native retrieval begins. Core prerequisite stages must each be covered exactly once, causal stages must request repository-owner evidence, and a separate `requires_repository_handoff` flag distinguishes narrative ordering from transitions that retrieval must prove.
- Invalid obligation structure receives one explicit obligation-only LLM repair. The repair preserves the selected intents, anchors, and search terms and replaces only the obligation array. It is not a deterministic surrogate or a legacy retrieval fallback; a still-invalid repair fails the intent stage.
- Native retrieval treats contextual dependencies as story order rather than sufficiency gates. Required handoffs need a CodeGraph edge or a strict semantic handoff in which selected snippets on both sides share at least two repository-confirmed request anchors.
- Dependent obligations can reuse evidence from the supported dependency frontier when the evidence role and obligation terms match. This keeps the retrieval path moving through already grounded owner code instead of restarting every obligation from unrelated whole-repository semantic hits.
- Test-role obligations are narrowed to repository-confirmed explicit test paths when the request supplies them. Generated obligations still determine the query; no Vue-specific path or symptom is hardcoded.
- Expected quality impact: prevent a broad single obligation from satisfying a multi-stage request, preserve source-owner evidence through a causal flow, and expose genuinely missing test/transition evidence as partial coverage.
- Expected cost impact: structurally invalid request analysis adds one bounded LLM repair call. Native traversal itself remains deterministic. Retrieval-specific request-analysis token totals are still not emitted, so the extra-call cost is visible through latency but cannot yet be reported accurately.
- Regression risks: intent selection still varies across identical requests; pre-fix snapshots may not contain issue-proposed regression tests; generated bundles can outrank source files; strict handoffs can therefore make otherwise relevant evidence sets remain insufficient.

### Vue repair sequence

- Attempt 1, `run-20260808T025532Z`: `partial/false`; seven stage-bound obligations replaced the previous single broad obligation, but narrative dependencies were incorrectly treated as required transitions.
- Attempt 2, `run-20260808T025715Z`: `partial/false`; six obligations, with effect/cause still grouped and cause evidence drifting into tests.
- Attempt 3, `run-20260808T025925Z`: `partial/false`; seven obligations and the new handoff distinction worked, leaving only the implementation-to-test effect transition unresolved.
- Attempt 4, `run-20260808T030224Z`: `partial/false`; six obligations, with one strict semantic handoff supported, but generated bundle evidence broke the remaining state-to-effect transition.
- Attempt 5, `run-20260808T030454Z`: `strong/true`; six obligations, source owner at rank 1, explicit test at rank 4, and no unresolved required transitions after dependency-frontier reuse.
- Strict selected-evidence verification, `run-20260808T030657Z`: `strong/true`; eight obligations, source owner at rank 1, explicit test at rank 4, and no unresolved transitions. The semantic handoff was grounded by confirmed `domProps`, `textarea`, and `value` anchors in the selected snippets.
- Identical repeat `run-20260808T030816Z`: `partial/false`; seven obligations and no collapse, but generic test snippets left two transitions unresolved.
- Query-stability experiments `run-20260808T031047Z`, `run-20260808T031221Z`, and `run-20260808T031454Z`: all retained six to eight obligations but remained `partial/false`. Stage-purpose-only queries were too abstract, and later combined queries exposed two remaining problems: a missing proposed regression test in the pre-fix snapshot and generated Vue server-renderer bundles outranking source-owner evidence.

### Result

- The original instability is resolved: none of the ten post-change Vue runs collapsed to one broad obligation; every run produced six to eight obligations tied to the selected intent stages.
- End-to-end sufficiency is not yet stable: two of ten runs were `strong/true`. The remaining failures now occur during evidence discovery/transition proof rather than request decomposition, so further work should address generated-artifact ranking and absent-test handling separately instead of weakening the obligation contract.
- Cross-repository verification on `microsoft-TypeScript-35468` did not reach obligation retrieval. The first full-test semantic-index attempt ended with an embedding-service `RemoteDisconnected`; the retry wrote an approximately 1.3 GB local embedding cache but ended as `run-20260808T032638Z` with `failed/false` and `qdrant_index_sync_failed` after exceeding the indexing timeout. No obligation-quality conclusion is claimed from that run.
- The TypeScript result exposes a separate scalability regression in the realistic all-tests index scope. Per the two-failed-real-comparison rule, the run was not retried again and no repository-specific exclusion was silently restored.

## Prompt provenance, generated-file ranking, and reduced TypeScript scope

- Stage boundary: global request analysis now labels each obligation as `prompt` or `repository`. Prompt-sourced symptoms, expected outputs, and proposed assertions remain part of the retrieval story but cannot launch Qdrant/CodeGraph searches, become selected code evidence, or satisfy repository handoffs. Repository obligations remain the only source of selected code evidence.
- Exact prompt literals and code fragments are confirmed against indexed chunk text before they can become repository anchors. Missing exact text remains visible as `prompt_only`; it no longer steers repository search as if the proposed patch already existed.
- Generated-artifact treatment has two layers. Files above 3,000,000 decoded characters are omitted from semantic indexing. During candidate ranking, files above 200,000 bytes with no CodeGraph cross-file provenance are penalized, while near-duplicate candidates prefer the smaller copy with real incoming/outgoing repository connections.
- Expected quality impact: distinguish issue evidence from repository evidence, prefer canonical source modules over self-contained bundles, and keep legitimate large connected source files eligible. Expected token impact: no additional LLM call; smaller indexes reduce embedding volume when oversized files or explicit exclusions apply.
- Regression risks: CodeGraph can miss real provenance, so the 200 KB rule is a ranking penalty rather than an exclusion. The 3 MB hard ceiling may omit unusually large hand-maintained source. Prompt-source classification remains LLM-generated, although impossible role/handoff combinations are normalized deterministically.
- Vue pre-rule run `run-20260808T055407Z` was `partial/false`, selected six snippets, and still included `packages/vue-template-compiler/browser.js`; request analysis also merged prompt-supplied expected behavior into a repository obligation.
- Vue post-rule run `run-20260808T055746Z` was `strong/true`, selected nine snippets, kept the reported expected/actual behavior as prompt evidence, and selected no compiled Vue bundles. The source set included the server/runtime DOM-prop modules and SSR tests. This is not proof that support assessment is solved: several later obligations reused the same nodes and passed through `shared_node`, reflecting the remaining candidate-to-support weakness.
- Full TypeScript scope measured 14,825 files and 149,786 chunks, with a frontend estimate of 125.3-376 minutes. Explicitly excluding root `lib` and `tests/cases` reduced it to 620 files, 20,146 chunks, and 14.2 MB of source text; the conservative estimate remained 16.8-50.4 minutes, so the UI now warns whenever the upper estimate exceeds 15 minutes and recommends deselecting generated outputs or large corpus directories.
- Cold TypeScript run `run-20260808T060129Z` did not finish within 15 minutes. CodeGraph/BM25 completed in about two minutes, but embedding generation submitted 6,371 uncached chunks and completed 5,347 before timeout. The incremental JSON embedding cache grew to about 1.8 GB, exposing cache serialization as an additional scaling cost.
- Warm continuation `run-20260808T061719Z` completed in 6m32s with the same 20,146-document scope. Retrieval was `partial/false`, selected eight snippets, found one oracle overlap in the top five, and left three required transitions unresolved. The selected set still overrepresented test/server support files, so reduced indexing scope improved feasibility but did not fix final owner selection or decisive-support assessment.
- Native retrieval does not currently report request-analysis token totals, and this change adds no retrieval LLM stage; no token delta is claimed.
- File-role correction: the shared classifier now tokenizes directory names, including camel-case and separator-delimited forms. Paths under `testRunner`, `unitTests`, `test-cases`, and similar conventional test roots are classified as test evidence, while source filenames such as `nodeTests.ts` remain implementation. The duplicate classifier in the local repository-sketch tool was removed so BM25, Qdrant metadata, and repository sketches use one role definition.
- Qdrant consistency correction: collection signatures now include source category and sorted chunk metadata. Previously, a BM25 rebuild could change `file_role` while Qdrant retained the old payload because text and locations were unchanged; payload filtering then used stale roles.
- Before the actual Qdrant payload resync, `run-20260808T064917Z` recovered `src/compiler/builder.ts` at rank 4 and two oracle overlaps, but `testRunner` chunks still leaked through the stale implementation-role payload. It remained `partial/false` with one unresolved transition.
- After resync, `run-20260808T065349Z` contained no test-role candidates in implementation obligations. It remained `partial/false`; `src/compiler/builder.ts` was rank 5, while broad semantic matches in `diagnosticMessages.json` and server files still ranked above it. The remaining unresolved transition is therefore downstream of a cleaner role filter, but decisive owner discovery and support ranking are still incomplete.

## Graph-grounded implementation support and resource references

- Implementation obligations now accept only candidates classified as implementation evidence and mapped to a concrete CodeGraph node. Semantically similar files without an executable node remain discovery hints; test, configuration, and documentation candidates can establish only obligations that explicitly request those roles. Structurally connected candidates receive a small provenance bonus.
- Expected quality impact: message catalogues, configuration, tests, and documentation can still help discovery without being mistaken for the executable mechanism. Expected token impact: none; the change reuses existing CodeGraph mappings. The principal regression risk is a CodeGraph miss causing valid implementation evidence to remain unresolved rather than being accepted semantically.
- TypeScript verification `run-20260808T144535Z` completed in 111.7 seconds with `partial/false` and seven selected snippets. `src/compiler/diagnosticMessages.json` disappeared from accepted evidence, while `src/compiler/builder.ts` and `src/compiler/tsbuildPublic.ts` remained selected. The previously misleading catalogue match became an honest unresolved `stale_diagnostic_cause_and_effect` obligation; two required transitions also remained unresolved.
- Resource files now use one deterministic `resource_reference` resolver shared by native obligation transitions and evidence-graph construction. It accepts only an exact quoted `.md`, `.json`, `.yaml`, `.yml`, or `.toml` literal that resolves to the selected resource. A basename-only literal is accepted only when it identifies one unique descendant of the referring source directory. The previous uppercase-constant and basename matching heuristic was removed.
- Focused verification resolved the maintained repository edge from `services/intent/classifier.py` to `services/intent/prompts/request_analysis_obligation_repair.md` through the exact literal `request_analysis_obligation_repair.md`. Ambiguous basename fixtures are rejected, and the native transition resolver returns `supported/resource_reference` when CodeGraph has no Markdown edge.
- Attempted native run `run-20260808-resource-reference-native` reached CodeGraph synchronization in 2.3 seconds (`7,205` edges) but did not reach Qdrant or obligation traversal. The ad hoc run used the Guided Intelligence repository root while failing to exclude the locally stored `TypeScript`, `pandas`, and `vue` repositories. A one-entry exclusion-scope mismatch (`.codegraph` versus the cached manifest's `.codegraphcontext`) invalidated BM25 reuse and started rebuilding approximately 68,804 files and 1.41 million chunks from 2.4 GB of text. It was stopped after roughly ten minutes at about 4.6 GB resident memory. The intended Guided Intelligence-only scope is about 390 files and 4,357 chunks. This setup error is not counted as a resource-reference retrieval pass; the deterministic maintained-repository and pipeline-transition tests are the current verification.
- Corrected-scope run `run-20260808-resource-reference-corrected` indexed exactly 4,357 points in 146 seconds and completed in 225 seconds. It exposed a general retrieval contradiction: documentation obligations sent `file_role=documentation` together with `source_category=source_code`, so the exact Markdown target returned zero candidates. Confirmed explicit paths were also only constraining test obligations. The run was `partial/false` and is not accepted as resource-reference verification.
- Obligation discovery now derives Qdrant source category from evidence role and uses every confirmed explicit path whose file role matches the obligation. Documentation therefore searches the documentation category and exact code/document targets form the initial bounded frontier.
- File-role classification no longer requires implementation code to live under a hardcoded directory such as `src`, `lib`, or `core`. Recognized programming-language files are implementation after documentation, configuration, generated, and test exclusions have been applied. This correctly classifies code under `services` and unconventional repository layouts.
- BM25 scope manifests now include an explicit indexing-schema version. Changes to role or indexing semantics therefore force metadata reconstruction instead of reusing a scope-compatible but semantically stale index.
- A post-fix real retry using Codex CLI for request analysis reached native retrieval, but the first Qdrant semantic query failed with `HTTP 429 credit_balance_exhausted` from the configured embeddings endpoint. The corrected 4,357-point collection remains present, but final end-to-end resource-reference verification is blocked until embedding-query credits are available. No sparse-only fallback was introduced.
- After embedding access was restored, real web-pipeline run `run-20260808-resource-reference-final` completed in 81.9 seconds with `strong/true`, four selected snippets, and no unresolved obligations or transitions. The documentation-to-code dependency was supported as `resource_reference` through the exact `request_analysis_obligation_repair.md` literal, and the evidence graph emitted the same direct configuration relationship. Index synchronization covered 390 files and 4,362 current chunks and took 31.6 seconds; obligation retrieval took 1.7 seconds. This is the accepted end-to-end resource-reference verification.
- Explicit prompt paths are now extracted deterministically before request-analysis parsing. Model-returned paths are retained only when they occur literally in the prompt. A symbol or identifier matching an explicit path basename is path-qualified: when that path is absent, retrieval cannot globally rebind the name to a different repository symbol. Semantic candidates with the same missing basename or a conflicting path-qualified symbol are retained only as discovery hints, not accepted evidence.
- Semantic candidates now record covered and missing obligation-specific search concepts. Coverage splits camel-case and underscore-delimited code identifiers and normalizes common inflections, allowing identifiers such as `exportedModulesMap` to contribute to an `re-export` concept. Incomplete lexical coverage applies only a small ranking penalty; an earlier strict rejection experiment lost `builder.ts` because code expressed the concept without repeating the prompt wording, so that behavior was removed before acceptance.
- TypeScript verification showed the progression. `run-20260808T161838Z` proved that global `Session` symbol confirmation became `path_qualified_prompt_only`, but the first strict concept-coverage version lost all oracle owners. `run-20260808T162532Z` recovered a complete result but exposed a second same-name route through broad semantic search. After rejecting conflicting basename and path-qualified-symbol substitutes, `run-20260808T163138Z` removed both `src/server/session.ts` and `src/compiler/program.ts`, recovered oracle owner `src/compiler/builder.ts`, and remained honestly `partial/false` with one unresolved transition. `src/compiler/builderState.ts` is still missing, so focused graph expansion remains the next quality problem rather than being concealed by these anchor/ranking fixes.

## Focused graph-frontier expansion

- Stage boundary: after initial grounding, each required repository obligation now expands only from its closest grounded CodeGraph nodes. File-level CodeGraph neighbors supplement node edges, then Qdrant ranks snippets only inside that frontier. One bounded refinement round repeats from newly grounded files; request analysis is not rerun.
- Focused Qdrant searches fetch a wider result pool but retain at most one result per path. This prevents several chunks from one large file from crowding graph-discovered neighboring files out of the candidate window.
- Expected quality impact: recover implementation neighbors hidden behind namespace or incomplete call edges, preserve different files in the focused result set, and keep expansion tied to one obligation. Expected token impact: no new LLM call; Qdrant performs the same number of query embeddings but scores up to 48 candidates for focused searches. Native retrieval still does not emit request-analysis token totals.
- Regression risks: CodeGraph file adjacency can be broad, and a graph-discovered file can still yield the wrong local chunk. The single refinement round is a safety boundary, not proof that every reachable owner has been localized.
- `run-20260808T190909Z` completed in 109.5 seconds before path diversity. It recovered `src/compiler/builder.ts` at unique-file rank 5 and put `src/compiler/builderState.ts` into the refined frontier, but selected no `builderState.ts` snippet.
- A qualified-call promotion experiment was rejected. Runs `run-20260808T191804Z` and `run-20260808T192241Z` promoted frequently called utility members and lost all oracle overlap. The tool, scoring path, tests, and payload fields were removed completely rather than retained as a fallback.
- Accepted post-cleanup run `run-20260808T193359Z` completed in 105 seconds, selected 12 snippets, raised oracle overlap from one to two, placed `src/compiler/builder.ts` at unique-file rank 4, and recovered the oracle watch-mode test at rank 10. `src/compiler/builderState.ts` appeared in focused Qdrant results in round 1, proving discovery reached the file, but the returned ranges were not the decisive `getFilesAffectedBy`/`updateShapeSignature` functions and therefore did not survive final selection.
- Result: focused traversal and path-diverse ranking are retained because they improved measured evidence coverage without a new LLM stage. The original namespace case is only partially solved: file discovery works, while exact snippet localization inside the discovered file remains unresolved and must not be reported as successful owner recovery.

### File-selection provenance experiment (rejected)

- Experiment: preserve the concrete CodeGraph relationships that selected each frontier file, translate edge names into short natural-language reasons, and append those reasons to the obligation-specific Qdrant query. The intent was to keep snippet ranking scoped to why each file entered the frontier without adding another LLM call.
- `run-20260808T211653Z` returned `strong/true` but had zero oracle overlap. Generic member relationships produced misleading protocol/server context and displaced the builder owners.
- After filtering relationship context against obligation concepts, `run-20260808T212005Z` returned `strong/true` with two oracle overlaps. It selected `src/compiler/builderState.ts` at unique-file rank 3 and `src/compiler/builder.ts` at rank 6.
- The identical repeat `run-20260808T212226Z` regressed to `partial/false`, one oracle overlap, `src/compiler/builder.ts` at rank 5, and no selected `builderState.ts` evidence.
- Result: readable relationship text amplified noisy CodeGraph member collisions and did not overcome variation in request-analysis anchors/frontiers. Across three runs, oracle overlap was 0, 2, and 1, and the target file was selected only once. Per the retrieval stability policy, the relationship payload, query augmentation, metadata field, and experiment-only tests were removed completely. The accepted focused graph frontier remains the only production path.

### Direct CodeGraph snippet selection experiment (rejected)

- Experiment: discount high-fan-out and multiply defined CodeGraph relationships, expose symbol ranges from graph-selected files, and create snippets directly from concrete nodes while retaining Qdrant for unresolved files. No LLM call was added.
- The first version treated any specific-looking function inside a graph-neighbor file as direct evidence. `run-20260808T222340Z` and `run-20260808T222642Z` both had zero oracle overlap. They promoted unrelated but lexically plausible functions from module resolution, resolution caching, emitter, and factory code.
- The second version restricted direct snippets to concrete cross-file edge endpoints. `run-20260808T223227Z` improved to one oracle overlap but emitted 59 direct graph paths and still displaced semantic evidence.
- The final version accepted only call/instantiation endpoints with at least two obligation-specific symbol terms, capped direct candidates, and kept Qdrant active for every frontier file. `run-20260808T223620Z` recovered `src/compiler/builderState.ts` and its `getFilesAffectedByUpdatedShapeWhenModuleEmit` and `...NonModuleEmit` functions, but overlap remained one and `builder.ts` was lost. The identical repeat `run-20260808T223933Z` regressed to zero overlap and selected unrelated import tracking, resolution cache, and transformer functions.
- Result: structural uniqueness and exact ranges are not sufficient to establish causal relevance when the generated obligation itself is broad. The final two runs scored one and zero oracle overlaps versus the accepted baseline's two, so the specificity scoring, relationship payloads, direct-node selection, metadata, and experiment-only tests were removed completely. Qdrant remains responsible for snippet localization inside the accepted CodeGraph file frontier.

## Narrow owner-qualified reference recovery

- Stage boundary: focused graph expansion now records exact cross-file owner-qualified calls from the current candidate files, such as `BuilderState.getFilesAffectedBy(...)`. The resolver requires an uppercase owner, an exact member definition, and an owner match through the target file or qualified symbol. Same-file targets and configured excluded paths are omitted.
- These relationships are recorded as discovery provenance, not accepted evidence. High-fan-out utility owners are suppressed unless they are semantically relevant to the obligation. A measured target-file ranking bonus was removed after the two real comparisons below returned zero oracle overlap.
- Expected quality impact: reliably recover namespace-spread implementation files without restoring the rejected broad qualified-call promotion. Expected token impact: no LLM call and no embedding request beyond the existing focused Qdrant searches; the added work is bounded local source scanning plus exact CodeGraph lookup.
- Regression risks: the syntax recognizer intentionally covers statically named owner-qualified calls, not dynamic property access. Owner/file naming conventions can differ, in which case the relationship remains unresolved instead of being guessed. A graph-connected target file can still contain several mechanisms, so exact qualified nodes do not bypass semantic snippet ranking.
- The rejected `run-20260808T192241Z` artifacts were re-examined and corrected an earlier diagnosis: they did contain a precise `BuilderState.getFilesAffectedBy` target at `src/compiler/builderState.ts:267-288`, cited from both `src/compiler/builder.ts` and `src/server/project.ts`. The failure came from promoting that signal together with many utility members, not from failure to discover it.
- Direct production-tool verification on the real `microsoft-TypeScript-35468` snapshot returned 15 exact cross-file owner-qualified links. Ten targeted `BuilderState` functions; `getFilesAffectedBy` had call sites at `builder.ts:381` and `project.ts:584`. Four `Debug` utility relationships and one `Completions` relationship were also observed; qualifier fan-out now prevents the `Debug` group from gaining priority merely from frequency.
- Focused tests pass for exact owner resolution, multi-source aggregation, call-site lines, exclusion handling, and utility-fan-out suppression. The attempted full run `run-20260809T005750Z` did not reach obligation traversal: it spent the 15-minute command budget rebuilding/restoring TypeScript Qdrant points and reached roughly 10 GB resident memory. No coverage or oracle result is claimed from that interrupted run.
- The interrupted run used the wrong index scope because the rerun command omitted the testcase's explicit `lib` and `tests/cases` exclusions. Its 94,284-document local cache and case-scoped Qdrant collection were deleted. Clean run `run-20260809T093501Z` rebuilt the intended 20,146-document scope and completed in 19m24s; warm repeat `run-20260809T095444Z` completed in 106s.
- Both post-change runs reported `strong/true` but had zero oracle overlap. Exact qualified references reached `builderState.ts` and appeared in discovery hints, while final selection still chose unrelated server/watch evidence. Because target-file bonus did not improve evidence quality in either real comparison, it was removed completely. Exact qualified calls remain visible in trace/discovery metadata without changing the frontier or Qdrant score.
- Current-code warm verification `run-20260809T095838Z` reused all 20,146 BM25/Qdrant points and completed in 86 seconds. It returned `partial/false`, seven snippets, and one implementation-oracle overlap. Required obligations remained unresolved, so qualified-reference observability is retained but no quality improvement is claimed.

## Accumulated structural candidate provenance experiment

- Stage boundary: combine exact request anchors, semantic discoveries, and CodeGraph relationships in the candidate state passed from file discovery into path-scoped Qdrant snippet ranking. Exact owner-qualified call targets contribute their target node range, source paths, relationship type, source confidence, and originating obligation instead of remaining trace-only hints.
- Expected quality impact: one specific call from a strong candidate should promote its target file and exact node into the semantic frontier; later independent discoveries should strengthen the same target rather than replace its earlier provenance. Qdrant remains responsible for deciding whether the promoted range establishes the obligation.
- Expected token impact: no additional LLM calls and no repository-wide semantic query. Existing focused Qdrant calls receive a graph-narrowed path set and concise target-symbol context. Local candidate merging and CodeGraph source scanning add bounded deterministic work.
- Regression risks: ubiquitous utility calls can connect many otherwise relevant files, and repeated observations can inflate scores if provenance is not deduplicated. Promotion therefore uses unique source paths, source-candidate confidence, exact target nodes, and qualifier fan-out; generated/test targets retain their existing role penalties.
- Comparison: use `microsoft-TypeScript-35468` against `run-20260809T095838Z` (`partial/false`, seven snippets, one implementation-oracle overlap). Record whether `src/compiler/builderState.ts` and its decisive function range enter the selected evidence, their ranks, required unresolved obligations/transitions, runtime, and whether unrelated qualified targets are promoted.
- Initial run `run-20260809T224415Z` had zero oracle overlap. CodeGraph and path-scoped Qdrant reached `builderState.ts`, but the broad lexical support gate rejected the exact qualified target. Repair 1 allowed an exact promoted node to use narrow obligation overlap; `run-20260809T224739Z` became `strong/true`, selected the target file at unique-file rank 3, and had one oracle overlap.
- The first repair applied provenance at file scope, allowing unrelated functions in `completions.ts` and `jsTyping.ts` to inherit structural confidence. Repair 2 limited inheritance to the exact CodeGraph node. `run-20260809T225552Z` selected `builder.ts` and exact `builderState.ts:updateShapeSignature` but remained `partial/false` on a required transition; `run-20260809T225804Z` was `strong/true` with one oracle overlap but omitted `builderState.ts` after Qdrant path diversification discarded its preferred range.
- Repair 3 made path-scoped Qdrant prioritize results overlapping the supplied exact CodeGraph ranges before one-result-per-path diversification. `run-20260809T230148Z` selected `builder.ts`, `watchMode.ts`, and exact `builderState.ts:getFilesAffectedBy` with three oracle overlaps, but remained `partial/false` because required transitions were unresolved. The unchanged `run-20260809T230344Z` retained only `builder.ts` in final evidence; `builderState.ts` stayed in discovery hints because Qdrant's chunk start resolved to a different enclosing node.
- Repair 4 joined semantic chunks to promotions by exact node ID or overlap with the exact CodeGraph target range. It does not grant confidence to another non-overlapping function in the same file. `run-20260809T231132Z` completed in 101 seconds as `strong/true`, selected ten snippets, had two implementation-oracle overlaps, and selected three `builderState.ts` ranges plus `builder.ts`; all three ranges carried qualified-reference provenance from structural source candidates.
- The unchanged repeat `run-20260809T231331Z` completed in 84 seconds as `partial/false`, selected eight snippets, and had one implementation-oracle overlap. It did not seed `builder.ts`, so qualified-call expansion had no relevant source from which to discover `builderState.ts`. Request analysis also changed `watch_build_trigger` from implementation to configuration and added a required test obligation, leaving `watch_build_trigger->reexport_dependency_path` unresolved.
- Result: accumulated exact structural provenance is retained because it produced no observed same-file leakage after Repair 2 and materially improved owner selection whenever the relevant source frontier existed. It is not claimed to stabilize the full testcase. Identical-run variation in global request analysis and initial semantic seeds remains an upstream limitation; no TypeScript names, paths, obligations, or oracle files were hardcoded to conceal it.
- Native request-analysis usage is still serialized as an empty `usage` object, so retrieval token totals could not be measured from these artifacts. This experiment added no LLM call; the missing usage instrumentation remains separate work.
## 2026-08-10 - Graph-connected obligation candidate ranking experiment

- Added the implementation framework in `graph-connected-obligation-retrieval.md` before real-run evaluation.
- Discovery-time Qdrant searches no longer filter by the LLM-selected evidence role. Roles remain part of final support assessment.
- CodeGraph file-neighbor results now preserve originating source paths and relationship kinds.
- Focused Qdrant searches now receive structurally scored preferred paths, and combine graph priority with semantic score.
- Obligations may expand from grounded evidence belonging to their declared prerequisite stages.
- Qualified CodeGraph targets are no longer discarded from a frontier because their file role differs from the current obligation role.
- Focused verification: `python -m unittest tests.test_obligation_retrieval tests.test_codegraph_tools` passed 40 tests.

## 2026-08-11 - Connected shortlist and structural eligibility replacement

- Removed the fixed 25% obligation-term overlap requirement from bounded CodeGraph continuation. Productive `calls`, `references`, `imports`, implementation, and related structural edges are eligible even when repository names differ from issue prose.
- Retained exact owner-qualified references, source paths, edge kinds, and originating obligations as provenance. Removed normalized `source_confidence`, additive qualified-reference promotion, generic connected-node bonuses, evidence-role score adjustments, role-based confirmed-path filtering, and lexical dependency-frontier copying.
- Replaced the four independent per-obligation shortlist winners with a component-first shortlist. Components are ranked by required-obligation coverage, retained Qdrant/request seeds, productive graph edges, provenance tier, and only then candidate score; same-file placement alone does not connect candidates.
- Evidence roles remain in the final LLM proof contract and source-category selection. They no longer decide whether retrieval may traverse a file or add a ranking bonus merely from path/extension classification.
- Focused verification: 49 obligation tests and 104 retrieval tests passed after dead shortlist tests were removed. Added regressions proving that zero-overlap productive graph edges survive and that a cross-obligation connected path outranks a high-scoring isolated candidate.
- `vuejs-vue-10803` run `run-20260811T082417Z`: `partial/false`, five selected snippets, 40 tool calls, 236 pre-selection candidates, owner file retained with exact `renderDOMProps` and `setText`, and 16,764 final-selection tokens. The unsupported VNode-to-serializer handoff remained unresolved.
- Unchanged final-code repeat, `run-20260811T084833Z`: `partial/false`, four selected snippets, 42 tool calls, 263 candidates, owner file retained with exact `renderDOMProps` and `setText`, and 23,670 final-selection tokens. Owner retention was stable, but candidate-connection count varied from 84 to 170 and made final-selection cost unstable; the separate semantic bridge to `renderNode` remains missing.
- `pandas-dev-pandas-10068` run `run-20260811T083935Z`: `partial/false`, four selected snippets, implementation owner `pandas/core/series.py` at rank 1, 39 tool calls, and 20,084 final-selection tokens. This preserved the previous owner overlap while reducing the prior measured 25,400-token final selection, but did not preserve the prior run's sufficiency decision.
- `vuejs-vue-242` run `run-20260811T084114Z`: `partial/false`, four selected snippets, 31 tool calls, 130 candidates, 13,448 final-selection tokens, and zero Oracle overlap. The Oracle `src/exp-parser.js` remained absent before graph traversal, so the connected shortlist correctly did not claim to fix this Qdrant seed-fusion miss.
- A temporary experiment removing semantic-seed eligibility checks produced `run-20260811T084312Z` on the main Vue case, then increased old Vue's candidate graph to 271 and reduced final evidence to one non-Oracle snippet in `run-20260811T084438Z`. It was reverted immediately; Qdrant ranking still requires obligation-specific semantic support, while CodeGraph traversal no longer requires the 25% overlap threshold.
- `microsoft-TypeScript-35468` produced no valid comparison. A two-minute parent-command timeout left its child indexer running; the concurrent retry hit a CodeGraph SQLite lock, and the surviving TypeScript embedding rebuild exceeded ten minutes. Those test processes were stopped and neither artifact is counted as retrieval-quality evidence.
- Candidate-connection compaction now serializes only real graph/provenance links within one obligation or across a declared dependency. Repeated use of the same node is not emitted as a causal connection. Final Vue run `run-20260811T085039Z` reduced connection records from 170 to 41 and final-selection tokens from 23,670 to 12,388 while retaining only exact `renderDOMProps` and `setText` evidence. It remained correctly `partial/false` on the missing serializer handoff.
- Final pandas repeat `run-20260811T085211Z` was `partial/false`, selected `pandas/core/series.py:Series::from_array` and `pandas/core/ops.py:add_special_arithmetic_methods`, used 38 tool calls, and consumed 16,586 final-selection tokens with 32 candidate connections. It retained an implementation Oracle file and a relevant arithmetic owner, but still failed to localize the decisive result-name mutation. The older `strong/true` comparison had accepted unrelated `MultiIndex.from_arrays/from_tuples` evidence across several obligations, so its higher sufficiency is not treated as better grounded quality.

## 2026-08-11 - Range grounding, exact prompt seeds, and one focused semantic bridge

- Stage boundaries: semantic chunks are now mapped to every executable CodeGraph node overlapping the complete chunk range rather than resolving only `line_start` and taking the first node. Rare prompt errors/literals are admitted as initial semantic seeds only when repository evidence is exact or one source-template result decisively dominates alternatives. After bounded structural traversal, one focused bridge may continue from the latest exact graph endpoint into a consumer that CodeGraph cannot connect through ordinary control-flow edges.
- Exact range grounding is native to the CodeGraph bridge through `resolve_ranges`. The original Qdrant range and score remain provenance, while exact function ranges become candidates. Point resolution remains available as a tool API but is no longer used to map semantic chunks in obligation retrieval.
- The bridge receives one structurally proven endpoint and one unresolved downstream obligation. It emits compact source-like producer/consumer terms, runs one Qdrant query, resolves exact proposed consumer symbols first, and examines executable CodeGraph nodes in the returned files so an exact function range cannot be replaced by an unrelated chunk in the same file. Final support requires selected evidence on both producer and newly discovered consumer sides.
- Expected quality impact: preserve decisive functions hidden inside broad chunks; recover one missing data-flow handoff without reopening repository-wide search; prevent a semantic-only hit from being mislabeled as a proven endpoint; keep external or ambiguous prompt text from becoming fabricated repository evidence.
- Expected token impact: range and exact-seed work is deterministic. A bridge adds one small LLM call and one query; measured Vue bridge usage was 777-838 tokens. Exact-symbol checks add up to three bounded local CodeGraph calls. Known risk: a bridge can still propose broad consumer terms and introduce irrelevant discovery candidates, but those candidates cannot satisfy the bridged transition unless final selection accepts consumer-side evidence.
- `vuejs-vue-10803` `run-20260811T110307Z`: bridge correctly started at `setText` but Qdrant localized `src/server/render.js:277-283` instead of `renderNode`; result remained `partial/false`. This established the need for exact consumer-symbol and whole-file CodeGraph localization.
- `vuejs-vue-10803` `run-20260811T110717Z`: before two-sided bridge validation, the run incorrectly returned `strong/true` using only `renderDOMProps` and `setText`. The generic transition checker had reused that edge for later obligations. This result is rejected.
- Accepted Vue verification `run-20260811T111234Z`: `strong/true`, no unresolved obligations/transitions, and selected `renderDOMProps`, exact `setText:46-50`, and exact `renderNode:74-94`. The bridge began at `setText`, discovered and selected the consumer, and used 833 tokens.
- `pandas-dev-pandas-10068` `run-20260811T111431Z`: `partial/false`; a semantic chunk spanning `pandas/core/series.py:1466-1511` resolved to and selected exact `Series::_binop` across its full range. This directly verifies that the former first-line/`nodes[0]` mapping defect is removed. Remaining unresolved transitions are retrieval-quality issues, not range truncation.
- Positive exact-error verification `vuejs-vue-242` `run-20260811T104956Z`: the reported expression-parser error was mapped to the dominant source template and seeded `src/exp-parser.js:93-101` with `exact_prompt_anchor` provenance; all required obligations were supported.
- Negative external-error verification `pandas-dev-pandas-9219` `run-20260811T111926Z`: `partial/false`; `TypeError: unorderable types: NoneType() >= tuple()` remained `prompt_only` with no repository match. Local literals were classified independently, and evidence stayed on pandas' HDF handoff path rather than inventing a PyTables root cause.
