from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from core.source_policy import SourceCategory
from services.retrieval.pipeline.models import RetrievalCandidate, RoleRetrievalBucket
from services.retrieval.pipeline.snippet_level import read_owner_text_file
from services.retrieval.step2.common import ordered_unique


@dataclass(frozen=True)
class ProtocolCandidatePromotion:
    target_bucket_index: int | None
    target_role: str
    source: str
    candidates: tuple[RetrievalCandidate, ...]


@dataclass(frozen=True)
class ProtocolRelationshipResult:
    routes: tuple[str, ...]
    message_terms: tuple[str, ...]
    promotions: tuple[ProtocolCandidatePromotion, ...]


def discover_protocol_relationship_candidates(
    *,
    workspace_root: str | Path,
    buckets: Sequence[RoleRetrievalBucket],
    max_candidates: int,
    seed_texts: Sequence[str] = (),
) -> ProtocolRelationshipResult:
    promotions: list[ProtocolCandidatePromotion] = []
    route_literals = _frontend_route_literals_from_buckets(buckets)
    target_index = _route_bridge_target_bucket_index(buckets) if route_literals else None
    ranked_routes = route_literals

    root = Path(workspace_root)
    if target_index is not None:
        target_bucket = buckets[target_index]
        ranked_routes = _rank_route_literals_for_bucket(route_literals, target_bucket)
        promoted = _frontend_route_bridge_candidates(
            workspace_root=root,
            role=target_bucket.role,
            route_literals=ranked_routes,
            existing_paths=_existing_candidate_paths(buckets),
            existing_refs=_existing_candidate_refs(buckets),
            max_candidates=max_candidates,
        )
        if promoted:
            promotions.append(
                ProtocolCandidatePromotion(
                    target_bucket_index=target_index,
                    target_role=target_bucket.role,
                    source="frontend_route_literal_to_backend_handler",
                    candidates=promoted,
                )
            )

    message_terms = _message_literal_terms(seed_texts)
    message_target_index = _target_bucket_index_for_role(buckets, "diagnostics")
    if message_target_index is not None and message_terms:
        target_bucket = buckets[message_target_index]
        promoted = _message_literal_bridge_candidates(
            workspace_root=root,
            role=target_bucket.role,
            message_terms=_rank_message_terms_for_bucket(message_terms, target_bucket),
            existing_paths=set(),
            existing_refs=_existing_candidate_refs(buckets),
            max_candidates=max_candidates,
        )
        if promoted:
            promotions.append(
                ProtocolCandidatePromotion(
                    target_bucket_index=message_target_index,
                    target_role=target_bucket.role,
                    source="prompt_message_literal_to_code",
                    candidates=promoted,
                )
            )

    return ProtocolRelationshipResult(
        routes=ranked_routes,
        message_terms=message_terms,
        promotions=tuple(promotions),
    )


def _existing_candidate_paths(buckets: Sequence[RoleRetrievalBucket]) -> set[str]:
    return {candidate.path for bucket in buckets for candidate in bucket.accepted_candidates if candidate.path}


def _existing_candidate_refs(buckets: Sequence[RoleRetrievalBucket]) -> set[str]:
    return {candidate.source_id for bucket in buckets for candidate in bucket.accepted_candidates}


def _frontend_route_literals_from_buckets(buckets: Sequence[RoleRetrievalBucket]) -> tuple[str, ...]:
    routes: list[str] = []
    for bucket in buckets:
        for candidate in bucket.accepted_candidates:
            path = (candidate.path or "").replace("\\", "/").lower()
            if _looks_like_frontend_api_caller(path, candidate.text):
                routes.extend(_extract_frontend_route_literals(candidate.text))
    return tuple(ordered_unique(routes))[:8]


def _looks_like_frontend_api_caller(path: str, text: str) -> bool:
    frontend_path = bool(re.search(r"(?:^|/)(?:ui|web|client|frontend|app|components|pages|src)(?:/|$)", path))
    frontend_extension = path.endswith((".tsx", ".jsx", ".vue", ".svelte"))
    api_call = bool(re.search(r"\brequestJson(?:<[^>\n]+>)?\s*\(|\b(?:fetch|axios\.(?:get|post|put|patch|delete))\s*\(", text))
    return api_call and (frontend_path or frontend_extension)


def _extract_frontend_route_literals(text: str) -> tuple[str, ...]:
    routes: list[str] = []
    patterns = (
        r"\brequestJson(?:<[^>\n]+>)?\s*\(\s*[\"'](?P<route>/[^\"']+)[\"']",
        r"\bfetch\s*\(\s*[\"'](?P<route>/[^\"']+)[\"']",
        r"\baxios\.(?:get|post|put|patch|delete)\s*\(\s*[\"'](?P<route>/[^\"']+)[\"']",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            route = _normalize_route_literal(match.group("route"))
            if route:
                routes.append(route)
    return tuple(ordered_unique(routes))


def _normalize_route_literal(route: str) -> str:
    route = route.strip()
    if not route.startswith("/") or route.startswith("//"):
        return ""
    route = route.split("?", 1)[0].split("#", 1)[0].rstrip("/")
    if not route or "{" in route or "}" in route or "$" in route:
        return ""
    return route


def _route_bridge_target_bucket_index(buckets: Sequence[RoleRetrievalBucket]) -> int | None:
    for role in ("input_parsing", "validation_checking", "behavior_output"):
        for index, bucket in enumerate(buckets):
            if bucket.role == role:
                return index
    return 0 if buckets else None


def _target_bucket_index_for_role(buckets: Sequence[RoleRetrievalBucket], role: str) -> int | None:
    for index, bucket in enumerate(buckets):
        if bucket.role == role:
            return index
    return None


def _rank_route_literals_for_bucket(route_literals: Sequence[str], bucket: RoleRetrievalBucket) -> tuple[str, ...]:
    query_text = " ".join((bucket.query, *bucket.helper_queries)).lower()
    ranked: list[tuple[int, int, str]] = []
    for index, route in enumerate(route_literals):
        route_terms = [term for term in re.split(r"[^a-z0-9]+", route.lower()) if len(term) >= 3]
        score = sum(1 for term in route_terms if term in query_text)
        if route.lower() in query_text:
            score += 4
        ranked.append((-score, index, route))
    return tuple(route for _score, _index, route in sorted(ranked))


def _message_literal_terms(seed_texts: Sequence[str]) -> tuple[str, ...]:
    candidates: list[str] = []
    for text in seed_texts:
        candidates.extend(_quoted_message_terms(text))
        candidates.extend(_error_line_message_terms(text))
    return tuple(ordered_unique(term for term in candidates if _looks_like_message_term(term)))[:12]


def _quoted_message_terms(text: str) -> tuple[str, ...]:
    terms: list[str] = []
    for match in re.finditer(r"[`\"'](?P<value>[^`\"'\n]{8,120})[`\"']", text):
        value = _normalize_message_term(match.group("value"))
        if value:
            terms.extend(_message_term_variants(value))
    return tuple(terms)


def _error_line_message_terms(text: str) -> tuple[str, ...]:
    terms: list[str] = []
    for line in text.splitlines():
        if not re.search(r"\b(?:error|warn|warning|invalid|unsafe|cannot|expects?|expected|must|required)\b", line, re.IGNORECASE):
            continue
        value = _normalize_message_term(line)
        if value:
            terms.extend(_message_term_variants(value))
    return tuple(terms)


def _normalize_message_term(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    value = value.replace("\\n", " ")
    value = re.sub(r"\s+", " ", value).strip(" `\"'.,;")
    return value


def _message_term_variants(value: str) -> tuple[str, ...]:
    variants = [value]
    for separator in (":", "."):
        if separator in value:
            prefix = value.split(separator, 1)[0].strip()
            if prefix:
                variants.append(prefix)
    if len(value) > 80:
        for match in re.finditer(r"\b(?:Error|Warning|Invalid|Unsafe|Cannot|expects?|expected|must|required)\b[^.:\n]{6,80}", value, re.IGNORECASE):
            variants.append(match.group(0).strip())
    for match in re.finditer(r"\b(?:expects?|expected|cannot|must|required|invalid|unsafe)\b[^.:\n]{3,80}", value, re.IGNORECASE):
        variants.append(match.group(0).strip())
    return tuple(variants)


def _looks_like_message_term(value: str) -> bool:
    if len(value) < 8 or len(value) > 120:
        return False
    if "/" in value and not re.search(r"\b(?:error|warn|invalid|cannot|expects?|must|required)\b", value, re.IGNORECASE):
        return False
    return bool(re.search(r"\b(?:error|warn|warning|invalid|unsafe|cannot|expects?|expected|must|required)\b", value, re.IGNORECASE))


def _rank_message_terms_for_bucket(message_terms: Sequence[str], bucket: RoleRetrievalBucket) -> tuple[str, ...]:
    query_text = " ".join((bucket.query, *bucket.helper_queries)).lower()
    ranked: list[tuple[int, int, str]] = []
    for index, term in enumerate(message_terms):
        term_tokens = [token for token in re.split(r"[^a-z0-9]+", term.lower()) if len(token) >= 4]
        score = sum(1 for token in term_tokens if token in query_text)
        if term.lower() in query_text:
            score += 4
        ranked.append((-score, index, term))
    return tuple(term for _score, _index, term in sorted(ranked))


def _frontend_route_bridge_candidates(
    *,
    workspace_root: Path,
    role: str,
    route_literals: Sequence[str],
    existing_paths: set[str],
    existing_refs: set[str],
    max_candidates: int,
) -> tuple[RetrievalCandidate, ...]:
    root = workspace_root.resolve()
    candidates: list[RetrievalCandidate] = []
    for file_path in _iter_route_bridge_source_files(root):
        relative_path = file_path.relative_to(root).as_posix()
        if relative_path in existing_paths:
            continue
        text = read_owner_text_file(file_path)
        if text is None:
            continue
        lines = text.splitlines()
        for route in route_literals:
            match_line = _first_route_literal_line(lines, route)
            if match_line is None:
                continue
            start, end = _route_bridge_span(lines, match_line)
            snippet = "\n".join(lines[start - 1 : end])
            source_id = f"repo-pre:{relative_path}:L{start}-L{end}"
            if source_id in existing_refs:
                continue
            candidates.append(
                RetrievalCandidate(
                    candidate_id=f"protocol_route_bridge:{relative_path}:{route}",
                    source_category=SourceCategory.SOURCE_CODE,
                    retrieval_path="protocol_route_bridge",
                    text=snippet,
                    score=18.0,
                    source_id=source_id,
                    path=relative_path,
                    line_range=f"L{start}-L{end}",
                    metadata={
                        "path": relative_path,
                        "coverage_area": role,
                        "file_role": "implementation",
                        "retrieval_path": "protocol_route_bridge",
                        "protocol_edge": "frontend_route_literal_to_backend_handler",
                        "bridge_route": route,
                    },
                )
            )
            existing_refs.add(source_id)
            break
        if len(candidates) >= max_candidates:
            break
    return tuple(candidates)


def _message_literal_bridge_candidates(
    *,
    workspace_root: Path,
    role: str,
    message_terms: Sequence[str],
    existing_paths: set[str],
    existing_refs: set[str],
    max_candidates: int,
) -> tuple[RetrievalCandidate, ...]:
    root = workspace_root.resolve()
    candidates: list[RetrievalCandidate] = []
    for file_path in _iter_message_bridge_source_files(root):
        relative_path = file_path.relative_to(root).as_posix()
        if relative_path in existing_paths:
            continue
        text = read_owner_text_file(file_path)
        if text is None:
            continue
        lines = text.splitlines()
        for term in message_terms:
            match_line = _first_message_literal_line(lines, term)
            if match_line is None:
                continue
            start, end = _message_bridge_span(lines, match_line)
            snippet = "\n".join(lines[start - 1 : end])
            source_id = f"repo-pre:{relative_path}:L{start}-L{end}"
            if source_id in existing_refs:
                continue
            candidates.append(
                RetrievalCandidate(
                    candidate_id=f"protocol_message_bridge:{relative_path}:{term}",
                    source_category=SourceCategory.SOURCE_CODE,
                    retrieval_path="protocol_message_bridge",
                    text=snippet,
                    score=16.0,
                    source_id=source_id,
                    path=relative_path,
                    line_range=f"L{start}-L{end}",
                    metadata={
                        "path": relative_path,
                        "coverage_area": role,
                        "file_role": "implementation",
                        "retrieval_path": "protocol_message_bridge",
                        "protocol_edge": "prompt_message_literal_to_code",
                        "bridge_message": term,
                    },
                )
            )
            existing_refs.add(source_id)
            break
        if len(candidates) >= max_candidates:
            break
    return tuple(candidates)


def _iter_route_bridge_source_files(root: Path) -> tuple[Path, ...]:
    excluded_parts = {
        ".git",
        ".guided-intelligence",
        ".venv",
        "__pycache__",
        "node_modules",
        "dist",
        "build",
        "coverage",
        "tests",
        "test",
        "__tests__",
    }
    suffixes = {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".go", ".rs", ".java", ".kt", ".cs", ".rb", ".php"}
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in suffixes:
            continue
        relative_parts = path.relative_to(root).parts
        if {part.lower() for part in relative_parts} & excluded_parts:
            continue
        if _looks_like_backend_route_path(path.relative_to(root).as_posix()):
            files.append(path)
    return tuple(sorted(files, key=lambda item: item.relative_to(root).as_posix()))


def _iter_message_bridge_source_files(root: Path) -> tuple[Path, ...]:
    excluded_parts = {
        ".git",
        ".guided-intelligence",
        ".venv",
        "__pycache__",
        "node_modules",
        "dist",
        "build",
        "coverage",
        "tests",
        "test",
        "__tests__",
    }
    suffixes = {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".go", ".rs", ".java", ".kt", ".cs", ".rb", ".php", ".json"}
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in suffixes:
            continue
        relative_parts = path.relative_to(root).parts
        if {part.lower() for part in relative_parts} & excluded_parts:
            continue
        if _looks_like_message_owner_path(path.relative_to(root).as_posix()):
            files.append(path)
    return tuple(sorted(files, key=lambda item: item.relative_to(root).as_posix()))


def _looks_like_backend_route_path(path: str) -> bool:
    return bool(re.search(r"(?:^|/)(?:server|backend|api|route|routes|handler|handlers|controller|controllers|service|services)(?:/|\.|-|_)", path.lower()))


def _looks_like_message_owner_path(path: str) -> bool:
    lowered = path.lower()
    return bool(
        re.search(
            r"(?:^|/)(?:diagnostic|diagnostics|error|errors|warning|warnings|parser|parse|directive|validator|validation|checker|check|messages?)(?:/|\.|-|_)",
            lowered,
        )
    )


def _first_route_literal_line(lines: Sequence[str], route: str) -> int | None:
    route_pattern = re.compile(rf"[\"']{re.escape(route)}(?:/)?[\"']")
    for index, line in enumerate(lines, start=1):
        if route_pattern.search(line):
            return index
    return None


def _first_message_literal_line(lines: Sequence[str], term: str) -> int | None:
    lowered = term.lower()
    for index, line in enumerate(lines, start=1):
        if lowered in line.lower():
            return index
    return None


def _route_bridge_span(lines: Sequence[str], match_line: int) -> tuple[int, int]:
    start = max(1, match_line - 8)
    end = min(len(lines), match_line + 24)
    for index in range(match_line, max(0, match_line - 40), -1):
        line = lines[index - 1]
        if re.search(r"\b(?:def|async\s+def|function|async\s+function|class)\s+[A-Za-z_][A-Za-z0-9_]*|(?:app|router|server|api)\.(?:get|post|put|patch|delete|route)\s*\(", line):
            start = index
            break
    return start, end


def _message_bridge_span(lines: Sequence[str], match_line: int) -> tuple[int, int]:
    start = max(1, match_line - 16)
    end = min(len(lines), match_line + 32)
    for index in range(match_line, max(0, match_line - 60), -1):
        line = lines[index - 1]
        if re.search(r"\b(?:function|def|async\s+function|async\s+def|class)\s+[A-Za-z_][A-Za-z0-9_]*|exports\.[A-Za-z_][A-Za-z0-9_]*\s*=|[A-Za-z_][A-Za-z0-9_]*\.parse\s*=", line):
            start = index
            break
    return start, end
