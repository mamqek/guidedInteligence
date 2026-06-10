from __future__ import annotations

import json
import re
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

from core.source_policy import SourceCategory
from services.retrieval.obsidian import ObsidianSearchResult, trusted_file_hints_from_obsidian_results
from services.retrieval.pipeline.constants import (
    MAX_EVIDENCE_ITEMS,
    MAX_FILE_ROLE_ALTERNATES,
    MAX_ROLE_CANDIDATE_EVALUATIONS,
    MAX_ROLE_CODE_CONTEXT_TERMS,
    MAX_ROLE_QUERIES,
)
from services.retrieval.pipeline.models import RetrievalCandidate, RoleRetrievalBucket, RoleValidationResult
from services.retrieval.role_specs import (
    path_matches_role,
    role_generic_terms,
    role_keywords as shared_role_keywords,
    role_path_hints,
    role_phrase_from_spec,
    role_query_hints,
    role_support_path_hints,
)
from services.retrieval.responsibility import FileResponsibilityProfile, profile_candidate
from services.retrieval.step2 import WorkspaceRetrievalPlan
from services.retrieval.step2.common import IDENTIFIER_PATTERN, ordered_unique
from services.retrieval.tools import ToolObservation
from services.retrieval.tools.local import file_role as tool_file_role


DECLARATION_PATTERN = re.compile(r"\b(?:class|interface|function|enum|type|namespace|module)\s+([A-Za-z_][A-Za-z0-9_]*)\b")
TRIPLE_SLASH_REFERENCE_PATTERN = re.compile(r'///\s*<reference\s+path=["\']([^"\']+)["\']\s*/?>', re.IGNORECASE)


def coverage_area_names(plan: WorkspaceRetrievalPlan) -> tuple[str, ...]:
    values = [subquery.role for subquery in plan.llm_subqueries]
    values.extend(plan.required_roles)
    values.append("prompt")
    return ordered_unique(values)


def extract_explicit_reference_paths(text: str) -> tuple[str, ...]:
    if not text.strip():
        return ()
    return ordered_unique(match.group(1).strip() for match in TRIPLE_SLASH_REFERENCE_PATTERN.finditer(text) if match.group(1).strip())


def resolve_explicit_reference_path(candidate_path: str, reference_path: str) -> str | None:
    normalized_candidate = candidate_path.replace("\\", "/").strip()
    normalized_reference = reference_path.replace("\\", "/").strip()
    if not normalized_candidate or not normalized_reference:
        return None
    if ":" in normalized_reference or normalized_reference.startswith("/"):
        return None
    if not looks_like_source_file(normalized_reference):
        return None
    base_dir = PurePosixPath(normalized_candidate).parent
    resolved = str((base_dir / PurePosixPath(normalized_reference)).as_posix())
    normalized_parts: list[str] = []
    for part in resolved.split("/"):
        if not part or part == ".":
            continue
        if part == "..":
            if not normalized_parts:
                return None
            normalized_parts.pop()
            continue
        normalized_parts.append(part)
    if not normalized_parts:
        return None
    return "/".join(normalized_parts)


def role_keywords(role: str) -> tuple[str, ...]:
    return shared_role_keywords(role)


def role_query_package(plan: WorkspaceRetrievalPlan, role: str, query: str) -> tuple[str, ...]:
    queries = [query.strip()]
    queries.extend(role_query_hints(role))
    role_term_set = set(role_keywords(role))
    for term in plan.retrieval_terms:
        lowered = term.lower()
        if any(keyword in lowered for keyword in role_term_set):
            queries.append(term)
    if plan.prompt_summary.strip():
        queries.append(f"{plan.prompt_summary.strip()} {role_phrase_from_spec(role, max_terms=2)}".strip())
    for entity in (plan.confirmed_entities or plan.grounded_entities)[:2]:
        if entity.strip():
            queries.append(entity)
    return ordered_unique(value for value in queries if value and value.strip())[:MAX_ROLE_QUERIES]


def iterative_code_context_queries(
    *,
    role: str,
    query: str,
    candidates: Sequence[RetrievalCandidate],
) -> tuple[str, ...]:
    path_diverse = path_diverse_candidates(candidates)
    terms: list[str] = []
    for candidate in path_diverse[:MAX_ROLE_CANDIDATE_EVALUATIONS]:
        if candidate.path:
            terms.append(PurePosixPath(candidate.path.replace("\\", "/")).stem)
        for reference_path in extract_explicit_reference_paths(candidate.text):
            resolved = resolve_explicit_reference_path(candidate.path or "", reference_path)
            if resolved:
                terms.append(PurePosixPath(resolved).stem)
        terms.extend(code_identifier_terms(candidate.text))
    terms.extend(role_owner_context_terms(role))
    selected_terms = ordered_unique(clean_query_terms(terms))[:MAX_ROLE_CODE_CONTEXT_TERMS]
    if not selected_terms:
        return ()
    return (f"{query} {' '.join(selected_terms)}".strip(),)


def code_identifier_terms(text: str) -> tuple[str, ...]:
    blocked = {
        "return",
        "function",
        "class",
        "interface",
        "module",
        "export",
        "public",
        "private",
        "static",
        "undefined",
        "string",
        "number",
        "boolean",
    }
    terms: list[str] = []
    for token in IDENTIFIER_PATTERN.findall(text):
        if len(token) < 5:
            continue
        lowered = token.lower()
        if lowered in blocked:
            continue
        if token[0].isupper() or any(char.isupper() for char in token[1:]):
            terms.append(token)
    return tuple(terms[:MAX_ROLE_CODE_CONTEXT_TERMS])


def role_owner_context_terms(role: str) -> tuple[str, ...]:
    return role_generic_terms(role)


def clean_query_terms(terms: Sequence[str]) -> tuple[str, ...]:
    cleaned: list[str] = []
    for term in terms:
        value = re.sub(r"[^A-Za-z0-9_./-]+", " ", str(term)).strip()
        if not value or len(value) < 3:
            continue
        cleaned.append(value)
    return tuple(cleaned)


def rank_unique_candidates(candidates: Sequence[RetrievalCandidate]) -> tuple[RetrievalCandidate, ...]:
    unique: dict[str, RetrievalCandidate] = {}
    for candidate in candidates:
        key = candidate.source_id or candidate.candidate_id
        existing = unique.get(key)
        if existing is None or candidate_rank_key(candidate) > candidate_rank_key(existing):
            unique[key] = candidate
    return tuple(sorted(unique.values(), key=candidate_rank_key, reverse=True))


def path_diverse_candidates(candidates: Sequence[RetrievalCandidate]) -> tuple[RetrievalCandidate, ...]:
    selected_by_path: dict[str, RetrievalCandidate] = {}
    for candidate in rank_unique_candidates(candidates):
        key = (candidate.path or candidate.source_id or candidate.candidate_id).replace("\\", "/").lower()
        existing = selected_by_path.get(key)
        if existing is None or candidate_rank_key(candidate) > candidate_rank_key(existing):
            selected_by_path[key] = candidate
    return tuple(sorted(selected_by_path.values(), key=candidate_rank_key, reverse=True))


def collapse_candidates_to_file_candidates(
    *,
    role: str,
    candidates: Sequence[RetrievalCandidate],
    retrieval_path: str,
) -> tuple[RetrievalCandidate, ...]:
    grouped: dict[str, list[RetrievalCandidate]] = {}
    for candidate in rank_unique_candidates(candidates):
        if not candidate.path:
            continue
        normalized_path = candidate.path.replace("\\", "/").lstrip("/")
        grouped.setdefault(normalized_path, []).append(candidate)

    collapsed: list[RetrievalCandidate] = []
    for path, path_candidates in grouped.items():
        ranked = sorted(path_candidates, key=candidate_rank_key, reverse=True)
        top = ranked[0]
        chunk_refs = tuple(ordered_unique(candidate.source_id for candidate in ranked[:3]))
        line_ranges = tuple(ordered_unique(str(candidate.line_range or "") for candidate in ranked[:3] if candidate.line_range))
        text_parts: list[str] = []
        for candidate in ranked[:3]:
            excerpt = candidate.text.strip()
            if excerpt:
                text_parts.append(excerpt[:900])
        text = "\n\n".join(text_parts).strip()
        source_id = f"repo-pre:{path}:FILE"
        collapsed.append(
            RetrievalCandidate(
                candidate_id=source_id,
                source_category=top.source_category,
                retrieval_path=retrieval_path,
                text=text,
                score=max(candidate.score for candidate in ranked),
                source_id=source_id,
                path=path,
                line_range="FILE",
                metadata={
                    **dict(top.metadata),
                    "path": path,
                    "coverage_area": role,
                    "retrieval_path": retrieval_path,
                    "file_candidate": "true",
                    "chunk_refs": json.dumps(list(chunk_refs)),
                    "chunk_line_ranges": json.dumps(list(line_ranges)),
                },
            )
        )
    return tuple(sorted(collapsed, key=candidate_rank_key, reverse=True)[:MAX_FILE_ROLE_ALTERNATES])


def role_scoped_narrowed_files(
    retrieval_plan: WorkspaceRetrievalPlan,
    role: str,
    narrowed_files: Sequence[str],
) -> tuple[str, ...]:
    metadata_hints = retrieval_plan.metadata.get("trusted_local_note_file_hints", ())
    trusted_hints = tuple(
        str(path).replace("\\", "/").lstrip("/")
        for path in metadata_hints
        if str(path).strip()
    ) if isinstance(metadata_hints, Sequence) and not isinstance(metadata_hints, (str, bytes)) else ()
    role_hints = tuple(path for path in trusted_hints if role_owner_path_match(role, path))
    return tuple(ordered_unique([*role_hints, *narrowed_files]))


def select_diverse_completion_entries(
    entries: Sequence[tuple[RetrievalCandidate, str, str, RoleValidationResult, float]],
    *,
    limit: int,
) -> tuple[tuple[RetrievalCandidate, str, str, RoleValidationResult, float], ...]:
    remaining = list(entries)
    selected: list[tuple[RetrievalCandidate, str, str, RoleValidationResult, float]] = []
    while remaining and len(selected) < limit:
        best_index = 0
        best_effective_score: float | None = None
        for index, entry in enumerate(remaining):
            effective_score = entry[4] - completion_redundancy_penalty(entry, selected)
            if best_effective_score is None or effective_score > best_effective_score:
                best_effective_score = effective_score
                best_index = index
        selected.append(remaining.pop(best_index))
    return tuple(selected)


def completion_redundancy_penalty(
    entry: tuple[RetrievalCandidate, str, str, RoleValidationResult, float],
    selected: Sequence[tuple[RetrievalCandidate, str, str, RoleValidationResult, float]],
) -> float:
    candidate, source_role, _, _, _ = entry
    penalty = 0.0
    candidate_path = (candidate.path or "").replace("\\", "/").lower()
    candidate_dir = str(Path(candidate_path).parent).replace("\\", "/")
    for selected_candidate, selected_source_role, _, _, _ in selected:
        selected_path = (selected_candidate.path or "").replace("\\", "/").lower()
        if candidate_path and selected_path and candidate_path == selected_path:
            penalty += 2.5
        elif candidate_dir and candidate_dir == str(Path(selected_path).parent).replace("\\", "/"):
            penalty += 0.7
        if source_role and source_role == selected_source_role:
            penalty += 0.35
    return penalty


def bucket_missing_roles(buckets: Sequence[RoleRetrievalBucket]) -> tuple[str, ...]:
    missing = [bucket.role for bucket in buckets if bucket.role_status == "missing"]
    return tuple(ordered_unique(missing))


def bucket_unresolved_roles(buckets: Sequence[RoleRetrievalBucket]) -> tuple[str, ...]:
    missing = [bucket.role for bucket in buckets if bucket.role_status != "strong"]
    return tuple(ordered_unique(missing))


def recovery_anchor_queries(role: str, buckets: Sequence[RoleRetrievalBucket]) -> tuple[str, ...]:
    queries: list[str] = []
    for bucket in buckets:
        if bucket.role == role or bucket.role_status != "strong":
            continue
        for candidate in bucket.accepted_candidates[:1]:
            tokens = DECLARATION_PATTERN.findall(candidate.text)
            if tokens:
                queries.append(f"{role} {' '.join(tokens[:2])}".strip())
            stem = Path(candidate.path or "").stem.lower() if candidate.path else ""
            if stem:
                queries.append(f"{role} {stem}".strip())
    return ordered_unique(queries)


def role_phase_path_allowed(role: str, path: str) -> bool:
    normalized_path = path.lower().replace("\\", "/")
    file_role = tool_file_role(normalized_path)
    if file_role in {"test", "baseline_or_generated"}:
        return False
    if "harness" in normalized_path or "fixture" in normalized_path:
        return False
    if "diagnostic" in normalized_path and role != "diagnostics":
        return False
    if role == "diagnostics":
        return file_role == "implementation" and ("diagnostic" in normalized_path or normalized_path.endswith(".json"))
    return file_role == "implementation"


def anchor_support_path_allowed(path: str) -> bool:
    normalized_path = path.lower().replace("\\", "/")
    file_role = tool_file_role(normalized_path)
    if file_role in {"test", "baseline_or_generated"}:
        return False
    if "harness" in normalized_path or "fixture" in normalized_path:
        return False
    return file_role == "implementation"


def anchor_support_paths(observation: ToolObservation) -> tuple[str, ...]:
    files = observation.payload.get("files", ())
    selected: list[str] = []
    for item in files:
        if not isinstance(item, Mapping):
            continue
        path = str(item.get("path", "")).strip().replace("\\", "/")
        if path and anchor_support_path_allowed(path):
            selected.append(path)
    return tuple(ordered_unique(selected))


def matched_anchor_paths(
    candidate_path: str,
    anchors: Sequence[Any],
    support_map: Mapping[str, Sequence[str]],
) -> tuple[str, ...]:
    normalized = candidate_path.replace("\\", "/").lower()
    supporting_paths: list[str] = []
    for anchor in anchors:
        supported = {path.replace("\\", "/").lower() for path in support_map.get(anchor.path, ())}
        if normalized in supported:
            supporting_paths.append(anchor.path)
    return tuple(ordered_unique(supporting_paths))


def diagnostics_like_candidate(candidate: RetrievalCandidate) -> bool:
    path = (candidate.path or "").lower()
    text = candidate.text.lower()
    return "diagnostic" in path or "error" in text or "message" in text


def candidate_symbol(candidate: RetrievalCandidate) -> str | None:
    for match in DECLARATION_PATTERN.finditer(candidate.text):
        symbol = match.group(1)
        if symbol and len(symbol) >= 4:
            return symbol
    for token in IDENTIFIER_PATTERN.findall(candidate.text):
        if token and len(token) >= 5 and token[0].isupper():
            return token
    return None


def candidate_is_reference_expansion_source(role: str, path: str, profile: FileResponsibilityProfile) -> bool:
    normalized_path = path.replace("\\", "/").lower()
    if profile.noise:
        return False
    if profile.support_only or profile.classification == "possible_owner":
        return True
    if profile.classification == "likely_owner" and not path_matches_role(role, normalized_path):
        return True
    if any(reason.startswith("adjacent_") for reason in profile.reasons):
        return True
    return False


def role_requires_owner_layer(role: str) -> bool:
    return role in {"validation_checking", "input_parsing", "representation", "diagnostics", "behavior_output"}


def candidate_satisfies_owner_layer(role: str, candidate: RetrievalCandidate) -> bool:
    path = candidate.path or ""
    if role_owner_path_match(role, path):
        return True
    profile = profile_candidate(
        role,
        path=path,
        text=candidate.text,
        file_role=candidate.metadata.get("file_role", ""),
    )
    if profile.noise or profile.support_only:
        return False
    return profile.classification == "likely_owner" and not any(reason in profile.reasons for reason in ("plumbing_path", "helper_path", "low_level_leaf"))


def has_role_owner_candidate(role: str, candidates: Sequence[RetrievalCandidate]) -> bool:
    return any(candidate_satisfies_owner_layer(role, candidate) for candidate in candidates)


def role_owner_path_match(role: str, path: str) -> bool:
    return path_matches_role(role, path)


def role_owner_path_tokens(role: str) -> tuple[str, ...]:
    return role_path_hints(role)


def target_matches_reference_owner_vocab(role: str, path: str) -> bool:
    return role_owner_path_match(role, path)


def is_generic_reference_hub(role: str, path: str) -> bool:
    normalized_path = path.replace("\\", "/").lower()
    if role == "validation_checking":
        return any(token in normalized_path for token in role_support_path_hints(role))
    return False


def looks_like_source_file(path: str) -> bool:
    lowered = path.lower()
    return lowered.endswith((".ts", ".tsx", ".js", ".jsx", ".py", ".c", ".cc", ".cpp", ".h", ".hpp", ".java", ".cs"))


def line_start_from_range(line_range: str | None) -> int:
    if not line_range:
        return 1
    match = re.match(r"L(\d+)", line_range)
    if match is None:
        return 1
    return max(1, int(match.group(1)))


def candidate_from_chunk_payload(payload: Mapping[str, Any], *, coverage_area: str, retrieval_path: str) -> RetrievalCandidate:
    path = str(payload.get("path", "") or "")
    line_range = str(payload.get("line_range", "") or "")
    metadata = {
        "snapshot": str(payload.get("snapshot", "")),
        "commit": str(payload.get("commit", "")),
        "visibility": str(payload.get("visibility", "")),
        "file_role": tool_file_role(path) if path else "",
        "coverage_area": coverage_area,
        "retrieval_path": retrieval_path,
        "path": path,
    }
    return RetrievalCandidate(
        candidate_id=str(payload.get("chunk_id", "")),
        source_category=SourceCategory(str(payload.get("source_category", SourceCategory.SOURCE_CODE.value))),
        retrieval_path=retrieval_path,
        text=str(payload.get("text", "")),
        score=float(payload.get("score", 0.0) or 0.0),
        source_id=str(payload.get("chunk_id", "")),
        path=path or None,
        line_range=line_range or None,
        metadata=metadata,
    )


def candidate_rank_key(candidate: RetrievalCandidate) -> tuple[float, float]:
    role_weight = {
        "implementation": 1.3,
        "documentation": 0.85,
        "test": 0.2,
        "baseline_or_generated": 0.1,
        "other": 0.6,
        "": 0.7,
    }.get(candidate.metadata.get("file_role", ""), 0.6)
    category_weight = {
        SourceCategory.SOURCE_CODE: 1.3,
        SourceCategory.DOCUMENTATION: 0.8,
        SourceCategory.ISSUE_TRACKER: 0.5,
        SourceCategory.PULL_REQUEST: 0.5,
        SourceCategory.LOCAL_NOTES: 0.5,
        SourceCategory.NOTEBOOKLM: 0.5,
    }.get(candidate.source_category, 0.5)
    return candidate.score * role_weight * category_weight, candidate.score


def merge_source_priorities(
    preferred: Sequence[SourceCategory],
    existing: Sequence[SourceCategory],
) -> tuple[SourceCategory, ...]:
    selected: list[SourceCategory] = []
    for category in (*preferred, *existing):
        if category not in selected:
            selected.append(category)
    return tuple(selected)


def trusted_file_hints_for_result(result: ObsidianSearchResult) -> tuple[str, ...]:
    return trusted_file_hints_from_obsidian_results((result,))


def obsidian_source_queries(prompt: str) -> tuple[str, ...]:
    normalized = prompt.replace("`", " ")
    candidates: list[str] = []
    title_match = re.search(r"^Title:\s*(.+)$", normalized, re.IGNORECASE | re.MULTILINE)
    if title_match:
        candidates.append(title_match.group(1))
    identifiers = [
        token
        for token in IDENTIFIER_PATTERN.findall(normalized)
        if len(token) >= 4 and token.lower() not in {"explain", "code", "context", "needed", "issue", "support"}
    ]
    if identifiers:
        candidates.append(" ".join(identifiers[:5]))
    candidates.append(prompt[:500])
    return ordered_unique([candidate.strip() for candidate in candidates if candidate.strip()])


def tool_summary_payload(observation: ToolObservation) -> dict[str, Any]:
    links: list[str] = []
    seen_links: set[str] = set()

    def add_link(value: str) -> None:
        normalized = value.strip()
        if not normalized or normalized in seen_links:
            return
        seen_links.add(normalized)
        links.append(normalized)

    for ref in observation.source_refs:
        add_link(str(ref))

    payload = observation.payload
    if isinstance(payload.get("files"), list):
        for item in payload["files"][:20]:
            if not isinstance(item, Mapping):
                continue
            path = str(item.get("path", "")).strip()
            line = item.get("line")
            add_link(f"{path}:L{line}" if path and line else path)
    if isinstance(payload.get("results"), list):
        for item in payload["results"][:20]:
            if not isinstance(item, Mapping):
                continue
            chunk_id = str(item.get("chunk_id", "")).strip()
            path = str(item.get("path", "")).strip()
            line_range = str(item.get("line_range", "")).strip()
            add_link(chunk_id or (f"{path}:{line_range}" if path and line_range else path))
    if isinstance(payload.get("snippets"), list):
        for item in payload["snippets"][:20]:
            if not isinstance(item, Mapping):
                continue
            chunk_id = str(item.get("chunk_id", "")).strip()
            path = str(item.get("path", "")).strip()
            line_range = str(item.get("line_range", "")).strip()
            add_link(chunk_id or (f"{path}:{line_range}" if path and line_range else path))

    return {
        "result_count": str(observation.metadata.get("result_count", "")),
        "result_links": links,
        "metadata": dict(observation.metadata),
    }
