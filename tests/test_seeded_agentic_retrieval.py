from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from services.llm.json_completion import _codex_usage_from_stdout
from services.retrieval.agentic.contracts import (
    AgentBudget,
    AgentObligation,
    AgentRetrievalRequest,
    AgentScope,
    AgentState,
    AgentToolOutcome,
    ArtifactRecord,
    InitialLead,
    StructuralHandle,
)
from services.retrieval.agentic.runtime import (
    _decide,
    _referenced_lead_candidates,
    _working_context,
    run_seeded_agent,
)
from services.retrieval.agentic.seed_builder import initial_leads_from_observations
from testing.codeRepoQA.run_case import _load_project_llm_config


class _Trace:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    def record(self, event_type: str, payload: dict) -> None:
        self.events.append((event_type, payload))

    def record_tool(self, request, observation, *, round_index: int) -> None:
        self.events.append(("tool", {"name": request.tool_name, "round": round_index}))


class SeededAgenticRetrievalTests(unittest.TestCase):
    @unittest.skipUnless(
        os.environ.get("RUN_LIVE_AGENTIC_MODEL_TESTS") == "1",
        "Set RUN_LIVE_AGENTIC_MODEL_TESTS=1 for the paid/live provider boundary.",
    )
    def test_live_model_selects_reminded_referenced_lead(self) -> None:
        run_config = json.loads(
            (Path(__file__).resolve().parents[1] / "configs" / "testing" / "agentic.json").read_text(
                encoding="utf-8"
            )
        )
        request = AgentRetrievalRequest(
            request_id="live-reference-probe",
            question="Trace how the flex wrapper delegates the operation.",
            workspace_root=".",
            obligations=(AgentObligation("o1", "Trace the delegated binary operation"),),
            initial_leads=(
                InitialLead("flex", "ops.py", 1, 2, "return self._binop(other, op)", "implementation"),
                InitialLead(
                    "binop", "series.py", 10, 20, "def _binop", "implementation",
                    structural_handles=(StructuralHandle("node-binop", "Series::_binop", "series.py", 10, 20),),
                ),
            ),
            scope=AgentScope(),
            budget=AgentBudget(max_iterations=5, max_tool_calls=5, max_no_gain_iterations=1),
        )
        state = AgentState(
            request=request,
            artifacts={
                "flex": ArtifactRecord(
                    "flex", "ops.py", 1, 2, "1: return self._binop(other, op)",
                    symbol="flex_wrapper", inspected=True, status="inspected",
                ),
                "binop": ArtifactRecord("binop", "series.py", 10, 20, "", symbol="Series::_binop"),
            },
            initial_lead_ids=("flex", "binop"),
            open_questions=["Trace the delegated binary operation"],
            tool_outcomes=[
                AgentToolOutcome(2, "exact_search", "ok", "exact_search|def add", "matches=0")
            ],
            referenced_lead_reminders={"binop": 1},
            iteration=3,
            no_gain_iterations=0,
        )

        decision = _decide(
            state,
            _working_context(state),
            llm_config=_load_project_llm_config(run_config),
            trace=_Trace(),
        )

        self.assertTrue(
            any(call.tool == "inspect_lead" and call.lead_id == "binop" for call in decision.tool_calls),
            decision,
        )

    def test_codex_json_completion_usage_is_read_from_jsonl(self) -> None:
        stdout = "\n".join((
            '{"type":"turn.started"}',
            '{"type":"turn.completed","usage":{"input_tokens":120,"output_tokens":30}}',
        ))

        self.assertEqual(
            _codex_usage_from_stdout(stdout),
            {"input_tokens": 120, "output_tokens": 30, "total_tokens": 150},
        )

    def test_seed_builder_preserves_distinct_structural_handles(self) -> None:
        provenance = (
            SimpleNamespace(
                retriever="qdrant_hybrid",
                query_id="q:o1",
                obligation_ids=("o1",),
                ranks=(1,),
                scores=(0.9,),
            ),
        )
        observations = (
            SimpleNamespace(
                id="lead-a",
                handle=SimpleNamespace(
                    path="pkg/file.py", line_start=10, line_end=20,
                    node_id="node-a", symbol="A", full_line_start=8, full_line_end=25, adapter="codegraph_node",
                ),
                provenance=provenance,
                observed_text="chunk",
                artifact_role="implementation",
                obligation_ids=("o1",),
            ),
            SimpleNamespace(
                id="lead-b",
                handle=SimpleNamespace(
                    path="pkg/file.py", line_start=10, line_end=20,
                    node_id="node-b", symbol="B", full_line_start=20, full_line_end=40, adapter="codegraph_node",
                ),
                provenance=provenance,
                observed_text="chunk",
                artifact_role="implementation",
                obligation_ids=("o1",),
            ),
        )

        leads = initial_leads_from_observations(observations)

        self.assertEqual([item.id for item in leads], ["lead-a", "lead-b"])
        self.assertEqual({item.structural_handles[0].node_id for item in leads}, {"node-a", "node-b"})

    def test_empty_tool_result_is_persisted_in_next_working_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "seed.py").write_text("value = 1\n", encoding="utf-8")
            request = AgentRetrievalRequest(
                request_id="run-tool-outcome",
                question="Find missing_symbol",
                workspace_root=str(root),
                obligations=(AgentObligation("o1", "Find missing_symbol"),),
                initial_leads=(InitialLead("lead", "seed.py", 1, 1, "value = 1", "implementation"),),
                scope=AgentScope(),
                budget=AgentBudget(max_iterations=3, max_tool_calls=3),
            )
            contexts: list[dict] = []

            def decide(_config, messages, **_kwargs):
                contexts.append(json.loads(messages[1]["content"]))
                if len(contexts) == 1:
                    return {
                        "kind": "tool_calls", "summary": "Search", "open_questions": ["Find it"],
                        "tool_calls": [{
                            "tool": "exact_search", "purpose": "Find symbol", "expected_signal": "definition",
                            "lead_id": "", "path": "", "line_start": 0, "line_end": 0,
                            "node_id": "", "direction": "both", "query": "missing_symbol", "limit": 5,
                        }],
                        "findings": [], "final_evidence_ids": [], "reason": "Need source",
                    }
                return {
                    "kind": "fail", "summary": "Not found", "open_questions": ["Find it"],
                    "tool_calls": [], "findings": [], "final_evidence_ids": [], "reason": "No match",
                }

            with patch("services.retrieval.agentic.runtime.complete_json", side_effect=decide):
                run_seeded_agent(
                    request,
                    llm_config=SimpleNamespace(model="fake", api_style="fake"),
                    qdrant_tool=SimpleNamespace(),
                    structural_tools={},
                    trace=_Trace(),
                )

        self.assertEqual(contexts[1]["recent_tool_outcomes"][0]["tool"], "exact_search")
        self.assertEqual(contexts[1]["recent_tool_outcomes"][0]["result_summary"], "matches=0")

    def test_inspected_symbol_reference_surfaces_exact_uninspected_lead(self) -> None:
        request = AgentRetrievalRequest(
            request_id="run-reference",
            question="Trace binary operation",
            workspace_root=".",
            obligations=(AgentObligation("o1", "Trace binary operation"),),
            initial_leads=(
                InitialLead("flex", "ops.py", 1, 2, "return self._binop(other, op)", "implementation"),
                InitialLead(
                    "binop", "series.py", 10, 20, "def _binop", "implementation",
                    structural_handles=(StructuralHandle("node-binop", "Series::_binop", "series.py", 10, 20),),
                ),
                InitialLead(
                    "other", "series.py", 30, 40, "def unrelated", "implementation",
                    structural_handles=(StructuralHandle("node-other", "Series::unrelated", "series.py", 30, 40),),
                ),
            ),
            scope=AgentScope(),
            budget=AgentBudget(),
        )
        state = AgentState(
            request=request,
            artifacts={
                "flex": ArtifactRecord(
                    "flex", "ops.py", 1, 2, "1: return self._binop(other, op)",
                    symbol="flex_wrapper", inspected=True, status="inspected",
                ),
                "binop": ArtifactRecord("binop", "series.py", 10, 20, "", symbol="Series::_binop"),
                "other": ArtifactRecord("other", "series.py", 30, 40, "", symbol="Series::unrelated"),
            },
            initial_lead_ids=("flex", "binop", "other"),
        )

        first = _referenced_lead_candidates(state)
        second = _referenced_lead_candidates(state)

        self.assertEqual(first, second)
        self.assertEqual([item["lead"]["id"] for item in first], ["binop"])
        self.assertEqual(first[0]["referenced_as"], "self._binop")

    def test_context_compaction_retains_reminded_referenced_lead(self) -> None:
        artifacts = {
            "flex": ArtifactRecord(
                "flex", "ops.py", 1, 80, "return self._binop(other, op)\n" + ("body " * 500),
                symbol="flex_wrapper", inspected=True, status="inspected",
            ),
            "binop": ArtifactRecord(
                "binop", "series.py", 100, 180, "def _binop", symbol="Series::_binop",
            ),
        }
        initial_ids = ["flex"]
        for index in range(28):
            artifact_id = f"noise-{index}"
            artifacts[artifact_id] = ArtifactRecord(
                artifact_id, f"noise/{index}.py", 1, 80, "noise " * 500,
                symbol=f"noise_{index}", inspected=True, status="inspected",
            )
            initial_ids.append(artifact_id)
        initial_ids.append("binop")
        request = AgentRetrievalRequest(
            request_id="run-compaction",
            question="Trace binary operation",
            workspace_root=".",
            obligations=(AgentObligation("o1", "Trace binary operation"),),
            initial_leads=(),
            scope=AgentScope(),
            budget=AgentBudget(max_context_chars=12000),
        )
        state = AgentState(
            request=request,
            artifacts=artifacts,
            initial_lead_ids=tuple(initial_ids),
            recent_artifact_ids=list(initial_ids[:-1]),
            referenced_lead_reminders={"binop": 1},
            tool_outcomes=[
                AgentToolOutcome(index, "open_source", "ok", f"call-{index}", "artifact=noise", ())
                for index in range(20)
            ],
        )

        context = json.loads(_working_context(state))

        self.assertLessEqual(len(json.dumps(context, sort_keys=True)), 12000)
        self.assertIn("binop", context["reminded_referenced_lead_ids"])
        self.assertEqual(context["referenced_lead_candidates"][0]["lead"]["id"], "binop")

    def test_agent_can_select_evidence_outside_initial_qdrant_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "seed.py").write_text("def seed():\n    return helper()\n", encoding="utf-8")
            (root / "other.py").write_text("def helper():\n    return 42\n", encoding="utf-8")
            request = AgentRetrievalRequest(
                request_id="run-1",
                question="Where is helper behavior implemented?",
                workspace_root=str(root),
                obligations=(AgentObligation("o1", "Find the helper implementation"),),
                initial_leads=(
                    InitialLead(
                        id="lead-1", path="seed.py", line_start=1, line_end=2,
                        preview="def seed():", artifact_kind="implementation",
                        obligation_ids=("o1",),
                        structural_handles=(StructuralHandle("node-seed", "seed", "seed.py", 1, 2),),
                    ),
                ),
                scope=AgentScope(),
                budget=AgentBudget(max_iterations=4, max_tool_calls=4),
            )
            external_id = "artifact_" + hashlib.sha1(
                "other.py:1:2::open_source".encode("utf-8")
            ).hexdigest()[:16]
            decisions = (
                {
                    "kind": "finish", "summary": "Incorrectly claims completion before inspection.",
                    "open_questions": [], "tool_calls": [], "reason": "Invalid premature finish.",
                    "findings": [{
                        "statement": "ungrounded", "evidence_ids": ["https://example.invalid/source"],
                        "obligation_ids": ["o1"],
                    }],
                    "final_evidence_ids": ["https://example.invalid/source"],
                },
                {
                    "kind": "tool_calls", "summary": "Inspect the implementation named by the seed.",
                    "open_questions": ["Find the helper implementation"], "findings": [],
                    "final_evidence_ids": [], "reason": "Need source outside the initial path.",
                    "tool_calls": [{
                        "tool": "open_source", "purpose": "Inspect helper implementation",
                        "expected_signal": "helper body", "lead_id": "", "path": "other.py",
                        "line_start": 1, "line_end": 2, "node_id": "", "direction": "outgoing",
                        "query": "", "limit": 12,
                    }],
                },
                {
                    "kind": "finish", "summary": "The helper implementation is grounded.",
                    "open_questions": [], "tool_calls": [], "reason": "Complete",
                    "findings": [{
                        "statement": "helper returns 42", "evidence_ids": [external_id],
                        "obligation_ids": ["o1"],
                    }],
                    "final_evidence_ids": [external_id],
                },
            )
            trace = _Trace()
            with patch("services.retrieval.agentic.runtime.complete_json", side_effect=decisions):
                report = run_seeded_agent(
                    request,
                    llm_config=SimpleNamespace(model="fake", api_style="fake"),
                    qdrant_tool=SimpleNamespace(),
                    structural_tools={},
                    trace=trace,
                )

        self.assertTrue(report.sufficient)
        self.assertEqual(report.evidence[0].path, "other.py")
        self.assertEqual(report.execution["selected_outside_initial_paths"], 1)
        self.assertEqual(report.execution["iterations"], 3)
        self.assertIn("agent_finish_rejected", [event for event, _payload in trace.events])

    def test_provider_failure_is_not_replaced_by_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "seed.py").write_text("value = 1\n", encoding="utf-8")
            request = AgentRetrievalRequest(
                request_id="run-fail",
                question="Explain value",
                workspace_root=str(root),
                obligations=(AgentObligation("o1", "Explain value"),),
                initial_leads=(InitialLead("lead", "seed.py", 1, 1, "value = 1", "implementation"),),
                scope=AgentScope(),
                budget=AgentBudget(max_iterations=1, max_tool_calls=1),
            )
            with patch(
                "services.retrieval.agentic.runtime.complete_json",
                side_effect=RuntimeError("provider unavailable"),
            ):
                with self.assertRaisesRegex(RuntimeError, "provider unavailable"):
                    run_seeded_agent(
                        request,
                        llm_config=SimpleNamespace(model="fake", api_style="fake"),
                        qdrant_tool=SimpleNamespace(),
                        structural_tools={},
                        trace=_Trace(),
                    )

    def test_no_gain_uses_model_only_final_synthesis(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "seed.py").write_text("value = 1\n", encoding="utf-8")
            request = AgentRetrievalRequest(
                request_id="run-finalize",
                question="Explain value",
                workspace_root=str(root),
                obligations=(AgentObligation("o1", "Explain value"),),
                initial_leads=(InitialLead("lead", "seed.py", 1, 1, "value = 1", "implementation"),),
                scope=AgentScope(),
                budget=AgentBudget(
                    max_iterations=4,
                    max_tool_calls=4,
                    max_no_gain_iterations=1,
                ),
            )
            inspect_call = {
                "tool": "inspect_lead", "purpose": "Read source", "expected_signal": "value",
                "lead_id": "lead", "path": "", "line_start": 0, "line_end": 0,
                "node_id": "", "direction": "outgoing", "query": "", "limit": 12,
            }
            decisions = (
                {
                    "kind": "tool_calls", "summary": "Inspect", "open_questions": ["Explain value"],
                    "tool_calls": [inspect_call], "findings": [], "final_evidence_ids": [], "reason": "Read it",
                },
                {
                    "kind": "tool_calls", "summary": "Repeats", "open_questions": ["Explain value"],
                    "tool_calls": [inspect_call], "findings": [], "final_evidence_ids": [], "reason": "Repeat",
                },
                {
                    "kind": "finish", "summary": "Grounded", "open_questions": [], "tool_calls": [],
                    "findings": [{
                        "statement": "value is assigned 1", "evidence_ids": ["lead"],
                        "obligation_ids": ["o1"],
                    }],
                    "final_evidence_ids": ["lead"], "reason": "Best inspected evidence",
                },
            )
            trace = _Trace()
            with patch("services.retrieval.agentic.runtime.complete_json", side_effect=decisions):
                report = run_seeded_agent(
                    request,
                    llm_config=SimpleNamespace(model="fake", api_style="fake"),
                    qdrant_tool=SimpleNamespace(),
                    structural_tools={},
                    trace=trace,
                )

        self.assertTrue(report.sufficient)
        self.assertEqual(report.stop_reason, "forced_final_after_no_executable_tool_call")
        self.assertIn("agent_forced_final_decision", [event for event, _payload in trace.events])

    def test_no_gain_is_deferred_for_exact_referenced_lead(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "ops.py").write_text("return self._binop(other, op)\n", encoding="utf-8")
            (root / "series.py").write_text("def _binop(self, other, op):\n    return op(self, other)\n", encoding="utf-8")
            request = AgentRetrievalRequest(
                request_id="run-reference-guard",
                question="Trace binary operation",
                workspace_root=str(root),
                obligations=(AgentObligation("o1", "Trace binary operation"),),
                initial_leads=(
                    InitialLead(
                        "flex", "ops.py", 1, 1, "return self._binop(other, op)", "implementation",
                        structural_handles=(StructuralHandle("node-flex", "flex_wrapper", "ops.py", 1, 1),),
                    ),
                    InitialLead(
                        "binop", "series.py", 1, 2, "def _binop", "implementation",
                        structural_handles=(StructuralHandle("node-binop", "Series::_binop", "series.py", 1, 2),),
                    ),
                ),
                scope=AgentScope(),
                budget=AgentBudget(max_iterations=5, max_tool_calls=5, max_no_gain_iterations=1),
            )
            contexts: list[dict] = []

            def tool_call(tool: str, *, lead_id: str = "", query: str = "") -> dict:
                return {
                    "tool": tool, "purpose": "Investigate", "expected_signal": "source",
                    "lead_id": lead_id, "path": "", "line_start": 0, "line_end": 0,
                    "node_id": "", "direction": "both", "query": query, "limit": 5,
                }

            def decide(_config, messages, **_kwargs):
                contexts.append(json.loads(messages[1]["content"]))
                index = len(contexts)
                if index == 1:
                    calls = [tool_call("inspect_lead", lead_id="flex")]
                elif index == 2:
                    calls = [tool_call("exact_search", query="def __add__")]
                elif index == 3:
                    calls = [tool_call("inspect_lead", lead_id="binop")]
                else:
                    return {
                        "kind": "finish", "summary": "Grounded", "open_questions": [], "tool_calls": [],
                        "findings": [{
                            "statement": "flex_wrapper calls Series._binop", "evidence_ids": ["flex", "binop"],
                            "obligation_ids": ["o1"],
                        }],
                        "final_evidence_ids": ["flex", "binop"], "reason": "Reference followed",
                    }
                return {
                    "kind": "tool_calls", "summary": "Investigate", "open_questions": ["Trace it"],
                    "tool_calls": calls, "findings": [], "final_evidence_ids": [], "reason": "Need source",
                }

            trace = _Trace()
            with patch("services.retrieval.agentic.runtime.complete_json", side_effect=decide):
                report = run_seeded_agent(
                    request,
                    llm_config=SimpleNamespace(model="fake", api_style="fake"),
                    qdrant_tool=SimpleNamespace(),
                    structural_tools={},
                    trace=trace,
                )

        self.assertTrue(report.sufficient)
        self.assertEqual(contexts[2]["reminded_referenced_lead_ids"], ["binop"])
        self.assertIn(
            "agent_no_gain_deferred_for_referenced_leads",
            [event for event, _payload in trace.events],
        )


if __name__ == "__main__":
    unittest.main()
