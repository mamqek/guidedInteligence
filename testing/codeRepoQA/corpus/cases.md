# Selected CodeRepoQA Corpus Cases

This table is generated from `selection_manifest.json`. Each case directory contains `issue.json` and `verification.json`.

## bug_regression

| Case ID | Repository | Issue | Original Issue File | Case Directory | Rationale |
| --- | --- | ---: | --- | --- | --- |
| `vuejs-vue-10803` | vuejs/vue | #10803: SSR: textarea domProps keeps falsy values | `vue/cloudide/workspace/QA_data/vue/10803.json` | `cases/vuejs-vue-10803` | Vue SSR bug with falsy DOM props; good framework/runtime rendering case. |
| `microsoft-TypeScript-2953` | microsoft/TypeScript | #2953: `DataView` and other interfaces missing from lib.d.ts | `TypeScript/cloudide/workspace/QA_data/TypeScript/2953.json` | `cases/microsoft-TypeScript-2953` | TypeScript standard library bug; expected retrieval should find lib declaration files. |
| `pandas-dev-pandas-10068` | pandas-dev/pandas | #10068: BUG/API: Series arithmetic ops inconsistently hold names | `pandas/cloudide/workspace/QA_data/pandas/10068.json` | `cases/pandas-dev-pandas-10068` | pandas Series arithmetic metadata bug; compact fix with production and test files. |

## feature_enhancement

| Case ID | Repository | Issue | Original Issue File | Case Directory | Rationale |
| --- | --- | ---: | --- | --- | --- |
| `vuejs-vue-6301` | vuejs/vue | #6301: Provide a Typescript declaration file for `vue-server-renderer/client-plugin` | `vue/cloudide/workspace/QA_data/vue/6301.json` | `cases/vuejs-vue-6301` | Vue TypeScript declaration enhancement for server renderer plugin. |
| `microsoft-TypeScript-45713` | microsoft/TypeScript | #45713: [CLI DX] Improve the 'x errors' message in the CLI | `TypeScript/cloudide/workspace/QA_data/TypeScript/45713.json` | `cases/microsoft-TypeScript-45713` | TypeScript CLI developer-experience enhancement with localized message path. |
| `pandas-dev-pandas-4542` | pandas-dev/pandas | #4542: ENH: Adding XlsxWriter as an ExcelWriter() option | `pandas/cloudide/workspace/QA_data/pandas/4542.json` | `cases/pandas-dev-pandas-4542` | pandas Excel writer capability enhancement involving IO subsystem. |

## performance_memory

| Case ID | Repository | Issue | Original Issue File | Case Directory | Rationale |
| --- | --- | ---: | --- | --- | --- |
| `pandas-dev-pandas-14942` | pandas-dev/pandas | #14942: groupby with category column and two additional columns eats up all main memory | `pandas/cloudide/workspace/QA_data/pandas/14942.json` | `cases/pandas-dev-pandas-14942` | pandas groupby categorical memory blow-up; clear performance/memory objective. |
| `pandas-dev-pandas-16764` | pandas-dev/pandas | #16764: PERF: pandas' import time | `pandas/cloudide/workspace/QA_data/pandas/16764.json` | `cases/pandas-dev-pandas-16764` | pandas import-time performance issue; broad startup responsibility rather than operation-specific speed. |
| `microsoft-TypeScript-52695` | microsoft/TypeScript | #52695: Reduce number of fs.stat call for files under node modules | `TypeScript/cloudide/workspace/QA_data/TypeScript/52695.json` | `cases/microsoft-TypeScript-52695` | TypeScript filesystem-stat performance issue under node_modules; good service/compiler IO case. |

## compatibility_versioning

| Case ID | Repository | Issue | Original Issue File | Case Directory | Rationale |
| --- | --- | ---: | --- | --- | --- |
| `vuejs-vue-9042` | vuejs/vue | #9042: First character or paste is not accepted for watch when assigning placeholder to "" in <textarea> tag with IE11 | `vue/cloudide/workspace/QA_data/vue/9042.json` | `cases/vuejs-vue-9042` | Vue browser compatibility issue with IE11 textarea placeholder/watch behavior. |
| `pandas-dev-pandas-22698` | pandas-dev/pandas | #22698: Handle FutureWarning from NumPy in Series Construction | `pandas/cloudide/workspace/QA_data/pandas/22698.json` | `cases/pandas-dev-pandas-22698` | pandas compatibility with NumPy FutureWarning in Series construction. |
| `microsoft-TypeScript-46770` | microsoft/TypeScript | #46770: Cannot import some packages when tsconfig.json specifies "module": "nodenext" | `TypeScript/cloudide/workspace/QA_data/TypeScript/46770.json` | `cases/microsoft-TypeScript-46770` | TypeScript NodeNext module-resolution compatibility case. |

## api_behavior_design

| Case ID | Repository | Issue | Original Issue File | Case Directory | Rationale |
| --- | --- | ---: | --- | --- | --- |
| `vuejs-vue-5884` | vuejs/vue | #5884: Vue.set Api strange behavior if path is a numerical string | `vue/cloudide/workspace/QA_data/vue/5884.json` | `cases/vuejs-vue-5884` | Vue.set API behavior with numeric string path; expected explanation should distinguish API semantics from bug surface. |
| `microsoft-TypeScript-24625` | microsoft/TypeScript | #24625: TypeScript 2.9 Watch API change breaking watch support in ts-loader? | `TypeScript/cloudide/workspace/QA_data/TypeScript/24625.json` | `cases/microsoft-TypeScript-24625` | TypeScript watch API behavior change breaking consumers; explicit API responsibility. |
| `pandas-dev-pandas-25183` | pandas-dev/pandas | #25183: DataFrame.merge with empty frame and Int64 column gives object dtype | `pandas/cloudide/workspace/QA_data/pandas/25183.json` | `cases/pandas-dev-pandas-25183` | pandas merge dtype behavior with nullable integer arrays; API consistency case. |

## testing_build_tooling

| Case ID | Repository | Issue | Original Issue File | Case Directory | Rationale |
| --- | --- | ---: | --- | --- | --- |
| `pandas-dev-pandas-16499` | pandas-dev/pandas | #16499: TST: ujson tests are not being run | `pandas/cloudide/workspace/QA_data/pandas/16499.json` | `cases/pandas-dev-pandas-16499` | pandas test discovery gap where ujson tests were not run. |
| `pandas-dev-pandas-32289` | pandas-dev/pandas | #32289: CI Failing - Linux py37_np_dev - test_constructor_list_frames | `pandas/cloudide/workspace/QA_data/pandas/32289.json` | `cases/pandas-dev-pandas-32289` | pandas CI failure case; retrieval should explain construction/test failure context, not product behavior. |
| `microsoft-TypeScript-35468` | microsoft/TypeScript | #35468: TS does not recompile correctly when using a combination of project references, wildcard re-exports and watch mode | `TypeScript/cloudide/workspace/QA_data/TypeScript/35468.json` | `cases/microsoft-TypeScript-35468` | TypeScript watch/project-reference recompilation case; build tooling behavior. |

## maintenance_refactor

| Case ID | Repository | Issue | Original Issue File | Case Directory | Rationale |
| --- | --- | ---: | --- | --- | --- |
| `pandas-dev-pandas-35925` | pandas-dev/pandas | #35925: CLN remove unnecessary trailing commas to get ready for new version of black | `pandas/cloudide/workspace/QA_data/pandas/35925.json` | `cases/pandas-dev-pandas-35925` | pandas cleanup for Black formatting readiness; pure maintenance/cleanup signal. |
| `pandas-dev-pandas-22872` | pandas-dev/pandas | #22872: Replace bare excepts by explicit excepts in pandas/tests/ | `pandas/cloudide/workspace/QA_data/pandas/22872.json` | `cases/pandas-dev-pandas-22872` | pandas tests maintenance cleanup replacing bare excepts. |
| `pandas-dev-pandas-36617` | pandas-dev/pandas | #36617: DOC: Replace single with double backticks in RST files | `pandas/cloudide/workspace/QA_data/pandas/36617.json` | `cases/pandas-dev-pandas-36617` | pandas documentation cleanup case; distinct RST/docstring maintenance. |

## question_usage

| Case ID | Repository | Issue | Original Issue File | Case Directory | Rationale |
| --- | --- | ---: | --- | --- | --- |
| `microsoft-TypeScript-6307` | microsoft/TypeScript | #6307: Exported variable <variable name> has or is using private name <private name> | `TypeScript/cloudide/workspace/QA_data/TypeScript/6307.json` | `cases/microsoft-TypeScript-6307` | TypeScript canonical question/docs explanation about private-name export errors. |
| `microsoft-TypeScript-8305` | microsoft/TypeScript | #8305: Recommendation for exposing multiple TypeScript modules from single NPM package | `TypeScript/cloudide/workspace/QA_data/TypeScript/8305.json` | `cases/microsoft-TypeScript-8305` | TypeScript question/docs case about package module exposure; explanation-based oracle. |
| `pandas-dev-pandas-9219` | pandas-dev/pandas | #9219: DataFrame.to_hdf fails in Python 3.4 | `pandas/cloudide/workspace/QA_data/pandas/9219.json` | `cases/pandas-dev-pandas-9219` | pandas Usage Question around HDF storage; useful for comparing explanation to maintainer guidance. |

