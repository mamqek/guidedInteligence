# General post-action continuation harvest

Status: proposed experiment; not implemented.

## Goal

Generalize the useful part of dormant completion: after any productive controller action, detect one newly grounded continuation instead of limiting that check to owner/test maturation.

## Proposed boundary

Run after action outputs are qualified and before islands are rebuilt:

1. Inspect only newly changed, retained source observations.
2. Accept only an exact visible symbol plus verified repository resolution or an existing dormant observation with a verified structural relationship.
3. Ignore targets already returned, observed, pending, or attempted.
4. Keep at most one continuation per island per round and two per run.
5. Materialize and qualify the target normally; a connection never promotes evidence by itself.
6. Reuse the existing verified-lead scheduling/execution contract rather than add an unbounded LLM stage.

## Comparison

- Baseline: current maturation-only dormant completion and general verified leads.
- Variant: the bounded harvest above for every productive action type.
- Start with focused controller tests, then TypeScript 35468, pandas 10068, and Vue 242 actual-pipeline runs.
- Compare selected files, direct/navigation decisions, connected-island membership, coverage, action counts, and retrieval tokens.
- Keep only if it repeatedly adds necessary evidence or grounded continuations without displacing baseline evidence or causing material token growth.

