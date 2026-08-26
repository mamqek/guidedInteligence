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

## 2026-08-26 reconnection experiment

### Observed disconnection

The stage remains invoked by `run_retrieval_controller`, but the live qualification-first caller does not pass
`owner_comparison.dormant` through `dormant_completion_observations`. Consequently the controller constructs an empty
`completion_candidate_ids` set and every live evaluation is a no-op. Current Pandas run `run-20260826T055210Z` and
Vue run `run-20260826T055743Z` each evaluated the stage in three rounds without a request or promotion.

Historical connected traces establish the intended boundary:

- TypeScript `run-20260822T184009Z`: 159 dormant candidates, one `buildTests` activation, 1,940 stage tokens;
- TypeScript `run-20260822T184509Z`: 163 dormant candidates, one `updateProgram` activation, 2,043 stage tokens;
- Pandas `run-20260822T184944Z`: 226 dormant candidates, one `names` activation, 1,772 stage tokens.

### Attempt 1 — minimal candidate handoff

- Boundary: pass the existing `owner_comparison.dormant` tuple into the existing controller argument. Do not change
  dormant candidate construction, deterministic eligibility, source disclosure, paired qualification, promotion,
  per-source attempt count, per-island cap, scheduler budgets, or final selection.
- Expected quality impact: restore the previously exercised opportunity to inspect an exact dormant nested owner or
  uniquely resolved same-file callee after a promoted maturation result names it as missing.
- Expected cost: zero additional LLM cost when no deterministic candidate qualifies; one bounded paired
  qualification call for each activation, historically about 1,800–2,100 tokens.
- Candidate-volume impact: dormant owners become controller-visible but remain excluded from ordinary qualification,
  scheduling, deferred inspection, and final candidates unless this stage explicitly promotes one.
- Risks: the old stage selected navigation-only helpers, including Pandas `_create_methods::names`; current grouped
  owner selection produces a different and potentially larger dormant pool; an activation may add noise without
  improving final evidence.

### Verification and decision

1. Add a focused integration assertion that the qualification-first boundary passes exactly the owner-comparison
   dormant tuple and does not mix it into ordinary deferred observations.
2. Run the existing dormant-island focused suite and the affected retrieval/controller tests.
3. Run one actual TypeScript diagnostic smoke with final selection disabled. Audit dormant pool size, matured sources,
   deterministic selections, paired qualification, promoted snippets, and stage tokens.
4. If the stage activates coherently or the trace proves the restored boundary is mechanically reachable, run two
   TypeScript acceptance runs with final selection enabled and explanation skipped, followed by one Pandas regression
   run. If stochastic upstream behavior prevents activation twice, record the experiment as naturally unexercised
   rather than attributing the final result to it.
5. Retain only if activations are semantically useful or the unchanged dormant opportunity measurably improves the
   downstream candidate/final-evidence chain without unstable Oracle loss. Revert if it repeatedly promotes noisy
   navigation, adds unexplained cost, or fails to improve the unchanged baseline.

| Step | Attempt | Focused run 1 | Focused run 2 | Cost change | Decision | Remaining issue |
|---|---:|---|---|---|---|---|
| Dormant candidate handoff | 1 | Pass: 95 focused tests | Pass: 95 focused tests | 0–4,550 stage tokens in acceptance | Best-effort retained | Useful TypeScript activation was not itself selected as final evidence. |

### Attempt 1 diagnostic result

- Invalid infrastructure artifact `run-20260826T064744Z` used Node 20 and failed before retrieval because CodeGraph
  requires `node:sqlite`; it is excluded.
- Valid Node-24 TypeScript diagnostic `run-20260826T064839Z` passed 122 dormant owners into the controller. Round 1
  matured `verifyTransitiveReferences` and selected its contained dormant owner
  `verifyTransitiveReferences::verifyScenario`.
- The paired qualifier promoted the owner as navigation-only because its visible body concretely applies the edit,
  checks incremental diagnostics, and verifies watch/server state, while the scenario-specific wildcard-export edit
  and expected error remained outside the owner. This is mechanism-relevant test infrastructure rather than the
  generic-name noise observed in the historical Pandas activation.
- The stage request used 11,350 input characters and 2,522 tokens (2,146 prompt, 376 completion). The owner entered
  the controller candidate pool; final selection was intentionally disabled in this diagnostic.
- The whole diagnostic used 83,243 retrieval LLM tokens. The stage itself accounted for the exact 2,522-token
  increment; upstream stochastic candidate and round differences prevent treating the remaining total as a causal
  cost comparison.

### Attempt 1 acceptance results

- TypeScript `run-20260826T065559Z`: 163 dormant owners; two natural activations.
  `verifyProjectChanges::buildTests` and `verifyTransitiveReferences::verifyScenario` were both qualified as direct
  evidence. `buildTests` then seeded one ordinary same-file handoff search for the omitted scenario helpers. Neither
  dormant owner was selected directly in final evidence, but both joined their test-mechanism islands. The run ended
  `partial/false` with ten final items, three implementation-Oracle overlaps, and 112,781 retrieval tokens. Dormant
  completion accounted for 4,550 tokens.
- TypeScript `run-20260826T070033Z`: 122 dormant owners; one natural round-3 call relationship selected
  `incrementalBuild`. Qualification retained it as navigation-only because it executes the incremental build and
  timeout queue but does not establish the wildcard-re-export error. It caused no later action and was not final
  evidence. The run ended `partial/false` with eleven final items, three implementation-Oracle overlaps, and 99,337
  retrieval tokens. Dormant completion accounted for 1,362 tokens.
- Pandas `run-20260826T070527Z`: 103 dormant owners were visible, but no target passed all deterministic gates and no
  extra LLM call occurred. Final evidence retained the complete five-item arithmetic-name chain
  `_arith_method_SERIES::wrapper -> _flex_method_SERIES -> Series::_binop -> _maybe_match_name -> __finalize__`,
  including the sole implementation Oracle. The run ended `partial/false` and used 81,421 retrieval tokens.
- Invalid TypeScript acceptance attempt immediately before `065559Z` failed at the unchanged initial-owner response
  validator and is excluded because dormant completion never ran.

### Reconnection decision

Best-effort retain the one-line candidate handoff. The restored stage activated in both valid TypeScript acceptance
runs, chose source-grounded test/build continuations rather than generic unrelated owners, and did not reduce the
three implementation-Oracle endpoint. Pandas did not repeat the historical `_create_methods::names` mistake and
incurred zero stage cost while retaining its complete causal chain.

This is not a claim of final-evidence improvement. One TypeScript run gained a concrete downstream handoff; the other
gained only navigation, and final selection omitted every dormant completion. Keep the strict existing gates and
caps unchanged. Further expansion, broader sibling matching, or deterministic promotion is not justified by these
runs.

### Disabled comparison and runtime flag

`WorkspaceRetrievalConfig.dormant_island_completion_enabled` now controls only the handoff of initial-owner dormant
snippets into the controller's completion stage. It defaults to `false`; the rejected/best-effort experiment must be
enabled explicitly. The CodeRepoQA runner exposes
`--dormant-island-completion` / `--no-dormant-island-completion`, accepts the same setting from a run configuration,
and records the effective value in run metadata and the retrieval trace. Disabling it does not change Qdrant,
CodeGraph resolution, initial owner comparison, ordinary deferred recovery, controller scheduling, or final evidence
selection.

Two actual TypeScript acceptance runs used `--no-dormant-island-completion`, kept final evidence selection enabled,
and skipped only explanation generation:

- `run-20260826T073825Z`: the initial owner comparison produced 164 dormant snippets, but all three controller-round
  evaluations recorded zero eligible completion candidates. The run made no completion LLM call, ended
  `partial/false`, selected 12 evidence items across five files, retained two implementation-Oracle files
  (`builder.ts` and `watchMode.ts`), and used 94,839 retrieval tokens.
- `run-20260826T074349Z`: the initial owner comparison produced 154 dormant snippets, but all three controller-round
  evaluations again recorded zero eligible completion candidates. The run made no completion LLM call, ended
  `partial/false`, selected 12 evidence items across six files, retained two implementation-Oracle files
  (`builder.ts` and `builderState.ts`), and used 102,205 retrieval tokens.

The enabled pair retained three implementation-Oracle files in each run and spent 4,550 / 1,362 tokens in the
completion stage. The disabled pair retained two in each run and spent zero completion-stage tokens. The missing
third file was not consistent: disabled run `073825Z` omitted `builderState.ts`, while `074349Z` omitted
`watchMode.ts`. Controller actions and upstream LLM selections also differed substantially across all four runs, so
the total-token and exact-file differences cannot be attributed solely to the flag. The directly causal effect is
limited to withholding the dormant pool, eliminating its paired qualification calls, and preventing its promoted
owners from influencing later rounds.

Two additional disabled attempts, `run-20260826T073633Z` and `run-20260826T074217Z`, failed the
unchanged initial-owner global-selection validator before the completion boundary and are excluded.

At that experiment boundary the default remained enabled. The ablation did not establish sufficiency improvement:
disabling saved 1,362–4,550 direct stage tokens while both measured runs lost one implementation-Oracle endpoint
relative to the enabled pair. The later correction below supersedes that operational default without changing the
historical comparison result.

### Default corrected after acceptance-run contamination

Later TypeScript acceptance runs `run-20260826T093942Z` and `run-20260826T094609Z` unintentionally omitted the
disable override and therefore inherited the experiment's enabled default. Both metadata files recorded `true`, and
both runs made a dormant-completion LLM call. The comparison flag itself worked, but the ordinary workspace run
surface did not preserve the intended disabled baseline. The runtime, CodeRepoQA, server, and workspace-profile
defaults are now `false`; `--dormant-island-completion` remains the explicit opt-in for this experiment.
