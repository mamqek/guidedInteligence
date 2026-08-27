from dataclasses import replace
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from services.retrieval.workspace.pipeline.execution_flow.discovery_observations import SourceHandle
from services.retrieval.workspace.pipeline.execution_flow.source_disclosure import DisclosureCard
from services.retrieval.workspace.pipeline.execution_flow.evidence_qualification import (
    QualificationReuseCache, qualify_cards,
)

MODULE = "services.retrieval.workspace.pipeline.execution_flow.evidence_qualification"


class QualificationReuseTests(unittest.TestCase):
    def setUp(self):
        self.cache = QualificationReuseCache()
        self.config = SimpleNamespace(model="fixed-model")
        self.obligations = (SimpleNamespace(id="subject", description="Explain state", evidence_role="implementation"),)
        self.card = DisclosureCard("owner", SourceHandle("src/state.ts", 1, 3), "full",
                                   "function state() {\n  return reverseMap();\n}",
                                   owner_kind="function", owner_name="state")
        self.events = []
        self.trace = SimpleNamespace(record=lambda name, value: self.events.append((name, value)))

    def answer(self, config, messages, **kwargs):
        payload = json.loads(messages[1]["content"])
        return {"decisions": {card["observation_id"]: {
            "classification": "promote_direct", "reason": "Visible reverse lookup",
            "visible_support": ["reverseMap()"], "missing_information": [],
            "local_follow_up": "", "supported_obligation_ids": ["subject"],
        } for card in payload["observations"]}}

    def qualify(self, cards, **overrides):
        args = dict(llm_config=self.config, user_request="Explain state", cards=cards,
                    max_input_chars=40000, obligations=self.obligations, reuse_cache=self.cache,
                    trace=self.trace)
        args.update(overrides)
        return qualify_cards(**args)

    def test_recurrence_and_provenance_reuse_without_a_second_call(self):
        with patch(MODULE + ".complete_json", side_effect=self.answer) as llm:
            first = self.qualify((self.card,), round_index=2)
            second = self.qualify((replace(self.card, provenance_summary={
                "recurrence": 7, "obligation_ids": ["other_query"],
                "exact_anchor_matches": ["state"], "relationship_kinds": ["calls"],
            }),), round_index=3)
        self.assertEqual(llm.call_count, 1)
        self.assertEqual(first.decisions, second.decisions)
        self.assertEqual(second.usage, {})
        self.assertEqual(second.input_chars, 0)
        self.assertEqual(self.events[-1][1]["previous_round"], 2)

    def test_changed_semantic_inputs_require_new_judgment(self):
        variants = [
            dict(cards=(replace(self.card, source_text=self.card.source_text + "\nchanged();"),)),
            dict(cards=(replace(self.card, owner_name="different"),)),
            dict(cards=(replace(self.card, owner_line_end=40),)),
            dict(cards=(replace(self.card, mode="preview", truncation_reason="incomplete"),)),
            dict(cards=(replace(self.card, provenance_summary={"artifact_role": "test"}),)),
            dict(user_request="Explain a different mechanism"),
            dict(obligations=(SimpleNamespace(id="subject", description="Different meaning", evidence_role="implementation"),)),
            dict(llm_config=SimpleNamespace(model="different-model")),
        ]
        for change in variants:
            with self.subTest(change=change):
                self.cache = QualificationReuseCache()
                with patch(MODULE + ".complete_json", side_effect=self.answer) as llm:
                    self.qualify((self.card,))
                    args = dict(cards=(self.card,))
                    args.update(change)
                    self.qualify(**args)
                self.assertEqual(llm.call_count, 2)

    def test_new_batch_aliases_do_not_invalidate_and_cached_card_is_absent_from_request(self):
        other = replace(self.card, observation_id="other", handle=SourceHandle("src/other.ts", 1, 3))
        with patch(MODULE + ".complete_json", side_effect=self.answer) as llm:
            self.qualify((self.card,))
            result = self.qualify((other, self.card))
        sent = json.loads(llm.call_args.args[1][1]["content"])
        self.assertEqual([x["observation_id"] for x in sent["observations"]], ["other"])
        self.assertEqual([x.observation_id for x in result.decisions], ["other", "owner"])
        self.assertEqual(len(result.cards), 2)

    def test_invalid_response_is_never_cached(self):
        with patch(MODULE + ".complete_json", return_value={"decisions": {}}):
            with self.assertRaises(RuntimeError):
                self.qualify((self.card,))
        self.assertFalse(self.cache.entries)

    def test_full_owner_retrieval_focus_is_not_new_semantic_context(self):
        first = replace(self.card, handle=SourceHandle("src/state.ts", 1, 3, full_line_start=1, full_line_end=3))
        focused = replace(first, handle=replace(first.handle, line_start=2, line_end=2))
        with patch(MODULE + ".complete_json", side_effect=self.answer) as llm:
            old = self.qualify((first,))
            new = self.qualify((focused,))
        self.assertEqual(llm.call_count, 1)
        self.assertEqual(old.decisions, new.decisions)

    def test_preview_source_location_change_requires_reassessment(self):
        first = replace(self.card, mode="preview")
        moved = replace(first, handle=replace(first.handle, line_start=10, line_end=12))
        with patch(MODULE + ".complete_json", side_effect=self.answer) as llm:
            self.qualify((first,))
            self.qualify((moved,))
        self.assertEqual(llm.call_count, 2)

    def test_budget_changed_source_is_requalified_without_redistribution(self):
        from services.retrieval.workspace.pipeline.execution_flow.evidence_qualification import prepare_qualification_request
        large = replace(self.card, source_text="\n".join(f"line_{i} = evaluate();" for i in range(70)))
        other = replace(large, observation_id="other", handle=SourceHandle("src/other.ts", 1, 70))
        with patch(MODULE + ".complete_json", side_effect=self.answer) as llm:
            first = self.qualify((large,))
            expected = prepare_qualification_request(user_request="Explain state", cards=(large, other),
                                                     max_input_chars=6000, obligations=self.obligations)
            second = self.qualify((large, other), max_input_chars=6000)
        self.assertNotEqual(first.cards[0].source_text, second.cards[0].source_text)
        self.assertEqual(llm.call_count, 2)
        self.assertEqual(second.cards, expected.cards)

    def test_hidden_continuity_disables_reuse(self):
        with patch(MODULE + ".complete_json", side_effect=self.answer) as llm:
            for _ in range(2):
                self.qualify((self.card,), llm_config=SimpleNamespace(continuity_enabled=True))
        self.assertEqual(llm.call_count, 2)
        self.assertFalse(self.cache.entries)

    def test_weak_judgment_is_not_frozen(self):
        def weak(config, messages, **kwargs):
            result = self.answer(config, messages, **kwargs)
            for decision in result["decisions"].values():
                decision.update(classification="promote_navigation", supported_obligation_ids=[])
            return result
        with patch(MODULE + ".complete_json", side_effect=weak):
            self.qualify((self.card,))
        self.assertFalse(self.cache.entries)
        with patch(MODULE + ".complete_json", side_effect=self.answer) as llm:
            result = self.qualify((self.card,))
        self.assertEqual(llm.call_count, 1)
        self.assertEqual(result.decisions[0].support_level, "direct_evidence")

    def test_budget_crop_retains_actual_qualified_source_not_just_label(self):
        source = "\n".join(f"line_{i} = evaluate();" for i in range(70))
        large = replace(self.card, source_text=source, complete_source_text=source)
        other = replace(large, observation_id="other", handle=SourceHandle("src/other.ts", 1, 70))
        with patch(MODULE + ".complete_json", side_effect=self.answer) as llm:
            first = self.qualify((large,))
            second = self.qualify((large, other), max_input_chars=6000)
        sent = json.loads(llm.call_args.args[1][1]["content"])
        self.assertEqual([x["observation_id"] for x in sent["observations"]], ["other"])
        self.assertEqual(second.cards[0].source_text, first.cards[0].source_text)
        self.assertTrue(any(p["reason"] == "retained_prior_direct_source_over_crop"
                            for name, p in self.events if name == "qualification_reuse_evaluated"))

    def test_new_body_and_changed_backing_do_not_inherit_proof(self):
        full = replace(self.card, mode="preview", preview_source_text=self.card.source_text,
                       complete_source_text=self.card.source_text + "\nother();")
        variants = [replace(full, source_text="other();", preview_source_text="other();"),
                    replace(full, complete_source_text=full.complete_source_text + "\ncontradiction();")]
        for changed in variants:
            with self.subTest(changed=changed):
                self.cache = QualificationReuseCache()
                with patch(MODULE + ".complete_json", side_effect=self.answer) as llm:
                    self.qualify((full,))
                    self.qualify((changed,))
                self.assertEqual(llm.call_count, 2)


if __name__ == "__main__":
    unittest.main()
