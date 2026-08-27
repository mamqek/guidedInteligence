# Append-crossing input-budget experiment

## Correction requested after review: preserve relationship metadata

The original implementation incorrectly let the crossing flow exhaust a second,
later budget gate for connections. That is not an acceptable consequence of retaining
one extra evidence unit. Correct only the connection stage: keep the exact admitted
candidate/flow prefix, then attach every already-eligible connection whose endpoints
are retained. Connections are metadata of that retained evidence, not new evidence
units competing for another slot. Continue measuring their characters and final
serialized size, but do not discard them because the final flow crossed the threshold.

No ranking, candidate selection, qualification, source disclosure, model output cap,
graph discovery, or relationship eligibility changes. Expected impact: recover the 12
eligible connections in each saved failed final request, without changing its candidates
or flows. Risk: larger metadata payload, explicitly measured. Verify focused tests and
same-input saved-boundary replays before another full-run comparison; prior failed runs
do not count as acceptance of this correction.

### Focused correction results

The 203-test suite passes. Saved-input replay was repeated byte-for-byte identically
(SHA-256 `4B4295531EE1C1EB59826B573F7AC4CBCC778453952F4ABFB9F3EE5E9C64D98B`).
Both recorded selected candidate sets and ordered flow prefixes reproduce exactly;
pre-connection character accounting also reproduces exactly.

| Saved run | Candidates / flows unchanged | Connections before → corrected | Literal user payload before → corrected |
|---|---|---|---|
| 131714Z | 13 / 11 | 0 → 12 | 48,180 → 51,671 characters |
| 131856Z | 16 / 12 | 0 → 12 | 47,971 → 51,421 characters |

The literal size calculation replaces only `candidate_connections` in the saved
request. Recovered metadata includes `BuilderState.updateShapeSignature(...)`,
`invalidateProjectAndScheduleBuilds(...)`, and the existing CodeGraph connector paths.
No new edges are inferred beyond the unchanged connection eligibility logic.
Artifacts: `connection-preservation-replay.json` and `connection-preservation-replay-repeat.json`.
Their `recorded_*` / `replay_connection_*` / `*_literal_payload_chars` fields isolate
this repair; legacy `old`/`added`/`removed` fields compare the earlier Git baseline,
not the before/after of this correction.

Two fresh actual pipeline attempts started: `run-20260827T142925Z` and
`run-20260827T142935Z`. Same model, 4,000 completion-token limit, index scope, and
round settings; explanation skipped, final selection enabled. No additional
replacement attempts planned if the unchanged LLM contracts fail.

### Completed correction verification

Both fresh runs completed without retry or model/config changes. Index-ready line 9
in each records `rebuilt=false`. The connection repair is retained; it is not evidence
that source visibility or semantic qualification has been fixed.

| Run | Final payload characters | Eligible / retained connections | Final output tokens (reasoning) | Retrieval tokens | Final result |
|---|---:|---:|---:|---:|---|
| run-20260827T142925Z | 51,075 | 8 / 8 | 3,869 (667) | 113,718 | partial / false; 3 implementation Oracles; 14 evidence items / 5 files |
| run-20260827T142935Z | 37,224 | 9 / 9 | 3,600 (886) | 97,572 | partial / false; 3 implementation Oracles; 12 evidence items / 7 files |

Run 142925Z crosses the 45K flow threshold at 48,148; relationship metadata brings
accounting to 50,443. Ledger 1891 and actual payload 1893 retain all eight eligible
connections despite overflow; response 1895 finishes normally with 12,600 content
characters. builderState.updateShapeSignature reaches final rank 10. Run 142935Z
does not cross the flow threshold: total accounting including nine connections is
37,067; payload 1836 is 37,224; response 1838 finishes normally with 11,076 content
characters. builderState.updateShapeSignature is rank 6, getFilesAffectedBy rank 7,
and updateExportedFilesMapFromCache rank 8. Both retain builder.ts and watchMode.ts.

Per-stage tokens (run 142925Z / 142935Z): context 1,767 / 1,871; owner comparison
26,679 / 22,837; qualification 32,835 / 34,274; coverage 33,597 / 23,742; final selection
18,840 / 14,848. Total new verification cost: 211,290 tokens. No explanation tokens.

These live runs vary upstream, so neither their Oracle overlap nor lower totals
against the failed attempts establish a causal quality/cost gain. The controlled
evidence is the unchanged selected candidate sets and flow prefixes in the saved
replay, with only connection metadata restored. The live overflow run confirms that
the real final request no longer strips those relationships. Final sufficiency is
still false, and the qualification downgrade/source-preview issues remain open.

Reproduction: `analyze_append_crossing_budgets.py` over the two run directories,
output `testing/codeRepoQA/qualified-file-lead-replays/connection-preservation-live.json`.

### Clarifying the independent earlier failures

For `getReferencedByPaths` in run 124548Z, qualification requests at lines 913 and
1340 contain the identical complete 331-character function body, both in full mode.
They contain the same obligations but different batches (six versus five snippets).
Round 2 assigns direct evidence for explain_subject (915); round 3 assigns navigation
only and no obligations (1342), citing missing reference-map population/wildcard proof.
The controller overwrites the earlier decision and candidate with the later one.
Thus this is semantic reclassification on unchanged source, not body truncation or
the qualified-helper final-flow filter. That filter only sees candidates that survive
obligation-state mapping. Partial-mechanism support versus complete obligation proof
is an unresolved qualification boundary (QFL-1/QOS-1), not changed in this repair.

The failed final requests explicitly sent `max_completion_tokens: 4000` to
gpt-5.6-luna. This is the entire response allowance, not a per-snippet input size.
Both responses in each run report `finish_reason=length`, 4,000 completion tokens,
4,000 reasoning tokens and zero content characters. The setting originates from
generation.max_tokens and is reused for retrieval LLM calls. Its identical-budget
JSON retry cannot guarantee room for actual JSON. A future controlled correction
should give final selection its own output allowance and distinguish output-budget
exhaustion from ordinary invalid JSON; neither change is included here. The traces
do not reveal why reasoning consumed the entire allowance or prove that missing
connections caused it.

## Request and fixed baseline

The user rejected skip-oversized-and-continue packing on 2026-08-27. Replace it with
ranked-prefix admission that includes the unit crossing the threshold, then stops.
Keep qualified-helper final-flow eligibility unchanged. Do not change ranking,
shortlisting, source previews, qualification, model, controller rounds, or index scope.

Actual configured thresholds are 60,000 preferred / 100,000 maximum initial comparison
characters and 50,000 final-selection characters (45,000 for flows after the existing
5,000 overhead reserve). This experiment changes stopping semantics, not these values.
These become append-then-stop thresholds: a complete crossing unit can exceed them.

## Separate boundaries

1. Initial owner comparison: append the next ranked complete file group while the
   existing request is not over either threshold. Measure the resulting serialized
   request, including prompt and schema, and stop after a crossing group. Do not
   backfill with smaller later files. Adapt the comparison-stage guard to allow this
   single crossing group, but reject requests containing further groups after crossing.
   Trace the crossing path, before/after characters, overshoot and all excluded paths.
2. Final selection: preserve causal/duplicate filters and adaptive flow ordering.
   Append the next eligible whole flow and its newly introduced snippets; stop after
   crossing the existing flow threshold. Subsequent connection admission uses the
   same already-over check. No downstream trimming may remove the crossing flow.
   Log the stopping rule, crossing flow and actual serialized final payload separately.

The admission units are file groups and mechanism flows, not individual text characters.
Overshoot can therefore be substantial. The per-snippet text limits and final evidence
count caps are unchanged. More input does not imply semantic acceptance.

## Verification and risks

- Focused boundary tests: below/equal/over thresholds, first oversized group, no
  smaller-file backfill, exact serialization and compatible comparison validation.
- Final-flow tests: complete crossing flow retained, no later flow added, helper
  semantic proof preserved, connection accounting and unbounded mode unchanged.
- Replay saved actual initial-admission input twice; distinguish deterministic
  counterfactual admission from actual LLM selections.
- Run TypeScript twice through the real npm evaluation surface, explanation disabled,
  final selection enabled, indexes reused. Record IDs, trace boundaries, tokens,
  coverage, sufficiency and implementation Oracle retention.
- Main expected benefit: the high-ranked crossing file/flow survives. Main risks:
  larger requests, changed LLM choices and displacement of other relevant evidence.
  Do not credit upstream/model variation to this change. Per user instruction, explain
  questionable quality results before reverting rather than silently removing it.

## Result ledger

| Boundary | Variant | Focused verification | Actual runs | Decision |
|---|---:|---|---|---|
| Initial comparison | 1 | 17 tests; identical saved-input replay twice | Three admission boundaries pass; one LLM contract failure | Mechanically verified, provisional |
| Final flow admission | 1 | 78 tests; crossing-unit invariants pass | Two final payloads preserve the crossing flow; both LLM calls fail | Mechanically verified, quality unverified |

## Existing diagnosis (not changed here)

- Pandas `run-20260827T125119Z`: `_binop` resolves to the complete owner at
  1466–1511, but its source view is only the 1466–1473 intersection of the raw
  1434–1473 hit (canonical trace line 61; literal comparison request line 65).
  The 80-character comparison preview shows the signature, not the full body.
  Correct owner identity/bounds do not guarantee useful pre-comparison disclosure.
- TypeScript `run-20260827T124548Z`: `getReferencedByPaths` becomes direct evidence
  at qualification trace line 915, then navigation-only without obligations at line
  1342. All surviving builderState snippets have no supported obligations and are
  absent from the final-flow inventory at line 1726. This explains its missing third
  implementation Oracle before the helper-filter exception can apply.

## Focused results and active runs

- Initial boundary: 17 focused tests pass, including a single group exceeding the
  maximum threshold, rejecting another group after that crossing, and exact equality.
- Final boundary: 78 tests pass, including retaining the complete crossing flow,
  no later-flow backfill, and the still-required helper semantic/call proof.
- Combined regression suite: 203 tests pass. `git diff --check` passes.
- Same-input Pandas replay `run-20260827T104726Z`, repeated identically:
  original prefix 4 files / 52 snippets / 20,356 characters; append-crossing prefix
  5 files / 209 snippets / 68,020 characters. The extra file is `pandas/tests/test_series.py`,
  with 157 snippets; `series.py` is still outside the prefix. The rule does not guarantee
  recovery of a desired file. Artifacts: `append-crossing-initial.json` and
  `append-crossing-initial-repeat.json` under `testing/codeRepoQA/qualified-file-lead-replays/`.
- Actual TypeScript runs started: `run-20260827T131714Z` and `run-20260827T131856Z`.
  Both use the unchanged workspace profile and skip explanation only.

### Invalid attempt: run-20260827T131714Z

Initial admission line 53 includes `src/server/project.ts`, moving 58,306 to 65,497
characters (11 files / 187 snippets). Its 23 snippets are all dormant after comparison.
Final flow ledger line 1776 includes the crossing `getNextInvalidatedProject` flow:
42,032 + 5,514 = 47,546 characters against the 45,000 threshold. Actual user payload
at line 1778 is 48,180 characters (13 snippets / 11 flows). Literal LLM request is
line 1779, with its identical retry at line 1782.

Both final responses finish with `length`: all 4,000 completion tokens are reasoning,
and content is empty. The pipeline explicitly fails; no final quality score exists.
126,329 recorded retrieval tokens, including both failed final calls (18,044 each).
The same failure occurred in baseline attempt `run-20260827T123717Z`; do not claim
the new input policy alone caused it. An unchanged replacement run is required.

The final connection list is serialized after flows. Once a flow crosses the shared
threshold, no later connections are added: this input has 12 eligible connections
and zero admitted connections. This is a measured consequence of the requested stop
rule, not a claim that the candidates lack source-level relationships. It may weaken
final comparison; changing the connection/flow admission unit is a separate decision.

## Completed attempt ledger (no valid final-quality results)

| Run | Initial files / snippets / characters | Flow accounting / actual user payload | Retrieval tokens | Outcome |
|---|---|---|---:|---|
| run-20260827T131714Z | 11 / 187 / 65,497 | 47,546 / 48,180 | 126,329 | Final request and retry exhaust 4,000 completion tokens with empty output |
| run-20260827T131856Z | 16 / 188 / 60,342 | 47,548 / 47,971 | 125,218 | Same final-output failure on request and retry |
| run-20260827T132218Z | 16 / 169 / 60,051 | Not reached | 24,619 | Owner-comparison model assigns two owners to the wrong file group |

All three reused the index (`workspace_index_ready`, line 9, `rebuilt=false`). Explanation
generation was disabled; final selection was enabled. There is no coverage_status,
sufficient value or implementation-Oracle result for any of these invalid attempts.
Do not report zero Oracles or partial/false as if those were measured final outcomes.
Total measured expenditure including failed calls: **276,166 retrieval tokens**.

In run 131856Z, initial admission line 53 appends `server/editorServices.ts`, adding
4,495 characters to 55,847; all 14 crossing-file snippets become dormant. Flow ledger
line 1809 appends the `startWatching` flow, introducing `startWatching`,
`watchWildCardDirectories` and `invalidateProjectAndScheduleBuilds`: 40,916 + 6,632 =
47,548. These are source-connected watch setup/invalidation mechanisms, not proof
of the reported wildcard re-export failure. They reach the literal final request;
the model never produces a valid final decision. Budget line 1811 records 16 snippets,
12 flows and 47,971 user-payload characters. As in run 131714Z, 12 eligible explicit
connections receive zero room after flow admission.

Run 132218Z includes `tests/lib/react16.d.ts` as the crossing file. Its comparison
response at line 57 selects `o81` (`verifyTransitiveReferences`) and `o86`
(`verifyTransitiveReferences::verifyScenario`) under `g7`, although both belong to
`g6`. The unchanged membership validator rejects the response. No silent repair,
fallback selection, relaxed schema or completion-limit increase was introduced.

### Cost comparison and attribution

Initial-comparison tokens: 24,289 / 23,163 / 22,875. Previous completed helper runs
123853Z / 124548Z used 21,886 / 22,819 comparison tokens, and 107,658 / 88,298 total
retrieval tokens. Those are different upstream inputs, not controlled cost deltas.
The deterministic saved-input replay isolates file admission. The literal crossing
flow proves preservation at the changed final boundary. Whole-run costs here are
inflated by invalid final retries (36,088 / 35,852 tokens for the two final stages).

The larger comparison pool has no demonstrated benefit from either server crossing
file, since every one of those snippets is dormant. The final crossing flows contain
plausible supporting mechanisms, but final selection quality is unknown. Repeated
final-output failure and missing connection metadata prevent acceptance. The output
failure also existed before this change; its frequency here is a warning, not proof
of one causal explanation.

### Decision and artifacts

Keep the user's requested rule **provisionally**, without claiming a quality improvement
or silently reverting it. Skip-and-continue is removed. Qualified-helper eligibility
is unchanged. Stop after two requested attempts and one unchanged replacement rather
than purchasing indefinite retries or broadening this task into LLM-contract repair.
Quality acceptance remains incomplete. Next decisions concern final-call reliability
and whether essential connection metadata should be part of each admitted flow's unit.

`testing/codeRepoQA/qualified-file-lead-replays/append-crossing-all-runs.json` records
exact trace-line references, payloads, crossing snippets, per-stage tokens and response
termination details. `testing/codeRepoQA/analyze_append_crossing_budgets.py` reproduces
that report from the literal traces. The 203-test combined suite passed twice.
