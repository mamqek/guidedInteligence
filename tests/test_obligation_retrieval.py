from __future__ import annotations

from dataclasses import replace
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from services.intent.models import EvidenceObligation, EvidenceRole
from services.retrieval.workspace.bm25 import build_index_from_repo
from services.retrieval.workspace.pipeline.execution_flow.obligation_retrieval import (
    GroundedCandidate,
    AnchorConfirmation,
    ObligationProgress,
    _apply_duplicate_provenance_ranking,
    _append_semantic_candidates,
    _best_bridge_nodes_in_files,
    _best_overlapping_nodes,
    _candidate_connections,
    _candidate_from_node,
    _candidate_provenance_tier,
    _candidate_review_id,
    _candidate_conflicts_with_missing_path,
    _concept_coverage,
    _consolidation_response_format,
    _consolidate_obligation_evidence,
    _connected_candidate_shortlists,
    _confirmed_obligation_paths,
    _edge_index,
    _expand_grounded_candidate_graph,
    _anchor_index_distribution,
    _anchor_is_repository_common,
    _exact_index_anchor_matches,
    _exact_prompt_seed_results,
    _focused_frontier_paths,
    _focused_seed_ids,
    _first_bridge_gap,
    _dependency_seed_candidates,
    _direct_target_context_score,
    _dominant_error_anchor_result,
    _graph_preferred_paths,
    _global_candidate_id,
    _ground_semantic_root_neighbors,
    _has_usable_exact_graph_ranges,
    _is_visible_direct_target,
    _remove_generated_candidates,
    _recover_prompt_relevant_exact_callees,
    _recover_factory_handoffs,
    _run_focused_semantic_bridge,
    _nodes_in_confirmed_paths,
    _normalized_expansion_edges,
    _obligation_query,
    _obligation_stage_query_text,
    _path_qualifications,
    _candidate_support_graph,
    _select_mechanism_flows,
    _qualified_reference_priority,
    _qualified_frontier_paths,
    _update_promotion_ledger,
    _distinctive_terms,
    _semantic_support_score,
    _source_authored_nodes,
    _terms,
    _resolve_repository_path,
    _resolve_file_transition,
    _source_category_for_role,
    _transition_from_edges,
    _transition_from_focused_bridge,
    _transition_from_shared_anchors,
)
from services.retrieval.workspace.tools.contracts import ToolObservation
from services.retrieval.workspace.tools.qdrant import (
    _include_preferred_range_results,
    _limit_results_per_path,
    _prioritize_preferred_paths,
    _prioritize_preferred_ranges,
)


class ObligationRetrievalTests(unittest.TestCase):
    def test_raw_file_node_never_becomes_candidate(self) -> None:
        with TemporaryDirectory() as root:
            workspace = Path(root)
            source = workspace / "src" / "large.ts"
            source.parent.mkdir()
            source.write_text("function target() {}\n", encoding="utf-8")
            rejected_events = []
            ctx = SimpleNamespace(
                config=SimpleNamespace(workspace_root=str(workspace)),
                trace=SimpleNamespace(
                    record=lambda event_type, payload: rejected_events.append((event_type, payload))
                ),
            )

            candidate = _candidate_from_node(
                ctx,
                {
                    "id": "file:src/large.ts",
                    "kind": "file",
                    "path": "src/large.ts",
                    "line_start": 1,
                    "line_end": 500,
                },
                score=1.0,
                origin="graph_neighbor",
            )

        self.assertIsNone(candidate)
        self.assertEqual(rejected_events[0][0], "raw_file_node_candidate_rejected")
        self.assertEqual(rejected_events[0][1]["decision_code"], "rejected_non_executable_graph_node")

    def test_localized_file_call_replaces_file_endpoint_with_named_owner(self) -> None:
        edges = _normalized_expansion_edges(
            (
                {
                    "kind": "calls",
                    "source": {"id": "file:src/watch.ts", "kind": "file", "path": "src/watch.ts"},
                    "target": {"id": "function:target", "kind": "function", "path": "src/target.ts"},
                    "file_call_localization": {
                        "status": "localized",
                        "adapter": "typescript_compiler_api",
                        "decision_code": "selected_ast_unqualified_target_call",
                        "selected": {
                            "owner": {
                                "id": "function:owner",
                                "kind": "function",
                                "name": "owner",
                                "path": "src/watch.ts",
                                "line_start": 10,
                                "line_end": 30,
                                "full_line_start": 1,
                                "full_line_end": 100,
                            },
                            "anchor": {"line_start": 20, "line_end": 20},
                            "reliability_tier": 3,
                        },
                    },
                },
            )
        )

        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0]["source"]["id"], "function:owner")
        self.assertEqual(edges[0]["kind"], "contained_call")
        self.assertEqual(edges[0]["source"]["anchor_reliability_tier"], 3)

    def test_candidate_review_id_is_stable_across_candidate_order(self) -> None:
        first = _candidate("first", "src/first.ts")
        second = _candidate("second", "src/second.ts")

        forward = [_candidate_review_id("cause", candidate) for candidate in (first, second)]
        reverse = [_candidate_review_id("cause", candidate) for candidate in (second, first)]

        self.assertEqual(set(forward), set(reverse))
        self.assertNotIn("candidate-", forward[0])

    def test_candidate_connections_preserve_codegraph_path_provenance(self) -> None:
        source = _candidate("source", "src/compiler/builder.ts")
        target = replace(
            _candidate("target", "src/compiler/builderState.ts"),
            source_paths=("src/compiler/builder.ts",),
        )

        connections = _candidate_connections(
            {"first:candidate-1": source, "second:candidate-1": target},
            expanded_edges=(),
        )

        self.assertEqual(connections[0]["relationship"], "codegraph_file_relationship")

    def test_graph_expansion_continues_through_new_exact_nodes_without_semantic_search(self) -> None:
        with TemporaryDirectory() as root:
            workspace = Path(root)
            src = workspace / "src"
            src.mkdir()
            (src / "entry.ts").write_text("function entry() { middle(); }\n", encoding="utf-8")
            (src / "middle.ts").write_text("function middle() { target(); }\n", encoding="utf-8")
            (src / "target.ts").write_text("function target() { return true; }\n", encoding="utf-8")
            state = ObligationProgress(
                EvidenceObligation("flow", "Trace entry through middle to target.", True),
                candidates=[
                    replace(
                        _candidate_with_text("function:entry", "src/entry.ts", "function entry() { middle(); }"),
                        symbol="entry",
                    )
                ],
            )

            class ExpandTool:
                def run(self, request):
                    seed = request.arguments["node_ids"][0]
                    if seed == "function:entry":
                        target = {
                            "id": "function:middle",
                            "name": "middle",
                            "path": "src/middle.ts",
                            "line_start": 1,
                            "line_end": 1,
                        }
                    else:
                        target = {
                            "id": "function:target",
                            "name": "target",
                            "path": "src/target.ts",
                            "line_start": 1,
                            "line_end": 1,
                        }
                    return ToolObservation(
                        tool_name="structural_expand_nodes",
                        status="ok",
                        payload={
                            "nodes": [target],
                            "edges": [
                                {
                                    "kind": "calls",
                                    "source": {"id": seed},
                                    "target": {"id": target["id"]},
                                }
                            ],
                        },
                    )

            ctx = SimpleNamespace(
                config=SimpleNamespace(workspace_root=str(workspace)),
                trace=SimpleNamespace(record_tool=lambda *args, **kwargs: None),
            )
            calls, edges, rounds = _expand_grounded_candidate_graph(
                ctx,
                states=(state,),
                structural_expand_tool=ExpandTool(),
                max_rounds=3,
            )

        self.assertEqual(calls, 2)
        self.assertEqual(rounds, 3)
        self.assertEqual({candidate.symbol for candidate in state.candidates}, {"entry", "middle", "target"})
        self.assertEqual(len(edges), 2)

    def test_productive_graph_edge_localizes_node_even_if_previously_visited_elsewhere(self) -> None:
        with TemporaryDirectory() as root:
            workspace = Path(root)
            source = workspace / "src" / "owner.ts"
            source.parent.mkdir()
            source.write_text("function internalStep() { return true; }\n", encoding="utf-8")
            state = ObligationProgress(
                EvidenceObligation("flow", "Explain the reported behavior.", True),
                candidates=[_candidate("function:seed", "src/seed.ts")],
            )
            tool = SimpleNamespace(
                run=lambda request: ToolObservation(
                    tool_name="structural_expand_nodes",
                    status="ok",
                    payload={
                        "nodes": [
                            {
                                "id": "function:internalStep",
                                "name": "internalStep",
                                "kind": "function",
                                "path": "src/owner.ts",
                                "line_start": 1,
                                "line_end": 1,
                            }
                        ],
                        "edges": [
                            {
                                "kind": "calls",
                                "source": {"id": "function:seed"},
                                "target": {"id": "function:internalStep"},
                            }
                        ],
                    },
                )
            )
            ctx = SimpleNamespace(
                config=SimpleNamespace(workspace_root=str(workspace)),
                trace=SimpleNamespace(record_tool=lambda *args, **kwargs: None),
            )

            _expand_grounded_candidate_graph(
                ctx,
                states=(state,),
                structural_expand_tool=tool,
                max_rounds=2,
                initially_visited={"function:internalStep"},
            )

        self.assertIn("function:internalStep", {candidate.node_id for candidate in state.candidates})

    def test_connected_shortlist_preserves_cross_obligation_path(self) -> None:
        linked_left = replace(
            _candidate("function:left", "src/left.ts"),
            relationship_types=("calls",),
            score=1.0,
        )
        linked_right = replace(
            _candidate("function:right", "src/right.ts"),
            relationship_types=("calls",),
            score=1.0,
        )
        isolated = replace(_candidate("function:isolated", "src/isolated.ts"), score=100.0)
        states = (
            ObligationProgress(EvidenceObligation("start", "Find the start.", True), candidates=[isolated, linked_left]),
            ObligationProgress(EvidenceObligation("effect", "Find the effect.", True), candidates=[linked_right]),
        )
        edges = (
            {
                "kind": "calls",
                "source": {"id": "function:left"},
                "target": {"id": "function:right"},
            },
        )

        shortlists = _connected_candidate_shortlists(states, expanded_edges=edges, limit=4)

        self.assertEqual(tuple(candidate.path for candidate in shortlists["start"]), ("src/left.ts",))
        self.assertEqual(tuple(candidate.path for candidate in shortlists["effect"]), ("src/right.ts",))

    def test_connected_shortlist_preserves_verified_exact_prompt_seed(self) -> None:
        exact = replace(
            _candidate("function:parser", "src/exp-parser.js"),
            origin="exact_prompt_anchor",
            provenance_origins=("exact_prompt_anchor",),
            score=1.0,
        )
        generic = replace(_candidate("function:generic", "src/compiler.js"), score=5.0)
        state = ObligationProgress(
            EvidenceObligation("effect", "Explain the parsing error.", True),
            candidates=[generic, exact],
        )

        shortlist = _connected_candidate_shortlists((state,), expanded_edges=(), limit=1)

        self.assertEqual(shortlist["effect"][0].path, "src/exp-parser.js")

    def test_productive_upstream_and_downstream_candidates_have_equal_provenance(self) -> None:
        upstream = replace(
            _candidate("function:caller", "src/owner.ts"),
            origin="graph_neighbor",
            provenance_origins=("graph_neighbor",),
            relationship="calls",
            relationship_types=("calls",),
        )
        downstream = replace(
            _candidate("function:callee", "src/consumer.ts"),
            origin="graph_direct_target",
            provenance_origins=("graph_direct_target",),
            relationship="calls",
            relationship_types=("calls",),
        )

        self.assertEqual(_candidate_provenance_tier(upstream), _candidate_provenance_tier(downstream))

    def test_candidate_support_graph_preserves_direct_and_inherited_obligations(self) -> None:
        watch_trigger = replace(
            _candidate("function:watch", "src/testRunner/watchMode.ts"),
            origin="semantic_anchor",
            provenance_origins=("semantic_anchor",),
            obligation_ids=("trigger",),
        )
        watch_mechanism = replace(watch_trigger, obligation_ids=("mechanism",))
        helper = replace(
            _candidate("function:helper", "src/testRunner/helpers.ts"),
            origin="graph_neighbor",
            provenance_origins=("graph_neighbor",),
            obligation_ids=("trigger", "mechanism"),
        )
        states = (
            ObligationProgress(
                EvidenceObligation("trigger", "Find the trigger.", True),
                candidates=[watch_trigger, helper],
            ),
            ObligationProgress(
                EvidenceObligation("mechanism", "Find the mechanism.", True),
                candidates=[watch_mechanism, helper],
            ),
        )

        candidates, direct, inherited = _candidate_support_graph(states)

        self.assertEqual(direct["node:function:watch"], {"trigger", "mechanism"})
        self.assertEqual(inherited["node:function:helper"], {"trigger", "mechanism"})
        self.assertEqual(len(candidates), 2)

    def test_mechanism_flows_select_directed_exact_nodes(self) -> None:
        watch = replace(
            _candidate("function:watch", "src/testRunner/watchMode.ts"),
            origin="semantic_anchor",
            provenance_origins=("semantic_anchor",),
            obligation_ids=("trigger",),
        )
        helper = replace(
            _candidate("function:helper", "src/testRunner/helpers.ts"),
            origin="graph_neighbor",
            provenance_origins=("graph_neighbor",),
            obligation_ids=("trigger", "mechanism"),
        )
        builder = replace(
            _candidate("function:builder", "src/compiler/builderState.ts"),
            origin="semantic_anchor",
            provenance_origins=("semantic_anchor",),
            obligation_ids=("state",),
        )
        states = (
            ObligationProgress(
                EvidenceObligation("trigger", "Find the trigger.", True),
                candidates=[watch, helper],
            ),
            ObligationProgress(EvidenceObligation("mechanism", "Trace the handoff.", True), candidates=[helper]),
            ObligationProgress(EvidenceObligation("state", "Find the mutation.", True), candidates=[builder]),
        )
        edges = (
            {"kind": "calls", "source": {"id": watch.node_id}, "target": {"id": helper.node_id}},
            {"kind": "qualified_call", "source": {"id": helper.node_id}, "target": {"id": builder.node_id}},
        )

        selected, direct, inherited, flows, connections, ledger = _select_mechanism_flows(
            states,
            expanded_edges=edges,
        )

        self.assertEqual(set(selected), {"node:function:watch", "node:function:helper", "node:function:builder"})
        self.assertEqual(direct["node:function:builder"], {"state"})
        self.assertEqual(inherited["node:function:helper"], {"trigger", "mechanism"})
        self.assertTrue(any(set(item["candidate_ids"]) == set(selected) for item in flows))
        self.assertEqual({item["relationship"] for item in connections}, {"calls", "qualified_call"})
        self.assertTrue(all(item["selected_for_final_request"] for item in ledger["candidate_inventory"]))
        self.assertTrue(any(item["decision"] == "selected" for item in ledger["flow_decisions"]))

    def test_mechanism_flows_connect_dynamic_callback_and_state_handoff(self) -> None:
        render_node = replace(
            _candidate_with_text(
                "function:renderNode",
                "src/server/render.js",
                "function renderNode(node) { return renderElement(node); }",
            ),
            origin="semantic_anchor",
            provenance_origins=("semantic_anchor",),
            obligation_ids=("entry",),
            line_start=1,
            line_end=3,
        )
        render_element = replace(
            _candidate_with_text(
                "function:renderElement",
                "src/server/render.js",
                "function renderElement(el) { renderStartingTag(el); return el.children; }",
            ),
            origin="graph_neighbor",
            provenance_origins=("graph_neighbor",),
            obligation_ids=("entry", "mutation"),
            line_start=5,
            line_end=7,
        )
        render_starting_tag = replace(
            _candidate_with_text(
                "function:renderStartingTag",
                "src/server/render.js",
                "function renderStartingTag(node) { modules[i](node); }",
            ),
            origin="graph_neighbor",
            provenance_origins=("graph_neighbor",),
            obligation_ids=("entry",),
            line_start=9,
            line_end=11,
        )
        render_dom_props = replace(
            _candidate_with_text(
                "function:renderDOMProps",
                "src/server/modules/dom-props.js",
                "export default function renderDOMProps(node) { setText(node, 'x'); }",
            ),
            origin="semantic_anchor",
            provenance_origins=("semantic_anchor",),
            obligation_ids=("mutation",),
            line_start=1,
            line_end=3,
        )
        set_text = replace(
            _candidate_with_text(
                "function:setText",
                "src/server/modules/dom-props.js",
                "function setText(node, text) { node.children = [{ text }]; }",
            ),
            origin="graph_neighbor",
            provenance_origins=("graph_neighbor",),
            obligation_ids=("mutation",),
            line_start=5,
            line_end=7,
        )
        states = (
            ObligationProgress(EvidenceObligation("entry", "Trace render node entry.", True), candidates=[render_node, render_element, render_starting_tag]),
            ObligationProgress(EvidenceObligation("mutation", "Find DOM text children mutation.", True), candidates=[render_dom_props, set_text, render_element]),
        )
        edges = (
            {"kind": "calls", "source": {"id": render_node.node_id}, "target": {"id": render_element.node_id}},
            {"kind": "calls", "source": {"id": render_element.node_id}, "target": {"id": render_starting_tag.node_id}},
            {"kind": "calls", "source": {"id": render_dom_props.node_id}, "target": {"id": set_text.node_id}},
        )

        selected, _direct, _inherited, flows, connections, ledger = _select_mechanism_flows(
            states,
            expanded_edges=edges,
        )

        self.assertEqual(
            set(selected),
            {
                "node:function:renderNode",
                "node:function:renderElement",
                "node:function:renderStartingTag",
                "node:function:renderDOMProps",
                "node:function:setText",
            },
        )
        relationships = {item["relationship"] for item in connections}
        self.assertIn("registered_callback", relationships)
        self.assertIn("state_write_read", relationships)
        self.assertTrue(
            any(
                item["candidate_ids"][:5]
                == [
                    "node:function:renderNode",
                    "node:function:renderElement",
                    "node:function:renderStartingTag",
                    "node:function:renderDOMProps",
                    "node:function:setText",
                ]
                for item in flows
            )
        )
        self.assertGreaterEqual(ledger["source_inferred_connection_count"], 2)

    def test_mechanism_flows_resolve_qualified_owner_call_to_exact_target(self) -> None:
        handle_change = replace(
            _candidate_with_text(
                "function:handleDtsMayChangeOf",
                "src/compiler/builder.ts",
                "function handleDtsMayChangeOf() { BuilderState.updateShapeSignature(state, program); }",
            ),
            symbol="handleDtsMayChangeOf",
            origin="semantic_anchor",
            provenance_origins=("semantic_anchor",),
            obligation_ids=("state",),
        )
        update_shape = replace(
            _candidate_with_text(
                "function:updateShapeSignature",
                "src/compiler/builderState.ts",
                "export function updateShapeSignature(state, program) { return computeHash(program); }",
            ),
            symbol="updateShapeSignature",
            origin="graph_neighbor",
            provenance_origins=("graph_neighbor",),
            obligation_ids=("state",),
        )
        state = ObligationProgress(
            EvidenceObligation("state", "Trace declaration signature update.", True),
            candidates=[handle_change, update_shape],
        )

        selected, _direct, _inherited, flows, connections, _ledger = _select_mechanism_flows(
            (state,),
            expanded_edges=(),
        )

        self.assertEqual(set(selected), {"node:function:handleDtsMayChangeOf", "node:function:updateShapeSignature"})
        self.assertTrue(any(item["candidate_ids"] == list(selected) for item in flows))
        self.assertEqual(len(connections), 1)
        self.assertEqual(connections[0]["relationship"], "qualified_call")

    def test_mechanism_flows_replace_only_weaker_parallel_connection(self) -> None:
        stronger_root = replace(
            _candidate_with_score("function:stronger", "src/compiler/builder.ts", 2.0),
            symbol="handleStrongChange",
            origin="graph_neighbor",
            obligation_ids=("state",),
        )
        weaker_root = replace(
            _candidate_with_score("function:weaker", "src/compiler/builder.ts", 0.1),
            symbol="handleWeakChange",
            origin="graph_neighbor",
            obligation_ids=("state",),
            line_start=10,
            line_end=11,
        )
        state_owner = replace(
            _candidate("function:update", "src/compiler/builderState.ts"),
            symbol="updateShapeSignature",
            text="function updateShapeSignature() { state.signature = next; }",
            origin="graph_neighbor",
            obligation_ids=("state",),
        )
        caller = replace(
            _candidate("function:caller", "src/compiler/builderPublic.ts"),
            symbol="createBuilderProgram",
            origin="graph_neighbor",
            obligation_ids=("state",),
        )
        progress = ObligationProgress(
            EvidenceObligation("state", "Trace signature state update.", True),
            candidates=[stronger_root, weaker_root, state_owner, caller],
        )
        edges = (
            {"kind": "calls", "source": {"id": caller.node_id}, "target": {"id": stronger_root.node_id}},
            {"kind": "instantiates", "source": {"id": stronger_root.node_id}, "target": {"id": state_owner.node_id}},
            {"kind": "calls", "source": {"id": stronger_root.node_id}, "target": {"id": state_owner.node_id}},
            {"kind": "calls", "source": {"id": weaker_root.node_id}, "target": {"id": state_owner.node_id}},
            {"kind": "calls", "source": {"id": state_owner.node_id}, "target": {"id": stronger_root.node_id}},
        )

        selected, _direct, _inherited, flows, connections, ledger = _select_mechanism_flows(
            (progress,),
            expanded_edges=edges,
        )

        self.assertIn("node:function:update", selected)
        self.assertTrue(
            any(
                item["candidate_ids"][:2]
                == ["node:function:caller", "node:function:stronger"]
                for item in flows
            )
        )
        self.assertTrue(
            any(
                item["candidate_ids"][-2:]
                == ["node:function:stronger", "node:function:update"]
                for item in flows
            )
        )
        self.assertEqual(
            {(item["from_candidate_id"], item["to_candidate_id"]) for item in connections},
            {
                ("node:function:caller", "node:function:stronger"),
                ("node:function:stronger", "node:function:update"),
                ("node:function:weaker", "node:function:update"),
                ("node:function:update", "node:function:stronger"),
            },
        )
        self.assertEqual(
            [
                item
                for item in connections
                if item["from_candidate_id"] == "node:function:stronger"
                and item["to_candidate_id"] == "node:function:update"
            ][0]["relationship"],
            "calls",
        )
        self.assertTrue(
            any(
                item["decision"] == "rejected_weaker_parallel_connection"
                and item["relationship"] == "instantiates"
                and item["replaced_by_relationship"] == "calls"
                for item in ledger["connection_decisions"]
            )
        )
        self.assertTrue(all(item["provenance"] == "exact_codegraph_edge" for item in connections))

    def test_mechanism_flows_do_not_consume_an_obligation_slot(self) -> None:
        reporter = replace(
            _candidate_with_text(
                "function:reportErrorSummary",
                "src/compiler/tsbuildPublic.ts",
                "function reportErrorSummary(state) { return getWatchErrorSummaryDiagnosticMessage(state); }",
            ),
            symbol="reportErrorSummary",
            origin="semantic_anchor",
            provenance_origins=("semantic_anchor",),
            obligation_ids=("state",),
            score=0.9,
        )
        diagnostic = replace(
            _candidate_with_text(
                "function:getWatchErrorSummaryDiagnosticMessage",
                "src/compiler/watch.ts",
                "function getWatchErrorSummaryDiagnosticMessage() { return Diagnostics.Found_errors; }",
            ),
            symbol="getWatchErrorSummaryDiagnosticMessage",
            origin="graph_neighbor",
            provenance_origins=("graph_neighbor",),
            obligation_ids=("state",),
        )
        update_signatures = replace(
            _candidate_with_text(
                "function:updateSignaturesFromCache",
                "src/compiler/builderState.ts",
                "function updateSignaturesFromCache(state, cache) { cache.forEach((signature, path) => state.fileInfos.get(path).signature = signature); }",
            ),
            symbol="updateSignaturesFromCache",
            origin="semantic_anchor",
            provenance_origins=("semantic_anchor",),
            obligation_ids=("state",),
            score=0.5,
        )
        read_signature = replace(
            _candidate_with_text(
                "function:readSignature",
                "src/compiler/builder.ts",
                "function readSignature(state, path) { return state.fileInfos.get(path).signature; }",
            ),
            symbol="readSignature",
            origin="graph_neighbor",
            provenance_origins=("graph_neighbor",),
            obligation_ids=("state",),
        )
        state = ObligationProgress(
            EvidenceObligation("state", "Identify changed declaration signature state.", True),
            candidates=[reporter, diagnostic, update_signatures, read_signature],
        )
        edges = (
            {"kind": "calls", "source": {"id": reporter.node_id}, "target": {"id": diagnostic.node_id}},
            {"kind": "calls", "source": {"id": update_signatures.node_id}, "target": {"id": read_signature.node_id}},
        )

        selected, _direct, _inherited, _flows, _connections, ledger = _select_mechanism_flows(
            (state,),
            expanded_edges=edges,
        )

        self.assertIn("node:function:updateSignaturesFromCache", selected)
        self.assertFalse(
            any(
                item["decision"]
                == "rejected_no_new_prompt_term_direct_obligation_or_protected_responsibility"
                for item in ledger["flow_decisions"]
            )
        )

    def test_consolidation_schema_has_one_global_evidence_budget(self) -> None:
        schema = _consolidation_response_format(("state", "why"), ("candidate:a", "candidate:b"))
        properties = schema["json_schema"]["schema"]["properties"]

        self.assertEqual(properties["selected_evidence"]["maxItems"], 14)
        self.assertNotIn("maxItems", properties["obligation_assessments"]["items"]["properties"]["supporting_candidate_ids"])
        self.assertNotIn(
            "enum",
            properties["selected_evidence"]["items"]["properties"]["candidate_id"],
        )
        self.assertNotIn(
            "enum",
            properties["mechanisms"]["items"]["properties"]["candidate_ids"]["items"],
        )

    def test_prompt_relevant_callee_localization_continues_named_flow(self) -> None:
        with TemporaryDirectory() as root:
            source = Path(root) / "src/server/render.js"
            source.parent.mkdir(parents=True)
            source.write_text(
                "function renderNode(node) { renderElement(node) }\n"
                "function renderElement(node) { renderStartingTag(node) }\n"
                "function renderStartingTag(node) { return node.tag }\n",
                encoding="utf-8",
            )
            state = ObligationProgress(
                EvidenceObligation(
                    "mechanism",
                    "Trace the server render mechanism.",
                    True,
                    stage_ids=("explain.ordered_mechanism",),
                ),
                candidates=[
                    replace(
                        _candidate_with_text(
                            "function:renderNode",
                            "src/server/render.js",
                            "function renderNode(node) { renderElement(node) }",
                        ),
                        symbol="renderNode",
                        origin="graph_continuation",
                        provenance_origins=("graph_continuation",),
                        relationship_types=("calls",),
                        obligation_ids=("mechanism",),
                    )
                ],
            )

            class ExactSymbols:
                def run(self, request):
                    name = request.arguments["query"]
                    nodes = {
                        "renderElement": {
                            "id": "function:renderElement",
                            "name": "renderElement",
                            "path": "src/server/render.js",
                            "line_start": 2,
                            "line_end": 2,
                        },
                        "renderStartingTag": {
                            "id": "function:renderStartingTag",
                            "name": "renderStartingTag",
                            "path": "src/server/render.js",
                            "line_start": 3,
                            "line_end": 3,
                        },
                    }
                    return ToolObservation(
                        tool_name=request.tool_name,
                        status="ok",
                        payload={"nodes": [nodes[name]], "match_count": 1},
                    )

            ctx = SimpleNamespace(
                config=SimpleNamespace(workspace_root=root),
                trace=SimpleNamespace(record=lambda *args, **kwargs: None, record_tool=lambda *args, **kwargs: None),
            )
            calls = _recover_prompt_relevant_exact_callees(
                ctx,
                states=(state,),
                find_exact_symbol_tool=ExactSymbols(),
            )

        self.assertEqual(calls, 2)
        self.assertEqual(
            {candidate.symbol for candidate in state.candidates},
            {"renderNode", "renderElement", "renderStartingTag"},
        )

    def test_factory_handoff_recovers_visible_default_factory(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "src").mkdir()
            (root / "src" / "watch.ts").write_text(
                "function createWatch(host) { return createWatchCompilerHostOfConfigFile(host); }\n"
                "function createWatchCompilerHostOfConfigFile(host) { return createWatchCompilerHost(host); }\n"
                "function createWatchCompilerHost(host) { return createProgramHost(host); }\n",
                encoding="utf-8",
            )
            (root / "src" / "public.ts").write_text(
                "function createProgramHost(createProgram) {\n"
                "  return { createProgram: createProgram || createBuilderProgram };\n"
                "}\n",
                encoding="utf-8",
            )
            (root / "src" / "builder.ts").write_text(
                "function createBuilderProgram(host) { return host; }\n",
                encoding="utf-8",
            )
            state = ObligationProgress(
                EvidenceObligation("mechanism", "Trace the watch program mechanism.", True),
                candidates=[
                    replace(
                        _candidate_with_text(
                            "function:createWatch",
                            "src/watch.ts",
                            "function createWatch(host) { return createWatchCompilerHostOfConfigFile(host); }",
                        ),
                        symbol="createWatch",
                        origin="semantic_anchor",
                        provenance_origins=("semantic_anchor",),
                        obligation_ids=("mechanism",),
                    )
                ],
            )

            class ExactSymbols:
                def run(self, request):
                    name = request.arguments["query"]
                    nodes = {
                        "createWatchCompilerHostOfConfigFile": {
                            "id": "function:createWatchCompilerHostOfConfigFile",
                            "name": "createWatchCompilerHostOfConfigFile",
                            "path": "src/watch.ts",
                            "line_start": 2,
                            "line_end": 2,
                        },
                        "createWatchCompilerHost": {
                            "id": "function:createWatchCompilerHost",
                            "name": "createWatchCompilerHost",
                            "path": "src/watch.ts",
                            "line_start": 3,
                            "line_end": 3,
                        },
                        "createProgramHost": {
                            "id": "function:createProgramHost",
                            "name": "createProgramHost",
                            "path": "src/public.ts",
                            "line_start": 1,
                            "line_end": 3,
                        },
                        "createBuilderProgram": {
                            "id": "function:createBuilderProgram",
                            "name": "createBuilderProgram",
                            "path": "src/builder.ts",
                            "line_start": 1,
                            "line_end": 1,
                        },
                    }
                    return ToolObservation(
                        tool_name=request.tool_name,
                        status="ok",
                        payload={"nodes": [nodes[name]], "match_count": 1},
                    )

            ctx = SimpleNamespace(
                config=SimpleNamespace(workspace_root=root),
                trace=SimpleNamespace(record=lambda *args, **kwargs: None, record_tool=lambda *args, **kwargs: None),
            )
            calls, edges = _recover_factory_handoffs(
                ctx,
                states=(state,),
                find_exact_symbol_tool=ExactSymbols(),
            )

        self.assertEqual(calls, 4)
        self.assertEqual(
            {candidate.symbol for candidate in state.candidates},
            {"createWatch", "createWatchCompilerHostOfConfigFile", "createWatchCompilerHost", "createProgramHost", "createBuilderProgram"},
        )
        program_host = next(candidate for candidate in state.candidates if candidate.symbol == "createProgramHost")
        self.assertEqual(program_host.facts.callable_defaults, (("createProgram", "createBuilderProgram"),))
        self.assertTrue(
            any(
                edge["kind"] == "factory_handoff"
                and edge["source"]["id"] == "function:createProgramHost"
                and edge["target"]["id"] == "function:createBuilderProgram"
                and edge["_retrieval_provenance"] == "source_inferred_factory_handoff"
                for edge in edges
            )
        )

    def test_graph_neighbor_localization_keeps_all_originating_obligations(self) -> None:
        states = (
            ObligationProgress(EvidenceObligation("trigger", "Find the watch trigger.", True)),
            ObligationProgress(EvidenceObligation("mechanism", "Trace the watch handoff.", True)),
        )
        semantic = {
            "trigger": ({"path": "src/watchMode.ts"},),
            "mechanism": ({"path": "src/watchMode.ts"},),
        }
        neighbors = (
            {
                "path": "src/helpers.ts",
                "source_paths": ["src/watchMode.ts"],
                "edge_count": 12,
                "edge_kinds": ["calls"],
                "root_connections": [
                    {"path": "src/watchMode.ts", "edge_count": 12, "score": 8.0},
                ],
            },
        )
        requests = []

        class Qdrant:
            def run(self, request):
                requests.append(request)
                return ToolObservation(
                    tool_name=request.tool_name,
                    status="ok",
                    payload={
                        "results": [
                            {
                                "path": "src/helpers.ts",
                                "line_start": 1,
                                "line_end": 2,
                                "text": "function helper() { return true; }",
                                "score": 1.0,
                                "matched_terms": ["watch"],
                            }
                        ]
                    },
                )

        class Resolver:
            def run(self, request):
                return ToolObservation(
                    tool_name=request.tool_name,
                    status="ok",
                    payload={
                        "results": [
                            {
                                "file": "src/helpers.ts",
                                "line_start": 1,
                                "line_end": 2,
                                "nodes": [
                                    {
                                        "id": "function:helper",
                                        "path": "src/helpers.ts",
                                        "name": "helper",
                                        "line_start": 1,
                                        "line_end": 2,
                                    }
                                ],
                            }
                        ]
                    },
                )

        with TemporaryDirectory() as root:
            source = Path(root) / "src" / "helpers.ts"
            source.parent.mkdir(parents=True)
            source.write_text("function helper() {\n  return true;\n}\n", encoding="utf-8")
            ctx = SimpleNamespace(
                config=SimpleNamespace(workspace_root=root),
                trace=SimpleNamespace(record_tool=lambda *args, **kwargs: None, record=lambda *args, **kwargs: None),
            )
            calls = _ground_semantic_root_neighbors(
                ctx,
                states=states,
                semantic_by_obligation=semantic,
                concepts_by_obligation={"trigger": (), "mechanism": ()},
                file_neighbors=neighbors,
                qdrant_tool=Qdrant(),
                resolve_ranges_tool=Resolver(),
            )

        self.assertEqual(calls, 2)
        self.assertEqual(tuple(candidate.path for candidate in states[0].candidates), ("src/helpers.ts",))
        self.assertEqual(tuple(candidate.path for candidate in states[1].candidates), ("src/helpers.ts",))
        self.assertEqual(states[0].candidates[0].obligation_ids, ("trigger",))
        self.assertEqual(states[1].candidates[0].obligation_ids, ("mechanism",))
        self.assertIn("Find the watch trigger.", requests[0].arguments["query"])
        self.assertIn("Trace the watch handoff.", requests[0].arguments["query"])

    def test_exact_graph_range_suppresses_frontier_semantic_localization(self) -> None:
        exact = replace(_candidate("function:owner", "src/owner.ts"), line_start=10, line_end=20)
        ungrounded = replace(exact, node_id="")

        self.assertTrue(_has_usable_exact_graph_ranges((exact,)))
        self.assertFalse(_has_usable_exact_graph_ranges((ungrounded,)))

    def test_range_grounding_prefers_function_covering_chunk_over_previous_method_and_class(self) -> None:
        nodes = (
            {"id": "append", "kind": "method", "line_start": 1443, "line_end": 1464},
            {"id": "binop", "kind": "method", "line_start": 1466, "line_end": 1511},
            {"id": "series", "kind": "class", "line_start": 84, "line_end": 2550},
        )

        selected = _best_overlapping_nodes(nodes, line_start=1464, line_end=1503)

        self.assertEqual(tuple(node["id"] for node in selected), ("binop",))

    def test_rare_exact_error_becomes_seed_only_for_related_obligation(self) -> None:
        confirmation = AnchorConfirmation(
            "error",
            'Error parsing expression: sortRows({ column: "name" })',
            True,
            (
                {
                    "path": "src/exp-parser.js",
                    "line_start": 93,
                    "line_end": 105,
                    "text": "warn(`Error parsing expression: ${exp}`)",
                },
            ),
            "exact_index_text",
        )
        obligations = (
            EvidenceObligation("parser", "Explain directive expression parsing errors.", True),
            EvidenceObligation("render", "Explain server rendering output.", True),
        )

        seeds = _exact_prompt_seed_results((confirmation,), obligations)

        self.assertEqual(tuple(item["path"] for item in seeds["parser"]), ("src/exp-parser.js",))
        self.assertEqual(seeds["render"], ())

    def test_common_or_short_prompt_text_does_not_become_exact_seed(self) -> None:
        common = AnchorConfirmation(
            "error",
            "Error parsing expression in component",
            True,
            ({"path": "src/a.js", "line_start": 1, "line_end": 2, "text": "Error parsing expression"},),
            "repository_common",
        )
        short = AnchorConfirmation(
            "literal",
            "name",
            True,
            ({"path": "src/b.js", "line_start": 1, "line_end": 2, "text": "name"},),
            "exact_index_text",
        )
        obligation = EvidenceObligation("parser", "Explain expression parsing errors.", True)

        seeds = _exact_prompt_seed_results((common, short), (obligation,))

        self.assertEqual(seeds["parser"], ())

    def test_dominant_error_anchor_accepts_source_template_but_rejects_ambiguous_hits(self) -> None:
        anchor = 'Error parsing expression: sortRows({ column: "name" })'
        source = {
            "path": "src/exp-parser.js",
            "line_start": 93,
            "line_end": 105,
            "text": "warn(`Error parsing expression: ${exp}`)",
            "score": 0.9,
        }
        weak_alternative = {
            "path": "docs/errors.md",
            "line_start": 1,
            "line_end": 4,
            "text": "Error parsing expression examples",
            "score": 0.4,
        }
        tied_alternative = {**weak_alternative, "score": 0.85}

        self.assertEqual(
            _dominant_error_anchor_result(anchor, (source, weak_alternative))["path"],
            "src/exp-parser.js",
        )
        self.assertIsNone(_dominant_error_anchor_result(anchor, (source, tied_alternative)))

    def test_focused_semantic_bridge_uses_terminal_snippet_and_adds_grounded_consumer(self) -> None:
        with TemporaryDirectory() as root:
            workspace = Path(root)
            source = workspace / "src" / "render.js"
            source.parent.mkdir()
            source.write_text(
                "function renderNode(node) { return String(node.text); }\n"
                "function renderStartingTag(node) { return '<div>'; }\n",
                encoding="utf-8",
            )
            trigger = ObligationProgress(
                EvidenceObligation("trigger", "Establish text vnode creation.", True),
                candidates=[
                    replace(
                        _candidate_with_text(
                            "function:setText",
                            "src/dom-props.js",
                            "function setText(node, text) { node.children = [new VNode(undefined, undefined, undefined, text)]; }",
                        ),
                        symbol="setText",
                        file_role="implementation",
                        origin="graph_direct_target",
                        provenance_origins=("graph_direct_target",),
                    )
                ],
            )
            effect = ObligationProgress(
                EvidenceObligation(
                    "effect",
                    "Establish how the stored vnode text is serialized into output.",
                    True,
                    ("trigger",),
                    requires_repository_handoff=True,
                )
            )
            qdrant = SimpleNamespace(
                run=lambda request: ToolObservation(
                    tool_name=request.tool_name,
                    status="ok",
                    payload={
                        "results": [
                            {
                                "path": "src/render.js",
                                "line_start": 2,
                                "line_end": 2,
                                "text": "function renderStartingTag(node) { return '<div>'; }",
                                "score": 0.9,
                                "matched_terms": ("render", "node"),
                            }
                        ]
                    },
                )
            )
            resolver = SimpleNamespace(
                run=lambda request: ToolObservation(
                    tool_name=request.tool_name,
                    status="ok",
                    payload={
                        "results": [
                            {
                                "file": "src/render.js",
                                "line_start": 2,
                                "line_end": 2,
                                "nodes": [
                                    {
                                        "id": "function:renderStartingTag",
                                        "name": "renderStartingTag",
                                        "path": "src/render.js",
                                        "line_start": 2,
                                        "line_end": 2,
                                    }
                                ],
                            }
                        ]
                    },
                )
            )
            exact_finder = SimpleNamespace(
                run=lambda request: ToolObservation(
                    tool_name=request.tool_name,
                    status="ok",
                    payload={
                        "nodes": [
                            {
                                "id": "function:renderNode",
                                "kind": "function",
                                "name": "renderNode",
                                "qualified_name": "renderNode",
                                "path": "src/render.js",
                                "line_start": 1,
                                "line_end": 1,
                            }
                        ]
                        if request.arguments.get("query") == "renderNode"
                        else [],
                        "match_count": 1 if request.arguments.get("query") == "renderNode" else 0,
                    },
                )
            )
            expander = SimpleNamespace(
                run=lambda request: ToolObservation(
                    tool_name=request.tool_name,
                    status="ok",
                    payload={"nodes": [], "edges": []},
                )
            )
            ctx = SimpleNamespace(
                config=SimpleNamespace(workspace_root=str(workspace), llm_config=SimpleNamespace()),
                trace=SimpleNamespace(record=lambda *args, **kwargs: None, record_tool=lambda *args, **kwargs: None),
            )

            with patch(
                "services.retrieval.workspace.pipeline.execution_flow.obligation_retrieval.complete_json",
                return_value={
                    "produced_state": "VNode node.text",
                    "consumer_goal": "server rendering serializes text",
                    "produced_terms": ["VNode", "node.text"],
                    "consumer_terms": ["renderNode", "String"],
                },
            ):
                result = _run_focused_semantic_bridge(
                    ctx,
                    states=(trigger, effect),
                    expanded_edges=(),
                    qdrant_tool=qdrant,
                    find_exact_symbol_tool=exact_finder,
                    resolve_ranges_tool=resolver,
                    expand_nodes_tool=expander,
                )

        self.assertTrue(result["attempted"])
        self.assertEqual(result["endpoint_symbol"], "setText")
        self.assertIn("node.text", result["query"])
        self.assertIn("renderNode", {candidate.symbol for candidate in effect.candidates})

    def test_bridge_file_localization_prefers_function_matching_produced_and_consumer_terms(self) -> None:
        selected = _best_bridge_nodes_in_files(
            {
                "src/render.js": (
                    {"id": "start", "kind": "function", "name": "renderStartingTag", "line_start": 347, "line_end": 407},
                    {"id": "node", "kind": "function", "name": "renderNode", "line_start": 74, "line_end": 93},
                )
            },
            query_terms=("VNode", "node.children", "serialize", "render"),
        )

        self.assertEqual([node["name"] for node in selected], ["renderNode"])

    def test_bridge_transition_requires_selected_consumer_evidence(self) -> None:
        endpoint = replace(
            _candidate_with_text("setText", "src/dom-props.js", "function setText() {}"),
            origin="graph_direct_target",
        )
        consumer = replace(
            _candidate_with_text("renderNode", "src/render.js", "function renderNode() {}"),
            origin="focused_semantic_bridge",
        )
        source = ObligationProgress(EvidenceObligation("source", "Source", True), candidates=[endpoint])
        target = ObligationProgress(EvidenceObligation("target", "Target", True), candidates=[endpoint])
        bridge = {
            "endpoint_node_id": "setText",
            "discovered_node_ids": ["renderNode"],
        }

        self.assertEqual(_transition_from_focused_bridge(source, target, bridge)["status"], "unresolved")
        target.candidates.append(consumer)
        self.assertEqual(_transition_from_focused_bridge(source, target, bridge)["status"], "semantic_handoff")

    def test_bridge_prefers_latest_structural_endpoint_over_semantic_candidate(self) -> None:
        semantic = replace(
            _candidate_with_text(
                "function:updateDOMProps",
                "src/runtime/dom-props.js",
                "function updateDOMProps(vnode) { return vnode.data.domProps }",
            ),
            score=5.0,
            symbol="updateDOMProps",
            file_role="implementation",
            origin="semantic_anchor",
            provenance_origins=("semantic_anchor",),
        )
        direct = replace(
            _candidate_with_text(
                "function:setText",
                "src/server/dom-props.js",
                "function setText(node, text) { node.children = [new VNode(undefined, undefined, undefined, text)] }",
            ),
            score=1.0,
            symbol="setText",
            file_role="implementation",
            origin="graph_direct_target",
            provenance_origins=("graph_direct_target",),
        )
        trigger = ObligationProgress(
            EvidenceObligation("trigger", "Establish the input trigger.", True),
            candidates=[semantic],
        )
        mechanism = ObligationProgress(
            EvidenceObligation(
                "mechanism",
                "Establish the mechanism.",
                True,
                ("trigger",),
                requires_repository_handoff=True,
            ),
            candidates=[semantic, direct],
        )
        effect = ObligationProgress(
            EvidenceObligation(
                "effect",
                "Establish the serialized result.",
                True,
                ("mechanism",),
                requires_repository_handoff=True,
            )
        )

        gap = _first_bridge_gap((trigger, mechanism, effect), ())

        self.assertIsNotNone(gap)
        assert gap is not None
        self.assertEqual(gap[0].obligation.id, "mechanism")
        self.assertEqual(gap[1].obligation.id, "effect")
        self.assertEqual(gap[2].symbol, "setText")

    def test_generated_bundle_is_removed_from_retrieval(self) -> None:
        state = ObligationProgress(
            EvidenceObligation("mechanism", "Explain the mechanism", True),
            candidates=[
                _candidate("bundle", "packages/renderer/build.prod.js"),
                _candidate("source", "src/renderer/render.ts"),
            ],
        )

        _remove_generated_candidates({"mechanism": state})

        self.assertEqual(tuple(item.path for item in state.candidates), ("src/renderer/render.ts",))
        self.assertEqual(state.discovery_hints, [])

    def test_evidence_consolidation_rejects_generic_match_and_keeps_direct_mechanism(self) -> None:
        obligation = EvidenceObligation(
            "cause",
            "Explain declaration signature invalidation.",
            True,
            evidence_role=EvidenceRole.IMPLEMENTATION,
        )
        direct = replace(
            _candidate_with_text(
                "shape",
                "src/compiler/builderState.ts",
                "latestSignature = computeHash(firstDts.text); updateExportedModules(sourceFile);",
            ),
            symbol="updateShapeSignature",
            file_role="implementation",
            score=2.0,
            relationship_types=("qualified_reference",),
            source_paths=("src/compiler/builder.ts",),
            origin="semantic_anchor",
            provenance_origins=("semantic_anchor",),
        )
        generic = replace(
            _candidate_with_text(
                "watch",
                "src/compiler/sys.ts",
                "function updateOptionsForWatchFile(options) { return options; }",
            ),
            file_role="implementation",
            score=3.0,
            origin="semantic_anchor",
            provenance_origins=("semantic_anchor",),
        )
        state = ObligationProgress(obligation, candidates=[generic, direct])
        direct_id = _global_candidate_id(direct)
        with TemporaryDirectory() as root:
            ctx = SimpleNamespace(
                config=SimpleNamespace(llm_config=SimpleNamespace()),
                trace=SimpleNamespace(record=lambda *args, **kwargs: None),
            )
            response = {
                "mechanisms": [
                    {
                        "id": "signature_invalidation",
                        "status": "complete",
                        "candidate_ids": [direct_id],
                        "description": "The builder-state function owns signature invalidation.",
                    }
                ],
                "selected_evidence": [
                    {
                        "candidate_id": direct_id,
                        "mechanism_role": "state_owner",
                        "obligation_ids": ["cause"],
                        "reason": "The signature code directly establishes the mechanism.",
                    },
                    {
                        "candidate_id": "wrong:candidate-1",
                        "mechanism_role": "state_owner",
                        "obligation_ids": ["cause"],
                        "reason": "Invalid test ID.",
                    },
                ],
                "obligation_assessments": [
                    {
                        "obligation_id": "cause",
                        "status": "repository_supported",
                        "supporting_candidate_ids": [direct_id],
                        "reason": "The signature code directly establishes the mechanism.",
                        "missing_handoff": "",
                    }
                ],
                "concepts": [
                    {
                        "id": "declaration_signature_change",
                        "proposition": "Declaration text is hashed and exported modules update when it changes.",
                        "supporting_candidate_ids": [direct_id],
                        "obligation_ids": ["cause"],
                    }
                ],
            }
            with patch(
                "services.retrieval.workspace.pipeline.execution_flow.obligation_retrieval.complete_json",
                return_value=response,
            ):
                result = _consolidate_obligation_evidence(ctx, (state,))

        self.assertEqual(tuple(candidate.path for candidate in state.candidates), ("src/compiler/builderState.ts",))
        self.assertIn("wrong:candidate-1", result["invalid_candidate_ids"])
        self.assertEqual(result["concepts"][0]["id"], "declaration_signature_change")

    def test_specific_single_source_qualified_call_enters_frontier(self) -> None:
        _relevance, productive = _qualified_reference_priority(
            {
                "name": "getFilesAffectedBy",
                "path": "src/compiler/builderState.ts",
                "source_count": 1,
                "qualifier_reference_count": 5,
            },
            obligation_terms=_distinctive_terms("Trace watch invalidation."),
            source_path_count=1,
        )
        candidate = replace(
            _candidate("affected", "src/compiler/builderState.ts"),
            file_role="implementation",
        )

        self.assertTrue(productive)
        self.assertEqual(
            _qualified_frontier_paths((candidate,)),
            ("src/compiler/builderState.ts",),
        )

    def test_graph_frontier_does_not_discard_a_connected_file_with_another_role(self) -> None:
        candidate = replace(
            _candidate("watch-test", "src/testRunner/watchMode.ts"),
            file_role="test",
        )

        self.assertEqual(
            _qualified_frontier_paths((candidate,)),
            ("src/testRunner/watchMode.ts",),
        )

    def test_candidate_ledger_accumulates_independent_sources_and_obligations(self) -> None:
        first = replace(
            _candidate("affected", "src/compiler/builderState.ts"),
            origin="graph_owner_qualified_reference",
            relationship="qualified_reference",
            provenance_origins=("graph_owner_qualified_reference",),
            source_paths=("src/compiler/builder.ts",),
            relationship_types=("qualified_reference",),
            obligation_ids=("propagate",),
        )
        second = replace(
            first,
            source_paths=("src/server/project.ts",),
            obligation_ids=("watch",),
        )
        ledger: dict[str, GroundedCandidate] = {}

        _update_promotion_ledger(ledger, (first,))
        _update_promotion_ledger(ledger, (second,))
        merged = tuple(ledger.values())

        self.assertEqual(merged[0].source_paths, ("src/compiler/builder.ts", "src/server/project.ts"))
        self.assertEqual(merged[0].obligation_ids, ("propagate", "watch"))

    def test_exact_promoted_node_uses_narrow_obligation_overlap(self) -> None:
        obligation = EvidenceObligation(
            "propagate",
            "Trace watch build affected files and dependent invalidation.",
            True,
            evidence_role=EvidenceRole.IMPLEMENTATION,
        )
        progress = ObligationProgress(obligation)
        promotion = replace(
            _candidate("affected", "src/compiler/builderState.ts"),
            symbol="getFilesAffectedBy",
            file_role="implementation",
            provenance_origins=("graph_owner_qualified_reference",),
            source_paths=("src/compiler/builder.ts",),
            relationship_types=("qualified_reference",),
            obligation_ids=("propagate",),
        )

        _append_semantic_candidates(
            progress,
            results=(
                {
                    "path": "src/compiler/builderState.ts",
                    "line_start": 267,
                    "line_end": 293,
                    "text": "function getFilesAffectedBy(state) { return affectedFiles; }",
                    "score": 0.05,
                    "matched_terms": ("files",),
                    "file_role": "implementation",
                },
            ),
            nodes_by_range={
                ("src/compiler/builderState.ts", 267, 293): {
                    "id": "affected",
                    "name": "getFilesAffectedBy",
                }
            },
            concepts=("affected files", "watch invalidation"),
            origin="graph_frontier_semantic",
            relationship="graph_frontier",
            promotions=(promotion,),
        )

        self.assertEqual(len(progress.candidates), 1)
        self.assertEqual(progress.candidates[0].source_paths, ("src/compiler/builder.ts",))
        self.assertIn("qualified_reference", progress.candidates[0].relationship_types)

    def test_semantic_candidate_preserves_graph_path_provenance(self) -> None:
        progress = ObligationProgress(
            EvidenceObligation(
                "mechanism",
                "Trace affected file propagation.",
                True,
                evidence_role=EvidenceRole.IMPLEMENTATION,
            )
        )

        _append_semantic_candidates(
            progress,
            results=(
                {
                    "path": "src/compiler/builderState.ts",
                    "line_start": 267,
                    "line_end": 293,
                    "text": "function getFilesAffectedBy() { return affectedFiles; }",
                    "score": 0.2,
                    "matched_terms": ("affected", "files"),
                    "file_role": "implementation",
                },
            ),
            nodes_by_range={
                ("src/compiler/builderState.ts", 267, 293): {"id": "affected", "name": "getFilesAffectedBy"}
            },
            concepts=("affected files",),
            origin="graph_frontier_semantic",
            path_provenance=(
                {
                    "path": "src/compiler/builderState.ts",
                    "score": 8.0,
                    "source_paths": ["src/compiler/builder.ts", "src/server/project.ts"],
                    "relationship_types": ["references", "qualified_reference"],
                },
            ),
        )

        self.assertEqual(
            progress.candidates[0].source_paths,
            ("src/compiler/builder.ts", "src/server/project.ts"),
        )
        self.assertIn("qualified_reference", progress.candidates[0].relationship_types)

    def test_owner_qualified_reference_prefers_specific_multi_source_target_over_utility_fanout(self) -> None:
        terms = _distinctive_terms("Trace which files are affected by the incremental builder.")

        affected_relevance, affected_productive = _qualified_reference_priority(
            {
                "name": "getFilesAffectedBy",
                "path": "src/compiler/builderState.ts",
                "source_count": 2,
                "qualifier_reference_count": 13,
            },
            obligation_terms=terms,
            source_path_count=2,
        )
        _debug_relevance, debug_productive = _qualified_reference_priority(
            {
                "name": "assertDefined",
                "path": "src/compiler/debug.ts",
                "source_count": 2,
                "qualifier_reference_count": 49,
            },
            obligation_terms=terms,
            source_path_count=2,
        )

        self.assertGreater(affected_relevance, 0.0)
        self.assertTrue(affected_productive)
        self.assertFalse(debug_productive)

    def test_focused_search_diversifies_results_across_paths(self) -> None:
        results = tuple(
            SimpleNamespace(chunk=SimpleNamespace(path=path))
            for path in ("src/large.ts", "src/large.ts", "src/neighbor.ts", "src/other.ts")
        )

        selected = _limit_results_per_path(results, limit=3, max_per_path=1)

        self.assertEqual(
            [item.chunk.path for item in selected],
            ["src/large.ts", "src/neighbor.ts", "src/other.ts"],
        )

    def test_qdrant_prefers_exact_structural_range_before_path_diversification(self) -> None:
        results = tuple(
            SimpleNamespace(
                chunk=SimpleNamespace(path=path, line_start=line_start, line_end=line_end)
            )
            for path, line_start, line_end in (
                ("src/compiler/builderState.ts", 334, 358),
                ("src/compiler/builderState.ts", 267, 293),
                ("src/compiler/watch.ts", 10, 30),
            )
        )

        prioritized = _prioritize_preferred_ranges(
            results,
            ({"path": "src/compiler/builderState.ts", "line_start": 267, "line_end": 288},),
        )
        selected = _limit_results_per_path(prioritized, limit=2, max_per_path=1)

        self.assertEqual(
            [(item.chunk.path, item.chunk.line_start) for item in selected],
            [("src/compiler/builderState.ts", 267), ("src/compiler/watch.ts", 10)],
        )

    def test_qdrant_includes_exact_structural_range_missing_from_semantic_results(self) -> None:
        with TemporaryDirectory() as root:
            workspace = Path(root)
            source = workspace / "src" / "server" / "render.js"
            source.parent.mkdir(parents=True)
            source.write_text(
                "\n".join(
                    [*(f"const filler{i} = {i}" for i in range(45)), "function setText (node, text) {}"]
                ),
                encoding="utf-8",
            )
            index = build_index_from_repo(
                repo_path=workspace,
                commit="test",
                chunk_line_count=20,
                chunk_line_overlap=5,
            )

        semantic_result = SimpleNamespace(
            chunk=SimpleNamespace(
                chunk_id="other",
                path="src/other.js",
                line_start=1,
                line_end=20,
            ),
            score=0.9,
        )
        selected = _include_preferred_range_results(
            (semantic_result,),
            index,
            ({"path": "src/server/render.js", "line_start": 46, "line_end": 46},),
        )

        self.assertEqual(selected[0].chunk.path, "src/server/render.js")
        self.assertLessEqual(selected[0].chunk.line_start, 46)
        self.assertGreaterEqual(selected[0].chunk.line_end, 46)
        self.assertEqual(selected[0].retrieval_path, "codegraph_preferred_range")

    def test_qdrant_combines_semantic_and_graph_path_scores(self) -> None:
        results = (
            SimpleNamespace(chunk=SimpleNamespace(path="src/noisy.ts"), score=0.42),
            SimpleNamespace(chunk=SimpleNamespace(path="src/compiler/builderState.ts"), score=0.30),
        )

        prioritized = _prioritize_preferred_paths(
            results,
            (
                {"path": "src/noisy.ts", "score": 1.0},
                {"path": "src/compiler/builderState.ts", "score": 8.0},
            ),
        )

        self.assertEqual(prioritized[0].chunk.path, "src/compiler/builderState.ts")

    def test_graph_preferred_paths_preserve_connection_provenance(self) -> None:
        promoted = replace(
            _candidate("affected", "src/compiler/builderState.ts"),
            source_paths=("src/compiler/builder.ts",),
            relationship_types=("qualified_reference",),
        )

        preferred = _graph_preferred_paths(
            (
                {
                    "path": "src/compiler/builderState.ts",
                    "score": 6,
                    "source_paths": ["src/server/project.ts"],
                    "edge_kinds": ["references"],
                },
            ),
            qualified_candidates=(promoted,),
        )

        self.assertEqual(preferred[0]["path"], "src/compiler/builderState.ts")
        self.assertEqual(
            preferred[0]["source_paths"],
            ["src/server/project.ts", "src/compiler/builder.ts"],
        )
        self.assertIn("qualified_reference", preferred[0]["relationship_types"])

    def test_focused_seed_selection_does_not_share_a_global_expansion_budget(self) -> None:
        obligation = EvidenceObligation("state_change", "Trace state changes.", True)
        progress = ObligationProgress(
            obligation,
            candidates=[
                _candidate_with_score("late-relevant", "src/builder.ts", 3.0),
                _candidate_with_score("secondary", "src/watch.ts", 2.0),
            ],
        )

        selected = _focused_seed_ids(
            progress,
            {
                "unrelated": {"another_obligation"},
                "late-relevant": {"state_change"},
                "secondary": {"state_change"},
            },
            "state_change",
        )

        self.assertEqual(selected, ("late-relevant", "secondary"))

    def test_dependent_obligation_can_expand_from_preceding_stage_evidence(self) -> None:
        dependency = EvidenceObligation("trigger", "Find the trigger.", True)
        mechanism = EvidenceObligation("mechanism", "Trace the mechanism.", True, ("trigger",))
        progress = {
            "trigger": ObligationProgress(
                dependency,
                candidates=[_candidate_with_score("watch", "src/watch.ts", 2.0)],
            ),
            "mechanism": ObligationProgress(mechanism),
        }

        seeds = _dependency_seed_candidates(progress, mechanism)

        self.assertEqual(tuple(candidate.path for candidate in seeds), ("src/watch.ts",))

    def test_focused_frontier_prefers_repeated_native_cross_file_relationships(self) -> None:
        seed = {"id": "builder", "path": "src/builder.ts"}
        edges = (
            {"kind": "references", "source": seed, "target": {"id": "state-type", "path": "src/builderState.ts"}},
            {"kind": "references", "source": seed, "target": {"id": "state-map", "path": "src/builderState.ts"}},
            {"kind": "calls", "source": seed, "target": {"id": "utility", "path": "src/utilities.ts"}},
            {"kind": "calls", "source": seed, "target": {"id": "local", "path": "src/builder.ts"}},
        )

        paths = _focused_frontier_paths(edges, seed_ids=("builder",))

        self.assertEqual(paths, ("src/builderState.ts", "src/utilities.ts"))

    def test_direct_graph_edge_supports_declared_transition(self) -> None:
        source = ObligationProgress(
            EvidenceObligation("trigger", "Establish the trigger.", True),
            candidates=[_candidate("a", "src/a.py")],
        )
        target = ObligationProgress(
            EvidenceObligation("effect", "Establish the effect.", True, ("trigger",)),
            candidates=[_candidate("b", "src/b.py")],
        )
        edges = _edge_index(({"kind": "calls", "source": {"id": "a"}, "target": {"id": "b"}},))

        transition = _transition_from_edges(source, target, edges)

        self.assertEqual(transition, {"from": "trigger", "status": "supported", "relationship": "calls"})

    def test_unconnected_nodes_do_not_claim_a_transition(self) -> None:
        source = ObligationProgress(
            EvidenceObligation("trigger", "Establish the trigger.", True),
            candidates=[_candidate("a", "src/a.py")],
        )
        target = ObligationProgress(
            EvidenceObligation("effect", "Establish the effect.", True, ("trigger",)),
            candidates=[_candidate("b", "src/b.py")],
        )

        self.assertIsNone(_transition_from_edges(source, target, {}))

    def test_reusing_one_node_does_not_claim_forward_progress(self) -> None:
        shared = _candidate("shared", "src/shared.py")
        source = ObligationProgress(
            EvidenceObligation("trigger", "Establish the trigger.", True),
            candidates=[shared],
        )
        target = ObligationProgress(
            EvidenceObligation("effect", "Establish the effect.", True, ("trigger",)),
            candidates=[shared],
        )

        self.assertIsNone(_transition_from_edges(source, target, {}))

    def test_lower_ranked_unselected_node_does_not_claim_a_transition(self) -> None:
        source = ObligationProgress(
            EvidenceObligation("trigger", "Establish the trigger.", True),
            candidates=[_candidate("a", "src/a.py"), _candidate("b", "src/b.py"), _candidate("shared", "src/shared.py")],
        )
        target = ObligationProgress(
            EvidenceObligation("effect", "Establish the effect.", True),
            candidates=[_candidate("c", "src/c.py"), _candidate("d", "src/d.py"), _candidate("shared", "src/shared.py")],
        )

        self.assertIsNone(_transition_from_edges(source, target, {}))

    def test_two_confirmed_anchors_support_a_semantic_handoff_across_snippets(self) -> None:
        source = ObligationProgress(
            EvidenceObligation("mechanism", "Establish serialization.", True),
            candidates=[_candidate_with_text("a", "src/render.js", "domProps.value is serialized for textarea")],
        )
        target = ObligationProgress(
            EvidenceObligation("effect", "Establish output.", True),
            candidates=[_candidate_with_text("b", "test/render.spec.js", "textarea uses domProps value null")],
        )

        transition = _transition_from_shared_anchors(source, target, {"domProps", "value", "textarea", "null"})

        self.assertEqual(transition["status"], "semantic_handoff")
        self.assertIn("domProps", transition["supporting_anchors"])

    def test_one_generic_anchor_does_not_support_a_semantic_handoff(self) -> None:
        source = ObligationProgress(
            EvidenceObligation("mechanism", "Establish serialization.", True),
            candidates=[_candidate_with_text("a", "src/render.js", "value")],
        )
        target = ObligationProgress(
            EvidenceObligation("effect", "Establish output.", True),
            candidates=[_candidate_with_text("b", "test/render.spec.js", "value")],
        )

        self.assertIsNone(_transition_from_shared_anchors(source, target, {"value"}))

    def test_obligation_query_does_not_mix_global_search_terms(self) -> None:
        self.assertEqual(
            _obligation_query("Identify validation tests."),
            "Identify validation tests.",
        )

    def test_unresolved_symbols_only_enrich_related_obligations(self) -> None:
        query = _obligation_query(
            "Show how textarea domProps values are serialized.",
            ("domProps.value", "renderVmWithOptions", "unrelatedSymbol"),
        )

        self.assertIn("domProps.value", query)
        self.assertNotIn("renderVmWithOptions", query)
        self.assertNotIn("unrelatedSymbol", query)

    def test_semantic_candidate_requires_obligation_specific_terms(self) -> None:
        expected = {"tests", "instrumentation", "validation", "filesystem", "probes"}

        unrelated = _semantic_support_score(
            expected,
            {"matched_terms": ["filesystem"]},
        )
        related = _semantic_support_score(
            expected,
            {"matched_terms": ["filesystem", "tests", "validation"]},
        )

        self.assertEqual(unrelated, 0.0)
        self.assertGreater(related, 0.0)

    def test_candidate_concept_coverage_keeps_partial_matches_distinct(self) -> None:
        covered, missing = _concept_coverage(
            ("project references", "wildcard re-exports", "defining consumer handoff"),
            "The program resolves project references and redirect targets.",
        )

        self.assertEqual(covered, ("project references",))
        self.assertEqual(missing, ("wildcard re-exports", "defining consumer handoff"))

    def test_explain_stage_query_keeps_backend_owned_mechanism_terms(self) -> None:
        query = _obligation_stage_query_text(
            EvidenceObligation(
                "why",
                "The generated proposition may describe this as an external handoff.",
                True,
                stage_ids=("explain.why",),
            )
        )

        self.assertIn("State why the established path produces that outcome.", query)
        self.assertIn("invalidation propagation", query)
        self.assertIn("affected dependency", query)
        self.assertIn("external handoff", query)

    def test_camel_case_code_terms_cover_related_prose_concepts(self) -> None:
        self.assertIn("export", _terms("currentAffectedFilesExportedModulesMap"))
        covered, _missing = _concept_coverage(
            ("wildcard re-exports",),
            "currentAffectedFilesExportedModulesMap tracks exported modules",
        )
        self.assertEqual(covered, ("wildcard re-exports",))

    def test_hyphenated_obligation_terms_match_repository_words(self) -> None:
        terms = _distinctive_terms("find module-resolution and web-host boundaries")

        self.assertIn("module", terms)
        self.assertIn("resolution", terms)
        self.assertIn("host", terms)

    def test_repository_prefixed_path_is_confirmed_without_repo_specific_rules(self) -> None:
        with TemporaryDirectory() as root:
            target = Path(root) / "test" / "ssr" / "ssr-string.spec.js"
            target.parent.mkdir(parents=True)
            target.write_text("test", encoding="utf-8")

            resolved = _resolve_repository_path(root, "vue/test/ssr/ssr-string.spec.js")

        self.assertEqual(resolved, "test/ssr/ssr-string.spec.js")

    def test_symbol_matching_explicit_path_stem_is_path_qualified(self) -> None:
        from services.retrieval.workspace.pipeline.execution_flow.obligation_retrieval import AnchorConfirmation

        qualifications = _path_qualifications(
            "Session",
            (
                AnchorConfirmation("path", "src/pure/session.ts", False, (), "prompt_only"),
                AnchorConfirmation("path", "src/main/index.ts", False, (), "prompt_only"),
            ),
        )

        self.assertEqual(tuple(item.value for item in qualifications), ("src/pure/session.ts",))

    def test_connected_note_paths_disambiguate_exact_symbol_nodes(self) -> None:
        from services.retrieval.workspace.pipeline.execution_flow.obligation_retrieval import AnchorConfirmation

        selected = _nodes_in_confirmed_paths(
            (
                {"id": "source", "path": "src/server/render.js", "name": "renderNode"},
                {"id": "bundle", "path": "packages/renderer/build.dev.js", "name": "renderNode"},
            ),
            (
                AnchorConfirmation(
                    "path",
                    "src/server/render.js",
                    True,
                    ({"path": "src/server/render.js"},),
                ),
            ),
        )

        self.assertEqual(tuple(node["id"] for node in selected), ("source",))

    def test_generated_symbol_match_does_not_make_source_match_ambiguous(self) -> None:
        selected = _source_authored_nodes(
            (
                {"id": "source", "path": "src/server/render.js", "name": "renderNode"},
                {"id": "bundle", "path": "packages/renderer/build.dev.js", "name": "renderNode"},
            )
        )

        self.assertEqual(tuple(node["id"] for node in selected), ("source",))

    def test_visible_direct_call_target_survives_without_obligation_term_overlap(self) -> None:
        seed = replace(
            _candidate("renderDOMProps", "src/platforms/web/server/modules/dom-props.js"),
            text="if (key === 'textContent' || key === 'innerHTML') setText(node, props[key])",
        )

        self.assertTrue(
            _is_visible_direct_target(
                relationship="calls",
                target_symbol="setText",
                seed_candidate=seed,
            )
        )
        self.assertFalse(
            _is_visible_direct_target(
                relationship="references",
                target_symbol="unrelatedSymbol",
                seed_candidate=seed,
            )
        )

    def test_direct_target_context_uses_the_call_site_branch(self) -> None:
        seed_text = """if (key === 'textContent' || key === 'innerHTML') {
  setText(node, props[key], key === 'innerHTML')
} else if (key === 'value' && node.tag === 'textarea') {
  setText(node, props[key])
} else {
  res += renderAttr(key, props[key])
}"""
        terms = {"textarea", "value", "serialization", "null"}

        self.assertGreater(
            _direct_target_context_score(terms, seed_text, "setText"),
            _direct_target_context_score(terms, seed_text, "renderAttr"),
        )

    def test_missing_explicit_path_rejects_same_basename_substitute(self) -> None:
        from services.retrieval.workspace.pipeline.execution_flow.obligation_retrieval import AnchorConfirmation

        obligation = EvidenceObligation(
            "subject",
            "Locate the requested Session subject.",
            True,
            anchor_refs=("src/pure/session.ts",),
        )
        confirmations = (
            AnchorConfirmation("path", "src/pure/session.ts", False, (), "prompt_only"),
        )

        self.assertTrue(
            _candidate_conflicts_with_missing_path(
                _candidate("server-session", "src/server/session.ts"),
                obligation,
                confirmations,
            )
        )
        self.assertFalse(
            _candidate_conflicts_with_missing_path(
                _candidate("builder", "src/compiler/builder.ts"),
                obligation,
                confirmations,
            )
        )

    def test_path_qualified_symbol_rejects_different_repository_definition(self) -> None:
        from services.retrieval.workspace.pipeline.execution_flow.obligation_retrieval import AnchorConfirmation

        obligation = EvidenceObligation(
            "subject",
            "Locate the requested Session subject.",
            True,
            anchor_refs=("Session",),
        )
        confirmations = (
            AnchorConfirmation("path", "src/pure/session.ts", False, (), "prompt_only"),
            AnchorConfirmation("symbol", "Session", False, (), "path_qualified_prompt_only"),
        )

        self.assertTrue(
            _candidate_conflicts_with_missing_path(
                replace(
                    _candidate("server-session", "src/server/session.ts"),
                    symbol="Session",
                ),
                obligation,
                confirmations,
            )
        )

    def test_resource_literal_supports_transition_when_codegraph_has_no_document_edge(self) -> None:
        with TemporaryDirectory() as root:
            workspace = Path(root)
            source_path = workspace / "services" / "loader.py"
            target_path = workspace / "services" / "prompts" / "contract.md"
            target_path.parent.mkdir(parents=True)
            source_path.write_text('PROMPT = Path(__file__).parent / "prompts/contract.md"\n', encoding="utf-8")
            target_path.write_text("Contract", encoding="utf-8")
            source = ObligationProgress(
                EvidenceObligation("load", "Load the resource.", True),
                candidates=[_candidate("loader", "services/loader.py")],
            )
            target = ObligationProgress(
                EvidenceObligation("contract", "Establish the resource contract.", True),
                candidates=[_candidate("contract", "services/prompts/contract.md")],
            )
            trace = SimpleNamespace(record_tool=lambda *args, **kwargs: None)
            ctx = SimpleNamespace(config=SimpleNamespace(workspace_root=str(workspace)), trace=trace)
            relationship_tool = SimpleNamespace(
                run=lambda request: ToolObservation(
                    tool_name=request.tool_name,
                    status="ok",
                    payload={"related": False, "edges": []},
                )
            )

            transition, tool_calls = _resolve_file_transition(ctx, source, target, relationship_tool)

        self.assertEqual(tool_calls, 1)
        self.assertEqual(transition["status"], "supported")
        self.assertEqual(transition["relationship"], "resource_reference")
        self.assertEqual(transition["literal"], "prompts/contract.md")

    def test_documentation_role_uses_documentation_source_category(self) -> None:
        self.assertEqual(_source_category_for_role(EvidenceRole.DOCUMENTATION), "documentation")
        self.assertEqual(_source_category_for_role(EvidenceRole.IMPLEMENTATION), "source_code")

    def test_explicit_confirmed_paths_constrain_matching_obligation_role(self) -> None:
        from services.retrieval.workspace.pipeline.execution_flow.obligation_retrieval import AnchorConfirmation

        obligation = EvidenceObligation(
            "contract",
            "Establish the repair contract.",
            True,
            anchor_refs=("services/intent/prompts/repair.md", "services/intent/classifier.py"),
            evidence_role=EvidenceRole.DOCUMENTATION,
        )
        confirmations = (
            AnchorConfirmation(
                "path",
                "services/intent/prompts/repair.md",
                True,
                ({"path": "services/intent/prompts/repair.md"},),
            ),
            AnchorConfirmation(
                "path",
                "services/intent/classifier.py",
                True,
                ({"path": "services/intent/classifier.py"},),
            ),
        )

        self.assertEqual(
            _confirmed_obligation_paths(obligation, confirmations),
            ("services/intent/prompts/repair.md",),
        )

    def test_explicit_test_path_does_not_constrain_implementation_obligation(self) -> None:
        obligation = EvidenceObligation(
            "mechanism",
            "Find the implementation behind the regression test.",
            True,
            anchor_refs=("test/ssr/ssr-string.spec.js",),
            evidence_role=EvidenceRole.IMPLEMENTATION,
        )
        confirmations = (
            AnchorConfirmation(
                "path",
                "test/ssr/ssr-string.spec.js",
                True,
                ({"path": "test/ssr/ssr-string.spec.js"},),
            ),
        )

        self.assertEqual(_confirmed_obligation_paths(obligation, confirmations), ())

    def test_near_duplicate_bundle_is_deranked_behind_connected_source(self) -> None:
        source_text = "function renderDOMProps node props value textarea setText return serialized content owner module"
        bundle_text = "function renderDOMProps node props value textarea setText return serialized content owner module"
        with TemporaryDirectory() as root:
            workspace = Path(root)
            source = workspace / "src" / "render.js"
            bundle = workspace / "packages" / "build.dev.js"
            source.parent.mkdir(parents=True)
            bundle.parent.mkdir(parents=True)
            source.write_text(source_text, encoding="utf-8")
            bundle.write_text(bundle_text * 100, encoding="utf-8")
            progress = {
                "mechanism": ObligationProgress(
                    EvidenceObligation("mechanism", "Trace rendering.", True),
                    candidates=[
                        GroundedCandidate(
                            path="packages/build.dev.js",
                            line_start=1,
                            line_end=2,
                            text=bundle_text,
                            score=1.4,
                            origin="semantic_anchor",
                            node_id="bundle",
                        ),
                        GroundedCandidate(
                            path="src/render.js",
                            line_start=1,
                            line_end=2,
                            text=source_text,
                            score=1.0,
                            origin="semantic_anchor",
                            node_id="source",
                        ),
                    ],
                )
            }

            _apply_duplicate_provenance_ranking(
                progress,
                expanded_edges=(
                    {
                        "source": {"id": "entry", "path": "src/index.js"},
                        "target": {"id": "source", "path": "src/render.js"},
                    },
                ),
                workspace_root=workspace,
            )

        ranked = sorted(progress["mechanism"].candidates, key=lambda candidate: -candidate.score)
        self.assertEqual(ranked[0].path, "src/render.js")

    def test_prompt_literal_requires_exact_repository_text(self) -> None:
        with TemporaryDirectory() as root:
            workspace = Path(root)
            source = workspace / "src" / "render.js"
            source.parent.mkdir(parents=True)
            source.write_text(
                "const expected = '<textarea></textarea>'\n",
                encoding="utf-8",
            )
            index = build_index_from_repo(repo_path=workspace, commit="test")
            qdrant_tool = type("QdrantTool", (), {"index": index})()

            present = _exact_index_anchor_matches(qdrant_tool, "<textarea></textarea>")
            absent = _exact_index_anchor_matches(qdrant_tool, "<textarea>null</textarea>")

        self.assertEqual(present[0]["path"], "src/render.js")
        self.assertEqual(absent, ())

    def test_anchor_distribution_counts_all_chunks_and_paths_while_bounding_samples(self) -> None:
        with TemporaryDirectory() as root:
            workspace = Path(root)
            for index in range(6):
                source = workspace / "src" / f"module_{index}.js"
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_text(f"export const value = {index};\n", encoding="utf-8")
            qdrant_tool = type(
                "QdrantTool",
                (),
                {
                    "index": build_index_from_repo(
                        repo_path=workspace,
                        commit="test",
                        chunk_line_count=1,
                        chunk_line_overlap=0,
                    )
                },
            )()

            distribution = _anchor_index_distribution(qdrant_tool, "value")

        self.assertEqual(distribution["chunk_count"], 6)
        self.assertEqual(distribution["path_count"], 6)
        self.assertEqual(len(distribution["matches"]), 4)
        self.assertTrue(_anchor_is_repository_common(distribution))
        self.assertFalse(_anchor_is_repository_common({"path_count": 1, "chunk_count": 50}))


def _candidate(node_id: str, path: str) -> GroundedCandidate:
    return GroundedCandidate(
        path=path,
        line_start=1,
        line_end=2,
        text="pass",
        score=1.0,
        origin="test",
        node_id=node_id,
    )


def _candidate_with_text(node_id: str, path: str, text: str) -> GroundedCandidate:
    return GroundedCandidate(
        path=path,
        line_start=1,
        line_end=2,
        text=text,
        score=1.0,
        origin="test",
        node_id=node_id,
    )


def _candidate_with_score(node_id: str, path: str, score: float) -> GroundedCandidate:
    return GroundedCandidate(
        path=path,
        line_start=1,
        line_end=2,
        text="function candidate() { return value }",
        score=score,
        origin="test",
        node_id=node_id,
    )


if __name__ == "__main__":
    unittest.main()
