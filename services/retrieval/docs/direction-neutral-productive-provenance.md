# Direction-Neutral Productive Provenance

## Stage boundary

At connected-shortlist ranking, productive one-hop CodeGraph relationships
(`calls`, `references`, `imports`, and the other accepted productive kinds)
receive the same structural provenance tier whether the discovered node is an
upstream caller or a downstream visible target. Edge direction and relationship
kind remain in candidate metadata for responsibility assessment.

The change does not add graph nodes, increase traversal depth, bypass final LLM
selection, or accept evidence automatically.

## Expected quality impact

State owners and orchestrators discovered as callers of a semantic seed no
longer lose solely because their symbol is not visible inside the seed snippet.
This should remove the observed direction-dependent eligibility flip for
TypeScript builder functions.

## Expected token impact

None directly. Candidate count, shortlist limits, graph depth, and LLM calls are
unchanged. Different components or candidates may win ranking.

## Regression risks

High-fan-in utilities can have many upstream callers. Direction neutrality can
therefore strengthen unrelated callers when semantic seeding is poor. The
existing bounded traversal and productive-edge requirement remain in force;
direction is still exposed to the final selector and is no longer used as a
universal responsibility prior.

## Comparison and retention

Run focused tests proving productive caller and callee candidates have equal
provenance strength. Inspect real TypeScript shortlist traces for builder-owner
survival and unrelated caller growth. This change is independent of the
protected-file-pool experiment and remains enabled if that separate experiment
is reverted, as explicitly requested by the user.

## Result

Focused tests confirm that productive upstream `graph_neighbor` candidates and
downstream `graph_direct_target` candidates now receive equal provenance
strength. In the combined real comparison, the final request contained zero/two
`graph_neighbor` candidates and two/zero `graph_direct_target` candidates, so no
unbounded caller inflation was observed. The protected pool consumed most slots,
which means these runs do not isolate direction quality; the direction change is
retained independently by explicit user instruction.
