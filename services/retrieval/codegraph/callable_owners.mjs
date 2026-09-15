import fs from 'node:fs';
import path from 'node:path';
import { parse } from '@babel/parser';

const JAVASCRIPT = new Set(['.js', '.jsx', '.mjs', '.cjs']);
const cache = new Map();

function children(node) {
  return Object.entries(node).filter(([key]) => !['loc', 'comments', 'tokens'].includes(key))
    .flatMap(([, value]) => Array.isArray(value) ? value : [value])
    .filter(value => value && typeof value === 'object' && typeof value.type === 'string');
}

function assignmentName(node) {
  if (node?.type === 'Identifier') return node.name;
  if (node?.type === 'MemberExpression') {
    const parent = assignmentName(node.object);
    const key = !node.computed ? node.property.name
      : ['StringLiteral', 'NumericLiteral'].includes(node.property.type) ? node.property.value : '';
    return parent && key !== '' ? `${parent}.${key}` : '';
  }
  return '';
}

function isCallable(node) {
  return ['FunctionDeclaration', 'FunctionExpression', 'ArrowFunctionExpression',
    'ObjectMethod', 'ClassMethod', 'ClassPrivateMethod'].includes(node.type);
}

export function callableInventory(projectRoot, sourcePath) {
  const absolute = path.resolve(projectRoot, sourcePath);
  const relative = path.relative(path.resolve(projectRoot), absolute);
  if (relative === '..' || relative.startsWith(`..${path.sep}`) || path.isAbsolute(relative)) {
    return { status: 'failed', reason: 'source_owner_outside_workspace', entries: [] };
  }
  if (!JAVASCRIPT.has(path.extname(sourcePath).toLowerCase())) return { status: 'unsupported', entries: [] };
  let stat;
  try { stat = fs.statSync(absolute); }
  catch { return { status: 'failed', reason: 'source_unreadable', entries: [] }; }
  const signature = `${stat.mtimeMs}:${stat.size}`;
  const previous = cache.get(absolute);
  if (previous?.signature === signature) return previous.value;
  const source = fs.readFileSync(absolute, 'utf8');
  let file;
  try {
    file = parse(source, { sourceType: 'unambiguous', plugins: ['flow', 'jsx'] });
  } catch {
    return { status: 'failed', reason: 'source_ast_parse_failed', entries: [],
      diagnostic_count: 1 };
  }
  const entries = [];
  function visit(node, parent = null, grandparent = null) {
    if (isCallable(node) && node.body) {
      let anchor = parent?.type === 'ExportNamedDeclaration' ? parent : node;
      let name = node.id?.name || node.key?.name || node.key?.value || '';
      const declaredName = name;
      let kind = node.type.includes('Method') ? (node.kind === 'constructor' ? 'constructor' : 'method') : 'function';
      if (['FunctionExpression', 'ArrowFunctionExpression'].includes(node.type)) {
        if (parent?.type === 'AssignmentExpression' && parent.operator === '='
            && grandparent?.type === 'ExpressionStatement') {
          anchor = grandparent;
          name = assignmentName(parent.left);
          kind = 'assigned_function';
        } else if (parent?.type === 'VariableDeclarator') {
          name = parent.id.name || '';
        }
      }
      const start = anchor.loc.start.line;
      const end = anchor.loc.end.line;
      const locationVariants = [[start, end], [node.loc.start.line, node.loc.end.line]];
      if (parent?.type === 'VariableDeclarator' && grandparent?.type === 'VariableDeclaration') {
        locationVariants.push([grandparent.loc.start.line, grandparent.loc.end.line]);
      }
      const names = [...new Set([name, declaredName].filter(Boolean))];
      entries.push({ node, name, names, kind, start, end, locationVariants });
    }
    for (const child of children(node)) visit(child, node, parent);
  }
  visit(file.program);
  const value = { status: 'ok', source, entries };
  if (cache.size >= 128) cache.delete(cache.keys().next().value);
  cache.set(absolute, { signature, value });
  return value;
}

function matchesGraphOwner(entry, node) {
  const start = Number(node.line_start ?? node.startLine);
  const end = Number(node.line_end ?? node.endLine ?? start);
  const name = String(node.name || node.qualified_name || node.qualifiedName || '').split('::').at(-1);
  return entry.locationVariants.some(([a, b]) => start === a && end === b)
    && (!entry.names.length || entry.names.some(alias => alias === name || alias.split('.').at(-1) === name));
}

export function graphCallableValidity(projectRoot, node) {
  if (!['function', 'method', 'constructor', 'assigned_function'].includes(node.kind)) return { valid: true };
  const sourcePath = node.path || node.filePath;
  if (!sourcePath) return { valid: true };
  const inventory = callableInventory(projectRoot, sourcePath);
  if (inventory.status === 'unsupported') return { valid: true };
  if (inventory.status !== 'ok') return { valid: false, reason: inventory.reason };
  return inventory.entries.some(entry => matchesGraphOwner(entry, node))
    ? { valid: true } : { valid: false, reason: 'graph_callable_disagrees_with_source_ast' };
}

function sourceOwner(sourcePath, entry) {
  return { id: `source_owner:${sourcePath}:${entry.start}:${entry.end}`, kind: entry.kind,
    name: entry.name, qualified_name: entry.name, path: sourcePath,
    line_start: entry.start, line_end: entry.end, language: 'javascript',
    adapter: 'babel_flow_parser', decision_code: 'validated_source_callable_recovery' };
}

export function reconcileCallableOwners(projectRoot, sourcePath, start, end, nodes) {
  const rejected = [];
  const retained = nodes.filter(node => {
    const result = graphCallableValidity(projectRoot, node);
    if (!result.valid) rejected.push({ node_id: node.id, path: sourcePath, name: node.name,
      line_start: node.line_start, line_end: node.line_end, reason: result.reason });
    return result.valid;
  });
  if (!rejected.length) return { nodes, rejected };
  const inventory = callableInventory(projectRoot, sourcePath);
  if (inventory.status === 'ok') {
    for (const entry of inventory.entries) {
      if (!entry.name || entry.start > end || entry.end < start
          || retained.some(node => matchesGraphOwner(entry, node))) continue;
      retained.push(sourceOwner(sourcePath, entry));
    }
  }
  return { nodes: retained, rejected };
}

export function findSourceCallable(projectRoot, sourceNode) {
  const inventory = callableInventory(projectRoot, sourceNode.path);
  if (inventory.status !== 'ok') return null;
  const matches = inventory.entries.filter(entry => {
    const owner = sourceOwner(sourceNode.path, entry);
    return owner.id === sourceNode.id && entry.start === sourceNode.line_start && entry.end === sourceNode.line_end
      && entry.name === (sourceNode.qualified_name || sourceNode.name);
  });
  return matches.length === 1 ? { ...matches[0], source: inventory.source } : null;
}

export function sourceCallableCalls(callable) {
  const calls = [];
  const text = node => callable.source.slice(node.start, node.end);
  function names(expression) {
    if (['TypeCastExpression', 'ParenthesizedExpression'].includes(expression.type)) return names(expression.expression);
    if (expression.type === 'ConditionalExpression') return [expression.consequent, expression.alternate]
      .flatMap(branch => names(branch).map(item => ({ ...item, expression_kind: `conditional_${item.expression_kind}` })));
    if (expression.type === 'Identifier') return [{ name: expression.name, qualifier: '', expression_kind: 'identifier' }];
    if (['MemberExpression', 'OptionalMemberExpression'].includes(expression.type)) {
      const name = !expression.computed ? expression.property.name
        : expression.property.type === 'StringLiteral' ? expression.property.value : '';
      if (name) return [{ name, qualifier: text(expression.object),
        expression_kind: expression.computed ? 'element_access' : 'property_access' }];
    }
    return [];
  }
  function visit(node) {
    if (isCallable(node) || ['ClassDeclaration', 'ClassExpression'].includes(node.type)) return;
    if (['CallExpression', 'OptionalCallExpression'].includes(node.type)) {
      for (const called of names(node.callee)) calls.push({ ...called, expression: text(node.callee),
        line_start: node.loc.start.line, line_end: node.loc.end.line });
    }
    for (const child of children(node)) visit(child);
  }
  visit(callable.node.body);
  return calls;
}

// Apply at every bridge exit so a rejected owner cannot return through outlines,
// expansion, or a connector. Drop the relationship too if any endpoint is invalid.
export function validateStructuralResult(projectRoot, result) {
  const rejected = new Map();
  function visit(value) {
    if (Array.isArray(value)) return value.map(visit).filter(item => item !== null);
    if (!value || typeof value !== 'object') return value;
    if (value.id && value.kind && (value.path || value.filePath)) {
      const check = graphCallableValidity(projectRoot, value);
      if (!check.valid) {
        rejected.set(value.id, { node_id: value.id, path: value.path || value.filePath,
          name: value.name || value.qualified_name, reason: check.reason });
        return null;
      }
    }
    const output = {};
    for (const [key, child] of Object.entries(value)) {
      const validated = visit(child);
      if (child && validated === null && ['source', 'target', 'connector', 'node'].includes(key)) return null;
      output[key] = validated;
    }
    return output;
  }
  const validated = visit(result) ?? {};
  if (rejected.size) validated.structural_owner_rejections = [...rejected.values()];
  return validated;
}
