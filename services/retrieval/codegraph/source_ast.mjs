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
    return { name: expression.text, expression_kind: "identifier" };
  }
  if (ts.isPropertyAccessExpression(expression)) {
    return { name: expression.name.text, expression_kind: "property_access" };
  }
  if (ts.isElementAccessExpression(expression) && expression.argumentExpression && ts.isStringLiteral(expression.argumentExpression)) {
    return { name: expression.argumentExpression.text, expression_kind: "element_access" };
  }
  return { name: "", expression_kind: "dynamic" };
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
  if (expressionKind === "identifier") {
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
      const called = calledName(node.expression);
      if (called.name === targetName) {
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

