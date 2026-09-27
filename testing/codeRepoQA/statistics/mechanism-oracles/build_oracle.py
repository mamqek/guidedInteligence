"""Build the curated source-transition Oracle and its review document."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
INVENTORY = ROOT / "testing/codeRepoQA/statistics/runs/2026-09-16-five-mode-four-runs.json"


def unit(
    unit_id: str,
    path: str,
    symbol: str,
    start: int,
    end: int,
    description: str,
    *anchors: str,
    evidence_type: str = "source_range",
    required: bool = True,
    partial_start: int | None = None,
    partial_end: int | None = None,
) -> dict:
    result = {
        "id": unit_id,
        "required": required,
        "evidence_type": evidence_type,
        "source": {
            "path": path,
            "symbol": symbol,
            "line_start": start,
            "line_end": end,
        },
        "anchors": list(anchors),
        "description": description,
    }
    if partial_start is not None and partial_end is not None:
        result["partial_range"] = {"line_start": partial_start, "line_end": partial_end}
    return result


def transition(transition_id: str, source: str, target: str, description: str) -> dict:
    return {"id": transition_id, "from": source, "to": target, "required": True, "description": description}


CASES: dict[str, dict] = {
    "vuejs-vue-10803": {
        "oracle_kind": "causal_code_path",
        "mechanism_applicable": True,
        "mechanism_summary": "SSR routes a textarea DOM value through renderDOMProps into a text VNode child; the pre-resolution path passes null through without string normalization.",
        "evidence_units": [
            unit("R", "src/platforms/web/server/modules/dom-props.js", "renderDOMProps", 8, 44, "Reads DOM properties and identifies the textarea value branch.", "function renderDOMProps", "key === 'value' && node.tag === 'textarea'"),
            unit("H", "src/platforms/web/server/modules/dom-props.js", "setText", 46, 50, "Constructs a text VNode and installs it as the element's child.", "function setText", "new VNode", "node.children = [child]"),
        ],
        "supporting_units": [
            unit("S", "test/ssr/ssr-string.spec.js", "textarea SSR tests", 1200, 1222, "Pre-existing textarea SSR tests; the later null-value regression test is absent from this snapshot.", "render v-model with textarea", required=False),
        ],
        "transitions": [transition("T1", "R", "H", "The textarea value branch calls setText, which turns that value into the child VNode later serialized as textarea content.")],
        "completeness_rule": "R and H must both be present and their call handoff must be visible; the pre-existing test is supporting only.",
    },
    "microsoft-TypeScript-2953": {
        "oracle_kind": "scoped_absence",
        "mechanism_applicable": False,
        "mechanism_summary": "The standard declaration surface contains ArrayBuffer types but omits DataView and its constructor.",
        "evidence_units": [
            unit("D", "src/lib/extensions.d.ts", "ArrayBuffer declaration region", 1, 45, "Establishes the declaration scope in which DataView is missing.", "interface ArrayBuffer", "interface ArrayBufferView", evidence_type="scoped_absence"),
        ],
        "supporting_units": [],
        "transitions": [],
        "completeness_rule": "Enough of the declaration scope must be selected to establish the missing DataView surface; this case has no source transition and is excluded from transition-coverage rates.",
        "applicability_note": "The resolution adds declarations rather than repairing a pre-existing executable path.",
    },
    "pandas-dev-pandas-10068": {
        "oracle_kind": "causal_code_path",
        "mechanism_applicable": True,
        "mechanism_summary": "Series.add dispatches through a generated flexible arithmetic wrapper into Series._binop, which calculates a common name but constructs and finalizes the result without using it.",
        "evidence_units": [
            unit("W", "pandas/core/ops.py", "_flex_method_SERIES.flex_wrapper", 755, 771, "Routes Series operands into Series._binop.", "def flex_wrapper", "return self._binop(other, op"),
            unit("M", "pandas/core/common.py", "_maybe_match_name", 3324, 3336, "Defines the common-name decision for equal and unequal operand names.", "def _maybe_match_name", "if a.name == b.name", "return None"),
            unit("B", "pandas/core/series.py", "Series._binop", 1466, 1511, "Combines the values, calculates the name, and constructs/finalizes the resulting Series.", "def _binop", "name = _maybe_match_name", "return self._constructor(result, index=new_index).__finalize__(self)"),
        ],
        "supporting_units": [
            unit("G", "pandas/core/series.py", "Series arithmetic registration", 2732, 2737, "Installs the generated flexible arithmetic methods on Series.", "ops.add_flex_arithmetic_methods(Series", required=False),
        ],
        "transitions": [
            transition("T1", "W", "B", "The generated Series.add wrapper invokes Series._binop."),
            transition("T2", "B", "M", "Series._binop delegates name choice to _maybe_match_name."),
            transition("T3", "M", "B", "The calculated name returns to _binop, where the pre-resolution constructor/finalizer path fails to preserve the intended result."),
        ],
        "completeness_rule": "W, M, and B must be present in the same run and jointly expose all three handoffs; G strengthens dispatch attribution but is not mandatory.",
    },
    "vuejs-vue-10519": {
        "oracle_kind": "causal_code_path",
        "mechanism_applicable": True,
        "mechanism_summary": "Prop-validation error construction eagerly formats the received Symbol using an expected primitive type, causing the diagnostic path itself to fail.",
        "evidence_units": [
            unit("V", "src/core/util/props.js", "getInvalidTypeMessage", 203, 222, "Builds the invalid-prop message and eagerly asks styleValue to format both expected and received representations.", "function getInvalidTypeMessage", "const expectedValue = styleValue", "const receivedValue = styleValue"),
            unit("F", "src/core/util/props.js", "styleValue/isExplicable", 224, 238, "Shows the primitive formatting and explicable-type checks that are unsafe when applied under the wrong inferred type.", "function styleValue", "return `${value}`", "function isExplicable"),
        ],
        "supporting_units": [],
        "transitions": [transition("T1", "V", "F", "Message generation passes the Symbol value into primitive formatting before checking whether that value is explicable.")],
        "completeness_rule": "Both V and F and the eager formatting handoff must be visible.",
    },
    "vuejs-vue-6301": {
        "oracle_kind": "api_surface_absence",
        "mechanism_applicable": False,
        "mechanism_summary": "The package exposes JavaScript client/server webpack-plugin entry points but provides no corresponding declaration entry points.",
        "evidence_units": [
            unit("P", "packages/vue-server-renderer/package.json", "package type metadata", 1, 40, "Shows the package-level type declaration and scripts but no plugin-specific declaration mapping.", '"types": "types/index.d.ts"', evidence_type="scoped_absence"),
            unit("C", "packages/vue-server-renderer/client-plugin.js", "client plugin runtime entry point", 17, 86, "Shows the existing client-plugin implementation and public runtime export for which a declaration entry point is missing.", "var VueSSRClientPlugin", "module.exports = VueSSRClientPlugin"),
            unit("S", "packages/vue-server-renderer/server-plugin.js", "server plugin runtime entry point", 32, 99, "Shows the existing server-plugin implementation and public runtime export for which a declaration entry point is missing.", "var VueSSRServerPlugin", "module.exports = VueSSRServerPlugin"),
        ],
        "supporting_units": [],
        "transitions": [],
        "completeness_rule": "P, C, and S must jointly expose the package declaration scope and both existing runtime plugin entry points.",
        "applicability_note": "The relevant change creates type declarations rather than changing an executable mechanism.",
    },
    "microsoft-TypeScript-45713": {
        "oracle_kind": "causal_code_path",
        "mechanism_applicable": True,
        "mechanism_summary": "Watch/build paths count diagnostics and forward only a scalar error count to a formatter that can print no per-file breakdown.",
        "evidence_units": [
            unit("C", "src/compiler/watch.ts", "getErrorCountForSummary/getErrorSummaryText", 96, 117, "Counts errors and formats only the aggregate count.", "getErrorCountForSummary", "getErrorSummaryText(errorCount: number"),
            unit("W", "src/compiler/watch.ts", "watch status reporter", 340, 360, "Passes only the count from watch diagnostics to the summary formatter.", "reportSummary(getErrorCountForSummary(diagnostics))"),
            unit("B", "src/compiler/tsbuildPublic.ts", "ReportEmitErrorSummary/reportErrorSummary", 75, 109, "Defines the build-host summary callback as accepting only an error count.", "ReportEmitErrorSummary = (errorCount: number)"),
            unit("R", "src/compiler/tsbuildPublic.ts", "solution-builder reportErrorSummary", 2000, 2027, "Aggregates project errors and calls the host with only totalErrors.", "function reportErrorSummary", "state.host.reportErrorSummary(totalErrors)"),
        ],
        "supporting_units": [],
        "transitions": [
            transition("T1", "W", "C", "Watch diagnostics are reduced to a scalar before formatting."),
            transition("T2", "R", "B", "The solution builder sends the same scalar through its public callback contract."),
        ],
        "completeness_rule": "C, W, B, and R must show both watch and solution-build summary paths losing file identity before formatting.",
    },
    "pandas-dev-pandas-4542": {
        "oracle_kind": "plugin_integration",
        "mechanism_applicable": True,
        "mechanism_summary": "DataFrame.to_excel delegates through ExcelWriter's engine registry, whose pre-resolution implementations support openpyxl and xlwt but not xlsxwriter.",
        "evidence_units": [
            unit("D", "pandas/core/frame.py", "DataFrame.to_excel", 1356, 1415, "Exposes the public DataFrame export entry point and its ExcelWriter delegation.", "def to_excel", "from pandas.io.excel import ExcelWriter"),
            unit("R", "pandas/io/excel.py", "writer registry and ExcelWriter", 20, 40, "Registers writer classes by engine name.", "def register_writer", "_writers[engine_name]"),
            unit("E", "pandas/io/excel.py", "ExcelWriter", 284, 411, "Selects a registered engine from the extension/configuration and instantiates it.", "class ExcelWriter", "class ExcelWriterMeta"),
            unit("X", "pandas/io/excel.py", "writer implementations", 412, 612, "Shows the complete pre-resolution writer implementation region ending with xlwt and lacking an xlsxwriter writer.", "class _OpenpyxlWriter", "register_writer(_XlwtWriter)", evidence_type="scoped_absence"),
        ],
        "supporting_units": [],
        "transitions": [
            transition("T1", "D", "E", "DataFrame.to_excel creates or uses an ExcelWriter."),
            transition("T2", "E", "R", "ExcelWriter resolves an engine through the registry."),
            transition("T3", "R", "X", "The registry can dispatch only to registered implementations, and xlsxwriter is absent."),
        ],
        "completeness_rule": "D, R, E, and the scoped absence X must jointly establish dispatch and the missing engine implementation.",
    },
    "microsoft-TypeScript-10020": {
        "oracle_kind": "causal_code_path",
        "mechanism_applicable": True,
        "mechanism_summary": "Organize Imports collects only top-level import declarations even though the compiler can identify ambient modules, so imports nested in those modules never enter grouping and edit generation.",
        "evidence_units": [
            unit("O", "src/services/organizeImports.ts", "OrganizeImports.organizeImports", 10, 57, "Collects, groups, rewrites, and deletes only sourceFile.statements imports; the TODO names ambient modules explicitly.", "function organizeImports", "TODO", "sourceFile.statements.filter(isImportDeclaration)"),
            unit("A", "src/compiler/utilities.ts", "isAmbientModule", 423, 433, "Provides the predicate that can identify string-named or global ambient modules.", "function isAmbientModule", "SyntaxKind.ModuleDeclaration"),
        ],
        "supporting_units": [],
        "transitions": [transition("T1", "A", "O", "Ambient modules are identifiable, but organizeImports never traverses their module blocks before grouping imports and creating edits.")],
        "completeness_rule": "A and O must both be present and the missing traversal between them must be explicit.",
    },
    "pandas-dev-pandas-14942": {
        "oracle_kind": "causal_code_path",
        "mechanism_applicable": True,
        "mechanism_summary": "Categorical groupby carries every category into grouping and later re-expands the Cartesian result space, even when only a small subset is observed.",
        "evidence_units": [
            unit("P", "pandas/core/generic.py", "NDFrame.groupby", 6601, 6668, "Exposes the public groupby entry point, which has no observed parameter and forwards no observed choice.", "def groupby", "return groupby(self", "squeeze=squeeze"),
            unit("C", "pandas/core/arrays/categorical.py", "Categorical._codes_for_groupby", 650, 689, "Returns category codes for grouping without an observed-only mode.", "def _codes_for_groupby(self, sort)"),
            unit("G", "pandas/core/groupby/groupby.py", "_GroupBy.__init__", 553, 590, "Builds the grouper without carrying an observed option.", "class _GroupBy", "_get_grouper(obj, keys"),
            unit("I", "pandas/core/groupby/groupby.py", "Grouping.__init__", 2874, 2990, "Recodes categorical groupers against the complete category set.", "class Grouping", "_codes_for_groupby(self.sort)"),
            unit("R", "pandas/core/groupby/groupby.py", "_GroupBy._reindex_output", 4690, 4725, "Re-expands results to the product of group levels.", "def _reindex_output", "This can re-expand the output space"),
        ],
        "supporting_units": [],
        "transitions": [
            transition("T0", "P", "G", "The public groupby entry point constructs GroupBy without an observed-only option."),
            transition("T1", "G", "I", "GroupBy construction delegates categorical grouping without an observed-only choice."),
            transition("T2", "I", "C", "Grouping obtains codes that retain the full category space."),
            transition("T3", "C", "R", "Those complete category levels are used to re-expand the output, producing the memory-heavy Cartesian product."),
        ],
        "completeness_rule": "P, C, G, I, and R must be present and expose the propagation from the public API through categorical codes to output re-expansion.",
    },
    "pandas-dev-pandas-16764": {
        "oracle_kind": "import_dependency_chain",
        "mechanism_applicable": True,
        "mechanism_summary": "Importing core pandas modules eagerly imports computation, plotting, and optional I/O dependencies before their features are used.",
        "evidence_units": [
            unit("F", "pandas/core/frame.py", "frame module imports", 65, 105, "Eagerly imports computation expression/eval and plotting modules while loading DataFrame.", "pandas.core.computation.expressions", "pandas.plotting._core"),
            unit("O", "pandas/core/ops.py", "ops module imports", 1, 25, "Eagerly imports the computation expression engine while loading arithmetic operations.", "pandas.core.computation.expressions as expressions"),
            unit("C", "pandas/core/computation/__init__.py", "computation package initialization", 1, 23, "Performs dependency checks and imports computation components at package import time.", evidence_type="source_range"),
            unit("P", "pandas/plotting/__init__.py", "plotting package initialization", 1, 19, "Imports plotting conversion, core, style, and tools modules eagerly.", "from pandas.plotting import _converter", "from pandas.plotting._core import boxplot"),
            unit("I", "pandas/io/common.py", "optional I/O imports", 1, 45, "Attempts optional cloud-filesystem imports while loading common I/O helpers.", "from s3fs import S3File"),
        ],
        "supporting_units": [],
        "transitions": [
            transition("T1", "F", "C", "Loading DataFrame imports the computation package before eval/query is invoked."),
            transition("T2", "F", "P", "Loading DataFrame imports plotting before any plot operation is requested."),
            transition("T3", "O", "C", "Loading arithmetic operations imports computation expressions before an arithmetic call needs them."),
            transition("T4", "F", "I", "The general import surface reaches optional I/O dependencies during module initialization."),
        ],
        "completeness_rule": "The selected evidence must expose each eager dependency branch F→C, F→P, O→C, and F→I; isolated imports are partial.",
    },
    "microsoft-TypeScript-10041": {
        "oracle_kind": "causal_code_path",
        "mechanism_applicable": True,
        "mechanism_summary": "Logical-or and conditional expressions reduce their alternatives directly through getUnionType, which can choose a less specific array type despite one alternative being assignable to the other.",
        "evidence_units": [
            unit("B", "src/compiler/checker.ts", "checkBinaryExpression", 12900, 13055, "Checks logical-or expressions and sends the two possible types directly to getUnionType.", "function checkBinaryExpression", "case SyntaxKind.BarBarToken", "getUnionType([removeDefinitelyFalsyTypes(leftType), rightType]"),
            unit("C", "src/compiler/checker.ts", "checkConditionalExpression", 13165, 13180, "Combines conditional branches through the same direct union reduction.", "function checkConditionalExpression", "getUnionType([type1, type2]"),
        ],
        "supporting_units": [],
        "transitions": [transition("T1", "B", "C", "Both choice-producing expressions share the same reduction rule and therefore the same subtype-selection defect.")],
        "completeness_rule": "B and C must show both affected choice paths and their common direct-union behavior.",
    },
    "microsoft-TypeScript-10473": {
        "oracle_kind": "event_delivery_chain",
        "mechanism_applicable": True,
        "mechanism_summary": "Configuration diagnostics are emitted only when the diagnostics array is non-empty, and Session separately gates the open-file event, so a config change that clears errors produces no event.",
        "evidence_units": [
            unit("P", "src/server/editorServices.ts", "ProjectService.reportConfigFileDiagnostics", 750, 770, "Suppresses configFileDiag when diagnostics is empty.", "reportConfigFileDiagnostics", "diagnostics.length > 0", 'eventName: "configFileDiag"'),
            unit("S", "src/server/session.ts", "Session constructor/handleEvent", 150, 205, "Creates the ProjectService event handler only when events are enabled and routes configFileDiag events.", "const eventHandler", "this.handleEvent(event)"),
            unit("O", "src/server/session.ts", "Session.openClientFile", 710, 730, "Emits the open-file config diagnostic only when configFileErrors is truthy.", "private openClientFile", "if (configFileErrors)"),
        ],
        "supporting_units": [],
        "transitions": [
            transition("T1", "P", "S", "ProjectService diagnostics reach Session only when the non-empty guard permits an event."),
            transition("T2", "O", "S", "The open-file path independently applies the same presence guard before event delivery."),
        ],
        "completeness_rule": "P, S, and O must establish both suppression points and the event-handler handoff.",
    },
    "microsoft-TypeScript-16278": {
        "oracle_kind": "api_protocol_chain",
        "mechanism_applicable": True,
        "mechanism_summary": "The old refactor API exposes applicable refactor names and then requests a whole refactor's code actions, without a distinct selected-action edit request and rename metadata contract.",
        "evidence_units": [
            unit("T", "src/services/types.ts", "LanguageService refactor contracts", 255, 375, "Defines applicable-refactor and getRefactorCodeActions contracts but no selected-action edit result.", "getApplicableRefactors", "getRefactorCodeActions", "interface ApplicableRefactorInfo"),
            unit("P", "src/services/refactorProvider.ts", "refactor registry/provider", 1, 59, "Finds applicable refactors and asks a named provider for code actions.", "registerRefactor", "getApplicableRefactors", "getRefactorCodeActions"),
            unit("L", "src/services/services.ts", "LanguageService refactor implementation", 1988, 2022, "Adapts the public LanguageService request into provider calls.", "function getApplicableRefactors", "function getRefactorCodeActions"),
            unit("Q", "src/server/protocol.ts", "refactor protocol contracts", 390, 448, "Defines discovery and whole-refactor code-action requests, with no selected-action edit command.", "GetApplicableRefactorsRequest", "GetRefactorCodeActionsRequest", "refactorName: string"),
            unit("S", "src/server/session.ts", "Session refactor commands", 1418, 1455, "Handles protocol requests and returns the refactor code actions.", "private getApplicableRefactors", "private getRefactorCodeActions"),
            unit("C", "src/server/client.ts", "SessionClient refactor adapter", 710, 745, "Sends the refactor request and converts returned code actions for the client.", "getApplicableRefactors", "getRefactorCodeActions"),
        ],
        "supporting_units": [],
        "transitions": [
            transition("T1", "C", "Q", "The client constructs the old refactor protocol request."),
            transition("T2", "Q", "S", "Session receives the discovery or whole-refactor code-action command."),
            transition("T3", "S", "L", "Session invokes the LanguageService refactor API."),
            transition("T4", "L", "P", "LanguageService delegates discovery/action generation to the registered refactor provider."),
            transition("T5", "P", "T", "Provider output is constrained by the old whole-refactor CodeAction contract."),
        ],
        "completeness_rule": "T, P, L, Q, S, and C must expose the end-to-end old API/protocol path and the missing selected-action edit boundary.",
    },
    "microsoft-TypeScript-19074": {
        "oracle_kind": "comment_only_maintenance",
        "mechanism_applicable": False,
        "mechanism_summary": "The change updates stale LSHost terminology in comments without altering runtime behavior.",
        "evidence_units": [
            unit("M", "src/compiler/moduleNameResolver.ts", "loadModuleFromGlobalCache comment", 1484, 1494, "Contains the stale LSHost terminology in the resolver comment.", "LSHost may load a module"),
            unit("P", "src/server/project.ts", "external-file comment", 946, 960, "Contains the stale LSHost terminology in the project comment.", "by the LSHost for files"),
        ],
        "supporting_units": [],
        "transitions": [],
        "completeness_rule": "Both comment sites define the maintenance surface; the case is excluded from mechanism-transition rates.",
        "applicability_note": "No executable source transition changes.",
    },
    "microsoft-TypeScript-24625": {
        "oracle_kind": "api_type_surface",
        "mechanism_applicable": False,
        "mechanism_summary": "Three watch-builder factory overloads require rootNames and options even though the CreateProgram callback contract can supply undefined values.",
        "evidence_units": [
            unit("B", "src/compiler/builder.ts", "builder factory overloads", 545, 577, "Shows the required rootNames/options parameters on all three builder factories.", "createSemanticDiagnosticsBuilderProgram(rootNames: ReadonlyArray<string>", "createEmitAndSemanticDiagnosticsBuilderProgram(rootNames: ReadonlyArray<string>", "createAbstractBuilder(rootNames: ReadonlyArray<string>"),
        ],
        "supporting_units": [],
        "transitions": [],
        "completeness_rule": "B must expose all three incompatible overloads; the case is an API type-surface defect rather than a source-transition case.",
        "applicability_note": "The resolution widens type signatures and does not alter the builder execution path.",
    },
    "microsoft-TypeScript-35468": {
        "oracle_kind": "state_identity_chain",
        "mechanism_applicable": True,
        "mechanism_summary": "Incremental builder state keys dependency, signature, affected-file, and emit maps by sourceFile.path even though project-reference aliases require the canonical resolvedPath identity.",
        "evidence_units": [
            unit("I", "src/compiler/builderState.ts", "BuilderState.create", 120, 235, "Builds file information and reference/export maps using sourceFile.path.", "sourceFile.path", "fileInfos.set(sourceFile.path"),
            unit("U", "src/compiler/builderState.ts", "updateShapeSignature", 304, 370, "Reads and updates signature/export caches using sourceFile.path.", "function updateShapeSignature", "fileInfos.get(sourceFile.path", "cacheToUpdateSignature.set(sourceFile.path"),
            unit("A", "src/compiler/builderState.ts", "affected-file traversal", 405, 560, "Seeds and deduplicates affected-file traversal with path rather than resolvedPath.", "const queue = [sourceFile.path]", "seenFileNamesMap.set(sourceFileWithUpdatedShape.path"),
            unit("E", "src/compiler/builder.ts", "builder affected/emit state", 315, 425, "Uses affectedFile.path for semantic-diagnostic and emit bookkeeping.", "seenAffectedFiles", "affectedFile.path", "seenEmittedFiles"),
        ],
        "supporting_units": [],
        "transitions": [
            transition("T1", "I", "U", "The identity chosen while building state is reused for signature lookup and updates."),
            transition("T2", "U", "A", "Signature changes drive dependency traversal keyed by the same non-canonical path."),
            transition("T3", "A", "E", "Affected files enter diagnostic and emit bookkeeping under that inconsistent identity."),
        ],
        "completeness_rule": "I, U, A, and E must show the same path identity crossing state creation, signature update, dependency propagation, and emission.",
    },
    "microsoft-TypeScript-46770": {
        "oracle_kind": "causal_code_path",
        "mechanism_applicable": True,
        "mechanism_summary": "NodeNext package resolution keeps ESM-mode extension rules active while resolving the main field of a CommonJS package, so an extensionless main target is rejected.",
        "evidence_units": [
            unit("R", "src/compiler/moduleNameResolver.ts", "loadNodeModuleFromDirectoryWorker", 1784, 1826, "Reads package fields and resolves the selected package path with the unchanged NodeNext feature state.", "function loadNodeModuleFromDirectoryWorker", "readPackageJsonMainField", "nodeLoadModuleByRelativeName(nextExtensions"),
        ],
        "supporting_units": [],
        "transitions": [transition("T1", "R", "R", "The package main value is handed to relative-name resolution without disabling ESM-mode rules for a CommonJS package.")],
        "completeness_rule": "R must show package-main selection, the retained feature state, and the relative-name resolution call.",
    },
    "microsoft-TypeScript-52695": {
        "oracle_kind": "causal_code_path",
        "mechanism_applicable": True,
        "mechanism_summary": "Node-module resolution performs file probes for URI-like specifiers and package-root candidates before directory/package handling, producing avoidable filesystem stat calls.",
        "evidence_units": [
            unit("N", "src/compiler/moduleNameResolver.ts", "nodeModuleNameResolverWorker", 1706, 1820, "Falls through unresolved non-relative names into node_modules lookup without rejecting URI-like names.", "function nodeModuleNameResolverWorker", "Loading_module_0_from_node_modules_folder"),
            unit("L", "src/compiler/moduleNameResolver.ts", "loadModuleFromSpecificNodeModulesDirectory", 2868, 2910, "Probes the package-root candidate as a file before loading it as a directory/package.", "function loadModuleFromSpecificNodeModulesDirectory", "loadModuleFromFile(extensions, candidate"),
        ],
        "supporting_units": [],
        "transitions": [transition("T1", "N", "L", "Unfiltered module names reach node_modules resolution, whose loader performs the unnecessary file probe.")],
        "completeness_rule": "N and L must jointly show the unfiltered entry and the unnecessary file probe.",
    },
    "pandas-dev-pandas-10150": {
        "oracle_kind": "causal_code_path",
        "mechanism_applicable": True,
        "mechanism_summary": "The value_counts wrapper delegates to algorithms.value_counts, which converts away the input object's name and constructs the count Series unnamed; index reconstruction then incorrectly applies the original name to the result index.",
        "evidence_units": [
            unit("A", "pandas/core/algorithms.py", "algorithms.value_counts", 176, 255, "Converts the input to raw values and constructs the result Series without preserving its name.", "def value_counts", "values = Series(values).values", "result = Series(counts"),
            unit("B", "pandas/core/base.py", "IndexOpsMixin.value_counts", 399, 445, "Calls algorithms.value_counts and uses self.name when rebuilding Period/Datetime indexes.", "def value_counts", "from pandas.core.algorithms import value_counts", "self._simple_new(result.index.values, self.name"),
        ],
        "supporting_units": [],
        "transitions": [transition("T1", "B", "A", "The public wrapper passes the named object into algorithms.value_counts, where conversion and result construction lose the name before the wrapper rebuilds the index.")],
        "completeness_rule": "A and B must expose both the delegation and the two inconsistent name assignments.",
    },
    "pandas-dev-pandas-16499": {
        "oracle_kind": "test_discovery_surface",
        "mechanism_applicable": False,
        "mechanism_summary": "Pytest cannot collect the ujson test groups because their class names do not begin with Test.",
        "evidence_units": [
            unit("U", "pandas/tests/io/json/test_ujson.py", "UltraJSONTests", 25, 45, "Defines the first uncollectable test class.", "class UltraJSONTests", partial_start=30, partial_end=946),
            unit("N", "pandas/tests/io/json/test_ujson.py", "NumpyJSONTests", 940, 965, "Defines the NumPy ujson tests under an uncollectable class name.", "class NumpyJSONTests", partial_start=947, partial_end=1222),
            unit("P", "pandas/tests/io/json/test_ujson.py", "PandasJSONTests", 1218, 1240, "Defines the pandas-object ujson tests under an uncollectable class name.", "class PandasJSONTests", partial_start=1223, partial_end=1642),
        ],
        "supporting_units": [],
        "transitions": [],
        "completeness_rule": "U, N, and P must all be present to cover the test-discovery defect; the case is excluded from runtime transition rates.",
        "applicability_note": "The repository's pytest collector implementation is external to this snapshot, so there is no internal source handoff to score.",
    },
    "pandas-dev-pandas-22698": {
        "oracle_kind": "causal_code_path",
        "mechanism_applicable": True,
        "mechanism_summary": "Index comparison deliberately records and suppresses NumPy's invalid-elementwise-comparison FutureWarning before returning the comparison result.",
        "evidence_units": [
            unit("C", "pandas/core/indexes/base.py", "Index comparison cmp_method", 60, 95, "Wraps the NumPy comparison in a warning-catching block that ignores FutureWarning.", "def cmp_method", "warnings.catch_warnings(record=True)", 'warnings.filterwarnings("ignore", "elementwise", FutureWarning)'),
        ],
        "supporting_units": [],
        "transitions": [transition("T1", "C", "C", "NumPy emits the warning inside a catch-and-ignore scope, preventing it from reaching the Series/Index constructor caller.")],
        "completeness_rule": "C must show both the comparison and the warning-suppression scope.",
    },
    "pandas-dev-pandas-22872": {
        "oracle_kind": "static_cleanup",
        "mechanism_applicable": False,
        "mechanism_summary": "Both repository lint configurations explicitly ignore E722, permitting bare except clauses in the test suite.",
        "evidence_units": [
            unit("S", "setup.cfg", "pycodestyle ignore list", 10, 25, "Disables E722 for the repository lint configuration.", "E722,  # do not use bare except"),
            unit("P", ".pep8speaks.yml", "pep8speaks ignore list", 8, 20, "Disables E722 for the review-bot lint configuration.", "E722,  # do not use bare except"),
        ],
        "supporting_units": [],
        "transitions": [],
        "completeness_rule": "S and P define the policy surface; the individual one-off test cleanups are not treated as a runtime mechanism.",
        "applicability_note": "This is a static style cleanup, not an executable repository mechanism.",
    },
    "pandas-dev-pandas-25183": {
        "oracle_kind": "causal_code_path",
        "mechanism_applicable": True,
        "mechanism_summary": "Concat reindexing treats an all-missing extension block like a NumPy block and replaces it with an array of the common empty dtype, losing the nullable Int64 extension dtype during merge.",
        "evidence_units": [
            unit("J", "pandas/core/internals/concat.py", "JoinUnit.get_reindexed_values", 165, 215, "Shows the missing-value branch and its NumPy replacement array, without an extension-block exemption.", "def get_reindexed_values", "missing_arr = np.empty", "missing_arr.fill(fill_value)"),
        ],
        "supporting_units": [],
        "transitions": [transition("T1", "J", "J", "An empty extension-backed join unit enters the generic missing-array construction and emerges with the common NumPy dtype.")],
        "completeness_rule": "J must expose the extension-block input condition and the generic replacement-array branch.",
    },
    "pandas-dev-pandas-32289": {
        "oracle_kind": "diagnostic_path",
        "mechanism_applicable": True,
        "mechanism_summary": "DataFrame construction converts each nested value with np.asarray, then rejects non-two-dimensional results with a generic error that omits the observed shape.",
        "evidence_units": [
            unit("C", "pandas/core/internals/construction.py", "to_arrays.convert", 290, 328, "Converts list elements and raises the generic dimensionality error.", "def convert(v)", "return maybe_convert_platform(v)", 'raise ValueError("Must pass 2-d input")'),
        ],
        "supporting_units": [],
        "transitions": [transition("T1", "C", "C", "The converted array's ndim triggers an error response that discards the shape information needed to diagnose the constructor failure.")],
        "completeness_rule": "C must show conversion, the dimensionality check, and the generic error.",
    },
    "pandas-dev-pandas-35925": {
        "oracle_kind": "formatting_migration",
        "mechanism_applicable": False,
        "mechanism_summary": "The repository pins Black 19.10b0; updating the formatter changes accepted trailing-comma formatting across many otherwise unrelated files.",
        "evidence_units": [
            unit("B", ".pre-commit-config.yaml", "Black pre-commit hook", 1, 7, "Pins the formatter version that motivates the mechanical source rewrite.", "repo: https://github.com/python/black", "rev: 19.10b0"),
        ],
        "supporting_units": [],
        "transitions": [],
        "completeness_rule": "B identifies the maintenance cause; mechanical formatting edits are not scored as a source mechanism.",
        "applicability_note": "This case is a formatter migration with no coherent runtime transition.",
    },
    "pandas-dev-pandas-36617": {
        "oracle_kind": "documentation_cleanup",
        "mechanism_applicable": False,
        "mechanism_summary": "The rst-backticks hook excludes a named set of documentation files, leaving their single-backtick markup outside automated enforcement.",
        "evidence_units": [
            unit("R", ".pre-commit-config.yaml", "rst-backticks hook", 33, 53, "Shows the documentation hook and its explicit exclusion list.", "id: rst-backticks", "exclude: (?x)("),
        ],
        "supporting_units": [],
        "transitions": [],
        "completeness_rule": "R defines the maintenance scope; the case is excluded from mechanism-transition rates.",
        "applicability_note": "The resolution is a documentation-wide markup cleanup plus removal of exclusions.",
    },
    "vuejs-vue-10004": {
        "oracle_kind": "lifecycle_cleanup_chain",
        "mechanism_applicable": True,
        "mechanism_summary": "DOM listeners are reconciled on create/update only; destroying a deactivated component has no hook that reuses the old element to remove stale v-model listeners.",
        "evidence_units": [
            unit("E", "src/platforms/web/runtime/modules/events.js", "updateDOMListeners/module hooks", 100, 120, "Targets vnode.elm and exports only create/update hooks, leaving no destroy cleanup path.", "function updateDOMListeners", "target = vnode.elm", "create: updateDOMListeners", "update: updateDOMListeners"),
        ],
        "supporting_units": [],
        "transitions": [transition("T1", "E", "E", "Listener reconciliation has no destroy lifecycle entry and cannot target oldVnode.elm when vnode.elm is absent.")],
        "completeness_rule": "E must show target selection and the missing destroy hook together.",
    },
    "vuejs-vue-11718": {
        "oracle_kind": "compatibility_adapter_chain",
        "mechanism_applicable": True,
        "mechanism_summary": "The SSR webpack plugins assume webpack 4's emit hook, string entry assets, space-suffixed module hashes, and the legacy libraryTarget shape.",
        "evidence_units": [
            unit("U", "src/server/webpack-plugin/util.js", "validate/onEmit", 1, 34, "Validates legacy output.libraryTarget and selects only legacy or webpack-4 emit hooks.", "export const validate", "output.libraryTarget", "export const onEmit", "compiler.hooks.emit.tapAsync"),
            unit("C", "src/server/webpack-plugin/client.js", "VueSSRClientPlugin.apply", 1, 55, "Passes webpack stats assets/module identifiers through string-only assumptions.", "onEmit(compiler, 'vue-client-plugin'", "m.identifier.replace(/\\s\\w+$/"),
            unit("S", "src/server/webpack-plugin/server.js", "VueSSRServerPlugin.apply", 1, 60, "Filters entry assets and consumes stats.assets under webpack-4 shapes.", "onEmit(compiler, 'vue-server-plugin'", "entryInfo.assets.filter(isJS)", "stats.assets.forEach"),
        ],
        "supporting_units": [],
        "transitions": [
            transition("T1", "C", "U", "The client plugin delegates emission through the legacy hook adapter."),
            transition("T2", "S", "U", "The server plugin delegates through the same adapter and legacy output validation."),
            transition("T3", "U", "C", "Webpack output then reaches client manifest construction under string/hash assumptions."),
            transition("T4", "U", "S", "Webpack output reaches server bundle construction under legacy asset shapes."),
        ],
        "completeness_rule": "U, C, and S must expose the shared hook/validation boundary and both consumers' incompatible data-shape assumptions.",
    },
    "vuejs-vue-11782": {
        "oracle_kind": "dependency_configuration",
        "mechanism_applicable": False,
        "mechanism_summary": "The test toolchain pins an http-server version whose command behavior is incompatible with the Windows test workflow.",
        "evidence_units": [
            unit("H", "package.json", "http-server development dependency", 96, 108, "Pins the incompatible test-server version.", '"http-server": "^0.11.1"'),
        ],
        "supporting_units": [],
        "transitions": [],
        "completeness_rule": "H defines the dependency configuration; external package behavior is not a repository source transition.",
        "applicability_note": "The fix is a dependency upgrade, while the failing behavior resides in the external package.",
    },
    "vuejs-vue-13052": {
        "oracle_kind": "dependency_configuration",
        "mechanism_applicable": False,
        "mechanism_summary": "The compiler-sfc package has no explicit optional Prettier dependency range, leaving compatibility to an undeclared host installation.",
        "evidence_units": [
            unit("P", "packages/compiler-sfc/package.json", "compiler-sfc dependency metadata", 1, 34, "Shows the package dependency scope in which a compatible Prettier range is absent.", '"name": "@vue/compiler-sfc"', evidence_type="scoped_absence"),
        ],
        "supporting_units": [],
        "transitions": [],
        "completeness_rule": "P must establish the missing package dependency declaration; the case is excluded from source-transition rates.",
        "applicability_note": "The resolution changes package metadata rather than a source execution path.",
    },
    "vuejs-vue-5884": {
        "oracle_kind": "causal_code_path",
        "mechanism_applicable": True,
        "mechanism_summary": "Vue.set recognizes only numeric-typed array keys, so a numeric string bypasses splice-based reactive array assignment and follows object-property handling.",
        "evidence_units": [
            unit("S", "src/core/observer/index.js", "set", 185, 225, "Branches to array splice only when key has JavaScript number type.", "export function set", "Array.isArray(target) && typeof key === 'number'", "target.splice(key, 1, val)"),
        ],
        "supporting_units": [],
        "transitions": [transition("T1", "S", "S", "A numeric-string key fails the array-index guard and therefore misses the splice/reactivity path.")],
        "completeness_rule": "S must show the key guard, splice path, and fall-through context.",
    },
    "vuejs-vue-6097": {
        "oracle_kind": "configuration_runtime_chain",
        "mechanism_applicable": True,
        "mechanism_summary": "Inject options normalize only array syntax into plain provider-name strings, and runtime resolution treats every normalized entry as a required provider key with no default path.",
        "evidence_units": [
            unit("N", "src/core/util/options.js", "normalizeInject", 265, 282, "Normalizes array entries to strings and has no object/default representation.", "function normalizeInject", "normalized[inject[i]] = inject[i]"),
            unit("R", "src/core/instance/inject.js", "resolveInject", 39, 67, "Uses the normalized value directly as provideKey and warns when no provider is found.", "function resolveInject", "const provideKey = inject[key]", "Injection \"${key}\" not found"),
        ],
        "supporting_units": [],
        "transitions": [transition("T1", "N", "R", "Normalized inject entries are consumed as bare provider keys, leaving no place for a default value to survive into resolution.")],
        "completeness_rule": "N and R must expose the option normalization and runtime missing-provider path.",
    },
    "vuejs-vue-8528": {
        "oracle_kind": "comment_only_maintenance",
        "mechanism_applicable": False,
        "mechanism_summary": "The requested change rewrites explanatory comments for shared utility functions without changing their implementations.",
        "evidence_units": [
            unit("U", "src/shared/util.js", "shared utility comments", 1, 308, "Contains the utility implementations and the comment surface revised by the resolution.", "export function isUndef", "export function looseEqual"),
        ],
        "supporting_units": [],
        "transitions": [],
        "completeness_rule": "U identifies the documentation surface; this case has no executable transition to score.",
        "applicability_note": "The pull request changes comments only.",
    },
    "vuejs-vue-9042": {
        "oracle_kind": "causal_code_path",
        "mechanism_applicable": True,
        "mechanism_summary": "On IE, assigning any placeholder to an input or textarea installs a one-shot input-event blocker; an empty textarea placeholder therefore consumes the first real user input event.",
        "evidence_units": [
            unit("A", "src/platforms/web/runtime/modules/attrs.js", "baseSetAttr", 88, 115, "Sets the placeholder attribute and installs the IE input blocker for both input and textarea without excluding the empty value.", "function baseSetAttr", "el.tagName === 'TEXTAREA' || el.tagName === 'INPUT'", "e.stopImmediatePropagation()"),
        ],
        "supporting_units": [],
        "transitions": [transition("T1", "A", "A", "The empty placeholder assignment creates a blocker whose next input event is stopped before v-model can retain the user's change.")],
        "completeness_rule": "A must show the empty-placeholder-eligible guard and the stopped input event.",
    },
    "vuejs-vue-9842": {
        "oracle_kind": "lifecycle_state_chain",
        "mechanism_applicable": True,
        "mechanism_summary": "KeepAlive stores the rendered VNode in its cache immediately, while transition patching can still replace its component instance; later pruning destroys the stale cached instance and leaves the live instance retained.",
        "evidence_units": [
            unit("P", "src/core/components/keep-alive.js", "pruneCache/pruneCacheEntry", 20, 55, "Reads cached VNodes and destroys the cached component instance when pruning.", "function pruneCache", "function pruneCacheEntry", "cached.componentInstance.$destroy()"),
            unit("L", "src/core/components/keep-alive.js", "KeepAlive lifecycle", 60, 82, "Initializes and prunes the cache but has no mounted/updated cache-commit step.", "created ()", "mounted ()", evidence_type="scoped_absence"),
            unit("R", "src/core/components/keep-alive.js", "KeepAlive.render", 83, 124, "Writes the current VNode directly into the cache during render.", "render ()", "cache[key] = vnode", "vnode.data.keepAlive = true"),
        ],
        "supporting_units": [],
        "transitions": [
            transition("T1", "R", "L", "Render commits the pre-patch VNode immediately instead of deferring cache commitment until mounted/updated."),
            transition("T2", "L", "P", "Later include/exclude or capacity pruning reads that stale cache entry and destroys its component instance."),
        ],
        "completeness_rule": "R, L, and P must jointly expose immediate cache storage, the missing post-update commit boundary, and stale-entry destruction.",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-root", type=Path, default=Path(r"C:\Programming\guidedInteligence_testcases"))
    parser.add_argument("--output", type=Path, default=HERE / "source-transition-oracle.json")
    parser.add_argument("--markdown", type=Path, default=HERE / "source-transition-oracle.md")
    return parser.parse_args()


def build_case(case_id: str, curated: dict, test_root: Path) -> dict:
    case_root = test_root / case_id
    verification = json.loads((case_root / "verification.json").read_text(encoding="utf-8"))
    snapshots = [path.name for path in (case_root / "s").iterdir() if path.is_dir()]
    if len(snapshots) != 1:
        raise ValueError(f"{case_id}: expected one snapshot, found {snapshots}")
    prs = verification["resolution_artifacts"].get("github_prs", [])
    resolution = [
        {
            "number": pr["number"],
            "title": pr["title"],
            "url": pr["url"],
            "base_sha": pr.get("base_sha", ""),
            "head_sha": pr.get("head_sha", ""),
        }
        for pr in prs
    ]
    curated = copy.deepcopy(curated)
    snapshot_root = case_root / "s" / snapshots[0]
    for section in ("evidence_units", "supporting_units"):
        for evidence in curated.get(section, []):
            source = evidence["source"]
            path = snapshot_root / Path(source["path"])
            if not path.is_file():
                source["source_presence"] = "absent"
                source["sha256"] = None
                continue
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            text = "\n".join(lines[source["line_start"] - 1 : source["line_end"]])
            source["source_presence"] = "present"
            source["sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()

    required_paths = {
        evidence["source"]["path"]
        for evidence in curated["evidence_units"]
        if evidence.get("required", True) and evidence["source"].get("source_presence") == "present"
    }
    connected_pairs = {
        (item["from"], item["to"])
        for item in curated.get("transitions", [])
        if item.get("required", True) and item.get("from") != item.get("to")
    }
    implementation_oracle_files = [normalize.replace("\\", "/") for normalize in verification["oracle"]["implementation_files"]]

    return {
        "case_id": case_id,
        "repository": verification["repository"],
        "issue_number": verification["issue_number"],
        "title": verification["title"],
        "review_status": "validated_for_scoring",
        "pre_resolution": {"snapshot": snapshots[0]},
        "resolution_oracle": resolution,
        "connected_required_evidence": len(curated["evidence_units"]) > 1 and bool(connected_pairs),
        "required_file_count": len(required_paths),
        "implementation_oracle_files": implementation_oracle_files,
        "implementation_oracle_file_count": len(implementation_oracle_files),
        **curated,
        "oracle_revision": 1,
    }


def render_markdown(data: dict) -> str:
    lines = [
        "# Required-evidence reference review",
        "",
        f"Campaign cases: **{len(data['cases'])}**. Mechanism-applicable: **{sum(c['mechanism_applicable'] for c in data['cases'])}**. Non-mechanistic/source-surface cases: **{sum(not c['mechanism_applicable'] for c in data['cases'])}**.",
        "",
        "This document is generated from `source-transition-oracle.json`. Only required units are scored; supporting units are retained as contextual notes.",
        "",
    ]
    for case in data["cases"]:
        lines.extend(
            [
                f"## {case['case_id']}",
                "",
                f"**{case['title']}**  ",
                f"Kind: `{case['oracle_kind']}`; connected required evidence: `{str(case['connected_required_evidence']).lower()}`; required files: `{case['required_file_count']}`; snapshot: `{case['pre_resolution']['snapshot']}`.",
                "",
                case["mechanism_summary"],
                "",
                "| Role | ID | Source | Responsibility |",
                "|---|---|---|---|",
            ]
        )
        for role, key in (("R", "evidence_units"), ("S", "supporting_units")):
            for evidence in case[key]:
                source = evidence["source"]
                lines.append(
                    f"| {role} | `{evidence['id']}` | `{source['path']}:{source['line_start']}-{source['line_end']}` (`{source['symbol']}`) | {evidence['description']} |"
                )
        lines.extend(["", "Required transitions:", ""])
        if case["transitions"]:
            for item in case["transitions"]:
                lines.append(f"- `{item['id']}` `{item['from']} → {item['to']}`: {item['description']}")
        else:
            lines.append(f"- None. {case.get('applicability_note', 'This case has no directed source transition.')}")
        lines.extend(["", f"Completeness: {case['completeness_rule']}", ""])
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    case_ids = list(dict.fromkeys(run["case"] for run in inventory["run_inventory"]))
    missing = [case_id for case_id in case_ids if case_id not in CASES]
    extra = [case_id for case_id in CASES if case_id not in case_ids]
    if missing or extra:
        raise ValueError(f"curation mismatch: missing={missing}, extra={extra}")
    data = {
        "schema_version": 2,
        "oracle_name": "final-september-required-evidence-reference",
        "review_status": "validated_for_scoring",
        "campaign_inventory": "testing/codeRepoQA/statistics/runs/2026-09-16-five-mode-four-runs.json",
        "construction_policy": {
            "source_state": "pre_resolution_snapshot_only",
            "resolution_use": "identify_required_pre_resolution_evidence_only",
            "file_presence_is_not_snippet_presence": True,
            "run_outcomes_used_to_define_oracle": False,
        },
        "cases": [build_case(case_id, CASES[case_id], args.test_root) for case_id in case_ids],
    }
    args.output.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    args.markdown.write_text(render_markdown(data), encoding="utf-8")
    print(f"Wrote {len(data['cases'])} cases to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
