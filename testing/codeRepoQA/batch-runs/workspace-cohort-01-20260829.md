# Workspace cohort 01 campaign

## Scope

- Run config: `configs/testing/statistics-workspace-cohort-01.json`
- Cohort size: 20 development cases
- Held-out cases: 0
- Target: 4 valid actual-pipeline runs per case
- Response generation: skipped
- Final evidence selection: enabled
- Corrected campaign lower bound: `run-20260829T184500Z`

The earlier `run-20260829T171936Z` through `run-20260829T175113Z`
attempts are not campaign results. They failed before retrieval because the batch
used Node 20 without `node:sqlite`.

## Valid-run rule

For a cohort case, include a run only when all of the following hold:

1. its run ID is at least `run-20260829T184500Z`;
2. `orchestration-result.json` exists;
3. `retrieval_result.coverage_status` is not `failed`.

The closing audit found exactly 80 matching runs: four for every cohort case and
no case with more than four. All 80 completed with `coverage_status=partial` and
`sufficient=false`. This records completion only; quality statistics have not
yet been interpreted.

## Explicitly excluded corrected-campaign attempts

These post-cutoff run directories are incomplete and must not enter statistics:

- `pandas-dev-pandas-10068/run-20260829T185959Z`
- `pandas-dev-pandas-10068/run-20260829T212009Z`
- `vuejs-vue-10004/run-20260829T210141Z`
- `pandas-dev-pandas-35925/run-20260830T003335Z`

They correspond to invalid LLM structured responses or an API read timeout.

## Audited valid boundaries

| Case | Valid runs | First valid run | Last valid run |
| --- | ---: | --- | --- |
| `vuejs-vue-10803` | 4 | `run-20260829T185019Z` | `run-20260829T210751Z` |
| `microsoft-TypeScript-2953` | 4 | `run-20260829T185244Z` | `run-20260829T211715Z` |
| `pandas-dev-pandas-10068` | 4 | `run-20260829T195601Z` | `run-20260829T212704Z` |
| `vuejs-vue-10519` | 4 | `run-20260829T195841Z` | `run-20260829T213339Z` |
| `vuejs-vue-6301` | 4 | `run-20260829T200132Z` | `run-20260829T214128Z` |
| `microsoft-TypeScript-45713` | 4 | `run-20260829T200407Z` | `run-20260829T215219Z` |
| `pandas-dev-pandas-4542` | 4 | `run-20260829T202126Z` | `run-20260829T220007Z` |
| `microsoft-TypeScript-10020` | 4 | `run-20260829T202351Z` | `run-20260829T220856Z` |
| `pandas-dev-pandas-14942` | 4 | `run-20260829T203552Z` | `run-20260829T221805Z` |
| `pandas-dev-pandas-16764` | 4 | `run-20260829T204041Z` | `run-20260829T222623Z` |
| `microsoft-TypeScript-52695` | 4 | `run-20260829T204456Z` | `run-20260829T223741Z` |
| `vuejs-vue-10004` | 4 | `run-20260829T224034Z` | `run-20260829T225038Z` |
| `vuejs-vue-9042` | 4 | `run-20260829T225442Z` | `run-20260829T230500Z` |
| `pandas-dev-pandas-22698` | 4 | `run-20260829T230808Z` | `run-20260829T231539Z` |
| `microsoft-TypeScript-46770` | 4 | `run-20260829T231718Z` | `run-20260829T233426Z` |
| `vuejs-vue-13052` | 4 | `run-20260829T233748Z` | `run-20260829T234312Z` |
| `vuejs-vue-5884` | 4 | `run-20260829T234450Z` | `run-20260829T235253Z` |
| `microsoft-TypeScript-24625` | 4 | `run-20260829T235503Z` | `run-20260830T000948Z` |
| `microsoft-TypeScript-35468` | 4 | `run-20260830T001311Z` | `run-20260830T002614Z` |
| `pandas-dev-pandas-35925` | 4 | `run-20260830T003010Z` | `run-20260830T003659Z` |
