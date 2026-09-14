# Frozen request-analysis diagnostic

User-authorized diagnostic, not acceptance: replay the successful saved classification
from `run-20260914T214357Z` through the actual remaining pipeline three times.
Historical runtime plus original request-analysis cleanup; callable fix absent; thesis untouched.

Only the benchmark harness substitutes the explicitly selected saved LLM result. Validate
successful status, exact contract round-trip, and matching user prompt; fail on mismatch.
No runtime fallback and no downstream fake LLM. Ordinary runs capture full request-analysis
API payload/response events, excluding authentication headers, in a separate trace file.
Replay mode is process-local `CODEREPOQA_REPLAY_ANALYSIS_RUN`, recorded in a per-run
diagnostic manifest with source hashes and acceptance_run=false. No production mode switch.

Keep model, snapshot, index, prompt files, and selection budgets unchanged. Final selection
on, response generation off. Analyze earliest recorded divergence before any final-file loss
claim. Expected cost: ordinary downstream usage, no fresh analysis call in replay. Risk:
freezing one favorable upstream result cannot establish normal end-to-end quality. Source
analysis input API trace was not recorded historically; do not claim it was identical.

## Results (diagnostic only)

| Run | Focal files | Coverage / sufficient | Downstream retrieval tokens |
| --- | --- | --- | --- |
| `run-20260914T224438Z` | 3/4: Builder, BuilderState, WatchMode | partial / false | 105503 |
| `run-20260914T225902Z` | 4/4, Helpers is file trace | partial / false | 111711 |
| `run-20260914T225912Z` | 4/4, Helpers is file trace | partial / false | 102072 |

Total 319286. All completed with final selection, no response generation. These are
saved-analysis downstream diagnostics, not new end-to-end acceptance runs. No live
request-analysis tokens are included because that stage was explicitly replayed.

All three replay manifests identify the same source classification hash
`4b2791ccf5f0f5146f5c9e7180f22d4d3b6bee515a524c974c6affb64c61072c`.
Their full initial-owner-comparison request JSON, canonicalized with sorted keys, has
the same SHA256 `80babffb57318246ea4c7f3b55d280c63df1dd903e6e4548cbb198820555da68`.
This compares actual messages, schema and request settings, not prompt IDs alone.

## First recorded divergences

The first downstream LLM responses (connected-source planning) differ despite identical
request payloads. One query says `TypeScript project references wildcard re-export watch
mode Session`; the other two omit TypeScript and use plural re-exports. All find and reject
the same local retrieval-policy note, producing no signals. Their initial owner input
then matches exactly, so that wording difference does not explain a changed owner payload.

The first differing code-candidate decisions occur at initial owner comparison:

- All choose WatchMode primary `o9`.
- `224438Z` adds `o14` (`verifyDependencies`).
- `225902Z` and `225912Z` instead add `o19` (`verifyIncrementalErrors`).
- Only `225912Z` also selects groups g3 (editorServices.ts) and g8 (commandLineParser.ts).
- BuilderState g4 and Builder g12 selections match across all three at this boundary.

Thus downstream model decisions differ on an identical source-bearing input. This is
direct evidence of a downstream variation source, not proof that the initial difference
alone caused each final result. Do not infer absent retrieval from final file overlap.

## Concrete late Helpers boundary in 224438Z

Source observation `obs_158e2d5a3ab67ecb` is verifyTransitiveReferences, L770-L1064.
It appears in canonicalized initial snippets, disclosed/admitted input, selected round-zero
observations, and qualification. Round zero and round three both promote it as navigation,
with no supported obligation IDs. The controller executes action `action_73e190cadfb10258`
and constructs a Helpers trace with 18 calls (16 verifyTscWatch, two checkOutputErrorsInitial).
The source reaches the final pool as `node:function:010ba3b9c3d49d91958f67a4f5d3c335`,
qualified_navigation_evidence with 3672 text characters. It is absent from accepted final
IDs. Consolidation has 14 accepted IDs, four generic active-island additions, and no
preserved file-trace source IDs. The explicit Helpers trace decision is
`source_island_not_selected`, source_accepted=false. That is a rejection at the exact-source
eligibility gate, not missing file discovery. No assertion here distinguishes capacity
from protected-island eligibility as the reason preservation failed; that requires a
separate exact preservation replay.

Both 4/4 runs record the same 18-call Helpers structure, source_accepted=true, and explicit
LLM-selected structural evidence. These observations do not demonstrate internal Helpers
behavior or semantic sufficiency. The current SSA-1/QRC-1 representation boundaries remain
relevant, even though their historical successful runs reached four files.

## Infrastructure incident and exclusions

Qdrant was unavailable at initial startup. Restarted native WSL Qdrant 1.18.3 against its
existing storage. Waiting concurrent attempts entered rebuild paths; their collection
recreation left a partial index (exact observed count 2304). The historical reuse gate in
index_setup.py only tests point_count > 0, not expected count. Stopped scoped benchmark
processes; excluded attempts 224137Z, 224204Z, 224214Z, and 224352Z. Even the completed
224204Z artifact is invalid for this comparison. Their recorded response usage totals
6045 tokens; interrupted/in-flight usage may be unknown.

Moved the stale qdrant-sync-manifest.json to qdrant-sync-manifest.pre-replay-recovery.json
in the testcase's index directory. One controlled run (224438Z) rebuilt from cached vectors.
Verified Qdrant's exact count at 83408 before starting the other two. No new document
embedding batches were sent. This is an actual infrastructure confound in these initial
attempts, not evidence that earlier historical score batches used partial collections.
Total recorded response usage including excluded attempts: 325331 (possible unreported
in-flight usage excluded). The index-completeness bug has not been patched in production.

## Implementation / verification / current state

Harness-only context manager: request_analysis_diagnostics.py. Explicit env replay,
prompt equality and exact classification round-trip validation, independent diagnostic
manifest, no downstream mocks. Normal harness runs now log request-analysis input and
complete_json API events to request-analysis-api-trace.jsonl; authentication headers are
not logged. Requests/responses may contain source/context and should be treated as local
diagnostic data. Unit tests exercise replay equality, wrong-prompt rejection, live delegation
and payload capture. An initial wrapper bypassed existing test mocks; corrected delegation
to the currently bound classifier. All 38 focused tests pass after correction; the running
saved-replay branch was unchanged by that correction. No new third-party dependencies.

Runtime remains historical plus the cleanup. Only testing/logging support was added;
no new retrieval heuristic, qualification change, or final-selection fix. Thesis untouched.
The user-authorized three-run diagnostic is complete. The next focused experiment can
freeze owner-comparison decisions or replay exact-source preservation on these saved
inputs; normal end-to-end quality remains unresolved.
