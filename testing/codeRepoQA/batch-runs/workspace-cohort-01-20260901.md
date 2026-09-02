# Workspace cohort 01 — 2026-09-01 default-behavior rerun

## Scope

- Run configuration: `configs/testing/statistics-workspace-cohort-01-20260901.json`
- Cohort: the same 20 development cases as the 2026-08-29 Workspace cohort
- Target: four sequential actual-pipeline runs per case (80 total)
- Response generation: skipped; final evidence selection: enabled
- Retrieval behavior: current defaults, including baseline-seeded island packets and dormant-file alternatives
- Per-case ceiling: 600 seconds. Runs beginning after the first run listed below belong to this campaign.

## Status

Complete. The closing audit found exactly 80 new runs after
`run-20260901T070451Z`: four runs for every cohort case. All 80 contain the
required orchestration and evaluator artifacts, and none has
`coverage_status=failed`.

This document and the run timestamps form the campaign boundary; no
pre-2026-09-01 run is part of this rerun.
