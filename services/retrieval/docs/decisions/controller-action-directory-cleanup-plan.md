# Controller action directory cleanup plan

Status: deferred; documentation only. Do not implement as part of the dormant-island-completion experiment.

## Goal

Make the controller's action lifecycle easier to understand without changing retrieval behavior, action budgets, scheduling order, action identities, trace events, or qualification semantics.

The current `execution_flow/actions/` package already separates action models, policy, scheduling, and pending file handoffs, but `catalogue_and_execution.py` still combines two distinct responsibilities: constructing executable actions and executing them. Dormant island completion is separately implemented in `execution_flow/dormant_island_completion.py`, but it is a post-action completion stage rather than a scheduled `RetrievalAction`.

## Proposed behavior-neutral structure

```text
execution_flow/
  actions/
    models.py
    policy.py
    catalogue.py
    scheduler.py
    execution.py
    pending_file_handoffs.py
  completion/
    dormant_island.py
```

- `models.py`: the closed action/result contracts.
- `policy.py`: action purpose and scheduler-pool mapping.
- `catalogue.py`: action enumeration only.
- `scheduler.py`: queue partitioning, capacity, backfill, and selection only.
- `execution.py`: dispatch from an already-selected action to tools and materialized observations/edges.
- `pending_file_handoffs.py`: persistence and revalidation of file-level cross-file continuations.
- `completion/dormant_island.py`: the bounded post-action rule that can promote a private dormant owner after a newly matured retained source exposes a grounded relationship to it.

Files should be split at semantic responsibility boundaries, not into one file for every action class. Several action purposes intentionally share the same execution mechanism—for example, ordinary within-file handoff expansion, owner maturation, test maturation, and deferred-file rescue all use `ExpandWithinFileHandoff` with different purposes and scheduler pools.

## Required semantic boundary

Dormant island completion must remain distinct from ordinary action execution during this cleanup:

1. A normal action directly materializes an observation.
2. The controller merges it by canonical observation ID, discloses it, and qualifies it.
3. A retained direct or navigation decision becomes a candidate and participates in the next island rebuild.

Dormant island completion instead starts after action-result qualification. It considers private owner-comparison observations that the ordinary action did not return, and only after an owner/test maturation action produced an eligible retained source. It then checks the bounded structural/semantic relationship and performs paired qualification before promotion.

Converting dormant completion into a scheduled `RetrievalAction` would not be a directory cleanup. It would change scheduler capacity, competition, retries, and trace semantics, and therefore requires a separately measured retrieval experiment.

## Invariants for a later cleanup

- No new flags and no default changes.
- Identical action IDs, purposes, pools, ordering, and per-round limits.
- Identical empty-action backfill behavior.
- Identical observation merge and qualification ordering.
- Identical dormant completion eligibility and paired qualification.
- Preserve existing public imports temporarily only where needed to make the move atomic; remove obsolete internal paths in the same change.
- Verify focused action catalogue/execution tests, controller tests, dormant-completion tests, then compare at least two actual-pipeline acceptance runs under the unchanged profile.

## Evidence motivating the separation

- TypeScript `run-20260827T032635Z` showed that a file-level WatchMode-to-Helpers continuation can be decisive and therefore must remain scheduler-visible independently of request serialization limits.
- The later island-frontier work showed that scheduling and action execution are independently meaningful policies; combining them obscures whether an action was absent, unscheduled, attempted, empty, or productive.
- Pandas `run-20260830T234551Z` and Vue `run-20260830T234551Z` evaluated dormant completion every round but selected no dormant target. This confirms that the stage is optional post-action promotion logic, not an ordinary graph/search action merely hidden behind a different name.
