import io
import unittest
from contextlib import redirect_stderr
from types import SimpleNamespace
from unittest.mock import patch

from services.llm.json_completion import complete_json, reset_runtime_state, _request_payload


def _config() -> SimpleNamespace:
    return SimpleNamespace(
        api_style="openai",
        api_key="test-key",
        endpoint_url="https://example.test/v1/chat/completions",
        model="gpt-test",
        temperature=0.0,
        max_tokens=100,
        timeout_seconds=10,
        continuity_enabled=False,
    )


def _response(content: str) -> dict[str, object]:
    return {"choices": [{"message": {"content": content}}]}


class JsonCompletionRetryTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_runtime_state()

    def test_optional_completion_budget_preserves_schema_and_explicit_caps(self) -> None:
        schema = {"type": "json_schema", "json_schema": {"name": "unchanged"}}
        for model, parameter in (("gpt-5.6-luna", "max_completion_tokens"), ("gpt-test", "max_tokens")):
            config = _config()
            config.model = model
            config.max_tokens = None
            payload = _request_payload(config, (), response_format=schema)
            self.assertNotIn("max_tokens", payload)
            self.assertNotIn("max_completion_tokens", payload)
            self.assertEqual(payload["response_format"], schema)
            config.max_tokens = 64
            self.assertEqual(_request_payload(config, ())[parameter], 64)

    def test_invalid_json_warns_and_retries_same_request_once(self) -> None:
        events: list[tuple[str, dict[str, object]]] = []
        warnings: list[dict[str, object]] = []
        stderr = io.StringIO()
        with patch(
            "services.llm.json_completion._perform_request",
            side_effect=(_response(""), _response('{"ok": true}')),
        ) as request, redirect_stderr(stderr):
            result = complete_json(
                _config(),
                ({"role": "user", "content": "return JSON"},),
                log_event=lambda event, payload: events.append((event, dict(payload))),
                log_warning=lambda payload: warnings.append(dict(payload)),
            )

        self.assertEqual(result, {"ok": True})
        self.assertEqual(request.call_count, 2)
        self.assertEqual(request.call_args_list[0].args[2], request.call_args_list[1].args[2])
        self.assertIn("WARNING: LLM returned invalid structured JSON", stderr.getvalue())
        self.assertEqual([event for event, _payload in events].count("llm_invalid_structured_output_retry"), 1)
        self.assertEqual(len(warnings), 1)
        self.assertTrue(warnings[0]["will_retry"])

    def test_second_invalid_json_aborts_without_third_request(self) -> None:
        events: list[str] = []
        stderr = io.StringIO()
        with patch(
            "services.llm.json_completion._perform_request",
            side_effect=(_response("not-json"), _response("[]")),
        ) as request, redirect_stderr(stderr):
            with self.assertRaisesRegex(RuntimeError, "JSON object"):
                complete_json(
                    _config(),
                    ({"role": "user", "content": "return JSON"},),
                    log_event=lambda event, _payload: events.append(event),
                )

        self.assertEqual(request.call_count, 2)
        self.assertIn("llm_invalid_structured_output_retry", events)
        self.assertIn("llm_invalid_structured_output_failed", events)
        self.assertIn("ERROR: LLM structured-JSON retry was also invalid", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
