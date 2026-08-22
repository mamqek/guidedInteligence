# Dormant Island Completion Experiment

## Stage boundary

This experiment runs immediately after a normal owner/test maturation result is disclosed and qualified, and before
coverage and semantic islands are rebuilt for that round. It does not add a scheduler action or a Qdrant search.

The stage may reconsider one named owner that:

- was already structurally resolved for initial owner comparison;
- was not promoted into ordinary qualification or scheduling;
- is in the same file as the newly matured promoted source;
- is named by a still-missing step, even when the matured source directly proves a different step;
- shares an unresolved obligation with that source;
- is an exact nested owner or exact source-level callee of the source;
- is explicitly named by the source qualification's missing information or local follow-up;
- has not already been attempted.

The candidate is disclosed from its stable source handle and receives a separate paired qualification decision with
the matured source as context. It becomes an island/evidence member only when that decision promotes it. A rejected
or deferred candidate is recorded but does not enter the controller observation/decision state.

## Bounds

- At most one dormant candidate is attempted for each maturation result.
- At most two dormant candidates may be promoted into one island during a run.
- Rejected candidates are never retried.
- Same-file membership, repeated words, broad recurrence, and raw retrieval rank are insufficient by themselves.

## Expected impact

- Quality: complete bounded mechanisms whose setup and assertion/helper owners were separated by the global
  one-file admission guardrail.
- Tokens: one small paired qualification call only when all deterministic gates pass. No embedding or Qdrant tokens.
- Runtime: local disclosure plus optional language-routed source-call verification.

## Known risks

- A qualification follow-up can name a real but irrelevant helper; therefore deterministic matching never promotes
  the helper directly.
- Large nested owners can still pressure the paired qualification payload; the stage uses existing disclosure limits
  and fails explicitly if the payload cannot fit.
- Island IDs can change after merging. The cap is therefore derived from successful source observations mapped into
  the current island, not stored against an old positional island ID.

## Measurement

- Focused selection and cap tests.
- One TypeScript diagnostic smoke to inspect the round where activation occurs.
- Two TypeScript final-selection runs with explanation generation disabled.
- One pandas final-selection regression run with explanation generation disabled.
- Record activation attempts, gates, paired-qualification usage, promoted targets, final selected evidence, coverage,
  sufficiency, and total retrieval tokens in the retrieval changelog.

## Result: rejected and disconnected

The strict exact-name version did not activate in measured runs even when the desired nested owner was resolved. A
bounded descriptive-name relaxation did activate, but selected different navigation-only continuations rather than
reliably assembling the missing mechanism:

- `run-20260822T184009Z` selected `verifyProjectChanges::buildTests` (1,940 LLM tokens for this stage).
- `run-20260822T184509Z` selected `createWatchProgram::updateProgram` (2,043 tokens).
- pandas `run-20260822T184944Z` selected `_create_methods::names` (1,772 tokens), which the paired qualifier itself
  described as name formatting rather than the required Series name-propagation mechanism.

The two TypeScript runs had 4 and 3 implementation-Oracle overlaps respectively; pandas retained `Series::_binop`
and was `strong/true`. Those overall results do not make the completion choice itself correct. Because the stage
promoted navigation-only fragments and did not consistently reconstruct the intended parent/helper story, it is not
accepted as a live retrieval behavior. Its pipeline call is disconnected; the isolated module and focused tests remain
as the measured experiment record.

The missing design element is a bounded joint comparison of all exact structural siblings against the incomplete
source, followed by admission only when the combined pair directly completes a missing claim. Choosing one sibling
from qualification wording before that comparison is not reliable enough.
