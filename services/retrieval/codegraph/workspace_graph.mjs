import readline from "node:readline";
import codegraphPackage from "@colbymchenry/codegraph";

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
  return {
    kind: edge.kind,
    provenance: edge.provenance || "",
    source: source ? nodePayload(source) : null,
    target: target ? nodePayload(target) : null,
  };
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

async function dispatch(operation, args) {
  if (operation === "index") return indexRepository();
  if (operation === "find_exact_symbol") return findExactSymbol(args);
  if (operation === "resolve_locations") return resolveLocations(args);
  if (operation === "expand_nodes") return expandNodes(args);
  if (operation === "callers") return analyzeCalls(args, "callers");
  if (operation === "callees") return analyzeCalls(args, "callees");
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
