# Pending cross-file handoff scheduling experiment

## Problem and unchanged baseline

TypeScript runs `run-20260829T003915Z` and `run-20260829T004122Z` enumerated an
ordinary WatchMode file-seeded, cross-file `calls` expansion in round 1. The two
ordinary slots went to earlier active islands. In a later round the action was no
longer reconstructible because the file node fell outside the combined 16-node
capability request. The historical `run-20260827T032635Z` selected this action and
created the supportive `tscWatch/helpers.ts` file trace.

The unchanged production baseline:

- enumerates capabilities for at most 16 combined owner/file node IDs;
- executes at most two ordinary actions per round;
- does not retain ordinary actions between rounds;
- has independent rescue, maturation, and verified-lead pools;
- runs at most the existing configured controller rounds;
- performs no LLM decision inside ordinary scheduling.

The prior capability-overflow experiment is reverted. It added graph requests but did
not naturally exercise the WatchMode target, and its live pair was unstable. This
experiment changes only what happens to an action already verified by the unchanged
catalogue.

## Step 1 — bounded pending file-handoff ledger

**Boundary.** Add deterministic run-scoped retention and ordinary scheduling for
file-seeded `ExpandRelationship` actions whose `cross_file_only` flag and
`handoff_reason` are set. Catalogue construction, capability limits, graph execution,
qualification, prompts, all other action pools, final selection, and round limits remain
unchanged.

**Attempt 1.** Retain an enumerated but unselected eligible action for at most two later
rounds. Keep at most two pending actions globally and one per current island. Beginning
in round 2, reserve at most one of the existing ordinary slots for the oldest eligible
pending action. Preserve the highest-ranked non-conflicting ordinary action in the
other slot. Eligibility requires that the source observation still be promoted, map to
an active island, support an unresolved obligation, and have no completed equivalent
effect. Ties are deterministic: discovery round, original catalogue rank, then action
ID.

**Expected quality effect.** A cross-file handoff that loses one round's island
competition can still execute before unrelated owner growth makes it impossible to
re-enumerate. This targets the WatchMode-to-Helpers loss without giving WatchMode or
Helpers testcase-specific priority.

**Expected cost.** Zero additional LLM calls, graph calls, action slots, or rounds.
Executing a retained action can change later qualification/final-selection token use
because it discovers different evidence; that downstream delta must be measured.

**Risks.** A stale action could execute after its source or obligation ceased to be
useful; a retained action could displace a newly higher-value ordinary action; unstable
island identities could invalidate the saved scope; duplicate effects could execute.
The eligibility checks, effect suppression, TTL, and bounds exist specifically to
contain these risks.

**Focused verification.** Deterministic scheduler/ledger tests must prove: round 1 is
unchanged; an unselected action is retained; it receives one existing slot in round 2
even if absent from the new catalogue; the other ordinary slot remains available; the
same effect is not duplicated; covered, rejected, inactive, attempted, and expired
entries are removed; and the two-global/one-per-island limits hold. Run the focused set
twice.

**Combined verification.** First run the actual TypeScript pipeline diagnostically
with response generation and final selection skipped, and audit the enumerated,
retained, scheduled, executed, and file-trace boundaries. Only if the mechanism is
sound, run at least two acceptance executions with response generation skipped and
final selection enabled.

**Acceptance criteria.** The exact WatchMode file action executes in a later round and
creates a Helpers file trace; Builder, BuilderState, and WatchMode remain returned;
there are at least three Oracle implementation files; ordinary actions never exceed
the configured two slots; graph/LLM call caps and controller rounds do not increase;
no duplicate/stale action executes; and retrieval-token changes are explained by
observed downstream work.

**Rollback criteria.** Revert if the intended action is not exercised after bounded
attempts, any stable Oracle file is lost, an ineligible or duplicate action executes,
the ordinary limit is exceeded, or the target trace still is not created after the
retained action executes.

**Attempt 2.** Attempt 1 proved the intended boundary in diagnostic
`run-20260829T042117Z`: the round-1 WatchMode action was retained, used one of two
ordinary round-2 slots, produced three file-level edges, and created the Helpers trace
with 18 direct call sites. Acceptance `run-20260829T042653Z`, however, selected the
WatchMode handoff naturally in round 1 and then retained an unrelated unselected
`sys.ts` file handoff. The forced round-2 `sys.ts` action produced zero edges; final
evidence lost WatchMode and Helpers and returned only the two stable Builder-family
Oracle files. Attempt 2 therefore records starvation debt only when the current round
selected no eligible cross-file file action. Once such an opportunity was used, other
unselected file actions do not acquire later-round priority. This keeps the targeted
fairness guarantee while preventing serial forced traversal of every file island.

**Attempt 3.** Attempt-2 acceptance runs `run-20260829T043211Z` and
`run-20260829T043614Z` both returned only Builder and BuilderState overlap. Neither
activated retained scheduling: the first reconstructed and executed WatchMode normally
in round 2, created Helpers, then lost it at the unchanged
`source_island_not_selected` final gate; the second created no WatchMode trace. Attempt
3 narrows retention itself to actions rooted in observations whose repository-derived
`artifact_role` is `test`. It removes attempt 2's per-round opportunity rule. This
allows a starved test-to-helper trace to survive even if a different file action ran,
while implementation actions such as the observed zero-edge `sys.ts` traversal never
gain starvation priority. No path, symbol, repository, or Oracle value is hardcoded.

## Result ledger

| Step | Attempt | Focused run 1 | Focused run 2 | Cost change | Decision | Remaining issue |
|---|---:|---|---|---|---|---|
| Pending file handoff | 1 | Pass: 103 tests | Pass: identical repeat | Diagnostic 88,240 tokens; no extra slots/calls | Rejected | Acceptance forced zero-edge sys.ts and lost WatchMode |
| Pending file handoff | 2 | Pass: 104 tests | Pass: identical repeat | 87,864 / 101,994 tokens; no retained execution | Rejected | Two/two Oracle overlap; target boundary inactive |
| Pending file handoff | 3 | Pass: 104 tests | Pass: identical repeat | Diagnostic 84,887; acceptance 108,387 tokens | Reverted | Target retention inactive; Helpers rejected by source-island gate |

## Results and decision

All production and experiment-test changes were reverted after the third variant. The
saved design remains in this record; it is not active behavior.

| Run | Kind / attempt | Pending behavior | Helpers boundary | Evidence / Oracle overlap | Coverage / sufficient | Retrieval tokens |
|---|---|---|---|---|---|---:|
| `run-20260829T042117Z` | Diagnostic / 1 | WatchMode retained in round 1 and selected in round 2 | Trace created, 18 calls | Final selection skipped | missing / false (diagnostic) | 88,240 |
| `run-20260829T042653Z` | Acceptance / 1 | WatchMode ran normally; zero-edge sys.ts retained and forced in round 2 | Trace created, not returned | 8 / 2 | partial / false | 79,867 |
| `run-20260829T043211Z` | Acceptance / 2 | No retained action | Trace created; `source_island_not_selected` | 9 / 2 | partial / false | 87,864 |
| `run-20260829T043614Z` | Acceptance / 2 | No retained action | No WatchMode trace | 13 / 2 | partial / false | 101,994 |
| `run-20260829T044106Z` | Diagnostic / 3 | Implementation action excluded; no test action retained | No WatchMode trace | Final selection skipped | missing / false (diagnostic) | 84,887 |
| `run-20260829T044424Z` | Acceptance / 3 | No retained action; WatchMode ran normally | Trace created; `source_island_not_selected` | 13 / 2 | partial / false | 108,387 |

Attempt 1 proved the original scheduling hypothesis at the exact intended boundary:
when WatchMode was enumerated but lost its two-slot competition, preserving the exact
action was sufficient to execute the historical traversal and reconstruct Helpers.
However, retaining every such action also created priority debt for unrelated file
roots. The observed `sys.ts` debt consumed a later slot and returned no edges.

Attempts 2 and 3 prevented that specific broad-retention behavior, but neither
activated retained WatchMode scheduling in an acceptance run. Both runs that created
Helpers under these safer variants did so through normal scheduling, and both lost the
trace at final selection because the WatchMode source island was not accepted. Every
acceptance run returned only two hidden-Oracle overlaps, versus the restored baseline's
repeatable three. No variant achieved two repeatable successful live runs.

Decision: revert. Persistent scheduling is mechanically capable of recovering the
historical action, but it is not sufficient to stabilize the final evidence set and its
general form can promote zero-yield work. The next experiment should replay and isolate
the final `source_island_not_selected` gate for an already-created Helpers trace before
changing scheduling again. It must not treat an arbitrary selected member of the same
island as equivalent to the exact file-trace source without a separately justified
semantic contract.
