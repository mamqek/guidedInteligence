from __future__ import annotations

import re
from typing import Sequence

from core.source_policy import SourceCategory


IDENTIFIER_PATTERN = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")
PATH_PATTERN = re.compile(
    r"\b(?:[\w.-]+/)+[\w.-]+\.(?:[A-Za-z0-9]+)\b|\b[\w.-]+\.(?:ts|tsx|js|jsx|py|java|go|rs|cs|cpp|c|h|json|md|txt)\b"
)
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "be",
    "by",
    "for",
    "from",
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "this",
    "to",
    "what",
    "with",
    "why",
}


def bounded_strings(values: object, *, limit: int) -> tuple[str, ...]:
    if not isinstance(values, list | tuple):
        return ()
    output: list[str] = []
    for item in values:
        value = str(item).strip()
        if not value:
            continue
        output.append(value)
        if len(output) >= limit:
            break
    return tuple(output)


def bounded_file_hints(values: object, *, limit: int) -> tuple[str, ...]:
    output: list[str] = []
    for value in bounded_strings(values, limit=limit * 2):
        if looks_like_absolute_path(value):
            continue
        normalized = value.replace("\\", "/").strip("/")
        if normalized:
            output.append(normalized)
        if len(output) >= limit:
            break
    return tuple(output)


def bounded_source_categories(values: object) -> tuple[SourceCategory, ...]:
    if not isinstance(values, list | tuple):
        return ()
    output: list[SourceCategory] = []
    for item in values:
        try:
            category = SourceCategory(str(item))
        except ValueError:
            continue
        if category not in output:
            output.append(category)
    return tuple(output)


def ordered_unique(values: Sequence[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        output.append(value)
    return tuple(output)


def merge_paths(values: object, narrowed_files: Sequence[str]) -> tuple[str, ...]:
    merged = list(narrowed_files)
    if isinstance(values, list | tuple):
        for item in values:
            normalized = str(item).replace("\\", "/").strip("/")
            if normalized and normalized not in merged:
                merged.append(normalized)
    return tuple(merged)


def source_ref_paths(values: Sequence[str]) -> tuple[str, ...]:
    output: list[str] = []
    for value in values:
        normalized = str(value).replace("\\", "/").strip("/")
        if normalized and "/" in normalized and ":" not in normalized.split("/", 1)[0]:
            output.append(normalized)
    return ordered_unique(output)


def looks_like_absolute_path(value: str) -> bool:
    normalized = value.replace("\\", "/")
    return normalized.startswith("/") or re.match(r"^[A-Za-z]:/", normalized) is not None


def is_query_token(token: str) -> bool:
    lowered = token.lower()
    return lowered not in STOPWORDS and (len(token) >= 3 or token in {"JS", "TS"})
