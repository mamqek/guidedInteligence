# Dormant file alternatives experiment plan

Status: retained as the default bounded controller behavior. The testcase CLI may still disable it for ablation.

Rejected scheduling follow-up: making round 3 the action's sole admission opportunity was tested without changing
eligibility, title support, disclosure, or qualification. The first implementation allowed `no_evidence_gain` to
terminate before round 3. A corrected implementation treated the delayed action as pending work and allowed a
productive round-3 rescue to open round 4. That made scheduling mechanically reliable but changed the winning file
after two rounds of new observations, forced otherwise unnecessary rounds, and produced unstable quality. The
follow-up was reverted; immediate opt-in scheduling remains the experimental behavior.

## Problem

`ExpandWithinFileHandoff` begins from a qualified observation and follows a qualification-produced local handoff.
It is effective local flow completion, but it cannot bootstrap a file whose admitted owners are all dormant or
rejected. In pandas 10068 `run-20260831T121739Z`, raw retrieval found the complete
`pandas/core/series.py::Series._binop` owner, but the file had no qualified observation. Every controller round marked
that owner `not_a_same_file_alternative_to_a_qualified_observation`, so no same-file action could inspect it.

Across 26 recent actual runs from five cases, the existing action executed 100 times: 98 executions produced new raw
source and 34 produced at least one newly retained evidence item, comprising 67 newly retained endpoints. It should
therefore remain a separate action rather than be replaced.

## Naming

Rename `SearchWithinFile` to `ExpandWithinFileHandoff`. The proposed name describes its actual contract: start from a
qualified owner, use the explicit missing local handoff, and expand to additional owners in the same file. Preserve
the serialized action type as a temporary trace alias only if old-trace replay requires it; do not keep duplicate
runtime implementations.

Add a distinct action named `InspectDormantFileAlternatives`. It reviews already-retrieved owner handles in a file
that has no qualified evidence. It is not a repository search and does not read the complete physical file.

## Eligibility

Create one dormant-file candidate only when all conditions hold:

- the normalized file has zero retained direct or navigation observations;
- at least two distinct structural owner handles from that file already exist in the deferred/dormant pool;
- those handles collectively support at least two unresolved obligations;
- either at least three distinct named structural owners ground the file independently, or a smaller two-owner
  hypothesis has owner-level title/request support;
- at least one associated obligation remains unresolved;
- the file has not already received this action in the run;
- no selected or pending action is already inspecting the same owner handles.

Rank self-grounded structural clusters primarily by semantic retrieval strength and unresolved-obligation breadth;
use title, request, and path overlap as later bonuses rather than eligibility vetoes. For a small two-owner
hypothesis that requires lexical grounding, title/request support may disambiguate the issue subject from a
comparison file. Recurrence may break ties but must not suppress a unique high-semantic owner merely because
unrelated owners recur more often.

## Execution contract

- Select at most one dormant file per run in the first implementation attempt.
- Disclose at most five distinct already-retrieved owners, capped by the existing qualification input budget.
- Prefer obligation-diverse owners and always include the file's best semantic owner; do not concatenate the entire
  file.
- Qualify all disclosed owners in one existing nested qualification request. Do not retry the LLM and do not use a
  deterministic fallback.
- Promote each owner independently according to the normal qualification contract. Same-file membership alone does
  not merge owners into one semantic island.
- Record the normalized file attempt key even when all owners defer or reject, preventing repeated inspection.
- The action consumes one existing ordinary action opportunity and adds no controller round. A later experiment may
  revisit scheduling only if the action is repeatedly eligible but starved.

## Relationship to earlier experiments

This exact action has not been tested. `InspectDeferredObservation` discloses one globally ranked deferred handle at
a time. The removed deferred-file-rescue fold allowed individual deferred seeds to compete with active-island work
and selected zero rescues. Dormant island completion requires a newly matured active source to expose a dormant
target. None batches several known owners from a zero-qualified file, so those results do not answer this experiment.

## Verification

Focused tests:

- pandas-shaped file with `_binop` plus several weaker retrieved owners produces one action and includes `_binop`;
- a file with an existing qualified observation remains owned by `ExpandWithinFileHandoff` and is ineligible here;
- single-hit, already-attempted, resolved-obligation, duplicate-owner, and over-budget cases are rejected;
- one failed batch is recorded once and never repeated;
- retained results enter ordinary island construction without forced same-file merging.

Actual pipeline:

1. pandas 10068 twice, with final selection enabled and response generation skipped;
2. TypeScript 35468 twice for regression and token comparison;
3. Vue 242 once for cross-language regression.

Compare action activation, disclosed owners, qualification dispositions, new islands, final candidate pool, Oracle
files, total retrieval tokens, `coverage_status`, and `sufficient`. Revert or leave disabled if both pandas runs fail
to expose useful Series evidence, or if TypeScript/Vue regress under unchanged settings.

## Results and adjustments

- The first integration enumerated candidates but starved them behind active-island scopes. Scheduling was corrected
  to reserve one of the existing ordinary slots; no new slot or round is created.
- A subsequent pandas run inspected `index.py`, `series.py`, and `test_index.py` over three rounds. This violated the
  intended bound. The scheduler now permits one dormant-file effect per run, regardless of path.
- Title-aware ranking corrected the issue-subject/comparison confusion (`Series` in the title versus `Index` in the
  explanatory body). Pandas `run-20260831T163654Z` executed exactly one batch on `pandas/core/series.py`, qualified
  `Series::_binop`, reached 2/3 Oracle overlap including the sole implementation Oracle, used 98,651 tokens, and
  remained `partial/false`.
- `run-20260831T163247Z` failed explicitly after the action because the qualification LLM returned an invalid nested
  disposition/evidence-kind combination. It is not an acceptance run; no retry or deterministic fallback was added.
- Vue `run-20260831T165814Z` exposed a weak path-word trigger on `directives/repeat.js`. The final gate now requires
  owner-level semantic support. Final Vue `run-20260831T172444Z` executed no dormant action and retained its
  implementation Oracle without `binding.js` noise.
- TypeScript `run-20260831T170259Z` exposed an exact-anchor-only false activation on `compiler/utilities.ts`; it
  consumed a slot and the run retained only Builder. Exact metadata without owner semantic support is now
  insufficient. Final-code runs `run-20260831T171235Z` and `run-20260831T171810Z` both recovered all four target
  files. The first executed no dormant action; the second inspected strongly matching `server/project.ts`, whose
  candidates were correctly rejected later without displacing the four-file result.

Historical decision at that experiment boundary: retain the action as an explicit opt-in for further corpus
measurement because TypeScript showed that even grounded dormant files could consume work without contributing
final evidence. Subsequent default promotion and its later grounding correction are recorded below.

## Title-independent structural grounding correction

Later default-enabled TypeScript runs exposed that the owner-level lexical safety gate had become a hard veto:
`run-20260901T183939Z` rejected six named BuilderState owners across two unresolved obligations and
`run-20260901T184539Z` rejected seven across three because neither an owner nor its symbol literally matched the
request title. `server/project.ts` was eligible solely through the generic word `project`. This contradicted the
action's purpose: independently retrieved named owners are grounded repository evidence even when the issue author
does not know their implementation name.

The action now accepts three or more distinct named structural owners as title-independent grounding while retaining
the two-owner lexical boundary that prevented the Vue `repeat.js` false activation. Semantic retrieval rank is
evaluated before lexical bonuses for these self-grounded clusters. The one-file-per-run and five-disclosed-owner
limits are unchanged.

Focused controller coverage passes 224 tests. Actual TypeScript 35468 acceptance retained the established floor:

- `run-20260901T204825Z`: 3/4 focal files, 122,868 retrieval tokens. BuilderState had five named owners but only one
  unresolved obligation and therefore did not match the corrected multi-obligation shape.
- `run-20260901T205528Z`: 4/4 focal files, 113,633 retrieval tokens. Seven BuilderState owners across two unresolved
  obligations became eligible with zero title/request owner support. `server/project.ts` won the single dormant slot;
  the ordinary round-three `InspectDeferredObservation` continuation independently qualified
  `getFilesAffectedByUpdatedShapeWhenNonModuleEmit`, which survived final selection at focal file rank 4.

The correction is retained because it removes the lexical veto without increasing slots, rounds, disclosed-owner
capacity, or the weak two-owner activation surface. It does not guarantee that every eligible dormant file executes.

## Rejected round-three scheduling follow-up

The scheduling-only variant first suppressed dormant inspection in rounds 1-2 and reserved one ordinary slot in
round 3. Two lifecycle defects had to be made explicit: `no_evidence_gain` could stop before the promised round, and
a productive round-3 dormant action did not qualify for the existing fourth-round continuation rule. The corrected
variant temporarily treated the known rescue as pending work through round 2 and allowed round 4 after a productive
dormant inspection.

Measured actual-pipeline results, with title support and all candidate gates unchanged:

- pandas `run-20260831T205925Z`: 2/3 Oracle files including `pandas/core/series.py`, 102,917 tokens;
- pandas `run-20260831T210407Z`: 1/3 Oracle files, 81,018 tokens; the delayed winner drifted to
  `pandas/computation/ops.py` and its continuation remained there;
- TypeScript `run-20260831T211039Z`: Builder, WatchMode, and Helpers survived, but BuilderState was lost; 133,704
  tokens. The delayed dormant batch inspected `src/compiler/watchPublic.ts`, which did not survive final selection.

All three runs remained `partial/false`. The variant was rejected because postponement made the candidate compete
against observations introduced by earlier controller actions and required preserving controller execution merely
to reach its scheduled opportunity. It was therefore neither a stable quality improvement nor a dependable cost
reduction. The original immediate opt-in scheduling was restored.
# Follow-up: balanced dormant-file ranking (2026-09-02)

## Observed defect

Pandas 10068 `run-20260902T002808Z` had ten distinct `core/series.py` owners and five
`core/base.py` owners. Both reached the five-owner structural cap. The lexicographic ranking then let Base's five
raw unresolved-obligation associations defeat Series's four before Series's substantially stronger request, title,
path, and retrieval evidence could be considered. Those obligation associations are retrieval provenance, not
qualified semantic support.

## Scoped change

Change only file ranking in `actions/dormant_file_alternatives.py`. Eligibility, the exact-anchor hard preference,
the one-file-per-run limit, the five-owner disclosure limit, scheduling, source materialization, qualification, and
final selection remain unchanged.

After eligibility, calculate one capped additive score from:

- independently retrieved structural-owner strength;
- support for obligations that are unresolved in the current controller state, discounted when only one owner
  carries an obligation;
- bounded recurrence;
- best retrieval rank and score;
- owner/path request and title overlap.

No single non-exact feature may decide the result categorically. Exact anchors remain a hard tier. The audit must
record every component and the total score.

## Verification and limits

1. Replay the 10-owner Series versus 5-owner Base shape and require Series to win.
2. Preserve the title-independent BuilderState cluster and unrelated two-owner rejection fixtures.
3. If the deterministic boundary passes, run pandas 10068 through the actual pipeline and inspect the selected
   dormant file and owner batch before final acceptance.
4. Run TypeScript 35468 as the regression case if the pandas boundary is sound.

Expected token impact is neutral for ranking. A better winner may reduce wasted qualification, but executing the
action still invokes ordinary LLM qualification. Stop after at most three scoring variants; revert if none improves
the saved boundary without breaking the existing cross-repository fixtures.

## Result: rejected and reverted

- Variant 1 let lexical support outweigh the stronger title-independent BuilderState cluster and failed its focused
  regression fixture.
- Variant 2 passed the focused Pandas and BuilderState fixtures, but diagnostic `run-20260902T014213Z` selected
  `core/index.py`; all five disclosed Index owners were rejected as irrelevant comparison-path evidence.
- Variant 3 reduced unresolved-obligation breadth, normalized recurrence, and strengthened bounded retrieval-rank
  evidence. Diagnostic `run-20260902T014620Z` selected `core/series.py`, included `Series::_binop`, and qualification
  retained `_binop` as direct evidence for mechanism, state, and why.
- Actual acceptance was not repeatable. In `run-20260902T014931Z`, `core/series.py` was eligible with 15 owners but
  scored 60; `sparse/series.py` scored 68 because its retrieval and recurrence components outweighed Core Series's
  stronger lexical fit. The action inspected SparseSeries and returned 0 implementation overlap.
  `run-20260902T015256Z` inspected `core/series.py` and returned 1 implementation overlap. One success from two
  unchanged runs does not satisfy acceptance.

The balanced score was therefore reverted. It corrected some candidate populations, but in another live population
it directly preferred the wrong eligible Series variant. Further weight tuning would continue trading retrieval
rank against semantic subject fit without qualified source and is not justified as a production change.

## Follow-up: bounded two-file ambiguity batch

Status: rejected and reverted, 2026-09-02.

Replace neither eligibility nor the restored single-file ranking. When the primary and one runner-up are both
eligible, neither has an exact anchor, and their paths share a meaningful issue-title term, represent them as two
hypotheses inside one `InspectDormantFileAlternatives` action. Disclose at most three owners per hypothesis and six
owners total. When no ambiguity companion qualifies, preserve the existing one-file/five-owner behavior.

The action consumes one existing ordinary slot and all disclosed owners enter one ordinary qualification batch. It
does not add an LLM call, round, retry, or second action. The nested hypothesis contract keeps each file and its
owner IDs together for tracing and novelty suppression.

Acceptance boundary:

1. Focused Core Series/SparseSeries fixture must produce one action containing both files and `_binop`.
2. Unrelated runner-up files must not be added; exact-anchor primaries must remain single-file.
3. Pandas diagnostic must show both live hypotheses and qualify `_binop`.
4. Two pandas final-selection runs must retain the implementation Oracle without displacing the regression test.
5. TypeScript 35468 must retain its established three-file floor; inspect any additional hypothesis for semantic
   coherence and token cost.

Reject or revise if the pair omits `_binop`, routinely adds unrelated files, consumes more than six owner snippets,
or fails repeatable pandas acceptance.

### Result

The deterministic and diagnostic boundaries passed. Focused tests produced one two-file action with three owners
per file, and pandas diagnostic `run-20260902T022450Z` disclosed both `pandas/core/series.py` and
`pandas/sparse/series.py`. Qualification retained `Series::_binop` as direct evidence. The first actual acceptance,
`run-20260902T022741Z`, also retained `_binop` in final evidence and obtained 1 implementation overlap with 87,454
retrieval tokens.

The improvement was not repeatable. In `run-20260902T023451Z`, `pandas/core/groupby.py` won the upstream dormant-file
ranking. Core Series and SparseSeries therefore never became the primary/companion pair, the action did not disclose
`_binop`, and final evidence returned 0 implementation overlap with 53,235 retrieval tokens. TypeScript 35468 safety
run `run-20260902T023735Z` retained Builder and BuilderState but missed WatchMode and its Helpers file trace, returning
2/4 focal files with 130,993 retrieval tokens—below the established three-file floor. All three actual runs remained
`partial/false`. A separate `run-20260902T023324Z` artifact is excluded because retrieval failed explicitly during
CodeGraph initialization under Node 20; the valid reruns used the bundled Node 24 runtime.

The variant was reverted. It resolves ambiguity only after the correct two files occupy the first two ranked
positions, so it does not address instability in the eligible-file population or winner ordering. Increasing one
action's disclosure from five to six owners also lacked a repeatable quality gain and failed the TypeScript safety
boundary. The retained single-file/five-owner contract is restored.

## Follow-up: pre-round-zero admission consistency

Status: initially rejected and reverted; restored after its exact-anchor dependency was corrected, 2026-09-02.

### Observed boundary mismatch

Initial snippet admission deterministically ranks every canonical owner before applying the preferred 60,000-character
comparison boundary. Dormant-file selection later reuses raw retrieval rank, score, and recurrence, but discards the
actual admission outcome: ranking position, admitted/excluded state, distance from the crossing, and per-file admitted
owner count. It then constructs a different lexicographic file rank.

Pandas `run-20260902T023451Z` demonstrates the contradiction. `core/series.py` first appeared at admission position
42 with four admitted owners, while `core/groupby.py` first appeared at 115 with none admitted. Dormant ranking still
selected GroupBy because its six raw unresolved-obligation associations defeated Core Series's three before the
earlier-stage ordering could matter.

### Scoped experiment

Step 1 preserves the deterministic initial-admission result as one structured observation signal. This representation
must keep ranking position, decision, budget crossing, coverage reservation, and priority provenance together. It
does not change initial admission, owner comparison, the character budget, qualification, scheduling, or final
selection.

Step 2 evaluates dormant files using cross-stage consistency rather than another unbounded additive score. Compare
eligible files across a small fixed set of ordinal dimensions: initial admission position/admitted representation,
request-title subject support, independent structural-owner support, and unresolved-obligation breadth. Record both
the winner and its margin. A single dimension must not categorically overwhelm all others. Close or conflicting
candidates remain explicitly ambiguous; the experiment must not pretend that metadata proved one file semantically.

Replay saved candidate populations before changing live behavior:

- Pandas: `002808Z`, `014620Z`, `014931Z`, `015256Z`, `022741Z`, and `023451Z`.
- TypeScript 35468: `183939Z`, `184539Z`, `204825Z`, `205528Z`, and `023735Z`.

The replay must report every candidate's component order and pairwise margin. It should consistently keep Core Series
ahead of Base/GroupBy, mark Core Series versus SparseSeries as close when their signals conflict, and avoid converting
title absence into a BuilderState veto. At most three deterministic ranking variants may be tried.

Expected token impact is zero at the ranking boundary. Live token cost changes only if a different dormant file is
executed. If replay passes, run focused tests, one Pandas diagnostic, two Pandas acceptance runs, and TypeScript 35468
safety acceptance. Revert if the saved populations merely exchange one wrong hard winner for another, if ambiguity
is hidden rather than represented, or if TypeScript falls below its established three-file floor.

### Replay ledger

| Attempt | Boundary | Saved result | Decision |
|---:|---|---|---|
| 1 | Four-dimension ordinal rank voting | Promoted `core/index.py` and test files in several Pandas populations, recreating broad balanced-ranking behavior | Rejected before implementation |
| 2 | Cross-stage admission contradiction only | Changed bad Base and GroupBy winners to Core Series; left two Core Series wins, the SparseSeries ambiguity, and all five TypeScript populations unchanged | Proceed to live diagnostic |

Attempt 2 does not globally rerank files. The existing winner changes only when it had zero initially admitted owners
and a challenger had admitted owners, an earlier admission position, at least as many independent structural owners,
no weaker title/request owner support, and strictly stronger support in at least one of those lexical dimensions.
Among multiple qualifying challengers, title support, request support, structural owners, and then admission position
order the correction. This makes repeated agreement across stages actionable while preserving conflicts as conflicts.

### Live result

The replay result did not survive the live boundary:

- Attempt 2 diagnostic `run-20260902T030853Z` preserved admission metadata, but the dormant-file catalogue could not
  use the four Core Series owners admitted at positions 40–43. Initial owner comparison had placed them in its private
  dormant pool, which is omitted from ordinary controller observations when dormant-island completion is disabled.
  The file had only one visible later owner, was ineligible, and the action inspected five `pandas/tseries/base.py`
  owners; qualification rejected all five.
- Attempt 3 exposed owner-comparison dormants only to dormant-file candidate construction and action materialization,
  without making them roots, islands, deferred actions, or evidence. Diagnostic `run-20260902T031413Z` then revealed
  that pre-round-zero rank itself was contaminated: the ambiguous exact symbol `add` put
  `doc/sphinxext/numpydoc/comment_eater.py` at position 6 with ten admitted owners. Core Series was position 20 with
  four admitted owners and eight eligible dormant owners. The exact-anchor tier selected Comment Eater; all five
  disclosed comment-processing functions were rejected by qualification.

Thus the repeated early signal was real but could not be retained while ambiguous exact-symbol expansion contaminated
it. The implementation was reverted at that boundary.

### Dependent exact-anchor correction and accepted result

The dependency was then implemented as a separate grounding contract. A unique authored structural match retains
`exact_symbol` authority and may create an exact observation. A multi-match identifier is now labelled
`ambiguous_symbol`: it remains available to obligation query expansion, but its matching nodes do not become exact
observations and it is excluded from the exact repository-symbol set used by sparse admission.

Only after that correction were the structured admission signal, private dormant pool, and narrow contradiction rule
restored. Private owner-comparison dormants are supplied exclusively to dormant-file enumeration and materialization;
ordinary controller observations, roots, islands, and other action types remain unchanged.

- Diagnostic `run-20260902T033100Z`: three authored `add` matches were recorded as ambiguous; Comment Eater no longer
  appeared in dormant eligibility; `_binop` reached the preselection pool through the normal controller flow.
- Acceptance `run-20260902T033436Z`: Core Series implementation 1/1 and the Oracle test survived final selection;
  2/3 overall, `partial/false`, 92,277 retrieval tokens.
- Acceptance `run-20260902T033821Z`: the same 1/1 implementation and 2/3 overall result repeated;
  `partial/false`, 112,034 retrieval tokens.
- TypeScript safety `run-20260902T034225Z`: Builder, WatchMode, and Helpers survived; BuilderState did not, leaving the
  established 3/4 floor; `partial/false`, 130,826 retrieval tokens. Replay confirms the dormant correction changes
  none of five saved TypeScript populations.

The dependent experiment is retained. Its semantic claim is deliberately narrow: an ambiguous identifier is a search
lead, not an exact target, and consistent pre-comparison admission may correct one specifically contradicted dormant
winner. It does not make raw retrieval metadata a substitute for source qualification.
