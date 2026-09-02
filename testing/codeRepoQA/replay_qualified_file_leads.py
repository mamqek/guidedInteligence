"""Replay saved round-zero qualification against existing AST/graph; no indexing or LLM calls."""
from __future__ import annotations

import argparse
from dataclasses import fields
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from services.retrieval.config import WorkspaceRetrievalConfig
from services.retrieval.workspace.tools.codegraph import (
    CodeGraphBridge, CodeGraphFindExactSymbolTool, CodeGraphEdgeCapabilitiesTool, SourceOwnerCallsTool,
)
from services.retrieval.workspace.pipeline.execution_flow.discovery_observations import (
    DiscoveryObservation, SourceHandle, DiscoveryProvenance,
)
from testing.codeRepoQA.qualification_trace_adapter import qualification_decision_from_trace
from services.retrieval.workspace.pipeline.execution_flow.source_disclosure import DisclosureCard
from services.retrieval.workspace.pipeline.execution_flow.coverage_evaluation import ObligationCoverage
from services.retrieval.workspace.pipeline.execution_flow.verified_leads import discover_qualified_file_leads, _verified_lead_to_dict
from services.retrieval.workspace.pipeline.execution_flow.action_novelty import RequestMemoizer
from services.retrieval.workspace.pipeline.execution_flow.tracing import RetrievalTrace


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-trace', required=True)
    parser.add_argument('--workspace-root', required=True)
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args()
    events = [json.loads(line) for line in Path(args.source_trace).read_text(encoding='utf-8').splitlines() if line.strip()]
    def first(kind):
        return next(e['payload'] for e in events if e['event_type'] == kind and e['payload'].get('round') == 0)
    response = next(e['payload'] for e in events if e['event_type'] == 'llm_response_received'
                    and e['payload'].get('stage') == 'evidence_qualification' and e['payload'].get('round') == 0)
    payload = json.loads(response['request_payload']['messages'][-1]['content'])
    observations, cards = {}, {}
    for row in payload['observations']:
        identifier = row['observation_id']
        context = payload['file_contexts'][row['file_context_id']]
        owner = context.get('relevant_owners', {}).get(row.get('owner_context_id'), {})
        handle_values = {key: value for key, value in row['source_handle'].items() if key in {f.name for f in fields(SourceHandle)}}
        handle_values['path'] = context['path']
        handle = SourceHandle(**handle_values)
        navigation = row.get('navigation_context', {})
        observations[identifier] = DiscoveryObservation(identifier, handle, row.get('source_text', ''),
            provenance=(DiscoveryProvenance('saved_qualification_replay', identifier,
                tuple(navigation.get('obligation_ids', ())), (), ()),),
            artifact_role=navigation.get('artifact_role', 'implementation'))
        cards[identifier] = DisclosureCard(identifier, handle, row['mode'], row.get('source_text', ''),
            owner_kind=owner.get('kind', ''), owner_name=owner.get('name', ''),
            owner_line_start=owner.get('line_start', 0), owner_line_end=owner.get('line_end', 0))
    decisions = {
        row['observation_id']: qualification_decision_from_trace(row)
        for row in first('qualification_decisions_created')['decisions']
    }
    coverage = tuple(ObligationCoverage(**row) for row in first('coverage_evaluated')['coverage'])
    config = WorkspaceRetrievalConfig(args.workspace_root, '', None, None, None)
    bridge = CodeGraphBridge(config)
    tools = [SourceOwnerCallsTool(config, bridge), CodeGraphFindExactSymbolTool(bridge), CodeGraphEdgeCapabilitiesTool(bridge)]
    tools = RequestMemoizer().wrap_tools({tool.name: tool for tool in tools})
    trace = RetrievalTrace(run_dir=Path(args.output_dir))
    try:
        leads, audit, count = discover_qualified_file_leads(round_index=0, changed_observation_ids=tuple(observations),
            observations=observations, decisions=decisions, cards=cards, coverage=coverage,
            pending_node_ids=set(), executed_node_ids=set(), structural_tools=tools, workspace_root=args.workspace_root, trace=trace)
        summary = dict(source_trace=args.source_trace, leads=[_verified_lead_to_dict(lead) for lead in leads],
            audit=audit, tool_calls=count, note='Original fitted source, decisions and coverage; no downstream actions or LLM. Unqualified pool omitted; it does not affect eligibility.')
        trace.record('qualified_structural_file_lead_replay', summary)
        print(json.dumps(summary, indent=2))
    finally:
        bridge.close()


if __name__ == '__main__':
    main()
