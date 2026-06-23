from __future__ import annotations

import json
import re
from typing import Any, Callable, Mapping, Sequence

from core.source_policy import SourceCategory
from .common import (
    IDENTIFIER_PATTERN,
    PATH_PATTERN,
    bounded_file_hints,
    is_query_token,
    ordered_unique,
)
from .constants import (
    DEFAULT_NEGATIVE_FILTERS,
    DEFAULT_REQUIRED_RETRIEVAL_ROLES,
    DEFAULT_SUPPORTING_RETRIEVAL_ROLES,
    MAX_GROUNDED_ENTITIES,
    MAX_GROUNDED_FILE_HINTS,
    MAX_RAW_PROMPT_TERMS,
)
from .prompts import STEP2_PLANNER_SYSTEM_PROMPT
from .schema import step2_response_format, validate_step2_planner_response
from .types import PromptEvidence, RoleDirectedSubquery, WorkspaceRetrievalPlan
from services.retrieval.workspace.llm import complete_json, message_to_dict


INLINE_CODE_PATTERN = re.compile(r"(?<!`)`([^`\n]+)`(?!`)")
QUOTED_TOKEN_PATTERN = re.compile(r"\"([^\n\"]{1,120})\"|(?<![A-Za-z0-9])'([^\n']{1,120})'(?![A-Za-z0-9])")
ERROR_TEXT_PATTERN = re.compile(r"(?im)^(?:error|exception|warning|traceback|failed|cannot|unsupported)\b.*$")
FLAG_PATTERN = re.compile(r"--[A-Za-z0-9_-]+|(?<!['â€™])\b[A-Za-z0-9_][A-Za-z0-9_-]*(?:\.[A-Za-z0-9_][A-Za-z0-9_-]*)+\b")


def plan_workspace_retrieval_step(
    *,
    state: Any,
    policy_result: Any,
    connected_documents: Sequence[Any],
    llm_config: Any,
    prompt_evidence: PromptEvidence | None = None,
    repo_context: Mapping[str, Any] | None = None,
    log_warning: Callable[[Mapping[str, Any]], None] | None = None,
    log_event: Callable[[str, Mapping[str, Any]], None] | None = None,
) -> WorkspaceRetrievalPlan:
    evidence = prompt_evidence or extract_prompt_evidence(state, policy_result.allowed_sources)
    payload = {
        "raw_prompt": state.user_input,
        "history": [message_to_dict(message) for message in state.history[-6:]],
        "existing_evidence": [item.to_dict() for item in state.evidence[:6]],
        "allowed_sources": [category.value for category in policy_result.allowed_sources],
        "connected_sources": [
            {
                "source_category": document.source_category.value,
                "source_key": str(getattr(document, "source_key", "") or ""),
                "source_id": document.source_id,
                "title": document.title,
                "snippet": str(getattr(document, "content", ""))[:800],
                "metadata": dict(getattr(document, "metadata", {}) or {}),
            }
            for document in connected_documents[:20]
        ],
        "required_roles": list(DEFAULT_REQUIRED_RETRIEVAL_ROLES),
        "supporting_roles": list(DEFAULT_SUPPORTING_RETRIEVAL_ROLES),
        "deterministic_prompt_evidence": evidence.to_dict(),
        "repo_context": dict(repo_context or {}),
    }
    messages = (
        {"role": "system", "content": STEP2_PLANNER_SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(payload, sort_keys=True)},
    )
    response = validate_step2_planner_response(
        complete_json(
            llm_config,
            messages,
            response_format=step2_response_format(),
            log_warning=log_warning,
            log_event=log_event,
        ),
        allowed_sources=policy_result.allowed_sources,
    )
    merged_negative_filters = ordered_unique(
        tuple(str(value).strip() for value in DEFAULT_NEGATIVE_FILTERS if str(value).strip())
        + tuple(response["negative_filters"])
    )
    confirmed_entities = tuple(
        str(value).strip()
        for value in (repo_context or {}).get("confirmed_entities", ())
        if str(value).strip()
    )
    confirmed_file_hints = tuple(
        str(value).strip()
        for value in (repo_context or {}).get("confirmed_file_hints", ())
        if str(value).strip()
    )
    return WorkspaceRetrievalPlan(
        conversation_id=state.conversation_id,
        raw_prompt=state.user_input,
        raw_prompt_evidence=evidence.raw_prompt_evidence,
        prompt_summary=response["prompt_summary"],
        retrieval_terms=tuple(response["retrieval_terms"]),
        surface_context_terms=tuple(response["surface_context_terms"]),
        owner_artifact_terms=tuple(response["owner_artifact_terms"]),
        grounded_entities=evidence.grounded_entities,
        confirmed_entities=confirmed_entities,
        grounded_file_hints=evidence.grounded_file_hints,
        confirmed_file_hints=confirmed_file_hints,
        llm_concept_terms=tuple(response["llm_concept_terms"]),
        llm_subqueries=tuple(
            subquery if isinstance(subquery, RoleDirectedSubquery) else RoleDirectedSubquery(**dict(subquery))
            for subquery in response["llm_subqueries"]
        ),
        owner_subqueries=tuple(
            subquery if isinstance(subquery, RoleDirectedSubquery) else RoleDirectedSubquery(**dict(subquery))
            for subquery in response["owner_subqueries"]
        ),
        support_subqueries=tuple(
            subquery if isinstance(subquery, RoleDirectedSubquery) else RoleDirectedSubquery(**dict(subquery))
            for subquery in response["support_subqueries"]
        ),
        speculative_entities=tuple(response["speculative_entities"]),
        source_priorities=tuple(SourceCategory(value) for value in response["source_priorities"]) or evidence.source_priorities,
        negative_filters=merged_negative_filters,
        required_roles=DEFAULT_REQUIRED_RETRIEVAL_ROLES,
        supporting_roles=DEFAULT_SUPPORTING_RETRIEVAL_ROLES,
        metadata={
            "planner": "llm_workspace_grounded_v2",
            "repo_context": dict(repo_context or {}),
        },
    )


def existing_evidence_plan(
    *,
    conversation_id: str,
    raw_prompt: str,
    allowed_sources: Sequence[SourceCategory],
) -> WorkspaceRetrievalPlan:
    source_priorities = tuple(
        category
        for category in allowed_sources
        if category in {SourceCategory.SOURCE_CODE, SourceCategory.DOCUMENTATION}
    ) or tuple(allowed_sources)
    return WorkspaceRetrievalPlan(
        conversation_id=conversation_id,
        raw_prompt=raw_prompt,
        raw_prompt_evidence=(),
        prompt_summary="",
        retrieval_terms=(),
        surface_context_terms=(),
        owner_artifact_terms=(),
        grounded_entities=(),
        confirmed_entities=(),
        grounded_file_hints=(),
        confirmed_file_hints=(),
        llm_concept_terms=(),
        llm_subqueries=(),
        owner_subqueries=(),
        support_subqueries=(),
        speculative_entities=(),
        source_priorities=source_priorities,
        negative_filters=DEFAULT_NEGATIVE_FILTERS,
        required_roles=DEFAULT_REQUIRED_RETRIEVAL_ROLES,
        supporting_roles=DEFAULT_SUPPORTING_RETRIEVAL_ROLES,
        metadata={"planner": "existing_evidence_short_circuit"},
    )


def extract_prompt_evidence(state: Any, allowed_sources: Sequence[SourceCategory]) -> PromptEvidence:
    return PromptEvidence(
        raw_prompt_evidence=_extract_raw_prompt_evidence(state),
        grounded_entities=_extract_grounded_entities(state.user_input),
        grounded_file_hints=_extract_grounded_file_hints(state),
        source_priorities=_source_priorities_for_prompt(state.user_input, allowed_sources),
    )


def _extract_raw_prompt_evidence(state: Any) -> tuple[str, ...]:
    combined = "\n".join([state.user_input, *[message.content for message in state.history[-6:]]])
    exact_terms: list[str] = []
    exact_terms.extend(match.group(1).strip() for match in INLINE_CODE_PATTERN.finditer(combined) if match.group(1).strip())
    for match in QUOTED_TOKEN_PATTERN.findall(combined):
        token = next((value.strip() for value in match if value.strip()), "")
        if token:
            exact_terms.append(token)
    exact_terms.extend(PATH_PATTERN.findall(combined))
    exact_terms.extend(match.group(0).strip() for match in ERROR_TEXT_PATTERN.finditer(combined))
    exact_terms.extend(match.group(0).strip() for match in FLAG_PATTERN.finditer(combined))
    exact = ordered_unique(exact_terms)
    if exact:
        return exact[:MAX_RAW_PROMPT_TERMS]
    return _extract_salient_prompt_terms(combined)[:MAX_RAW_PROMPT_TERMS]


def _extract_salient_prompt_terms(text: str) -> tuple[str, ...]:
    tokens = [
        token.lower()
        for token in IDENTIFIER_PATTERN.findall(text)
        if len(token) >= 4 and is_query_token(token) and token.lower() not in _RAW_PROMPT_STOPWORDS
    ]
    terms: list[str] = []
    terms.extend(tokens)
    terms.extend(_salient_domain_expansions(tokens))
    for left, right in zip(tokens, tokens[1:]):
        if left == right:
            continue
        terms.append(f"{left} {right}")
    return ordered_unique(terms)


def _salient_domain_expansions(tokens: Sequence[str]) -> tuple[str, ...]:
    token_set = set(tokens)
    expansions: list[str] = []
    if {"indexing", "alert"} <= token_set or ({"indexing", "completion"} <= token_set):
        expansions.extend(
            [
                "index_ready",
                "index_status",
                "index_estimate",
                "index prepare",
                "prepare index",
                "index readiness",
            ]
        )
    return tuple(expansions)


def _extract_grounded_entities(prompt: str) -> tuple[str, ...]:
    entities: list[str] = []
    for match in INLINE_CODE_PATTERN.finditer(prompt):
        token = match.group(1).strip()
        if token and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*", token):
            entities.append(token)
    entities.extend(
        token
        for token in IDENTIFIER_PATTERN.findall(prompt)
        if is_query_token(token) and ("_" in token or "." in token or token.isupper() or any(char.isupper() for char in token[1:]))
    )
    return ordered_unique(entities)[:MAX_GROUNDED_ENTITIES]


def _extract_grounded_file_hints(state: Any) -> tuple[str, ...]:
    combined = "\n".join([state.user_input, *[message.content for message in state.history[-6:]]])
    return bounded_file_hints(PATH_PATTERN.findall(combined), limit=MAX_GROUNDED_FILE_HINTS)


def _source_priorities_for_prompt(prompt: str, allowed_sources: Sequence[SourceCategory]) -> tuple[SourceCategory, ...]:
    ordered: list[SourceCategory] = []
    normalized = prompt.lower()
    for category in allowed_sources:
        if category in {SourceCategory.SOURCE_CODE, SourceCategory.DOCUMENTATION}:
            ordered.append(category)
    if "issue" in normalized and SourceCategory.ISSUE_TRACKER in allowed_sources:
        ordered.append(SourceCategory.ISSUE_TRACKER)
    if ("pr" in normalized or "pull request" in normalized) and SourceCategory.PULL_REQUEST in allowed_sources:
        ordered.append(SourceCategory.PULL_REQUEST)
    if "note" in normalized and SourceCategory.LOCAL_NOTES in allowed_sources:
        ordered.append(SourceCategory.LOCAL_NOTES)
    if "notebook" in normalized and SourceCategory.NOTEBOOKLM in allowed_sources:
        ordered.append(SourceCategory.NOTEBOOKLM)
    ordered.extend(category for category in allowed_sources if category not in ordered)
    return tuple(ordered)


_RAW_PROMPT_STOPWORDS = {
    "about",
    "after",
    "already",
    "before",
    "could",
    "does",
    "from",
    "have",
    "here",
    "into",
    "like",
    "look",
    "made",
    "more",
    "need",
    "reason",
    "repo",
    "right",
    "shows",
    "some",
    "something",
    "still",
    "that",
    "these",
    "this",
    "tool",
    "part",
    "wasn",
    "when",
    "where",
    "whether",
    "while",
    "with",
    "would",
}

