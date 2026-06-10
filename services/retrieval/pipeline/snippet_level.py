from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from services.retrieval.pipeline.constants import MAX_EVIDENCE_ITEMS, MAX_ROLE_FILE_REFINE_QUERIES
from services.retrieval.pipeline.file_level import (
    DECLARATION_PATTERN,
    candidate_rank_key,
    looks_like_source_file,
    role_owner_context_terms,
)
from services.retrieval.pipeline.models import RetrievalCandidate, RoleCandidateEvaluation
from services.retrieval.step2 import WorkspaceRetrievalPlan
from services.retrieval.step2.common import ordered_unique


def role_snippet_queries(role: str, *, query: str, helper_queries: Sequence[str]) -> tuple[str, ...]:
    queries = [query.strip()]
    role_specific = {
        "representation": (
            "class declaration interface symbol flags",
            "ast node method declaration type representation",
        ),
        "input_parsing": (
            "parse declaration syntaxkind modifier keyword",
            "parseexpected createnode parser declaration",
        ),
        "validation_checking": (
            "check diagnostics error cannot must enforce",
            "checker semantic constraint implementation instantiate",
        ),
        "diagnostics": (
            "diagnostics error message grammarerror",
            "report error diagnostics message",
        ),
        "behavior_output": (
            "emit transform runtime output",
            "compile time behavior runtime prevent",
        ),
    }
    queries.extend(role_specific.get(role, ()))
    queries.extend(helper_queries[:2])
    return ordered_unique(value for value in queries if value and value.strip())


def best_direct_owner_span(*, role: str, query: str, lines: Sequence[str], search_terms: Sequence[str] = ()) -> tuple[int, int]:
    line_start, line_end, score = best_in_file_refinement_span(
        role=role,
        query=query,
        helper_queries=(),
        search_terms=search_terms,
        lines=lines,
    )
    if score > 0:
        return line_start, line_end
    window_size = 80
    step = 40
    preferred_line = preferred_direct_owner_line(role=role, query=query, lines=lines)
    if preferred_line is not None:
        line_start = max(1, preferred_line - 20)
        return line_start, min(len(lines), line_start + window_size - 1)
    query_terms = set(tokenize_for_direct_owner_query(query))
    query_terms.update(term.lower() for term in role_owner_context_terms(role))
    query_terms.update(direct_owner_bonus_terms(role))
    best_score = -1.0
    best_start = 1
    total = len(lines)
    for start_index in range(0, total, step):
        end_index = min(total, start_index + window_size)
        text = "\n".join(lines[start_index:end_index]).lower()
        score = float(sum(1 for term in query_terms if term and term in text))
        score += direct_owner_window_bonus(role, text)
        if score > best_score:
            best_score = score
            best_start = start_index + 1
        if end_index >= total:
            break
    return best_start, min(total, best_start + window_size - 1)


def best_in_file_refinement_span(
    *,
    role: str,
    query: str,
    helper_queries: Sequence[str],
    search_terms: Sequence[str],
    lines: Sequence[str],
) -> tuple[int, int, float]:
    window_size = 80
    query_text = " ".join([query, *helper_queries, *search_terms])
    terms = in_file_refinement_terms(role=role, query_text=query_text)
    if not terms:
        return 1, min(len(lines), window_size), 0.0

    best_score = -1.0
    best_start = 1
    seen_starts: set[int] = set()
    for start in in_file_candidate_window_starts(lines, terms=terms, window_size=window_size):
        if start in seen_starts:
            continue
        seen_starts.add(start)
        end = min(len(lines), start + window_size - 1)
        text = "\n".join(lines[start - 1 : end])
        score = score_in_file_window(role=role, query_text=query_text, text=text, start_line=start)
        if score > best_score:
            best_score = score
            best_start = start
    return best_start, min(len(lines), best_start + window_size - 1), max(best_score, 0.0)


def in_file_candidate_window_starts(lines: Sequence[str], *, terms: Sequence[str], window_size: int) -> tuple[int, ...]:
    starts: list[int] = []
    total = len(lines)
    step = max(20, window_size // 2)
    for index in range(0, total, step):
        starts.append(index + 1)
        if index + window_size >= total:
            break
    for index, line in enumerate(lines, start=1):
        lowered = line.lower()
        is_declaration = bool(DECLARATION_PATTERN.search(line)) or re.search(r"\bfunction\s+[A-Za-z_][A-Za-z0-9_]*\b", line)
        if is_declaration or any(term in lowered for term in terms[:18]):
            starts.append(max(1, index - 20))
    return tuple(ordered_unique(starts))


def in_file_refinement_terms(*, role: str, query_text: str) -> tuple[str, ...]:
    terms = list(tokenize_for_direct_owner_query(query_text))
    terms.extend(term.lower() for term in role_owner_context_terms(role))
    terms.extend(direct_owner_bonus_terms(role))
    terms.extend(
        {
            "validation_checking": (
                "check",
                "error",
                "diagnostics",
                "assignable",
                "implements",
                "extends",
                "base",
                "constructor",
                "construct",
                "call",
                "property",
                "method",
                "declaration",
            ),
            "input_parsing": ("parse", "modifier", "keyword", "token", "declaration", "member"),
            "representation": ("flags", "symbol", "declaration", "type", "interface", "enum", "modifier"),
            "diagnostics": ("diagnostics", "message", "error", "code"),
            "behavior_output": ("emit", "transform", "output", "runtime"),
        }.get(role, ())
    )
    return tuple(ordered_unique(term.lower() for term in terms if len(term) >= 3))


def score_in_file_window(
    *,
    role: str,
    query_text: str,
    text: str,
    start_line: int,
) -> float:
    lowered = text.lower()
    query_lowered = query_text.lower()
    terms = in_file_refinement_terms(role=role, query_text=query_text)
    score = 0.0
    for term in terms:
        if term in lowered:
            score += 1.0
            score += min(lowered.count(term), 4) * 0.2
    for phrase in important_query_phrases(query_text):
        if phrase in lowered:
            score += 3.0
    score += direct_owner_window_bonus(role, lowered)
    score += declaration_anchor_bonus(role=role, query_text=query_lowered, text=text)
    score -= min(start_line / 10000.0, 0.6)
    return score


def important_query_phrases(query_text: str) -> tuple[str, ...]:
    phrases: list[str] = []
    for raw_phrase in re.findall(r"`([^`]+)`|'([^']+)'|\"([^\"]+)\"", query_text):
        phrase = next((item for item in raw_phrase if item), "")
        normalized = re.sub(r"\s+", " ", phrase.strip().lower())
        if len(normalized) >= 5:
            phrases.append(normalized)
    for phrase in re.findall(r"\b(?:cannot|must|only|incorrectly|extends|implements)\s+[a-z0-9_ .-]{4,80}", query_text.lower()):
        phrases.append(re.sub(r"\s+", " ", phrase.strip()))
    return tuple(ordered_unique(phrases[:12]))


def declaration_anchor_bonus(*, role: str, query_text: str, text: str) -> float:
    bonus = 0.0
    declarations = [match.group(0).lower() for match in re.finditer(r"\b(?:function|class|interface|enum|type)\s+[A-Za-z_][A-Za-z0-9_]*", text)]
    if not declarations:
        return bonus
    query_wants_class = any(term in query_text for term in ("class", "base", "extends", "implements", "constructor"))
    query_wants_super = "super" in query_text
    query_wants_diagnostics = any(term in query_text for term in ("diagnostic", "error", "cannot", "must"))
    for declaration in declarations:
        if role == "validation_checking" and declaration.startswith("function check"):
            bonus += 4.0
            if query_wants_class and "class" in declaration:
                bonus += 8.0
            if query_wants_super and "super" in declaration:
                bonus += 5.0
            if query_wants_diagnostics:
                bonus += 1.5
        elif role == "input_parsing" and declaration.startswith("function parse"):
            bonus += 5.0
        elif role == "representation" and any(kind in declaration for kind in ("interface", "enum", "type")):
            bonus += 4.0
        elif role == "behavior_output" and declaration.startswith("function emit"):
            bonus += 4.0
    return bonus


def preferred_direct_owner_line(*, role: str, query: str, lines: Sequence[str]) -> int | None:
    if role != "validation_checking":
        return None
    lowered_query = query.lower()
    wants_class_layer = any(term in lowered_query for term in ("class", "inherit", "extends", "base", "implement"))
    wants_super_layer = "super" in lowered_query
    if wants_class_layer:
        for index, line in enumerate(lines, start=1):
            lowered = line.lower()
            if "classdeclaration" in lowered and any(term in lowered for term in ("basetype", "basetypes", "extends")):
                return index
        for index, line in enumerate(lines, start=1):
            lowered = line.lower()
            if "getdeclaredtypeofclass" in lowered or ("classdeclaration" in lowered and "declaration" in lowered):
                return index
    if wants_super_layer:
        for index, line in enumerate(lines, start=1):
            if "superkeyword" in line.lower():
                return index
    return None


def read_owner_text_file(path: Path) -> str | None:
    for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1", "utf-16", "utf-16-le", "utf-16-be"):
        try:
            text = path.read_text(encoding=encoding)
        except UnicodeError:
            continue
        if looks_like_bad_text_decode(text):
            continue
        return text
    return None


def looks_like_bad_text_decode(text: str) -> bool:
    nul_count = text.count("\x00")
    return nul_count > max(1, len(text) // 200)


def tokenize_for_direct_owner_query(query: str) -> tuple[str, ...]:
    return tuple(term for term in re.findall(r"[A-Za-z_][A-Za-z0-9_]{3,}", query.lower()) if term not in {"where", "find", "search", "like", "with", "that", "this", "from"})


def direct_owner_bonus_terms(role: str) -> set[str]:
    if role == "validation_checking":
        return {
            "classdeclaration",
            "basetype",
            "basetypes",
            "getbasetypes",
            "getdeclaredtypeofclass",
            "getpropertiesoftype",
            "getsignaturesoftype",
            "diagnostics",
            "error",
            "superkeyword",
            "construct",
            "instantiate",
        }
    if role == "input_parsing":
        return {"parse", "syntaxkind", "modifier", "keyword", "token", "classdeclaration", "classmember", "parseandcheckmodifiers"}
    if role == "representation":
        return {"interface", "enum", "nodeflags", "symbolflags", "declaration", "classdeclaration", "methoddeclaration"}
    if role == "diagnostics":
        return {"diagnostics", "message", "error", "code"}
    if role == "behavior_output":
        return {"emit", "runtime", "transform", "output", "directive", "emitclass", "classdeclaration", "emitmember"}
    return set()


def direct_owner_window_bonus(role: str, text: str) -> float:
    if role == "validation_checking":
        score = 0.0
        if "function checkclassdeclaration" in text:
            score += 24.0
        if "function checkinterfacedeclaration" in text:
            score += 10.0
        if "case syntaxkind.classdeclaration" in text and "checkclassdeclaration" in text:
            score += 8.0
        if "classdeclaration" in text and ("basetype" in text or "basetypes" in text):
            score += 6.0
        if "diagnostics." in text or "error(" in text:
            score += 3.0
        if "getdeclaredtypeofclass" in text or "getpropertiesoftype" in text:
            score += 2.0
        if "superkeyword" in text:
            score += 2.0
            if "function checkclassdeclaration" not in text:
                score -= 4.0
        return score
    if role == "input_parsing":
        score = 0.0
        if "function parseandcheckmodifiers" in text:
            score += 68.0
        if "function parseclassmemberdeclaration" in text:
            score += 12.0
        if "function parseclassdeclaration" in text:
            score += 10.0
        if "parseclassdeclaration" in text or "parseclassmemberdeclaration" in text:
            score += 8.0
        if "parseandcheckmodifiers" in text or ("modifier" in text and "syntaxkind" in text):
            score += 5.0
        if "case syntaxkind." in text and "function parseclass" not in text:
            score -= 8.0
        if any(token in text for token in ("parseparenthesizedexpression", "parsevariablestatement", "parsewithstatement")) and "class" not in text:
            score -= 4.0
        return score
    if role == "representation":
        score = 0.0
        if "export enum nodeflags" in text:
            score += 24.0
        if "interface node" in text and "flags: nodeflags" in text:
            score += 18.0
        if "interface classdeclaration" in text:
            score += 18.0
        if "interface methoddeclaration" in text:
            score += 14.0
        if "nodeflags" in text or "symbolflags" in text:
            score += 6.0
        if "classdeclaration" in text or "methoddeclaration" in text:
            score += 4.0
        if ("interface nodelinks" in text or "enum typeflags" in text or "interface type" in text) and "nodeflags" not in text:
            score -= 10.0
        return score
    if role == "behavior_output":
        score = 0.0
        if "function emitclassdeclaration" in text:
            score += 28.0
        if "function emitmemberfunctions" in text or "function emitclassmembers" in text:
            score += 20.0
        if "function emitmemberassignments" in text:
            score += 10.0
        if "emitclassdeclaration" in text or "emitmemberfunctions" in text or "emitclassmembers" in text:
            score += 8.0
        if "classdeclaration" in text and "emit" in text:
            score += 5.0
        if "case syntaxkind." in text and "function emitclassdeclaration" not in text:
            score -= 8.0
        if "function emitmoduledeclaration" in text and "classdeclaration" not in text:
            score -= 6.0
        if any(token in text for token in ("emitthrowstatement", "emittrystatement", "emitcatchclause")) and "class" not in text:
            score -= 5.0
        return score
    return 0.0


def role_followup_queries(
    role: str,
    *,
    query: str,
    helper_queries: Sequence[str],
    candidate_path: str,
    candidate_text: str,
) -> tuple[str, ...]:
    queries: list[str] = []
    followup_specific = {
        "representation": (
            "nodeflags modifier syntaxkind classdeclaration methoddeclaration",
            "symbolflags declaration interface class method",
        ),
        "input_parsing": (
            "parse declaration modifier syntaxkind keyword",
            "parseclassdeclaration parseclassmemberdeclaration parseandcheckmodifiers",
        ),
        "validation_checking": (
            "check abstract instantiate implement diagnostics",
            "cannot must enforce semantic error abstract",
        ),
        "diagnostics": (
            "diagnostics grammarerror error message abstract",
            "report error diagnostics instantiate super abstract",
        ),
        "behavior_output": (
            "emit class declaration method modifier output",
            "emitclassdeclaration emitmemberfunctions emit class members",
        ),
    }
    queries.extend(followup_specific.get(role, ()))
    queries.extend(role_snippet_queries(role, query=query, helper_queries=helper_queries)[1:])
    for token in DECLARATION_PATTERN.findall(candidate_text):
        if len(token) >= 5:
            queries.append(token)
    stem = Path(candidate_path).stem.lower() if candidate_path else ""
    if stem:
        queries.append(stem)
    queries.append(query.strip())
    return ordered_unique(value for value in queries if value and value.strip())


def in_file_search_terms(
    retrieval_plan: WorkspaceRetrievalPlan,
    role: str,
    query: str,
    helper_queries: Sequence[str],
) -> tuple[str, ...]:
    role_queries = [subquery.query for subquery in retrieval_plan.llm_subqueries if subquery.role == role]
    return tuple(
        ordered_unique(
            [
                query,
                *helper_queries,
                *role_queries,
                *retrieval_plan.retrieval_terms,
                *retrieval_plan.raw_prompt_evidence,
                *retrieval_plan.grounded_entities,
                *retrieval_plan.confirmed_entities,
                retrieval_plan.prompt_summary,
            ]
        )
    )


def latest_evaluation_for_ref(
    evaluations: Sequence[RoleCandidateEvaluation],
    ref: str,
) -> RoleCandidateEvaluation | None:
    latest: RoleCandidateEvaluation | None = None
    for evaluation in evaluations:
        if evaluation.candidate.source_id == ref:
            latest = evaluation
    return latest


def is_file_candidate(candidate: RetrievalCandidate) -> bool:
    return candidate.metadata.get("file_candidate") == "true" or str(candidate.line_range or "").upper() == "FILE"


def drop_redundant_file_candidates(candidates: Sequence[RetrievalCandidate]) -> tuple[RetrievalCandidate, ...]:
    if not candidates:
        return ()
    if not any(is_file_candidate(candidate) for candidate in candidates):
        return tuple(candidates)
    non_file_candidates = [candidate for candidate in candidates if not is_file_candidate(candidate)]
    if not non_file_candidates:
        return tuple(candidates)
    non_file_paths = {candidate.path for candidate in non_file_candidates if candidate.path}
    return tuple(
        candidate
        for candidate in candidates
        if not is_file_candidate(candidate) or (candidate.path and candidate.path not in non_file_paths)
    )


def snippet_quality_for_ref(ref: str, assessments: Sequence[Mapping[str, str]]) -> str:
    for item in assessments:
        if str(item.get("ref", "")) == ref:
            role = str(item.get("role", "")).strip().lower()
            if role:
                return role
    return ""


def snippet_reason_for_ref(ref: str, assessments: Sequence[Mapping[str, str]]) -> str:
    for item in assessments:
        if str(item.get("ref", "")) == ref:
            return str(item.get("reason", "")).strip()
    return ""


def late_snippet_quality(
    *,
    ref: str,
    quality_by_ref: Mapping[str, str],
    rejected_refs: set[str],
    accepted_refs: set[str],
) -> str:
    if ref in rejected_refs:
        return "noise"
    quality = quality_by_ref.get(ref, "").strip().lower()
    if quality in {"core", "secondary", "noise"}:
        return quality
    if ref in accepted_refs:
        return "core"
    return "secondary"


def followup_snippet_quality(
    *,
    role: str,
    candidate: RetrievalCandidate,
    rescued_refs: set[str],
    existing_assessment: Sequence[Mapping[str, str]],
) -> str:
    if candidate.source_id not in rescued_refs:
        return snippet_quality_for_ref(candidate.source_id, existing_assessment)
    if role == "validation_checking":
        text = candidate.text.lower()
        if any(token in text for token in ("cannot", "must", "instantiate", "implement", "super", "diagnostic", "semantic", "extends", "check")):
            return "core"
    if role == "input_parsing":
        text = candidate.text.lower()
        if any(token in text for token in ("parseclass", "parseandcheckmodifiers", "modifier", "syntaxkind", "keyword")):
            return "core"
    if role == "behavior_output":
        text = candidate.text.lower()
        if any(token in text for token in ("emit", "transform", "runtime", "output")):
            return "core"
    return "secondary"


def merge_retrieved_candidates(
    existing: Sequence[RetrievalCandidate],
    new_candidates: Sequence[RetrievalCandidate],
) -> tuple[RetrievalCandidate, ...]:
    merged: dict[str, RetrievalCandidate] = {candidate.source_id: candidate for candidate in existing}
    for candidate in new_candidates:
        merged[candidate.source_id] = candidate
    return tuple(merged.values())


def planning_snippets(candidates: Sequence[RetrievalCandidate]) -> tuple[dict[str, Any], ...]:
    snippets: list[dict[str, Any]] = []
    for candidate in list(candidates)[:MAX_EVIDENCE_ITEMS]:
        snippets.append(
            {
                "ref": candidate.source_id or (candidate.path or ""),
                "path": candidate.path or "",
                "line_range": candidate.line_range or "",
                "retrieval_path": candidate.retrieval_path,
                "file_role": candidate.metadata.get("file_role", ""),
                "score": candidate.score,
                "snippet": salient_candidate_excerpt(candidate, limit=900),
            }
        )
    return tuple(snippets)


def salient_candidate_excerpt(candidate: RetrievalCandidate, *, limit: int) -> str:
    text = candidate.text
    if len(text) <= limit:
        return text
    role = candidate.metadata.get("coverage_area", "")
    terms = in_file_refinement_terms(role=role, query_text=text)
    lines = text.splitlines()
    best_index = 0
    best_score = -1.0
    for index, line in enumerate(lines):
        lowered = line.lower()
        score = 0.0
        if DECLARATION_PATTERN.search(line) or re.search(r"\bfunction\s+[A-Za-z_][A-Za-z0-9_]*\b", line):
            score += 5.0
        score += sum(1.0 for term in terms[:24] if term in lowered)
        if role == "validation_checking" and re.search(r"\bfunction\s+check", lowered):
            score += 6.0
            if "class" in lowered:
                score += 12.0
            if any(term in lowered for term in ("base", "implement", "inherit", "extends", "super", "construct")):
                score += 4.0
        if score > best_score:
            best_score = score
            best_index = index
    selected: list[str] = []
    char_count = 0
    start = max(0, best_index - 8)
    for line in lines[start:]:
        if selected and char_count + len(line) + 1 > limit:
            break
        selected.append(line)
        char_count += len(line) + 1
    excerpt = "\n".join(selected).strip()
    if not excerpt:
        return text[:limit]
    if start > 0:
        excerpt = "...\n" + excerpt
    return excerpt
