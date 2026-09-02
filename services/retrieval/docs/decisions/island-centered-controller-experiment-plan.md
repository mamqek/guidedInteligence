# Island-Centered Controller Experiment Plan

Date: 2026-08-30

Status: completed through the safe measured boundary. Read-only projection is retained; ordinary persistence and
owner-maturation folding remain opt-in. Broader pool folding is stopped.

## Motivation And Trace Evidence

The current controller exposes several separately scheduled action families: ordinary actions, deferred-file rescue,
deferred observation inspection, owner maturation, test maturation, maturation children, verified leads, and pending
file handoffs. Their caps are isolated, so the user-visible description of "two actions per round" governs only the
ordinary pool.

Concrete TypeScript 35468 evidence:

- `run-20260830T001311Z` executed five actions in round one: two ordinary actions, one deferred-file rescue, one owner
  maturation, and one verified-lead inspection. It executed 13 actions over three rounds, versus six actions over
  three rounds in August 15 run `run-20260815T183615Z`.
- The round-one `src/compiler/sys.ts` file expansion returned zero edges and observations but exhausted one ordinary
  slot. This motivates the separately implemented bounded empty-action backfill, not this redesign.
- In runs `run-20260829T003915Z` and `run-20260829T004122Z`, the WatchMode file-seeded cross-file action was enumerated
  but lost round-one scheduling to earlier islands. Later owner growth filled the combined 16-node capability request,
  so the file-node action was not reliably reconstructed.
- Diagnostic `run-20260829T042117Z` retained the exact starved action and recovered the historical 18
  WatchMode-to-Helpers call sites. Broad retained scheduling variants were reverted because forced unrelated work
  reduced final Oracle overlap.
- Accepted runs `run-20260829T150112Z` and `run-20260829T150534Z` recovered Builder, BuilderState, WatchMode, and
  Helpers only after a narrow pending file-handoff ledger and exact trace-source preservation were combined. This
  proves that executable-continuation persistence matters, while also showing that global forced scheduling is too
  broad.

## Problem Statement

Tool-request representation, scheduler memory, and semantic progress are currently coupled. A node-cap limit intended
to bound one graph request can erase a previously known action. Meanwhile, conceptually similar operations use
different global pools and caps. The controller can spend several actions around an island without exposing a single
auditable answer to: what explanatory gap was extended, what continuation remains, and why should this island receive
more work?

## Proposed State Contract

Each active semantic island receives one persistent `IslandFrontier`:

```text
IslandFrontier
  island_id
  established_evidence_ids
  established_navigation_ids
  unresolved_gap_ids
  continuations[]
    continuation_id
    gap_id
    source_observation_id
    executor_kind
    normalized_effect
    grounding/provenance
    estimated_cost
    state: available | attempted_empty | produced_gain | blocked | expired
  completed_gap_ids
  terminal_reason
```

The frontier stores semantic intentions and normalized effects, not a serialized list of graph node capabilities.
An executor materializes the bounded tool request only when its continuation is chosen. The existing 16-node boundary
therefore limits a request but cannot delete controller memory.

## Unified Continuation Model

Existing action implementations remain typed executors, but cease to be independent global scheduling pools:

| Current action family | Island continuation meaning |
|---|---|
| relationship expansion | Follow a represented structural connection for one gap |
| within-file search | Resolve missing behavior inside a known file |
| deferred observation inspection | Materialize a previously retrieved but undisclosed owner |
| owner/test maturation | Reveal an omitted section of an already grounded owner |
| verified lead inspection | Follow an exact source-grounded symbol/call lead |
| pending file handoff | Persist an already-grounded cross-file continuation |
| new-island search | Remains a separate frontier-creation operation because it has no source island |

Executor kind must not determine scheduling priority by itself. Priority derives from island value, unresolved gap,
grounding strength, novelty, and estimated marginal cost.

## Round Semantics

1. Recompute active islands and obligation gaps from qualified evidence and coverage.
2. Reconcile each persistent frontier with island merges/splits using observation provenance.
3. Rank islands by unresolved required-obligation value, best grounded continuation, and prior productive gain.
4. Select at most the configured number of islands for successful extension.
5. Within each island, execute its best available continuation.
6. An empty execution is marked attempted and may be backfilled from the same island, then another selected island,
   under a separate bounded empty-attempt allowance.
7. A productive execution consumes one successful-extension slot, is disclosed/qualified, and updates gaps and
   frontier state.
8. Continuations survive later rounds independently of graph request serialization, unless their gap is covered,
   their source becomes invalid, their effect has executed, or an explicit lifetime/cost policy expires them.
9. Stop an island only when its required gaps are covered, no grounded continuation remains, or its explicit bounded
   work allowance is exhausted.

## Limits With Single Meanings

- `max_successful_island_extensions_per_round`: productive semantic extensions, replacing the ambiguous ordinary
  action count.
- `max_empty_attempts_per_round`: bounded backfill attempts that produced no materialized result.
- `max_frontier_continuations_per_island`: controller-memory cap, ranked by grounding and gap value.
- `max_nodes_per_structural_request`: tool payload only; never scheduler memory.
- `max_rounds`: sequential qualify/coverage updates.
- `MAX_EVIDENCE`: final output only; never a reason to erase controller continuations.

## Incremental Experiment Steps

### Step 1 — Read-only frontier projection

Build and trace `IslandFrontier` from the existing catalogue without changing scheduling. Verify that every currently
selected action maps to one island/gap/effect and that the historical WatchMode action remains represented after owner
growth. No LLM, candidate, or action behavior changes.

### Step 2 — Ordinary-pool scheduling from frontiers

Replace only ordinary action selection with island-first continuation selection. Auxiliary pools remain unchanged.
Compare selected effects against saved traces and require the WatchMode action to remain eligible without forcing it.

### Step 3 — Fold one auxiliary family at a time

Fold deferred inspection, then maturation, then verified leads, then pending handoffs into the continuation contract.
Each fold is a separate attempt and must demonstrate equivalent or better grounded gain before the next family moves.
Do not combine all families in one patch.

### Step 4 — Decouple structural request capacity

Materialize graph-node requests from the selected continuation. Prove that truncating a request leaves unmaterialized
continuations in frontier memory and that they remain eligible in the next round.

### Step 5 — Integrated acceptance

Run two actual TypeScript 35468 comparisons with final selection enabled and explanation skipped, followed by one Vue
and one Pandas regression case. Compare Oracle files, semantic flow, successful/empty actions, tool calls, stage tokens,
pending work at termination, coverage, and sufficiency.

## Expected Effects

- Quality: fewer lost grounded continuations; more coherent within-island mechanism completion; no forced unrelated
  work merely because it was retained.
- Tokens: Step 1 adds none. Later steps should reduce redundant disclosure/qualification; productive backfills may
  increase payloads. Any increase must be measured by stage.
- Runtime: fewer duplicated source/graph inspections are expected, but persistent reconciliation adds deterministic
  bookkeeping.
- Candidate volume: not inherently larger; the intended change is persistence and scheduling coherence.

## Regression Risks

- A large island could monopolize work and reduce discovery diversity.
- Incorrect island merges could preserve irrelevant continuations.
- Stable frontier identity across island merges/splits may be difficult.
- Treating every empty execution as free could create tool-call scans; the empty-attempt limit is mandatory.
- Folding auxiliary families too quickly could remove useful isolated protections.
- Frontier persistence could retain stale actions after coverage changes unless reconciliation is strict.

## Acceptance And Rollback

Accept a step only if two repeatable focused checks preserve grounded continuations and do not increase duplicate
effects. Actual-pipeline acceptance requires no loss of the stable TypeScript core files, no worse cross-repository
Oracle overlap in both regression cases, and a justified token/tool-call delta. Revert any step that merely moves
starvation to a new queue, forces unrelated actions, or increases tokens without improving semantic flow or retained
evidence.

## Result Ledger

| Step | Attempt | Focused run 1 | Focused run 2 | Cost change | Decision | Remaining issue |
|---|---:|---|---|---|---|---|
| Read-only frontier projection | 1 | 99 focused tests pass | 99 focused tests pass | No LLM/tool calls; trace-only bookkeeping | Accepted | Diagnostic `run-20260830T121409Z` mapped all 13 selected actions and retained 7 available continuations absent from the terminal catalogue; WatchMode file expansion remained identified through island migration |
| Ordinary frontier scheduling | 1 | 100 focused tests pass | 100 focused tests pass | Diagnostic `run-20260830T122246Z`: 82,510 preselection retrieval tokens | Rejected | Projection effect-deduplication changed a current round-2 choice even though no persisted action was selected; violated additive-only boundary |
| Ordinary frontier scheduling | 2 | 101 focused tests pass | 101 focused tests pass | Diagnostic `122756Z` 76,449 preselection tokens; acceptance `123149Z` / `123601Z` 104,871 / 110,580 tokens | Best-effort retained, opt-in | Both acceptances retained all four target files. First had no activation; second selected one same-island persisted `watch.ts` file expansion, which returned empty and backfilled. Persistence is proven, quality gain is not |
| Fold deferred-file rescue | 1 | 102 focused tests pass | 102 focused tests pass | Diagnostic `run-20260830T124320Z`: 88,148 preselection tokens and 3–4 total actions/round | Reverted | Zero rescues selected across all three rounds because active islands occupied shared capacity; moved starvation rather than unifying value |
| Fold owner maturation | 1 | 102 focused tests pass | 102 focused tests pass | Diagnostic `125058Z` 78,277 preselection tokens; TypeScript `125440Z` / `125843Z` 102,460 / 103,130 total tokens | Best-effort retained, opt-in | Both TypeScript runs retained all four target files and activated folding 2/3 times. Vue retained its implementation Oracle. Pandas was blocked upstream before controller twice |
| Fold test maturation / verified leads / pending handoffs | 1–3 | Not run | Not run | Not measured | Stopped | Do not fold more families after deferred-rescue starvation and incomplete Pandas regression evidence |
| Structural-capacity decoupling | 1 | Deterministic persistence fixture passes | Deterministic persistence fixture passes | No extra LLM; one later structural tool call only if selected | Best-effort retained for ordinary continuations | `123601Z` executed an ordinary file action absent from the current catalogue, proving request truncation no longer erases it; that activation returned empty, so quality benefit is unproven |
| Integrated acceptance | 1 | TypeScript `125440Z`: four targets | TypeScript `125843Z`: four targets | 102,460 / 103,130 tokens; Vue `130338Z` 46,733 | Incomplete / opt-in only | Vue retained `src/exp-parser.js`; Pandas `130550Z` / `130714Z` failed the identical round-zero qualification contract before controller execution |

## Execution Conclusion

The experiment supports persistent controller memory, but not wholesale queue unification. As of 2026-08-31, the
retained `IslandFrontierLedger` and owner-maturation folding are the default and only controller policy. The ledger
stores normalized executable effects independently of the 16-node structural request, reconciles their island
identity across rounds, and records `available`, `attempted_empty`, `produced_gain`, and `expired` state. The two
experiment CLI/config flags were removed rather than preserved as permanent compatibility branches.

Ordinary persistence attempt 1 was rejected because effect-level projection accidentally replaced the current
catalogue's exact action objects. Attempt 2 is additive: it supplies the untouched current ordinary actions plus only
available actions missing from the catalogue. `123601Z` demonstrated a retained same-island `watch.ts` file action
executing in round 3 after disappearing from catalogue representation. It returned empty and used the bounded
empty-action backfill, so this proves persistence and safe execution—not improved evidence.

Deferred-file rescue cannot yet share the active-island allowance. In `124320Z`, every rescue vanished because two
active promoted islands always outranked the unresolved rescue frontier. That implementation and switch were removed.
Owner maturation is different: the existing scheduler has already grounded it inside an active island. Folding only
that one preselected maturation action produced new source in diagnostic `125058Z`, and both TypeScript acceptances
retained all four target files. The later nested qualification contract removed the Pandas round-zero failure, after
which the behavior was retained as the default without enlarging ordinary capacity.

No test-maturation, verified-lead, or pending-handoff fold was attempted. Their independent safeguards remain intact.
The experiment therefore rejects the idea that executor families can simply be merged into one queue; comparable
semantic frontier value must exist first.
