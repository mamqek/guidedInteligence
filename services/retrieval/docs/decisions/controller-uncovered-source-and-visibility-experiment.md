# Controller Uncovered-Source and Visibility Experiment

## Status and boundary

Completed incremental experiment. The initial retrieval path through Qdrant retrieval, exact-range deduplication,
CodeGraph resolution, canonicalization, file admission, initial owner comparison, and round-zero snippet selection is
unchanged. Controller-wide residual materialization, forced complete-source reservation, rejected-owner lifecycle
re-entry, experiment-specific uncovered-range telemetry, and trace-only rendered-owner visibility were measured and
reverted. The independently accepted raw-source/materialized-snippet/loss telemetry remains.

The experiment separates two loss boundaries:

1. **materialization coverage:** whether every part of a controller-retrieved range survives ownership conversion as
   either a structural snippet or an unresolved residual snippet;
2. **rendered-owner completeness:** whether qualification actually receives the complete smallest resolved owner.

Semantic relevance remains an LLM qualification decision. Neither condition promotes source deterministically.

## Baseline

- A retrieved range resolving to any owners produces only those owner snippets; uncovered portions disappear.
- `DisclosureCard` retains complete and preview strings internally, but the post-fit card does not state whether the
  complete owner survived the 40,000-character qualification fit.
- Explicit inspection is fitted like every other card and therefore does not guarantee a more complete view.
- Controller materialization telemetry records only the complete failure where one raw source produces zero snippets.

## Incremental sequence

### Step 1 — Hypothetical residual telemetry

Boundary: controller `_execute_search` only. Calculate `retrieved range - union(resolved owner intersections)` and
trace the residual intervals that would be retained. Do not create observations or alter qualification.

Expected cost: deterministic line/range arithmetic and trace bytes only. Candidate and LLM-token counts are unchanged.
Risk: incorrect interval arithmetic or misleading counts when owners extend beyond the retrieved range.

Acceptance: focused fixtures cover no owners, containing owners, partial owners, multiple owners, and overlapping
owners; two real controller runs expose auditable residual counts without changing materialized snippets.

### Step 2 — Post-fit owner-completeness telemetry

Boundary: disclosure/fitting and traces. Add `owner_source_complete` to `DisclosureCard`, compute it conservatively
before and after fitting, and trace the post-fit value. Do not change qualification decisions or action eligibility.

Expected cost: one boolean per card. No candidate-volume change.
Risk: incorrectly marking nested skeleton views complete or treating unresolved ranges as resolved owners.

### Step 3 — Controller-only residual materialization

Boundary: controller `_execute_search`. Convert measured, non-empty residual intervals into unresolved observations
with exact sliced text and original Qdrant provenance. Do not change shared initial `observation_from_result` behavior.

Expected cost: more controller observations and qualification source. Initial comparison cost remains unchanged.
Risk: fragmented/noisy residuals displace better controller cards.

Rollback when residuals are predominantly noise, lifecycle counts become unstable, or token growth lacks a repeatable
source-quality benefit.

### Step 4 — Reserved explicit inspection

Boundary: controller qualification fitting. Existing inspection actions may reserve complete views for at most two
resolved small owners under the existing 80-line/4,000-character card limits and 40,000-character request ceiling.

Expected cost: no new model call; at most 8,000 source characters redistributed from other cards.
Risk: non-reserved evidence is starved.

### Step 5 — Incomplete-handle lifecycle

Boundary: action eligibility and lifecycle accounting. A negative judgment over an incomplete resolved owner retains
one bounded inspection opportunity. Unresolved residuals do not receive repeated full-owner inspection merely because
they lack an owner. Every handle ends selected, deferred, dormant, rejected-complete, or inspection-exhausted.

All actions continue through typed validation, pre-slot novelty suppression, scheduler/executor accounting, normal
trace logging, and run-local deterministic request memoization.

### Step 6 — Combined acceptance

After each prior step is independently accepted, run two Pandas and two Vue actual-pipeline comparisons with response
generation skipped and final evidence selection enabled. Audit residual usefulness, post-fit visibility, inspections,
candidate displacement, final evidence, and retrieval tokens.

## Explicit exclusions

- no change to initial/prequalification materialization or selection;
- no coverage-owned agent action selection;
- no new action type or semantic qualification enum;
- no automatic large-owner paging;
- no repository- or Oracle-specific rule;
- no silent decision rewriting or LLM fallback.

## Result ledger

| Step | Attempt | Focused run 1 | Focused run 2 | Cost change | Decision | Remaining issue |
|---|---:|---|---|---|---|---|
| Hypothetical residual telemetry | 1 | Pandas `run-20260825T224035Z`: 21 raw ranges, 12 residuals/57 lines | Pandas `run-20260825T224325Z`: 30 raw ranges, 12 residuals/44 lines | Trace bytes and deterministic arithmetic only; materialized counts unchanged | accepted | Residual usefulness varies; first run preserved the missing Series method-installation statements while both runs also found blank/import/module-level fragments |
| Post-fit completeness telemetry | 1 | Pandas `run-20260825T224806Z`: 28/38 complete | Pandas `run-20260825T225115Z`: 23/40 complete | One trace boolean/card; no qualification-payload change | accepted | No global-budget truncation naturally occurred; incomplete cards were ambiguous folds plus large/unresolved/continuation previews |
| Controller residual materialization | 1 | Corrected Pandas `run-20260825T234452Z`: two true residuals reached qualification; neither reached final evidence | Corrected Pandas `run-20260825T234825Z`: one true residual reached qualification; it did not reach final evidence | 72,015/73,003 retrieval tokens; no repeatable final mechanism gain | rejected and reverted | Earlier positive counts included a discovered no-owner duplication: source already preserved by the ordinary unresolved path was incorrectly tagged again as a residual |
| Reserved explicit inspection | 1 | Pandas `run-20260825T231307Z`: two reservations completed (613/558 chars) | Pandas `run-20260825T231704Z`: two reservations completed in rounds 1/3 (37/980 chars) | No new calls; exact source redistributed inside existing 40K requests | rejected and reverted | Final-state trial `run-20260826T000256Z` reserved two deferred test owners and then lost all implementation evidence; repeat `run-20260826T000519Z` reserved one test owner and retained `_binop`. The benefit was not stable or mechanism-directed |
| Incomplete-handle lifecycle | 1 | Focused tests: rejected incomplete resolved small owner regained one typed inspection | Pandas `run-20260825T232212Z`: no globally truncated eligible owner occurred naturally | No new action type or slot | rejected and reverted | No natural activation demonstrated a quality benefit, so the new rejected-owner re-entry policy did not meet the acceptance boundary |
| Combined acceptance | 1 | Final non-behavioral Pandas `run-20260826T001953Z` / `run-20260826T002319Z`: `partial/false`, Oracle ranks 3/2, 73,763/65,955 tokens | Final non-behavioral Vue `run-20260826T001050Z` / `run-20260826T001345Z`: `partial/false`, Oracle rank 1 in both, 66,721/63,452 tokens | All below 100K; telemetry recorded 30/19 and 1/2 residual intervals with zero behavior changes | accepted for telemetry/visibility only | The controller still fails to complete the Pandas generated-registration chain and Vue downstream SSR serialization chain |

## Final decision

Do not materialize every uncovered interval as a canonical controller snippet. The corrected four-run acceptance showed
no repeatable final mechanism gain, and Vue demonstrated that a source-valid residual can still be irrelevant benchmark
noise. Do not force complete-source allocation merely because the scheduler selected an inspection, and do not reopen a
rejected owner solely because its fitted card was incomplete; those behaviors did not show stable mechanism quality.
The later design review established that trace-only completeness was not the central hypothesis: the LLM needed to see
semantic qualification and completeness together and decide whether inspection had value. The experiment-specific
uncovered-range telemetry and `owner_source_complete` runtime field are therefore also reverted to restore a clean
baseline. Their measurement code can be reintroduced inside the integrated LLM-guided experiment rather than retained
as partially connected plumbing.

The replacement plan is
[`../temporary-source-visibility-and-agent-inspection-plan.md`](../temporary-source-visibility-and-agent-inspection-plan.md).
It treats the compact incomplete-handle catalogue, coverage-owned LLM action choice, typed novelty-checked execution,
and materially expanded requalification as one behavioral experiment. No component is accepted merely because its
mechanics work in isolation.
