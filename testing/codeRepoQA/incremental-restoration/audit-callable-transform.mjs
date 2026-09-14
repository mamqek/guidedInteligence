import fs from 'node:fs';
import path from 'node:path';
import { reconcileCallableOwners, validateStructuralResult } from '../../../services/retrieval/codegraph/callable_owners.mjs';

// Offline deterministic replay of saved real structural outputs; no LLM surrogate.
const root = process.argv[2];
for (const runPath of process.argv.slice(3)) {
  const events = fs.readFileSync(path.join(runPath, 'retrieval-trace.jsonl'), 'utf8')
    .trim().split('\n').map(line => JSON.parse(line));
  let checked = 0, changed = 0, ranges = 0, changedRanges = 0;
  const changes = [];
  for (const event of events) {
    if (event.event_type !== 'tool_observation_created' ||
        !String(event.payload.tool_name).startsWith('structural_')) continue;
    const result = event.payload.payload;
    checked++;
    if (JSON.stringify(result) !== JSON.stringify(validateStructuralResult(root, result))) {
      changed++;
      changes.push(event.payload.tool_name);
    }
    for (const range of result?.results ?? []) {
      if (!Array.isArray(range.nodes) || !range.file) continue;
      ranges++;
      const next = reconcileCallableOwners(root, range.file, range.line_start, range.line_end, range.nodes);
      if (JSON.stringify(next.nodes) !== JSON.stringify(range.nodes) || next.rejected.length) changedRanges++;
    }
  }
  console.log(JSON.stringify({run: path.basename(runPath), checked, changed, ranges, changedRanges, changes}));
}
