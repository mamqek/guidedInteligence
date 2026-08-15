# Selected CodeRepoQA Corpus Cases

This table is generated from `selection_manifest.json`. Each case directory contains `issue.json` and `verification.json`.

## bug_regression

| Case ID | Partition | Repository | Issue | Original Issue File | Case Directory | Rationale |
| --- | --- | --- | ---: | --- | --- | --- |
| `vuejs-vue-10803` | `development` | vuejs/vue | #10803: SSR: textarea domProps keeps falsy values | `vue/cloudide/workspace/QA_data/vue/10803.json` | `cases/vuejs-vue-10803` | Vue SSR bug with falsy DOM props; good framework/runtime rendering case. |
| `microsoft-TypeScript-2953` | `development` | microsoft/TypeScript | #2953: `DataView` and other interfaces missing from lib.d.ts | `TypeScript/cloudide/workspace/QA_data/TypeScript/2953.json` | `cases/microsoft-TypeScript-2953` | TypeScript standard library bug; expected retrieval should find lib declaration files. |
| `pandas-dev-pandas-10068` | `development` | pandas-dev/pandas | #10068: BUG/API: Series arithmetic ops inconsistently hold names | `pandas/cloudide/workspace/QA_data/pandas/10068.json` | `cases/pandas-dev-pandas-10068` | pandas Series arithmetic metadata bug; compact fix with production and test files. |
| `vuejs-vue-10519` | `development` | vuejs/vue | #10519: prop validator fails to generate validation error message when using Symbols | `vue/cloudide/workspace/QA_data/vue/10519.json` | `cases/vuejs-vue-10519` | Vue prop-validation bug with a compact runtime fix and unit-test Oracle. |
| `microsoft-TypeScript-10473` | `final` | microsoft/TypeScript | #10473: TSServer: config file diagnostics event not sent if config file changes | `TypeScript/cloudide/workspace/QA_data/TypeScript/10473.json` | `cases/microsoft-TypeScript-10473` | Held-out tsserver configuration-diagnostic event bug with server owners and a harness test. |

## feature_enhancement

| Case ID | Partition | Repository | Issue | Original Issue File | Case Directory | Rationale |
| --- | --- | --- | ---: | --- | --- | --- |
| `vuejs-vue-6301` | `development` | vuejs/vue | #6301: Provide a Typescript declaration file for `vue-server-renderer/client-plugin` | `vue/cloudide/workspace/QA_data/vue/6301.json` | `cases/vuejs-vue-6301` | Vue TypeScript declaration enhancement for server renderer plugin. |
| `microsoft-TypeScript-45713` | `development` | microsoft/TypeScript | #45713: [CLI DX] Improve the 'x errors' message in the CLI | `TypeScript/cloudide/workspace/QA_data/TypeScript/45713.json` | `cases/microsoft-TypeScript-45713` | TypeScript CLI developer-experience enhancement with localized message path. |
| `pandas-dev-pandas-4542` | `development` | pandas-dev/pandas | #4542: ENH: Adding XlsxWriter as an ExcelWriter() option | `pandas/cloudide/workspace/QA_data/pandas/4542.json` | `cases/pandas-dev-pandas-4542` | pandas Excel writer capability enhancement involving IO subsystem. |
| `microsoft-TypeScript-10020` | `development` | microsoft/TypeScript | #10020: Support 'Organize Imports' feature | `TypeScript/cloudide/workspace/QA_data/TypeScript/10020.json` | `cases/microsoft-TypeScript-10020` | TypeScript Organize Imports feature spanning the language service and focused harness coverage. |
| `vuejs-vue-6097` | `final` | vuejs/vue | #6097: Allow defining optional inject dependency with default values | `vue/cloudide/workspace/QA_data/vue/6097.json` | `cases/vuejs-vue-6097` | Held-out Vue inject-default feature with implementation and unit-test coverage. |

## performance_memory

| Case ID | Partition | Repository | Issue | Original Issue File | Case Directory | Rationale |
| --- | --- | --- | ---: | --- | --- | --- |
| `pandas-dev-pandas-14942` | `development` | pandas-dev/pandas | #14942: groupby with category column and two additional columns eats up all main memory | `pandas/cloudide/workspace/QA_data/pandas/14942.json` | `cases/pandas-dev-pandas-14942` | pandas groupby categorical memory blow-up; clear performance/memory objective. |
| `pandas-dev-pandas-16764` | `development` | pandas-dev/pandas | #16764: PERF: pandas' import time | `pandas/cloudide/workspace/QA_data/pandas/16764.json` | `cases/pandas-dev-pandas-16764` | pandas import-time performance issue; broad startup responsibility rather than operation-specific speed. |
| `microsoft-TypeScript-52695` | `development` | microsoft/TypeScript | #52695: Reduce number of fs.stat call for files under node modules | `TypeScript/cloudide/workspace/QA_data/TypeScript/52695.json` | `cases/microsoft-TypeScript-52695` | TypeScript filesystem-stat performance issue under node_modules; good service/compiler IO case. |
| `vuejs-vue-10004` | `development` | vuejs/vue | #10004: Memory leak with component with input with v-model | `vue/cloudide/workspace/QA_data/vue/10004.json` | `cases/vuejs-vue-10004` | Vue v-model listener memory leak with a runtime owner and focused regression test. |
| `vuejs-vue-9842` | `final` | vuejs/vue | #9842: Memory leak when using "transition" and "keep-alive" | `vue/cloudide/workspace/QA_data/vue/9842.json` | `cases/vuejs-vue-9842` | Held-out transition/keep-alive memory case with a focused owner and regression test. |

## compatibility_versioning

| Case ID | Partition | Repository | Issue | Original Issue File | Case Directory | Rationale |
| --- | --- | --- | ---: | --- | --- | --- |
| `vuejs-vue-9042` | `development` | vuejs/vue | #9042: First character or paste is not accepted for watch when assigning placeholder to "" in <textarea> tag with IE11 | `vue/cloudide/workspace/QA_data/vue/9042.json` | `cases/vuejs-vue-9042` | Vue browser compatibility issue with IE11 textarea placeholder/watch behavior. |
| `pandas-dev-pandas-22698` | `development` | pandas-dev/pandas | #22698: Handle FutureWarning from NumPy in Series Construction | `pandas/cloudide/workspace/QA_data/pandas/22698.json` | `cases/pandas-dev-pandas-22698` | pandas compatibility with NumPy FutureWarning in Series construction. |
| `microsoft-TypeScript-46770` | `development` | microsoft/TypeScript | #46770: Cannot import some packages when tsconfig.json specifies "module": "nodenext" | `TypeScript/cloudide/workspace/QA_data/TypeScript/46770.json` | `cases/microsoft-TypeScript-46770` | TypeScript NodeNext module-resolution compatibility case. |
| `vuejs-vue-13052` | `development` | vuejs/vue | #13052: compiler-sfc not compatible with prettier v3 | `vue/cloudide/workspace/QA_data/vue/13052.json` | `cases/vuejs-vue-13052` | Vue compiler-sfc compatibility case with an explicit package-level dependency owner. |
| `microsoft-TypeScript-10041` | `final` | microsoft/TypeScript | #10041: RegExpMatchArray has lost some compatibility with Array since 2.1.0-dev.20160729 | `TypeScript/cloudide/workspace/QA_data/TypeScript/10041.json` | `cases/microsoft-TypeScript-10041` | Held-out TypeScript array-compatibility regression with checker and conformance Oracles. |

## api_behavior_design

| Case ID | Partition | Repository | Issue | Original Issue File | Case Directory | Rationale |
| --- | --- | --- | ---: | --- | --- | --- |
| `vuejs-vue-5884` | `development` | vuejs/vue | #5884: Vue.set Api strange behavior if path is a numerical string | `vue/cloudide/workspace/QA_data/vue/5884.json` | `cases/vuejs-vue-5884` | Vue.set API behavior with numeric string path; expected explanation should distinguish API semantics from bug surface. |
| `microsoft-TypeScript-24625` | `development` | microsoft/TypeScript | #24625: TypeScript 2.9 Watch API change breaking watch support in ts-loader? | `TypeScript/cloudide/workspace/QA_data/TypeScript/24625.json` | `cases/microsoft-TypeScript-24625` | TypeScript watch API behavior change breaking consumers; explicit API responsibility. |
| `pandas-dev-pandas-25183` | `development` | pandas-dev/pandas | #25183: DataFrame.merge with empty frame and Int64 column gives object dtype | `pandas/cloudide/workspace/QA_data/pandas/25183.json` | `cases/pandas-dev-pandas-25183` | pandas merge dtype behavior with nullable integer arrays; API consistency case. |
| `microsoft-TypeScript-16278` | `development` | microsoft/TypeScript | #16278: New refactor API | `TypeScript/cloudide/workspace/QA_data/TypeScript/16278.json` | `cases/microsoft-TypeScript-16278` | TypeScript refactor API case with protocol, service, client/server, and fourslash coverage. |
| `pandas-dev-pandas-10150` | `final` | pandas-dev/pandas | #10150: BUG/API: inconsistent name handling in value_counts  | `pandas/cloudide/workspace/QA_data/pandas/10150.json` | `cases/pandas-dev-pandas-10150` | Held-out pandas value_counts naming-semantics issue with implementation, tests, and release note. |

## testing_build_tooling

| Case ID | Partition | Repository | Issue | Original Issue File | Case Directory | Rationale |
| --- | --- | --- | ---: | --- | --- | --- |
| `pandas-dev-pandas-16499` | `development` | pandas-dev/pandas | #16499: TST: ujson tests are not being run | `pandas/cloudide/workspace/QA_data/pandas/16499.json` | `cases/pandas-dev-pandas-16499` | pandas test discovery gap where ujson tests were not run. |
| `pandas-dev-pandas-32289` | `development` | pandas-dev/pandas | #32289: CI Failing - Linux py37_np_dev - test_constructor_list_frames | `pandas/cloudide/workspace/QA_data/pandas/32289.json` | `cases/pandas-dev-pandas-32289` | pandas CI failure case; retrieval should explain construction/test failure context, not product behavior. |
| `microsoft-TypeScript-35468` | `development` | microsoft/TypeScript | #35468: TS does not recompile correctly when using a combination of project references, wildcard re-exports and watch mode | `TypeScript/cloudide/workspace/QA_data/TypeScript/35468.json` | `cases/microsoft-TypeScript-35468` | TypeScript watch/project-reference recompilation case; build tooling behavior. |
| `vuejs-vue-11718` | `development` | vuejs/vue | #11718: vuejs/vue-ssr-webpack-plugin and webpack 5 | `vue/cloudide/workspace/QA_data/vue/11718.json` | `cases/vuejs-vue-11718` | Vue SSR webpack-plugin compatibility case with focused plugin implementation owners. |
| `vuejs-vue-11782` | `final` | vuejs/vue | #11782: npm test fails on Windows | `vue/cloudide/workspace/QA_data/vue/11782.json` | `cases/vuejs-vue-11782` | Held-out Windows npm-test tooling failure with a focused package-script owner. |

## maintenance_refactor

| Case ID | Partition | Repository | Issue | Original Issue File | Case Directory | Rationale |
| --- | --- | --- | ---: | --- | --- | --- |
| `pandas-dev-pandas-35925` | `development` | pandas-dev/pandas | #35925: CLN remove unnecessary trailing commas to get ready for new version of black | `pandas/cloudide/workspace/QA_data/pandas/35925.json` | `cases/pandas-dev-pandas-35925` | pandas cleanup for Black formatting readiness; pure maintenance/cleanup signal. |
| `pandas-dev-pandas-22872` | `development` | pandas-dev/pandas | #22872: Replace bare excepts by explicit excepts in pandas/tests/ | `pandas/cloudide/workspace/QA_data/pandas/22872.json` | `cases/pandas-dev-pandas-22872` | pandas tests maintenance cleanup replacing bare excepts. |
| `pandas-dev-pandas-36617` | `development` | pandas-dev/pandas | #36617: DOC: Replace single with double backticks in RST files | `pandas/cloudide/workspace/QA_data/pandas/36617.json` | `cases/pandas-dev-pandas-36617` | pandas documentation cleanup case; distinct RST/docstring maintenance. |
| `vuejs-vue-8528` | `development` | vuejs/vue | #8528: Better comments in `shared/util.js` code | `vue/cloudide/workspace/QA_data/vue/8528.json` | `cases/vuejs-vue-8528` | Focused maintenance issue whose owner is a single shared utility source file. |
| `microsoft-TypeScript-19074` | `final` | microsoft/TypeScript | #19074: Clean up LSHost mentions | `TypeScript/cloudide/workspace/QA_data/TypeScript/19074.json` | `cases/microsoft-TypeScript-19074` | Held-out TypeScript language-service-host cleanup with production and test-runner owners. |

## question_usage

| Case ID | Partition | Repository | Issue | Original Issue File | Case Directory | Rationale |
| --- | --- | --- | ---: | --- | --- | --- |
| `microsoft-TypeScript-6307` | `excluded_explanation` | microsoft/TypeScript | #6307: Exported variable <variable name> has or is using private name <private name> | `TypeScript/cloudide/workspace/QA_data/TypeScript/6307.json` | `cases/microsoft-TypeScript-6307` | TypeScript canonical question/docs explanation about private-name export errors. |
| `microsoft-TypeScript-8305` | `excluded_explanation` | microsoft/TypeScript | #8305: Recommendation for exposing multiple TypeScript modules from single NPM package | `TypeScript/cloudide/workspace/QA_data/TypeScript/8305.json` | `cases/microsoft-TypeScript-8305` | TypeScript question/docs case about package module exposure; explanation-based oracle. |
| `pandas-dev-pandas-9219` | `excluded_explanation` | pandas-dev/pandas | #9219: DataFrame.to_hdf fails in Python 3.4 | `pandas/cloudide/workspace/QA_data/pandas/9219.json` | `cases/pandas-dev-pandas-9219` | pandas Usage Question around HDF storage; useful for comparing explanation to maintainer guidance. |
