import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from services.intent.models import IntentClassificationInput
from testing.codeRepoQA.request_analysis_diagnostics import request_analysis_diagnostics
from tests.test_coderepoqa_retrieval import _intent_result


class RequestAnalysisDiagnosticsTests(unittest.TestCase):
    def test_replay_exact_result_and_reject_wrong_prompt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            source.mkdir()
            result = _intent_result()
            events = [{'event_type': 'run_started', 'payload': {'turn_request': 'same prompt'}},
                      {'event_type': 'intent_classification', 'payload': result.to_dict()}]
            (source / 'orchestration-trace.jsonl').write_text('\n'.join(map(json.dumps, events)))
            with request_analysis_diagnostics(root, source):
                from core.control_layer import classify_intent
                actual = classify_intent(IntentClassificationInput(user_prompt='same prompt'), llm_config=None)
                self.assertEqual(actual.classification.to_dict(), result.classification.to_dict())
                with self.assertRaisesRegex(ValueError, 'prompt differs'):
                    classify_intent(IntentClassificationInput(user_prompt='wrong'), llm_config=None)
            manifest = json.loads((root / 'request-analysis-diagnostic.json').read_text())
            self.assertFalse(manifest['acceptance_run'])

    def test_live_logging_delegates_without_changing_messages(self):
        with tempfile.TemporaryDirectory() as directory:
            messages = [{'role': 'user', 'content': 'payload'}]
            def completion(config, actual, **kwargs):
                self.assertEqual(actual, messages)
                kwargs['log_event']('llm_request_sent', {'request_payload': {'messages': actual}})
                return {'value': 'real result'}
            def classifier(request, *, llm_config, complete_json_fn):
                return complete_json_fn(llm_config, messages)
            with patch('core.control_layer.classify_intent', classifier), patch(
                    'testing.codeRepoQA.request_analysis_diagnostics.complete_json', completion):
                with request_analysis_diagnostics(directory):
                    from core.control_layer import classify_intent
                    self.assertEqual(classify_intent(IntentClassificationInput(user_prompt='x'), llm_config=None),
                                     {'value': 'real result'})
            trace = (Path(directory) / 'request-analysis-api-trace.jsonl').read_text()
            self.assertIn('request_payload', trace)

