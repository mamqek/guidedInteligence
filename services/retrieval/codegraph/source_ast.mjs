import fs from "node:fs";
import path from "node:path";
import ts from "typescript";


const SUPPORTED_EXTENSIONS = new Set([".ts", ".tsx", ".js", ".jsx", ".mts", ".cts", ".mjs", ".cjs"]);
const MAX_EXCERPT_LINES = 60;
const ANCHOR_CONTEXT_LINES = 12;


function normalizePath(value) {
  return String(value || "").replaceAll("\\", "/").replace(/^\.\//, "");
}


function lineOf(sourceFile, position) {
  return sourceFile.getLineAndCharacterOfPosition(position).line + 1;
}


function propertyNameText(name, sourceFile) {
  if (!name) return "";
  if (ts.isIdentifier(name) || ts.isPrivateIdentifier(name) || ts.isStringLiteral(name) || ts.isNumericLiteral(name)) {
    return String(name.text || "");
  }
  return name.getText(sourceFile);
}


function assignedFunctionName(node, sourceFile) {
  if (!ts.isArrowFunction(node) && !ts.isFunctionExpression(node)) return "";
  if (node.name) return propertyNameText(node.name, sourceFile);
  const parent = node.parent;
  if (ts.isVariableDeclaration(parent)) return propertyNameText(parent.name, sourceFile);
  if (ts.isPropertyAssignment(parent) || ts.isPropertyDeclaration(parent)) return propertyNameText(parent.name, sourceFile);
  return "";
}


function stableAssignmentPath(expression, sourceFile) {
  if (ts.isIdentifier(expression)) return expression.text;
  if (ts.isPropertyAccessExpression(expression)) {
    const base = stableAssignmentPath(expression.expression, sourceFile);
    return base ? `${base}.${expression.name.text}` : "";
  }
  if (
    ts.isElementAccessExpression(expression)
    && expression.argumentExpression
    && (ts.isStringLiteral(expression.argumentExpression) || ts.isNumericLiteral(expression.argumentExpression))
  ) {
    const base = stableAssignmentPath(expression.expression, sourceFile);
    return base ? `${base}.${String(expression.argumentExpression.text || "")}` : "";
  }
  return "";
}


export function resolveSourceOwners(projectRoot, args) {
  const sourcePath = normalizePath(args.path || args.file);
  const requestedStart = Math.max(1, Number(args.line_start || 1));
  const requestedEnd = Math.max(requestedStart, Number(args.line_end || requestedStart));
  const extension = path.extname(sourcePath).toLowerCase();
  const base = {
    source_path: sourcePath,
    line_start: requestedStart,
    line_end: requestedEnd,
    adapter: SUPPORTED_EXTENSIONS.has(extension) ? "typescript_compiler_api" : "unsupported",
    owners: [],
  };
  if (!SUPPORTED_EXTENSIONS.has(extension)) return { ...base, status: "unsupported" };
  let source;
  try {
    source = fs.readFileSync(path.join(projectRoot, sourcePath), "utf8");
  } catch {
    return { ...base, status: "failed", reason: "source_unreadable" };
  }
  const scriptKind = extension === ".tsx" ? ts.ScriptKind.TSX
    : extension === ".jsx" ? ts.ScriptKind.JSX
      : [".js", ".mjs", ".cjs"].includes(extension) ? ts.ScriptKind.JS
        : ts.ScriptKind.TS;
  const sourceFile = ts.createSourceFile(sourcePath, source, ts.ScriptTarget.Latest, true, scriptKind);
  const owners = [];
  function visit(node) {
    if (
      ts.isBinaryExpression(node)
      && node.operatorToken.kind === ts.SyntaxKind.EqualsToken
      && (ts.isFunctionExpression(node.right) || ts.isArrowFunction(node.right))
      && ts.isExpressionStatement(node.parent)
      && ts.isSourceFile(node.parent.parent)
    ) {
      const name = stableAssignmentPath(node.left, sourceFile);
      const start = lineOf(sourceFile, node.parent.getStart(sourceFile));
      const end = lineOf(sourceFile, node.parent.end);
      if (name && start <= requestedEnd && end >= requestedStart) {
        owners.push({
          id: `source_owner:${sourcePath}:${start}:${end}`,
          kind: "assigned_function",
          name,
          qualified_name: name,
          path: sourcePath,
          line_start: start,
          line_end: end,
          language: "typescript",
          adapter: "typescript_compiler_api",
          decision_code: "direct_top_level_function_assignment",
        });
      }
    }
    ts.forEachChild(node, visit);
  }
  visit(sourceFile);
  return { ...base, status: "ok", owners };
}


function executableIdentity(node, sourceFile) {
  if (ts.isFunctionDeclaration(node) && node.name) {
    return { kind: "function", name: node.name.text };
  }
  if (ts.isMethodDeclaration(node)) {
    return { kind: "method", name: propertyNameText(node.name, sourceFile) };
  }
  if (ts.isConstructorDeclaration(node)) {
    return { kind: "constructor", name: "constructor" };
  }
  if (ts.isGetAccessorDeclaration(node)) {
    return { kind: "getter", name: propertyNameText(node.name, sourceFile) };
  }
  if (ts.isSetAccessorDeclaration(node)) {
    return { kind: "setter", name: propertyNameText(node.name, sourceFile) };
  }
  const assignedName = assignedFunctionName(node, sourceFile);
  if (assignedName) return { kind: "assigned_function", name: assignedName };
  return null;
}


function classOwner(node, sourceFile) {
  let current = node.parent;
  while (current && !ts.isSourceFile(current)) {
    if ((ts.isClassDeclaration(current) || ts.isClassExpression(current)) && current.name) {
      return current.name.text;
    }
    current = current.parent;
  }
  return "";
}


function qualifiedOwnerName(node, identity, sourceFile) {
  const className = classOwner(node, sourceFile);
  return className ? `${className}.${identity.name}` : identity.name;
}


function outermostNamedExecutable(call, sourceFile) {
  const owners = [];
  let current = call.parent;
  let nestingDepth = 0;
  while (current && !ts.isSourceFile(current)) {
    if (ts.isFunctionLike(current)) {
      const identity = executableIdentity(current, sourceFile);
      if (identity) {
        owners.push({ node: current, identity, nesting_depth: nestingDepth });
      }
      nestingDepth += 1;
    }
    current = current.parent;
  }
  return owners.length ? owners[owners.length - 1] : null;
}


function calledName(expression) {
  if (ts.isIdentifier(expression)) {
    return { name: expression.text, qualifier: "", expression_kind: "identifier" };
  }
  if (ts.isPropertyAccessExpression(expression)) {
    return {
      name: expression.name.text,
      qualifier: expression.expression.getText(),
      expression_kind: "property_access",
    };
  }
  if (ts.isElementAccessExpression(expression) && expression.argumentExpression && ts.isStringLiteral(expression.argumentExpression)) {
    return {
      name: expression.argumentExpression.text,
      qualifier: expression.expression.getText(),
      expression_kind: "element_access",
    };
  }
  return { name: "", qualifier: "", expression_kind: "dynamic" };
}


function calledNames(expression) {
  if (ts.isParenthesizedExpression(expression) || ts.isAsExpression(expression) || ts.isNonNullExpression(expression)) {
    return calledNames(expression.expression);
  }
  if (ts.isConditionalExpression(expression)) {
    return [
      ...calledNames(expression.whenTrue).map((item) => ({ ...item, expression_kind: `conditional_${item.expression_kind}` })),
      ...calledNames(expression.whenFalse).map((item) => ({ ...item, expression_kind: `conditional_${item.expression_kind}` })),
    ];
  }
  const single = calledName(expression);
  return single.name ? [single] : [];
}


function matchingCodeGraphOwner(codegraph, sourcePath, owner, sourceFile) {
  const ownerStart = lineOf(sourceFile, owner.node.getStart(sourceFile));
  const ownerEnd = lineOf(sourceFile, owner.node.end);
  const expected = owner.identity.name;
  const nodes = codegraph.getNodesInFile(sourcePath)
    .filter((node) => {
      if (["file", "import"].includes(node.kind)) return false;
      const start = Number(node.startLine || 0);
      const end = Number(node.endLine || start);
      return start > 0 && start <= ownerStart && end >= ownerEnd;
    })
    .sort((left, right) => {
      const leftName = String(left.name || "") === expected ? 0 : 1;
      const rightName = String(right.name || "") === expected ? 0 : 1;
      const leftSpan = Number(left.endLine || left.startLine || 0) - Number(left.startLine || 0);
      const rightSpan = Number(right.endLine || right.startLine || 0) - Number(right.startLine || 0);
      return leftName - rightName || leftSpan - rightSpan;
    });
  return nodes[0] || null;
}


function hasExactCodeGraphCall(codegraph, ownerNode, targetNode) {
  if (!ownerNode || !targetNode) return false;
  return codegraph.getOutgoingEdges(ownerNode.id).some(
    (edge) => edge.kind === "calls" && edge.target === targetNode.id,
  );
}


function reliabilityFor(expressionKind, exactCodeGraphCall) {
  if (exactCodeGraphCall) {
    return { tier: 4, code: "exact_codegraph_function_call" };
  }
  if (expressionKind === "identifier" || expressionKind === "conditional_identifier") {
    return { tier: 3, code: "ast_unqualified_target_call" };
  }
  if (expressionKind === "property_access") {
    return { tier: 2, code: "ast_property_target_call" };
  }
  return { tier: 1, code: "ast_literal_element_target_call" };
}


function excerptRange(ownerStart, ownerEnd, anchorStart, anchorEnd) {
  const anchorContextStart = Math.max(ownerStart, anchorStart - ANCHOR_CONTEXT_LINES);
  const anchorContextEnd = Math.min(ownerEnd, anchorEnd + ANCHOR_CONTEXT_LINES);
  if (ownerEnd - ownerStart + 1 <= MAX_EXCERPT_LINES) {
    return { line_start: ownerStart, line_end: ownerEnd, includes_owner_signature: true };
  }
  if (anchorContextEnd - ownerStart + 1 <= MAX_EXCERPT_LINES) {
    return { line_start: ownerStart, line_end: anchorContextEnd, includes_owner_signature: true };
  }
  return {
    line_start: anchorContextStart,
    line_end: Math.min(ownerEnd, anchorContextStart + MAX_EXCERPT_LINES - 1),
    includes_owner_signature: false,
  };
}


function candidatePayload(codegraph, sourcePath, targetNode, sourceFile, call, owner, expressionKind) {
  const ownerStart = lineOf(sourceFile, owner.node.getStart(sourceFile));
  const ownerEnd = lineOf(sourceFile, owner.node.end);
  const anchorStart = lineOf(sourceFile, call.getStart(sourceFile));
  const anchorEnd = lineOf(sourceFile, call.end);
  const graphOwner = matchingCodeGraphOwner(codegraph, sourcePath, owner, sourceFile);
  const reliability = reliabilityFor(expressionKind, hasExactCodeGraphCall(codegraph, graphOwner, targetNode));
  const excerpt = excerptRange(ownerStart, ownerEnd, anchorStart, anchorEnd);
  return {
    owner: {
      id: graphOwner?.id || `source_owner:${sourcePath}:${ownerStart}:${ownerEnd}`,
      kind: graphOwner?.kind || owner.identity.kind,
      name: owner.identity.name,
      qualified_name: graphOwner?.qualifiedName || qualifiedOwnerName(owner.node, owner.identity, sourceFile),
      path: sourcePath,
      line_start: excerpt.line_start,
      line_end: excerpt.line_end,
      full_line_start: ownerStart,
      full_line_end: ownerEnd,
      language: graphOwner?.language || "typescript",
    },
    anchor: {
      line_start: anchorStart,
      line_end: anchorEnd,
      expression: call.expression.getText(sourceFile),
      expression_kind: expressionKind,
    },
    reliability_tier: reliability.tier,
    decision_code: reliability.code,
    includes_owner_signature: excerpt.includes_owner_signature,
    nesting_depth: owner.nesting_depth,
  };
}


export function localizeFileCall(codegraph, projectRoot, sourceNode, targetNode) {
  const sourcePath = normalizePath(sourceNode?.filePath);
  const targetName = String(targetNode?.name || "");
  const extension = path.extname(sourcePath).toLowerCase();
  const base = {
    source_file_node_id: String(sourceNode?.id || ""),
    source_path: sourcePath,
    target_node_id: String(targetNode?.id || ""),
    target_symbol: targetName,
    adapter: SUPPORTED_EXTENSIONS.has(extension) ? "typescript_compiler_api" : "unsupported",
  };
  if (!SUPPORTED_EXTENSIONS.has(extension)) {
    return { ...base, status: "rejected", decision_code: "rejected_unsupported_language", considered: [] };
  }
  if (!sourcePath || !targetName) {
    return { ...base, status: "rejected", decision_code: "rejected_missing_source_or_target", considered: [] };
  }
  let source;
  try {
    source = fs.readFileSync(path.join(projectRoot, sourcePath), "utf8");
  } catch {
    return { ...base, status: "rejected", decision_code: "rejected_source_unreadable", considered: [] };
  }
  const scriptKind = extension === ".tsx" ? ts.ScriptKind.TSX
    : extension === ".jsx" ? ts.ScriptKind.JSX
      : [".js", ".mjs", ".cjs"].includes(extension) ? ts.ScriptKind.JS
        : ts.ScriptKind.TS;
  const sourceFile = ts.createSourceFile(sourcePath, source, ts.ScriptTarget.Latest, true, scriptKind);
  const considered = [];
  function visit(node) {
    if (ts.isCallExpression(node)) {
      for (const called of calledNames(node.expression).filter((item) => item.name === targetName)) {
        const owner = outermostNamedExecutable(node, sourceFile);
        if (!owner) {
          considered.push({
            anchor_line: lineOf(sourceFile, node.getStart(sourceFile)),
            expression: node.expression.getText(sourceFile),
            decision_code: "rejected_no_named_outer_executable",
            reliability_tier: 0,
          });
        } else {
          considered.push(candidatePayload(codegraph, sourcePath, targetNode, sourceFile, node, owner, called.expression_kind));
        }
      }
    }
    ts.forEachChild(node, visit);
  }
  visit(sourceFile);
  const eligible = considered.filter((item) => item.owner);
  eligible.sort((left, right) =>
    right.reliability_tier - left.reliability_tier
    || left.nesting_depth - right.nesting_depth
    || left.anchor.line_start - right.anchor.line_start
    || left.owner.qualified_name.localeCompare(right.owner.qualified_name),
  );
  if (!eligible.length) {
    return {
      ...base,
      status: "rejected",
      decision_code: considered.length ? "rejected_no_named_outer_executable" : "rejected_target_call_not_found",
      considered,
    };
  }
  const chosen = eligible[0];
  return {
    ...base,
    status: "localized",
    decision_code: `selected_${chosen.decision_code}`,
    selected: chosen,
    considered,
  };
}


export function sourceOwnerCalls(codegraph, projectRoot, sourceNode) {
  const sourcePath = normalizePath(sourceNode?.filePath || sourceNode?.path);
  const extension = path.extname(sourcePath).toLowerCase();
  const base = {
    source_node_id: String(sourceNode?.id || ""),
    source_path: sourcePath,
    adapter: SUPPORTED_EXTENSIONS.has(extension) ? "typescript_compiler_api" : "unsupported",
    calls: [],
  };
  if (!SUPPORTED_EXTENSIONS.has(extension)) {
    return { ...base, status: "unsupported", reason: "unsupported_extension" };
  }
  let source;
  try {
    source = fs.readFileSync(path.join(projectRoot, sourcePath), "utf8");
  } catch {
    return { ...base, status: "failed", reason: "source_unreadable" };
  }
  const scriptKind = extension === ".tsx" ? ts.ScriptKind.TSX
    : extension === ".jsx" ? ts.ScriptKind.JSX
      : [".js", ".mjs", ".cjs"].includes(extension) ? ts.ScriptKind.JS
        : ts.ScriptKind.TS;
  const sourceFile = ts.createSourceFile(sourcePath, source, ts.ScriptTarget.Latest, true, scriptKind);
  const calls = [];
  function visit(node) {
    if (ts.isCallExpression(node)) {
      const owner = outermostNamedExecutable(node, sourceFile);
      const graphOwner = owner ? matchingCodeGraphOwner(codegraph, sourcePath, owner, sourceFile) : null;
      if (graphOwner?.id === sourceNode.id) {
        for (const called of calledNames(node.expression)) {
          calls.push({
            name: called.name,
            qualifier: called.qualifier || "",
            expression_kind: called.expression_kind,
            expression: node.expression.getText(sourceFile),
            line_start: lineOf(sourceFile, node.getStart(sourceFile)),
            line_end: lineOf(sourceFile, node.end),
          });
        }
      }
    }
    ts.forEachChild(node, visit);
  }
  visit(sourceFile);
  return { ...base, status: "ok", calls };
}


export function summarizeFileCallsToDestination(codegraph, projectRoot, sourceNode, destinationPath) {
  const sourcePath = normalizePath(sourceNode?.filePath);
  const normalizedDestination = normalizePath(destinationPath);
  const base = {
    source_path: sourcePath,
    destination_path: normalizedDestination,
    direct_call_site_count: 0,
    destination_symbols: [],
    localized_source_owners: [],
  };
  if (!sourceNode?.id || !sourcePath || !normalizedDestination) return base;
  const targets = [];
  const seenTargets = new Set();
  for (const edge of codegraph.getOutgoingEdges(sourceNode.id)) {
    if (edge.kind !== "calls" || seenTargets.has(edge.target)) continue;
    const target = codegraph.getNode(edge.target);
    if (!target || normalizePath(target.filePath) !== normalizedDestination) continue;
    seenTargets.add(edge.target);
    targets.push(target);
  }
  const ownerNames = new Set();
  const symbols = [];
  for (const target of targets) {
    const localization = localizeFileCall(codegraph, projectRoot, sourceNode, target);
    const callSites = Array.isArray(localization.considered) ? localization.considered : [];
    const lines = [...new Set(callSites.map((item) => Number(item.anchor?.line_start || item.anchor_line || 0)).filter(Boolean))].sort((a, b) => a - b);
    for (const item of callSites) {
      if (item.owner?.qualified_name) ownerNames.add(String(item.owner.qualified_name));
    }
    symbols.push({
      symbol: String(target.name || ""),
      call_site_count: lines.length,
      call_lines: lines,
    });
  }
  return {
    ...base,
    direct_call_site_count: symbols.reduce((total, item) => total + item.call_site_count, 0),
    destination_symbols: symbols.sort((left, right) => left.symbol.localeCompare(right.symbol)),
    localized_source_owners: [...ownerNames].sort(),
  };
}

export function scopeCallsForRange(codegraph, projectRoot, sourceNode, args) {
  const sourcePath = normalizePath(args.path || sourceNode?.filePath);
  const start = Number(args.line_start || 0), end = Math.max(start, Number(args.line_end || start));
  const base = { source_path: sourcePath, line_start: start, line_end: end, scope: null, destinations: [] };
  if (!sourcePath || !start) return base;
  let text;
  try { text = fs.readFileSync(path.join(projectRoot, sourcePath), "utf8"); } catch { return base; }
  const sf = ts.createSourceFile(sourcePath, text, ts.ScriptTarget.Latest, true);
  let chosen = null;
  function visit(node) {
    if (ts.isFunctionLike(node)) {
      const first = lineOf(sf, node.getStart(sf)), last = lineOf(sf, node.end);
      if (first <= start && last >= end && (!chosen || last - first < chosen.last - chosen.first)) chosen = { node, first, last };
    }
    ts.forEachChild(node, visit);
  }
  visit(sf);
  if (!chosen) return base;
  const parentCall = chosen.node.parent && ts.isCallExpression(chosen.node.parent) ? chosen.node.parent : null;
  const callee = parentCall ? calledName(parentCall.expression).name : "";
  const label = callee ? `${callee} callback` : (executableIdentity(chosen.node, sf)?.name || "anonymous callback");
  // CodeGraph's file node can have same-name edges to unrelated declarations.
  // For a lexical callback scope, resolve imported bindings from TypeScript source
  // instead: `checkOutputErrorsInitial` must point to the module this file imports.
  const importedTargets = new Map();
  for (const statement of sf.statements) {
    if (!ts.isImportDeclaration(statement) || !ts.isStringLiteral(statement.moduleSpecifier)) continue;
    const clause = statement.importClause;
    if (!clause?.namedBindings || !ts.isNamedImports(clause.namedBindings)) continue;
    const specifier = statement.moduleSpecifier.text;
    if (!specifier.startsWith(".")) continue;
    const basePath = path.resolve(path.dirname(path.join(projectRoot, sourcePath)), specifier);
    const resolved = [".ts", ".tsx", ".js", "/index.ts"].map((suffix) => `${basePath}${suffix}`).find(fs.existsSync);
    if (!resolved) continue;
    const destination = normalizePath(path.relative(projectRoot, resolved));
    for (const element of clause.namedBindings.elements) importedTargets.set(element.name.text, destination);
  }
  if (!importedTargets.size) {
    // Older TypeScript test sources use namespace/import-equals bindings.  Preserve
    // CodeGraph's concrete outgoing targets in that case; scope filtering below
    // still limits the call sites to the enclosing callback.
    for (const edge of codegraph.getOutgoingEdges(sourceNode?.id || "")) {
      if (edge.kind !== "calls") continue;
      const target = codegraph.getNode(edge.target);
      if (!target || normalizePath(target.filePath) === sourcePath) continue;
      const values = importedTargets.get(String(target.name || "")) || [];
      values.push(normalizePath(target.filePath)); importedTargets.set(String(target.name || ""), values);
    }
  }
  const grouped = new Map();
  function collect(node) {
    if (ts.isCallExpression(node)) {
      const called = calledName(node.expression).name;
      const targetPaths = importedTargets.get(called);
      for (const destination of Array.isArray(targetPaths) ? targetPaths : (targetPaths ? [targetPaths] : [])) {
        const entry = grouped.get(destination) || { path: destination, symbols: new Map(), call_lines: [] };
        entry.symbols.set(called, (entry.symbols.get(called) || 0) + 1);
        entry.call_lines.push(lineOf(sf, node.getStart(sf))); grouped.set(destination, entry);
      }
    }
    ts.forEachChild(node, collect);
  }
  collect(chosen.node);
  return { ...base, scope: { kind: callee ? "test_callback" : "function", label, line_start: chosen.first, line_end: chosen.last }, destinations: [...grouped.values()].map((item) => ({ path: item.path, direct_call_site_count: item.call_lines.length, call_lines: [...new Set(item.call_lines)].sort((a,b)=>a-b), destination_symbols: [...item.symbols].map(([symbol, call_site_count]) => ({ symbol, call_site_count })) })).sort((a,b) => a.path.localeCompare(b.path)) };
}
