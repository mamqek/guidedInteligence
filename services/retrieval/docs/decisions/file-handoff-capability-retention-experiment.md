# File-handoff capability retention experiment

## Problem and saved baseline

TypeScript runs `run-20260829T003915Z` and `run-20260829T004122Z` both enumerated a
WatchMode file-seeded, cross-file `calls` expansion in round 1, but did not execute it.
In later rounds the same file node was resolved, yet the action catalogue marked its
`calls` edge unavailable. The capability request is built from owner nodes followed by
file nodes and truncated to 16 entries. Once 16 owner nodes were present, the WatchMode
file node was omitted from capability discovery and the unexecuted action could not be
reconstructed.

The unchanged baseline:

- resolves at most 16 bounded-handoff file paths;
- queries capabilities for at most the first 16 combined owner/file node IDs;
- retains two ordinary controller execution slots;
- treats owner- and file-seeded expansions as distinct effects;
- prefers a bounded file handoff over an ordinary owner expansion in later rounds when
  both are available;
- performs no LLM call at the capability-discovery boundary.

## Step 1 — protect omitted bounded-handoff file capabilities

**Boundary.** Change only deterministic action-catalogue capability discovery in
`actions/catalogue_and_execution.py`. Keep qualification, islands, action construction,
scheduler ranking, execution limits, prompts, graph expansion, and final selection
unchanged.

**Attempt 1.** Preserve the current first capability request and its 16-node owner
behavior. If resolved bounded-handoff file nodes were omitted by that slice, issue one
additional capability request containing only those omitted file nodes (still capped at
16), then merge both responses into the same capability map.

**Expected quality effect.** An eligible but unscheduled file handoff remains
enumerable in later crowded rounds instead of disappearing because unrelated owner
nodes filled the capability request.

**Expected cost.** Zero LLM tokens and no candidate-volume change at this boundary.
Crowded rounds with omitted file nodes add one deterministic CodeGraph capability call
and a response for at most 16 file nodes. Uncrowded rounds are unchanged.

**Risks.** Later scheduling may execute a file handoff that previously disappeared,
changing downstream candidate and qualification volume. Additional graph calls may add
small runtime. A broad query must not replace or displace the existing owner-node
capability request.

**Isolated verification.** A focused fixture with more than 16 active owner roots and
one bounded WatchMode handoff must show two capability requests, retain the first 16
owner IDs unchanged, query the omitted file ID separately, and enumerate the
file-seeded cross-file action. Existing file-handoff and scheduler tests must continue
to pass.

**Combined acceptance.** Run the focused qualification/controller test module. If the
local LLM-backed actual pipeline is configured and runtime permits, run the TypeScript
case twice with response generation skipped and final evidence selection enabled.

**Rollback criteria.** Revert if owner capabilities are displaced, uncrowded rounds
gain an extra call, the file action is still unavailable, or focused controller tests
regress.

## Result ledger

| Step | Attempt | Focused run 1 | Focused run 2 | Cost change | Decision | Remaining issue |
|---|---:|---|---|---|---|---|
| Protected file capabilities | 1 | Pass: exact small-round action ID retained after 16-owner growth | Pass: identical deterministic repeat | 0 LLM tokens; +1 graph call in each overflow round | Reverted | Live target unexercised; one experiment run lost BuilderState; both reverted-code counterfactuals restored three Oracles |

## Results

Attempt 1 was mechanically valid at its isolated boundary but was reverted after live
comparison. It is not retained in production.

- The focused fixture first enumerates the WatchMode file action with one owner, then
  repeats after sixteen unrelated owner nodes precede its file node. The original first
  16 owner capability IDs remain unchanged, one overflow request contains only the
  omitted WatchMode file ID, and the same file-action ID is reconstructed. The focused
  check passed twice.
- The qualification/controller regression set passed with the experiment enabled. The
  experiment-only lifecycle test was removed when the behavior was reverted.
- An initial actual-pipeline invocation, `run-20260829T015651Z`, failed explicitly at
  CodeGraph startup because the system Node lacked `node:sqlite`. It is an environmental
  diagnostic, not an acceptance run. Both replacements used bundled Node 24.19.0.
- `run-20260829T015817Z` completed `partial/false`, returned 12 evidence items and three
  Oracle implementation files, used 96,050 retrieval tokens, and issued two overflow
  capability calls. `run-20260829T020528Z` completed `partial/false`, returned 12 items
  and two Oracle implementation files, used 103,858 tokens, and also issued two overflow
  calls.
- Neither experiment run made WatchMode an eligible bounded-handoff root during controller action
  construction. The protected overflow nodes were other files, so neither run created,
  selected, or executed the WatchMode-to-Helpers file action. No action enabled by an
  overflow request was selected or executed in either run.
- At user request, production behavior was restored and two unchanged actual-pipeline
  counterfactuals were run. `run-20260829T034209Z` returned 12 evidence items, three
  Oracle files, `partial/false`, and 103,951 retrieval tokens. `run-20260829T034747Z`
  returned 14 items, three Oracle files, `partial/false`, and 108,293 tokens. Together
  with the earlier `003915Z` / `004122Z` baseline pair, reverted behavior produced the
  three-Oracle result four times, while the experiment produced three and two.
- The exact two-Oracle loss in `020528Z` occurred in the separate verified-lead queue.
  BuilderState was excluded from initial admission, then two valid BuilderState leads
  were discovered in round 1. Explicit qualification-follow-up leads to
  `getSemanticDiagnosticsOfNextAffectedFile` and `createWildcardDirectoryWatcher`
  outranked them and consumed the two-execution cap; both BuilderState leads remained
  pending at controller termination and BuilderState never entered the final pool.
  Importantly, those BuilderState leads and the higher-priority qualification follow-up
  existed before the first overflow capability request, and verified-lead selection is
  an isolated pool. The trace therefore does not show a deterministic overflow-action
  displacement, despite the unfavorable aggregate comparison.

Decision: revert. The change did not naturally exercise its intended WatchMode target,
and an additive retrieval change is not justified against a worse/unstable live pair even
when the observed BuilderState loss arose earlier in another queue. The patch design and
focused proof remain in this record for a future replay-first experiment. Any retry must
first exercise the saved WatchMode-active catalogue input directly and then prove that
the restored action changes scheduling without perturbing unrelated lead competition.
