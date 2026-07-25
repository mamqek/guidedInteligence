from __future__ import annotations

import unittest

from core.source_policy import SourceCategory
from services.retrieval.workspace.connected_context import (
    ConnectedSourceContextSettings,
    ConnectedSourceContextStage,
    ConnectedSourceHandle,
)
from services.retrieval.config import ConnectedSourceDocument, RunLLMConfig


def _llm_config() -> RunLLMConfig:
    return RunLLMConfig(
        model="test-model",
        endpoint_url="http://example.invalid/chat/completions",
        api_key="test-key",
    )


def _document(source_id: str, *, source_key: str = "github_issues", content: str = "context") -> ConnectedSourceDocument:
    return ConnectedSourceDocument(
        source_category=SourceCategory.ISSUE_TRACKER,
        source_key=source_key,
        source_id=source_id,
        title=f"Title for {source_id}",
        content=content,
        metadata={"provider": "github", "source_key": source_key},
    )


def _query_plan(*source_keys: str) -> dict[str, object]:
    return {
        "queries": [
            {
                "source_key": source_key,
                "query": "abstract class parsing validation",
                "reason": "This source may contain design context.",
                "should_query": True,
            }
            for source_key in source_keys
        ]
    }


def _analysis(
    source_id: str,
    *,
    accept: bool,
    include_unknown_signal: bool = False,
) -> dict[str, object]:
    source_ids = [source_id] if accept else []
    retrieval_terms = [
        {"value": "abstract class validation", "source_ids": source_ids},
    ]
    if include_unknown_signal:
        retrieval_terms.append({"value": "invented unsupported term", "source_ids": ["unknown"]})
    return {
        "ranked_documents": [
            {
                "source_id": source_id,
                "relevance_score": 0.9 if accept else 0.1,
                "decision": "accept" if accept else "reject",
                "reason": "Useful implementation context." if accept else "Only a lexical overlap.",
                "contribution_type": "behavior" if accept else "terminology_only",
                "adds_code_retrieval_signal": accept,
                "currentness": "current",
                "confidence": "high" if accept else "low",
                "context_use": accept,
                "evidence_use": accept,
            }
        ],
        "signals": {
            "retrieval_terms": retrieval_terms,
            "file_hints": [],
            "symbol_hints": [
                {"value": "checkClassDeclaration", "source_ids": source_ids}
            ],
            "suggested_subqueries": [
                {"value": "Where are abstract class declarations validated?", "source_ids": source_ids}
            ],
        },
        "facts": [
            {"text": "Abstract declarations require semantic validation.", "source_ids": source_ids}
        ],
        "conflicts": [],
    }


class ConnectedSourceContextStageTests(unittest.TestCase):
    def test_no_sources_is_inert_and_does_not_call_llm(self) -> None:
        calls: list[object] = []

        def completion(*args, **kwargs):
            calls.append((args, kwargs))
            raise AssertionError("LLM must not run when no connected source is selected")

        result = ConnectedSourceContextStage(
            llm_config=_llm_config(),
            complete_json_fn=completion,
        ).run(prompt="Explain parsing", prompt_evidence={}, sources=())

        self.assertEqual((), result.documents)
        self.assertEqual(0, result.usage.get("llm_calls", 0))
        self.assertEqual([], calls)

    def test_relevant_document_produces_provenanced_context_and_evidence(self) -> None:
        responses = iter((_query_plan("github_issues"), _analysis("issue:1", accept=True)))

        def completion(*args, **kwargs):
            return next(responses)

        result = ConnectedSourceContextStage(
            llm_config=_llm_config(),
            complete_json_fn=completion,
        ).run(
            prompt="Explain abstract class parsing and validation",
            prompt_evidence={"grounded_entities": ["abstract class"]},
            sources=(
                ConnectedSourceHandle(
                    source_key="github_issues",
                    provider="github",
                    name="GitHub issues",
                    search=lambda query: (_document("issue:1", content="A human discussion of semantic checks."),),
                ),
            ),
        )

        self.assertEqual(("issue:1",), result.selected_context_ids)
        self.assertEqual(("issue:1",), result.selected_evidence_ids)
        self.assertIn("abstract class validation", result.retrieval_terms)
        self.assertEqual(("issue:1",), result.signal_provenance["retrieval_terms:abstract class validation"])
        self.assertEqual(2, result.usage["llm_calls"])

    def test_irrelevant_document_cannot_influence_context_or_evidence(self) -> None:
        responses = iter((_query_plan("github_issues"), _analysis("issue:noise", accept=False)))
        result = ConnectedSourceContextStage(
            llm_config=_llm_config(),
            complete_json_fn=lambda *args, **kwargs: next(responses),
        ).run(
            prompt="Explain abstract class parsing and validation",
            prompt_evidence={},
            sources=(
                ConnectedSourceHandle(
                    source_key="github_issues",
                    provider="github",
                    name="GitHub issues",
                    search=lambda query: (_document("issue:noise", content="A release planning note with no code context."),),
                ),
            ),
        )

        self.assertEqual((), result.selected_context_ids)
        self.assertEqual((), result.selected_evidence_ids)
        self.assertEqual((), result.retrieval_terms)
        self.assertEqual((), result.selected_context_documents)

    def test_uncertain_stale_document_is_blocked_even_when_model_requests_context(self) -> None:
        analysis = _analysis("obsidian:old.md", accept=True)
        decision = analysis["ranked_documents"][0]
        decision["contribution_type"] = "implementation_history"
        decision["currentness"] = "uncertain"
        decision["confidence"] = "low"
        responses = iter((_query_plan("local_notes"), analysis))
        result = ConnectedSourceContextStage(
            llm_config=_llm_config(),
            complete_json_fn=lambda *args, **kwargs: next(responses),
        ).run(
            prompt="Explain parsing",
            prompt_evidence={},
            sources=(
                ConnectedSourceHandle(
                    "local_notes",
                    "obsidian",
                    "Obsidian",
                    lambda query: (
                        _document("obsidian:old.md", source_key="local_notes", content="An old uncertain note."),
                    ),
                ),
            ),
        )

        self.assertEqual((), result.selected_context_ids)
        self.assertEqual((), result.selected_evidence_ids)

    def test_explicit_stale_guidance_is_blocked_even_when_model_marks_current(self) -> None:
        analysis = _analysis("notion:stale", accept=True)
        analysis["signals"]["file_hints"] = [
            {"value": "src/runtime/notionLegacyCert.ts", "source_ids": ["notion:stale"]}
        ]
        responses = iter((_query_plan("notion"), analysis))
        result = ConnectedSourceContextStage(
            llm_config=_llm_config(),
            complete_json_fn=lambda *args, **kwargs: next(responses),
        ).run(
            prompt="Explain certification owner behavior",
            prompt_evidence={},
            sources=(
                ConnectedSourceHandle(
                    "notion",
                    "notion",
                    "Notion",
                    lambda query: (
                        _document(
                            "notion:stale",
                            source_key="notion",
                            content=(
                                "This is stale/superseded connector-cert data.\n"
                                "Do not use as current owner guidance.\n"
                                "owner file: `src/runtime/notionLegacyCert.ts`"
                            ),
                        ),
                    ),
                ),
            ),
        )

        self.assertEqual((), result.selected_context_ids)
        self.assertEqual((), result.selected_evidence_ids)
        self.assertEqual((), result.file_hints)
        self.assertEqual((), result.facts)

    def test_configured_empty_stale_terms_disable_deterministic_guidance_block(self) -> None:
        analysis = _analysis("notion:stale", accept=True)
        responses = iter((_query_plan("notion"), analysis))
        result = ConnectedSourceContextStage(
            llm_config=_llm_config(),
            settings=ConnectedSourceContextSettings(stale_block_terms=()),
            complete_json_fn=lambda *args, **kwargs: next(responses),
        ).run(
            prompt="Explain certification owner behavior",
            prompt_evidence={},
            sources=(
                ConnectedSourceHandle(
                    "notion",
                    "notion",
                    "Notion",
                    lambda query: (
                        _document(
                            "notion:stale",
                            source_key="notion",
                            content=(
                                "This is stale/superseded connector-cert data.\n"
                                "Do not use as current owner guidance."
                            ),
                        ),
                    ),
                ),
            ),
        )

        self.assertEqual(("notion:stale",), result.selected_context_ids)
        self.assertEqual(("notion:stale",), result.selected_evidence_ids)

    def test_provider_failure_is_isolated_from_successful_source(self) -> None:
        def fail(_query: str):
            raise RuntimeError("provider unavailable")

        responses = iter(
            (
                _query_plan("github_issues", "local_notes"),
                _analysis("obsidian:note.md", accept=True),
            )
        )
        result = ConnectedSourceContextStage(
            llm_config=_llm_config(),
            complete_json_fn=lambda *args, **kwargs: next(responses),
        ).run(
            prompt="Explain abstract class parsing and validation",
            prompt_evidence={},
            sources=(
                ConnectedSourceHandle("github_issues", "github", "GitHub issues", fail),
                ConnectedSourceHandle(
                    "local_notes",
                    "obsidian",
                    "Obsidian",
                    lambda query: (
                        _document("obsidian:note.md", source_key="local_notes", content="A design note."),
                    ),
                ),
            ),
        )

        self.assertEqual(("obsidian:note.md",), result.selected_context_ids)
        self.assertEqual("github_issues", result.failures[0].source_key)
        self.assertIn("provider unavailable", result.failures[0].reason)

    def test_connected_evidence_is_capped_after_ranking(self) -> None:
        ids = ("issue:1", "issue:2", "issue:3")
        analysis = {
            "ranked_documents": [
                {
                    "source_id": source_id,
                    "relevance_score": 0.9 - index * 0.1,
                    "decision": "accept",
                    "reason": "Concrete behavior context.",
                    "contribution_type": "behavior",
                    "adds_code_retrieval_signal": True,
                    "currentness": "current",
                    "confidence": "high",
                    "context_use": True,
                    "evidence_use": True,
                }
                for index, source_id in enumerate(ids)
            ],
            "signals": {
                "retrieval_terms": [],
                "file_hints": [],
                "symbol_hints": [],
                "suggested_subqueries": [],
            },
            "facts": [],
            "conflicts": [],
        }
        responses = iter((_query_plan("github_issues"), analysis))
        result = ConnectedSourceContextStage(
            llm_config=_llm_config(),
            complete_json_fn=lambda *args, **kwargs: next(responses),
        ).run(
            prompt="Explain parsing",
            prompt_evidence={},
            sources=(
                ConnectedSourceHandle(
                    "github_issues",
                    "github",
                    "GitHub issues",
                    lambda query: tuple(_document(source_id) for source_id in ids),
                ),
            ),
        )

        self.assertEqual(ids, result.selected_context_ids)
        self.assertEqual(ids[:2], result.selected_evidence_ids)

    def test_required_llm_failure_is_not_replaced(self) -> None:
        stage = ConnectedSourceContextStage(
            llm_config=_llm_config(),
            complete_json_fn=lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("LLM unavailable")),
        )

        with self.assertRaisesRegex(RuntimeError, "LLM unavailable"):
            stage.run(
                prompt="Explain parsing",
                prompt_evidence={},
                sources=(
                    ConnectedSourceHandle(
                        "github_issues",
                        "github",
                        "GitHub issues",
                        lambda query: (_document("issue:1"),),
                    ),
                ),
            )

    def test_invented_signal_source_id_fails_validation(self) -> None:
        responses = iter(
            (
                _query_plan("github_issues"),
                _analysis("issue:1", accept=True, include_unknown_signal=True),
            )
        )
        stage = ConnectedSourceContextStage(
            llm_config=_llm_config(),
            complete_json_fn=lambda *args, **kwargs: next(responses),
        )

        with self.assertRaisesRegex(RuntimeError, "unsupported source IDs"):
            stage.run(
                prompt="Explain parsing",
                prompt_evidence={},
                sources=(
                    ConnectedSourceHandle(
                        "github_issues",
                        "github",
                        "GitHub issues",
                        lambda query: (_document("issue:1"),),
                    ),
                ),
            )


if __name__ == "__main__":
    unittest.main()

