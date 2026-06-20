from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from core.models import ConversationState, EvidenceItem, RetrievalResult
from services.guidance.questions import UnderstandingCheck, build_question_contexts
from services.llm.json_completion import complete_json


LINE_RANGE_PATTERN = re.compile(r":L(?P<start>\d+)(?:-L(?P<end>\d+))?$")
RETRIEVAL_LABEL_QUESTION_PATTERN = re.compile(
    r"\b(?:evidence|retrieved|coverage|role)\b|representation/types|emitter/output",
    re.IGNORECASE,
)
PROMPT_TEMPLATE_ID = "explanation_markdown_v2"
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
EXPLANATION_PROMPT_PATH = PROMPTS_DIR / "explanation.md"
EXPLANATION_SOURCES_PATH = PROMPTS_DIR / "explanation_sources.md"


@dataclass(frozen=True)
class ExplanationGenerationResult:
    markdown: str
    used_evidence_refs: tuple[str, ...]
    render_notes: Mapping[str, str]
    understanding_checks: tuple[UnderstandingCheck, ...]
    prompt_template_id: str = PROMPT_TEMPLATE_ID


def generate_explanation(
    *,
    state: ConversationState,
    retrieval_result: RetrievalResult,
    llm_config: Any,
    log_warning: Callable[[Mapping[str, Any]], None] | None = None,
    log_event: Callable[[str, Mapping[str, Any]], None] | None = None,
) -> ExplanationGenerationResult:
    required_evidence = _required_evidence_items(state.user_input, retrieval_result.evidence[:8])
    question_contexts = build_question_contexts(retrieval_result)
    prompt_terms = _classify_prompt_terms(state.user_input)
    candidate_prompt_terms = tuple(prompt_terms["requested_target_terms"])
    absent_prompt_terms = _prompt_terms_absent_from_evidence(candidate_prompt_terms, retrieval_result.evidence[:8])
    implementation_context = _build_implementation_context(retrieval_result.evidence[:8], retrieval_result.retrieval_summary)
    payload = {
        "user_prompt": state.user_input,
        "coverage_status": _model_facing_coverage_status(retrieval_result.coverage_status),
        "retrieval_coverage_status": retrieval_result.coverage_status,
        "coverage_meaning": _coverage_meaning(),
        "retrieval_sufficient": retrieval_result.sufficient,
        "prompt_terms": prompt_terms,
        "implementation_context": implementation_context,
        "evidence": [_compact_evidence(item) for item in retrieval_result.evidence[:8]],
        "required_evidence": [_compact_evidence(item) for item in required_evidence],
        "prompt_terms_absent_from_evidence": absent_prompt_terms,
        "question_contexts": [context.to_dict() for context in question_contexts],
        "question_rules": {
            "default_count": 1,
            "max_count": 3,
            "primary_question_id": question_contexts[0].id if question_contexts else "",
            "secondary_questions_must_explain_origin": True,
            "hints_are_hidden_in_ui": True,
        },
        "retrieval_summary": _compact_retrieval_summary(retrieval_result.retrieval_summary),
        "citation_rules": {
            "allowed_links": [_evidence_link(item) for item in retrieval_result.evidence[:8]],
            "allowed_refs": [item.source_id for item in retrieval_result.evidence[:8]],
            "required_refs": [item.source_id for item in required_evidence],
        },
    }
    if log_event is not None:
        log_event(
            "response_generation_request_payload",
            {
                "prompt_template_id": PROMPT_TEMPLATE_ID,
                "payload": payload,
            },
        )
    response = complete_json(
        llm_config,
        (
            {"role": "system", "content": _load_prompt(EXPLANATION_PROMPT_PATH)},
            {"role": "user", "content": json.dumps(payload, sort_keys=True)},
        ),
        response_format=_response_format(),
        log_warning=log_warning,
        log_event=log_event,
    )
    result = _validate_generation_response(
        response,
        retrieval_result.evidence,
        required_evidence=required_evidence,
        question_contexts=tuple(context.to_dict() for context in question_contexts),
        absent_prompt_terms=absent_prompt_terms,
        candidate_prompt_terms=candidate_prompt_terms,
    )
    if log_event is not None:
        log_event(
            "response_generation_response_payload",
            {
                "prompt_template_id": PROMPT_TEMPLATE_ID,
                "used_evidence_refs": list(result.used_evidence_refs),
                "render_notes": dict(result.render_notes),
            },
        )
    return result


def prompt_template_id() -> str:
    return PROMPT_TEMPLATE_ID


def prompt_sources_path() -> Path:
    return EXPLANATION_SOURCES_PATH


def _validate_generation_response(
    response: Mapping[str, Any],
    evidence: Sequence[EvidenceItem],
    *,
    required_evidence: Sequence[EvidenceItem] = (),
    question_contexts: Sequence[Mapping[str, Any]] = (),
    absent_prompt_terms: Sequence[str] = (),
    candidate_prompt_terms: Sequence[str] = (),
) -> ExplanationGenerationResult:
    markdown = str(response.get("markdown", "")).strip()
    if not markdown:
        raise RuntimeError("Explanation generation returned empty markdown.")
    markdown = _repair_absent_feature_title(markdown, absent_prompt_terms, candidate_prompt_terms)
    markdown = _strip_leaked_understanding_check_sections(markdown)
    markdown = _dedupe_repeated_absence_caveats(markdown, candidate_prompt_terms)

    allowed_refs = {item.source_id for item in evidence}
    used_refs: list[str] = []
    for ref in response.get("used_evidence_refs", ()):
        ref_text = str(ref).strip()
        if ref_text and ref_text in allowed_refs and ref_text not in used_refs:
            used_refs.append(ref_text)

    render_notes_raw = response.get("render_notes", {})
    render_notes: dict[str, str] = {}
    if isinstance(render_notes_raw, Mapping):
        for key in ("title", "summary"):
            value = str(render_notes_raw.get(key, "")).strip()
            if value:
                render_notes[key] = value[:500]

    markdown, used_refs = _repair_missing_required_evidence(
        markdown,
        used_refs,
        evidence=evidence,
        required_evidence=required_evidence,
    )
    checks = _validate_understanding_checks(
        response.get("understanding_checks", ()),
        evidence=evidence,
        question_contexts=question_contexts,
    )
    return ExplanationGenerationResult(
        markdown=markdown,
        used_evidence_refs=tuple(used_refs),
        render_notes=render_notes,
        understanding_checks=checks,
    )


def _strip_leaked_understanding_check_sections(markdown: str) -> str:
    lines = markdown.splitlines()
    for index, line in enumerate(lines):
        normalized = line.strip().strip("#").strip().lower()
        if normalized in {
            "understanding check",
            "understanding checks",
            "understanding check question",
            "understanding-check question",
        }:
            return "\n".join(lines[:index]).strip()
        if normalized.startswith("expected answer point"):
            return "\n".join(lines[:index]).strip()
    return markdown


def _dedupe_repeated_absence_caveats(markdown: str, candidate_prompt_terms: Sequence[str]) -> str:
    terms = tuple(term.lower() for term in candidate_prompt_terms if term.strip())
    if not terms:
        return markdown
    absence_markers = (
        "does not show",
        "do not show",
        "does not explicitly",
        "do not explicitly",
        "not explicitly",
        "not shown",
        "not confirm",
        "not confirmed",
        "no explicit",
    )
    output: list[str] = []
    seen_terms: set[str] = set()
    in_final_absence_section = False
    for line in markdown.splitlines():
        normalized_heading = line.strip().strip("#").strip().lower()
        if normalized_heading.startswith("what is not shown") or normalized_heading.startswith("not shown"):
            in_final_absence_section = True
            output.append(line)
            continue
        if line.lstrip().startswith("#"):
            in_final_absence_section = False
        if in_final_absence_section or not line.strip():
            output.append(line)
            continue
        kept_sentences: list[str] = []
        for sentence in _split_sentences_preserving_punctuation(line):
            lowered = sentence.lower()
            matching_terms = tuple(term for term in terms if term in lowered)
            is_repeated_absence = bool(matching_terms) and any(marker in lowered for marker in absence_markers)
            if is_repeated_absence and any(term in seen_terms for term in matching_terms):
                continue
            kept_sentences.append(sentence)
            if is_repeated_absence:
                seen_terms.update(matching_terms)
        if kept_sentences:
            output.append(" ".join(part.strip() for part in kept_sentences if part.strip()))
    return "\n".join(output).strip()


def _split_sentences_preserving_punctuation(line: str) -> list[str]:
    if not line.strip() or line.lstrip().startswith(("-", "*", "|")):
        return [line]
    return [part for part in re.split(r"(?<=[.!?])\s+", line) if part]


def _build_implementation_context(
    evidence: Sequence[EvidenceItem],
    retrieval_summary: Mapping[str, Any],
) -> list[dict[str, Any]]:
    evidence_by_ref = {item.source_id: item for item in evidence}
    contexts: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str]] = set()
    for refs in _ordered_context_refs(evidence, retrieval_summary):
        items = [evidence_by_ref[ref] for ref in refs if ref in evidence_by_ref]
        if not items:
            continue
        primary = items[0]
        path = str(primary.metadata.get("path") or _path_from_source_id(primary.source_id))
        role = str(primary.metadata.get("coverage_area") or primary.source_category.value)
        key = (role, path)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        context = _implementation_context_for_group(role=role, path=path, items=items)
        if context is not None:
            contexts.append(context)
        if len(contexts) >= 6:
            break
    return contexts


def _ordered_context_refs(
    evidence: Sequence[EvidenceItem],
    retrieval_summary: Mapping[str, Any],
) -> list[tuple[str, ...]]:
    groups: list[tuple[str, ...]] = []
    buckets = retrieval_summary.get("required_role_buckets")
    if isinstance(buckets, Sequence) and not isinstance(buckets, (str, bytes)):
        for bucket in buckets:
            if not isinstance(bucket, Mapping):
                continue
            refs = _string_tuple(bucket.get("accepted_refs")) or _string_tuple(bucket.get("satisfying_refs"))
            if refs:
                groups.append(refs)
    used_refs = {ref for group in groups for ref in group}
    for item in evidence:
        if item.source_id not in used_refs:
            groups.append((item.source_id,))
    return groups


def _implementation_context_for_group(
    *,
    role: str,
    path: str,
    items: Sequence[EvidenceItem],
) -> dict[str, Any] | None:
    positive_claims = _positive_claims_for_items(items)
    next_targets = _next_inspection_targets_for_role(role, items)
    if not positive_claims and not next_targets:
        return None
    return {
        "responsibility": _responsibility_for_role(role, path),
        "stage": _stage_for_role(role, path),
        "path": path,
        "evidence_refs": [item.source_id for item in items],
        "what_this_file_does": _what_file_does(role, path),
        "why_it_matters_for_issue": _why_it_matters(role),
        "positive_claims": positive_claims,
        "next_inspection_targets": next_targets,
        "avoid_repeating": [
            "Do not repeat absent requested-feature caveats in this section; reserve them for the bottom line or final uncertainty section."
        ],
    }


def _stage_for_role(role: str, path: str) -> str:
    normalized = f"{role} {path}".lower()
    if "parser" in normalized or "input_parsing" in normalized:
        return "parser"
    if "checker" in normalized or "validation" in normalized:
        return "checker"
    if "diagnostic" in normalized:
        return "diagnostics"
    if "emitter" in normalized or "behavior_output" in normalized:
        return "emitter"
    if "types" in normalized or "representation" in normalized:
        return "representation"
    return role.replace("_", " ")


def _responsibility_for_role(role: str, path: str) -> str:
    labels = {
        "parser": "Parse class declarations and members",
        "checker": "Validate class declarations and related semantic rules",
        "diagnostics": "Define diagnostic messages for errors",
        "emitter": "Emit runtime JavaScript for parsed nodes",
        "representation": "Represent declarations, symbols, and type-system state",
    }
    return labels.get(_stage_for_role(role, path), role.replace("_", " ").capitalize())


def _what_file_does(role: str, path: str) -> str:
    descriptions = {
        "parser": "Turns source tokens into AST nodes and member/declaration lists that later compiler stages consume.",
        "checker": "Walks parsed declarations and expressions to validate semantic rules and report errors.",
        "diagnostics": "Stores diagnostic message definitions that parser/checker code can report to users.",
        "emitter": "Turns checked AST nodes into emitted JavaScript output, skipping or transforming nodes based on node kind and flags.",
        "representation": "Defines compiler data shapes such as AST nodes, symbols, type flags, and declaration metadata.",
    }
    return descriptions.get(_stage_for_role(role, path), "Provides retrieved implementation context for this responsibility.")


def _why_it_matters(role: str) -> str:
    reasons = {
        "parser": "A new source-language keyword or declaration shape must be accepted and attached to parsed nodes before later stages can reason about it.",
        "checker": "Semantic restrictions are enforced after parsing, so this is where invalid uses of a feature are likely reported.",
        "diagnostics": "New validation rules usually need user-facing diagnostic text.",
        "emitter": "If a feature changes emitted JavaScript or runtime behavior, the emitter is where that output path is inspected.",
        "representation": "Later stages need a stable representation for any new declaration state they must inspect.",
    }
    return reasons.get(_stage_for_role(role, ""), "It is one of the retrieved responsibilities connected to the user's issue.")


def _positive_claims_for_items(items: Sequence[EvidenceItem]) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    for item in items:
        snippet = item.snippet
        ref = item.source_id
        if "function parseClassDeclaration" in snippet:
            claims.extend(
                [
                    _claim("parseClassDeclaration creates a ClassDeclaration AST node.", ref),
                    _claim("It assigns node.flags from the flags passed into the parser path.", ref),
                    _claim("It parses class name, type parameters, extends, implements, and class members.", ref),
                ]
            )
        if "function parseClassMemberDeclaration" in snippet:
            claims.extend(
                [
                    _claim("parseClassMemberDeclaration parses class members.", ref),
                    _claim("It calls parseAndCheckModifiers(ModifierContext.ClassMembers) before deciding which member form to parse.", ref),
                    _claim("It routes accessors, constructors, property members, and index signatures into their specific parser paths.", ref),
                ]
            )
        if "function parseContextualModifier" in snippet:
            claims.append(_claim("parseContextualModifier and parseAnyContextualModifier are parser helpers for contextual modifier-like tokens.", ref))
        if "export enum SymbolFlags" in snippet:
            claims.append(_claim("SymbolFlags defines compiler symbol categories, including Class.", ref))
        if "export interface Symbol" in snippet:
            claims.append(_claim("Symbol records flags, name, declarations, parent, members, and exports for compiler symbols.", ref))
        if "export interface Node" in snippet:
            claims.append(_claim("Node carries kind, flags, parent, and optional symbol information for AST nodes.", ref))
        if "function checkClassDeclaration" in snippet:
            claims.extend(
                [
                    _claim("checkClassDeclaration validates class declarations.", ref),
                    _claim("It calls checkDeclarationModifiers before checking names, type parameters, symbols, and base types.", ref),
                ]
            )
        if "Diagnostics." in snippet or '"category"' in snippet:
            claims.append(_claim("The diagnostic evidence shows user-facing error message definitions or reporting paths.", ref))
        if "function emitNode" in snippet:
            claims.append(_claim("emitNode dispatches AST node kinds to specific emitter functions and skips ambient nodes.", ref))
        if "function checkPropertyAccess" in snippet:
            claims.append(_claim("checkPropertyAccess validates property access by resolving the property on the apparent type.", ref))
    return _dedupe_claims(claims)[:6]


def _claim(text: str, ref: str, *, strength: str = "direct") -> dict[str, Any]:
    return {"claim": text, "claim_strength": strength, "evidence_refs": [ref]}


def _next_inspection_targets_for_role(role: str, items: Sequence[EvidenceItem]) -> list[dict[str, Any]]:
    refs = [item.source_id for item in items]
    targets_by_stage = {
        "parser": (
            "where flags are produced before parseClassDeclaration",
            "modifier parsing before class declarations and class members",
            "SyntaxKind keyword handling for source-language modifiers",
        ),
        "checker": (
            "checkDeclarationModifiers and nearby class validation paths",
            "class instantiation validation",
            "subclass/member compatibility checks",
        ),
        "diagnostics": (
            "diagnostic messages for invalid feature usage",
            "diagnostic reporting sites that would reference those messages",
        ),
        "emitter": (
            "whether the feature changes emitted output",
            "node kind and flag checks that suppress or transform output",
        ),
        "representation": (
            "NodeFlags and SymbolFlags definitions",
            "AST declaration interfaces that carry modifier state",
            "symbol/type links consumed by checker code",
        ),
    }
    return [
        {"target": target, "claim_strength": "inspection_target", "evidence_refs": refs[:3]}
        for target in targets_by_stage.get(_stage_for_role(role, ""), ())
    ]


def _dedupe_claims(claims: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for claim in claims:
        text = str(claim.get("claim") or "")
        if not text or text in seen:
            continue
        seen.add(text)
        output.append(claim)
    return output


def _repair_absent_feature_title(
    markdown: str,
    absent_prompt_terms: Sequence[str],
    candidate_prompt_terms: Sequence[str] = (),
) -> str:
    if not absent_prompt_terms and not candidate_prompt_terms:
        return markdown
    lines = markdown.splitlines()
    for index, line in enumerate(lines[:8]):
        match = re.match(r"^(#{1,2})\s+(.+?)\s*$", line)
        if not match:
            continue
        title = match.group(2)
        title_lower = title.lower()
        matching_terms = [term for term in absent_prompt_terms if term.lower() in title_lower]
        if not matching_terms:
            matching_terms = [
                term
                for term in candidate_prompt_terms
                if term.lower() in title_lower and _markdown_marks_term_unconfirmed(markdown, term)
            ]
        if not matching_terms:
            return markdown
        safe_framing = (
            "add",
            "adding",
            "change",
            "connect",
            "implement",
            "implementation",
            "inspect",
            "investigation",
            "path",
            "support",
            "target",
        )
        if any(word in title_lower for word in safe_framing):
            return markdown
        target = " / ".join(matching_terms[:3])
        lines[index] = f"{match.group(1)} Where to inspect or add {target} support in the selected snippets"
        return "\n".join(lines).strip()
    return markdown


def _markdown_marks_term_unconfirmed(markdown: str, term: str) -> bool:
    lowered = markdown.lower()
    escaped = re.escape(term.lower())
    patterns = (
        rf"(?:does not|do not|not|no explicit|not confirmed)[^.\n]{{0,140}}{escaped}",
        rf"{escaped}[^.\n]{{0,140}}(?:not shown|not confirmed|not explicitly|no explicit)",
    )
    return any(re.search(pattern, lowered) for pattern in patterns)


def _validate_understanding_checks(
    value: Any,
    *,
    evidence: Sequence[EvidenceItem],
    question_contexts: Sequence[Mapping[str, Any]],
) -> tuple[UnderstandingCheck, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise RuntimeError("Explanation generation must return understanding_checks.")
    allowed_refs = {item.source_id for item in evidence}
    context_by_id = {str(context.get("id")): context for context in question_contexts}
    checks: list[UnderstandingCheck] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        check_id = str(item.get("id") or "").strip()
        context = context_by_id.get(check_id)
        if context is None:
            continue
        refs = tuple(ref for ref in _string_tuple(item.get("evidence_refs")) if ref in allowed_refs)
        if not refs:
            refs = tuple(ref for ref in _string_tuple(context.get("evidence_refs")) if ref in allowed_refs)
        points = _string_tuple(item.get("expected_answer_points"))[:4]
        question = str(item.get("question") or "").strip()
        hint = str(item.get("hint") or "").strip()
        if not question or not points or not hint:
            continue
        if _uses_retrieval_label_wording(question):
            continue
        if _uses_retrieval_label_wording(hint):
            continue
        checks.append(
            UnderstandingCheck(
                id=check_id,
                role=str(item.get("role") or context.get("role") or "").strip(),
                question_type=str(item.get("question_type") or context.get("question_type") or "").strip(),
                question=question[:600],
                expected_answer_points=points,
                hint=hint[:500],
                evidence_refs=refs[:4],
                origin=str(item.get("origin") or context.get("origin") or "").strip(),
            )
        )
    if not checks:
        raise RuntimeError("Explanation generation returned no valid understanding checks.")
    return tuple(checks[:3])


def _uses_retrieval_label_wording(text: str) -> bool:
    return bool(RETRIEVAL_LABEL_QUESTION_PATTERN.search(text))


def _string_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())


def _compact_evidence(item: EvidenceItem) -> dict[str, Any]:
    metadata = dict(item.metadata)
    return {
        "ref": item.source_id,
        "citation_markdown": _evidence_link(item),
        "path": metadata.get("path") or _path_from_source_id(item.source_id) or item.source_id,
        "line_range": metadata.get("line_range") or _line_range_from_source_id(item.source_id),
        "coverage_area": metadata.get("coverage_area", ""),
        "retrieval_path": metadata.get("retrieval_path", ""),
        "snippet_quality": metadata.get("snippet_quality", ""),
        "snippet": _compact_snippet(item.snippet),
    }


def _required_evidence_items(user_prompt: str, evidence: Sequence[EvidenceItem]) -> tuple[EvidenceItem, ...]:
    prompt_terms = _high_signal_prompt_terms(user_prompt)
    required: list[EvidenceItem] = []
    for item in evidence:
        snippet = item.snippet or ""
        metadata = dict(item.metadata)
        coverage_area = str(metadata.get("coverage_area", "")).strip().lower()
        if _contains_prompt_anchor(snippet, prompt_terms):
            required.append(item)
            continue
        if coverage_area == "diagnostics" and _contains_diagnostic_emission(snippet):
            required.append(item)
            continue
        if _contains_diagnostic_emission(snippet) and _contains_prompt_anchor(snippet, prompt_terms, minimum_length=8):
            required.append(item)
            continue
    return tuple(required[:3])


def _model_facing_coverage_status(retrieval_coverage_status: str) -> str:
    normalized = retrieval_coverage_status.strip().lower()
    if normalized in {"strong", "sufficient_context", "state_evidence"}:
        return "strong_context_coverage"
    if normalized in {"partial", "weak", "preparing_index"}:
        return "partial_context_coverage"
    if normalized in {"missing", "failed"}:
        return "missing_context_coverage"
    return f"{normalized}_context_coverage" if normalized else "unknown_context_coverage"


def _coverage_meaning() -> str:
    return (
        "Retrieved snippets cover relevant code responsibilities for explaining the prompt, "
        "not necessarily direct implementation of the requested behavior."
    )


def _classify_prompt_terms(user_prompt: str) -> dict[str, list[str]]:
    code_blocks = _fenced_code_blocks(user_prompt)
    prompt_without_code = _remove_fenced_code_blocks(user_prompt)
    example_terms = _example_terms_from_code_blocks(code_blocks)
    requested_terms = _requested_target_terms(prompt_without_code)
    ignored_terms = _ignored_prose_terms(prompt_without_code, requested_terms=requested_terms, example_terms=example_terms)
    return {
        "requested_target_terms": list(requested_terms),
        "example_terms": list(example_terms),
        "prose_terms_ignored_for_grounding": list(ignored_terms),
    }


def _fenced_code_blocks(text: str) -> tuple[str, ...]:
    blocks: list[str] = []
    for match in re.finditer(r"```[^\n\r]*[\r\n]+(.*?)(?:```|$)", text, flags=re.DOTALL):
        block = match.group(1).strip()
        if block:
            blocks.append(block)
    return tuple(blocks)


def _remove_fenced_code_blocks(text: str) -> str:
    return re.sub(r"```[^\n\r]*[\r\n]+.*?(?:```|$)", " ", text, flags=re.DOTALL)


def _example_terms_from_code_blocks(code_blocks: Sequence[str]) -> tuple[str, ...]:
    ignored = {
        "abstract",
        "also",
        "class",
        "extends",
        "return",
        "var",
        "new",
        "string",
        "super",
        "ok",
        "error",
    }
    terms: list[str] = []
    for block in code_blocks:
        for token in re.findall(r"\b[A-Za-z_$][A-Za-z0-9_$]*\b", block):
            if token.lower() in ignored:
                continue
            if token and (token[0].isupper() or any(char.isupper() for char in token[1:]) or any(char.isdigit() for char in token)):
                _append_unique(terms, token)
    return tuple(terms[:20])


def _requested_target_terms(prompt_without_code: str) -> tuple[str, ...]:
    terms: list[str] = []
    title_match = re.search(r"^\s*Title:\s*(.+)$", prompt_without_code, flags=re.IGNORECASE | re.MULTILINE)
    if title_match:
        title = title_match.group(1)
        for phrase in _target_phrases_from_text(title):
            _append_unique(terms, phrase)
    for match in re.finditer(r"`([^`]+)`", prompt_without_code):
        token = match.group(1).strip()
        if not token:
            continue
        lowered = token.lower()
        _append_unique(terms, lowered)
        window = prompt_without_code[match.end() : match.end() + 80].lower()
        if "keyword" in window:
            _append_unique(terms, f"{lowered} keyword")
        if "class" in window:
            _append_unique(terms, f"{lowered} classes")
        if "method" in window:
            _append_unique(terms, f"{lowered} methods")
    for phrase in _target_phrases_from_text(prompt_without_code):
        _append_unique(terms, phrase)
    return tuple(terms[:12])


def _target_phrases_from_text(text: str) -> tuple[str, ...]:
    normalized = text.lower()
    phrases: list[str] = []
    for adjective in ("abstract",):
        if re.search(rf"\b{adjective}\b", normalized):
            _append_unique(phrases, adjective)
        for noun in ("class", "classes", "method", "methods", "member", "members", "keyword"):
            if re.search(rf"\b{adjective}\s+{noun}\b", normalized):
                _append_unique(phrases, f"{adjective} {noun}")
    return tuple(phrases)


def _ignored_prose_terms(
    prompt_without_code: str,
    *,
    requested_terms: Sequence[str],
    example_terms: Sequence[str],
) -> tuple[str, ...]:
    ignored_words = {
        "actual",
        "also",
        "code",
        "concrete",
        "context",
        "either",
        "example",
        "examples",
        "explain",
        "implement",
        "issue",
        "needed",
        "suggestion",
        "support",
        "their",
        "title",
        "where",
    }
    requested_parts = {part for term in requested_terms for part in re.findall(r"[a-z0-9]+", term.lower())}
    example_lower = {term.lower() for term in example_terms}
    output: list[str] = []
    for token in re.findall(r"\b[A-Za-z_][A-Za-z0-9_]{4,}\b", prompt_without_code):
        lowered = token.lower()
        if lowered in requested_parts or lowered in example_lower:
            continue
        if lowered in ignored_words:
            _append_unique(output, lowered)
    return tuple(output[:20])


def _append_unique(items: list[str], value: str) -> None:
    normalized = value.strip()
    if normalized and normalized not in items:
        items.append(normalized)


def _prompt_terms_absent_from_evidence(terms: Sequence[str], evidence: Sequence[EvidenceItem]) -> tuple[str, ...]:
    if not terms:
        return ()
    combined = "\n".join(item.snippet for item in evidence).lower()
    absent: list[str] = []
    for term in terms:
        if term.lower() not in combined:
            absent.append(term)
    return tuple(absent[:12])


def _candidate_prompt_terms(user_prompt: str) -> tuple[str, ...]:
    stop_words = {
        "about",
        "actual",
        "added",
        "class",
        "classes",
        "code",
        "context",
        "could",
        "explain",
        "happen",
        "happens",
        "where",
        "with",
    }
    output: list[str] = []
    for token in re.findall(r"\b[A-Za-z_][A-Za-z0-9_]{5,}\b", user_prompt):
        lowered = token.lower()
        if lowered in stop_words:
            continue
        if token not in output:
            output.append(token)
    return tuple(output)


def _high_signal_prompt_terms(user_prompt: str) -> tuple[str, ...]:
    terms: list[str] = []
    for match in re.findall(r"`([^`]+)`|'([^']+)'|\"([^\"]+)\"", user_prompt):
        value = next((item for item in match if item), "")
        normalized = _normalize_phrase(value)
        if len(normalized) >= 6:
            terms.append(normalized)
    for match in re.findall(r"\b(?:error|warning|diagnostic|expects?|cannot|must|invalid|unsafe)\b[^.\n\r]{0,90}", user_prompt, flags=re.IGNORECASE):
        normalized = _normalize_phrase(match)
        if len(normalized) >= 8:
            terms.append(normalized)
    return tuple(dict.fromkeys(terms[:12]))


def _contains_prompt_anchor(snippet: str, prompt_terms: Sequence[str], *, minimum_length: int = 6) -> bool:
    normalized_snippet = _normalize_phrase(snippet)
    if not normalized_snippet:
        return False
    for term in prompt_terms:
        if len(term) < minimum_length:
            continue
        if term in normalized_snippet:
            return True
        compact_term = re.sub(r"[^a-z0-9]+", "", term)
        if len(compact_term) >= 10 and compact_term in re.sub(r"[^a-z0-9]+", "", normalized_snippet):
            return True
    return False


def _contains_diagnostic_emission(snippet: str) -> bool:
    return bool(
        re.search(
            r"\b(?:warn|warning|error|diagnostic|throw|fail|expects?|invalid|unsafe)\b",
            snippet,
            flags=re.IGNORECASE,
        )
    )


def _normalize_phrase(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _repair_missing_required_evidence(
    markdown: str,
    used_refs: Sequence[str],
    *,
    evidence: Sequence[EvidenceItem],
    required_evidence: Sequence[EvidenceItem],
) -> tuple[str, list[str]]:
    used = list(used_refs)
    used_set = set(used)
    missing = [item for item in required_evidence if not _required_evidence_is_visibly_cited(item, markdown)]
    if not missing:
        return markdown, used

    additions: list[str] = []
    evidence_by_ref = {item.source_id: item for item in evidence}
    for item in missing:
        if item.source_id not in evidence_by_ref:
            continue
        additions.append(_required_evidence_note(item))
        if item.source_id not in used_set:
            used.append(item.source_id)
            used_set.add(item.source_id)
    if not additions:
        return markdown, used

    repaired = markdown.rstrip()
    repaired += "\n\n## Evidence Not To Miss\n\n"
    repaired += "\n".join(additions)
    return repaired, used


def _required_evidence_note(item: EvidenceItem) -> str:
    metadata = dict(item.metadata)
    coverage_area = str(metadata.get("coverage_area", "")).strip()
    link = _evidence_link(item)
    reason = "This retrieved snippet is a high-priority anchor for the explanation."
    if _contains_diagnostic_emission(item.snippet):
        reason = "This snippet matters because it shows the diagnostic or error path directly."
    if coverage_area:
        reason += f" It was retrieved for the `{coverage_area}` part of the question."
    return f"- {reason} See {link}."


def _required_evidence_is_visibly_cited(item: EvidenceItem, markdown: str) -> bool:
    if _evidence_link(item) in markdown:
        return True
    item_path = _path_from_source_id(item.source_id)
    item_range = _line_bounds_from_source_id(item.source_id)
    for cited_path, cited_range in _markdown_citation_ranges(markdown):
        if cited_path != item_path:
            continue
        if item_range is None or cited_range is None:
            return True
        if _line_ranges_overlap(item_range, cited_range):
            return True
    return False


def _markdown_citation_ranges(markdown: str) -> tuple[tuple[str, tuple[int, int] | None], ...]:
    citations: list[tuple[str, tuple[int, int] | None]] = []
    for href in re.findall(r"\]\(([^)]+)\)", markdown):
        path, _, anchor = href.partition("#")
        normalized_path = path.replace("%20", " ").replace("\\", "/")
        line_range = _line_bounds_from_anchor(anchor)
        citations.append((normalized_path, line_range))
    return tuple(citations)


def _line_bounds_from_source_id(source_id: str) -> tuple[int, int] | None:
    match = LINE_RANGE_PATTERN.search(source_id)
    if match is None:
        return None
    start = int(match.group("start"))
    end = int(match.group("end") or start)
    return (start, end)


def _line_bounds_from_anchor(anchor: str) -> tuple[int, int] | None:
    match = re.match(r"^L(?P<start>\d+)(?:-L(?P<end>\d+))?$", anchor)
    if match is None:
        return None
    start = int(match.group("start"))
    end = int(match.group("end") or start)
    return (start, end)


def _line_ranges_overlap(left: tuple[int, int], right: tuple[int, int]) -> bool:
    left_start, left_end = left
    right_start, right_end = right
    return left_start <= right_end and right_start <= left_end


def _compact_retrieval_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    gate = summary.get("deterministic_coverage_gate", {})
    compact: dict[str, Any] = {
        "selected_count": summary.get("selected_count"),
        "stop_reason": summary.get("stop_reason"),
    }
    if isinstance(gate, Mapping):
        compact["deterministic_coverage_gate"] = {
            "satisfied": gate.get("satisfied"),
            "missing_roles": list(gate.get("missing_roles", ()))[:8],
            "reasons": list(gate.get("reasons", ()))[:8],
        }
    required_buckets = summary.get("required_role_buckets", ())
    if isinstance(required_buckets, Sequence) and not isinstance(required_buckets, (str, bytes)):
        compact["required_role_buckets"] = [
            {
                "role": str(bucket.get("role", "")),
                "role_status": str(bucket.get("role_status", "")),
                "missing_reason": str(bucket.get("missing_reason", "")),
                "accepted_refs": list(bucket.get("accepted_refs", ()))[:4],
            }
            for bucket in required_buckets[:8]
            if isinstance(bucket, Mapping)
        ]
    return compact


def _response_format() -> Mapping[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "response_explanation_markdown",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "markdown": {"type": "string"},
                    "used_evidence_refs": {"type": "array", "items": {"type": "string"}},
                    "understanding_checks": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 3,
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "role": {"type": "string"},
                                "question_type": {"type": "string"},
                                "question": {"type": "string"},
                                "expected_answer_points": {"type": "array", "items": {"type": "string"}},
                                "hint": {"type": "string"},
                                "evidence_refs": {"type": "array", "items": {"type": "string"}},
                                "origin": {"type": "string"},
                            },
                            "required": [
                                "id",
                                "role",
                                "question_type",
                                "question",
                                "expected_answer_points",
                                "hint",
                                "evidence_refs",
                                "origin",
                            ],
                            "additionalProperties": False,
                        },
                    },
                    "render_notes": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "summary": {"type": "string"},
                        },
                        "required": ["title", "summary"],
                        "additionalProperties": False,
                    },
                },
                "required": ["markdown", "used_evidence_refs", "understanding_checks", "render_notes"],
                "additionalProperties": False,
            },
        },
    }


def _load_prompt(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _evidence_link(item: EvidenceItem) -> str:
    label = _evidence_label(item)
    href = _evidence_href(item)
    return f"[{label}]({href})"


def _evidence_label(item: EvidenceItem) -> str:
    metadata = dict(item.metadata)
    path = metadata.get("path") or _path_from_source_id(item.source_id) or item.source_id
    line_range = metadata.get("line_range") or _line_range_from_source_id(item.source_id)
    if line_range and line_range not in path:
        return f"{path}:{line_range}"
    return path


def _evidence_href(item: EvidenceItem) -> str:
    metadata = dict(item.metadata)
    if metadata.get("url"):
        return str(metadata["url"])
    path = metadata.get("path") or _path_from_source_id(item.source_id) or item.source_id
    line_range = metadata.get("line_range") or _line_range_from_source_id(item.source_id)
    normalized = path.replace("\\", "/").replace(" ", "%20")
    if line_range:
        return f"{normalized}#{line_range}"
    return normalized


def _path_from_source_id(source_id: str) -> str:
    if source_id.startswith("repo-pre:"):
        return source_id[len("repo-pre:") :].split(":L", 1)[0]
    if source_id.startswith("workspace:"):
        return source_id[len("workspace:") :].split(":L", 1)[0]
    return ""


def _line_range_from_source_id(source_id: str) -> str:
    match = LINE_RANGE_PATTERN.search(source_id)
    if match is None:
        return ""
    start = match.group("start")
    end = match.group("end")
    return f"L{start}-L{end}" if end else f"L{start}"


def _compact_snippet(snippet: str, *, max_lines: int = 10, max_line_length: int = 180) -> str:
    cleaned = snippet.replace("```", "'''")
    meaningful = [line.rstrip() for line in cleaned.splitlines() if line.strip()]
    selected = meaningful[:max_lines]
    if not selected:
        return ""
    truncated: list[str] = []
    for line in selected:
        if len(line) > max_line_length:
            truncated.append(line[: max_line_length - 3].rstrip() + "...")
        else:
            truncated.append(line)
    if len(meaningful) > len(selected):
        truncated.append("...")
    return "\n".join(truncated)
