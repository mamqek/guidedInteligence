# Positive proof retention, owner body cards, and island audit

## Authorization and fixed baseline (2026-08-27)

The user authorized testing qualification-proof retention and the two owner-body approaches in the
[handoff](retrieval-handoff-qualification-and-owner-source-plan.md). The final-island proposal is an audit first:
no final ranking or budget behavior changes until measurements justify a separate experiment.

Baseline is the dirty working tree recorded by the handoff, not HEAD alone. Preserve unrelated edits.
Existing final acceptance pair: run-20260827T153030Z / run-20260827T153303Z, 3/1 implementation Oracle files,
108,312 / 112,242 tokens, partial/false. Existing indexes, native model, prompts, scheduling, final selection,
completion settings, and dormant-completion=false stay fixed. No explanation generation or indexing.

## Step P — Positive proof retention, attempt 1

Boundary: qualification cache and returned source cards only. Cache direct judgments, not weak/rejected judgments.
Exact semantic input reuses direct proof. A smaller later card can reuse the prior direct decision **and its actual
source card** only when the full source backing is identical, owner/request/obligation/model context matches, and
the later visible source contains no new lines outside that proof. Replaced provenance remains current. New body
content, unknown backing, changed context or source requires the LLM; this is not permanent immunity for positives.
The first implementation deliberately does not infer semantic contradiction from prose or freeze disjoint views.

Expected quality: avoid erasing direct proof through cropping, allow weak judgments to be reconsidered when already
queued. Risks: repeat weak judgments cost more and vary; retained proof consumes downstream source budget; unchanged
full backing does not alone guarantee a new view is semantically redundant, hence the subset check.
Fit incoming cards first; do not redistribute freed capacity. Previously evaluated proof is not sent again, and the
trace distinguishes retained downstream source from current LLM input characters.

Verification: focused exact/cropped/changed/negative/context tests; saved real-card audits where available; two
actual TypeScript runs with final selection on. No claim of crop protection from an unexercised live path.

## Steps A and B — Owner-body representation

Use the same frozen accepted/provisional qualification baseline for both. A repairs declaration/docstring-only
views; B consistently renders signature plus bounded original-focus body context. Complete small owners;
explicit line-labelled gaps for distant signature and focus. One canonical owner stays one candidate.
Choose and record a common numerical card budget from saved-source measurements before paid calls. Calculate file
admission from exactly the rendered cards used by comparison. No regions, new per-file owner cap, ranking change,
new query, qualification-prompt change or input-budget increase. Keep acquisition/rendering in one cohesive stage.
Expected quality: useful body visible before owner rejection. Risks: fewer admitted files, extra reads/tokens,
unhelpful but nonempty fragments, or useful focus lost inside large bodies.
Focused fixtures and repeated saved-input comparisons precede two full TypeScript runs per viable variant.
Questionable outcomes are reported before reverting. At most three implementation attempts per step.

## Step I — Saved-run island audit (read-only behavior)

Inspect actual island membership and final candidate/flow graphs in successful and weak saved runs. Count direct
versus navigation snippets, disconnected direct singletons, useful benchmark mechanisms, and exact source/payload
cost per island. Distinguish the controller's actual islands from independently computed connected components.
Check the proposed >3-direct and direct-majority rules without treating them as proven relevance measures.
An island count alone cannot bound input cost or guarantee complete evidence. Record counterexamples and whether
whole-island admission would omit useful isolated snippets or include irrelevant large connected components.

## Result ledger

| Step | Attempt | Focused checks | Actual runs | Decision |
|---|---:|---|---|---|
| P | 1 | Positive/cropped/changed/negative tests pass | 213229Z / 213541Z, 3/2 Oracle files | Provisional; no stable overall gain |
| A | 2 | Representation repaired; two real comparison calls fail group validation | Not run: focused boundary failed | Replay-only, not activated |
| B | 2 | Two valid real comparison calls | 214614Z / 214625Z, 2/2 Oracle files | Provisional for user review, not quality-accepted |
| I | audit | Four TypeScript, two Pandas, two Vue traces | Saved runs only | Promising unit of admission; proposed count gates unsafe |

### P execution log

- 170 focused tests pass, including source retention over a budget crop, negative reconsideration, changed backing
  and genuinely new body content. A first fixture incorrectly used full mode (which renders the complete backing);
  corrected it to preview mode to exercise a genuinely different visible body. No production rule changed for that.
- run-20260827T213219Z failed at unchanged owner-comparison validation, before qualification. Recorded, not counted
  as a completed acceptance run; replacement invocation started. run-20260827T213229Z is the other original run.
- Completed P pair: 213229Z / 213541Z, partial/false, 3/2 implementation Oracle files, 109,545 / 105,584 tokens.
  Both reuse two direct judgments; getReferencedByPaths survives at ranks 9/8. No live crop-retention event.
  Result is provisional, not stable overall quality acceptance. Freeze this policy for A/B; do not tune it alongside
  body changes. Audit: `testing/codeRepoQA/qualified-file-lead-replays/positive-proof-acceptance.json`.

### Owner-card preparation and budget choice

- Saved-input audit reconstructs literal comparison payloads before comparing. Some merged owners retain source
  views not derivable solely from their final provenance/owner intersection; recover those ranges from the actual
  saved request and verify their rendered text against the unchanged snapshot. No LLM judgment is fabricated.
- Initial rendering attempt expanded backward into docstrings. Saved _binop cards exposed that defect before live
  calls. Attempt 2 bounds expansion at the first real AST body line while preserving the separately labelled signature.
- Measured 512 and 1,024 character cards offline. At 1,024, targeted TypeScript admission was 17→8 files; at 512 it
  was 17→11. This is a real cost risk, not a reason to inflate admission budgets. Compare both modes using 1,024
  characters after the docstring repair: the aim is useful body disclosure rather than minimal extra bytes.
- No owner-card variant has been activated in the actual pipeline yet. New AST layout operations and the renderer
  are isolated preparation code until the focused real-comparison boundary passes.

### Focused real owner-comparison calls

- A, `typescript-targeted-llm-1/2.jsonl`: both invalid global selections (22,440 / 21,811 tokens). Owners are assigned
  to the wrong groups. The validator remains unchanged; no selection is repaired deterministically. A has not
  passed the focused boundary, so no full pipeline runs are counted for A and it is not activated.
- B, `typescript-consistent-llm-1/2.json`: both valid, 23/15 selected owners; 21,311 / 20,565 tokens. Same input,
  95 comparison candidates across six files versus the 174/17 baseline; 72,921 accounted input characters.
  No claim that the valid selections are all relevant. The smaller admitted file set is a known risk requiring
  full acceptance. The original builderState file is outside that admitted prefix.
- Activate B alone for the real TypeScript pair after focused checks. P is frozen, and A remains a replay-only
  alternative. No change to final input ranking, island selection, budgets or controller scheduling.

### Consistent-card admission measurements

- run-20260827T214614Z: 420 canonical candidates; 259 prepared owner cards; 63 source/layout file requests.
  Four files admitted: tsbuildPublic.ts, tsbuild/watchMode.ts, watch.ts, watchPublic.ts; 67,594 comparison input chars.
- run-20260827T214625Z: 456 canonical candidates; 315 prepared owner cards; 62 source/layout file requests.
  Three files admitted: builderState.ts, tsbuild/watchMode.ts, server/session.ts; 93,706 input chars.
- Both passed owner comparison and reached qualification. These are different live inventories, so their different
  file counts are not an isolated A/B estimate. The saved-input 17→6 comparison establishes the representation-cost
  effect without upstream variation. Completed final results follow below.

### Completed actual results and exact affected behavior

Both B runs completed partial/false with **two implementation Oracle files each**. Costs: 102,159 / 86,236 retrieval
tokens; combined 188,395 versus P's 215,129 (-26,734, -12.4%). No explanation generation; index a27de1ce reused with
83,401 indexed points and `rebuilt=false` in both traces (line 9). Dormant completion and round settings unchanged.
This is not accepted based on token reduction: upstream inventories differ and evidence coverage remains incomplete.

- 214614Z: 13 prepared cards were selected. Three had no body in their previous compact comparison views:
  `createSolutionAndWatchModeOfProject`, `invalidateProjectAndScheduleBuilds`, `startWatching`. All three qualified
  direct in round zero (trace 90); the first two reached final ranks 2 and 4. Their bodies genuinely show setup,
  invalidation/scheduling and watcher registration, not the complete wildcard-export failure mechanism.
  The source change is observed, but without paired decisions over the same live inventory it does not prove these
  owners would have been rejected with their old views. Preparation is trace 53, comparison selection 59.
- 214614Z first loss: builderState had 2 dense / 3 sparse hits and three canonical snippets; builder had 6 dense /
  2 sparse hits and four canonical snippets. Both were structurally resolved, then excluded by file admission
  (trace 54). The controller later recovered builder::getNextAffectedFile, which qualified direct and reached final
  rank 8; builderState never received a qualification card. This was not a final-model rejection of builderState.
- 214625Z: 10 prepared cards were selected, but none was previously bodyless. Four builderState owners were selected;
  getFilesAffectedByUpdatedShapeWhenModuleEmit qualified direct (84) and reached final rank 2. updateExportedModules
  and the non-module path were navigation-only. The final selector still selected the non-module path as context.
  Visible body alone does not guarantee direct qualification or prevent contextual final selections.
- 214625Z first loss: builder had 16 dense / 13 sparse hits, 18 canonical snippets and best file retrieval rank 2,
  but did not pass file admission (54). It was never qualified or selected. tscWatch/helpers had six dense hits and
  six canonical snippets, was excluded initially, later recovered verifyTscWatch as navigation-only (616), and did
  not reach final evidence. A large session.ts group was in the admitted prefix.
- Both final pools and flow ledgers are preserved: 214614Z lines 1326/1328; 214625Z lines 1148/1150. Full joins:
  `testing/codeRepoQA/owner-source-replays/consistent-boundary-audit.json`; stage/token summaries:
  `consistent-acceptance.json` in the same directory.

P-specific attribution: the positive reuse of getReferencedByPaths also existed under the previous all-judgment
cache, so do not credit those ranks specifically to the new positive-only policy. Exact saved-input audits find
one formerly cached weak judgment re-evaluated in 213229Z (ConfigFileExistenceInfo: navigation→insufficient) and two
in 213541Z (introduceError and a test range: navigation→navigation). The observed navigation→direct changes elsewhere
had changed semantic inputs and would already have been requalified by the old policy. Crop retention is verified
by focused tests but naturally unexercised in both runs. Counterfactual artifacts: `positive-proof-old-cache-counterfactual-1/2.json`.

### Disposition and costs

- P remains provisional. The current rule protects exact direct proof and verified poorer crops; it is deliberately
  not a permanent never-downgrade latch for disjoint new views. There is no demonstrated incremental live-quality
  benefit over the previous cache in this pair.
- A is not active: two focused real calls failed, and the pipeline was not run with invalid repaired selections.
  The failure is the existing owner/group membership contract, not a source-read failure. Do not fix it by guessing
  which group the model intended. Any schema/alias redesign is a separate experiment.
- B is left **provisionally applied for explicit user review**, following the user's instruction to report
  questionable outcomes before reverting. It is **not quality-accepted**, and narrower admission is a material
  downside. Do not describe it as a successful replacement or retain it merely for token savings. Recommend resolving
  that tradeoff with the user before further production/baseline runs; no automatic additional tuning or budget
  increases were made.
- Island-based final admission has not been implemented; the evidence and caveats below are for a separate decision.
- Total paid verification this execution: 239,677 P actual tokens including the 24,548-token upstream failed run;
  188,395 B actual tokens; 44,251 failed A comparison-replay tokens; 41,876 successful B comparison-replay tokens;
  **514,199 total**. Four completed actual runs, one failed actual run, and four isolated real comparison calls.
  Offline audits/focused tests do not count as actual acceptance or spend LLM tokens. Final focused suite: 277 tests.

## Saved-run island audit results

Artifacts: `testing/codeRepoQA/qualified-file-lead-replays/island-audit.json`, `island-audit-pandas.json`,
`island-audit-vue.json`; generated by `testing/codeRepoQA/audit_final_islands.py`. The script reads actual controller
islands, maps every final-pool candidate to disclosed source, checks its source character count, and verifies that
reconstructed candidate payloads match literal final-input candidates where those were selected. It creates no
retrieval decisions and makes no LLM calls. Counts are latest judgments at final-pool time, not retrieval labels.

| TypeScript run | Islands | Direct snippets | Direct snippets in top two islands | Top-two visible source chars | Top-two current-flow candidate arrays chars |
|---|---:|---:|---:|---:|---:|
| 142925Z | 7 | 23 | 21 | 30,070 | 57,899 |
| 142935Z | 7 | 11 | 10 | 33,684 | 28,199 |
| 153030Z | 6 | 17 | 17 | 31,862 | 48,678 |
| 153303Z | 7 | 20 | 15 | 21,877 | 35,430 |

Top two here means sorted by actual direct-snippet count, not the controller's existing active-island order.
Source characters include all mapped promoted members. Candidate-array characters use the existing final schema,
2,400-character candidate source cap and members surviving its support-graph inventory. They **exclude** prompt,
response schema, flows, connections and members not in that inventory: not complete hypothetical whole-island
request totals. Those missing members are explicitly listed in JSON; no fabricated full prompt cost is claimed.
Actual pool/flow trace lines respectively: 1889/1891, 1832/1834, 1828/1830, 2306/2308.

Concrete implications:

- In weak TypeScript 153303Z, the largest island contains 11 direct plus seven navigation snippets. It includes
  introduceError and createWatchProgram::onSourceFileChange, both absent from final input. The second contains
  four direct plus two navigation, including builderState's cache helpers. Whole-island preservation could prevent
  these *input* omissions; it does not ensure final semantic selection.
- Five direct snippets lie outside those two islands: two watcher/system snippets, Project::onInvalidatedResolution,
  updateModuleResolutionCache, and getBinderAndCheckerDiagnosticsOfFile. The last is also excluded from final input.
  Some external items are generic, but direct count alone cannot establish that all five are dispensable.
- In 142925Z, the top-two candidate arrays alone exceed the existing 45,000-character flow threshold before flow,
  connection and prompt overhead. Island count is not a bound on size. In 153303Z the analogous arrays are smaller.
- In Pandas 125119Z (pool/flow lines 781/783), the principal island has exactly three direct and three navigation
  snippets: operator wrapper, _maybe_match_name and Series::_binop are direct; registration helpers are navigation.
  Both `direct > 3` and `direct > navigation` reject this useful island. No island passes either rule in that run.
- Pandas 125129Z (897/899) has a one-direct test island and a twelve-navigation implementation island, including
  _binop, flex_wrapper and __finalize__. A direct-majority rule selects the test and excludes the implementation
  chain because earlier qualification labelled it navigation. Island admission cannot repair classification itself.
- Vue 115757Z and 115408Z have five/seven islands and one/six direct snippets respectively. In the latter, top two
  contain only four of six direct snippets; no island has more than three direct snippets. A hard two-island or
  >3-direct rule is not supported as a general policy by these runs.

Island membership is broader than source-verified calls: it also preserves previous unions, merges enclosing owners,
bounded action parentage, and action/structural overlap with unresolved obligations. Large membership is not proof
of one coherent causal chain; retrieval-associated obligation labels in an island are not all semantic support.

Recommendation for a **future separate** experiment: use islands as completeness-aware admission units, with a
preferred character target rather than splitting a chosen connected mechanism at an arbitrary later flow. Compare
this against the same final pools; retain a route for important isolated direct snippets. Rank using actual semantic
support and distinct contributions, not an untested direct-count cutoff. Explicitly measure the whole rendered input
and keep a provider-safe maximum/oversize handling policy. Do not implement the final policy inside the present
qualification/body experiments. No island budget behavior has been changed.
