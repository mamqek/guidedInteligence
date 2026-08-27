# Qualified helper survival, then fixed-budget file packing

## Sequence and unchanged baseline

Requested 2026-08-27. Run two consecutive, independently reversible experiments. The user explicitly asks that
questionable outcomes be reported before continuing, not automatically reverted. A questionable change is retained
provisionally and labelled as such, not accepted. Maximum three implementation variants per step; two complete actual
pipeline runs per main case, final selection enabled, explanation skipped. Existing indexes are reused. Model,
query/qualification prompts, source-owner compatibility, dormant-completion setting and scheduler stay fixed.

The requested order deliberately tests the downstream filter first, then upstream packing. Step 2 uses the recorded
Step 1 decision as its fixed baseline; saved-input replays isolate packing from the earlier filter change.

## 1. Qualified connecting helpers survive the causal-role filter

Baseline: TypeScript run-20260827T105127Z / run-20260827T105613Z recovered getReferencedByPaths and qualified it as
direct evidence. Final-flow ledgers at 1837 / 1892 rejected its flows as rejected_no_new_causal_responsibility.
The name/body heuristic calls this read-only reverse-dependency lookup supporting. Final LLM never saw it.

Boundary: mechanism-flow admission only. Permit new semantically qualified direct candidates connected by an existing
exact/source-grounded call to another qualified direct candidate in the current flow or already selected pool. Do not
require a new heuristic causal-role label. Keep known generic utilities excluded from this exception; do not infer
semantic support from the connection. Existing flow ranking, deduplication, source limits, global character budget,
LLM prompt/schema and final selection remain unchanged. No automatic final admission and no symbol-specific rule.

Quality hypothesis: useful read-only connecting source can compete in final selection. Cost risk: more candidates and
larger final payloads may crowd out stronger evidence or increase final LLM tokens; generic qualified readers may still
be tangential. Log the exact exception-eligible candidate/connection IDs, budget fate, final LLM fate and displacements.

Verification: focused negative/positive boundary tests, replay saved real TypeScript final pools with original and new
selectors, then two actual TypeScript runs. Compare the helper specifically as well as all newly admitted candidates,
Oracle retention, coverage/sufficiency and stage tokens. Baselines: 109,229 / 116,904 tokens, partial/false, 3 Oracles each.

## 2. Skip oversized file groups and continue at the same limits

Baseline: Pandas run-20260827T104726Z stopped at tests/test_series.py after only 20,356 comparison-input characters,
excluding all later files including core/series.py. _binop was already retrieved/resolved and remained deferred.

Boundary: deterministic initial file admission. Measure complete file groups in unchanged rank order; if a group
exceeds the preferred 60,000 target or hard 100,000 ceiling, defer that group and continue trying later groups.
Keep the existing first-file preferred-target exception, hard ceiling, maximum file count, all within-file candidates,
owner comparison and subsequent lifecycle rules. Log every skipped path, tentative size, and resulting actual payload.

Quality hypothesis: smaller useful groups stop being collateral exclusions behind an oversized group. Risks: favoring
small noisy groups, more candidate tokens than a short prefix, displacement during global comparison, and still
excluding a large essential file. No guarantee that series.py fits: measure it. Do not raise either size threshold.

Verification: deterministic fixtures including first oversized group, later fitting groups, no fitting group and file
cap; original/new admission replay on saved Pandas inventory; two actual Pandas runs with Step 1 fixed. Compare all
newly admitted paths, _binop through each loss boundary, owner choices, qualification, final evidence and stage tokens.
Prior Pandas baseline: partial/false, 0 implementation Oracles, 3 final items / 2 files, 53,091 tokens.

## Result ledger

| Step | Variant | Focused evidence | Actual runs | Decision |
|---|---:|---|---|---|
| Qualified connecting helpers | 1 | 78 focused flow tests pass; two exact saved-pool replays repeated identically | 123853Z / 124548Z complete; 123717Z / 124317Z invalid | Provisionally retained; final stability not established |
| Skip oversized file groups | 1 | 97 comparison/qualification tests; identical saved-input replays | 125119Z / 125129Z complete | Provisionally retained; packing works, final benefit unproven |

Detailed metrics and exact run IDs will be recorded here and summarized in the retrieval changelog. Invalid pipeline
runs are retained in the ledger but excluded from acceptance. A smaller token count alone is not acceptance evidence.

### Step 1 saved-input measurements

`testing/codeRepoQA/replay_helper_flow_admission.py` reconstructs literal qualification source and final inventory,
then checks the original selector from commit c6a40a60d83b5e8fec78b27f95646cd1a225ea7c reproduces both selected IDs
and exact used characters before running the new selector. Both runs reproduce exactly; repeated outputs are identical.
No source expansion, retrieval or LLM calls occur in this diagnostic replay.

| Saved run | Candidate count old/new | Characters old/new | Newly included | Displaced |
|---|---|---|---|---|
| 105127Z | 13 / 14 | 44,831 / 44,819 | getReferencedByPaths; updateExportedFilesMapFromCache | getNextInvalidatedProject |
| 105613Z | 14 / 15 | 44,806 / 44,854 | getReferencedByPaths; getFilesAffectedByUpdatedShapeWhenNonModuleEmit | getUpToDateStatusWorker |

This verifies the intended helper survival but also makes the unchanged-budget displacement risk concrete. The
second newly included owner need not itself be a helper: admitting a flow changes later budget/connectivity order.
Both displaced owners are useful compiler mechanisms. Do not present this as unqualified quality improvement.
Artifacts: `testing/codeRepoQA/qualified-file-lead-replays/helper-flow-replay.json` and `helper-flow-replay-repeat.json`.

### Step 1 actual-run ledger

| Run | Validity | Result | Retrieval tokens |
|---|---|---|---:|
| run-20260827T123717Z | Invalid final LLM output, excluded | Both final JSON responses invalid; helper reached payload | 121,627 recorded response tokens |
| run-20260827T123853Z | Complete | partial/false, 3 implementation Oracles, 13 items / 6 files | 107,658 |
| run-20260827T124317Z | Invalid upstream owner comparison, excluded | initial_owner_comparison_invalid_global_selection | 24,326 |
| run-20260827T124548Z | Complete | partial/false, 2 implementation Oracles, 9 items / 5 files | 88,298 |

In 123853Z, getReferencedByPaths was recovered at round 1, qualified direct (508; reassessed at 928), admitted via
the new exception in final-flow ledger 1763, and selected by the final LLM (1770) at evidence rank 9. Its selected
flow has no new substantive IDs or responsibility keys: this demonstrates the exception actually changed that
decision. The final LLM describes its contribution as the concrete referencedMap-to-referencing-path extraction,
not proof of the full wildcard/watch bug. All three implementation Oracle files survive; global result stays partial.
Stage tokens: context 1,810; owner comparison 21,886; qualification 33,704; coverage 33,107; final selection 17,151.

Replay caution: the two historical inputs reproduce exactly. A full same-input counterfactual replay of live
123853Z did not reproduce the selected pool (two IDs differ), despite matching serialized candidate facts; it is
excluded as causal evidence. Recorded candidate scores have finite precision and reconstituted stage inputs are
not a full runtime checkpoint. The live exception claim above uses its literal decision fields, not that replay.
123717Z replay reproduces selected IDs but differs by one character; its size comparison is approximate. Neither
invalid run is counted as final-quality evidence; no production validator or LLM retry policy was changed.

The first invalid run's final response and retry exhausted 4,000 completion tokens entirely on reasoning and returned
empty content (`finish_reason=length`). This is a real observed runtime failure, not a valid quality result; no causal
attribution to the filter is established. The existing completion budget was not changed.

In 124548Z, the helper was retrieved by verified action in round 2 (897), qualified direct at 915, then requalified
navigation_only with zero supported obligations at 1342. All five final builderState.ts candidates were navigation_only
with empty obligation_ids. They remain in the final raw pool but are not attached to any obligation progress state,
so none enter the flow selector's candidate inventory (1726). Thus the new direct-evidence exception does not apply.
This is an earlier semantic/lifecycle boundary, not a final LLM rejection or a new-filter budget displacement.
Stage tokens: context 1,800; comparison 22,819; qualification 33,193; coverage 19,192; final selection 11,294.

Decision communicated before Step 2: provisionally retain per user instruction, not fully accept. Historical-input
improvement is repeatable; one complete live run admits and finally selects the intended helper, but the second
loses it earlier and retains only two Oracle files. Do not automatically revert a questionable result or silently
change qualification. Frozen Step 1 now becomes the Step 2 baseline. Complete reports are in
`testing/codeRepoQA/qualified-file-lead-replays/helper-complete-acceptance.json`.

### Step 2 saved-input measurements

`replay_file_packing.py` reconstructs original source views from raw tool output and canonical provenance, validates
the original selector's admitted paths and exact payload size, then runs the new selector. Two identical replays of
Pandas 104726Z: 4 -> 17 files, 52 -> 194 candidates, 20,356 -> 59,808 comparison-input characters. No old admitted file
is displaced. test_series.py remains excluded: its tentative total is 68,020. core/series.py now fits, along with
generic.py, sparse/series.py and several test/config files. This fixes collateral prefix exclusion but is not a new
relevance policy: it also increases noisy comparison material and cannot guarantee the LLM will choose _binop.
The preferred 60,000 and hard 100,000 limits remain unchanged, including the original first-file preference exception.
Artifacts: `testing/codeRepoQA/qualified-file-lead-replays/packing-replay.json` / `packing-replay-repeat.json`.

### Step 2 live admission measurements

The same-input replay also reproduces each new run's actual admitted paths and character total exactly, before
comparing the old prefix rule. This isolates packing from stochastic changes in queries/initial candidates.

| Run | Files old/new | Snippets old/new | Characters old/new | series.py |
|---|---|---|---|---|
| run-20260827T125119Z | 4 / 22 | 48 / 191 | 18,169 / 59,845 | Newly admitted, 3,278 marginal characters |
| run-20260827T125129Z | 6 / 7 | 177 / 180 | 58,838 / 59,928 | Still skipped, tentative 61,039 |

In 125119Z, _binop reaches owner comparison as o73, but its only view v82 is lines 1466-1473 and the entire compact
text is `def _binop(self, other, func, level=None, fill_value=None):`. The LLM chooses only four ops.py owners and
leaves _binop dormant. Insufficient visible body is a plausible explanation, not a claimed LLM reason (this schema
does not return selection reasons). Changing packing does not change source views or force semantic selection.
125129Z adds only pandas/tools/plotting.py relative to its unchanged-input prefix baseline; that is no demonstrated
mechanism gain. Additional low-cost file admission is not synonymous with better evidence.
Artifacts: `packing-live-counterfactual-1.json` / `packing-live-counterfactual-2.json` under the replay directory.

### Step 2 complete outcomes and attribution

| Run | Coverage / sufficient | Implementation Oracles | Final items / files | Retrieval tokens | Comparison tokens | Final-selection tokens |
|---|---|---:|---:|---:|---:|---:|
| run-20260827T104726Z (prior baseline) | partial / false | 0 | 3 / 2 | 53,091 | 7,819 | 7,147 |
| run-20260827T125119Z | partial / false | 1 | 5 / 4 | 81,491 | 24,339 | 7,004 |
| run-20260827T125129Z | partial / false | 0 | 2 / 2 | 80,185 | 23,767 | 4,502 |

Both runs reuse all 10,334 indexed points (trace 9, rebuilt=false), complete four controller rounds, and execute final
selection without explanation. The previous baseline used three rounds. No round-count or model setting was changed.
Step 1's qualified-call exception affected no Pandas flow decisions in these runs, so it did not directly admit an
extra final candidate; this separates its effect from Step 2 at the observed final boundary.

125119Z loss/recovery: raw _binop source resolves to its existing node, series.py is admitted at 62, and comparison
leaves _binop dormant at 67 (signature-only preview). A new-island action in round 1 independently recovers its body
(185), qualification promotes it as direct (207), it reaches the final pool (781), flow input (783), and final LLM
selection (790), finishing at rank 2. Other final source includes _arith_method_SERIES::wrapper, _maybe_match_name,
_flex_method_SERIES and a scalar-name test. It has useful contrasting arithmetic bodies but does not prove the
complete dynamic binding/metadata chain; partial/false remains appropriate.

125129Z loss/recovery: initial admission excludes series.py at 62 (61,039 tentative characters). The same kind of
new-island action independently recovers _binop in round 1 (185), qualifying it direct (207). Round 4 requalification
downgrades it to navigation_only with no supported obligations (767): the model says the source shows unused computed
name plus finalization but does not prove add dispatch. The raw final pool still contains it with no obligations (897),
but the obligation-state flow inventory omits it (899). Final evidence is only test_binop_maybe_preserve_name and
_maybe_match_name (906). This is neither a final-size rejection nor a final LLM decision over the _binop body.

Important attribution: the eventual _binop recovery in both runs came from SearchNewIsland, not deferred/dormant
inspection enabled by newly admitting its file. Thus one final Oracle is not proof that packing improved final quality.
The causal packing evidence is the exact same-input file/character replay. In the second live run, the only newly
admitted file is plotting.py and it is not chosen by initial owner comparison. Larger whole-run token totals should
not be attributed entirely to packing: the old rule on that same second input already used 58,838 characters, unlike
the earlier 20,356-character baseline. Upstream candidate variation accounts for much of that run's comparison cost.

Decision: provisionally retain without automatic rollback, as requested. The deterministic collateral-exclusion defect
is corrected and the budget is respected, but two stable final-quality gains have not been demonstrated. The tradeoff
is much larger comparison pools on short-prefix inputs, including irrelevant small files. Do not raise the ceiling,
change ranking weights, or fix signature-only previews/qualification downgrades inside this experiment.

## Completion and artifacts

Subsequent user decision (2026-08-27): reject Step 2 skip-and-continue packing. Replace it with append-crossing-then-stop
admission, documented in [append-crossing-input-budget-experiment.md](append-crossing-input-budget-experiment.md).
The measurements below remain historical; Step 1 qualified-helper admission remains unchanged and provisional.

- One behavior variant per step, independently scoped; no index/model/prompt/round-count change.
- 202 focused regression tests pass together. No explanation tokens spent.
- Two complete actual TypeScript runs and two complete Pandas runs; two TypeScript invalid attempts recorded separately.
- Reports: `helper-complete-acceptance.json`, `packing-complete-acceptance.json`, and `two-experiment-baselines.json`
  in `testing/codeRepoQA/qualified-file-lead-replays/`, with run IDs, literal trace-line references, lifecycle and stage costs.
- Both changes remain provisional for user review, not presented as stable end-to-end improvements. Outstanding
  decisions concern the cost of extra file groups and qualification's repeated removal of useful connected partial
  evidence before final comparison.
