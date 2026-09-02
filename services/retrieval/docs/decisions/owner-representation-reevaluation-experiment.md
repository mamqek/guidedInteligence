# Owner representation reevaluation experiment

Status: accepted bounded implementation, 2026-09-02.

## Problem

Initial owner admission discloses and qualifies only a bounded subset of retrieved owners. Later controller actions
can disclose better owners, but there is no explicit per-file/per-obligation state that reelects the primary owner
after qualification. Undisclosed same-file alternatives also compete as repository-wide obligation actions rather
than as challengers to the weak representative they could improve.

TypeScript 35468 `run-20260901T225105Z` retained
`builderState.ts::getFilesAffectedByUpdatedShapeWhenNonModuleEmit`, while several held BuilderState owners were
eligible but never qualified. A neighboring 4/4 run executed a BuilderState continuation and supplied the stronger
mechanism. Pandas 10068 additionally shows why raw retrieval tags cannot elect evidence: `run-20260902T002808Z`
preferred five generic `core/base.py` delegation owners over ten `core/series.py` owners because unqualified
retrieval provenance claimed broader obligation coverage.

## Stage boundary and contract

Add one responsibility-owned stage between qualification and island/action construction. It runs after round-zero
qualification and after every controller qualification update.

For each normalized file and obligation it records:

- the primary retained, qualified owner;
- other retained qualified owners, which remain available as complementary evidence;
- bounded undisclosed structural challengers retrieved for that obligation;
- rejected or already attempted owners;
- the reason and source signals used for the election.

The stage never calls an LLM. Qualified obligation contributions come only from the existing qualification
contract. Raw retrieval obligation IDs may nominate an undisclosed challenger but cannot make it superior to
qualified evidence. A challenger must be disclosed and pass ordinary qualification before it can replace or
supplement a primary.

The controller may spend the existing single deferred-file-rescue allowance on one challenger batch. The initial
bounded variant requires an implementation owner whose symbol overlaps the qualified primary's concrete local
follow-up, missing-information terms, or owner identity; test-file challengers remain excluded. No new round,
slot, retry, search query, or final-selection guarantee is added. The challenger executor discloses already-retrieved
owners directly; ranking and lifecycle state remain in the owner-representation module rather than the action.

## Expected impact

- Quality: weak initially qualified owners can be superseded after a stronger same-file owner is qualified;
  complementary owners are retained rather than discarded.
- Tokens: zero tokens for reelection; at most one existing qualification batch per round when a challenger action
  wins the existing rescue slot.
- Risks: raw challengers can still be noisy, repeated groups can consume rescue opportunities, and metadata ranking
  cannot know source semantics before disclosure. Batches are limited, normalized effects are attempted once, and
  every election/challenger decision is traced.

## Verification and decision rule

1. Focused tests: initial primary election, challenger nomination, no raw-owner replacement, qualified challenger
   promotion, complementary retention, rejected-owner exclusion, and stable reelection.
2. Pandas 10068: inspect every representation decision involving `core/series.py`; verify whether `_binop` is
   nominated, qualified, and elected or why it loses.
3. TypeScript 35468: inspect every Builder/BuilderState/WatchMode/Helpers decision; require the established
   three-file floor and verify whether BuilderState challengers improve the weak-owner case.

Retain only if focused invariants pass and actual runs show a grounded boundary improvement without displacing the
established TypeScript floor. Revise or revert after at most three implementation variants.

## Measured result

The first live pandas variant admitted superficially related PANEL/FRAME arithmetic factories because one generic
owner token was enough. That variant was revised: challenger grounding now ignores generic factory terms and
requires an exact anchor or overlap on a distinctive owner/follow-up term. A focused Series reconstruction verifies
that `_arith_method_SERIES::na_op` is admitted beside `_arith_method_SERIES::wrapper`, while the parallel PANEL and
FRAME factories are not.

Pandas diagnostic `run-20260902T005759Z` then reelected
`pandas/core/ops.py::_arith_method_SERIES::wrapper` over the initially qualified `_flex_method_SERIES`; a later
qualified `_arith_method_SERIES::na_op` remained complementary. Coherent SparseSeries challengers also qualified,
showing the remaining cost limitation: a same-file challenger can be structurally and semantically consistent yet
unnecessary to the central regular-Series mechanism. The missing `core/series.py::_binop` was not recoverable by
this stage because that file had no qualified primary; zero-qualified-file recovery remains DFA-1's responsibility.

TypeScript diagnostic `run-20260902T010157Z` retained `builderState.ts::getFilesAffectedBy` as the strongest primary
and qualified three useful complements: the module/non-module updated-shape branches and
`updateSignaturesFromCache`. No raw challenger displaced qualified evidence. Actual acceptance runs
`run-20260902T010629Z` and `run-20260902T011114Z` both recovered Builder, BuilderState, WatchMode, and Helpers (4/4),
selected 14 and 10 evidence items, consumed 127,396 and 121,753 retrieval tokens, and remained `partial/false`.
The focused and neighboring retrieval suite passes 225 tests.
