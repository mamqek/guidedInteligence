# Appendix: Required-Evidence Audit

This appendix reports all 700 run-level judgements. P means present, Partial means related source survives without all required anchors, and A means absent. `Final files` is the total number of distinct files returned by final selection. The two represented-file columns show how many files from the required-evidence reference and the broader implementation Oracle occur in that result. A directly recorded loss is supported by an explicit final-selection omission. An inferred boundary is the first stage at which a unit is unavailable after appearing in an earlier recorded stage; it does not identify the exact internal decision responsible.

## vuejs-vue-10803

SSR routes a textarea DOM value through renderDOMProps into a text VNode child; the pre-resolution path passes null through without string normalization.

Connected required evidence: **yes**. Required-evidence files: **1**. Implementation-Oracle files: **1**. Required units: R, H.

| Unit | Exact pre-resolution source | Required responsibility |
|---|---|---|
| R | `src/platforms/web/server/modules/dom-props.js:8-44` (`renderDOMProps`) | Reads DOM properties and identifies the textarea value branch. |
| H | `src/platforms/web/server/modules/dom-props.js:46-50` (`setText`) | Constructs a text VNode and installs it as the element's child. |

| Condition | Repetition / run ID | R | H | Complete? | Final files | Required files represented | Implementation-Oracle files represented | Unit unavailability boundaries |
|---|---|---|---|---:|---:|---:|---:|---|
| Full Workspace | 1 · run-20260915T083906Z | P | P | Yes | 4 | 1/1 | 1/1 | — |
| Full Workspace | 2 · run-20260915T090105Z | P | A | No | 4 | 1/1 | 1/1 | H: final evidence selection [direct] |
| Full Workspace | 3 · run-20260915T090445Z | P | A | No | 5 | 1/1 | 1/1 | H: final evidence selection [direct] |
| Full Workspace | 4 · run-20260915T091330Z | P | A | No | 3 | 1/1 | 1/1 | H: final evidence selection [direct] |
| Without CodeGraph | 1 · run-20260915T085608Z | P | A | No | 4 | 1/1 | 1/1 | H: final evidence selection [direct] |
| Without CodeGraph | 2 · run-20260915T091709Z | P | A | No | 3 | 1/1 | 1/1 | H: final evidence selection [direct] |
| Without CodeGraph | 3 · run-20260915T092330Z | P | A | No | 2 | 1/1 | 1/1 | H: final evidence selection [direct] |
| Without CodeGraph | 4 · run-20260915T095308Z | P | A | No | 2 | 1/1 | 1/1 | H: final evidence selection [direct] |
| Without controller | 1 · run-20260915T084555Z | P | A | No | 2 | 1/1 | 1/1 | H: initial comparison [inferred] |
| Without controller | 2 · run-20260915T084834Z | P | A | No | 2 | 1/1 | 1/1 | H: raw retrieval [inferred] |
| Without controller | 3 · run-20260915T085058Z | P | A | No | 2 | 1/1 | 1/1 | H: raw retrieval [inferred] |
| Without controller | 4 · run-20260915T085339Z | P | A | No | 3 | 1/1 | 1/1 | H: raw retrieval [inferred] |
| Without either | 1 · run-20260915T090901Z | P | A | No | 2 | 1/1 | 1/1 | H: raw retrieval [inferred] |
| Without either | 2 · run-20260915T091102Z | P | A | No | 3 | 1/1 | 1/1 | H: raw retrieval [inferred] |
| Without either | 3 · run-20260915T092631Z | P | A | No | 2 | 1/1 | 1/1 | H: raw retrieval [inferred] |
| Without either | 4 · run-20260915T092951Z | P | A | No | 4 | 1/1 | 1/1 | H: raw retrieval [inferred] |
| Codex | 1 · run-20260902T171057Z | P | P | Yes | 5 | 1/1 | 1/1 | — |
| Codex | 2 · run-20260902T173511Z | P | P | Yes | 7 | 1/1 | 1/1 | — |
| Codex | 3 · run-20260902T173744Z | P | P | Yes | 5 | 1/1 | 1/1 | — |
| Codex | 4 · run-20260902T174007Z | P | Partial | No | 6 | 1/1 | 1/1 | H: Codex internal trace unavailable [trace unavailable] |

## microsoft-TypeScript-2953

The standard declaration surface contains ArrayBuffer types but omits DataView and its constructor.

Connected required evidence: **no**. Required-evidence files: **1**. Implementation-Oracle files: **1**. Required units: D.

| Unit | Exact pre-resolution source | Required responsibility |
|---|---|---|
| D | `src/lib/extensions.d.ts:1-45` (`ArrayBuffer declaration region`) | Establishes the declaration scope in which DataView is missing. |

| Condition | Repetition / run ID | D | Complete? | Final files | Required files represented | Implementation-Oracle files represented | Unit unavailability boundaries |
|---|---|---|---:|---:|---:|---:|---|
| Full Workspace | 1 · run-20260915T092041Z | P | Yes | 6 | 1/1 | 1/1 | — |
| Full Workspace | 2 · run-20260915T092856Z | A | No | 4 | 0/1 | 0/1 | D: controller recovery or qualification [inferred] |
| Full Workspace | 3 · run-20260915T093324Z | A | No | 2 | 0/1 | 0/1 | D: controller recovery or qualification [inferred] |
| Full Workspace | 4 · run-20260915T094712Z | A | No | 3 | 0/1 | 0/1 | D: controller recovery or qualification [inferred] |
| Without CodeGraph | 1 · run-20260915T095838Z | A | No | 3 | 0/1 | 0/1 | D: controller recovery or qualification [inferred] |
| Without CodeGraph | 2 · run-20260915T100205Z | A | No | 2 | 0/1 | 0/1 | D: controller recovery or qualification [inferred] |
| Without CodeGraph | 3 · run-20260915T100713Z | A | No | 3 | 0/1 | 0/1 | D: controller recovery or qualification [inferred] |
| Without CodeGraph | 4 · run-20260915T101019Z | A | No | 3 | 0/1 | 0/1 | D: controller recovery or qualification [inferred] |
| Without controller | 1 · run-20260915T085609Z | A | No | 1 | 0/1 | 0/1 | D: controller recovery or qualification [inferred] |
| Without controller | 2 · run-20260915T090411Z | A | No | 3 | 0/1 | 0/1 | D: controller recovery or qualification [inferred] |
| Without controller | 3 · run-20260915T090654Z | A | No | 2 | 0/1 | 0/1 | D: controller recovery or qualification [inferred] |
| Without controller | 4 · run-20260915T090941Z | A | No | 2 | 0/1 | 0/1 | D: controller recovery or qualification [inferred] |
| Without either | 1 · run-20260915T093816Z | A | No | 3 | 0/1 | 0/1 | D: controller recovery or qualification [inferred] |
| Without either | 2 · run-20260915T094024Z | A | No | 1 | 0/1 | 0/1 | D: controller recovery or qualification [inferred] |
| Without either | 3 · run-20260915T094231Z | A | No | 3 | 0/1 | 0/1 | D: controller recovery or qualification [inferred] |
| Without either | 4 · run-20260915T094447Z | A | No | 4 | 0/1 | 0/1 | D: final evidence selection [direct] |
| Codex | 1 · run-20260902T142427Z | A | No | 6 | 0/1 | 0/1 | D: Codex internal trace unavailable [trace unavailable] |
| Codex | 2 · run-20260902T142728Z | A | No | 5 | 0/1 | 0/1 | D: Codex internal trace unavailable [trace unavailable] |
| Codex | 3 · run-20260902T143011Z | P | Yes | 9 | 1/1 | 1/1 | — |
| Codex | 4 · run-20260902T143228Z | A | No | 7 | 0/1 | 0/1 | D: Codex internal trace unavailable [trace unavailable] |

## pandas-dev-pandas-10068

Series.add dispatches through a generated flexible arithmetic wrapper into Series._binop, which calculates a common name but constructs and finalizes the result without using it.

Connected required evidence: **yes**. Required-evidence files: **3**. Implementation-Oracle files: **1**. Required units: W, M, B.

| Unit | Exact pre-resolution source | Required responsibility |
|---|---|---|
| W | `pandas/core/ops.py:755-771` (`_flex_method_SERIES.flex_wrapper`) | Routes Series operands into Series._binop. |
| M | `pandas/core/common.py:3324-3336` (`_maybe_match_name`) | Defines the common-name decision for equal and unequal operand names. |
| B | `pandas/core/series.py:1466-1511` (`Series._binop`) | Combines the values, calculates the name, and constructs/finalizes the resulting Series. |

| Condition | Repetition / run ID | W | M | B | Complete? | Final files | Required files represented | Implementation-Oracle files represented | Unit unavailability boundaries |
|---|---|---|---|---|---:|---:|---:|---:|---|
| Full Workspace | 1 · run-20260915T101856Z | A | P | P | No | 4 | 3/3 | 1/1 | W: final evidence selection [direct] |
| Full Workspace | 2 · run-20260915T110633Z | A | P | A | No | 3 | 2/3 | 0/1 | W: candidate-pool construction [inferred]; B: candidate-pool construction [inferred] |
| Full Workspace | 3 · run-20260915T114427Z | P | A | A | No | 5 | 1/3 | 0/1 | M: raw retrieval [inferred]; B: candidate-pool construction [inferred] |
| Full Workspace | 4 · run-20260915T114934Z | A | P | A | No | 4 | 2/3 | 0/1 | W: candidate-pool construction [inferred]; B: raw retrieval [inferred] |
| Without CodeGraph | 1 · run-20260915T102301Z | A | A | A | No | 4 | 1/3 | 0/1 | W: candidate-pool construction [inferred]; M: raw retrieval [inferred]; B: controller recovery or qualification [inferred] |
| Without CodeGraph | 2 · run-20260915T103119Z | Partial | A | A | No | 4 | 1/3 | 0/1 | W: candidate-pool construction [inferred]; M: raw retrieval [inferred]; B: candidate-pool construction [inferred] |
| Without CodeGraph | 3 · run-20260915T103934Z | Partial | A | A | No | 2 | 1/3 | 0/1 | W: candidate-pool construction [inferred]; M: raw retrieval [inferred]; B: initial comparison [inferred] |
| Without CodeGraph | 4 · run-20260915T104408Z | Partial | A | A | No | 4 | 1/3 | 0/1 | W: candidate-pool construction [inferred]; M: raw retrieval [inferred]; B: controller recovery or qualification [inferred] |
| Without controller | 1 · run-20260915T091223Z | A | A | A | No | 3 | 1/3 | 0/1 | W: controller recovery or qualification [inferred]; M: raw retrieval [inferred]; B: initial comparison [inferred] |
| Without controller | 2 · run-20260915T091646Z | A | A | A | No | 2 | 1/3 | 0/1 | W: initial comparison [inferred]; M: raw retrieval [inferred]; B: initial comparison [inferred] |
| Without controller | 3 · run-20260915T091925Z | A | A | A | No | 2 | 1/3 | 0/1 | W: initial comparison [inferred]; M: raw retrieval [inferred]; B: initial comparison [inferred] |
| Without controller | 4 · run-20260915T092751Z | A | A | A | No | 2 | 1/3 | 0/1 | W: initial comparison [inferred]; M: raw retrieval [inferred]; B: raw retrieval [inferred] |
| Without either | 1 · run-20260915T095111Z | Partial | A | A | No | 1 | 1/3 | 0/1 | W: raw retrieval [inferred]; M: raw retrieval [inferred]; B: controller recovery or qualification [inferred] |
| Without either | 2 · run-20260915T095614Z | A | A | A | No | 2 | 1/3 | 0/1 | W: controller recovery or qualification [inferred]; M: raw retrieval [inferred]; B: controller recovery or qualification [inferred] |
| Without either | 3 · run-20260915T100522Z | Partial | A | A | No | 1 | 1/3 | 0/1 | W: raw retrieval [inferred]; M: raw retrieval [inferred]; B: controller recovery or qualification [inferred] |
| Without either | 4 · run-20260915T101354Z | A | A | A | No | 3 | 1/3 | 0/1 | W: controller recovery or qualification [inferred]; M: raw retrieval [inferred]; B: controller recovery or qualification [inferred] |
| Codex | 1 · run-20260902T151336Z | P | P | P | Yes | 6 | 3/3 | 1/1 | — |
| Codex | 2 · run-20260902T151542Z | P | P | P | Yes | 7 | 3/3 | 1/1 | — |
| Codex | 3 · run-20260902T151815Z | P | P | P | Yes | 5 | 3/3 | 1/1 | — |
| Codex | 4 · run-20260902T152024Z | P | P | P | Yes | 6 | 3/3 | 1/1 | — |

## vuejs-vue-10519

Prop-validation error construction eagerly formats the received Symbol using an expected primitive type, causing the diagnostic path itself to fail.

Connected required evidence: **yes**. Required-evidence files: **1**. Implementation-Oracle files: **1**. Required units: V, F.

| Unit | Exact pre-resolution source | Required responsibility |
|---|---|---|
| V | `src/core/util/props.js:203-222` (`getInvalidTypeMessage`) | Builds the invalid-prop message and eagerly asks styleValue to format both expected and received representations. |
| F | `src/core/util/props.js:224-238` (`styleValue/isExplicable`) | Shows the primitive formatting and explicable-type checks that are unsafe when applied under the wrong inferred type. |

| Condition | Repetition / run ID | V | F | Complete? | Final files | Required files represented | Implementation-Oracle files represented | Unit unavailability boundaries |
|---|---|---|---|---:|---:|---:|---:|---|
| Full Workspace | 1 · run-20260915T115429Z | P | A | No | 2 | 1/1 | 1/1 | F: candidate-pool construction [inferred] |
| Full Workspace | 2 · run-20260915T115735Z | A | A | No | 2 | 1/1 | 1/1 | V: final evidence selection [direct]; F: final evidence selection [direct] |
| Full Workspace | 3 · run-20260915T120026Z | P | A | No | 4 | 1/1 | 1/1 | F: final evidence selection [direct] |
| Full Workspace | 4 · run-20260915T120411Z | P | A | No | 3 | 1/1 | 1/1 | F: final evidence selection [direct] |
| Without CodeGraph | 1 · run-20260915T111343Z | P | A | No | 3 | 1/1 | 1/1 | F: controller recovery or qualification [inferred] |
| Without CodeGraph | 2 · run-20260915T112238Z | P | A | No | 1 | 1/1 | 1/1 | F: controller recovery or qualification [inferred] |
| Without CodeGraph | 3 · run-20260915T112539Z | P | A | No | 1 | 1/1 | 1/1 | F: controller recovery or qualification [inferred] |
| Without CodeGraph | 4 · run-20260915T112829Z | P | A | No | 2 | 1/1 | 1/1 | F: controller recovery or qualification [inferred] |
| Without controller | 1 · run-20260915T093159Z | P | Partial | No | 1 | 1/1 | 1/1 | F: controller recovery or qualification [inferred] |
| Without controller | 2 · run-20260915T093423Z | P | A | No | 1 | 1/1 | 1/1 | F: controller recovery or qualification [inferred] |
| Without controller | 3 · run-20260915T093637Z | P | A | No | 1 | 1/1 | 1/1 | F: raw retrieval [inferred] |
| Without controller | 4 · run-20260915T093855Z | P | A | No | 1 | 1/1 | 1/1 | F: controller recovery or qualification [inferred] |
| Without either | 1 · run-20260915T101551Z | P | A | No | 1 | 1/1 | 1/1 | F: controller recovery or qualification [inferred] |
| Without either | 2 · run-20260915T101813Z | P | A | No | 1 | 1/1 | 1/1 | F: controller recovery or qualification [inferred] |
| Without either | 3 · run-20260915T102025Z | P | A | No | 1 | 1/1 | 1/1 | F: controller recovery or qualification [inferred] |
| Without either | 4 · run-20260915T102818Z | P | A | No | 1 | 1/1 | 1/1 | F: controller recovery or qualification [inferred] |
| Codex | 1 · run-20260902T170425Z | P | Partial | No | 6 | 1/1 | 1/1 | F: Codex internal trace unavailable [trace unavailable] |
| Codex | 2 · run-20260902T170553Z | P | Partial | No | 6 | 1/1 | 1/1 | F: Codex internal trace unavailable [trace unavailable] |
| Codex | 3 · run-20260902T170729Z | P | Partial | No | 6 | 1/1 | 1/1 | F: Codex internal trace unavailable [trace unavailable] |
| Codex | 4 · run-20260902T170920Z | P | Partial | No | 5 | 1/1 | 1/1 | F: Codex internal trace unavailable [trace unavailable] |

## vuejs-vue-6301

The package exposes JavaScript client/server webpack-plugin entry points but provides no corresponding declaration entry points.

Connected required evidence: **no**. Required-evidence files: **3**. Implementation-Oracle files: **11**. Required units: P, C, S.

| Unit | Exact pre-resolution source | Required responsibility |
|---|---|---|
| P | `packages/vue-server-renderer/package.json:1-40` (`package type metadata`) | Shows the package-level type declaration and scripts but no plugin-specific declaration mapping. |
| C | `packages/vue-server-renderer/client-plugin.js:17-86` (`client plugin runtime entry point`) | Shows the existing client-plugin implementation and public runtime export for which a declaration entry point is missing. |
| S | `packages/vue-server-renderer/server-plugin.js:32-99` (`server plugin runtime entry point`) | Shows the existing server-plugin implementation and public runtime export for which a declaration entry point is missing. |

| Condition | Repetition / run ID | P | C | S | Complete? | Final files | Required files represented | Implementation-Oracle files represented | Unit unavailability boundaries |
|---|---|---|---|---|---:|---:|---:|---:|---|
| Full Workspace | 1 · run-20260915T121324Z | P | Partial | A | No | 7 | 2/3 | 1/11 | C: candidate-pool construction [inferred]; S: controller recovery or qualification [inferred] |
| Full Workspace | 2 · run-20260915T121705Z | A | Partial | A | No | 3 | 1/3 | 0/11 | P: controller recovery or qualification [inferred]; C: candidate-pool construction [inferred]; S: controller recovery or qualification [inferred] |
| Full Workspace | 3 · run-20260915T122053Z | P | Partial | A | No | 6 | 2/3 | 1/11 | C: candidate-pool construction [inferred]; S: controller recovery or qualification [inferred] |
| Full Workspace | 4 · run-20260915T122529Z | P | Partial | A | No | 6 | 2/3 | 1/11 | C: candidate-pool construction [inferred]; S: controller recovery or qualification [inferred] |
| Without CodeGraph | 1 · run-20260915T113145Z | P | P | A | No | 5 | 2/3 | 1/11 | S: controller recovery or qualification [inferred] |
| Without CodeGraph | 2 · run-20260915T113618Z | P | Partial | A | No | 4 | 2/3 | 1/11 | C: final evidence selection [direct]; S: controller recovery or qualification [inferred] |
| Without CodeGraph | 3 · run-20260915T114039Z | A | Partial | Partial | No | 5 | 2/3 | 0/11 | P: final evidence selection [direct]; C: final evidence selection [direct]; S: controller recovery or qualification [inferred] |
| Without CodeGraph | 4 · run-20260915T115307Z | P | P | A | No | 5 | 2/3 | 1/11 | S: controller recovery or qualification [inferred] |
| Without controller | 1 · run-20260915T094112Z | P | Partial | A | No | 3 | 2/3 | 1/11 | C: initial comparison [inferred]; S: controller recovery or qualification [inferred] |
| Without controller | 2 · run-20260915T094440Z | A | Partial | A | No | 4 | 1/3 | 0/11 | P: controller recovery or qualification [inferred]; C: initial comparison [inferred]; S: controller recovery or qualification [inferred] |
| Without controller | 3 · run-20260915T094738Z | P | Partial | A | No | 4 | 2/3 | 1/11 | C: initial comparison [inferred]; S: controller recovery or qualification [inferred] |
| Without controller | 4 · run-20260915T095017Z | P | Partial | A | No | 4 | 2/3 | 1/11 | C: initial comparison [inferred]; S: controller recovery or qualification [inferred] |
| Without either | 1 · run-20260915T103038Z | P | Partial | A | No | 4 | 2/3 | 1/11 | C: controller recovery or qualification [inferred]; S: controller recovery or qualification [inferred] |
| Without either | 2 · run-20260915T103303Z | A | Partial | A | No | 4 | 1/3 | 0/11 | P: controller recovery or qualification [inferred]; C: controller recovery or qualification [inferred]; S: controller recovery or qualification [inferred] |
| Without either | 3 · run-20260915T103543Z | P | Partial | A | No | 4 | 2/3 | 1/11 | C: controller recovery or qualification [inferred]; S: controller recovery or qualification [inferred] |
| Without either | 4 · run-20260915T103813Z | P | Partial | A | No | 6 | 2/3 | 1/11 | C: controller recovery or qualification [inferred]; S: controller recovery or qualification [inferred] |
| Codex | 1 · run-20260902T181141Z | P | A | A | No | 11 | 1/3 | 1/11 | C: Codex internal trace unavailable [trace unavailable]; S: Codex internal trace unavailable [trace unavailable] |
| Codex | 2 · run-20260902T181330Z | P | Partial | A | No | 8 | 2/3 | 1/11 | C: Codex internal trace unavailable [trace unavailable]; S: Codex internal trace unavailable [trace unavailable] |
| Codex | 3 · run-20260902T181511Z | P | A | A | No | 6 | 1/3 | 1/11 | C: Codex internal trace unavailable [trace unavailable]; S: Codex internal trace unavailable [trace unavailable] |
| Codex | 4 · run-20260902T181713Z | P | P | A | No | 9 | 2/3 | 1/11 | S: Codex internal trace unavailable [trace unavailable] |

## microsoft-TypeScript-45713

Watch/build paths count diagnostics and forward only a scalar error count to a formatter that can print no per-file breakdown.

Connected required evidence: **yes**. Required-evidence files: **2**. Implementation-Oracle files: **7**. Required units: C, W, B, R.

| Unit | Exact pre-resolution source | Required responsibility |
|---|---|---|
| C | `src/compiler/watch.ts:96-117` (`getErrorCountForSummary/getErrorSummaryText`) | Counts errors and formats only the aggregate count. |
| W | `src/compiler/watch.ts:340-360` (`watch status reporter`) | Passes only the count from watch diagnostics to the summary formatter. |
| B | `src/compiler/tsbuildPublic.ts:75-109` (`ReportEmitErrorSummary/reportErrorSummary`) | Defines the build-host summary callback as accepting only an error count. |
| R | `src/compiler/tsbuildPublic.ts:2000-2027` (`solution-builder reportErrorSummary`) | Aggregates project errors and calls the host with only totalErrors. |

| Condition | Repetition / run ID | C | W | B | R | Complete? | Final files | Required files represented | Implementation-Oracle files represented | Unit unavailability boundaries |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| Full Workspace | 1 · run-20260915T122948Z | P | P | A | A | No | 8 | 1/2 | 3/7 | B: raw retrieval [inferred]; R: controller recovery or qualification [inferred] |
| Full Workspace | 2 · run-20260915T123455Z | P | P | A | A | No | 5 | 1/2 | 2/7 | B: initial comparison [inferred]; R: controller recovery or qualification [inferred] |
| Full Workspace | 3 · run-20260915T123954Z | P | P | A | P | No | 7 | 2/2 | 4/7 | B: candidate-pool construction [inferred] |
| Full Workspace | 4 · run-20260915T124602Z | P | P | A | A | No | 6 | 1/2 | 3/7 | B: initial comparison [inferred]; R: initial comparison [inferred] |
| Without CodeGraph | 1 · run-20260915T115644Z | P | A | A | A | No | 4 | 1/2 | 1/7 | W: controller recovery or qualification [inferred]; B: raw retrieval [inferred]; R: controller recovery or qualification [inferred] |
| Without CodeGraph | 2 · run-20260915T120753Z | Partial | A | A | P | No | 5 | 2/2 | 4/7 | C: final evidence selection [direct]; W: controller recovery or qualification [inferred]; B: controller recovery or qualification [inferred] |
| Without CodeGraph | 3 · run-20260915T121157Z | Partial | A | A | A | No | 4 | 1/2 | 3/7 | C: final evidence selection [direct]; W: controller recovery or qualification [inferred]; B: controller recovery or qualification [inferred]; R: controller recovery or qualification [inferred] |
| Without CodeGraph | 4 · run-20260915T172023Z | Partial | A | A | A | No | 4 | 1/2 | 3/7 | C: final evidence selection [direct]; W: controller recovery or qualification [inferred]; B: controller recovery or qualification [inferred]; R: controller recovery or qualification [inferred] |
| Without controller | 1 · run-20260915T095247Z | P | P | A | A | No | 6 | 1/2 | 2/7 | B: initial comparison [inferred]; R: controller recovery or qualification [inferred] |
| Without controller | 2 · run-20260915T101236Z | P | P | A | A | No | 5 | 1/2 | 3/7 | B: initial comparison [inferred]; R: controller recovery or qualification [inferred] |
| Without controller | 3 · run-20260915T101541Z | P | P | A | P | No | 7 | 2/2 | 3/7 | B: initial comparison [inferred] |
| Without controller | 4 · run-20260915T102257Z | P | P | A | P | No | 5 | 2/2 | 3/7 | B: controller recovery or qualification [inferred] |
| Without either | 1 · run-20260915T104513Z | P | A | A | A | No | 2 | 1/2 | 2/7 | W: controller recovery or qualification [inferred]; B: initial comparison [inferred]; R: controller recovery or qualification [inferred] |
| Without either | 2 · run-20260915T104915Z | P | A | A | A | No | 2 | 1/2 | 2/7 | W: controller recovery or qualification [inferred]; B: controller recovery or qualification [inferred]; R: controller recovery or qualification [inferred] |
| Without either | 3 · run-20260915T105133Z | P | A | A | A | No | 3 | 1/2 | 1/7 | W: controller recovery or qualification [inferred]; B: controller recovery or qualification [inferred]; R: controller recovery or qualification [inferred] |
| Without either | 4 · run-20260915T105354Z | P | A | A | A | No | 4 | 1/2 | 3/7 | W: controller recovery or qualification [inferred]; B: controller recovery or qualification [inferred]; R: controller recovery or qualification [inferred] |
| Codex | 1 · run-20260902T144336Z | P | P | A | P | No | 6 | 2/2 | 4/7 | B: Codex internal trace unavailable [trace unavailable] |
| Codex | 2 · run-20260902T144559Z | P | P | P | P | Yes | 5 | 2/2 | 4/7 | — |
| Codex | 3 · run-20260902T144810Z | P | P | A | A | No | 6 | 1/2 | 4/7 | B: Codex internal trace unavailable [trace unavailable]; R: Codex internal trace unavailable [trace unavailable] |
| Codex | 4 · run-20260902T145024Z | P | P | A | P | No | 5 | 2/2 | 4/7 | B: Codex internal trace unavailable [trace unavailable] |

## pandas-dev-pandas-4542

DataFrame.to_excel delegates through ExcelWriter's engine registry, whose pre-resolution implementations support openpyxl and xlwt but not xlsxwriter.

Connected required evidence: **yes**. Required-evidence files: **2**. Implementation-Oracle files: **3**. Required units: D, R, E, X.

| Unit | Exact pre-resolution source | Required responsibility |
|---|---|---|
| D | `pandas/core/frame.py:1356-1415` (`DataFrame.to_excel`) | Exposes the public DataFrame export entry point and its ExcelWriter delegation. |
| R | `pandas/io/excel.py:20-40` (`writer registry and ExcelWriter`) | Registers writer classes by engine name. |
| E | `pandas/io/excel.py:284-411` (`ExcelWriter`) | Selects a registered engine from the extension/configuration and instantiates it. |
| X | `pandas/io/excel.py:412-612` (`writer implementations`) | Shows the complete pre-resolution writer implementation region ending with xlwt and lacking an xlsxwriter writer. |

| Condition | Repetition / run ID | D | R | E | X | Complete? | Final files | Required files represented | Implementation-Oracle files represented | Unit unavailability boundaries |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| Full Workspace | 1 · run-20260915T125132Z | P | P | P | Partial | No | 4 | 2/2 | 2/3 | X: initial comparison [inferred] |
| Full Workspace | 2 · run-20260915T125409Z | P | P | P | Partial | No | 3 | 2/2 | 2/3 | X: candidate-pool construction [inferred] |
| Full Workspace | 3 · run-20260915T125911Z | P | P | P | Partial | No | 3 | 2/2 | 2/3 | X: candidate-pool construction [inferred] |
| Full Workspace | 4 · run-20260915T130428Z | P | P | P | Partial | No | 4 | 2/2 | 2/3 | X: candidate-pool construction [inferred] |
| Without CodeGraph | 1 · run-20260915T172445Z | P | P | Partial | Partial | No | 4 | 2/2 | 2/3 | E: candidate-pool construction [inferred]; X: candidate-pool construction [inferred] |
| Without CodeGraph | 2 · run-20260915T173007Z | P | A | P | Partial | No | 6 | 2/2 | 2/3 | R: candidate-pool construction [inferred]; X: controller recovery or qualification [inferred] |
| Without CodeGraph | 3 · run-20260915T173553Z | P | A | P | Partial | No | 5 | 2/2 | 2/3 | R: candidate-pool construction [inferred]; X: controller recovery or qualification [inferred] |
| Without CodeGraph | 4 · run-20260915T174047Z | P | P | Partial | Partial | No | 5 | 2/2 | 2/3 | E: candidate-pool construction [inferred]; X: controller recovery or qualification [inferred] |
| Without controller | 1 · run-20260915T102605Z | P | P | P | Partial | No | 3 | 2/2 | 2/3 | X: initial comparison [inferred] |
| Without controller | 2 · run-20260915T104233Z | P | P | P | Partial | No | 4 | 2/2 | 2/3 | X: initial comparison [inferred] |
| Without controller | 3 · run-20260915T104744Z | P | P | P | Partial | No | 3 | 2/2 | 2/3 | X: initial comparison [inferred] |
| Without controller | 4 · run-20260915T105032Z | P | P | P | A | No | 4 | 2/2 | 2/3 | X: controller recovery or qualification [inferred] |
| Without either | 1 · run-20260915T105627Z | Partial | A | Partial | Partial | No | 4 | 2/2 | 2/3 | D: controller recovery or qualification [inferred]; R: controller recovery or qualification [inferred]; E: initial comparison [inferred]; X: controller recovery or qualification [inferred] |
| Without either | 2 · run-20260915T105852Z | Partial | A | Partial | Partial | No | 3 | 2/2 | 2/3 | D: controller recovery or qualification [inferred]; R: controller recovery or qualification [inferred]; E: initial comparison [inferred]; X: controller recovery or qualification [inferred] |
| Without either | 3 · run-20260915T110124Z | A | A | Partial | P | No | 4 | 1/2 | 1/3 | D: controller recovery or qualification [inferred]; R: controller recovery or qualification [inferred]; E: initial comparison [inferred] |
| Without either | 4 · run-20260915T110358Z | A | A | P | Partial | No | 4 | 1/2 | 1/3 | D: controller recovery or qualification [inferred]; R: controller recovery or qualification [inferred]; X: controller recovery or qualification [inferred] |
| Codex | 1 · run-20260902T164612Z | P | P | P | Partial | No | 6 | 2/2 | 2/3 | X: Codex internal trace unavailable [trace unavailable] |
| Codex | 2 · run-20260902T164803Z | P | P | Partial | Partial | No | 8 | 2/2 | 2/3 | E: Codex internal trace unavailable [trace unavailable]; X: Codex internal trace unavailable [trace unavailable] |
| Codex | 3 · run-20260902T165006Z | P | P | P | Partial | No | 6 | 2/2 | 2/3 | X: Codex internal trace unavailable [trace unavailable] |
| Codex | 4 · run-20260902T165201Z | P | P | P | Partial | No | 9 | 2/2 | 2/3 | X: Codex internal trace unavailable [trace unavailable] |

## microsoft-TypeScript-10020

Organize Imports collects only top-level import declarations even though the compiler can identify ambient modules, so imports nested in those modules never enter grouping and edit generation.

Connected required evidence: **yes**. Required-evidence files: **2**. Implementation-Oracle files: **2**. Required units: O, A.

| Unit | Exact pre-resolution source | Required responsibility |
|---|---|---|
| O | `src/services/organizeImports.ts:10-57` (`OrganizeImports.organizeImports`) | Collects, groups, rewrites, and deletes only sourceFile.statements imports; the TODO names ambient modules explicitly. |
| A | `src/compiler/utilities.ts:423-433` (`isAmbientModule`) | Provides the predicate that can identify string-named or global ambient modules. |

| Condition | Repetition / run ID | O | A | Complete? | Final files | Required files represented | Implementation-Oracle files represented | Unit unavailability boundaries |
|---|---|---|---|---:|---:|---:|---:|---|
| Full Workspace | 1 · run-20260915T130940Z | P | A | No | 7 | 1/2 | 1/2 | A: raw retrieval [inferred] |
| Full Workspace | 2 · run-20260915T131533Z | P | A | No | 4 | 1/2 | 1/2 | A: raw retrieval [inferred] |
| Full Workspace | 3 · run-20260915T132035Z | P | A | No | 4 | 1/2 | 1/2 | A: raw retrieval [inferred] |
| Full Workspace | 4 · run-20260915T132457Z | P | A | No | 7 | 1/2 | 1/2 | A: raw retrieval [inferred] |
| Without CodeGraph | 1 · run-20260915T174428Z | Partial | A | No | 5 | 1/2 | 1/2 | O: final evidence selection [direct]; A: raw retrieval [inferred] |
| Without CodeGraph | 2 · run-20260915T174947Z | P | A | No | 3 | 1/2 | 1/2 | A: raw retrieval [inferred] |
| Without CodeGraph | 3 · run-20260915T175649Z | P | A | No | 5 | 1/2 | 1/2 | A: raw retrieval [inferred] |
| Without CodeGraph | 4 · run-20260915T180220Z | P | A | No | 4 | 1/2 | 1/2 | A: raw retrieval [inferred] |
| Without controller | 1 · run-20260915T105300Z | P | A | No | 5 | 1/2 | 1/2 | A: raw retrieval [inferred] |
| Without controller | 2 · run-20260915T110538Z | P | A | No | 7 | 1/2 | 1/2 | A: raw retrieval [inferred] |
| Without controller | 3 · run-20260915T110856Z | P | A | No | 4 | 1/2 | 1/2 | A: raw retrieval [inferred] |
| Without controller | 4 · run-20260915T111157Z | P | A | No | 5 | 1/2 | 1/2 | A: raw retrieval [inferred] |
| Without either | 1 · run-20260915T111631Z | P | A | No | 5 | 1/2 | 1/2 | A: raw retrieval [inferred] |
| Without either | 2 · run-20260915T111910Z | P | A | No | 4 | 1/2 | 1/2 | A: raw retrieval [inferred] |
| Without either | 3 · run-20260915T112152Z | P | A | No | 4 | 1/2 | 1/2 | A: raw retrieval [inferred] |
| Without either | 4 · run-20260915T112436Z | P | A | No | 3 | 1/2 | 1/2 | A: raw retrieval [inferred] |
| Codex | 1 · run-20260902T133446Z | Partial | A | No | 5 | 1/2 | 1/2 | O: Codex internal trace unavailable [trace unavailable]; A: Codex internal trace unavailable [trace unavailable] |
| Codex | 2 · run-20260902T133625Z | Partial | A | No | 5 | 1/2 | 1/2 | O: Codex internal trace unavailable [trace unavailable]; A: Codex internal trace unavailable [trace unavailable] |
| Codex | 3 · run-20260902T133744Z | Partial | A | No | 6 | 1/2 | 1/2 | O: Codex internal trace unavailable [trace unavailable]; A: Codex internal trace unavailable [trace unavailable] |
| Codex | 4 · run-20260902T133926Z | P | A | No | 5 | 1/2 | 1/2 | A: Codex internal trace unavailable [trace unavailable] |

## pandas-dev-pandas-14942

Categorical groupby carries every category into grouping and later re-expands the Cartesian result space, even when only a small subset is observed.

Connected required evidence: **yes**. Required-evidence files: **3**. Implementation-Oracle files: **6**. Required units: P, C, G, I, R.

| Unit | Exact pre-resolution source | Required responsibility |
|---|---|---|
| P | `pandas/core/generic.py:6601-6668` (`NDFrame.groupby`) | Exposes the public groupby entry point, which has no observed parameter and forwards no observed choice. |
| C | `pandas/core/arrays/categorical.py:650-689` (`Categorical._codes_for_groupby`) | Returns category codes for grouping without an observed-only mode. |
| G | `pandas/core/groupby/groupby.py:553-590` (`_GroupBy.__init__`) | Builds the grouper without carrying an observed option. |
| I | `pandas/core/groupby/groupby.py:2874-2990` (`Grouping.__init__`) | Recodes categorical groupers against the complete category set. |
| R | `pandas/core/groupby/groupby.py:4690-4725` (`_GroupBy._reindex_output`) | Re-expands results to the product of group levels. |

| Condition | Repetition / run ID | P | C | G | I | R | Complete? | Final files | Required files represented | Implementation-Oracle files represented | Unit unavailability boundaries |
|---|---|---|---|---|---|---|---:|---:|---:|---:|---|
| Full Workspace | 1 · run-20260915T133038Z | A | P | A | P | A | No | 4 | 2/3 | 2/6 | P: candidate-pool construction [inferred]; G: candidate-pool construction [inferred]; R: candidate-pool construction [inferred] |
| Full Workspace | 2 · run-20260915T133659Z | A | P | A | P | A | No | 7 | 2/3 | 2/6 | P: candidate-pool construction [inferred]; G: candidate-pool construction [inferred]; R: candidate-pool construction [inferred] |
| Full Workspace | 3 · run-20260915T134316Z | A | P | A | P | A | No | 5 | 2/3 | 2/6 | P: candidate-pool construction [inferred]; G: candidate-pool construction [inferred]; R: candidate-pool construction [inferred] |
| Full Workspace | 4 · run-20260915T134908Z | A | P | A | P | A | No | 4 | 2/3 | 2/6 | P: candidate-pool construction [inferred]; G: candidate-pool construction [inferred]; R: candidate-pool construction [inferred] |
| Without CodeGraph | 1 · run-20260915T174227Z | A | A | A | A | P | No | 5 | 2/3 | 2/6 | P: controller recovery or qualification [inferred]; C: initial comparison [inferred]; G: raw retrieval [inferred]; I: candidate-pool construction [inferred] |
| Without CodeGraph | 2 · run-20260915T185651Z | A | P | A | P | P | No | 6 | 2/3 | 2/6 | P: final evidence selection [direct]; G: raw retrieval [inferred] |
| Without CodeGraph | 3 · run-20260915T190338Z | A | A | A | A | A | No | 5 | 1/3 | 1/6 | P: controller recovery or qualification [inferred]; C: controller recovery or qualification [inferred]; G: raw retrieval [inferred]; I: final evidence selection [direct]; R: raw retrieval [inferred] |
| Without CodeGraph | 4 · run-20260915T190926Z | A | P | A | P | A | No | 6 | 2/3 | 3/6 | P: controller recovery or qualification [inferred]; G: raw retrieval [inferred]; R: raw retrieval [inferred] |
| Without controller | 1 · run-20260915T111451Z | A | A | A | A | A | No | 3 | 0/3 | 0/6 | P: controller recovery or qualification [inferred]; C: initial comparison [inferred]; G: raw retrieval [inferred]; I: initial comparison [inferred]; R: raw retrieval [inferred] |
| Without controller | 2 · run-20260915T111712Z | A | P | A | Partial | A | No | 5 | 2/3 | 2/6 | P: controller recovery or qualification [inferred]; G: raw retrieval [inferred]; I: final evidence selection [direct]; R: initial comparison [inferred] |
| Without controller | 3 · run-20260915T112013Z | A | A | A | A | A | No | 1 | 0/3 | 0/6 | P: controller recovery or qualification [inferred]; C: initial comparison [inferred]; G: raw retrieval [inferred]; I: initial comparison [inferred]; R: initial comparison [inferred] |
| Without controller | 4 · run-20260915T112726Z | A | A | A | P | A | No | 4 | 1/3 | 1/6 | P: controller recovery or qualification [inferred]; C: initial comparison [inferred]; G: raw retrieval [inferred]; R: initial comparison [inferred] |
| Without either | 1 · run-20260915T114437Z | A | A | A | A | A | No | 7 | 2/3 | 2/6 | P: controller recovery or qualification [inferred]; C: controller recovery or qualification [inferred]; G: raw retrieval [inferred]; I: controller recovery or qualification [inferred]; R: controller recovery or qualification [inferred] |
| Without either | 2 · run-20260915T114720Z | A | A | A | A | P | No | 5 | 2/3 | 2/6 | P: controller recovery or qualification [inferred]; C: controller recovery or qualification [inferred]; G: raw retrieval [inferred]; I: controller recovery or qualification [inferred] |
| Without either | 3 · run-20260915T115008Z | A | A | A | A | P | No | 5 | 1/3 | 1/6 | P: initial comparison [inferred]; C: controller recovery or qualification [inferred]; G: raw retrieval [inferred]; I: controller recovery or qualification [inferred] |
| Without either | 4 · run-20260915T120226Z | A | A | A | A | A | No | 3 | 1/3 | 1/6 | P: controller recovery or qualification [inferred]; C: controller recovery or qualification [inferred]; G: raw retrieval [inferred]; I: controller recovery or qualification [inferred]; R: controller recovery or qualification [inferred] |
| Codex | 1 · run-20260902T153037Z | A | P | A | P | P | No | 4 | 2/3 | 2/6 | P: Codex internal trace unavailable [trace unavailable]; G: Codex internal trace unavailable [trace unavailable] |
| Codex | 2 · run-20260902T153316Z | Partial | P | A | P | P | No | 8 | 3/3 | 3/6 | P: Codex internal trace unavailable [trace unavailable]; G: Codex internal trace unavailable [trace unavailable] |
| Codex | 3 · run-20260902T153605Z | P | P | A | P | A | No | 7 | 3/3 | 3/6 | G: Codex internal trace unavailable [trace unavailable]; R: Codex internal trace unavailable [trace unavailable] |
| Codex | 4 · run-20260902T153916Z | A | A | A | P | P | No | 5 | 1/3 | 1/6 | P: Codex internal trace unavailable [trace unavailable]; C: Codex internal trace unavailable [trace unavailable]; G: Codex internal trace unavailable [trace unavailable] |

## pandas-dev-pandas-16764

Importing core pandas modules eagerly imports computation, plotting, and optional I/O dependencies before their features are used.

Connected required evidence: **yes**. Required-evidence files: **5**. Implementation-Oracle files: **17**. Required units: F, O, C, P, I.

| Unit | Exact pre-resolution source | Required responsibility |
|---|---|---|
| F | `pandas/core/frame.py:65-105` (`frame module imports`) | Eagerly imports computation expression/eval and plotting modules while loading DataFrame. |
| O | `pandas/core/ops.py:1-25` (`ops module imports`) | Eagerly imports the computation expression engine while loading arithmetic operations. |
| C | `pandas/core/computation/__init__.py:1-23` (`computation package initialization`) | Performs dependency checks and imports computation components at package import time. |
| P | `pandas/plotting/__init__.py:1-19` (`plotting package initialization`) | Imports plotting conversion, core, style, and tools modules eagerly. |
| I | `pandas/io/common.py:1-45` (`optional I/O imports`) | Attempts optional cloud-filesystem imports while loading common I/O helpers. |

| Condition | Repetition / run ID | F | O | C | P | I | Complete? | Final files | Required files represented | Implementation-Oracle files represented | Unit unavailability boundaries |
|---|---|---|---|---|---|---|---:|---:|---:|---:|---|
| Full Workspace | 1 · run-20260915T135514Z | A | A | A | A | A | No | 2 | 0/5 | 1/17 | F: initial comparison [inferred]; O: raw retrieval [inferred]; C: initial comparison [inferred]; P: candidate-pool construction [inferred]; I: raw retrieval [inferred] |
| Full Workspace | 2 · run-20260915T171716Z | A | A | A | A | A | No | 2 | 0/5 | 1/17 | F: raw retrieval [inferred]; O: raw retrieval [inferred]; C: initial comparison [inferred]; P: raw retrieval [inferred]; I: raw retrieval [inferred] |
| Full Workspace | 3 · run-20260915T172229Z | A | A | A | A | A | No | 2 | 0/5 | 0/17 | F: raw retrieval [inferred]; O: raw retrieval [inferred]; C: candidate-pool construction [inferred]; P: candidate-pool construction [inferred]; I: raw retrieval [inferred] |
| Full Workspace | 4 · run-20260915T172726Z | A | A | A | A | A | No | 2 | 0/5 | 0/17 | F: initial comparison [inferred]; O: raw retrieval [inferred]; C: candidate-pool construction [inferred]; P: raw retrieval [inferred]; I: raw retrieval [inferred] |
| Without CodeGraph | 1 · run-20260915T174227Z | A | A | A | A | A | No | 6 | 0/5 | 0/17 | F: initial comparison [inferred]; O: raw retrieval [inferred]; C: initial comparison [inferred]; P: raw retrieval [inferred]; I: raw retrieval [inferred] |
| Without CodeGraph | 2 · run-20260915T174801Z | A | A | A | A | A | No | 2 | 0/5 | 0/17 | F: initial comparison [inferred]; O: raw retrieval [inferred]; C: initial comparison [inferred]; P: raw retrieval [inferred]; I: raw retrieval [inferred] |
| Without CodeGraph | 3 · run-20260915T175110Z | A | A | A | A | A | No | 6 | 0/5 | 1/17 | F: initial comparison [inferred]; O: raw retrieval [inferred]; C: initial comparison [inferred]; P: raw retrieval [inferred]; I: raw retrieval [inferred] |
| Without CodeGraph | 4 · run-20260915T175648Z | A | A | A | A | A | No | 6 | 0/5 | 1/17 | F: raw retrieval [inferred]; O: raw retrieval [inferred]; C: initial comparison [inferred]; P: raw retrieval [inferred]; I: raw retrieval [inferred] |
| Without controller | 1 · run-20260915T113022Z | A | A | A | A | A | No | 2 | 0/5 | 0/17 | F: raw retrieval [inferred]; O: raw retrieval [inferred]; C: initial comparison [inferred]; P: initial comparison [inferred]; I: raw retrieval [inferred] |
| Without controller | 2 · run-20260915T113559Z | A | A | A | A | A | No | 1 | 0/5 | 0/17 | F: raw retrieval [inferred]; O: raw retrieval [inferred]; C: initial comparison [inferred]; P: raw retrieval [inferred]; I: raw retrieval [inferred] |
| Without controller | 3 · run-20260915T113818Z | A | A | A | A | A | No | 2 | 0/5 | 0/17 | F: raw retrieval [inferred]; O: raw retrieval [inferred]; C: initial comparison [inferred]; P: raw retrieval [inferred]; I: raw retrieval [inferred] |
| Without controller | 4 · run-20260915T114139Z | A | A | A | A | A | No | 2 | 0/5 | 0/17 | F: raw retrieval [inferred]; O: raw retrieval [inferred]; C: initial comparison [inferred]; P: raw retrieval [inferred]; I: raw retrieval [inferred] |
| Without either | 1 · run-20260915T120457Z | A | A | A | A | A | No | 2 | 0/5 | 1/17 | F: controller recovery or qualification [inferred]; O: raw retrieval [inferred]; C: controller recovery or qualification [inferred]; P: raw retrieval [inferred]; I: raw retrieval [inferred] |
| Without either | 2 · run-20260915T120659Z | A | A | A | A | A | No | 5 | 0/5 | 2/17 | F: initial comparison [inferred]; O: raw retrieval [inferred]; C: controller recovery or qualification [inferred]; P: initial comparison [inferred]; I: raw retrieval [inferred] |
| Without either | 3 · run-20260915T120915Z | A | A | A | A | A | No | 4 | 0/5 | 1/17 | F: initial comparison [inferred]; O: raw retrieval [inferred]; C: controller recovery or qualification [inferred]; P: raw retrieval [inferred]; I: raw retrieval [inferred] |
| Without either | 4 · run-20260915T121124Z | A | A | A | A | A | No | 1 | 0/5 | 0/17 | F: initial comparison [inferred]; O: raw retrieval [inferred]; C: controller recovery or qualification [inferred]; P: raw retrieval [inferred]; I: raw retrieval [inferred] |
| Codex | 1 · run-20260902T154702Z | Partial | A | Partial | P | A | No | 32 | 3/5 | 6/17 | F: Codex internal trace unavailable [trace unavailable]; O: Codex internal trace unavailable [trace unavailable]; C: Codex internal trace unavailable [trace unavailable]; I: Codex internal trace unavailable [trace unavailable] |
| Codex | 2 · run-20260902T154912Z | A | A | Partial | P | A | No | 19 | 2/5 | 5/17 | F: Codex internal trace unavailable [trace unavailable]; O: Codex internal trace unavailable [trace unavailable]; C: Codex internal trace unavailable [trace unavailable]; I: Codex internal trace unavailable [trace unavailable] |
| Codex | 3 · run-20260902T155131Z | A | A | A | P | A | No | 14 | 1/5 | 3/17 | F: Codex internal trace unavailable [trace unavailable]; O: Codex internal trace unavailable [trace unavailable]; C: Codex internal trace unavailable [trace unavailable]; I: Codex internal trace unavailable [trace unavailable] |
| Codex | 4 · run-20260902T155344Z | A | A | A | P | A | No | 9 | 1/5 | 3/17 | F: Codex internal trace unavailable [trace unavailable]; O: Codex internal trace unavailable [trace unavailable]; C: Codex internal trace unavailable [trace unavailable]; I: Codex internal trace unavailable [trace unavailable] |

## microsoft-TypeScript-10041

Logical-or and conditional expressions reduce their alternatives directly through getUnionType, which can choose a less specific array type despite one alternative being assignable to the other.

Connected required evidence: **yes**. Required-evidence files: **1**. Implementation-Oracle files: **1**. Required units: B, C.

| Unit | Exact pre-resolution source | Required responsibility |
|---|---|---|
| B | `src/compiler/checker.ts:12900-13055` (`checkBinaryExpression`) | Checks logical-or expressions and sends the two possible types directly to getUnionType. |
| C | `src/compiler/checker.ts:13165-13180` (`checkConditionalExpression`) | Combines conditional branches through the same direct union reduction. |

| Condition | Repetition / run ID | B | C | Complete? | Final files | Required files represented | Implementation-Oracle files represented | Unit unavailability boundaries |
|---|---|---|---|---:|---:|---:|---:|---|
| Full Workspace | 1 · run-20260916T084338Z | A | A | No | 3 | 0/1 | 0/1 | B: raw retrieval [inferred]; C: raw retrieval [inferred] |
| Full Workspace | 2 · run-20260916T084731Z | A | A | No | 4 | 1/1 | 1/1 | B: raw retrieval [inferred]; C: raw retrieval [inferred] |
| Full Workspace | 3 · run-20260916T085008Z | A | A | No | 3 | 1/1 | 1/1 | B: raw retrieval [inferred]; C: raw retrieval [inferred] |
| Full Workspace | 4 · run-20260916T085300Z | A | A | No | 2 | 0/1 | 0/1 | B: initial comparison [inferred]; C: raw retrieval [inferred] |
| Without CodeGraph | 1 · run-20260916T045952Z | A | A | No | 2 | 0/1 | 0/1 | B: raw retrieval [inferred]; C: raw retrieval [inferred] |
| Without CodeGraph | 2 · run-20260916T051650Z | A | A | No | 3 | 1/1 | 1/1 | B: raw retrieval [inferred]; C: raw retrieval [inferred] |
| Without CodeGraph | 3 · run-20260916T051920Z | A | A | No | 4 | 1/1 | 1/1 | B: raw retrieval [inferred]; C: raw retrieval [inferred] |
| Without CodeGraph | 4 · run-20260916T052152Z | A | A | No | 1 | 0/1 | 0/1 | B: raw retrieval [inferred]; C: raw retrieval [inferred] |
| Without controller | 1 · run-20260916T041240Z | A | A | No | 3 | 1/1 | 1/1 | B: raw retrieval [inferred]; C: raw retrieval [inferred] |
| Without controller | 2 · run-20260916T041714Z | A | A | No | 3 | 1/1 | 1/1 | B: raw retrieval [inferred]; C: raw retrieval [inferred] |
| Without controller | 3 · run-20260916T041903Z | A | A | No | 2 | 0/1 | 0/1 | B: raw retrieval [inferred]; C: raw retrieval [inferred] |
| Without controller | 4 · run-20260916T042041Z | A | A | No | 3 | 0/1 | 0/1 | B: raw retrieval [inferred]; C: raw retrieval [inferred] |
| Without either | 1 · run-20260916T085523Z | A | A | No | 3 | 1/1 | 1/1 | B: raw retrieval [inferred]; C: raw retrieval [inferred] |
| Without either | 2 · run-20260916T085650Z | A | A | No | 2 | 1/1 | 1/1 | B: raw retrieval [inferred]; C: raw retrieval [inferred] |
| Without either | 3 · run-20260916T085807Z | A | A | No | 1 | 0/1 | 0/1 | B: raw retrieval [inferred]; C: raw retrieval [inferred] |
| Without either | 4 · run-20260916T085921Z | A | A | No | 3 | 1/1 | 1/1 | B: raw retrieval [inferred]; C: raw retrieval [inferred] |
| Codex | 1 · run-20260902T134119Z | P | A | No | 2 | 1/1 | 1/1 | C: Codex internal trace unavailable [trace unavailable] |
| Codex | 2 · run-20260902T134446Z | P | A | No | 4 | 1/1 | 1/1 | C: Codex internal trace unavailable [trace unavailable] |
| Codex | 3 · run-20260902T134809Z | Partial | A | No | 5 | 1/1 | 1/1 | B: Codex internal trace unavailable [trace unavailable]; C: Codex internal trace unavailable [trace unavailable] |
| Codex | 4 · run-20260902T135126Z | P | A | No | 5 | 1/1 | 1/1 | C: Codex internal trace unavailable [trace unavailable] |

## microsoft-TypeScript-10473

Configuration diagnostics are emitted only when the diagnostics array is non-empty, and Session separately gates the open-file event, so a config change that clears errors produces no event.

Connected required evidence: **yes**. Required-evidence files: **2**. Implementation-Oracle files: **2**. Required units: P, S, O.

| Unit | Exact pre-resolution source | Required responsibility |
|---|---|---|
| P | `src/server/editorServices.ts:750-770` (`ProjectService.reportConfigFileDiagnostics`) | Suppresses configFileDiag when diagnostics is empty. |
| S | `src/server/session.ts:150-205` (`Session constructor/handleEvent`) | Creates the ProjectService event handler only when events are enabled and routes configFileDiag events. |
| O | `src/server/session.ts:710-730` (`Session.openClientFile`) | Emits the open-file config diagnostic only when configFileErrors is truthy. |

| Condition | Repetition / run ID | P | S | O | Complete? | Final files | Required files represented | Implementation-Oracle files represented | Unit unavailability boundaries |
|---|---|---|---|---|---:|---:|---:|---:|---|
| Full Workspace | 1 · run-20260916T085521Z | P | Partial | P | No | 4 | 2/2 | 2/2 | S: final evidence selection [direct] |
| Full Workspace | 2 · run-20260916T090006Z | P | Partial | A | No | 3 | 2/2 | 2/2 | S: candidate-pool construction [inferred]; O: candidate-pool construction [inferred] |
| Full Workspace | 3 · run-20260916T090329Z | P | Partial | A | No | 3 | 2/2 | 2/2 | S: candidate-pool construction [inferred]; O: final evidence selection [direct] |
| Full Workspace | 4 · run-20260916T090632Z | P | Partial | A | No | 4 | 2/2 | 2/2 | S: candidate-pool construction [inferred]; O: candidate-pool construction [inferred] |
| Without CodeGraph | 1 · run-20260916T053345Z | Partial | A | A | No | 5 | 2/2 | 2/2 | P: candidate-pool construction [inferred]; S: candidate-pool construction [inferred]; O: raw retrieval [inferred] |
| Without CodeGraph | 2 · run-20260916T054440Z | Partial | A | A | No | 5 | 2/2 | 2/2 | P: controller recovery or qualification [inferred]; S: initial comparison [inferred]; O: raw retrieval [inferred] |
| Without CodeGraph | 3 · run-20260916T054732Z | Partial | A | A | No | 4 | 2/2 | 2/2 | P: controller recovery or qualification [inferred]; S: final evidence selection [direct]; O: raw retrieval [inferred] |
| Without CodeGraph | 4 · run-20260916T055019Z | A | A | A | No | 5 | 2/2 | 2/2 | P: candidate-pool construction [inferred]; S: candidate-pool construction [inferred]; O: raw retrieval [inferred] |
| Without controller | 1 · run-20260916T042544Z | P | Partial | A | No | 3 | 2/2 | 2/2 | S: initial comparison [inferred]; O: raw retrieval [inferred] |
| Without controller | 2 · run-20260916T042852Z | P | Partial | A | No | 3 | 2/2 | 2/2 | S: initial comparison [inferred]; O: raw retrieval [inferred] |
| Without controller | 3 · run-20260916T043041Z | P | Partial | A | No | 3 | 2/2 | 2/2 | S: initial comparison [inferred]; O: raw retrieval [inferred] |
| Without controller | 4 · run-20260916T044045Z | P | Partial | A | No | 3 | 2/2 | 2/2 | S: initial comparison [inferred]; O: raw retrieval [inferred] |
| Without either | 1 · run-20260916T022633Z | A | A | A | No | 4 | 2/2 | 2/2 | P: controller recovery or qualification [inferred]; S: initial comparison [inferred]; O: raw retrieval [inferred] |
| Without either | 2 · run-20260916T023626Z | A | A | A | No | 3 | 2/2 | 2/2 | P: controller recovery or qualification [inferred]; S: initial comparison [inferred]; O: raw retrieval [inferred] |
| Without either | 3 · run-20260916T090942Z | A | A | A | No | 4 | 2/2 | 2/2 | P: controller recovery or qualification [inferred]; S: initial comparison [inferred]; O: raw retrieval [inferred] |
| Without either | 4 · run-20260916T091106Z | A | A | A | No | 5 | 2/2 | 2/2 | P: controller recovery or qualification [inferred]; S: controller recovery or qualification [inferred]; O: raw retrieval [inferred] |
| Codex | 1 · run-20260902T135436Z | P | Partial | P | No | 4 | 2/2 | 2/2 | S: Codex internal trace unavailable [trace unavailable] |
| Codex | 2 · run-20260902T135642Z | Partial | Partial | P | No | 4 | 2/2 | 2/2 | P: Codex internal trace unavailable [trace unavailable]; S: Codex internal trace unavailable [trace unavailable] |
| Codex | 3 · run-20260902T135846Z | P | Partial | P | No | 6 | 2/2 | 2/2 | S: Codex internal trace unavailable [trace unavailable] |
| Codex | 4 · run-20260902T140031Z | P | Partial | P | No | 4 | 2/2 | 2/2 | S: Codex internal trace unavailable [trace unavailable] |

## microsoft-TypeScript-16278

The old refactor API exposes applicable refactor names and then requests a whole refactor's code actions, without a distinct selected-action edit request and rename metadata contract.

Connected required evidence: **yes**. Required-evidence files: **6**. Implementation-Oracle files: **8**. Required units: T, P, L, Q, S, C.

| Unit | Exact pre-resolution source | Required responsibility |
|---|---|---|
| T | `src/services/types.ts:255-375` (`LanguageService refactor contracts`) | Defines applicable-refactor and getRefactorCodeActions contracts but no selected-action edit result. |
| P | `src/services/refactorProvider.ts:1-59` (`refactor registry/provider`) | Finds applicable refactors and asks a named provider for code actions. |
| L | `src/services/services.ts:1988-2022` (`LanguageService refactor implementation`) | Adapts the public LanguageService request into provider calls. |
| Q | `src/server/protocol.ts:390-448` (`refactor protocol contracts`) | Defines discovery and whole-refactor code-action requests, with no selected-action edit command. |
| S | `src/server/session.ts:1418-1455` (`Session refactor commands`) | Handles protocol requests and returns the refactor code actions. |
| C | `src/server/client.ts:710-745` (`SessionClient refactor adapter`) | Sends the refactor request and converts returned code actions for the client. |

| Condition | Repetition / run ID | T | P | L | Q | S | C | Complete? | Final files | Required files represented | Implementation-Oracle files represented | Unit unavailability boundaries |
|---|---|---|---|---|---|---|---|---:|---:|---:|---:|---|
| Full Workspace | 1 · run-20260916T085646Z | A | Partial | P | Partial | P | P | No | 6 | 5/6 | 5/8 | T: controller recovery or qualification [inferred]; P: final evidence selection [direct]; Q: final evidence selection [direct] |
| Full Workspace | 2 · run-20260916T090646Z | A | Partial | Partial | P | A | A | No | 5 | 4/6 | 4/8 | T: final evidence selection [direct]; P: final evidence selection [direct]; L: final evidence selection [direct]; S: final evidence selection [direct]; C: final evidence selection [direct] |
| Full Workspace | 3 · run-20260916T091040Z | A | Partial | P | Partial | P | P | No | 6 | 5/6 | 5/8 | T: controller recovery or qualification [inferred]; P: candidate-pool construction [inferred]; Q: candidate-pool construction [inferred] |
| Full Workspace | 4 · run-20260916T091509Z | A | P | P | Partial | P | P | No | 5 | 5/6 | 5/8 | T: controller recovery or qualification [inferred]; Q: final evidence selection [direct] |
| Without CodeGraph | 1 · run-20260916T062310Z | A | P | P | P | A | A | No | 5 | 4/6 | 5/8 | T: controller recovery or qualification [inferred]; S: controller recovery or qualification [inferred]; C: controller recovery or qualification [inferred] |
| Without CodeGraph | 2 · run-20260916T062638Z | A | P | P | Partial | A | P | No | 6 | 5/6 | 5/8 | T: final evidence selection [direct]; Q: final evidence selection [direct]; S: controller recovery or qualification [inferred] |
| Without CodeGraph | 3 · run-20260916T063452Z | A | Partial | P | P | A | P | No | 6 | 4/6 | 5/8 | T: final evidence selection [direct]; P: final evidence selection [direct]; S: controller recovery or qualification [inferred] |
| Without CodeGraph | 4 · run-20260916T063816Z | A | P | P | P | P | A | No | 5 | 4/6 | 5/8 | T: final evidence selection [direct]; C: controller recovery or qualification [inferred] |
| Without controller | 1 · run-20260916T053801Z | A | Partial | A | P | A | P | No | 4 | 3/6 | 3/8 | T: final evidence selection [direct]; P: final evidence selection [direct]; L: final evidence selection [direct]; S: final evidence selection [direct] |
| Without controller | 2 · run-20260916T054206Z | A | Partial | A | Partial | A | A | No | 4 | 2/6 | 3/8 | T: final evidence selection [direct]; P: controller recovery or qualification [inferred]; L: final evidence selection [direct]; Q: controller recovery or qualification [inferred]; S: final evidence selection [direct]; C: final evidence selection [direct] |
| Without controller | 3 · run-20260916T055700Z | A | P | P | Partial | P | P | No | 5 | 5/6 | 5/8 | T: controller recovery or qualification [inferred]; Q: controller recovery or qualification [inferred] |
| Without controller | 4 · run-20260916T055944Z | A | Partial | P | P | P | P | No | 5 | 5/6 | 5/8 | T: controller recovery or qualification [inferred]; P: controller recovery or qualification [inferred] |
| Without either | 1 · run-20260916T023900Z | A | Partial | P | P | A | A | No | 5 | 3/6 | 4/8 | T: final evidence selection [direct]; P: controller recovery or qualification [inferred]; S: controller recovery or qualification [inferred]; C: controller recovery or qualification [inferred] |
| Without either | 2 · run-20260916T024954Z | A | P | P | P | A | P | No | 5 | 5/6 | 5/8 | T: final evidence selection [direct]; S: controller recovery or qualification [inferred] |
| Without either | 3 · run-20260916T030001Z | A | P | P | Partial | A | A | No | 4 | 3/6 | 3/8 | T: final evidence selection [direct]; Q: controller recovery or qualification [inferred]; S: controller recovery or qualification [inferred]; C: controller recovery or qualification [inferred] |
| Without either | 4 · run-20260916T030904Z | A | Partial | P | P | A | P | No | 5 | 4/6 | 4/8 | T: final evidence selection [direct]; P: controller recovery or qualification [inferred]; S: controller recovery or qualification [inferred] |
| Codex | 1 · run-20260902T140217Z | A | P | P | P | P | P | No | 6 | 5/6 | 6/8 | T: Codex internal trace unavailable [trace unavailable] |
| Codex | 2 · run-20260902T140431Z | Partial | P | P | P | P | P | No | 7 | 6/6 | 7/8 | T: Codex internal trace unavailable [trace unavailable] |
| Codex | 3 · run-20260902T140638Z | Partial | P | P | P | P | A | No | 6 | 5/6 | 6/8 | T: Codex internal trace unavailable [trace unavailable]; C: Codex internal trace unavailable [trace unavailable] |
| Codex | 4 · run-20260902T140840Z | Partial | P | A | P | P | P | No | 6 | 5/6 | 6/8 | T: Codex internal trace unavailable [trace unavailable]; L: Codex internal trace unavailable [trace unavailable] |

## microsoft-TypeScript-19074

The change updates stale LSHost terminology in comments without altering runtime behavior.

Connected required evidence: **no**. Required-evidence files: **2**. Implementation-Oracle files: **2**. Required units: M, P.

| Unit | Exact pre-resolution source | Required responsibility |
|---|---|---|
| M | `src/compiler/moduleNameResolver.ts:1484-1494` (`loadModuleFromGlobalCache comment`) | Contains the stale LSHost terminology in the resolver comment. |
| P | `src/server/project.ts:946-960` (`external-file comment`) | Contains the stale LSHost terminology in the project comment. |

| Condition | Repetition / run ID | M | P | Complete? | Final files | Required files represented | Implementation-Oracle files represented | Unit unavailability boundaries |
|---|---|---|---|---:|---:|---:|---:|---|
| Full Workspace | 1 · run-20260916T085745Z | A | A | No | 4 | 0/2 | 0/2 | M: controller recovery or qualification [inferred]; P: controller recovery or qualification [inferred] |
| Full Workspace | 2 · run-20260916T090646Z | A | A | No | 0 | 0/2 | 0/2 | M: candidate-pool construction [inferred]; P: controller recovery or qualification [inferred] |
| Full Workspace | 3 · run-20260916T090935Z | Partial | A | No | 2 | 1/2 | 1/2 | M: final evidence selection [direct]; P: controller recovery or qualification [inferred] |
| Full Workspace | 4 · run-20260916T091426Z | A | A | No | 0 | 0/2 | 0/2 | M: candidate-pool construction [inferred]; P: controller recovery or qualification [inferred] |
| Without CodeGraph | 1 · run-20260916T064145Z | A | A | No | 0 | 0/2 | 0/2 | M: controller recovery or qualification [inferred]; P: initial comparison [inferred] |
| Without CodeGraph | 2 · run-20260916T064247Z | A | A | No | 4 | 0/2 | 0/2 | M: controller recovery or qualification [inferred]; P: controller recovery or qualification [inferred] |
| Without CodeGraph | 3 · run-20260916T064846Z | P | A | No | 4 | 1/2 | 1/2 | P: controller recovery or qualification [inferred] |
| Without CodeGraph | 4 · run-20260916T065152Z | A | A | No | 0 | 0/2 | 0/2 | M: controller recovery or qualification [inferred]; P: controller recovery or qualification [inferred] |
| Without controller | 1 · run-20260916T060455Z | A | A | No | 1 | 0/2 | 0/2 | M: controller recovery or qualification [inferred]; P: initial comparison [inferred] |
| Without controller | 2 · run-20260916T060845Z | A | A | No | 0 | 0/2 | 0/2 | M: controller recovery or qualification [inferred]; P: controller recovery or qualification [inferred] |
| Without controller | 3 · run-20260916T061046Z | A | A | No | 1 | 0/2 | 0/2 | M: controller recovery or qualification [inferred]; P: initial comparison [inferred] |
| Without controller | 4 · run-20260916T061240Z | A | A | No | 0 | 0/2 | 0/2 | M: controller recovery or qualification [inferred]; P: controller recovery or qualification [inferred] |
| Without either | 1 · run-20260916T031409Z | A | A | No | 1 | 0/2 | 0/2 | M: controller recovery or qualification [inferred]; P: initial comparison [inferred] |
| Without either | 2 · run-20260916T031913Z | A | A | No | 1 | 0/2 | 0/2 | M: controller recovery or qualification [inferred]; P: controller recovery or qualification [inferred] |
| Without either | 3 · run-20260916T032032Z | A | A | No | 1 | 0/2 | 0/2 | M: controller recovery or qualification [inferred]; P: initial comparison [inferred] |
| Without either | 4 · run-20260916T032140Z | A | A | No | 1 | 0/2 | 0/2 | M: controller recovery or qualification [inferred]; P: controller recovery or qualification [inferred] |
| Codex | 1 · run-20260902T141017Z | P | P | Yes | 8 | 2/2 | 2/2 | — |
| Codex | 2 · run-20260902T141201Z | P | P | Yes | 7 | 2/2 | 2/2 | — |
| Codex | 3 · run-20260902T141315Z | P | P | Yes | 7 | 2/2 | 2/2 | — |
| Codex | 4 · run-20260902T141439Z | P | P | Yes | 7 | 2/2 | 2/2 | — |

## microsoft-TypeScript-24625

Three watch-builder factory overloads require rootNames and options even though the CreateProgram callback contract can supply undefined values.

Connected required evidence: **no**. Required-evidence files: **1**. Implementation-Oracle files: **1**. Required units: B.

| Unit | Exact pre-resolution source | Required responsibility |
|---|---|---|
| B | `src/compiler/builder.ts:545-577` (`builder factory overloads`) | Shows the required rootNames/options parameters on all three builder factories. |

| Condition | Repetition / run ID | B | Complete? | Final files | Required files represented | Implementation-Oracle files represented | Unit unavailability boundaries |
|---|---|---|---:|---:|---:|---:|---|
| Full Workspace | 1 · run-20260916T025333Z | Partial | No | 3 | 1/1 | 1/1 | B: candidate-pool construction [inferred] |
| Full Workspace | 2 · run-20260916T030235Z | Partial | No | 3 | 1/1 | 1/1 | B: candidate-pool construction [inferred] |
| Full Workspace | 3 · run-20260916T030622Z | Partial | No | 3 | 1/1 | 1/1 | B: candidate-pool construction [inferred] |
| Full Workspace | 4 · run-20260916T031040Z | Partial | No | 3 | 1/1 | 1/1 | B: candidate-pool construction [inferred] |
| Without CodeGraph | 1 · run-20260916T065326Z | Partial | No | 3 | 1/1 | 1/1 | B: controller recovery or qualification [inferred] |
| Without CodeGraph | 2 · run-20260916T065653Z | A | No | 3 | 1/1 | 1/1 | B: controller recovery or qualification [inferred] |
| Without CodeGraph | 3 · run-20260916T065920Z | Partial | No | 5 | 1/1 | 1/1 | B: raw retrieval [inferred] |
| Without CodeGraph | 4 · run-20260916T070314Z | Partial | No | 4 | 1/1 | 1/1 | B: controller recovery or qualification [inferred] |
| Without controller | 1 · run-20260916T061634Z | Partial | No | 4 | 1/1 | 1/1 | B: initial comparison [inferred] |
| Without controller | 2 · run-20260916T062055Z | Partial | No | 4 | 1/1 | 1/1 | B: initial comparison [inferred] |
| Without controller | 3 · run-20260916T063036Z | Partial | No | 3 | 1/1 | 1/1 | B: raw retrieval [inferred] |
| Without controller | 4 · run-20260916T063232Z | Partial | No | 4 | 1/1 | 1/1 | B: initial comparison [inferred] |
| Without either | 1 · run-20260916T033048Z | Partial | No | 3 | 1/1 | 1/1 | B: raw retrieval [inferred] |
| Without either | 2 · run-20260916T033340Z | Partial | No | 3 | 1/1 | 1/1 | B: controller recovery or qualification [inferred] |
| Without either | 3 · run-20260916T033511Z | A | No | 2 | 1/1 | 1/1 | B: controller recovery or qualification [inferred] |
| Without either | 4 · run-20260916T034050Z | Partial | No | 5 | 1/1 | 1/1 | B: raw retrieval [inferred] |
| Codex | 1 · run-20260902T141614Z | Partial | No | 5 | 1/1 | 1/1 | B: Codex internal trace unavailable [trace unavailable] |
| Codex | 2 · run-20260902T141831Z | Partial | No | 5 | 1/1 | 1/1 | B: Codex internal trace unavailable [trace unavailable] |
| Codex | 3 · run-20260902T142022Z | Partial | No | 3 | 1/1 | 1/1 | B: Codex internal trace unavailable [trace unavailable] |
| Codex | 4 · run-20260902T142250Z | Partial | No | 6 | 1/1 | 1/1 | B: Codex internal trace unavailable [trace unavailable] |

## microsoft-TypeScript-35468

Incremental builder state keys dependency, signature, affected-file, and emit maps by sourceFile.path even though project-reference aliases require the canonical resolvedPath identity.

Connected required evidence: **yes**. Required-evidence files: **2**. Implementation-Oracle files: **4**. Required units: I, U, A, E.

| Unit | Exact pre-resolution source | Required responsibility |
|---|---|---|
| I | `src/compiler/builderState.ts:120-235` (`BuilderState.create`) | Builds file information and reference/export maps using sourceFile.path. |
| U | `src/compiler/builderState.ts:304-370` (`updateShapeSignature`) | Reads and updates signature/export caches using sourceFile.path. |
| A | `src/compiler/builderState.ts:405-560` (`affected-file traversal`) | Seeds and deduplicates affected-file traversal with path rather than resolvedPath. |
| E | `src/compiler/builder.ts:315-425` (`builder affected/emit state`) | Uses affectedFile.path for semantic-diagnostic and emit bookkeeping. |

| Condition | Repetition / run ID | I | U | A | E | Complete? | Final files | Required files represented | Implementation-Oracle files represented | Unit unavailability boundaries |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| Full Workspace | 1 · run-20260916T032244Z | A | A | A | Partial | No | 9 | 1/2 | 3/4 | I: raw retrieval [inferred]; U: initial comparison [inferred]; A: candidate-pool construction [inferred]; E: candidate-pool construction [inferred] |
| Full Workspace | 2 · run-20260916T033648Z | A | A | Partial | Partial | No | 6 | 2/2 | 3/4 | I: candidate-pool construction [inferred]; U: candidate-pool construction [inferred]; A: candidate-pool construction [inferred]; E: candidate-pool construction [inferred] |
| Full Workspace | 3 · run-20260916T034302Z | Partial | P | Partial | Partial | No | 5 | 2/2 | 4/4 | I: candidate-pool construction [inferred]; A: candidate-pool construction [inferred]; E: candidate-pool construction [inferred] |
| Full Workspace | 4 · run-20260916T034916Z | A | A | Partial | Partial | No | 7 | 2/2 | 4/4 | I: initial comparison [inferred]; U: initial comparison [inferred]; A: raw retrieval [inferred]; E: candidate-pool construction [inferred] |
| Without CodeGraph | 1 · run-20260916T070719Z | A | A | A | Partial | No | 8 | 1/2 | 2/4 | I: raw retrieval [inferred]; U: initial comparison [inferred]; A: initial comparison [inferred]; E: raw retrieval [inferred] |
| Without CodeGraph | 2 · run-20260916T071043Z | Partial | P | A | A | No | 6 | 2/2 | 3/4 | I: raw retrieval [inferred]; A: controller recovery or qualification [inferred]; E: controller recovery or qualification [inferred] |
| Without CodeGraph | 3 · run-20260916T071449Z | A | A | Partial | A | No | 10 | 2/2 | 3/4 | I: raw retrieval [inferred]; U: controller recovery or qualification [inferred]; A: raw retrieval [inferred]; E: controller recovery or qualification [inferred] |
| Without CodeGraph | 4 · run-20260916T071803Z | Partial | Partial | Partial | A | No | 5 | 1/2 | 2/4 | I: raw retrieval [inferred]; U: controller recovery or qualification [inferred]; A: raw retrieval [inferred]; E: initial comparison [inferred] |
| Without controller | 1 · run-20260916T064452Z | A | A | A | A | No | 7 | 0/2 | 0/4 | I: raw retrieval [inferred]; U: initial comparison [inferred]; A: initial comparison [inferred]; E: initial comparison [inferred] |
| Without controller | 2 · run-20260916T065655Z | A | A | A | Partial | No | 8 | 2/2 | 3/4 | I: raw retrieval [inferred]; U: initial comparison [inferred]; A: initial comparison [inferred]; E: raw retrieval [inferred] |
| Without controller | 3 · run-20260916T065934Z | A | A | A | Partial | No | 7 | 2/2 | 3/4 | I: raw retrieval [inferred]; U: initial comparison [inferred]; A: controller recovery or qualification [inferred]; E: raw retrieval [inferred] |
| Without controller | 4 · run-20260916T070316Z | A | A | Partial | Partial | No | 7 | 2/2 | 3/4 | I: raw retrieval [inferred]; U: initial comparison [inferred]; A: raw retrieval [inferred]; E: raw retrieval [inferred] |
| Without either | 1 · run-20260916T034735Z | A | A | A | A | No | 6 | 1/2 | 2/4 | I: raw retrieval [inferred]; U: controller recovery or qualification [inferred]; A: controller recovery or qualification [inferred]; E: initial comparison [inferred] |
| Without either | 2 · run-20260916T035325Z | A | A | A | Partial | No | 8 | 1/2 | 2/4 | I: initial comparison [inferred]; U: initial comparison [inferred]; A: controller recovery or qualification [inferred]; E: raw retrieval [inferred] |
| Without either | 3 · run-20260916T042239Z | A | A | Partial | Partial | No | 6 | 2/2 | 3/4 | I: raw retrieval [inferred]; U: controller recovery or qualification [inferred]; A: raw retrieval [inferred]; E: raw retrieval [inferred] |
| Without either | 4 · run-20260916T043236Z | A | A | A | Partial | No | 5 | 1/2 | 2/4 | I: initial comparison [inferred]; U: initial comparison [inferred]; A: controller recovery or qualification [inferred]; E: raw retrieval [inferred] |
| Codex | 1 · run-20260902T132352Z | P | P | Partial | Partial | No | 6 | 2/2 | 2/4 | A: Codex internal trace unavailable [trace unavailable]; E: Codex internal trace unavailable [trace unavailable] |
| Codex | 2 · run-20260902T143438Z | P | P | Partial | Partial | No | 8 | 2/2 | 2/4 | A: Codex internal trace unavailable [trace unavailable]; E: Codex internal trace unavailable [trace unavailable] |
| Codex | 3 · run-20260902T143736Z | Partial | P | Partial | Partial | No | 6 | 2/2 | 2/4 | I: Codex internal trace unavailable [trace unavailable]; A: Codex internal trace unavailable [trace unavailable]; E: Codex internal trace unavailable [trace unavailable] |
| Codex | 4 · run-20260902T144021Z | Partial | Partial | Partial | Partial | No | 6 | 2/2 | 2/4 | I: Codex internal trace unavailable [trace unavailable]; U: Codex internal trace unavailable [trace unavailable]; A: Codex internal trace unavailable [trace unavailable]; E: Codex internal trace unavailable [trace unavailable] |

## microsoft-TypeScript-46770

NodeNext package resolution keeps ESM-mode extension rules active while resolving the main field of a CommonJS package, so an extensionless main target is rejected.

Connected required evidence: **no**. Required-evidence files: **1**. Implementation-Oracle files: **1**. Required units: R.

| Unit | Exact pre-resolution source | Required responsibility |
|---|---|---|
| R | `src/compiler/moduleNameResolver.ts:1784-1826` (`loadNodeModuleFromDirectoryWorker`) | Reads package fields and resolves the selected package path with the unchanged NodeNext feature state. |

| Condition | Repetition / run ID | R | Complete? | Final files | Required files represented | Implementation-Oracle files represented | Unit unavailability boundaries |
|---|---|---|---:|---:|---:|---:|---|
| Full Workspace | 1 · run-20260916T035524Z | Partial | No | 8 | 1/1 | 1/1 | R: final evidence selection [direct] |
| Full Workspace | 2 · run-20260916T040401Z | Partial | No | 5 | 1/1 | 1/1 | R: final evidence selection [direct] |
| Full Workspace | 3 · run-20260916T040849Z | A | No | 6 | 1/1 | 1/1 | R: initial comparison [inferred] |
| Full Workspace | 4 · run-20260916T043433Z | Partial | No | 4 | 1/1 | 1/1 | R: candidate-pool construction [inferred] |
| Without CodeGraph | 1 · run-20260916T072126Z | Partial | No | 5 | 1/1 | 1/1 | R: initial comparison [inferred] |
| Without CodeGraph | 2 · run-20260916T072444Z | Partial | No | 8 | 1/1 | 1/1 | R: raw retrieval [inferred] |
| Without CodeGraph | 3 · run-20260916T072957Z | A | No | 8 | 1/1 | 1/1 | R: controller recovery or qualification [inferred] |
| Without CodeGraph | 4 · run-20260916T073351Z | Partial | No | 5 | 1/1 | 1/1 | R: controller recovery or qualification [inferred] |
| Without controller | 1 · run-20260916T070605Z | A | No | 7 | 0/1 | 0/1 | R: initial comparison [inferred] |
| Without controller | 2 · run-20260916T071025Z | Partial | No | 4 | 1/1 | 1/1 | R: final evidence selection [direct] |
| Without controller | 3 · run-20260916T071243Z | Partial | No | 5 | 1/1 | 1/1 | R: controller recovery or qualification [inferred] |
| Without controller | 4 · run-20260916T071454Z | A | No | 7 | 0/1 | 0/1 | R: initial comparison [inferred] |
| Without either | 1 · run-20260916T045448Z | Partial | No | 7 | 1/1 | 1/1 | R: controller recovery or qualification [inferred] |
| Without either | 2 · run-20260916T051304Z | Partial | No | 5 | 1/1 | 1/1 | R: initial comparison [inferred] |
| Without either | 3 · run-20260916T052743Z | A | No | 8 | 1/1 | 1/1 | R: controller recovery or qualification [inferred] |
| Without either | 4 · run-20260916T052959Z | Partial | No | 8 | 1/1 | 1/1 | R: initial comparison [inferred] |
| Codex | 1 · run-20260902T145207Z | P | Yes | 5 | 1/1 | 1/1 | — |
| Codex | 2 · run-20260902T145537Z | P | Yes | 5 | 1/1 | 1/1 | — |
| Codex | 3 · run-20260902T145822Z | Partial | No | 4 | 1/1 | 1/1 | R: Codex internal trace unavailable [trace unavailable] |
| Codex | 4 · run-20260902T150102Z | P | Yes | 7 | 1/1 | 1/1 | — |

## microsoft-TypeScript-52695

Node-module resolution performs file probes for URI-like specifiers and package-root candidates before directory/package handling, producing avoidable filesystem stat calls.

Connected required evidence: **yes**. Required-evidence files: **1**. Implementation-Oracle files: **3**. Required units: N, L.

| Unit | Exact pre-resolution source | Required responsibility |
|---|---|---|
| N | `src/compiler/moduleNameResolver.ts:1706-1820` (`nodeModuleNameResolverWorker`) | Falls through unresolved non-relative names into node_modules lookup without rejecting URI-like names. |
| L | `src/compiler/moduleNameResolver.ts:2868-2910` (`loadModuleFromSpecificNodeModulesDirectory`) | Probes the package-root candidate as a file before loading it as a directory/package. |

| Condition | Repetition / run ID | N | L | Complete? | Final files | Required files represented | Implementation-Oracle files represented | Unit unavailability boundaries |
|---|---|---|---|---:|---:|---:|---:|---|
| Full Workspace | 1 · run-20260916T044511Z | A | P | No | 2 | 1/1 | 1/3 | N: candidate-pool construction [inferred] |
| Full Workspace | 2 · run-20260916T050329Z | P | P | Yes | 6 | 1/1 | 1/3 | — |
| Full Workspace | 3 · run-20260916T050929Z | A | A | No | 5 | 1/1 | 1/3 | N: candidate-pool construction [inferred]; L: candidate-pool construction [inferred] |
| Full Workspace | 4 · run-20260916T052357Z | A | A | No | 5 | 1/1 | 1/3 | N: final evidence selection [direct]; L: final evidence selection [direct] |
| Without CodeGraph | 1 · run-20260916T084338Z | A | A | No | 4 | 1/1 | 1/3 | N: initial comparison [inferred]; L: controller recovery or qualification [inferred] |
| Without CodeGraph | 2 · run-20260916T084811Z | A | A | No | 4 | 1/1 | 1/3 | N: candidate-pool construction [inferred]; L: initial comparison [inferred] |
| Without CodeGraph | 3 · run-20260916T085103Z | A | A | No | 4 | 1/1 | 1/3 | N: initial comparison [inferred]; L: initial comparison [inferred] |
| Without CodeGraph | 4 · run-20260916T085411Z | A | A | No | 3 | 1/1 | 1/3 | N: candidate-pool construction [inferred]; L: controller recovery or qualification [inferred] |
| Without controller | 1 · run-20260916T071724Z | A | A | No | 6 | 1/1 | 1/3 | N: initial comparison [inferred]; L: initial comparison [inferred] |
| Without controller | 2 · run-20260916T072136Z | A | P | No | 4 | 1/1 | 1/3 | N: initial comparison [inferred] |
| Without controller | 3 · run-20260916T072356Z | A | A | No | 4 | 1/1 | 1/3 | N: initial comparison [inferred]; L: raw retrieval [inferred] |
| Without controller | 4 · run-20260916T072611Z | A | A | No | 5 | 1/1 | 1/3 | N: initial comparison [inferred]; L: initial comparison [inferred] |
| Without either | 1 · run-20260916T053210Z | A | A | No | 5 | 1/1 | 1/3 | N: initial comparison [inferred]; L: controller recovery or qualification [inferred] |
| Without either | 2 · run-20260916T055302Z | A | A | No | 5 | 1/1 | 1/3 | N: initial comparison [inferred]; L: initial comparison [inferred] |
| Without either | 3 · run-20260916T055446Z | A | P | No | 4 | 1/1 | 1/3 | N: initial comparison [inferred] |
| Without either | 4 · run-20260916T060229Z | A | A | No | 3 | 1/1 | 1/3 | N: controller recovery or qualification [inferred]; L: controller recovery or qualification [inferred] |
| Codex | 1 · run-20260902T150412Z | P | P | Yes | 4 | 1/1 | 1/3 | — |
| Codex | 2 · run-20260902T150642Z | A | P | No | 5 | 1/1 | 1/3 | N: Codex internal trace unavailable [trace unavailable] |
| Codex | 3 · run-20260902T150850Z | A | P | No | 5 | 1/1 | 1/3 | N: Codex internal trace unavailable [trace unavailable] |
| Codex | 4 · run-20260902T151121Z | A | P | No | 4 | 1/1 | 1/3 | N: Codex internal trace unavailable [trace unavailable] |

## pandas-dev-pandas-10150

The value_counts wrapper delegates to algorithms.value_counts, which converts away the input object's name and constructs the count Series unnamed; index reconstruction then incorrectly applies the original name to the result index.

Connected required evidence: **yes**. Required-evidence files: **2**. Implementation-Oracle files: **2**. Required units: A, B.

| Unit | Exact pre-resolution source | Required responsibility |
|---|---|---|
| A | `pandas/core/algorithms.py:176-255` (`algorithms.value_counts`) | Converts the input to raw values and constructs the result Series without preserving its name. |
| B | `pandas/core/base.py:399-445` (`IndexOpsMixin.value_counts`) | Calls algorithms.value_counts and uses self.name when rebuilding Period/Datetime indexes. |

| Condition | Repetition / run ID | A | B | Complete? | Final files | Required files represented | Implementation-Oracle files represented | Unit unavailability boundaries |
|---|---|---|---|---:|---:|---:|---:|---|
| Full Workspace | 1 · run-20260916T052744Z | P | P | Yes | 4 | 2/2 | 2/2 | — |
| Full Workspace | 2 · run-20260916T053153Z | P | P | Yes | 5 | 2/2 | 2/2 | — |
| Full Workspace | 3 · run-20260916T053456Z | P | P | Yes | 5 | 2/2 | 2/2 | — |
| Full Workspace | 4 · run-20260916T053741Z | P | P | Yes | 5 | 2/2 | 2/2 | — |
| Without CodeGraph | 1 · run-20260916T084338Z | P | P | Yes | 6 | 2/2 | 2/2 | — |
| Without CodeGraph | 2 · run-20260916T084713Z | P | P | Yes | 5 | 2/2 | 2/2 | — |
| Without CodeGraph | 3 · run-20260916T085024Z | P | P | Yes | 6 | 2/2 | 2/2 | — |
| Without CodeGraph | 4 · run-20260916T085344Z | A | P | No | 4 | 1/2 | 1/2 | A: controller recovery or qualification [inferred] |
| Without controller | 1 · run-20260916T070314Z | P | P | Yes | 3 | 2/2 | 2/2 | — |
| Without controller | 2 · run-20260916T070518Z | P | P | Yes | 2 | 2/2 | 2/2 | — |
| Without controller | 3 · run-20260916T070659Z | P | P | Yes | 2 | 2/2 | 2/2 | — |
| Without controller | 4 · run-20260916T070838Z | P | P | Yes | 2 | 2/2 | 2/2 | — |
| Without either | 1 · run-20260916T060836Z | Partial | P | No | 2 | 2/2 | 2/2 | A: controller recovery or qualification [inferred] |
| Without either | 2 · run-20260916T061015Z | A | P | No | 2 | 1/2 | 1/2 | A: controller recovery or qualification [inferred] |
| Without either | 3 · run-20260916T061132Z | A | P | No | 3 | 1/2 | 1/2 | A: controller recovery or qualification [inferred] |
| Without either | 4 · run-20260916T061250Z | Partial | P | No | 3 | 2/2 | 2/2 | A: controller recovery or qualification [inferred] |
| Codex | 1 · run-20260902T152222Z | P | P | Yes | 4 | 2/2 | 2/2 | — |
| Codex | 2 · run-20260902T152415Z | P | P | Yes | 5 | 2/2 | 2/2 | — |
| Codex | 3 · run-20260902T152646Z | P | P | Yes | 5 | 2/2 | 2/2 | — |
| Codex | 4 · run-20260902T152831Z | P | P | Yes | 4 | 2/2 | 2/2 | — |

## pandas-dev-pandas-16499

Pytest cannot collect the ujson test groups because their class names do not begin with Test.

Connected required evidence: **no**. Required-evidence files: **1**. Implementation-Oracle files: **1**. Required units: U, N, P.

| Unit | Exact pre-resolution source | Required responsibility |
|---|---|---|
| U | `pandas/tests/io/json/test_ujson.py:25-45` (`UltraJSONTests`) | Defines the first uncollectable test class. |
| N | `pandas/tests/io/json/test_ujson.py:940-965` (`NumpyJSONTests`) | Defines the NumPy ujson tests under an uncollectable class name. |
| P | `pandas/tests/io/json/test_ujson.py:1218-1240` (`PandasJSONTests`) | Defines the pandas-object ujson tests under an uncollectable class name. |

| Condition | Repetition / run ID | U | N | P | Complete? | Final files | Required files represented | Implementation-Oracle files represented | Unit unavailability boundaries |
|---|---|---|---|---|---:|---:|---:|---:|---|
| Full Workspace | 1 · run-20260916T054102Z | P | P | P | Yes | 1 | 1/1 | 1/1 | — |
| Full Workspace | 2 · run-20260916T054447Z | P | P | P | Yes | 1 | 1/1 | 1/1 | — |
| Full Workspace | 3 · run-20260916T054751Z | P | P | P | Yes | 3 | 1/1 | 1/1 | — |
| Full Workspace | 4 · run-20260916T055041Z | P | P | P | Yes | 1 | 1/1 | 1/1 | — |
| Without CodeGraph | 1 · run-20260916T085606Z | Partial | A | A | No | 1 | 1/1 | 1/1 | U: candidate-pool construction [inferred]; N: final evidence selection [direct]; P: candidate-pool construction [inferred] |
| Without CodeGraph | 2 · run-20260916T085743Z | Partial | A | A | No | 2 | 1/1 | 1/1 | U: controller recovery or qualification [inferred]; N: candidate-pool construction [inferred]; P: controller recovery or qualification [inferred] |
| Without CodeGraph | 3 · run-20260916T085905Z | Partial | A | A | No | 1 | 1/1 | 1/1 | U: candidate-pool construction [inferred]; N: final evidence selection [direct]; P: candidate-pool construction [inferred] |
| Without CodeGraph | 4 · run-20260916T090037Z | Partial | A | A | No | 1 | 1/1 | 1/1 | U: controller recovery or qualification [inferred]; N: candidate-pool construction [inferred]; P: candidate-pool construction [inferred] |
| Without controller | 1 · run-20260916T071013Z | P | A | A | No | 1 | 1/1 | 1/1 | N: controller recovery or qualification [inferred]; P: controller recovery or qualification [inferred] |
| Without controller | 2 · run-20260916T071137Z | P | P | P | Yes | 1 | 1/1 | 1/1 | — |
| Without controller | 3 · run-20260916T071304Z | P | A | P | No | 1 | 1/1 | 1/1 | N: controller recovery or qualification [inferred] |
| Without controller | 4 · run-20260916T071426Z | P | P | P | Yes | 1 | 1/1 | 1/1 | — |
| Without either | 1 · run-20260916T061431Z | Partial | A | A | No | 1 | 1/1 | 1/1 | U: controller recovery or qualification [inferred]; N: controller recovery or qualification [inferred]; P: controller recovery or qualification [inferred] |
| Without either | 2 · run-20260916T061542Z | Partial | A | A | No | 1 | 1/1 | 1/1 | U: controller recovery or qualification [inferred]; N: controller recovery or qualification [inferred]; P: controller recovery or qualification [inferred] |
| Without either | 3 · run-20260916T061656Z | Partial | A | A | No | 1 | 1/1 | 1/1 | U: controller recovery or qualification [inferred]; N: controller recovery or qualification [inferred]; P: controller recovery or qualification [inferred] |
| Without either | 4 · run-20260916T061808Z | Partial | A | A | No | 1 | 1/1 | 1/1 | U: controller recovery or qualification [inferred]; N: controller recovery or qualification [inferred]; P: controller recovery or qualification [inferred] |
| Codex | 1 · run-20260902T154136Z | P | P | P | Yes | 2 | 1/1 | 1/1 | — |
| Codex | 2 · run-20260902T154250Z | P | P | P | Yes | 4 | 1/1 | 1/1 | — |
| Codex | 3 · run-20260902T154416Z | P | P | P | Yes | 2 | 1/1 | 1/1 | — |
| Codex | 4 · run-20260902T154527Z | P | P | P | Yes | 2 | 1/1 | 1/1 | — |

## pandas-dev-pandas-22698

Index comparison deliberately records and suppresses NumPy's invalid-elementwise-comparison FutureWarning before returning the comparison result.

Connected required evidence: **no**. Required-evidence files: **1**. Implementation-Oracle files: **1**. Required units: C.

| Unit | Exact pre-resolution source | Required responsibility |
|---|---|---|
| C | `pandas/core/indexes/base.py:60-95` (`Index comparison cmp_method`) | Wraps the NumPy comparison in a warning-catching block that ignores FutureWarning. |

| Condition | Repetition / run ID | C | Complete? | Final files | Required files represented | Implementation-Oracle files represented | Unit unavailability boundaries |
|---|---|---|---:|---:|---:|---:|---|
| Full Workspace | 1 · run-20260916T055334Z | A | No | 3 | 0/1 | 0/1 | C: raw retrieval [inferred] |
| Full Workspace | 2 · run-20260916T055753Z | A | No | 3 | 0/1 | 0/1 | C: candidate-pool construction [inferred] |
| Full Workspace | 3 · run-20260916T060203Z | A | No | 1 | 0/1 | 0/1 | C: raw retrieval [inferred] |
| Full Workspace | 4 · run-20260916T060354Z | A | No | 5 | 0/1 | 0/1 | C: raw retrieval [inferred] |
| Without CodeGraph | 1 · run-20260916T085745Z | A | No | 4 | 0/1 | 0/1 | C: raw retrieval [inferred] |
| Without CodeGraph | 2 · run-20260916T090147Z | A | No | 4 | 0/1 | 0/1 | C: raw retrieval [inferred] |
| Without CodeGraph | 3 · run-20260916T090519Z | A | No | 4 | 0/1 | 0/1 | C: raw retrieval [inferred] |
| Without CodeGraph | 4 · run-20260916T090855Z | A | No | 1 | 0/1 | 0/1 | C: raw retrieval [inferred] |
| Without controller | 1 · run-20260916T071549Z | A | No | 3 | 0/1 | 0/1 | C: initial comparison [inferred] |
| Without controller | 2 · run-20260916T071752Z | A | No | 1 | 0/1 | 0/1 | C: raw retrieval [inferred] |
| Without controller | 3 · run-20260916T071947Z | A | No | 2 | 0/1 | 0/1 | C: raw retrieval [inferred] |
| Without controller | 4 · run-20260916T072124Z | A | No | 3 | 0/1 | 0/1 | C: raw retrieval [inferred] |
| Without either | 1 · run-20260916T061925Z | A | No | 2 | 0/1 | 0/1 | C: raw retrieval [inferred] |
| Without either | 2 · run-20260916T062053Z | A | No | 1 | 0/1 | 0/1 | C: raw retrieval [inferred] |
| Without either | 3 · run-20260916T063242Z | A | No | 2 | 0/1 | 0/1 | C: raw retrieval [inferred] |
| Without either | 4 · run-20260916T063853Z | A | No | 2 | 0/1 | 0/1 | C: raw retrieval [inferred] |
| Codex | 1 · run-20260902T155601Z | A | No | 4 | 0/1 | 0/1 | C: Codex internal trace unavailable [trace unavailable] |
| Codex | 2 · run-20260902T155754Z | A | No | 5 | 0/1 | 0/1 | C: Codex internal trace unavailable [trace unavailable] |
| Codex | 3 · run-20260902T160001Z | A | No | 4 | 0/1 | 0/1 | C: Codex internal trace unavailable [trace unavailable] |
| Codex | 4 · run-20260902T160157Z | A | No | 3 | 0/1 | 0/1 | C: Codex internal trace unavailable [trace unavailable] |

## pandas-dev-pandas-22872

Both repository lint configurations explicitly ignore E722, permitting bare except clauses in the test suite.

Connected required evidence: **no**. Required-evidence files: **2**. Implementation-Oracle files: **2**. Required units: S, P.

| Unit | Exact pre-resolution source | Required responsibility |
|---|---|---|
| S | `setup.cfg:10-25` (`pycodestyle ignore list`) | Disables E722 for the repository lint configuration. |
| P | `.pep8speaks.yml:8-20` (`pep8speaks ignore list`) | Disables E722 for the review-bot lint configuration. |

| Condition | Repetition / run ID | S | P | Complete? | Final files | Required files represented | Implementation-Oracle files represented | Unit unavailability boundaries |
|---|---|---|---|---:|---:|---:|---:|---|
| Full Workspace | 1 · run-20260916T062153Z | A | A | No | 3 | 0/2 | 0/2 | S: raw retrieval [inferred]; P: initial comparison [inferred] |
| Full Workspace | 2 · run-20260916T062521Z | A | A | No | 1 | 0/2 | 0/2 | S: raw retrieval [inferred]; P: initial comparison [inferred] |
| Full Workspace | 3 · run-20260916T062711Z | A | A | No | 0 | 0/2 | 0/2 | S: raw retrieval [inferred]; P: initial comparison [inferred] |
| Full Workspace | 4 · run-20260916T062913Z | A | A | No | 3 | 0/2 | 0/2 | S: raw retrieval [inferred]; P: raw retrieval [inferred] |
| Without CodeGraph | 1 · run-20260916T022633Z | A | A | No | 3 | 0/2 | 0/2 | S: raw retrieval [inferred]; P: initial comparison [inferred] |
| Without CodeGraph | 2 · run-20260916T090153Z | A | A | No | 2 | 0/2 | 0/2 | S: raw retrieval [inferred]; P: initial comparison [inferred] |
| Without CodeGraph | 3 · run-20260916T090646Z | A | A | No | 2 | 0/2 | 0/2 | S: raw retrieval [inferred]; P: initial comparison [inferred] |
| Without CodeGraph | 4 · run-20260916T090936Z | A | A | No | 2 | 0/2 | 0/2 | S: raw retrieval [inferred]; P: initial comparison [inferred] |
| Without controller | 1 · run-20260916T072258Z | A | A | No | 1 | 0/2 | 0/2 | S: raw retrieval [inferred]; P: raw retrieval [inferred] |
| Without controller | 2 · run-20260916T072455Z | A | A | No | 4 | 0/2 | 0/2 | S: raw retrieval [inferred]; P: raw retrieval [inferred] |
| Without controller | 3 · run-20260916T072712Z | A | A | No | 5 | 0/2 | 0/2 | S: raw retrieval [inferred]; P: raw retrieval [inferred] |
| Without controller | 4 · run-20260916T072848Z | A | A | No | 6 | 0/2 | 0/2 | S: raw retrieval [inferred]; P: raw retrieval [inferred] |
| Without either | 1 · run-20260916T065651Z | A | A | No | 5 | 0/2 | 0/2 | S: raw retrieval [inferred]; P: raw retrieval [inferred] |
| Without either | 2 · run-20260916T065840Z | A | A | No | 5 | 0/2 | 0/2 | S: raw retrieval [inferred]; P: initial comparison [inferred] |
| Without either | 3 · run-20260916T070034Z | A | A | No | 3 | 0/2 | 0/2 | S: raw retrieval [inferred]; P: raw retrieval [inferred] |
| Without either | 4 · run-20260916T070427Z | A | A | No | 1 | 0/2 | 0/2 | S: raw retrieval [inferred]; P: raw retrieval [inferred] |
| Codex | 1 · run-20260902T160337Z | A | A | No | 8 | 0/2 | 0/2 | S: Codex internal trace unavailable [trace unavailable]; P: Codex internal trace unavailable [trace unavailable] |
| Codex | 2 · run-20260902T160553Z | A | A | No | 8 | 0/2 | 0/2 | S: Codex internal trace unavailable [trace unavailable]; P: Codex internal trace unavailable [trace unavailable] |
| Codex | 3 · run-20260902T160737Z | A | A | No | 8 | 0/2 | 0/2 | S: Codex internal trace unavailable [trace unavailable]; P: Codex internal trace unavailable [trace unavailable] |
| Codex | 4 · run-20260902T160958Z | A | A | No | 8 | 0/2 | 0/2 | S: Codex internal trace unavailable [trace unavailable]; P: Codex internal trace unavailable [trace unavailable] |

## pandas-dev-pandas-25183

Concat reindexing treats an all-missing extension block like a NumPy block and replaces it with an array of the common empty dtype, losing the nullable Int64 extension dtype during merge.

Connected required evidence: **no**. Required-evidence files: **1**. Implementation-Oracle files: **1**. Required units: J.

| Unit | Exact pre-resolution source | Required responsibility |
|---|---|---|
| J | `pandas/core/internals/concat.py:165-215` (`JoinUnit.get_reindexed_values`) | Shows the missing-value branch and its NumPy replacement array, without an extension-block exemption. |

| Condition | Repetition / run ID | J | Complete? | Final files | Required files represented | Implementation-Oracle files represented | Unit unavailability boundaries |
|---|---|---|---:|---:|---:|---:|---|
| Full Workspace | 1 · run-20260916T063404Z | A | No | 4 | 0/1 | 0/1 | J: raw retrieval [inferred] |
| Full Workspace | 2 · run-20260916T064133Z | A | No | 2 | 0/1 | 0/1 | J: raw retrieval [inferred] |
| Full Workspace | 3 · run-20260916T064430Z | A | No | 3 | 0/1 | 0/1 | J: raw retrieval [inferred] |
| Full Workspace | 4 · run-20260916T064808Z | A | No | 2 | 0/1 | 0/1 | J: raw retrieval [inferred] |
| Without CodeGraph | 1 · run-20260916T023343Z | A | No | 3 | 0/1 | 0/1 | J: raw retrieval [inferred] |
| Without CodeGraph | 2 · run-20260916T024104Z | A | No | 3 | 0/1 | 0/1 | J: raw retrieval [inferred] |
| Without CodeGraph | 3 · run-20260916T024434Z | A | No | 2 | 0/1 | 0/1 | J: controller recovery or qualification [inferred] |
| Without CodeGraph | 4 · run-20260916T024749Z | A | No | 2 | 0/1 | 0/1 | J: raw retrieval [inferred] |
| Without controller | 1 · run-20260916T073114Z | A | No | 2 | 0/1 | 0/1 | J: raw retrieval [inferred] |
| Without controller | 2 · run-20260916T073235Z | A | No | 2 | 0/1 | 0/1 | J: initial comparison [inferred] |
| Without controller | 3 · run-20260916T073527Z | A | No | 2 | 0/1 | 0/1 | J: raw retrieval [inferred] |
| Without controller | 4 · run-20260916T073627Z | A | No | 2 | 0/1 | 0/1 | J: raw retrieval [inferred] |
| Without either | 1 · run-20260916T070614Z | A | No | 3 | 0/1 | 0/1 | J: controller recovery or qualification [inferred] |
| Without either | 2 · run-20260916T070742Z | A | No | 3 | 0/1 | 0/1 | J: raw retrieval [inferred] |
| Without either | 3 · run-20260916T070907Z | A | No | 2 | 0/1 | 0/1 | J: controller recovery or qualification [inferred] |
| Without either | 4 · run-20260916T071040Z | A | No | 2 | 0/1 | 0/1 | J: raw retrieval [inferred] |
| Codex | 1 · run-20260902T161142Z | P | Yes | 6 | 1/1 | 1/1 | — |
| Codex | 2 · run-20260902T161425Z | A | No | 6 | 1/1 | 1/1 | J: Codex internal trace unavailable [trace unavailable] |
| Codex | 3 · run-20260902T161634Z | P | Yes | 8 | 1/1 | 1/1 | — |
| Codex | 4 · run-20260902T161908Z | A | No | 7 | 1/1 | 1/1 | J: Codex internal trace unavailable [trace unavailable] |

## pandas-dev-pandas-32289

DataFrame construction converts each nested value with np.asarray, then rejects non-two-dimensional results with a generic error that omits the observed shape.

Connected required evidence: **no**. Required-evidence files: **1**. Implementation-Oracle files: **1**. Required units: C.

| Unit | Exact pre-resolution source | Required responsibility |
|---|---|---|
| C | `pandas/core/internals/construction.py:290-328` (`to_arrays.convert`) | Converts list elements and raises the generic dimensionality error. |

| Condition | Repetition / run ID | C | Complete? | Final files | Required files represented | Implementation-Oracle files represented | Unit unavailability boundaries |
|---|---|---|---:|---:|---:|---:|---|
| Full Workspace | 1 · run-20260916T065036Z | A | No | 2 | 0/1 | 0/1 | C: raw retrieval [inferred] |
| Full Workspace | 2 · run-20260916T065335Z | A | No | 3 | 1/1 | 1/1 | C: candidate-pool construction [inferred] |
| Full Workspace | 3 · run-20260916T065651Z | A | No | 1 | 0/1 | 0/1 | C: raw retrieval [inferred] |
| Full Workspace | 4 · run-20260916T065845Z | A | No | 1 | 0/1 | 0/1 | C: raw retrieval [inferred] |
| Without CodeGraph | 1 · run-20260916T025119Z | A | No | 1 | 0/1 | 0/1 | C: raw retrieval [inferred] |
| Without CodeGraph | 2 · run-20260916T025735Z | A | No | 3 | 0/1 | 0/1 | C: raw retrieval [inferred] |
| Without CodeGraph | 3 · run-20260916T025941Z | A | No | 2 | 0/1 | 0/1 | C: raw retrieval [inferred] |
| Without CodeGraph | 4 · run-20260916T030117Z | A | No | 1 | 0/1 | 0/1 | C: raw retrieval [inferred] |
| Without controller | 1 · run-20260916T073736Z | A | No | 1 | 0/1 | 0/1 | C: raw retrieval [inferred] |
| Without controller | 2 · run-20260916T073851Z | A | No | 0 | 0/1 | 0/1 | C: raw retrieval [inferred] |
| Without controller | 3 · run-20260916T073957Z | A | No | 1 | 0/1 | 0/1 | C: raw retrieval [inferred] |
| Without controller | 4 · run-20260916T074114Z | A | No | 3 | 0/1 | 0/1 | C: raw retrieval [inferred] |
| Without either | 1 · run-20260916T071214Z | A | No | 1 | 0/1 | 0/1 | C: raw retrieval [inferred] |
| Without either | 2 · run-20260916T071312Z | A | No | 4 | 0/1 | 0/1 | C: raw retrieval [inferred] |
| Without either | 3 · run-20260916T071439Z | A | No | 1 | 0/1 | 0/1 | C: raw retrieval [inferred] |
| Without either | 4 · run-20260916T071541Z | A | No | 1 | 0/1 | 0/1 | C: raw retrieval [inferred] |
| Codex | 1 · run-20260902T162153Z | P | Yes | 5 | 1/1 | 1/1 | — |
| Codex | 2 · run-20260902T162348Z | P | Yes | 5 | 1/1 | 1/1 | — |
| Codex | 3 · run-20260902T162558Z | P | Yes | 4 | 1/1 | 1/1 | — |
| Codex | 4 · run-20260902T162810Z | P | Yes | 4 | 1/1 | 1/1 | — |

## pandas-dev-pandas-35925

The repository pins Black 19.10b0; updating the formatter changes accepted trailing-comma formatting across many otherwise unrelated files.

Connected required evidence: **no**. Required-evidence files: **1**. Implementation-Oracle files: **13**. Required units: B.

| Unit | Exact pre-resolution source | Required responsibility |
|---|---|---|
| B | `.pre-commit-config.yaml:1-7` (`Black pre-commit hook`) | Pins the formatter version that motivates the mechanical source rewrite. |

| Condition | Repetition / run ID | B | Complete? | Final files | Required files represented | Implementation-Oracle files represented | Unit unavailability boundaries |
|---|---|---|---:|---:|---:|---:|---|
| Full Workspace | 1 · run-20260916T070315Z | A | No | 1 | 0/1 | 1/13 | B: raw retrieval [inferred] |
| Full Workspace | 2 · run-20260916T070438Z | A | No | 1 | 0/1 | 1/13 | B: raw retrieval [inferred] |
| Full Workspace | 3 · run-20260916T070618Z | A | No | 1 | 0/1 | 1/13 | B: raw retrieval [inferred] |
| Full Workspace | 4 · run-20260916T070821Z | A | No | 1 | 0/1 | 1/13 | B: candidate-pool construction [inferred] |
| Without CodeGraph | 1 · run-20260916T030343Z | A | No | 2 | 0/1 | 1/13 | B: raw retrieval [inferred] |
| Without CodeGraph | 2 · run-20260916T030827Z | A | No | 2 | 0/1 | 1/13 | B: raw retrieval [inferred] |
| Without CodeGraph | 3 · run-20260916T031023Z | A | No | 1 | 0/1 | 1/13 | B: raw retrieval [inferred] |
| Without CodeGraph | 4 · run-20260916T031454Z | A | No | 1 | 0/1 | 1/13 | B: raw retrieval [inferred] |
| Without controller | 1 · run-20260916T084338Z | A | No | 1 | 0/1 | 1/13 | B: raw retrieval [inferred] |
| Without controller | 2 · run-20260916T084442Z | A | No | 1 | 0/1 | 1/13 | B: raw retrieval [inferred] |
| Without controller | 3 · run-20260916T084539Z | A | No | 1 | 0/1 | 1/13 | B: raw retrieval [inferred] |
| Without controller | 4 · run-20260916T084631Z | A | No | 1 | 0/1 | 1/13 | B: raw retrieval [inferred] |
| Without either | 1 · run-20260916T071649Z | A | No | 1 | 0/1 | 1/13 | B: raw retrieval [inferred] |
| Without either | 2 · run-20260916T071734Z | A | No | 1 | 0/1 | 1/13 | B: raw retrieval [inferred] |
| Without either | 3 · run-20260916T071834Z | A | No | 1 | 0/1 | 1/13 | B: raw retrieval [inferred] |
| Without either | 4 · run-20260916T071919Z | A | No | 1 | 0/1 | 1/13 | B: raw retrieval [inferred] |
| Codex | 1 · run-20260902T162949Z | P | Yes | 3 | 1/1 | 2/13 | — |
| Codex | 2 · run-20260902T163053Z | P | Yes | 4 | 1/1 | 2/13 | — |
| Codex | 3 · run-20260902T163207Z | P | Yes | 4 | 1/1 | 2/13 | — |
| Codex | 4 · run-20260902T163327Z | P | Yes | 8 | 1/1 | 3/13 | — |

## pandas-dev-pandas-36617

The rst-backticks hook excludes a named set of documentation files, leaving their single-backtick markup outside automated enforcement.

Connected required evidence: **no**. Required-evidence files: **1**. Implementation-Oracle files: **1**. Required units: R.

| Unit | Exact pre-resolution source | Required responsibility |
|---|---|---|
| R | `.pre-commit-config.yaml:33-53` (`rst-backticks hook`) | Shows the documentation hook and its explicit exclusion list. |

| Condition | Repetition / run ID | R | Complete? | Final files | Required files represented | Implementation-Oracle files represented | Unit unavailability boundaries |
|---|---|---|---:|---:|---:|---:|---|
| Full Workspace | 1 · run-20260916T071034Z | P | Yes | 2 | 1/1 | 1/1 | — |
| Full Workspace | 2 · run-20260916T071650Z | A | No | 2 | 0/1 | 0/1 | R: controller recovery or qualification [inferred] |
| Full Workspace | 3 · run-20260916T072403Z | P | Yes | 1 | 1/1 | 1/1 | — |
| Full Workspace | 4 · run-20260916T072554Z | P | Yes | 1 | 1/1 | 1/1 | — |
| Without CodeGraph | 1 · run-20260916T031613Z | P | Yes | 2 | 1/1 | 1/1 | — |
| Without CodeGraph | 2 · run-20260916T031845Z | P | Yes | 1 | 1/1 | 1/1 | — |
| Without CodeGraph | 3 · run-20260916T032050Z | P | Yes | 1 | 1/1 | 1/1 | — |
| Without CodeGraph | 4 · run-20260916T032225Z | A | No | 3 | 0/1 | 0/1 | R: candidate-pool construction [inferred] |
| Without controller | 1 · run-20260916T084729Z | P | Yes | 1 | 1/1 | 1/1 | — |
| Without controller | 2 · run-20260916T085005Z | P | Yes | 1 | 1/1 | 1/1 | — |
| Without controller | 3 · run-20260916T085119Z | P | Yes | 1 | 1/1 | 1/1 | — |
| Without controller | 4 · run-20260916T085229Z | P | Yes | 1 | 1/1 | 1/1 | — |
| Without either | 1 · run-20260916T072005Z | P | Yes | 1 | 1/1 | 1/1 | — |
| Without either | 2 · run-20260916T072053Z | A | No | 1 | 0/1 | 0/1 | R: controller recovery or qualification [inferred] |
| Without either | 3 · run-20260916T072146Z | P | Yes | 1 | 1/1 | 1/1 | — |
| Without either | 4 · run-20260916T072253Z | A | No | 2 | 0/1 | 0/1 | R: controller recovery or qualification [inferred] |
| Codex | 1 · run-20260902T163455Z | P | Yes | 14 | 1/1 | 1/1 | — |
| Codex | 2 · run-20260902T163747Z | P | Yes | 13 | 1/1 | 1/1 | — |
| Codex | 3 · run-20260902T164020Z | P | Yes | 13 | 1/1 | 1/1 | — |
| Codex | 4 · run-20260902T164307Z | P | Yes | 15 | 1/1 | 1/1 | — |

## vuejs-vue-10004

DOM listeners are reconciled on create/update only; destroying a deactivated component has no hook that reuses the old element to remove stale v-model listeners.

Connected required evidence: **no**. Required-evidence files: **1**. Implementation-Oracle files: **1**. Required units: E.

| Unit | Exact pre-resolution source | Required responsibility |
|---|---|---|
| E | `src/platforms/web/runtime/modules/events.js:100-120` (`updateDOMListeners/module hooks`) | Targets vnode.elm and exports only create/update hooks, leaving no destroy cleanup path. |

| Condition | Repetition / run ID | E | Complete? | Final files | Required files represented | Implementation-Oracle files represented | Unit unavailability boundaries |
|---|---|---|---:|---:|---:|---:|---|
| Full Workspace | 1 · run-20260916T090733Z | A | No | 10 | 0/1 | 0/1 | E: raw retrieval [inferred] |
| Full Workspace | 2 · run-20260916T091550Z | A | No | 7 | 0/1 | 0/1 | E: raw retrieval [inferred] |
| Full Workspace | 3 · run-20260916T094954Z | A | No | 8 | 0/1 | 0/1 | E: raw retrieval [inferred] |
| Full Workspace | 4 · run-20260916T101717Z | A | No | 12 | 0/1 | 0/1 | E: raw retrieval [inferred] |
| Without CodeGraph | 1 · run-20260916T091943Z | A | No | 9 | 0/1 | 0/1 | E: raw retrieval [inferred] |
| Without CodeGraph | 2 · run-20260916T092418Z | A | No | 5 | 0/1 | 0/1 | E: raw retrieval [inferred] |
| Without CodeGraph | 3 · run-20260916T093127Z | A | No | 5 | 0/1 | 0/1 | E: raw retrieval [inferred] |
| Without CodeGraph | 4 · run-20260916T094323Z | A | No | 7 | 0/1 | 0/1 | E: raw retrieval [inferred] |
| Without controller | 1 · run-20260916T090432Z | A | No | 6 | 0/1 | 0/1 | E: raw retrieval [inferred] |
| Without controller | 2 · run-20260916T093609Z | A | No | 6 | 0/1 | 0/1 | E: raw retrieval [inferred] |
| Without controller | 3 · run-20260916T093833Z | A | No | 8 | 0/1 | 0/1 | E: raw retrieval [inferred] |
| Without controller | 4 · run-20260916T094054Z | A | No | 7 | 0/1 | 0/1 | E: raw retrieval [inferred] |
| Without either | 1 · run-20260916T091220Z | A | No | 4 | 1/1 | 1/1 | E: raw retrieval [inferred] |
| Without either | 2 · run-20260916T091404Z | A | No | 4 | 0/1 | 0/1 | E: raw retrieval [inferred] |
| Without either | 3 · run-20260916T092927Z | A | No | 7 | 1/1 | 1/1 | E: raw retrieval [inferred] |
| Without either | 4 · run-20260916T094734Z | A | No | 6 | 0/1 | 0/1 | E: raw retrieval [inferred] |
| Codex | 1 · run-20260902T165354Z | Partial | No | 11 | 1/1 | 1/1 | E: Codex internal trace unavailable [trace unavailable] |
| Codex | 2 · run-20260902T165614Z | P | Yes | 16 | 1/1 | 1/1 | — |
| Codex | 3 · run-20260902T165836Z | Partial | No | 13 | 1/1 | 1/1 | E: Codex internal trace unavailable [trace unavailable] |
| Codex | 4 · run-20260902T170109Z | P | Yes | 14 | 1/1 | 1/1 | — |

## vuejs-vue-11718

The SSR webpack plugins assume webpack 4's emit hook, string entry assets, space-suffixed module hashes, and the legacy libraryTarget shape.

Connected required evidence: **yes**. Required-evidence files: **3**. Implementation-Oracle files: **3**. Required units: U, C, S.

| Unit | Exact pre-resolution source | Required responsibility |
|---|---|---|
| U | `src/server/webpack-plugin/util.js:1-34` (`validate/onEmit`) | Validates legacy output.libraryTarget and selects only legacy or webpack-4 emit hooks. |
| C | `src/server/webpack-plugin/client.js:1-55` (`VueSSRClientPlugin.apply`) | Passes webpack stats assets/module identifiers through string-only assumptions. |
| S | `src/server/webpack-plugin/server.js:1-60` (`VueSSRServerPlugin.apply`) | Filters entry assets and consumes stats.assets under webpack-4 shapes. |

| Condition | Repetition / run ID | U | C | S | Complete? | Final files | Required files represented | Implementation-Oracle files represented | Unit unavailability boundaries |
|---|---|---|---|---|---:|---:|---:|---:|---|
| Full Workspace | 1 · run-20260916T070502Z | Partial | A | P | No | 3 | 2/3 | 2/3 | U: candidate-pool construction [inferred]; C: controller recovery or qualification [inferred] |
| Full Workspace | 2 · run-20260916T070802Z | Partial | A | A | No | 2 | 1/3 | 1/3 | U: final evidence selection [direct]; C: controller recovery or qualification [inferred]; S: controller recovery or qualification [inferred] |
| Full Workspace | 3 · run-20260916T071018Z | Partial | A | P | No | 4 | 2/3 | 2/3 | U: final evidence selection [direct]; C: controller recovery or qualification [inferred] |
| Full Workspace | 4 · run-20260916T071314Z | Partial | A | A | No | 2 | 1/3 | 1/3 | U: final evidence selection [direct]; C: controller recovery or qualification [inferred]; S: controller recovery or qualification [inferred] |
| Without CodeGraph | 1 · run-20260916T033518Z | P | A | A | No | 2 | 1/3 | 1/3 | C: controller recovery or qualification [inferred]; S: controller recovery or qualification [inferred] |
| Without CodeGraph | 2 · run-20260916T033720Z | P | A | Partial | No | 6 | 2/3 | 2/3 | C: candidate-pool construction [inferred]; S: candidate-pool construction [inferred] |
| Without CodeGraph | 3 · run-20260916T033940Z | P | A | Partial | No | 3 | 2/3 | 2/3 | C: controller recovery or qualification [inferred]; S: candidate-pool construction [inferred] |
| Without CodeGraph | 4 · run-20260916T034153Z | P | A | Partial | No | 2 | 2/3 | 2/3 | C: controller recovery or qualification [inferred]; S: candidate-pool construction [inferred] |
| Without controller | 1 · run-20260916T022736Z | Partial | A | A | No | 3 | 1/3 | 1/3 | U: controller recovery or qualification [inferred]; C: controller recovery or qualification [inferred]; S: final evidence selection [direct] |
| Without controller | 2 · run-20260916T023115Z | P | A | A | No | 2 | 1/3 | 1/3 | C: controller recovery or qualification [inferred]; S: controller recovery or qualification [inferred] |
| Without controller | 3 · run-20260916T023335Z | P | A | P | No | 3 | 2/3 | 2/3 | C: controller recovery or qualification [inferred] |
| Without controller | 4 · run-20260916T023559Z | Partial | A | A | No | 2 | 1/3 | 1/3 | U: controller recovery or qualification [inferred]; C: controller recovery or qualification [inferred]; S: final evidence selection [direct] |
| Without either | 1 · run-20260916T071531Z | A | A | Partial | No | 2 | 1/3 | 1/3 | U: controller recovery or qualification [inferred]; C: controller recovery or qualification [inferred]; S: controller recovery or qualification [inferred] |
| Without either | 2 · run-20260916T071622Z | P | A | A | No | 2 | 1/3 | 1/3 | C: controller recovery or qualification [inferred]; S: controller recovery or qualification [inferred] |
| Without either | 3 · run-20260916T071735Z | P | A | Partial | No | 2 | 2/3 | 2/3 | C: controller recovery or qualification [inferred]; S: controller recovery or qualification [inferred] |
| Without either | 4 · run-20260916T071903Z | P | A | Partial | No | 3 | 2/3 | 2/3 | C: controller recovery or qualification [inferred]; S: controller recovery or qualification [inferred] |
| Codex | 1 · run-20260902T174151Z | P | A | Partial | No | 5 | 2/3 | 2/3 | C: Codex internal trace unavailable [trace unavailable]; S: Codex internal trace unavailable [trace unavailable] |
| Codex | 2 · run-20260902T174330Z | P | A | P | No | 5 | 2/3 | 2/3 | C: Codex internal trace unavailable [trace unavailable] |
| Codex | 3 · run-20260902T174447Z | P | A | P | No | 4 | 2/3 | 2/3 | C: Codex internal trace unavailable [trace unavailable] |
| Codex | 4 · run-20260902T174620Z | Partial | A | Partial | No | 6 | 2/3 | 2/3 | U: Codex internal trace unavailable [trace unavailable]; C: Codex internal trace unavailable [trace unavailable]; S: Codex internal trace unavailable [trace unavailable] |

## vuejs-vue-11782

The test toolchain pins an http-server version whose command behavior is incompatible with the Windows test workflow.

Connected required evidence: **no**. Required-evidence files: **1**. Implementation-Oracle files: **1**. Required units: H.

| Unit | Exact pre-resolution source | Required responsibility |
|---|---|---|
| H | `package.json:96-108` (`http-server development dependency`) | Pins the incompatible test-server version. |

| Condition | Repetition / run ID | H | Complete? | Final files | Required files represented | Implementation-Oracle files represented | Unit unavailability boundaries |
|---|---|---|---:|---:|---:|---:|---|
| Full Workspace | 1 · run-20260916T071531Z | A | No | 5 | 1/1 | 1/1 | H: raw retrieval [inferred] |
| Full Workspace | 2 · run-20260916T071823Z | A | No | 5 | 1/1 | 1/1 | H: raw retrieval [inferred] |
| Full Workspace | 3 · run-20260916T072048Z | A | No | 5 | 0/1 | 0/1 | H: raw retrieval [inferred] |
| Full Workspace | 4 · run-20260916T072344Z | A | No | 4 | 0/1 | 0/1 | H: raw retrieval [inferred] |
| Without CodeGraph | 1 · run-20260916T034328Z | A | No | 7 | 1/1 | 1/1 | H: raw retrieval [inferred] |
| Without CodeGraph | 2 · run-20260916T034538Z | A | No | 6 | 1/1 | 1/1 | H: candidate-pool construction [inferred] |
| Without CodeGraph | 3 · run-20260916T034803Z | A | No | 5 | 1/1 | 1/1 | H: raw retrieval [inferred] |
| Without CodeGraph | 4 · run-20260916T035000Z | A | No | 6 | 1/1 | 1/1 | H: candidate-pool construction [inferred] |
| Without controller | 1 · run-20260916T023840Z | A | No | 4 | 1/1 | 1/1 | H: initial comparison [inferred] |
| Without controller | 2 · run-20260916T024208Z | A | No | 5 | 0/1 | 0/1 | H: raw retrieval [inferred] |
| Without controller | 3 · run-20260916T024446Z | A | No | 4 | 0/1 | 0/1 | H: raw retrieval [inferred] |
| Without controller | 4 · run-20260916T024720Z | A | No | 5 | 1/1 | 1/1 | H: raw retrieval [inferred] |
| Without either | 1 · run-20260916T072622Z | A | No | 6 | 1/1 | 1/1 | H: raw retrieval [inferred] |
| Without either | 2 · run-20260916T072753Z | A | No | 6 | 1/1 | 1/1 | H: raw retrieval [inferred] |
| Without either | 3 · run-20260916T072924Z | A | No | 6 | 1/1 | 1/1 | H: initial comparison [inferred] |
| Without either | 4 · run-20260916T073056Z | A | No | 4 | 0/1 | 0/1 | H: raw retrieval [inferred] |
| Codex | 1 · run-20260902T174800Z | A | No | 7 | 1/1 | 1/1 | H: Codex internal trace unavailable [trace unavailable] |
| Codex | 2 · run-20260902T174920Z | A | No | 7 | 1/1 | 1/1 | H: Codex internal trace unavailable [trace unavailable] |
| Codex | 3 · run-20260902T175107Z | A | No | 8 | 1/1 | 1/1 | H: Codex internal trace unavailable [trace unavailable] |
| Codex | 4 · run-20260902T175245Z | A | No | 7 | 1/1 | 1/1 | H: Codex internal trace unavailable [trace unavailable] |

## vuejs-vue-13052

The compiler-sfc package has no explicit optional Prettier dependency range, leaving compatibility to an undeclared host installation.

Connected required evidence: **no**. Required-evidence files: **1**. Implementation-Oracle files: **1**. Required units: P.

| Unit | Exact pre-resolution source | Required responsibility |
|---|---|---|
| P | `packages/compiler-sfc/package.json:1-34` (`compiler-sfc dependency metadata`) | Shows the package dependency scope in which a compatible Prettier range is absent. |

| Condition | Repetition / run ID | P | Complete? | Final files | Required files represented | Implementation-Oracle files represented | Unit unavailability boundaries |
|---|---|---|---:|---:|---:|---:|---|
| Full Workspace | 1 · run-20260916T072622Z | A | No | 1 | 0/1 | 0/1 | P: controller recovery or qualification [inferred] |
| Full Workspace | 2 · run-20260916T072803Z | A | No | 1 | 0/1 | 0/1 | P: initial comparison [inferred] |
| Full Workspace | 3 · run-20260916T072943Z | A | No | 1 | 0/1 | 0/1 | P: initial comparison [inferred] |
| Full Workspace | 4 · run-20260916T073115Z | A | No | 1 | 0/1 | 0/1 | P: initial comparison [inferred] |
| Without CodeGraph | 1 · run-20260916T035433Z | A | No | 1 | 0/1 | 0/1 | P: controller recovery or qualification [inferred] |
| Without CodeGraph | 2 · run-20260916T035619Z | A | No | 1 | 0/1 | 0/1 | P: controller recovery or qualification [inferred] |
| Without CodeGraph | 3 · run-20260916T035718Z | A | No | 1 | 0/1 | 0/1 | P: initial comparison [inferred] |
| Without CodeGraph | 4 · run-20260916T035905Z | A | No | 1 | 0/1 | 0/1 | P: controller recovery or qualification [inferred] |
| Without controller | 1 · run-20260916T025000Z | A | No | 1 | 0/1 | 0/1 | P: raw retrieval [inferred] |
| Without controller | 2 · run-20260916T025351Z | A | No | 1 | 0/1 | 0/1 | P: initial comparison [inferred] |
| Without controller | 3 · run-20260916T025504Z | A | No | 2 | 0/1 | 0/1 | P: initial comparison [inferred] |
| Without controller | 4 · run-20260916T025632Z | A | No | 1 | 0/1 | 0/1 | P: raw retrieval [inferred] |
| Without either | 1 · run-20260916T073246Z | A | No | 1 | 0/1 | 0/1 | P: initial comparison [inferred] |
| Without either | 2 · run-20260916T073347Z | A | No | 1 | 0/1 | 0/1 | P: raw retrieval [inferred] |
| Without either | 3 · run-20260916T073501Z | A | No | 1 | 0/1 | 0/1 | P: controller recovery or qualification [inferred] |
| Without either | 4 · run-20260916T073611Z | A | No | 1 | 0/1 | 0/1 | P: initial comparison [inferred] |
| Codex | 1 · run-20260902T175415Z | A | No | 3 | 0/1 | 0/1 | P: Codex internal trace unavailable [trace unavailable] |
| Codex | 2 · run-20260902T175521Z | A | No | 2 | 0/1 | 0/1 | P: Codex internal trace unavailable [trace unavailable] |
| Codex | 3 · run-20260902T175626Z | A | No | 3 | 0/1 | 0/1 | P: Codex internal trace unavailable [trace unavailable] |
| Codex | 4 · run-20260902T175755Z | A | No | 1 | 0/1 | 0/1 | P: Codex internal trace unavailable [trace unavailable] |

## vuejs-vue-5884

Vue.set recognizes only numeric-typed array keys, so a numeric string bypasses splice-based reactive array assignment and follows object-property handling.

Connected required evidence: **no**. Required-evidence files: **1**. Implementation-Oracle files: **1**. Required units: S.

| Unit | Exact pre-resolution source | Required responsibility |
|---|---|---|
| S | `src/core/observer/index.js:185-225` (`set`) | Branches to array splice only when key has JavaScript number type. |

| Condition | Repetition / run ID | S | Complete? | Final files | Required files represented | Implementation-Oracle files represented | Unit unavailability boundaries |
|---|---|---|---:|---:|---:|---:|---|
| Full Workspace | 1 · run-20260916T073247Z | P | Yes | 5 | 1/1 | 1/1 | — |
| Full Workspace | 2 · run-20260916T073542Z | P | Yes | 2 | 1/1 | 1/1 | — |
| Full Workspace | 3 · run-20260916T073750Z | P | Yes | 6 | 1/1 | 1/1 | — |
| Full Workspace | 4 · run-20260916T074049Z | P | Yes | 4 | 1/1 | 1/1 | — |
| Without CodeGraph | 1 · run-20260916T040052Z | P | Yes | 3 | 1/1 | 1/1 | — |
| Without CodeGraph | 2 · run-20260916T040347Z | P | Yes | 6 | 1/1 | 1/1 | — |
| Without CodeGraph | 3 · run-20260916T040639Z | P | Yes | 1 | 1/1 | 1/1 | — |
| Without CodeGraph | 4 · run-20260916T040855Z | P | Yes | 3 | 1/1 | 1/1 | — |
| Without controller | 1 · run-20260916T025753Z | P | Yes | 6 | 1/1 | 1/1 | — |
| Without controller | 2 · run-20260916T025951Z | P | Yes | 3 | 1/1 | 1/1 | — |
| Without controller | 3 · run-20260916T030121Z | P | Yes | 3 | 1/1 | 1/1 | — |
| Without controller | 4 · run-20260916T030246Z | P | Yes | 2 | 1/1 | 1/1 | — |
| Without either | 1 · run-20260916T074324Z | P | Yes | 3 | 1/1 | 1/1 | — |
| Without either | 2 · run-20260916T074450Z | P | Yes | 3 | 1/1 | 1/1 | — |
| Without either | 3 · run-20260916T074621Z | P | Yes | 5 | 1/1 | 1/1 | — |
| Without either | 4 · run-20260916T074800Z | P | Yes | 3 | 1/1 | 1/1 | — |
| Codex | 1 · run-20260902T175857Z | P | Yes | 6 | 1/1 | 1/1 | — |
| Codex | 2 · run-20260902T180047Z | P | Yes | 6 | 1/1 | 1/1 | — |
| Codex | 3 · run-20260902T180221Z | P | Yes | 7 | 1/1 | 1/1 | — |
| Codex | 4 · run-20260902T180353Z | P | Yes | 8 | 1/1 | 1/1 | — |

## vuejs-vue-6097

Inject options normalize only array syntax into plain provider-name strings, and runtime resolution treats every normalized entry as a required provider key with no default path.

Connected required evidence: **yes**. Required-evidence files: **2**. Implementation-Oracle files: **2**. Required units: N, R.

| Unit | Exact pre-resolution source | Required responsibility |
|---|---|---|
| N | `src/core/util/options.js:265-282` (`normalizeInject`) | Normalizes array entries to strings and has no object/default representation. |
| R | `src/core/instance/inject.js:39-67` (`resolveInject`) | Uses the normalized value directly as provideKey and warns when no provider is found. |

| Condition | Repetition / run ID | N | R | Complete? | Final files | Required files represented | Implementation-Oracle files represented | Unit unavailability boundaries |
|---|---|---|---|---:|---:|---:|---:|---|
| Full Workspace | 1 · run-20260916T074324Z | A | Partial | No | 4 | 1/2 | 1/2 | N: controller recovery or qualification [inferred]; R: candidate-pool construction [inferred] |
| Full Workspace | 2 · run-20260916T074626Z | A | A | No | 3 | 1/2 | 1/2 | N: controller recovery or qualification [inferred]; R: controller recovery or qualification [inferred] |
| Full Workspace | 3 · run-20260916T074813Z | P | Partial | No | 6 | 2/2 | 2/2 | R: candidate-pool construction [inferred] |
| Full Workspace | 4 · run-20260916T075137Z | A | Partial | No | 3 | 1/2 | 1/2 | N: controller recovery or qualification [inferred]; R: candidate-pool construction [inferred] |
| Without CodeGraph | 1 · run-20260916T041140Z | P | P | Yes | 5 | 2/2 | 2/2 | — |
| Without CodeGraph | 2 · run-20260916T041355Z | P | P | Yes | 5 | 2/2 | 2/2 | — |
| Without CodeGraph | 3 · run-20260916T041554Z | P | P | Yes | 5 | 2/2 | 2/2 | — |
| Without CodeGraph | 4 · run-20260916T041819Z | P | P | Yes | 3 | 2/2 | 2/2 | — |
| Without controller | 1 · run-20260916T030414Z | P | Partial | No | 4 | 2/2 | 2/2 | R: initial comparison [inferred] |
| Without controller | 2 · run-20260916T030622Z | A | Partial | No | 3 | 1/2 | 1/2 | N: final evidence selection [direct]; R: initial comparison [inferred] |
| Without controller | 3 · run-20260916T030807Z | P | A | No | 5 | 2/2 | 2/2 | R: controller recovery or qualification [inferred] |
| Without controller | 4 · run-20260916T030952Z | P | Partial | No | 4 | 2/2 | 2/2 | R: initial comparison [inferred] |
| Without either | 1 · run-20260916T084338Z | P | P | Yes | 3 | 2/2 | 2/2 | — |
| Without either | 2 · run-20260916T084516Z | A | P | No | 3 | 1/2 | 1/2 | N: controller recovery or qualification [inferred] |
| Without either | 3 · run-20260916T084647Z | P | P | Yes | 3 | 2/2 | 2/2 | — |
| Without either | 4 · run-20260916T084816Z | P | P | Yes | 5 | 2/2 | 2/2 | — |
| Codex | 1 · run-20260902T180547Z | P | Partial | No | 6 | 2/2 | 2/2 | R: Codex internal trace unavailable [trace unavailable] |
| Codex | 2 · run-20260902T180722Z | P | P | Yes | 6 | 2/2 | 2/2 | — |
| Codex | 3 · run-20260902T180845Z | P | P | Yes | 7 | 2/2 | 2/2 | — |
| Codex | 4 · run-20260902T181006Z | P | P | Yes | 7 | 2/2 | 2/2 | — |

## vuejs-vue-8528

The requested change rewrites explanatory comments for shared utility functions without changing their implementations.

Connected required evidence: **no**. Required-evidence files: **1**. Implementation-Oracle files: **1**. Required units: U.

| Unit | Exact pre-resolution source | Required responsibility |
|---|---|---|
| U | `src/shared/util.js:1-308` (`shared utility comments`) | Contains the utility implementations and the comment surface revised by the resolution. |

| Condition | Repetition / run ID | U | Complete? | Final files | Required files represented | Implementation-Oracle files represented | Unit unavailability boundaries |
|---|---|---|---:|---:|---:|---:|---|
| Full Workspace | 1 · run-20260916T075427Z | Partial | No | 1 | 1/1 | 1/1 | U: candidate-pool construction [inferred] |
| Full Workspace | 2 · run-20260916T075704Z | Partial | No | 2 | 1/1 | 1/1 | U: final evidence selection [direct] |
| Full Workspace | 3 · run-20260916T080046Z | A | No | 1 | 0/1 | 0/1 | U: controller recovery or qualification [inferred] |
| Full Workspace | 4 · run-20260916T080237Z | Partial | No | 4 | 1/1 | 1/1 | U: candidate-pool construction [inferred] |
| Without CodeGraph | 1 · run-20260916T042101Z | Partial | No | 2 | 1/1 | 1/1 | U: raw retrieval [inferred] |
| Without CodeGraph | 2 · run-20260916T042327Z | Partial | No | 3 | 1/1 | 1/1 | U: raw retrieval [inferred] |
| Without CodeGraph | 3 · run-20260916T042457Z | Partial | No | 1 | 1/1 | 1/1 | U: raw retrieval [inferred] |
| Without CodeGraph | 4 · run-20260916T042641Z | Partial | No | 2 | 1/1 | 1/1 | U: raw retrieval [inferred] |
| Without controller | 1 · run-20260916T031142Z | Partial | No | 1 | 1/1 | 1/1 | U: raw retrieval [inferred] |
| Without controller | 2 · run-20260916T031303Z | Partial | No | 2 | 1/1 | 1/1 | U: raw retrieval [inferred] |
| Without controller | 3 · run-20260916T031448Z | Partial | No | 1 | 1/1 | 1/1 | U: raw retrieval [inferred] |
| Without controller | 4 · run-20260916T031559Z | Partial | No | 1 | 1/1 | 1/1 | U: raw retrieval [inferred] |
| Without either | 1 · run-20260916T084951Z | Partial | No | 1 | 1/1 | 1/1 | U: raw retrieval [inferred] |
| Without either | 2 · run-20260916T085119Z | Partial | No | 1 | 1/1 | 1/1 | U: raw retrieval [inferred] |
| Without either | 3 · run-20260916T085223Z | Partial | No | 1 | 1/1 | 1/1 | U: raw retrieval [inferred] |
| Without either | 4 · run-20260916T085336Z | Partial | No | 1 | 1/1 | 1/1 | U: raw retrieval [inferred] |
| Codex | 1 · run-20260902T181851Z | Partial | No | 6 | 1/1 | 1/1 | U: Codex internal trace unavailable [trace unavailable] |
| Codex | 2 · run-20260902T182033Z | Partial | No | 1 | 1/1 | 1/1 | U: Codex internal trace unavailable [trace unavailable] |
| Codex | 3 · run-20260902T182133Z | Partial | No | 1 | 1/1 | 1/1 | U: Codex internal trace unavailable [trace unavailable] |
| Codex | 4 · run-20260902T182239Z | Partial | No | 1 | 1/1 | 1/1 | U: Codex internal trace unavailable [trace unavailable] |

## vuejs-vue-9042

On IE, assigning any placeholder to an input or textarea installs a one-shot input-event blocker; an empty textarea placeholder therefore consumes the first real user input event.

Connected required evidence: **no**. Required-evidence files: **1**. Implementation-Oracle files: **1**. Required units: A.

| Unit | Exact pre-resolution source | Required responsibility |
|---|---|---|
| A | `src/platforms/web/runtime/modules/attrs.js:88-115` (`baseSetAttr`) | Sets the placeholder attribute and installs the IE input blocker for both input and textarea without excluding the empty value. |

| Condition | Repetition / run ID | A | Complete? | Final files | Required files represented | Implementation-Oracle files represented | Unit unavailability boundaries |
|---|---|---|---:|---:|---:|---:|---|
| Full Workspace | 1 · run-20260916T080552Z | P | Yes | 7 | 1/1 | 1/1 | — |
| Full Workspace | 2 · run-20260916T080912Z | P | Yes | 7 | 1/1 | 1/1 | — |
| Full Workspace | 3 · run-20260916T081241Z | P | Yes | 9 | 1/1 | 1/1 | — |
| Full Workspace | 4 · run-20260916T081627Z | P | Yes | 8 | 1/1 | 1/1 | — |
| Without CodeGraph | 1 · run-20260916T042849Z | P | Yes | 6 | 1/1 | 1/1 | — |
| Without CodeGraph | 2 · run-20260916T043220Z | A | No | 5 | 0/1 | 0/1 | A: controller recovery or qualification [inferred] |
| Without CodeGraph | 3 · run-20260916T043526Z | P | Yes | 5 | 1/1 | 1/1 | — |
| Without CodeGraph | 4 · run-20260916T043810Z | A | No | 4 | 0/1 | 0/1 | A: candidate-pool construction [inferred] |
| Without controller | 1 · run-20260916T031735Z | P | Yes | 6 | 1/1 | 1/1 | — |
| Without controller | 2 · run-20260916T031953Z | P | Yes | 5 | 1/1 | 1/1 | — |
| Without controller | 3 · run-20260916T032151Z | P | Yes | 7 | 1/1 | 1/1 | — |
| Without controller | 4 · run-20260916T032351Z | P | Yes | 6 | 1/1 | 1/1 | — |
| Without either | 1 · run-20260916T085444Z | P | Yes | 4 | 1/1 | 1/1 | — |
| Without either | 2 · run-20260916T085624Z | A | No | 6 | 0/1 | 0/1 | A: controller recovery or qualification [inferred] |
| Without either | 3 · run-20260916T085805Z | A | No | 6 | 0/1 | 0/1 | A: controller recovery or qualification [inferred] |
| Without either | 4 · run-20260916T085958Z | A | No | 6 | 0/1 | 0/1 | A: controller recovery or qualification [inferred] |
| Codex | 1 · run-20260902T182355Z | P | Yes | 7 | 1/1 | 1/1 | — |
| Codex | 2 · run-20260902T182614Z | P | Yes | 10 | 1/1 | 1/1 | — |
| Codex | 3 · run-20260902T182854Z | P | Yes | 10 | 1/1 | 1/1 | — |
| Codex | 4 · run-20260902T183138Z | P | Yes | 11 | 1/1 | 1/1 | — |

## vuejs-vue-9842

KeepAlive stores the rendered VNode in its cache immediately, while transition patching can still replace its component instance; later pruning destroys the stale cached instance and leaves the live instance retained.

Connected required evidence: **yes**. Required-evidence files: **1**. Implementation-Oracle files: **1**. Required units: P, L, R.

| Unit | Exact pre-resolution source | Required responsibility |
|---|---|---|
| P | `src/core/components/keep-alive.js:20-55` (`pruneCache/pruneCacheEntry`) | Reads cached VNodes and destroys the cached component instance when pruning. |
| L | `src/core/components/keep-alive.js:60-82` (`KeepAlive lifecycle`) | Initializes and prunes the cache but has no mounted/updated cache-commit step. |
| R | `src/core/components/keep-alive.js:83-124` (`KeepAlive.render`) | Writes the current VNode directly into the cache during render. |

| Condition | Repetition / run ID | P | L | R | Complete? | Final files | Required files represented | Implementation-Oracle files represented | Unit unavailability boundaries |
|---|---|---|---|---|---:|---:|---:|---:|---|
| Full Workspace | 1 · run-20260916T082027Z | P | P | P | Yes | 6 | 1/1 | 1/1 | — |
| Full Workspace | 2 · run-20260916T082311Z | P | P | Partial | No | 6 | 1/1 | 1/1 | R: final evidence selection [direct] |
| Full Workspace | 3 · run-20260916T082640Z | P | P | Partial | No | 7 | 1/1 | 1/1 | R: final evidence selection [direct] |
| Full Workspace | 4 · run-20260916T082948Z | P | P | Partial | No | 6 | 1/1 | 1/1 | R: candidate-pool construction [inferred] |
| Without CodeGraph | 1 · run-20260916T044108Z | P | P | Partial | No | 7 | 1/1 | 1/1 | R: final evidence selection [direct] |
| Without CodeGraph | 2 · run-20260916T044526Z | P | P | Partial | No | 8 | 1/1 | 1/1 | R: final evidence selection [direct] |
| Without CodeGraph | 3 · run-20260916T044933Z | P | P | Partial | No | 6 | 1/1 | 1/1 | R: controller recovery or qualification [inferred] |
| Without CodeGraph | 4 · run-20260916T045241Z | P | P | P | Yes | 7 | 1/1 | 1/1 | — |
| Without controller | 1 · run-20260916T032553Z | A | A | Partial | No | 6 | 1/1 | 1/1 | P: final evidence selection [direct]; L: controller recovery or qualification [inferred]; R: controller recovery or qualification [inferred] |
| Without controller | 2 · run-20260916T032824Z | P | P | Partial | No | 7 | 1/1 | 1/1 | R: final evidence selection [direct] |
| Without controller | 3 · run-20260916T033039Z | P | P | Partial | No | 5 | 1/1 | 1/1 | R: controller recovery or qualification [inferred] |
| Without controller | 4 · run-20260916T035233Z | P | P | P | Yes | 5 | 1/1 | 1/1 | — |
| Without either | 1 · run-20260916T085745Z | P | P | Partial | No | 5 | 1/1 | 1/1 | R: controller recovery or qualification [inferred] |
| Without either | 2 · run-20260916T090233Z | P | P | Partial | No | 6 | 1/1 | 1/1 | R: controller recovery or qualification [inferred] |
| Without either | 3 · run-20260916T090419Z | A | A | A | No | 7 | 1/1 | 1/1 | P: controller recovery or qualification [inferred]; L: controller recovery or qualification [inferred]; R: controller recovery or qualification [inferred] |
| Without either | 4 · run-20260916T090600Z | P | P | A | No | 10 | 1/1 | 1/1 | R: controller recovery or qualification [inferred] |
| Codex | 1 · run-20260902T183427Z | P | P | P | Yes | 7 | 1/1 | 1/1 | — |
| Codex | 2 · run-20260902T183620Z | P | P | P | Yes | 7 | 1/1 | 1/1 | — |
| Codex | 3 · run-20260902T184607Z | P | P | P | Yes | 7 | 1/1 | 1/1 | — |
| Codex | 4 · run-20260902T184850Z | Partial | Partial | P | No | 8 | 1/1 | 1/1 | P: Codex internal trace unavailable [trace unavailable]; L: Codex internal trace unavailable [trace unavailable] |

