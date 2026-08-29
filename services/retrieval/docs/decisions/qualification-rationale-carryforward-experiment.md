# Bounded qualification rationale carried with evidence

## Scope and baseline (2026-08-28)

Baseline: `7c50ba2`, branch `codex/dormant-island-reconnection`, after removing source descriptions.
Prior experiment documents/replays are preserved and unrelated to this patch. Reference TypeScript runs:
`run-20260827T225224Z` / `run-20260827T225234Z`, partial/false, 3/2 Oracle files,
101,440/101,088 retrieval tokens. Source-description runs must not enter this baseline cohort.

The baseline records qualification reason/support/missing information but drops the reason from normal
candidate payloads and fresh reassessments. This experiment carries the existing reason, not a new summary stage.

## Implementation boundaries

1. Qualification emits one sentence of at most 400 characters identifying the observed behavior and why it
   warrants its classification, including the decisive limitation where relevant. Enforce the bound in schema
   and runtime validation; do not silently truncate the conclusion or add an LLM call to shorten it.
2. The latest per-snippet decision accompanies genuine reassessment as prior judgment, not new proof. It must
   not prevent correction when current source contradicts it. Preserve existing direct-proof/crop reuse; merely
   adding prior rationale must not invalidate its fingerprint. Initial unqualified hits have no invented reason.
3. Qualified candidates retain `qualification_reason` in coverage, final-selection input, trace and returned
   evidence metadata. Do not transfer rationale between owners, grow a history string, change ranking, or inherit
   semantic support from the rationale. Include the field in existing payload budget accounting.

No query/owner rendering/admission/source allocation/round count/index/model/budget change; no source-description
module, full-owner inspection queue or explanation implementation change. Extra input is bounded metadata only.
Expected benefit: continuity of the reason for acceptance/rejection and clearer limits on downstream interpretation.
Risks: anchoring on an incorrect previous judgment, additional metadata displacing source inside unchanged budgets,
and semantic variation unrelated to the change. Token savings and Oracle gains are not assumed.

## Verification and decision

Focused checks: reason length/empty validation; prior reason on changed source; unchanged positive cache reuse;
negative reassessment and correction; budget accounting; candidate/coverage/final/evidence propagation.
Then two actual TypeScript evaluations with `--skip-response-generation`, final selection enabled, existing index,
workspace profile and dormant completion disabled. Record exact run IDs, tokens, Oracle ranks, coverage/sufficiency,
rationale presence/length, actual reassessments and their outcomes. Attribute upstream inventory changes separately.
At most three implementation variants; questionable quality is reported before further action. Do not accept an
untested reassessment benefit solely from final counts. No new experiments are bundled into this one.

## Ledger

- Attempt 1: 177 focused/relevant tests pass (7 new rationale, 11 reuse, 81 qualification/controller,
  78 obligation/final selection). Two small-budget test fixtures now use 7,500 rather than 6,000 characters
  because the added prompt instructions exceeded their old metadata allowance; production budgets are unchanged.
- Actual run 1: `run-20260828T021522Z`, completed, workspace native, no explanation, final selection enabled.
- Actual run 2: `run-20260828T021533Z`, completed, identical configuration.

## Completed results

| Measurement | 021522Z | 021533Z |
|---|---:|---:|
| Coverage / sufficient | partial / false | partial / false |
| Implementation-Oracle file overlap | 2 | 2 |
| Returned evidence items | 7 | 10 |
| Retrieval tokens | 87,747 | 107,062 |
| Qualification tokens / calls | 26,004 / 4 | 28,237 / 5 |
| Coverage tokens / calls | 22,819 / 4 | 42,534 / 5 |
| Final-selection tokens | 12,244 | 16,676 |
| Fresh qualification decisions | 27 | 30 |
| Longest reason, characters | 281 | 279 |
| Actual reassessments receiving prior reason | 2 | 1 |
| Direct judgments reused by unchanged existing cache | 2 | 2 |
| Final-input candidates carrying reason | 8 / 8 | 12 / 12 |
| Reason text in final input, characters | 2,031 | 2,792 |
| Returned evidence carrying reason | 7 / 7 | 10 / 10 |
| Completed controller rounds | 3 | 4 |

Both reused the same 83,401-point index with `rebuilt=false` (trace line 9 in both), dormant completion disabled.
CodeGraph's normal synchronization reported the same two retrying large files and 97,250 nodes as the baseline;
there was no intentional index rebuild or scope change. The second run used the existing exact-lead fourth-round
allowance, not a changed round limit. The new metadata introduced no additional LLM stage or mandatory call.

Combined retrieval tokens: 194,809 versus baseline 202,528 (-3.8%). This is not a causal saving: initial
inventories, owner-comparison selections, source sizes and the second run's additional existing round differed.
The metadata adds characters within unchanged budgets, so it can reduce source space rather than cost nothing.
All 57 newly produced reasons stayed within the 400-character limit, without truncation or shortening calls.

### Actual continuity behavior

- Run 1 `verifyTransitiveReferences`: prior navigation reason was supplied at trace line 263 and the decision at
  line 265 remained navigation-only, retaining the limitation that the visible excerpt lacks the specific
  wildcard/interface-change assertion. It did not become an issue anchor merely because it was previously seen.
- Run 1 `getNextInvalidatedProject`: navigation reason from line 265 was supplied at line 461. The new decision
  at line 463 promoted it for `explain_state_changes`, explaining UpToDate, UpToDateWithUpstreamTypes and blocked
  transitions while retaining the wildcard-specific limitation. It reached returned rank 4. The visible source
  differed (3,302 -> 2,259 characters), so this is not proof that the rationale alone caused promotion.
- Run 2 `invalidDotDotAfterRecursiveWildcardPattern`: prior rejection was supplied at line 972; line 974 again
  rejected it as a path-validation regex rather than project-reference/re-export evidence. No history string grew.
- Neither run naturally requalified previously direct evidence: those unchanged cases used the existing cache.
  Therefore prevention of a previously direct-to-navigation flip remains unproven in live retrieval; focused
  tests show that current contradictory source can still correct an earlier direct judgment.

### Downstream propagation and remaining boundaries

Literal final requests at run-1 line 952 and run-2 line 1163 carry the same latest reason on every candidate;
returned evidence metadata also retains it. All coverage requests carry reasons for every direct candidate.
The first final mechanism description explicitly retains the missing wildcard-specific/diagnostic handoff rather
than treating the partial implementation as a full explanation (response line 953).

This does not guarantee downstream correctness. In run 2, `watchRecursivePattern` returned at rank 10 despite
being navigation-only with a reason explicitly denying proof of re-export/invalidation behavior. It was absent
from the final LLM request and seven-item accepted list (lines 1163/1168); the unchanged post-LLM active-island
preservation function appended it. This is active-island preservation, not dormant-island completion and not a
new rationale-based promotion. Do not claim the new field fixes deterministic post-selection admission.

The missing `builder.ts` is upstream of this change in both runs: raw dense/sparse counts were 13/3 and 8/12;
CodeGraph submitted/resolved 11/10 and 15/15 range/owner occurrences (line 51). Canonical pools retained 10/12
snippets, but file positions 17/6 failed initial admission (line 54), before qualification reasons exist.
`builderState.ts` had 6/4 and 6/5 raw dense/sparse hits, eight resolved owner occurrences in each, and 7/8
canonical snippets. It was excluded at file position 9 in run 1, later recovered and qualified direct in round 3
(line 706), and returned at rank 5. Run 2 admitted it at file position 1 and returned updateShapeSignature and
updateExportedFilesMapFromCache at ranks 6/7. No attribution of that different early admission to this patch.

## Decision and artifacts

Mechanically verified and retained for review as the requested bounded continuity field; **not demonstrated as
an overall retrieval-quality improvement**. Baseline Oracle counts were 3/2 versus 2/2 here, with materially
different upstream admission. No new heuristic, budget increase, source-description code, or explanation change.

Audit script: `testing/codeRepoQA/audit_qualification_rationale.py`; saved per-run audits under
`testing/codeRepoQA/qualification-rationale-runs/`. Actual traces and results stay in the original testcase run
directories. Each run is labelled `qualification-rationale-carryforward`, separate from baseline and the reverted
source-description cohort. Detailed trace line numbers above refer to each run's `retrieval-trace.jsonl`.

## Follow-up: why only two Oracle files (loss-boundary audit)

Both returned BuilderState and tsbuild/watchMode; the missing implementation-Oracle files were Builder and
tscWatch/Helpers. This is not a uniform final-input-budget failure.

- Run 1 initial admission (line 54): watch.ts adds 8 candidates / 11,390 request characters; tsbuildPublic.ts
  adds 26 / 23,809; watchMode.ts adds 28 / 14,965; editorServices.ts adds 43 / 40,613. Cumulative input moves
  11,390 -> 35,199 -> 50,164 -> 90,777, crossing the 60K preferred threshold at the fourth file. These are exact
  marginal serialized request costs, including metadata/schema, not source-only characters. The 43 editor owners
  produce zero owner-comparison selections (line 59); largest prepared editor owner source is 1,020 characters
  (line 53). Builder at file rank 17 and Helpers at 41 are excluded before comparison. The problem is a large
  whole-file group, not one unbounded snippet. Helpers' one initial dense hit is lines 76-80 (line 40), not the
  eventual verifyTscWatch owner.
- Run 2 admission (line 54): BuilderState adds 8 / 11,462; tsbuildPublic adds 26 / 25,009; watchPublic adds
  12 / 10,388; watchMode adds 30 / 16,840. Cumulative input reaches 63,699; Builder at rank 6 is excluded after
  the crossing watchMode group. Helpers has no initial exact file hit in the logged dense/sparse breakdown, but
  raw retrieved ranges contain explicit verifyTscWatch call sites in other files. The source at logged raw ranges
  in the unchanged snapshot confirms 29/30 channel-hit occurrences containing that call in runs 1/2. These are
  retrieval leads, not exact helper-owner retrieval, and the controller does follow such a lead in both runs.
- Run 1 recovers Helpers into qualification: verifyTscWatch, 223 characters, in round 1 (request 263, decision
  265); tscWatchCompile, 941 characters, and baselineProgram, 1,113 characters, in round 3 (704/706). All three
  become navigation-only with zero supported obligations. They remain in the general final candidate pool
  (947), but do not enter obligation-specific final-selection input (952): progress is built from candidate
  obligation IDs, not all navigation candidates. The final flow ledger (949) has zero budget exclusions and
  the final serialized request is only 32,016 characters (951). Their loss is qualification/eligibility, not size.
- Run 2 recovers the same complete 223-character verifyTscWatch wrapper in round 2 (558), but qualification
  rejects it as insufficient (560): it groups scenario/subscenario and calls tscWatchCompile without showing
  the concrete diagnostic scenario. It is absent from the final candidate pool (1158), before final budgeting.
- Run 2 does exclude one watchMode range, lines 1187-1213, after the 45K final-flow threshold is crossed (1160).
  Other watchMode evidence is returned, so that exclusion does not explain either missing Oracle file.

These findings map to existing FPK-1/IOC-1 whole-file admission and QRC-1 semantic eligibility boundaries.
No ranking, budget, qualification or final-selection behavior was changed during this read-only run audit.

### Correction: Helpers also survives as a file trace before a separate eligibility gate

Both runs create a WatchMode-to-tscWatch/Helpers file trace: `021522Z` trace line 945 and `021533Z` line 1156.
Each records 18 direct file-level call sites (16 verifyTscWatch, two checkOutputErrorsInitial). The trace source
is `obs_158e2d5a3ab67ecb` / verifyTransitiveReferences, the root of the file-expansion action, not every owner in
the source file. The summary itself names other localized callers, so file-level connectivity must not be
mistaken for a verified call from that particular root owner.

Both traces fail before the dedicated file-trace LLM: lines 955/1166 record `source_island_not_selected`,
`source_accepted=false`. Despite that label, obligation_retrieval.py maps source_candidate_ids using exact
source observation identity, then requires acceptance by final snippet consolidation. Run 1's root is
navigation-only with no obligations and absent from final input; run 2's direct root reaches final input but
is not selected. Returning another WatchMode owner later through active-island preservation does not rerun
this check. Neither exclusion is a file-trace character-budget failure.

Historical contrast: `run-20260826T094609Z`, trace line 2017, selects Helpers as unresolved file evidence with
`source_accepted=true`, even though its endpoint is `defer/insufficient`. The LLM explicitly preserves a distinct
verification participant without claiming that the unresolved helper proves the issue behavior. Thus the
earlier explanation of the two latest missing Helpers files was incomplete: qualification explains the
snippet path; exact-source eligibility explains the independent file-level path.
