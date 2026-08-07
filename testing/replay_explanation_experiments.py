from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from core.models import ConversationState, EvidenceItem, RetrievalResult
from core.source_policy import SourceCategory
from services.intent.models import IntentContext, Specificity, TaskIntent
from services.retrieval.server import RuntimeState
from services.response_generation import comprehension as generation


VARIANT_INSTRUCTIONS = {
    "baseline": "",
    "presentation": """

Controlled presentation experiment:
- Before drafting stage prose, inspect the supplied evidence for repeated dimensions, ordered handoffs, and concrete request/response/configuration shapes.
- Treat rich blocks as preferred representations when their trigger is present, not as decorative additions after prose is complete.
- If an ordered-mechanism or ordered-steps stage has three or more evidence-supported handoffs, put those handoffs in one ordered presentation list. Use only a short connective stage sentence to introduce it.
- If at least two entities have at least two shared evidence-supported dimensions, use a comparison table and do not repeat its cells in prose.
- If supplied snippets or claim_supported values establish a useful request, response, command, or configuration shape, include one compact direct or conceptual example.
- Keep prose sentences focused on one relationship and generally below 28 words. Do not create a rich block when its factual pattern is absent.
""",
    "reader": """

Controlled reader-understanding experiment:
- Decompose the user_prompt into its explicit requested parts before drafting. Make every supported part visibly answerable from a named presentation section; state an evidence boundary for an unsupported part.
- Lead each section with the actor, subsystem, client, or state that the reader needs to follow, rather than with a filename or retrieval artifact.
- After an important mechanism, add one concise practical consequence when it follows from supplied evidence or a supplied evidence connection.
- Keep repository entry-point links inline beside the behavior they establish. Do not move them into a separate navigation section.
- Establish each fact once. A later section may explain its consequence but must not restate the mechanism.
""",
    "example": """

Controlled explicit-example experiment:
- The user explicitly requested a JSON configuration snippet, and the supplied evidence contains that exact JSON object.
- Return exactly one `examples` block with `language: "json"`, `provenance: "direct"`, and content copied from the supplied configuration evidence.
- Copy the complete outer `generation` object, including the `"generation"` key; do not return only its inner value.
- Do not place JSON, configuration fields, or the same values inside a stage sentence or presentation list. Use a short connective sentence to introduce the example.
- Keep all other rich presentation arrays empty unless another format is independently necessary to answer the question.
""",
}

LINK_PATTERN = re.compile(r"\s*\[([^\]]+)\]\(([^)]+)\)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay explanation generation against saved retrieval evidence.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--source-run")
    source.add_argument("--case-file", type=Path)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--variants", default="baseline,presentation,reader")
    parser.add_argument("--providers", default="api,codex")
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--api-model", default="gpt-5.6-luna")
    parser.add_argument("--codex-model", default="gpt-5.4-mini")
    parser.add_argument("--citation-compaction", action="store_true")
    args = parser.parse_args()

    root = Path.cwd().resolve()
    source_name, prompt, raw_evidence, selected_intents, retrieval_payload, expectations = _load_source(
        root,
        source_run=args.source_run,
        case_file=args.case_file,
    )
    if not isinstance(raw_evidence, list):
        raise RuntimeError("Saved evidence-items.json must contain an array.")

    output_dir = args.output_dir or (
        root
        / ".guided-intelligence"
        / "explanation-experiments"
        / datetime.now(timezone.utc).strftime("experiment-%Y%m%dT%H%M%SZ")
    )
    output_dir.mkdir(parents=True, exist_ok=False)
    prompt_dir = output_dir / "prompts"
    prompt_dir.mkdir()

    evidence = tuple(_evidence_item(item) for item in raw_evidence)
    state = ConversationState(
        conversation_id=f"explanation-experiment-{source_name}",
        user_input=prompt,
        intent_context=IntentContext(selected_intents, Specificity.BROAD, ()),
    )
    retrieval = RetrievalResult(
        evidence=evidence,
        coverage_status=str(retrieval_payload.get("coverage_status") or "unknown"),
        sufficient=bool(retrieval_payload.get("sufficient")),
        retrieval_summary=_mapping(retrieval_payload.get("retrieval_summary")),
    )
    runtime = RuntimeState(root, tool_root=root)
    base_prompt = generation.PROMPT_PATH.read_text(encoding="utf-8")
    variants = _choices(args.variants, allowed=set(VARIANT_INSTRUCTIONS))
    providers = _choices(args.providers, allowed={"api", "codex"})
    manifest: dict[str, Any] = {
        "source": source_name,
        "user_prompt": prompt,
        "evidence_count": len(evidence),
        "selected_intents": [intent.value for intent in selected_intents],
        "variants": variants,
        "providers": providers,
        "repeats": args.repeats,
        "api_model": args.api_model,
        "codex_model": args.codex_model,
        "expectations": expectations,
        "citation_compaction": args.citation_compaction,
        "runs": [],
    }

    for variant in variants:
        prompt_path = prompt_dir / f"{variant}.md"
        prompt_path.write_text(base_prompt + VARIANT_INSTRUCTIONS[variant], encoding="utf-8")
        generation.PROMPT_PATH = prompt_path
        for provider in providers:
            llm_config = (
                runtime._api_llm_config(
                    model_override=args.api_model,
                    max_tokens_override=8000,
                    timeout_override=180,
                )
                if provider == "api"
                else runtime._codex_llm_config(model=args.codex_model, timeout_seconds=300)
            )
            for repeat in range(1, args.repeats + 1):
                run_name = f"{variant}-{provider}-{repeat}"
                events: list[dict[str, Any]] = []
                warnings: list[dict[str, Any]] = []
                started = time.monotonic()
                try:
                    result = generation.generate_comprehension_explanation(
                        state=state,
                        retrieval_result=retrieval,
                        llm_config=llm_config,
                        log_warning=lambda value: warnings.append(dict(value)),
                        log_event=lambda event, payload: events.append({"event": event, "payload": dict(payload)}),
                    )
                    elapsed = round(time.monotonic() - started, 3)
                    compact_markdown = compact_citations(result.markdown) if args.citation_compaction else ""
                    metrics = _metrics(result, compact_markdown=compact_markdown or None)
                    payload = {
                        "status": "complete",
                        "name": run_name,
                        "variant": variant,
                        "provider": provider,
                        "model": llm_config.model,
                        "elapsed_seconds": elapsed,
                        "markdown": result.markdown,
                        "metrics": metrics,
                        "expectation_results": _evaluate_expectations(result, expectations),
                        "story_flow": list(result.story_flow),
                        "presentation_sections": list(result.presentation_sections),
                        "presentation_lists": list(result.presentation_lists),
                        "examples": list(result.examples),
                        "comparison_tables": list(result.comparison_tables),
                        "additional_implementation_observations": list(result.additional_implementation_observations),
                        "source_attributions": list(result.source_attributions),
                        "understanding_checks": [asdict(check) for check in result.understanding_checks],
                        "used_evidence_refs": list(result.used_evidence_refs),
                        "warnings": warnings,
                        "events": events,
                        "event_names": [item["event"] for item in events],
                    }
                    if compact_markdown:
                        payload["citation_compact_markdown"] = compact_markdown
                except Exception as exc:
                    elapsed = round(time.monotonic() - started, 3)
                    payload = {
                        "status": "failed",
                        "name": run_name,
                        "variant": variant,
                        "provider": provider,
                        "model": llm_config.model,
                        "elapsed_seconds": elapsed,
                        "error": f"{type(exc).__name__}: {exc}",
                        "warnings": warnings,
                        "events": events,
                        "event_names": [item["event"] for item in events],
                    }
                (output_dir / f"{run_name}.json").write_text(
                    json.dumps(payload, indent=2, ensure_ascii=False, default=str),
                    encoding="utf-8",
                )
                manifest["runs"].append(
                    {
                        key: payload.get(key)
                        for key in (
                            "name",
                            "status",
                            "variant",
                            "provider",
                            "model",
                            "elapsed_seconds",
                            "metrics",
                            "expectation_results",
                            "error",
                        )
                        if payload.get(key) is not None
                    }
                )
                print(json.dumps(manifest["runs"][-1], ensure_ascii=False, default=str), flush=True)

    generation.PROMPT_PATH = Path(__file__).resolve().parents[1] / "services" / "response_generation" / "prompts" / "intent_composed_explanation.md"
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(f"EXPERIMENT_DIR={output_dir}")


def compact_citations(markdown: str) -> str:
    """Move repeated source links to the end of each prose paragraph or list item."""
    output: list[str] = []
    inside_code = False
    for block in markdown.split("\n\n"):
        stripped = block.lstrip()
        fence_count = block.count("```")
        eligible = not inside_code and not stripped.startswith(("#", "|"))
        if eligible:
            links: list[str] = []

            def remove_link(match: re.Match[str]) -> str:
                link = f"[{match.group(1)}]({match.group(2)})"
                if link not in links:
                    links.append(link)
                return ""

            without_links = LINK_PATTERN.sub(remove_link, block)
            without_links = re.sub(r"[ \t]+\n", "\n", without_links)
            without_links = re.sub(r" {2,}", " ", without_links).strip()
            block = f"{without_links} {' '.join(links)}".strip() if links else without_links
        output.append(block)
        if fence_count % 2:
            inside_code = not inside_code
    return "\n\n".join(output).strip()


def _metrics(result: Any, *, compact_markdown: str | None) -> dict[str, Any]:
    sentences = [
        str(sentence.get("text") or "")
        for stage in result.story_flow
        for sentence in stage.get("sentences", ())
        if isinstance(sentence, Mapping)
    ]
    original_links = LINK_PATTERN.findall(result.markdown)
    compact_links = LINK_PATTERN.findall(compact_markdown) if compact_markdown is not None else []
    metrics = {
        "sections": len(result.presentation_sections),
        "lists": len(result.presentation_lists),
        "list_items": sum(len(value.get("items", ())) for value in result.presentation_lists),
        "examples": len(result.examples),
        "tables": len(result.comparison_tables),
        "table_rows": sum(len(value.get("rows", ())) for value in result.comparison_tables),
        "observations": len(result.additional_implementation_observations),
        "stage_sentences": len(sentences),
        "average_sentence_characters": round(sum(map(len, sentences)) / max(1, len(sentences)), 1),
        "maximum_sentence_characters": max(map(len, sentences), default=0),
        "understanding_checks": len(result.understanding_checks),
        "source_attributions": len(result.source_attributions),
        "evidence_links": len(original_links),
        "unique_evidence_links": len(set(original_links)),
        "flow_repairs": result.flow_repair_attempts,
        "question_repairs": result.question_repair_attempts,
        "hint_repairs": result.hint_repair_attempts,
    }
    if compact_markdown is not None:
        metrics["compact_evidence_links"] = len(compact_links)
    return metrics


def _load_source(
    root: Path,
    *,
    source_run: str | None,
    case_file: Path | None,
) -> tuple[str, str, list[Any], tuple[TaskIntent, ...], dict[str, Any], dict[str, Any]]:
    if case_file is not None:
        resolved = case_file if case_file.is_absolute() else root / case_file
        case = _mapping(_load_json(resolved))
        prompt = str(case.get("user_prompt") or "").strip()
        if not prompt:
            raise RuntimeError("Explanation case requires `user_prompt`.")
        intents = tuple(TaskIntent(str(value)) for value in case.get("selected_intents", ()))
        if not intents:
            raise RuntimeError("Explanation case requires at least one `selected_intents` value.")
        evidence = case.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            raise RuntimeError("Explanation case requires a non-empty `evidence` array.")
        retrieval = {
            "coverage_status": str(case.get("coverage_status") or "complete"),
            "sufficient": bool(case.get("sufficient", True)),
            "retrieval_summary": _mapping(case.get("retrieval_summary")),
        }
        return resolved.stem, prompt, evidence, intents, retrieval, _mapping(case.get("expectations"))

    if not source_run:
        raise RuntimeError("A source run or case file is required.")
    source_dir = root / ".guided-intelligence" / "runs" / source_run
    metadata = _mapping(_load_json(source_dir / "run-metadata.json"))
    orchestration = _mapping(_load_json(source_dir / "orchestration-result.json"))
    evidence = _load_json(source_dir / "evidence-items.json")
    response_metadata = _mapping(_mapping(orchestration.get("response_payload")).get("metadata"))
    intents = tuple(TaskIntent(str(value)) for value in response_metadata.get("selected_intents", ())) or (
        TaskIntent.EXPLORE,
        TaskIntent.EXPLAIN,
    )
    return (
        source_run,
        str(metadata.get("prompt") or "").strip(),
        evidence,
        intents,
        _mapping(orchestration.get("retrieval_result")),
        {},
    )


def _evaluate_expectations(result: Any, expectations: Mapping[str, Any]) -> dict[str, Any]:
    checks: dict[str, bool] = {}
    if "min_tables" in expectations:
        checks["min_tables"] = len(result.comparison_tables) >= int(expectations["min_tables"])
    if "min_examples" in expectations:
        checks["min_examples"] = len(result.examples) >= int(expectations["min_examples"])
    expected_languages = {str(value).lower() for value in expectations.get("example_languages", ())}
    if expected_languages:
        actual_languages = {str(value.get("language") or "").lower() for value in result.examples}
        checks["example_languages"] = expected_languages.issubset(actual_languages)
    required_example_content = tuple(str(value) for value in expectations.get("example_content_contains", ()))
    if required_example_content:
        checks["example_content_contains"] = any(
            all(required in str(example.get("content") or "") for required in required_example_content)
            for example in result.examples
        )
    return {"passed": all(checks.values()), "checks": checks}


def _evidence_item(value: Mapping[str, Any]) -> EvidenceItem:
    return EvidenceItem(
        source_category=SourceCategory(str(value["source_category"])),
        source_id=str(value["source_id"]),
        snippet=str(value.get("snippet") or ""),
        rank=int(value["rank"]) if value.get("rank") is not None else None,
        metadata=_mapping(value.get("metadata")),
    )


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _choices(value: str, *, allowed: set[str]) -> list[str]:
    output = [item.strip() for item in value.split(",") if item.strip()]
    unknown = set(output) - allowed
    if unknown:
        raise ValueError(f"Unknown choices: {', '.join(sorted(unknown))}")
    return output


if __name__ == "__main__":
    main()
