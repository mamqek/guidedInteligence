# Baseline-seeded island packet experiment plan

Status: implemented as the opt-in `island_packets` representation; accepted for continued experimentation, not the default.

## Question

Can island packets add coherent local flow context and independently useful singleton islands without ever removing a
candidate that the unchanged mechanism-flow selector would have sent to final comparison?

The first `island_packets` implementation did not provide that invariant because it constructed its request
independently. The retained implementation now uses the unchanged normal-flow result as its mandatory seed set.

## Required invariant

Run the unchanged mechanism-flow reducer first. Every candidate it selects is a mandatory seed in the packet request.
Packet construction may reorganize those candidates into island packets and add context, but it may not remove,
replace, or demote any seed. If the seeds consume the complete input budget, the experimental request is identical to
the baseline request and adds nothing.

This requires no additional LLM call: both seed selection and packet completion are deterministic preparation for the
same final-selection request.

## Residual-capacity ordering

After admitting all seeds, form two bounded queues:

1. **Seeded-island completion:** the best structurally connected, role-distinct companion not already selected for
   each island containing a seed.
2. **Qualified singleton representation:** one candidate from every singleton island that independently qualified
   for at least one obligation. An obligation already represented by another island is not an exclusion reason.

Alternate between the two queues, starting with seeded-island completion, and admit at most one item from an island
per pass. This prevents one large seeded island from consuming all residual capacity while also preventing singleton
breadth from eliminating all context around the baseline seeds. If the next item does not fit, record its rejection
and continue to the other queue; never evict a seed.

After both first-pass queues are exhausted, spend any remaining capacity in this order:

1. second and third connected companions for seeded islands;
2. compact packets from unseeded connected islands that independently qualified;
3. optional additional members from any admitted packet.

The fixed budget means it is impossible to guarantee admission of every qualified candidate. The enforceable
guarantees are narrower and testable:

- every normal-flow-selected candidate survives;
- duplicate obligation coverage never suppresses a singleton;
- neither seeded-island depth nor singleton breadth can monopolize residual capacity before the other class receives
  a turn;
- no repository, filename, symbol, or testcase exception is introduced.

## Implementation

The unchanged `mechanism_flows` reducer now runs first when packet mode is selected. Its candidate IDs and flows are
passed to `select_island_evidence_packets` as mandatory seeds. Packet construction alternates one connected companion
for a seeded island with one independently qualified singleton before considering later optional members. The trace
ledger records `mandatory_seed_candidate_ids`, `mandatory_seed_count`, `mandatory_seed_preserved`, packet membership,
per-candidate admission decisions, and the actual character total. No extra LLM call was added.

## Measurement

Replay identical saved candidate pools through both reducers and assert seed-set inclusion.
Focused tests must cover a nearly full baseline budget, multiple seed islands, duplicate-obligation singletons,
oversized companions, and deterministic ordering.

Actual-pipeline comparison:

- TypeScript 35468: two packet runs with final selection enabled and response generation skipped;
- pandas 10068: two runs to measure whether richer flow context remains useful without reducing baseline precision;
- Vue 242: one regression run.

Record final-request candidates and files, seed preservation, singleton admissions, connected companions, rejected
additions, input characters, final-selection tokens, selected evidence, Oracle overlap, `coverage_status`, and
`sufficient`. Do not promote the mode unless seed preservation is exact in every replay and real run.

## Results

- Focused verification: 246 tests pass, including mandatory-seed survival when no companion fits, preservation of
  every baseline seed, duplicate-obligation singleton admission, and deterministic bounded scheduling.
- Pandas `run-20260831T163654Z`: 8/8 mandatory seeds preserved; 30,563 request characters; no qualified omission;
  final evidence contained the implementation Oracle `pandas/core/series.py` and its regression test. The only
  missing Oracle was `doc/source/whatsnew/v0.17.0.txt`. Retrieval used 98,651 tokens and remained `partial/false`.
- TypeScript final-code acceptances `run-20260831T171235Z` and `run-20260831T171810Z`: 8/8 and 13/13 mandatory
  seeds preserved; both selected Builder, BuilderState, WatchMode, and the Helpers file trace. The first sent every
  qualified candidate in 36,835 characters. The second inherited the baseline reducer's single-unit crossing at
  47,967 characters and added nothing beyond it; four packet additions were omitted, but each omitted file was
  already represented by another sent member and no Oracle file disappeared. Retrieval used 113,575 and 135,105
  tokens; both remained `partial/false`.
- Vue `run-20260831T172444Z`: 6/6 seeds preserved; 22,534 characters; no qualified omission; final evidence retained
  both `exp-parser.js` functions and excluded the unrelated `binding.js` file present in prior normal-flow
  `run-20260830T231051Z`. The missing Oracle test file was absent upstream. Retrieval used 66,114 tokens and remained
  `partial/false`.

Decision: the preservation invariant held in every measured run, and packet inputs were coherent. Keep packet mode
available explicitly. Do not make it the default yet: token cost remains high and TypeScript still occasionally
relies on post-selector file-trace/source preservation for navigation evidence.
