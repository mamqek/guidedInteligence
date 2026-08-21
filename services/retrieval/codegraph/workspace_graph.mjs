import readline from "node:readline";
import fs from "node:fs";
import path from "node:path";
import codegraphPackage from "@colbymchenry/codegraph";
import { localizeFileCall, sourceOwnerCalls, summarizeFileCallsToDestination } from "./source_ast.mjs";

const { CodeGraph, setLogger, silentLogger } = codegraphPackage;

setLogger(silentLogger);

const projectRoot = process.argv[2];
if (!projectRoot) {
  throw new Error("workspace_graph.mjs requires a project root argument");
}

let graph = null;

function normalizePath(value) {
  return String(value || "").replaceAll("\\", "/").replace(/^\.\//, "");
}

async function openGraph() {
  if (graph) return graph;
  graph = CodeGraph.isInitialized(projectRoot)
    ? await CodeGraph.open(projectRoot, { sync: false })
    : await CodeGraph.init(projectRoot, { index: false });
  return graph;
}

function nodePayload(node) {
  return {
    id: node.id,
    kind: node.kind,
    name: node.name,
    qualified_name: node.qualifiedName || node.name,
    path: normalizePath(node.filePath),
    line_start: Number(node.startLine || 0),
    line_end: Number(node.endLine || node.startLine || 0),
    language: node.language || "",
  };
}

function uniqueNodes(nodes) {
  const seen = new Set();
  return nodes.filter((node) => {
    if (!node?.id || seen.has(node.id)) return false;
    seen.add(node.id);
    return true;
  });
}

function exactNodes(codegraph, name, file = "") {
  const normalizedFile = normalizePath(file);
  return uniqueNodes(codegraph.getNodesByName(String(name || "").trim())).filter(
    (node) => !normalizedFile || normalizePath(node.filePath) === normalizedFile,
  );
}

function nodesAtLocation(codegraph, file, line) {
  const normalizedFile = normalizePath(file);
  const targetLine = Number(line || 0);
  if (!normalizedFile || targetLine <= 0) return [];
  return uniqueNodes(codegraph.getNodesInFile(normalizedFile))
    .filter((node) => {
      const start = Number(node.startLine || 0);
      const end = Number(node.endLine || start);
      return start > 0 && start <= targetLine && end >= targetLine && !["file", "import"].includes(node.kind);
    })
    .sort((left, right) => {
      const leftSpan = Number(left.endLine || left.startLine || 0) - Number(left.startLine || 0);
      const rightSpan = Number(right.endLine || right.startLine || 0) - Number(right.startLine || 0);
      return leftSpan - rightSpan;
    });
}

function uniqueFiles(nodes, limit = 50) {
  const seen = new Set();
  const files = [];
  for (const node of nodes) {
    const path = normalizePath(node.filePath);
    if (!path || seen.has(path)) continue;
    seen.add(path);
    files.push({ path, name: node.name, kind: node.kind, line: Number(node.startLine || 0) });
    if (files.length >= limit) break;
  }
  return files;
}

function edgePayload(codegraph, edge) {
  const source = codegraph.getNode(edge.source);
  const target = codegraph.getNode(edge.target);
  const payload = {
    kind: edge.kind,
    provenance: edge.provenance || "",
    source: source ? nodePayload(source) : null,
    target: target ? nodePayload(target) : null,
  };
  if (edge.kind === "calls" && source?.kind === "file" && target && target.kind !== "file") {
    payload.file_call_localization = localizeFileCall(codegraph, projectRoot, source, target);
    payload.file_connection_summary = summarizeFileCallsToDestination(
      codegraph, projectRoot, source, normalizePath(target.filePath),
    );
  }
  return payload;
}

function identifierTerms(value) {
  return String(value || "")
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .split(/[^A-Za-z0-9]+/)
    .map((item) => item.toLowerCase())
    .filter((item) => item.length >= 4);
}

async function indexRepository() {
  const initialized = CodeGraph.isInitialized(projectRoot);
  const codegraph = await openGraph();
  const result = initialized ? await codegraph.sync() : await codegraph.indexAll();
  return {
    initialized,
    result,
    index_state: codegraph.getIndexState(),
    last_indexed_at: codegraph.getLastIndexedAt(),
    pending_references: codegraph.getPendingReferenceCount(),
    stats: codegraph.getStats(),
  };
}

async function findExactSymbol(args) {
  const codegraph = await openGraph();
  const nodes = exactNodes(codegraph, args.query);
  const limit = Math.max(1, Math.min(Number(args.limit || 20), 100));
  return {
    query: String(args.query || ""),
    match_count: nodes.length,
    nodes: nodes.slice(0, limit).map(nodePayload),
    files: uniqueFiles(nodes, limit),
  };
}

async function resolveLocations(args) {
  const codegraph = await openGraph();
  const locations = Array.isArray(args.locations) ? args.locations.slice(0, 80) : [];
  return {
    results: locations.map((location) => ({
      file: normalizePath(location.file),
      line: Number(location.line || 0),
      nodes: nodesAtLocation(codegraph, location.file, location.line).slice(0, 4).map(nodePayload),
    })),
  };
}

async function resolveRanges(args) {
  const codegraph = await openGraph();
  const ranges = Array.isArray(args.ranges) ? args.ranges.slice(0, 80) : [];
  return {
    results: ranges.map((range) => ({
      file: normalizePath(range.file),
      line_start: Number(range.line_start || 0),
      line_end: Number(range.line_end || range.line_start || 0),
      nodes: nodesOverlappingRange(
        codegraph,
        range.file,
        range.line_start,
        range.line_end,
      ).slice(0, 12).map(nodePayload),
    })),
  };
}

async function fileOutline(args) {
  const codegraph = await openGraph();
  const file = normalizePath(args.path);
  const limit = Math.max(1, Math.min(Number(args.max_entries || 120), 400));
  const focusStart = Math.max(0, Number(args.line_start || 0));
  const focusEnd = Math.max(focusStart, Number(args.line_end || focusStart));
  const nodes = uniqueNodes(codegraph.getNodesInFile(file))
    .filter((node) => !["file", "import"].includes(node.kind))
    .sort((left, right) =>
      Number(left.startLine || 0) - Number(right.startLine || 0) ||
      Number(left.endLine || left.startLine || 0) - Number(right.endLine || right.startLine || 0) ||
      String(left.name || "").localeCompare(String(right.name || "")),
    );
  let selected = nodes;
  if (focusStart) {
    const distance = (node) => {
      const start = Number(node.startLine || 0);
      const end = Number(node.endLine || start);
      if (start <= focusEnd && end >= focusStart) return 0;
      return start > focusEnd ? start - focusEnd : focusStart - end;
    };
    const nearby = [...nodes].sort((left, right) =>
      distance(left) - distance(right) ||
      (Number(left.endLine || left.startLine || 0) - Number(left.startLine || 0)) -
        (Number(right.endLine || right.startLine || 0) - Number(right.startLine || 0)),
    ).slice(0, limit);
    const ids = new Set(nearby.map((node) => node.id));
    selected = nodes.filter((node) => ids.has(node.id));
  }
  return { path: file, total_count: nodes.length, nodes: selected.slice(0, limit).map(nodePayload) };
}

async function resolveFileNodes(args) {
  const codegraph = await openGraph();
  const paths = [...new Set((Array.isArray(args.paths) ? args.paths : []).map(normalizePath).filter(Boolean))].slice(0, 16);
  const nodes = [];
  for (const file of paths) {
    const fileNode = uniqueNodes(codegraph.getNodesInFile(file)).find((node) => node.kind === "file");
    if (fileNode) nodes.push(nodePayload(fileNode));
  }
  return { paths, nodes };
}

async function relationshipsWithinNodes(args) {
  const codegraph = await openGraph();
  const nodeIds = [...new Set((Array.isArray(args.node_ids) ? args.node_ids : []).map(String).filter(Boolean))].slice(0, 80);
  const requested = new Set(nodeIds);
  const allowedKinds = new Set((Array.isArray(args.edge_kinds) ? args.edge_kinds : []).map(String).filter(Boolean));
  const connectorKinds = new Set(
    (Array.isArray(args.connector_edge_kinds) ? args.connector_edge_kinds : ["calls"])
      .map(String)
      .filter(Boolean),
  );
  const nodes = nodeIds.map((id) => codegraph.getNode(id)).filter(Boolean);
  const edges = [];
  const seen = new Set();
  for (const node of nodes) {
    for (const edge of codegraph.getOutgoingEdges(node.id)) {
      if (!requested.has(edge.source) || !requested.has(edge.target)) continue;
      if (allowedKinds.size && !allowedKinds.has(edge.kind)) continue;
      const key = `${edge.source}\0${edge.target}\0${edge.kind}`;
      if (seen.has(key)) continue;
      seen.add(key);
      edges.push(edgePayload(codegraph, edge));
    }
  }
  const connectorPaths = [];
  const seenConnectorPaths = new Set();
  for (const source of nodes) {
    for (const first of codegraph.getOutgoingEdges(source.id)) {
      if (!connectorKinds.has(first.kind) || requested.has(first.target)) continue;
      const connector = codegraph.getNode(first.target);
      if (!connector || ["file", "import"].includes(connector.kind)) continue;
      for (const second of codegraph.getOutgoingEdges(connector.id)) {
        if (!connectorKinds.has(second.kind) || !requested.has(second.target) || second.target === source.id) continue;
        const target = codegraph.getNode(second.target);
        if (!target) continue;
        const key = `${source.id}\0${connector.id}\0${target.id}\0${first.kind}\0${second.kind}`;
        if (seenConnectorPaths.has(key)) continue;
        seenConnectorPaths.add(key);
        connectorPaths.push({
          source: nodePayload(source),
          connector: nodePayload(connector),
          target: nodePayload(target),
          edge_kinds: [first.kind, second.kind],
          edges: [edgePayload(codegraph, first), edgePayload(codegraph, second)],
        });
      }
    }
  }
  connectorPaths.sort((left, right) =>
    left.source.id.localeCompare(right.source.id)
      || left.target.id.localeCompare(right.target.id)
      || left.connector.id.localeCompare(right.connector.id),
  );
  return {
    node_ids: nodeIds,
    nodes: nodes.map(nodePayload),
    edges,
    connector_paths: connectorPaths.slice(0, 40),
  };
}

async function edgeCapabilities(args) {
  const codegraph = await openGraph();
  const nodeIds = [...new Set((Array.isArray(args.node_ids) ? args.node_ids : []).map(String).filter(Boolean))].slice(0, 16);
  const nodes = [];
  for (const nodeId of nodeIds) {
    const node = codegraph.getNode(nodeId);
    if (!node) continue;
    const incoming = new Map();
    const outgoing = new Map();
    for (const edge of codegraph.getIncomingEdges(nodeId)) incoming.set(edge.kind, (incoming.get(edge.kind) || 0) + 1);
    for (const edge of codegraph.getOutgoingEdges(nodeId)) outgoing.set(edge.kind, (outgoing.get(edge.kind) || 0) + 1);
    const counts = (values) => [...values.entries()]
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([kind, count]) => ({ kind, count }));
    nodes.push({ node_id: nodeId, node: nodePayload(node), incoming: counts(incoming), outgoing: counts(outgoing) });
  }
  return { nodes };
}

async function expandRelationships(args) {
  const codegraph = await openGraph();
  const seedIds = [...new Set((Array.isArray(args.node_ids) ? args.node_ids : []).map(String).filter(Boolean))].slice(0, 16);
  const direction = String(args.direction || "");
  if (!["incoming", "outgoing"].includes(direction)) throw new Error("direction must be incoming or outgoing");
  const allowedKinds = new Set((Array.isArray(args.edge_kinds) ? args.edge_kinds : []).map(String).filter(Boolean));
  if (!allowedKinds.size) throw new Error("edge_kinds must be a non-empty allowlist");
  const targetSymbols = new Set(
    (Array.isArray(args.target_symbols) ? args.target_symbols : [])
      .map(normalizedOwner)
      .filter(Boolean),
  );
  const targetTerms = new Set(
    (Array.isArray(args.target_terms) ? args.target_terms : [])
      .flatMap(identifierTerms),
  );
  const crossFileOnly = Boolean(args.cross_file_only);
  const limit = Math.max(1, Math.min(Number(args.limit || 3), 20));
  const candidates = new Map();
  const seenEdges = new Set();
  const seedPaths = new Set(seedIds.map((id) => normalizePath(codegraph.getNode(id)?.filePath)).filter(Boolean));
  for (const seedId of seedIds) {
    const adjacent = direction === "incoming" ? codegraph.getIncomingEdges(seedId) : codegraph.getOutgoingEdges(seedId);
    for (const edge of adjacent) {
      if (!allowedKinds.has(edge.kind)) continue;
      const endpointId = direction === "incoming" ? edge.source : edge.target;
      const endpoint = codegraph.getNode(endpointId);
      if (!endpoint) continue;
      if (crossFileOnly && seedPaths.has(normalizePath(endpoint.filePath))) continue;
      const normalizedEndpoint = normalizedOwner(endpoint.qualifiedName || endpoint.name);
      const exactScore = targetSymbols.has(normalizedEndpoint) ? 100 : 0;
      const endpointTerms = new Set(identifierTerms(`${endpoint.name || ""} ${endpoint.qualifiedName || ""}`));
      const termScore = [...endpointTerms].filter((term) => targetTerms.has(term)).length * 10;
      if ((targetSymbols.size || targetTerms.size) && exactScore + termScore === 0) continue;
      const edgeKey = `${edge.source}\0${edge.target}\0${edge.kind}`;
      const current = candidates.get(endpointId);
      const score = exactScore + termScore;
      if (!current || score > current.score) {
        candidates.set(endpointId, {
          endpoint,
          edge,
          edgeKey,
          score,
          ordinal: current?.ordinal ?? candidates.size,
        });
      }
    }
  }
  const selected = [...candidates.values()]
    .sort((left, right) =>
      right.score - left.score
      || ((targetSymbols.size || targetTerms.size)
        ? String(left.endpoint.name || "").localeCompare(String(right.endpoint.name || ""))
          || normalizePath(left.endpoint.filePath).localeCompare(normalizePath(right.endpoint.filePath))
        : left.ordinal - right.ordinal),
    )
    .slice(0, limit);
  const endpoints = selected.map((item) => nodePayload(item.endpoint));
  const edges = selected.filter((item) => {
    if (seenEdges.has(item.edgeKey)) return false;
    seenEdges.add(item.edgeKey);
    return true;
  }).map((item) => edgePayload(codegraph, item.edge));
  return {
    seed_node_ids: seedIds,
    direction,
    edge_kinds: [...allowedKinds].sort(),
    target_symbols: [...targetSymbols].sort(),
    target_terms: [...targetTerms].sort(),
    cross_file_only: crossFileOnly,
    nodes: endpoints,
    edges,
  };
}

async function expandNodes(args) {
  const codegraph = await openGraph();
  const seedIds = [...new Set((Array.isArray(args.node_ids) ? args.node_ids : []).map(String).filter(Boolean))].slice(0, 80);
  const depth = Math.max(1, Math.min(Number(args.depth || 1), 3));
  const limit = Math.max(1, Math.min(Number(args.limit || 120), 400));
  const visited = new Set(seedIds);
  let frontier = [...seedIds];
  const nodes = [];
  const edges = [];
  const edgeKeys = new Set();
  for (const id of seedIds) {
    const node = codegraph.getNode(id);
    if (node) nodes.push(nodePayload(node));
  }
  for (let level = 0; level < depth && frontier.length && nodes.length < limit; level += 1) {
    const next = [];
    for (const id of frontier) {
      const adjacent = [...codegraph.getOutgoingEdges(id), ...codegraph.getIncomingEdges(id)];
      for (const edge of adjacent) {
        const key = `${edge.source}\0${edge.target}\0${edge.kind}`;
        if (!edgeKeys.has(key)) {
          edgeKeys.add(key);
          edges.push(edgePayload(codegraph, edge));
        }
        const otherId = edge.source === id ? edge.target : edge.source;
        if (visited.has(otherId)) continue;
        const other = codegraph.getNode(otherId);
        if (!other) continue;
        visited.add(otherId);
        next.push(otherId);
        nodes.push(nodePayload(other));
        if (nodes.length >= limit) break;
      }
      if (nodes.length >= limit) break;
    }
    frontier = next;
  }
  return { seed_node_ids: seedIds, nodes, edges: edges.slice(0, limit * 3) };
}

async function analyzeCalls(args, direction) {
  const codegraph = await openGraph();
  const sources = nodesAtLocation(codegraph, args.file, args.line);
  const related = [];
  for (const source of sources) {
    const entries = direction === "callers" ? codegraph.getCallers(source.id, 1) : codegraph.getCallees(source.id, 1);
    for (const entry of entries) related.push(entry.node);
  }
  return {
    symbol: sources[0]?.name || "",
    source_nodes: sources.map(nodePayload),
    files: uniqueFiles(uniqueNodes(related), Number(args.limit || 50)),
  };
}

async function relationshipBetweenFiles(args) {
  const codegraph = await openGraph();
  const sourcePath = normalizePath(args.source_path);
  const targetPath = normalizePath(args.target_path);
  const sourceNodes = codegraph.getNodesInFile(sourcePath);
  const targetNodes = codegraph.getNodesInFile(targetPath);
  const targetIds = new Set(targetNodes.map((node) => node.id));
  const sourceIds = new Set(sourceNodes.map((node) => node.id));
  const edges = [];
  const seen = new Set();

  function collect(nodes, expectedIds, direction) {
    for (const node of nodes) {
      const candidates = direction === "outgoing" ? codegraph.getOutgoingEdges(node.id) : codegraph.getIncomingEdges(node.id);
      for (const edge of candidates) {
        const otherId = direction === "outgoing" ? edge.target : edge.source;
        if (!expectedIds.has(otherId)) continue;
        const other = codegraph.getNode(otherId);
        if (!other) continue;
        const key = `${edge.source}\0${edge.target}\0${edge.kind}`;
        if (seen.has(key)) continue;
        seen.add(key);
        const source = codegraph.getNode(edge.source);
        const target = codegraph.getNode(edge.target);
        edges.push({
          edge_kind: edge.kind,
          provenance: edge.provenance || "",
          source: source ? nodePayload(source) : null,
          target: target ? nodePayload(target) : null,
        });
      }
    }
  }

  collect(sourceNodes, targetIds, "outgoing");
  collect(sourceNodes, targetIds, "incoming");
  collect(targetNodes, sourceIds, "outgoing");
  collect(targetNodes, sourceIds, "incoming");

  return {
    source_path: sourcePath,
    target_path: targetPath,
    edges: edges.slice(0, Math.max(1, Math.min(Number(args.limit || 25), 100))),
    source_depends_on_target: codegraph.getFileDependencies(sourcePath).map(normalizePath).includes(targetPath),
    target_depends_on_source: codegraph.getFileDependencies(targetPath).map(normalizePath).includes(sourcePath),
  };
}

function nodesOverlappingRange(codegraph, file, lineStart, lineEnd) {
  const normalizedFile = normalizePath(file);
  const startLine = Number(lineStart || 0);
  const endLine = Math.max(startLine, Number(lineEnd || startLine));
  if (!normalizedFile || startLine <= 0) return [];
  return uniqueNodes(codegraph.getNodesInFile(normalizedFile))
    .filter((node) => {
      const start = Number(node.startLine || 0);
      const end = Number(node.endLine || start);
      return start > 0 && start <= endLine && end >= startLine && !["file", "import"].includes(node.kind);
    })
    .sort((left, right) => {
      const leftOverlap = Math.max(0, Math.min(Number(left.endLine || left.startLine || 0), endLine) - Math.max(Number(left.startLine || 0), startLine) + 1);
      const rightOverlap = Math.max(0, Math.min(Number(right.endLine || right.startLine || 0), endLine) - Math.max(Number(right.startLine || 0), startLine) + 1);
      const leftSpan = Number(left.endLine || left.startLine || 0) - Number(left.startLine || 0);
      const rightSpan = Number(right.endLine || right.startLine || 0) - Number(right.startLine || 0);
      return rightOverlap - leftOverlap || leftSpan - rightSpan;
    });
}

function normalizedOwner(value) {
  return String(value || "").replace(/[^A-Za-z0-9_$]/g, "").toLowerCase();
}

async function fileNeighbors(args) {
  const codegraph = await openGraph();
  const paths = [...new Set((Array.isArray(args.paths) ? args.paths : []).map(normalizePath).filter(Boolean))].slice(0, 8);
  const limit = Math.max(1, Math.min(Number(args.limit || 20), 80));
  const weights = { calls: 4, imports: 4, instantiates: 3, references: 2 };
  const scores = new Map();
  const seenEdges = new Set();

  for (const sourcePath of paths) {
    for (const node of codegraph.getNodesInFile(sourcePath)) {
      for (const edge of [...codegraph.getOutgoingEdges(node.id), ...codegraph.getIncomingEdges(node.id)]) {
        const edgeKey = `${edge.source}\0${edge.target}\0${edge.kind}`;
        if (seenEdges.has(edgeKey)) continue;
        seenEdges.add(edgeKey);
        const otherId = edge.source === node.id ? edge.target : edge.source;
        const other = codegraph.getNode(otherId);
        const otherPath = normalizePath(other?.filePath);
        if (!otherPath || otherPath === sourcePath || paths.includes(otherPath)) continue;
        const entry = scores.get(otherPath) || {
          path: otherPath,
          score: 0,
          edge_count: 0,
          edge_kinds: new Set(),
          source_paths: new Set(),
          relationship_counts: new Map(),
        };
        entry.edge_count += 1;
        entry.edge_kinds.add(edge.kind);
        entry.source_paths.add(sourcePath);
        const relationshipKey = `${sourcePath}\0${edge.kind}`;
        entry.relationship_counts.set(relationshipKey, (entry.relationship_counts.get(relationshipKey) || 0) + 1);
        scores.set(otherPath, entry);
      }
    }
    for (const dependency of codegraph.getFileDependencies(sourcePath)) {
      const dependencyPath = normalizePath(dependency);
      if (!dependencyPath || dependencyPath === sourcePath || paths.includes(dependencyPath)) continue;
      const entry = scores.get(dependencyPath) || {
        path: dependencyPath,
        score: 0,
        edge_count: 0,
        edge_kinds: new Set(),
        source_paths: new Set(),
        relationship_counts: new Map(),
      };
      entry.edge_kinds.add("file_dependency");
      entry.source_paths.add(sourcePath);
      const relationshipKey = `${sourcePath}\0file_dependency`;
      entry.relationship_counts.set(relationshipKey, (entry.relationship_counts.get(relationshipKey) || 0) + 1);
      scores.set(dependencyPath, entry);
    }
  }

  for (const entry of scores.values()) {
    entry.score = [...entry.relationship_counts.entries()].reduce((total, [key, count]) => {
      const kind = key.slice(key.lastIndexOf("\0") + 1);
      const repetitionBonus = Math.min(1.5, Math.log2(Math.max(1, count)) * 0.25);
      return total + ((weights[kind] || 1) * (1 + repetitionBonus));
    }, 0);
    entry.score += Math.max(0, entry.source_paths.size - 1) * 2;
  }

  const neighbors = [...scores.values()]
    .sort((left, right) => right.score - left.score || right.edge_count - left.edge_count || left.path.localeCompare(right.path))
    .slice(0, limit)
    .map((item) => ({
      ...item,
      edge_kinds: [...item.edge_kinds].sort(),
      source_paths: [...item.source_paths].sort(),
      relationship_counts: undefined,
    }));
  return { source_paths: paths, neighbors };
}

async function qualifiedReferences(args) {
  const codegraph = await openGraph();
  const sourcePaths = [...new Set((Array.isArray(args.paths) ? args.paths : []).map(normalizePath).filter(Boolean))].slice(0, 12);
  const excludedPaths = [...new Set((Array.isArray(args.exclude_paths) ? args.exclude_paths : []).map(normalizePath).filter(Boolean))];
  const limit = Math.max(1, Math.min(Number(args.limit || 40), 120));
  const matches = new Map();
  const expressionPattern = /\b([A-Za-z_$][\w$]*)\s*\.\s*([A-Za-z_$][\w$]*)\s*(?:<[^;{}()]*>)?\s*\(/g;

  for (const sourcePath of sourcePaths) {
    let source;
    try {
      source = fs.readFileSync(path.join(projectRoot, sourcePath), "utf8");
    } catch {
      continue;
    }
    const lineStarts = [0];
    for (let offset = source.indexOf("\n"); offset >= 0; offset = source.indexOf("\n", offset + 1)) lineStarts.push(offset + 1);
    for (const match of source.matchAll(expressionPattern)) {
      const qualifier = match[1];
      const member = match[2];
      if (!/^[A-Z]/.test(qualifier)) continue;
      const owner = normalizedOwner(qualifier);
      const targets = exactNodes(codegraph, member).filter((node) => {
        const targetPath = normalizePath(node.filePath);
        if (sourcePaths.includes(targetPath)) return false;
        if (excludedPaths.some((excluded) => targetPath === excluded || targetPath.startsWith(`${excluded}/`))) return false;
        const fileOwner = normalizedOwner(path.basename(normalizePath(node.filePath), path.extname(node.filePath || "")));
        const qualifiedOwner = normalizedOwner(String(node.qualifiedName || "").split("::", 1)[0]);
        return owner && (owner === fileOwner || owner === qualifiedOwner);
      });
      if (!targets.length) continue;
      const callOffset = Number(match.index || 0);
      let sourceLine = 1;
      for (let index = 1; index < lineStarts.length && lineStarts[index] <= callOffset; index += 1) sourceLine = index + 1;
      const sourceNode = nodesAtLocation(codegraph, sourcePath, sourceLine)[0];
      for (const target of targets) {
        const current = matches.get(target.id) || {
          ...nodePayload(target),
          qualifier,
          expression: `${qualifier}.${member}`,
          source_references: [],
        };
        if (!current.source_references.some((item) => item.path === sourcePath && item.line === sourceLine)) {
          current.source_references.push({
            path: sourcePath,
            line: sourceLine,
            source_node: sourceNode ? nodePayload(sourceNode) : null,
          });
        }
        matches.set(target.id, current);
      }
    }
  }

  const resolvedNodes = [...matches.values()]
    .map((node) => ({
      ...node,
      source_paths: [...new Set(node.source_references.map((item) => item.path))],
      source_count: new Set(node.source_references.map((item) => item.path)).size,
      reference_count: node.source_references.length,
    }));
  const qualifierReferenceCounts = new Map();
  for (const node of resolvedNodes) {
    qualifierReferenceCounts.set(
      node.qualifier,
      (qualifierReferenceCounts.get(node.qualifier) || 0) + node.reference_count,
    );
  }
  const nodes = resolvedNodes
    .map((node) => ({
      ...node,
      qualifier_reference_count: qualifierReferenceCounts.get(node.qualifier) || node.reference_count,
    }))
    .sort((left, right) =>
      right.source_count - left.source_count ||
      right.reference_count - left.reference_count ||
      right.name.length - left.name.length ||
      left.path.localeCompare(right.path),
    )
    .slice(0, limit);
  return { source_paths: sourcePaths, nodes };
}

async function dispatch(operation, args) {
  if (operation === "index") return indexRepository();
  if (operation === "find_exact_symbol") return findExactSymbol(args);
  if (operation === "resolve_locations") return resolveLocations(args);
  if (operation === "resolve_ranges") return resolveRanges(args);
  if (operation === "file_outline") return fileOutline(args);
  if (operation === "resolve_file_nodes") return resolveFileNodes(args);
  if (operation === "relationships_within_nodes") return relationshipsWithinNodes(args);
  if (operation === "source_owner_calls") {
    const codegraph = await openGraph();
    const sourceNode = codegraph.getNode(String(args.node_id || ""));
    if (!sourceNode) return { status: "failed", reason: "unknown_source_node", calls: [] };
    return sourceOwnerCalls(codegraph, projectRoot, sourceNode);
  }
  if (operation === "edge_capabilities") return edgeCapabilities(args);
  if (operation === "expand_relationships") return expandRelationships(args);
  if (operation === "expand_nodes") return expandNodes(args);
  if (operation === "callers") return analyzeCalls(args, "callers");
  if (operation === "callees") return analyzeCalls(args, "callees");
  if (operation === "file_neighbors") return fileNeighbors(args);
  if (operation === "qualified_references") return qualifiedReferences(args);
  if (operation === "relationship_between_files") return relationshipBetweenFiles(args);
  if (operation === "status") {
    const codegraph = await openGraph();
    return { index_state: codegraph.getIndexState(), stats: codegraph.getStats(), pending_references: codegraph.getPendingReferenceCount() };
  }
  throw new Error(`Unsupported CodeGraph operation: ${operation}`);
}

const lines = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
for await (const line of lines) {
  if (!line.trim()) continue;
  let request;
  try {
    request = JSON.parse(line);
    if (request.operation === "close") {
      process.stdout.write(`${JSON.stringify({ id: request.id, ok: true, result: {} })}\n`);
      break;
    }
    const result = await dispatch(request.operation, request.arguments || {});
    process.stdout.write(`${JSON.stringify({ id: request.id, ok: true, result })}\n`);
  } catch (error) {
    process.stdout.write(`${JSON.stringify({ id: request?.id || "", ok: false, error: error?.stack || error?.message || String(error) })}\n`);
  }
}

if (graph) await Promise.resolve(graph.close());
