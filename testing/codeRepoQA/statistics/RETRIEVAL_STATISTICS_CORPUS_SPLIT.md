# Retrieval Statistics Corpus Expansion And Split

## Status

This document records the selected expansion candidates and their intended partition. It does **not** add incomplete cases to `selection_manifest.json`. No repositories were cloned and no retrieval runs were made during screening.

The current 21 retrieval-grounded cases provide three cases in each of seven categories. Add the 14 candidates below—two per category—to reach 35 cases. The resulting split is exactly 28 development / 7 final, with four development and one final case in every category.

## Resulting Balance

| Dimension | Vue | TypeScript | pandas | Total |
| --- | ---: | ---: | ---: | ---: |
| Existing retrieval-grounded | 3 | 7 | 11 | 21 |
| New development | 5 | 2 | 0 | 7 |
| New final | 3 | 3 | 1 | 7 |
| Resulting corpus | 11 | 12 | 12 | 35 |

The repository mix is therefore as even as possible while preserving the 21 existing cases and adding only 14.

| Category | Existing | New development | New final | Result |
| --- | ---: | ---: | ---: | ---: |
| Bug/regression | 3 | 1 | 1 | 5 |
| Feature/enhancement | 3 | 1 | 1 | 5 |
| Performance/memory | 3 | 1 | 1 | 5 |
| Compatibility/versioning | 3 | 1 | 1 | 5 |
| API behavior/design | 3 | 1 | 1 | 5 |
| Testing/build/tooling | 3 | 1 | 1 | 5 |
| Maintenance/refactor | 3 | 1 | 1 | 5 |

## Secondary retrieval topology

The seven categories above describe issue intent, not repository evidence shape. Statistics must additionally use
the reporting-only `retrieval_topology` axis defined by the
[statistics protocol](RETRIEVAL_STATISTICS_PROTOCOL.md#secondary-retrieval-topology-axis):

- `localized_declarative`
- `localized_implementation`
- `connected_mechanism`
- `broad_cross_cutting`

This axis is not balanced and must not affect case selection, retrieval, ranking, or Oracle membership. Its purpose
is to make results interpretable: a system based heavily on callable relationships should not be expected to fail
or succeed for the same reasons on a manifest-only correction, a focused runtime owner, a multi-file mechanism, and
a repository-wide cleanup.

Examples already audited in the development partition are:

| Case | Issue category | Retrieval topology | Reason |
| --- | --- | --- | --- |
| `microsoft-TypeScript-2953` | `bug_regression` | `localized_declarative` | The implementation Oracle is an authored standard-library declaration file with no useful callable graph owner. |
| `vuejs-vue-6301` | `feature_enhancement` | `localized_declarative` | The relevant resolution includes declarations and package metadata, so literal/artifact retrieval matters more than call flow. |
| `vuejs-vue-10803` | `bug_regression` | `localized_implementation` | `renderDOMProps` is one focused runtime implementation owner; CodeGraph resolves it normally. |
| `microsoft-TypeScript-46770` | `compatibility_versioning` | `connected_mechanism` | The issue requires following NodeNext configuration through package resolution and format interpretation. |
| `pandas-dev-pandas-16764` | `performance_memory` | `broad_cross_cutting` | The import-time resolution changes a broad startup/import surface rather than one operation owner. |

Freeze the remaining assignments from existing case metadata before the next declared statistics campaign. Do not
inspect held-out retrieval output or use final-partition results to revise an assignment.

## New Development Candidates

These cases may be materialized, run, inspected, and used for tuning.

| Category | Case | Issue | Resolution snapshot evidence found locally |
| --- | --- | --- | --- |
| `bug_regression` | `vuejs-vue-10519` | prop validator fails to generate validation error message when using Symbols | Fix PR #10529; commit `abb5ef35`, parent `b97606`; implementation and unit-test changes |
| `feature_enhancement` | `microsoft-TypeScript-10020` | Support 'Organize Imports' feature | Fix PR #22087; merge `b31aa4`, first parent `4d284d`; service implementation, harness, and baselines |
| `performance_memory` | `vuejs-vue-10004` | Memory leak with component with input with v-model | Fix PR #10085; commit `3d29ba`, parent `509de2`; runtime event handling and regression test |
| `compatibility_versioning` | `vuejs-vue-13052` | compiler-sfc not compatible with prettier v3 | Fix PR #13053; commit `45d6ad`, parent `0ad8e8`; package compatibility and lockfile changes |
| `api_behavior_design` | `microsoft-TypeScript-16278` | New refactor API | Fix PR #16307; merge `6007eb`, first parent `b217c3`; protocol, client/server, service, and test changes |
| `testing_build_tooling` | `vuejs-vue-11718` | vuejs/vue-ssr-webpack-plugin and webpack 5 | Fix PR #12002; commit `80e773`, parent `38f71d`; webpack plugin implementation changes |
| `maintenance_refactor` | `vuejs-vue-8528` | Better comments in `shared/util.js` code | Fix PR #8529; commit `af819a`, parent `5e9129`; focused shared utility maintenance |

## Reserved Final Candidates

These seven cases form the entire 20% final partition. They were newly selected, so none of the 21 previously exercised cases enters final evaluation.

Eligibility and snapshot feasibility have been screened. From this point, do not run retrieval, tune against, or manually inspect system output for these cases before the declared final evaluation.

| Category | Case | Issue | Resolution snapshot evidence found locally |
| --- | --- | --- | --- |
| `bug_regression` | `microsoft-TypeScript-10473` | TSServer: config file diagnostics event not sent if config file changes | Primary fix PR #11285; commit `635313`, parent `81fc75`; server/project-system implementation changes |
| `feature_enhancement` | `vuejs-vue-6097` | Allow defining optional inject dependency with default values | Fix PR #6322; commit `88423f`, parent `b3cd9b`; injection/options implementation and test |
| `performance_memory` | `vuejs-vue-9842` | Memory leak when using transition and keep-alive | Fix PR #12015; commit `e7baaa`, parent `2b93e8`; keep-alive implementation and regression test |
| `compatibility_versioning` | `microsoft-TypeScript-10041` | RegExpMatchArray lost Array compatibility | Fix PR #10069; merge `1435fb`, first parent `36b611`; checker and conformance tests |
| `api_behavior_design` | `pandas-dev-pandas-10150` | BUG/API: inconsistent name handling in `value_counts` | Fix PR #10419; merge `654e739`, first parent `3908ad5`; algorithms/base implementation, tests, and release note |
| `testing_build_tooling` | `vuejs-vue-11782` | npm test fails on Windows | Fix PR #11784; commit `14882c`, parent `b800e8`; focused package-script fix |
| `maintenance_refactor` | `microsoft-TypeScript-19074` | Clean up LSHost mentions | Fix PR #32018; commit `37b20f`, parent `a97c18`; compiler/server/test-runner cleanup |

## Screening Performed

For all 14 candidates:

- the local archive contains a closed issue JSON with usable issue text;
- labels and issue content support the assigned retrieval category;
- the existing local origin repository contains the identified fix and pre-fix parent;
- the resolution exposes file changes from which implementation and supporting Oracles can be prepared;
- a pre-fix snapshot can be derived from the recorded parent without cloning a repository.

This is feasibility screening, not full testcase construction. Before promotion into the runnable manifest, each case still needs a materialized issue file, verification file, frozen Oracle classification, snapshot reference, and leakage check under [RETRIEVAL_STATISTICS_PROTOCOL.md](RETRIEVAL_STATISTICS_PROTOCOL.md).
