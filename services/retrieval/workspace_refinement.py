from __future__ import annotations

from typing import Any, Sequence


def candidate_refs(candidate: Any) -> tuple[str, ...]:
    refs: list[str] = []
    source_id = str(getattr(candidate, "source_id", "") or "").strip()
    path = str(getattr(candidate, "path", "") or "").strip().replace("\\", "/").strip("/")
    if source_id:
        refs.append(source_id)
    if path:
        refs.append(path)
    return tuple(dict.fromkeys(refs))


def accepted_anchor_paths(candidates: Sequence[Any], accepted_refs: Sequence[str]) -> tuple[str, ...]:
    accepted = {str(ref).strip() for ref in accepted_refs if str(ref).strip()}
    if not accepted:
        return ()
    paths: list[str] = []
    for candidate in candidates:
        candidate_path = str(getattr(candidate, "path", "") or "").strip().replace("\\", "/").strip("/")
        if not candidate_path:
            continue
        if any(ref in accepted for ref in candidate_refs(candidate)) and candidate_path not in paths:
            paths.append(candidate_path)
    return tuple(paths)


def filter_rejected_candidates(candidates: Sequence[Any], rejected_refs: Sequence[str]) -> tuple[Any, ...]:
    rejected = {str(ref).strip() for ref in rejected_refs if str(ref).strip()}
    if not rejected:
        return tuple(candidates)
    filtered: list[Any] = []
    for candidate in candidates:
        refs = candidate_refs(candidate)
        if any(ref in rejected for ref in refs):
            continue
        filtered.append(candidate)
    return tuple(filtered)


def no_new_accepted_anchors(previous_refs: Sequence[str], current_refs: Sequence[str]) -> bool:
    previous = {str(ref).strip() for ref in previous_refs if str(ref).strip()}
    current = {str(ref).strip() for ref in current_refs if str(ref).strip()}
    return current.issubset(previous)
