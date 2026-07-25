from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.serve_run_explanation import RunExplanationPage, _infer_repo_root


class RunExplanationPageTests(unittest.TestCase):
    def test_infer_repo_root_prefers_repo_pre_path_from_run_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            snapshot_dir = root / "s" / "abc123"
            snapshot_dir.mkdir(parents=True)
            run_dir = root / "runs" / "run-1"
            run_dir.mkdir(parents=True)
            (run_dir / "run-metadata.json").write_text(
                json.dumps({"repo_pre_path": str(snapshot_dir)}),
                encoding="utf-8",
            )

            inferred = _infer_repo_root(run_dir)

            self.assertEqual(inferred, snapshot_dir)

    def test_page_renders_generated_markdown_and_evidence_links(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repo_root = root / "repo"
            repo_root.mkdir()
            run_dir = root / "run"
            run_dir.mkdir()

            (run_dir / "orchestration-result.json").write_text(
                json.dumps(
                    {
                        "conversation_id": "case-1",
                        "retrieval_result": {
                            "coverage_status": "partial",
                            "sufficient": False,
                            "retrieval_summary": {"selected_count": 1, "retrieval_plan": {"raw_prompt": "Explain this issue."}},
                        },
                        "response_payload": {
                            "content": "# Bottom line\n\nSee [src/compiler/checker.ts:L10-L12](src/compiler/checker.ts#L10-L12).",
                            "metadata": {
                                "generator": "llm_explanation",
                                "prompt_template_id": "comprehension_plan_explanation_v1",
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )
            (run_dir / "evidence-items.json").write_text(
                json.dumps(
                    [
                        {
                            "source_id": "repo-pre:src/compiler/checker.ts:L10-L12",
                            "snippet": "function checkAbstractClass() {\n  return error;\n}",
                            "metadata": {"path": "src/compiler/checker.ts"},
                        }
                    ]
                ),
                encoding="utf-8",
            )

            page = RunExplanationPage(run_dir, repo_root)
            html = page.render()

            self.assertIn("<h1>Bottom line</h1>", html)
            self.assertIn('href="/open?path=', html)
            self.assertIn("function checkAbstractClass()", html)
            self.assertIn('class="promptCard"', html)
            self.assertNotIn("generator: llm_explanation", html)
            self.assertNotIn("prompt: comprehension_plan_explanation_v1", html)
            self.assertNotIn("Primary Source Trail", html)
            self.assertNotIn("How the compiler would represent abstract state", html)

    def test_page_does_not_duplicate_snippet_without_explicit_quote(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repo_root = root / "repo"
            repo_root.mkdir()
            run_dir = root / "run"
            run_dir.mkdir()

            snippet = "function checkAbstractClass() {\n  return error;\n}"
            (run_dir / "orchestration-result.json").write_text(
                json.dumps(
                    {
                        "conversation_id": "case-2",
                        "retrieval_result": {
                            "coverage_status": "partial",
                            "sufficient": False,
                            "retrieval_summary": {"selected_count": 1, "retrieval_plan": {"raw_prompt": "Explain this issue."}},
                        },
                        "response_payload": {
                            "content": "See [src/compiler/checker.ts:L10-L12](src/compiler/checker.ts#L10-L12).",
                            "metadata": {"generator": "llm_explanation"},
                        },
                    }
                ),
                encoding="utf-8",
            )
            (run_dir / "evidence-items.json").write_text(
                json.dumps(
                    [
                        {
                            "source_id": "repo-pre:src/compiler/checker.ts:L10-L12",
                            "snippet": snippet,
                            "metadata": {"path": "src/compiler/checker.ts"},
                        }
                    ]
                ),
                encoding="utf-8",
            )

            page = RunExplanationPage(run_dir, repo_root)
            html = page.render()

            self.assertEqual(html.count("function checkAbstractClass()"), 1)
            self.assertNotIn("<blockquote>", html)

    def test_matched_snippet_renders_inline_header_and_expandable_full_chunk(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repo_root = root / "repo"
            repo_root.mkdir()
            run_dir = root / "run"
            run_dir.mkdir()

            visible_excerpt = "function checkAbstractClass() {\n  return error;\n}"
            full_chunk = "function helper() {\n  return ok;\n}\n\nfunction checkAbstractClass() {\n  return error;\n}\n\nfunction tail() {\n  return done;\n}"
            (run_dir / "orchestration-result.json").write_text(
                json.dumps(
                    {
                        "conversation_id": "case-3",
                        "retrieval_result": {
                            "coverage_status": "partial",
                            "sufficient": False,
                            "retrieval_summary": {"selected_count": 1, "retrieval_plan": {"raw_prompt": "Explain this issue."}},
                        },
                        "response_payload": {
                            "content": (
                                "The key implementation path is here.\n\n"
                                "```ts\n"
                                "function checkAbstractClass() {\n"
                                "  return error;\n"
                                "}\n"
                                "```\n"
                                "[src/compiler/checker.ts:L10-L18](src/compiler/checker.ts#L10-L18)"
                            ),
                            "evidence_refs": ["repo-pre:src/compiler/checker.ts:L10-L18"],
                            "metadata": {"generator": "llm_explanation"},
                        },
                    }
                ),
                encoding="utf-8",
            )
            (run_dir / "evidence-items.json").write_text(
                json.dumps(
                    [
                        {
                            "source_id": "repo-pre:src/compiler/checker.ts:L10-L18",
                            "snippet": full_chunk,
                            "metadata": {"path": "src/compiler/checker.ts"},
                        }
                    ]
                ),
                encoding="utf-8",
            )

            page = RunExplanationPage(run_dir, repo_root)
            html = page.render()

            self.assertIn("Show full", html)
            self.assertIn('class="snippetCard"', html)
            self.assertIn('aria-controls="snippet-full-1"', html)
            self.assertIn("src/compiler/checker.ts:L10-L18", html)
            self.assertIn("function tail()", html)
            self.assertNotIn('<span class="tooltip"><pre>', html)
            self.assertIn('data-snippet-view="expanded"', html)
            self.assertIn('class="snippetHighlight">function checkAbstractClass() {</span>', html)
            self.assertEqual(html.count("src/compiler/checker.ts:L10-L18"), 1)

    def test_inline_bold_renders_as_strong(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repo_root = root / "repo"
            repo_root.mkdir()
            run_dir = root / "run"
            run_dir.mkdir()

            (run_dir / "orchestration-result.json").write_text(
                json.dumps(
                    {
                        "conversation_id": "case-4",
                        "retrieval_result": {
                            "coverage_status": "partial",
                            "sufficient": False,
                            "retrieval_summary": {"selected_count": 0, "retrieval_plan": {"raw_prompt": "Explain this issue."}},
                        },
                        "response_payload": {
                            "content": "1. **Cannot instantiate an abstract class**",
                            "metadata": {"generator": "llm_explanation"},
                        },
                    }
                ),
                encoding="utf-8",
            )
            (run_dir / "evidence-items.json").write_text("[]", encoding="utf-8")

            page = RunExplanationPage(run_dir, repo_root)
            html = page.render()

            self.assertIn("<strong>Cannot instantiate an abstract class</strong>", html)
            self.assertNotIn("**Cannot instantiate an abstract class**", html)

    def test_ordered_list_items_share_one_ordered_list(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repo_root = root / "repo"
            repo_root.mkdir()
            run_dir = root / "run"
            run_dir.mkdir()

            (run_dir / "orchestration-result.json").write_text(
                json.dumps(
                    {
                        "conversation_id": "case-5",
                        "retrieval_result": {
                            "coverage_status": "partial",
                            "sufficient": False,
                            "retrieval_summary": {"selected_count": 0, "retrieval_plan": {"raw_prompt": "Explain this issue."}},
                        },
                        "response_payload": {
                            "content": (
                                "1. **AST representation**\n\n"
                                "- Add `Abstract` to `NodeFlags`.\n\n"
                                "1. **Parsing**\n\n"
                                "- Recognize the keyword.\n\n"
                                "1. **Type checking**\n\n"
                                "- Enforce the rules."
                            ),
                            "metadata": {"generator": "llm_explanation"},
                        },
                    }
                ),
                encoding="utf-8",
            )
            (run_dir / "evidence-items.json").write_text("[]", encoding="utf-8")

            page = RunExplanationPage(run_dir, repo_root)
            html = page.render()

            self.assertEqual(html.count("<ol>"), 1)
            self.assertEqual(html.count("<li><p><strong>"), 3)


if __name__ == "__main__":
    unittest.main()
