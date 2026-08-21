# Bounded same-owner contextual refinement

Status: implemented on 2026-08-18; focused verification passed and one real TypeScript run exercised the mechanism. The run did retrieve `builderState.ts`, but the initial observation guardrail dropped its weak, non-owner chunk before qualification; the motivating `builderState.ts::updateShapeSignature` path was therefore not reached and its recovery remains unverified.

## Boundary

This is not a file-level fallback and it is not a new broad semantic search. It applies only after qualification has already found a particular owner useful, but the source shown to the LLM was incomplete.

The action selects one later window inside that same owner, preserves the original owner identity and range, then sends the newly disclosed source through normal qualification. It may therefore upgrade a navigation observation to direct evidence only when the newly visible lines support the claim.

## Eligibility and limits

The action is emitted only when all of these are true:

- qualification promoted the observation as `navigation_only`;
- it named missing information and coverage still has a concrete missing claim;
- the qualification card has a known multi-line owner and its source was incomplete because of preview or input-budget truncation;
- this owner/obligation pair has not already received a continuation.

The later window is deterministic: a bounded section centred around the last third of the owner. It is deliberately one action, not repeated retries. Existing qualification and final-evidence stages remain authoritative; there is no deterministic evidence promotion.

## Expected impact and risks

Expected quality impact: recover behavior in an already located owner when the original card showed only its header/cache guard. The intended TypeScript case is `updateShapeSignature`, where later signature comparison and exported-module propagation were not visible.

Expected token impact: one additional qualification card only when the narrow eligibility conditions hold. It uses no extra retrieval or explanation call.

Risk: a locally relevant but non-causal owner can become a stronger direct-evidence candidate after fuller disclosure. Trace records therefore include the owner range, continuation window, the qualification's stated missing behavior, and the post-continuation decision. Review whether it improves the unresolved obligation rather than merely adding a plausible surrounding mechanism.

## Verification

- Focused test `test_incomplete_navigation_owner_gets_one_later_continuation_view` confirms that an incomplete 180-line owner produces one later-window action, preserves owner identity, and shows that later source instead of its initial lines.
- Focused suites: 128 tests passed.
- TypeScript `run-20260818T165410Z`, with final evidence selection enabled and explanation generation skipped, executed one continuation for `src/server/session.ts::Session::updateErrorCheck`, lines 881-897 of owner 855-906. The new view showed the complete member through the normal class-member disclosure path. Qualification upgraded it from navigation to direct evidence because it visibly showed dirty-project update, file membership gating, and ordered syntactic/semantic diagnostics.
- The run initially retrieved `src/compiler/builderState.ts:L81-L86` at rank 10 for the `explain_why` query. That chunk is a comment/type-alias area about computing the exported-modules map, not `updateShapeSignature`. The 24-observation admission guardrail marked it `outside_observation_guardrail`, so it was not qualified, could not become an island root, and could not receive a same-owner continuation. The run ended `partial/false`, with two implementation-oracle overlaps (`builder.ts`, `watchMode.ts`) and 9 selected evidence items. Do not use it to claim the BuilderState problem is fixed.
