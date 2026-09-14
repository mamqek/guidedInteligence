# Exact trace-source capacity ordering experiment

September 15: isolate final deterministic preservation only. Request-analysis cleanup,
qualification, controller, model prompts, index and evidence limit remain unchanged.
Thesis is out of scope.

Saved-input replay reproduces accepted IDs exactly for 224438Z, 225902Z and 225912Z
(September 14). Failed 224438Z starts with ten model selections; four generic island
additions exhaust fourteen slots before exact source preservation. Its WatchMode source
is active and present. Successful runs start with eight/seven selections and retain it.

Variant 1: preserve existing eligible exact trace sources before generic island diversity;
recompute represented islands afterward. Never evict model selections or automatically
accept a trace destination. Existing protected-island and one-source-per-path rules remain.
Expected effect: restore eligibility of already discovered structural traces. No extra
model calls; downstream trace payload/token usage may increase. Risk: generic island
diversity can lose a slot; source retention does not establish destination behavior.

Verification: exact baseline replay, focused cap/dedup tests, variant replay on the same
three pools, then three fresh actual-pipeline runs with final selection on and explanation
off. Use existing verified 83408-point WSL index; Docker engine is unavailable. Compare
trace eligibility, four focal files, partial/sufficient, tokens and displaced evidence.
Revert if repeated live regression or unstable quality provides no defensible improvement.
Do not call deterministic preservation replay an end-to-end improvement.

## Focused results

Baseline replay exact 3/3. Variant restores verifyTransitiveReferences in 224438Z,
displacing generic createWatchProgram (watchPublic.ts), not a model-selected candidate.
The two successful pools retain the same candidate sets (append order changes).
84 focused tests pass, including duplicate traces and a full model-selected pool.
Full suite under Node 22: 482/486 pass; three index fixtures lack lexical_ranking_profile,
and the manifest check flags analyze_qualified_file_leads. None is in the changed stage.
The first suite invocation used the wrong default Node and additionally failed FTS5;
corrected the test environment. Actual pipeline commands use Node 22 throughout.

Expanded saved-pool check: baseline reproduced exactly for 214357Z, 214407Z, 215946Z,
215956Z, 221537Z, 221547Z and 222120Z. Variant additionally repairs capacity-blocked
WatchMode in 215956Z; other candidate sets unchanged. Baseline reconstruction did NOT
match 214417Z and 220006Z, so those two are excluded from counterfactual conclusions.
The helper reconstructs candidate metadata/observations, not source excerpts; preservation
does not inspect text. No LLM output or semantic selection is simulated.

Live runs 232154Z, 232229Z, 232239Z started with fresh request analysis, final selection
enabled and response generation disabled. All explicitly reused the 83408-document index.
Focused/replay token cost: zero.

## Fresh actual-pipeline results and decision

| Run (20260914 UTC) | Focal files | Coverage/sufficient | Retrieval tokens |
|---|---|---|---:|
| 232154Z | 4/4 | partial/false | 105549 |
| 232229Z | 4/4 | partial/false | 101153 |
| 232239Z | 3/4 | partial/false | 94317 |

All commands completed successfully. Total 301019; mean 100340 (rounded).
Previous fresh cleanup batch 221537Z/221547Z/222120Z: 3/4, 4/4, 2/4,
total 300081, mean 100027. Difference +938 total, +0.31%. These are provider
usage totals from retrieval llm_response_received events, not request analysis,
response prose, or wiki generation. No duplicate cumulative stage usage included.

Important causal limit: current preservation replay exactly reproduces all three new
outputs. Replaying the old preservation order on these same new pools produces the SAME
candidate sets, with only append order changing in the first two. Therefore the new 4/4
scores do not demonstrate causal quality improvement from this patch. They are live
non-regression checks. The causal deterministic improvement is on the older capacity-
blocked 224438Z and 215956Z pools, not an assertion that the old full runs become 4/4.

232154Z accepts Helpers and BuilderState as structural file traces; the 4/4 count is
not four behavior-proving owner snippets. 232229Z accepts Helpers structurally and has
BuilderState source evidence. Both still report partial/false. 232239Z's final pool
contains WatchMode verifyTransitiveReferences, but the only created final file trace is
watch.ts -> program.ts (endpoint rejected). No Helpers trace exists at this boundary.
Helpers appears in raw query/range processing and controller action enumeration; do not
call it absent from retrieval. The earlier scheduling/trace-creation boundary requires
separate auditing and is not modified by this experiment.

Decision: best-effort retained as a narrow deterministic capacity-ordering repair, not
accepted as a repeatable overall recall improvement. No model-selected candidate is
evicted by preservation, no limits/prompts/qualification are changed, and no automatic
destination acceptance is added. Broader quality remains variable. Thesis untouched;
Docker was not restarted; existing WSL Qdrant index was reused, not rebuilt.
