import codegraphPackage from "@colbymchenry/codegraph";

const { CodeGraph } = codegraphPackage;

const EDGE_PRIORITY = new Map([
  ["calls", 0],
  ["references", 1],
  ["imports", 2],
  ["instantiates", 3],
  ["returns", 4],
  ["extends", 5],
  ["implements", 6],
  ["overrides", 7],
  ["decorates", 8],
  ["exports", 9],
  ["type_of", 10],
]);

function normalizePath(value) {
  return String(value || "").replaceAll("\\", "/").replace(/^\.\//, "");
}

function readInput() {
  return new Promise((resolve, reject) => {
    let body = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (chunk) => { body += chunk; });
    process.stdin.on("end", () => {
      try {
        resolve(JSON.parse(body));
      } catch (error) {
        reject(new Error(`Invalid selected-evidence input: ${error.message}`));
      }
    });
    process.stdin.on("error", reject);
  });
}

function overlappingNodes(codegraph, item) {
  const start = Number(item.line_start || 1);
  const end = Number(item.line_end || start);
  return codegraph
    .getNodesInFile(normalizePath(item.path))
    .filter((node) => node.kind !== "file" && node.startLine <= end && node.endLine >= start);
}

function candidateKey(candidate) {
  return [candidate.source_ref, candidate.target_ref, candidate.edge_kind].join("\u0000");
}

function addCandidate(output, seen, candidate) {
  if (!candidate.source_ref || !candidate.target_ref || candidate.source_ref === candidate.target_ref) return;
  const key = candidateKey(candidate);
  if (seen.has(key)) return;
  seen.add(key);
  output.push(candidate);
}

async function main() {
  const input = await readInput();
  const projectRoot = String(input.workspace_root || "").trim();
  const evidence = Array.isArray(input.evidence) ? input.evidence : [];
  if (!projectRoot) throw new Error("workspace_root is required");

  const codegraph = CodeGraph.isInitialized(projectRoot)
    ? await CodeGraph.open(projectRoot, { sync: true })
    : await CodeGraph.init(projectRoot, { index: true });

  try {
    const evidenceByNode = new Map();
    const nodesByEvidence = new Map();
    for (const item of evidence) {
      const ref = String(item.source_ref || "");
      const path = normalizePath(item.path);
      const nodes = overlappingNodes(codegraph, { ...item, path });
      nodesByEvidence.set(ref, nodes);
      for (const node of nodes) {
        if (!evidenceByNode.has(node.id)) evidenceByNode.set(node.id, []);
        evidenceByNode.get(node.id).push(ref);
      }
    }

    const candidates = [];
    const seen = new Set();
    for (const [sourceRef, nodes] of nodesByEvidence.entries()) {
      for (const sourceNode of nodes) {
        for (const edge of codegraph.getOutgoingEdges(sourceNode.id)) {
          if (!EDGE_PRIORITY.has(edge.kind)) continue;
          const targetNode = codegraph.getNode(edge.target);
          if (!targetNode) continue;
          for (const targetRef of evidenceByNode.get(targetNode.id) || []) {
            addCandidate(candidates, seen, {
              source_ref: sourceRef,
              target_ref: targetRef,
              edge_kind: edge.kind,
              source_symbol: sourceNode.name,
              target_symbol: targetNode.name,
              source_file: normalizePath(sourceNode.filePath),
              target_file: normalizePath(targetNode.filePath),
              line: Number(edge.line || sourceNode.startLine || 0),
              provenance: String(edge.provenance || "tree-sitter"),
            });
          }
        }
      }
    }

    candidates.sort((left, right) => {
      const priority = (EDGE_PRIORITY.get(left.edge_kind) ?? 99) - (EDGE_PRIORITY.get(right.edge_kind) ?? 99);
      return priority || left.source_ref.localeCompare(right.source_ref) || left.target_ref.localeCompare(right.target_ref);
    });

    process.stdout.write(JSON.stringify({
      index: {
        state: codegraph.getIndexState(),
        last_indexed_at: codegraph.getLastIndexedAt(),
        stats: codegraph.getStats(),
      },
      evidence_nodes: Object.fromEntries(
        [...nodesByEvidence.entries()].map(([ref, nodes]) => [ref, nodes.map((node) => ({
          id: node.id,
          kind: node.kind,
          name: node.name,
          file: normalizePath(node.filePath),
          line_start: node.startLine,
          line_end: node.endLine,
          language: node.language,
        }))]),
      ),
      direct_candidates: candidates.slice(0, 40),
    }));
  } finally {
    codegraph.close();
  }
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error.message || String(error)}\n`);
  process.exitCode = 1;
});
