"""Real API replay of a saved final request with only its completion cap removed."""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from testing.codeRepoQA.run_case import _load_project_llm_config
from services.llm.json_completion import complete_json, _request_payload


def validate(value, schema):
    """Check the saved schema's object/array/enum/string constraints for this diagnostic."""
    kind = schema.get("type")
    assert isinstance(value, {"object": dict, "array": list, "string": str,
                              "boolean": bool, "integer": int, "number": (int, float)}[kind]), kind
    if "enum" in schema:
        assert value in schema["enum"], value
    if kind == "object":
        assert set(schema.get("required", ())) <= set(value)
        if schema.get("additionalProperties") is False:
            assert set(value) <= set(schema["properties"])
        for key, item in value.items():
            validate(item, schema["properties"][key])
    if kind == "array":
        assert schema.get("minItems", 0) <= len(value) <= schema.get("maxItems", float("inf"))
        for item in value:
            validate(item, schema["items"])
    if kind == "string":
        assert len(value) >= schema.get("minLength", 0)


def run(directory, output):
    rows = [json.loads(line) for line in (directory / "retrieval-trace.jsonl").read_text(encoding="utf8").splitlines()]
    original = next(row["payload"]["request_payload"] for row in rows
                    if row["event_type"] == "llm_request_sent" and
                    row["payload"].get("stage") == "obligation_evidence_consolidation")
    config = replace(_load_project_llm_config({}), max_tokens=None, model=original["model"],
                     temperature=original.get("temperature", 0.0))
    updated = _request_payload(config, original["messages"], response_format=original["response_format"])
    expected = {k: v for k, v in original.items() if k not in ("max_tokens", "max_completion_tokens")}
    if "temperature" not in original:
        # Preserve a previously temperature-disabled model's exact request.
        from services.llm.json_completion import _TEMPERATURE_DISABLED_MODELS, _temperature_cache_key
        _TEMPERATURE_DISABLED_MODELS.add(_temperature_cache_key(config))
        updated.pop("temperature", None)
    assert updated == expected, "Replay would change more than the cap"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf8") as log:
        def event(name, payload):
            log.write(json.dumps({"event_type": name, "payload": payload}) + "\n")
            log.flush()
        event("replay_started", {"source_run": directory.name, "config": config.public_dict(),
                                  "changed_parameters": ["max_completion_tokens"]})
        try:
            result = complete_json(config, original["messages"], response_format=original["response_format"], log_event=event)
            validate(result, original["response_format"]["json_schema"]["schema"])
            payload = json.loads(next(x["content"] for x in original["messages"] if x["role"] == "user"))
            known = {x["candidate_id"] for x in payload["candidates"]}
            assert all(x["candidate_id"] in known for x in result["selected_evidence"])
            event("replay_validated", {"selected_count": len(result["selected_evidence"]), "result": result})
            print(f"Validated {len(result['selected_evidence'])} selections: {output}", flush=True)
        except Exception as exc:
            event("replay_failed", {"error": str(exc)})
            raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.run, args.output)
