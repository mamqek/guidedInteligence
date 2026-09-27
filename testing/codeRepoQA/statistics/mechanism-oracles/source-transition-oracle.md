# Required-evidence reference review

Campaign cases: **35**. Mechanism-applicable: **24**. Non-mechanistic/source-surface cases: **11**.

This document is generated from `source-transition-oracle.json`. Only required units are scored; supporting units are retained as contextual notes.

## vuejs-vue-10803

**SSR: textarea domProps keeps falsy values**  
Kind: `causal_code_path`; connected required evidence: `true`; required files: `1`; snapshot: `6390f70c2e4e`.

SSR routes a textarea DOM value through renderDOMProps into a text VNode child; the pre-resolution path passes null through without string normalization.

| Role | ID | Source | Responsibility |
|---|---|---|---|
| R | `R` | `src/platforms/web/server/modules/dom-props.js:8-44` (`renderDOMProps`) | Reads DOM properties and identifies the textarea value branch. |
| R | `H` | `src/platforms/web/server/modules/dom-props.js:46-50` (`setText`) | Constructs a text VNode and installs it as the element's child. |
| S | `S` | `test/ssr/ssr-string.spec.js:1200-1222` (`textarea SSR tests`) | Pre-existing textarea SSR tests; the later null-value regression test is absent from this snapshot. |

Required transitions:

- `T1` `R → H`: The textarea value branch calls setText, which turns that value into the child VNode later serialized as textarea content.

Completeness: R and H must both be present and their call handoff must be visible; the pre-existing test is supporting only.

## microsoft-TypeScript-2953

**`DataView` and other interfaces missing from lib.d.ts**  
Kind: `scoped_absence`; connected required evidence: `false`; required files: `1`; snapshot: `0d2e50b16794`.

The standard declaration surface contains ArrayBuffer types but omits DataView and its constructor.

| Role | ID | Source | Responsibility |
|---|---|---|---|
| R | `D` | `src/lib/extensions.d.ts:1-45` (`ArrayBuffer declaration region`) | Establishes the declaration scope in which DataView is missing. |

Required transitions:

- None. The resolution adds declarations rather than repairing a pre-existing executable path.

Completeness: Enough of the declaration scope must be selected to establish the missing DataView surface; this case has no source transition and is excluded from transition-coverage rates.

## pandas-dev-pandas-10068

**BUG/API: Series arithmetic ops inconsistently hold names**  
Kind: `causal_code_path`; connected required evidence: `true`; required files: `3`; snapshot: `ed000e98f711`.

Series.add dispatches through a generated flexible arithmetic wrapper into Series._binop, which calculates a common name but constructs and finalizes the result without using it.

| Role | ID | Source | Responsibility |
|---|---|---|---|
| R | `W` | `pandas/core/ops.py:755-771` (`_flex_method_SERIES.flex_wrapper`) | Routes Series operands into Series._binop. |
| R | `M` | `pandas/core/common.py:3324-3336` (`_maybe_match_name`) | Defines the common-name decision for equal and unequal operand names. |
| R | `B` | `pandas/core/series.py:1466-1511` (`Series._binop`) | Combines the values, calculates the name, and constructs/finalizes the resulting Series. |
| S | `G` | `pandas/core/series.py:2732-2737` (`Series arithmetic registration`) | Installs the generated flexible arithmetic methods on Series. |

Required transitions:

- `T1` `W → B`: The generated Series.add wrapper invokes Series._binop.
- `T2` `B → M`: Series._binop delegates name choice to _maybe_match_name.
- `T3` `M → B`: The calculated name returns to _binop, where the pre-resolution constructor/finalizer path fails to preserve the intended result.

Completeness: W, M, and B must be present in the same run and jointly expose all three handoffs; G strengthens dispatch attribution but is not mandatory.

## vuejs-vue-10519

**prop validator fails to generate validation error message when using Symbols**  
Kind: `causal_code_path`; connected required evidence: `true`; required files: `1`; snapshot: `b97606cdc658`.

Prop-validation error construction eagerly formats the received Symbol using an expected primitive type, causing the diagnostic path itself to fail.

| Role | ID | Source | Responsibility |
|---|---|---|---|
| R | `V` | `src/core/util/props.js:203-222` (`getInvalidTypeMessage`) | Builds the invalid-prop message and eagerly asks styleValue to format both expected and received representations. |
| R | `F` | `src/core/util/props.js:224-238` (`styleValue/isExplicable`) | Shows the primitive formatting and explicable-type checks that are unsafe when applied under the wrong inferred type. |

Required transitions:

- `T1` `V → F`: Message generation passes the Symbol value into primitive formatting before checking whether that value is explicable.

Completeness: Both V and F and the eager formatting handoff must be visible.

## vuejs-vue-6301

**Provide a Typescript declaration file for `vue-server-renderer/client-plugin`**  
Kind: `api_surface_absence`; connected required evidence: `false`; required files: `3`; snapshot: `1b96ba701907`.

The package exposes JavaScript client/server webpack-plugin entry points but provides no corresponding declaration entry points.

| Role | ID | Source | Responsibility |
|---|---|---|---|
| R | `P` | `packages/vue-server-renderer/package.json:1-40` (`package type metadata`) | Shows the package-level type declaration and scripts but no plugin-specific declaration mapping. |
| R | `C` | `packages/vue-server-renderer/client-plugin.js:17-86` (`client plugin runtime entry point`) | Shows the existing client-plugin implementation and public runtime export for which a declaration entry point is missing. |
| R | `S` | `packages/vue-server-renderer/server-plugin.js:32-99` (`server plugin runtime entry point`) | Shows the existing server-plugin implementation and public runtime export for which a declaration entry point is missing. |

Required transitions:

- None. The relevant change creates type declarations rather than changing an executable mechanism.

Completeness: P, C, and S must jointly expose the package declaration scope and both existing runtime plugin entry points.

## microsoft-TypeScript-45713

**[CLI DX] Improve the 'x errors' message in the CLI**  
Kind: `causal_code_path`; connected required evidence: `true`; required files: `2`; snapshot: `016d78b09e36`.

Watch/build paths count diagnostics and forward only a scalar error count to a formatter that can print no per-file breakdown.

| Role | ID | Source | Responsibility |
|---|---|---|---|
| R | `C` | `src/compiler/watch.ts:96-117` (`getErrorCountForSummary/getErrorSummaryText`) | Counts errors and formats only the aggregate count. |
| R | `W` | `src/compiler/watch.ts:340-360` (`watch status reporter`) | Passes only the count from watch diagnostics to the summary formatter. |
| R | `B` | `src/compiler/tsbuildPublic.ts:75-109` (`ReportEmitErrorSummary/reportErrorSummary`) | Defines the build-host summary callback as accepting only an error count. |
| R | `R` | `src/compiler/tsbuildPublic.ts:2000-2027` (`solution-builder reportErrorSummary`) | Aggregates project errors and calls the host with only totalErrors. |

Required transitions:

- `T1` `W → C`: Watch diagnostics are reduced to a scalar before formatting.
- `T2` `R → B`: The solution builder sends the same scalar through its public callback contract.

Completeness: C, W, B, and R must show both watch and solution-build summary paths losing file identity before formatting.

## pandas-dev-pandas-4542

**ENH: Adding XlsxWriter as an ExcelWriter() option**  
Kind: `plugin_integration`; connected required evidence: `true`; required files: `2`; snapshot: `ebfb4c8a91d8`.

DataFrame.to_excel delegates through ExcelWriter's engine registry, whose pre-resolution implementations support openpyxl and xlwt but not xlsxwriter.

| Role | ID | Source | Responsibility |
|---|---|---|---|
| R | `D` | `pandas/core/frame.py:1356-1415` (`DataFrame.to_excel`) | Exposes the public DataFrame export entry point and its ExcelWriter delegation. |
| R | `R` | `pandas/io/excel.py:20-40` (`writer registry and ExcelWriter`) | Registers writer classes by engine name. |
| R | `E` | `pandas/io/excel.py:284-411` (`ExcelWriter`) | Selects a registered engine from the extension/configuration and instantiates it. |
| R | `X` | `pandas/io/excel.py:412-612` (`writer implementations`) | Shows the complete pre-resolution writer implementation region ending with xlwt and lacking an xlsxwriter writer. |

Required transitions:

- `T1` `D → E`: DataFrame.to_excel creates or uses an ExcelWriter.
- `T2` `E → R`: ExcelWriter resolves an engine through the registry.
- `T3` `R → X`: The registry can dispatch only to registered implementations, and xlsxwriter is absent.

Completeness: D, R, E, and the scoped absence X must jointly establish dispatch and the missing engine implementation.

## microsoft-TypeScript-10020

**Support 'Organize Imports' feature**  
Kind: `causal_code_path`; connected required evidence: `true`; required files: `2`; snapshot: `4d284d617f78`.

Organize Imports collects only top-level import declarations even though the compiler can identify ambient modules, so imports nested in those modules never enter grouping and edit generation.

| Role | ID | Source | Responsibility |
|---|---|---|---|
| R | `O` | `src/services/organizeImports.ts:10-57` (`OrganizeImports.organizeImports`) | Collects, groups, rewrites, and deletes only sourceFile.statements imports; the TODO names ambient modules explicitly. |
| R | `A` | `src/compiler/utilities.ts:423-433` (`isAmbientModule`) | Provides the predicate that can identify string-named or global ambient modules. |

Required transitions:

- `T1` `A → O`: Ambient modules are identifiable, but organizeImports never traverses their module blocks before grouping imports and creating edits.

Completeness: A and O must both be present and the missing traversal between them must be explicit.

## pandas-dev-pandas-14942

**groupby with category column and two additional columns eats up all main memory**  
Kind: `causal_code_path`; connected required evidence: `true`; required files: `3`; snapshot: `28edd0649898`.

Categorical groupby carries every category into grouping and later re-expands the Cartesian result space, even when only a small subset is observed.

| Role | ID | Source | Responsibility |
|---|---|---|---|
| R | `P` | `pandas/core/generic.py:6601-6668` (`NDFrame.groupby`) | Exposes the public groupby entry point, which has no observed parameter and forwards no observed choice. |
| R | `C` | `pandas/core/arrays/categorical.py:650-689` (`Categorical._codes_for_groupby`) | Returns category codes for grouping without an observed-only mode. |
| R | `G` | `pandas/core/groupby/groupby.py:553-590` (`_GroupBy.__init__`) | Builds the grouper without carrying an observed option. |
| R | `I` | `pandas/core/groupby/groupby.py:2874-2990` (`Grouping.__init__`) | Recodes categorical groupers against the complete category set. |
| R | `R` | `pandas/core/groupby/groupby.py:4690-4725` (`_GroupBy._reindex_output`) | Re-expands results to the product of group levels. |

Required transitions:

- `T0` `P → G`: The public groupby entry point constructs GroupBy without an observed-only option.
- `T1` `G → I`: GroupBy construction delegates categorical grouping without an observed-only choice.
- `T2` `I → C`: Grouping obtains codes that retain the full category space.
- `T3` `C → R`: Those complete category levels are used to re-expand the output, producing the memory-heavy Cartesian product.

Completeness: P, C, G, I, and R must be present and expose the propagation from the public API through categorical codes to output re-expansion.

## pandas-dev-pandas-16764

**PERF: pandas' import time**  
Kind: `import_dependency_chain`; connected required evidence: `true`; required files: `5`; snapshot: `2781b18008a7`.

Importing core pandas modules eagerly imports computation, plotting, and optional I/O dependencies before their features are used.

| Role | ID | Source | Responsibility |
|---|---|---|---|
| R | `F` | `pandas/core/frame.py:65-105` (`frame module imports`) | Eagerly imports computation expression/eval and plotting modules while loading DataFrame. |
| R | `O` | `pandas/core/ops.py:1-25` (`ops module imports`) | Eagerly imports the computation expression engine while loading arithmetic operations. |
| R | `C` | `pandas/core/computation/__init__.py:1-23` (`computation package initialization`) | Performs dependency checks and imports computation components at package import time. |
| R | `P` | `pandas/plotting/__init__.py:1-19` (`plotting package initialization`) | Imports plotting conversion, core, style, and tools modules eagerly. |
| R | `I` | `pandas/io/common.py:1-45` (`optional I/O imports`) | Attempts optional cloud-filesystem imports while loading common I/O helpers. |

Required transitions:

- `T1` `F → C`: Loading DataFrame imports the computation package before eval/query is invoked.
- `T2` `F → P`: Loading DataFrame imports plotting before any plot operation is requested.
- `T3` `O → C`: Loading arithmetic operations imports computation expressions before an arithmetic call needs them.
- `T4` `F → I`: The general import surface reaches optional I/O dependencies during module initialization.

Completeness: The selected evidence must expose each eager dependency branch F→C, F→P, O→C, and F→I; isolated imports are partial.

## microsoft-TypeScript-10041

**RegExpMatchArray has lost some compatibility with Array since 2.1.0-dev.20160729**  
Kind: `causal_code_path`; connected required evidence: `true`; required files: `1`; snapshot: `36b611334dff`.

Logical-or and conditional expressions reduce their alternatives directly through getUnionType, which can choose a less specific array type despite one alternative being assignable to the other.

| Role | ID | Source | Responsibility |
|---|---|---|---|
| R | `B` | `src/compiler/checker.ts:12900-13055` (`checkBinaryExpression`) | Checks logical-or expressions and sends the two possible types directly to getUnionType. |
| R | `C` | `src/compiler/checker.ts:13165-13180` (`checkConditionalExpression`) | Combines conditional branches through the same direct union reduction. |

Required transitions:

- `T1` `B → C`: Both choice-producing expressions share the same reduction rule and therefore the same subtype-selection defect.

Completeness: B and C must show both affected choice paths and their common direct-union behavior.

## microsoft-TypeScript-10473

**TSServer: config file diagnostics event not sent if config file changes**  
Kind: `event_delivery_chain`; connected required evidence: `true`; required files: `2`; snapshot: `81fc759530c3`.

Configuration diagnostics are emitted only when the diagnostics array is non-empty, and Session separately gates the open-file event, so a config change that clears errors produces no event.

| Role | ID | Source | Responsibility |
|---|---|---|---|
| R | `P` | `src/server/editorServices.ts:750-770` (`ProjectService.reportConfigFileDiagnostics`) | Suppresses configFileDiag when diagnostics is empty. |
| R | `S` | `src/server/session.ts:150-205` (`Session constructor/handleEvent`) | Creates the ProjectService event handler only when events are enabled and routes configFileDiag events. |
| R | `O` | `src/server/session.ts:710-730` (`Session.openClientFile`) | Emits the open-file config diagnostic only when configFileErrors is truthy. |

Required transitions:

- `T1` `P → S`: ProjectService diagnostics reach Session only when the non-empty guard permits an event.
- `T2` `O → S`: The open-file path independently applies the same presence guard before event delivery.

Completeness: P, S, and O must establish both suppression points and the event-handler handoff.

## microsoft-TypeScript-16278

**New refactor API**  
Kind: `api_protocol_chain`; connected required evidence: `true`; required files: `6`; snapshot: `b217c39bb160`.

The old refactor API exposes applicable refactor names and then requests a whole refactor's code actions, without a distinct selected-action edit request and rename metadata contract.

| Role | ID | Source | Responsibility |
|---|---|---|---|
| R | `T` | `src/services/types.ts:255-375` (`LanguageService refactor contracts`) | Defines applicable-refactor and getRefactorCodeActions contracts but no selected-action edit result. |
| R | `P` | `src/services/refactorProvider.ts:1-59` (`refactor registry/provider`) | Finds applicable refactors and asks a named provider for code actions. |
| R | `L` | `src/services/services.ts:1988-2022` (`LanguageService refactor implementation`) | Adapts the public LanguageService request into provider calls. |
| R | `Q` | `src/server/protocol.ts:390-448` (`refactor protocol contracts`) | Defines discovery and whole-refactor code-action requests, with no selected-action edit command. |
| R | `S` | `src/server/session.ts:1418-1455` (`Session refactor commands`) | Handles protocol requests and returns the refactor code actions. |
| R | `C` | `src/server/client.ts:710-745` (`SessionClient refactor adapter`) | Sends the refactor request and converts returned code actions for the client. |

Required transitions:

- `T1` `C → Q`: The client constructs the old refactor protocol request.
- `T2` `Q → S`: Session receives the discovery or whole-refactor code-action command.
- `T3` `S → L`: Session invokes the LanguageService refactor API.
- `T4` `L → P`: LanguageService delegates discovery/action generation to the registered refactor provider.
- `T5` `P → T`: Provider output is constrained by the old whole-refactor CodeAction contract.

Completeness: T, P, L, Q, S, and C must expose the end-to-end old API/protocol path and the missing selected-action edit boundary.

## microsoft-TypeScript-19074

**Clean up LSHost mentions**  
Kind: `comment_only_maintenance`; connected required evidence: `false`; required files: `2`; snapshot: `a97c18f227c2`.

The change updates stale LSHost terminology in comments without altering runtime behavior.

| Role | ID | Source | Responsibility |
|---|---|---|---|
| R | `M` | `src/compiler/moduleNameResolver.ts:1484-1494` (`loadModuleFromGlobalCache comment`) | Contains the stale LSHost terminology in the resolver comment. |
| R | `P` | `src/server/project.ts:946-960` (`external-file comment`) | Contains the stale LSHost terminology in the project comment. |

Required transitions:

- None. No executable source transition changes.

Completeness: Both comment sites define the maintenance surface; the case is excluded from mechanism-transition rates.

## microsoft-TypeScript-24625

**TypeScript 2.9 Watch API change breaking watch support in ts-loader?**  
Kind: `api_type_surface`; connected required evidence: `false`; required files: `1`; snapshot: `34e68efdae72`.

Three watch-builder factory overloads require rootNames and options even though the CreateProgram callback contract can supply undefined values.

| Role | ID | Source | Responsibility |
|---|---|---|---|
| R | `B` | `src/compiler/builder.ts:545-577` (`builder factory overloads`) | Shows the required rootNames/options parameters on all three builder factories. |

Required transitions:

- None. The resolution widens type signatures and does not alter the builder execution path.

Completeness: B must expose all three incompatible overloads; the case is an API type-surface defect rather than a source-transition case.

## microsoft-TypeScript-35468

**TS does not recompile correctly when using a combination of project references, wildcard re-exports and watch mode**  
Kind: `state_identity_chain`; connected required evidence: `true`; required files: `2`; snapshot: `f7860b048037`.

Incremental builder state keys dependency, signature, affected-file, and emit maps by sourceFile.path even though project-reference aliases require the canonical resolvedPath identity.

| Role | ID | Source | Responsibility |
|---|---|---|---|
| R | `I` | `src/compiler/builderState.ts:120-235` (`BuilderState.create`) | Builds file information and reference/export maps using sourceFile.path. |
| R | `U` | `src/compiler/builderState.ts:304-370` (`updateShapeSignature`) | Reads and updates signature/export caches using sourceFile.path. |
| R | `A` | `src/compiler/builderState.ts:405-560` (`affected-file traversal`) | Seeds and deduplicates affected-file traversal with path rather than resolvedPath. |
| R | `E` | `src/compiler/builder.ts:315-425` (`builder affected/emit state`) | Uses affectedFile.path for semantic-diagnostic and emit bookkeeping. |

Required transitions:

- `T1` `I → U`: The identity chosen while building state is reused for signature lookup and updates.
- `T2` `U → A`: Signature changes drive dependency traversal keyed by the same non-canonical path.
- `T3` `A → E`: Affected files enter diagnostic and emit bookkeeping under that inconsistent identity.

Completeness: I, U, A, and E must show the same path identity crossing state creation, signature update, dependency propagation, and emission.

## microsoft-TypeScript-46770

**Cannot import some packages when tsconfig.json specifies "module": "nodenext"**  
Kind: `causal_code_path`; connected required evidence: `false`; required files: `1`; snapshot: `7e57c81802b4`.

NodeNext package resolution keeps ESM-mode extension rules active while resolving the main field of a CommonJS package, so an extensionless main target is rejected.

| Role | ID | Source | Responsibility |
|---|---|---|---|
| R | `R` | `src/compiler/moduleNameResolver.ts:1784-1826` (`loadNodeModuleFromDirectoryWorker`) | Reads package fields and resolves the selected package path with the unchanged NodeNext feature state. |

Required transitions:

- `T1` `R → R`: The package main value is handed to relative-name resolution without disabling ESM-mode rules for a CommonJS package.

Completeness: R must show package-main selection, the retained feature state, and the relative-name resolution call.

## microsoft-TypeScript-52695

**Reduce number of fs.stat call for files under node modules**  
Kind: `causal_code_path`; connected required evidence: `true`; required files: `1`; snapshot: `2291afc18735`.

Node-module resolution performs file probes for URI-like specifiers and package-root candidates before directory/package handling, producing avoidable filesystem stat calls.

| Role | ID | Source | Responsibility |
|---|---|---|---|
| R | `N` | `src/compiler/moduleNameResolver.ts:1706-1820` (`nodeModuleNameResolverWorker`) | Falls through unresolved non-relative names into node_modules lookup without rejecting URI-like names. |
| R | `L` | `src/compiler/moduleNameResolver.ts:2868-2910` (`loadModuleFromSpecificNodeModulesDirectory`) | Probes the package-root candidate as a file before loading it as a directory/package. |

Required transitions:

- `T1` `N → L`: Unfiltered module names reach node_modules resolution, whose loader performs the unnecessary file probe.

Completeness: N and L must jointly show the unfiltered entry and the unnecessary file probe.

## pandas-dev-pandas-10150

**BUG/API: inconsistent name handling in value_counts **  
Kind: `causal_code_path`; connected required evidence: `true`; required files: `2`; snapshot: `3908ad53e33c`.

The value_counts wrapper delegates to algorithms.value_counts, which converts away the input object's name and constructs the count Series unnamed; index reconstruction then incorrectly applies the original name to the result index.

| Role | ID | Source | Responsibility |
|---|---|---|---|
| R | `A` | `pandas/core/algorithms.py:176-255` (`algorithms.value_counts`) | Converts the input to raw values and constructs the result Series without preserving its name. |
| R | `B` | `pandas/core/base.py:399-445` (`IndexOpsMixin.value_counts`) | Calls algorithms.value_counts and uses self.name when rebuilding Period/Datetime indexes. |

Required transitions:

- `T1` `B → A`: The public wrapper passes the named object into algorithms.value_counts, where conversion and result construction lose the name before the wrapper rebuilds the index.

Completeness: A and B must expose both the delegation and the two inconsistent name assignments.

## pandas-dev-pandas-16499

**TST: ujson tests are not being run**  
Kind: `test_discovery_surface`; connected required evidence: `false`; required files: `1`; snapshot: `e81f3cc30725`.

Pytest cannot collect the ujson test groups because their class names do not begin with Test.

| Role | ID | Source | Responsibility |
|---|---|---|---|
| R | `U` | `pandas/tests/io/json/test_ujson.py:25-45` (`UltraJSONTests`) | Defines the first uncollectable test class. |
| R | `N` | `pandas/tests/io/json/test_ujson.py:940-965` (`NumpyJSONTests`) | Defines the NumPy ujson tests under an uncollectable class name. |
| R | `P` | `pandas/tests/io/json/test_ujson.py:1218-1240` (`PandasJSONTests`) | Defines the pandas-object ujson tests under an uncollectable class name. |

Required transitions:

- None. The repository's pytest collector implementation is external to this snapshot, so there is no internal source handoff to score.

Completeness: U, N, and P must all be present to cover the test-discovery defect; the case is excluded from runtime transition rates.

## pandas-dev-pandas-22698

**Handle FutureWarning from NumPy in Series Construction**  
Kind: `causal_code_path`; connected required evidence: `false`; required files: `1`; snapshot: `cfd65e98e694`.

Index comparison deliberately records and suppresses NumPy's invalid-elementwise-comparison FutureWarning before returning the comparison result.

| Role | ID | Source | Responsibility |
|---|---|---|---|
| R | `C` | `pandas/core/indexes/base.py:60-95` (`Index comparison cmp_method`) | Wraps the NumPy comparison in a warning-catching block that ignores FutureWarning. |

Required transitions:

- `T1` `C → C`: NumPy emits the warning inside a catch-and-ignore scope, preventing it from reaching the Series/Index constructor caller.

Completeness: C must show both the comparison and the warning-suppression scope.

## pandas-dev-pandas-22872

**Replace bare excepts by explicit excepts in pandas/tests/**  
Kind: `static_cleanup`; connected required evidence: `false`; required files: `2`; snapshot: `960a73f0c81d`.

Both repository lint configurations explicitly ignore E722, permitting bare except clauses in the test suite.

| Role | ID | Source | Responsibility |
|---|---|---|---|
| R | `S` | `setup.cfg:10-25` (`pycodestyle ignore list`) | Disables E722 for the repository lint configuration. |
| R | `P` | `.pep8speaks.yml:8-20` (`pep8speaks ignore list`) | Disables E722 for the review-bot lint configuration. |

Required transitions:

- None. This is a static style cleanup, not an executable repository mechanism.

Completeness: S and P define the policy surface; the individual one-off test cleanups are not treated as a runtime mechanism.

## pandas-dev-pandas-25183

**DataFrame.merge with empty frame and Int64 column gives object dtype**  
Kind: `causal_code_path`; connected required evidence: `false`; required files: `1`; snapshot: `f74aba614554`.

Concat reindexing treats an all-missing extension block like a NumPy block and replaces it with an array of the common empty dtype, losing the nullable Int64 extension dtype during merge.

| Role | ID | Source | Responsibility |
|---|---|---|---|
| R | `J` | `pandas/core/internals/concat.py:165-215` (`JoinUnit.get_reindexed_values`) | Shows the missing-value branch and its NumPy replacement array, without an extension-block exemption. |

Required transitions:

- `T1` `J → J`: An empty extension-backed join unit enters the generic missing-array construction and emerges with the common NumPy dtype.

Completeness: J must expose the extension-block input condition and the generic replacement-array branch.

## pandas-dev-pandas-32289

**CI Failing - Linux py37_np_dev - test_constructor_list_frames**  
Kind: `diagnostic_path`; connected required evidence: `false`; required files: `1`; snapshot: `f6fb2576be6f`.

DataFrame construction converts each nested value with np.asarray, then rejects non-two-dimensional results with a generic error that omits the observed shape.

| Role | ID | Source | Responsibility |
|---|---|---|---|
| R | `C` | `pandas/core/internals/construction.py:290-328` (`to_arrays.convert`) | Converts list elements and raises the generic dimensionality error. |

Required transitions:

- `T1` `C → C`: The converted array's ndim triggers an error response that discards the shape information needed to diagnose the constructor failure.

Completeness: C must show conversion, the dimensionality check, and the generic error.

## pandas-dev-pandas-35925

**CLN remove unnecessary trailing commas to get ready for new version of black**  
Kind: `formatting_migration`; connected required evidence: `false`; required files: `1`; snapshot: `a0d6d061de42`.

The repository pins Black 19.10b0; updating the formatter changes accepted trailing-comma formatting across many otherwise unrelated files.

| Role | ID | Source | Responsibility |
|---|---|---|---|
| R | `B` | `.pre-commit-config.yaml:1-7` (`Black pre-commit hook`) | Pins the formatter version that motivates the mechanical source rewrite. |

Required transitions:

- None. This case is a formatter migration with no coherent runtime transition.

Completeness: B identifies the maintenance cause; mechanical formatting edits are not scored as a source mechanism.

## pandas-dev-pandas-36617

**DOC: Replace single with double backticks in RST files**  
Kind: `documentation_cleanup`; connected required evidence: `false`; required files: `1`; snapshot: `e088ea31a897`.

The rst-backticks hook excludes a named set of documentation files, leaving their single-backtick markup outside automated enforcement.

| Role | ID | Source | Responsibility |
|---|---|---|---|
| R | `R` | `.pre-commit-config.yaml:33-53` (`rst-backticks hook`) | Shows the documentation hook and its explicit exclusion list. |

Required transitions:

- None. The resolution is a documentation-wide markup cleanup plus removal of exclusions.

Completeness: R defines the maintenance scope; the case is excluded from mechanism-transition rates.

## vuejs-vue-10004

**Memory leak with component with input with v-model**  
Kind: `lifecycle_cleanup_chain`; connected required evidence: `false`; required files: `1`; snapshot: `509de2af793a`.

DOM listeners are reconciled on create/update only; destroying a deactivated component has no hook that reuses the old element to remove stale v-model listeners.

| Role | ID | Source | Responsibility |
|---|---|---|---|
| R | `E` | `src/platforms/web/runtime/modules/events.js:100-120` (`updateDOMListeners/module hooks`) | Targets vnode.elm and exports only create/update hooks, leaving no destroy cleanup path. |

Required transitions:

- `T1` `E → E`: Listener reconciliation has no destroy lifecycle entry and cannot target oldVnode.elm when vnode.elm is absent.

Completeness: E must show target selection and the missing destroy hook together.

## vuejs-vue-11718

**vuejs/vue-ssr-webpack-plugin and webpack 5**  
Kind: `compatibility_adapter_chain`; connected required evidence: `true`; required files: `3`; snapshot: `38f71de380d5`.

The SSR webpack plugins assume webpack 4's emit hook, string entry assets, space-suffixed module hashes, and the legacy libraryTarget shape.

| Role | ID | Source | Responsibility |
|---|---|---|---|
| R | `U` | `src/server/webpack-plugin/util.js:1-34` (`validate/onEmit`) | Validates legacy output.libraryTarget and selects only legacy or webpack-4 emit hooks. |
| R | `C` | `src/server/webpack-plugin/client.js:1-55` (`VueSSRClientPlugin.apply`) | Passes webpack stats assets/module identifiers through string-only assumptions. |
| R | `S` | `src/server/webpack-plugin/server.js:1-60` (`VueSSRServerPlugin.apply`) | Filters entry assets and consumes stats.assets under webpack-4 shapes. |

Required transitions:

- `T1` `C → U`: The client plugin delegates emission through the legacy hook adapter.
- `T2` `S → U`: The server plugin delegates through the same adapter and legacy output validation.
- `T3` `U → C`: Webpack output then reaches client manifest construction under string/hash assumptions.
- `T4` `U → S`: Webpack output reaches server bundle construction under legacy asset shapes.

Completeness: U, C, and S must expose the shared hook/validation boundary and both consumers' incompatible data-shape assumptions.

## vuejs-vue-11782

**npm test fails on Windows**  
Kind: `dependency_configuration`; connected required evidence: `false`; required files: `1`; snapshot: `b800e8e9ee4f`.

The test toolchain pins an http-server version whose command behavior is incompatible with the Windows test workflow.

| Role | ID | Source | Responsibility |
|---|---|---|---|
| R | `H` | `package.json:96-108` (`http-server development dependency`) | Pins the incompatible test-server version. |

Required transitions:

- None. The fix is a dependency upgrade, while the failing behavior resides in the external package.

Completeness: H defines the dependency configuration; external package behavior is not a repository source transition.

## vuejs-vue-13052

**compiler-sfc not compatible with prettier v3**  
Kind: `dependency_configuration`; connected required evidence: `false`; required files: `1`; snapshot: `0ad8e8d94f3a`.

The compiler-sfc package has no explicit optional Prettier dependency range, leaving compatibility to an undeclared host installation.

| Role | ID | Source | Responsibility |
|---|---|---|---|
| R | `P` | `packages/compiler-sfc/package.json:1-34` (`compiler-sfc dependency metadata`) | Shows the package dependency scope in which a compatible Prettier range is absent. |

Required transitions:

- None. The resolution changes package metadata rather than a source execution path.

Completeness: P must establish the missing package dependency declaration; the case is excluded from source-transition rates.

## vuejs-vue-5884

**Vue.set Api strange behavior if path is a numerical string**  
Kind: `causal_code_path`; connected required evidence: `false`; required files: `1`; snapshot: `080c387d49cd`.

Vue.set recognizes only numeric-typed array keys, so a numeric string bypasses splice-based reactive array assignment and follows object-property handling.

| Role | ID | Source | Responsibility |
|---|---|---|---|
| R | `S` | `src/core/observer/index.js:185-225` (`set`) | Branches to array splice only when key has JavaScript number type. |

Required transitions:

- `T1` `S → S`: A numeric-string key fails the array-index guard and therefore misses the splice/reactivity path.

Completeness: S must show the key guard, splice path, and fall-through context.

## vuejs-vue-6097

**Allow defining optional inject dependency with default values**  
Kind: `configuration_runtime_chain`; connected required evidence: `true`; required files: `2`; snapshot: `b3cd9bc3940e`.

Inject options normalize only array syntax into plain provider-name strings, and runtime resolution treats every normalized entry as a required provider key with no default path.

| Role | ID | Source | Responsibility |
|---|---|---|---|
| R | `N` | `src/core/util/options.js:265-282` (`normalizeInject`) | Normalizes array entries to strings and has no object/default representation. |
| R | `R` | `src/core/instance/inject.js:39-67` (`resolveInject`) | Uses the normalized value directly as provideKey and warns when no provider is found. |

Required transitions:

- `T1` `N → R`: Normalized inject entries are consumed as bare provider keys, leaving no place for a default value to survive into resolution.

Completeness: N and R must expose the option normalization and runtime missing-provider path.

## vuejs-vue-8528

**Better comments in `shared/util.js` code**  
Kind: `comment_only_maintenance`; connected required evidence: `false`; required files: `1`; snapshot: `5e912976c45c`.

The requested change rewrites explanatory comments for shared utility functions without changing their implementations.

| Role | ID | Source | Responsibility |
|---|---|---|---|
| R | `U` | `src/shared/util.js:1-308` (`shared utility comments`) | Contains the utility implementations and the comment surface revised by the resolution. |

Required transitions:

- None. The pull request changes comments only.

Completeness: U identifies the documentation surface; this case has no executable transition to score.

## vuejs-vue-9042

**First character or paste is not accepted for watch when assigning placeholder to "" in <textarea> tag with IE11**  
Kind: `causal_code_path`; connected required evidence: `false`; required files: `1`; snapshot: `dbc0582587f9`.

On IE, assigning any placeholder to an input or textarea installs a one-shot input-event blocker; an empty textarea placeholder therefore consumes the first real user input event.

| Role | ID | Source | Responsibility |
|---|---|---|---|
| R | `A` | `src/platforms/web/runtime/modules/attrs.js:88-115` (`baseSetAttr`) | Sets the placeholder attribute and installs the IE input blocker for both input and textarea without excluding the empty value. |

Required transitions:

- `T1` `A → A`: The empty placeholder assignment creates a blocker whose next input event is stopped before v-model can retain the user's change.

Completeness: A must show the empty-placeholder-eligible guard and the stopped input event.

## vuejs-vue-9842

**Memory leak when using "transition" and "keep-alive"**  
Kind: `lifecycle_state_chain`; connected required evidence: `true`; required files: `1`; snapshot: `2b93e86aa143`.

KeepAlive stores the rendered VNode in its cache immediately, while transition patching can still replace its component instance; later pruning destroys the stale cached instance and leaves the live instance retained.

| Role | ID | Source | Responsibility |
|---|---|---|---|
| R | `P` | `src/core/components/keep-alive.js:20-55` (`pruneCache/pruneCacheEntry`) | Reads cached VNodes and destroys the cached component instance when pruning. |
| R | `L` | `src/core/components/keep-alive.js:60-82` (`KeepAlive lifecycle`) | Initializes and prunes the cache but has no mounted/updated cache-commit step. |
| R | `R` | `src/core/components/keep-alive.js:83-124` (`KeepAlive.render`) | Writes the current VNode directly into the cache during render. |

Required transitions:

- `T1` `R → L`: Render commits the pre-patch VNode immediately instead of deferring cache commitment until mounted/updated.
- `T2` `L → P`: Later include/exclude or capacity pruning reads that stale cache entry and destroys its component instance.

Completeness: R, L, and P must jointly expose immediate cache storage, the missing post-update commit boundary, and stale-entry destruction.

