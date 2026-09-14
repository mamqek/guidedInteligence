"""Explicit saved-stage replay and API logging for the benchmark harness only."""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from services.intent.logging import IntentStageResult
from services.intent.models import classification_from_mapping
from services.llm.json_completion import complete_json


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


@contextmanager
def request_analysis_diagnostics(output_dir, replay_run=None):
    from core import control_layer
    live_classifier = control_layer.classify_intent
    output_dir = Path(output_dir)
    saved = None
    if replay_run:
        source = Path(replay_run) / 'orchestration-trace.jsonl'
        events = [json.loads(line) for line in source.read_text(encoding='utf-8').splitlines()]
        starts = [e['payload']['turn_request'] for e in events if e['event_type'] == 'run_started']
        results = [e['payload'] for e in events if e['event_type'] == 'intent_classification']
        if len(starts) != 1 or len(results) != 1 or results[0]['status'] != 'success':
            raise ValueError('Replay requires exactly one successful saved analysis and turn request')
        saved = results[0]
        classification = classification_from_mapping(saved['classification'])
        if classification.to_dict() != saved['classification']:
            raise ValueError('Saved analysis does not round-trip through the current contract')
        manifest = {'mode': 'diagnostic_saved_analysis_replay', 'source_run': str(Path(replay_run).resolve()),
                    'source_trace_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                    'classification_sha256': digest(saved['classification']),
                    'acceptance_run': False}
    else:
        manifest = {'mode': 'live_request_analysis'}
    (output_dir / 'request-analysis-diagnostic.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')

    def log(event, payload):
        with (output_dir / 'request-analysis-api-trace.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({'event_type': event, 'payload': payload}, sort_keys=True) + '\n')

    def classify(request, *, llm_config):
        log('classification_input', request.to_dict())
        if saved is not None:
            prompt = starts[0] if isinstance(starts[0], str) else starts[0].get('user_input', starts[0].get('user_prompt'))
            if prompt is None or request.user_prompt != prompt:
                raise ValueError('Replay prompt differs from saved turn request')
            log('saved_analysis_replayed', manifest)
            return IntentStageResult(status='success', classification=classification, error=None,
                                     fallback_used=False, latency_ms=0, classifier_model=saved['classifier_model'])

        def logged_complete(config, messages, **kwargs):
            return complete_json(config, messages, log_event=log, **kwargs)
        return live_classifier(request, llm_config=llm_config, complete_json_fn=logged_complete)

    with patch('core.control_layer.classify_intent', classify):
        yield
