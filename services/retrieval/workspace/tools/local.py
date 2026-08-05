from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

from services.retrieval.workspace.bm25 import BM25Index, BM25SearchResult
from services.retrieval.workspace.tools.contracts import ToolObservation, ToolRequest, ToolSpec


IDENTIFIER_PATTERN = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")
DECLARATION_IDENTIFIER_PATTERN = re.compile(
    r"\b(?:class|interface|function|enum|type|module|namespace)\s+([A-Za-z_][A-Za-z0-9_]*)\b"
)
REPO_SKETCH_PATH_LIMIT = 40
REPO_SKETCH_DIR_LIMIT = 20
REPO_SKETCH_FILE_INDEX_LIMIT = 80
REPO_SKETCH_IDENTIFIERS_PER_FILE = 12
COMMON_PATH_PARTS = (
    "/src/",
    "/lib/",
    "/app/",
    "/packages/",
    "/pkg/",
    "/core/",
    "/compiler/",
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
    "with",
}


class BM25SearchTool:
    name = "bm25_search"

    def __init__(self, index: BM25Index) -> None:
        self.index = index

    def run(self, request: ToolRequest) -> ToolObservation:
        query = str(request.arguments.get("query", ""))
        limit = _bounded_int(request.arguments.get("limit"), default=12, minimum=1, maximum=50)
        path = _normalize_path(str(request.arguments.get("path", "")))
        paths = _normalized_paths(request.arguments.get("paths"))
        min_score = float(request.arguments.get("min_score", 0.0) or 0.0)
        needs_full_scan = bool(path or paths)
        results = self.index.search(query, limit=len(self.index.documents) if needs_full_scan else limit)
        if path:
            results = tuple(result for result in results if _normalize_path(result.chunk.path) == path)
        if paths:
            results = tuple(result for result in results if _normalize_path(result.chunk.path) in paths)
        if min_score > 0:
            results = tuple(result for result in results if result.score >= min_score)
        results = results[:limit]
        return ToolObservation(
            tool_name=self.name,
            status="ok",
            payload={
                "query": query,
                "path": path,
                "paths": list(paths),
                "results": [_bm25_result_to_payload(result) for result in results],
            },
            source_refs=tuple(result.chunk.chunk_id for result in results),
            metadata={
                "result_count": str(len(results)),
                "path_filter_count": str(len(paths)),
            },
        )


class OpenFileTool:
    name = "open_file"

    def __init__(self, index: BM25Index) -> None:
        self.index = index
        self._documents_by_path: dict[str, list[Any]] = defaultdict(list)
        for document in index.documents:
            self._documents_by_path[_normalize_path(document.chunk.path)].append(document)

    def run(self, request: ToolRequest) -> ToolObservation:
        path = _normalize_path(str(request.arguments.get("path", "")))
        if not path or _looks_like_absolute_path(path):
            return ToolObservation(
                tool_name=self.name,
                status="rejected",
                payload={"reason": "invalid_path", "path": path},
                metadata={"result_count": "0"},
            )
        documents = self._documents_by_path.get(path, [])
        if not documents:
            return ToolObservation(
                tool_name=self.name,
                status="missing",
                payload={"path": path, "snippets": []},
                metadata={"result_count": "0"},
            )
        line_start = _bounded_int(request.arguments.get("line_start"), default=1, minimum=1, maximum=1_000_000)
        line_count = _bounded_int(request.arguments.get("line_count"), default=80, minimum=1, maximum=120)
        line_end = line_start + line_count - 1
        snippets: list[dict[str, Any]] = []
        for document in documents:
            chunk = document.chunk
            if chunk.line_start is None or chunk.line_end is None:
                continue
            if chunk.line_end < line_start or chunk.line_start > line_end:
                continue
            snippets.append(_chunk_payload(chunk, score=1.0, matched_terms=()))
        return ToolObservation(
            tool_name=self.name,
            status="ok",
            payload={"path": path, "line_start": line_start, "line_end": line_end, "snippets": snippets[:4]},
            source_refs=tuple(snippet["chunk_id"] for snippet in snippets[:4]),
            metadata={"result_count": str(len(snippets[:4]))},
        )


def local_tool_specs() -> tuple[ToolSpec, ...]:
    return (
        ToolSpec(
            name="open_file",
            title="Open Indexed File Snippets",
            description=(
                "Open indexed snippets from a relative repository path. Use after another tool "
                "identifies a concrete file and nearby line range."
            ),
            arguments={
                "path": "Required relative repo path. Absolute paths are rejected.",
                "line_start": "Optional 1-based line number. Defaults to 1.",
                "line_count": "Optional integer from 1 to 120. Defaults to 80.",
            },
            examples=(
                {
                    "tool_name": "open_file",
                    "arguments": {"path": "src/compiler/checker.ts", "line_start": 1200, "line_count": 80},
                    "reason": "Inspect the checker code near a likely relevant location.",
                },
            ),
        ),
    )


def build_repo_sketch(index: BM25Index) -> dict[str, Any]:
    paths = sorted({document.chunk.path for document in index.documents})
    directory_counts: Counter[str] = Counter()
    extension_counts: Counter[str] = Counter()
    role_counts: Counter[str] = Counter()
    documents_by_path: dict[str, list[Any]] = defaultdict(list)

    for document in index.documents:
        documents_by_path[document.chunk.path].append(document)

    for path in paths:
        parts = Path(path).parts
        directory = "/".join(parts[:2]) if len(parts) >= 2 else (parts[0] if parts else "")
        if directory:
            directory_counts[directory] += 1
        suffix = Path(path).suffix.lower() or "<none>"
        extension_counts[suffix] += 1
        role_counts[file_role(path)] += 1

    return {
        "total_files": len(paths),
        "total_chunks": len(index.documents),
        "top_directories": [
            {"path": path, "file_count": count}
            for path, count in directory_counts.most_common(REPO_SKETCH_DIR_LIMIT)
        ],
        "file_roles": dict(sorted(role_counts.items())),
        "extensions": dict(extension_counts.most_common(20)),
        "representative_files": _representative_files(paths, REPO_SKETCH_PATH_LIMIT),
        "file_index": _repo_sketch_file_index(documents_by_path, REPO_SKETCH_FILE_INDEX_LIMIT),
    }


def file_role(path: str) -> str:
    normalized_path = path.lower().replace("\\", "/")
    normalized = f"/{normalized_path}"
    parts = tuple(part for part in normalized.split("/") if part)
    name = parts[-1] if parts else ""
    suffix = Path(name).suffix.lower()

    if suffix in {".md", ".rst", ".adoc"} or "docs" in parts or "documentation" in parts:
        return "documentation"
    if (
        "bin" in parts
        or normalized.startswith("/bin/")
        or "baseline" in normalized
        or "baselines" in parts
        or "snapshot" in normalized
        or "snapshots" in parts
        or "golden" in normalized
        or "generated" in normalized
        or name.endswith(".generated.ts")
        or name.endswith(".generated.js")
    ):
        return "baseline_or_generated"
    if (
        "test" in parts
        or "tests" in parts
        or "__tests__" in parts
        or "spec" in parts
        or "fixtures" in parts
        or name.endswith(".test.ts")
        or name.endswith(".spec.ts")
        or name.endswith(".test.js")
        or name.endswith(".spec.js")
    ):
        return "test"
    if any(part in normalized for part in COMMON_PATH_PARTS):
        return "implementation"
    return "other"


def _bm25_result_to_payload(result: BM25SearchResult) -> dict[str, Any]:
    return _chunk_payload(result.chunk, score=result.score, matched_terms=result.matched_terms)


def _chunk_payload(chunk: Any, *, score: float, matched_terms: Sequence[str]) -> dict[str, Any]:
    line_range = (
        f"L{chunk.line_start}-L{chunk.line_end}"
        if chunk.line_start is not None and chunk.line_end is not None
        else ""
    )
    return {
        "chunk_id": chunk.chunk_id,
        "source_category": chunk.source_category.value,
        "snapshot": chunk.snapshot,
        "commit": chunk.commit,
        "path": chunk.path,
        "line_start": chunk.line_start,
        "line_end": chunk.line_end,
        "line_range": line_range,
        "text": chunk.text,
        "score": score,
        "matched_terms": list(matched_terms),
        "visibility": chunk.metadata.get("visibility", ""),
        "case_id": chunk.metadata.get("case_id", ""),
    }


def _build_file_entries(index: BM25Index) -> tuple[dict[str, Any], ...]:
    documents_by_path: dict[str, list[Any]] = defaultdict(list)
    for document in index.documents:
        documents_by_path[document.chunk.path].append(document)
    return tuple(_file_entry(path, documents) for path, documents in sorted(documents_by_path.items()))


def _file_entry(path: str, documents: Sequence[Any]) -> dict[str, Any]:
    path_obj = Path(path)
    identifiers = _file_index_identifiers(path, documents, limit=24)
    return {
        "path": path,
        "basename": path_obj.name,
        "directory": path_obj.parent.as_posix() if str(path_obj.parent) != "." else "",
        "extension": path_obj.suffix.lower() or "<none>",
        "role": file_role(path),
        "identifiers": list(identifiers),
    }


def _repo_sketch_file_index(
    documents_by_path: Mapping[str, Sequence[Any]],
    limit: int,
) -> tuple[dict[str, Any], ...]:
    paths = sorted(
        documents_by_path,
        key=lambda path: (_file_role_sort_key(file_role(path)), path),
    )
    return tuple(_file_entry(path, documents_by_path[path]) for path in paths[:limit])


def _file_index_identifiers(path: str, documents: Sequence[Any], *, limit: int) -> tuple[str, ...]:
    candidates: list[str] = []
    for token in _identifier_tokens(path.replace("/", " ").replace(".", " ")):
        if _is_query_token(token):
            candidates.append(token)
    for document in documents:
        for match in DECLARATION_IDENTIFIER_PATTERN.finditer(document.chunk.text):
            token = match.group(1)
            if _is_query_token(token):
                candidates.append(token)
        if len(_ordered_unique(candidates)) >= limit:
            break
    return _ordered_unique(candidates)[:limit]


def _representative_files(paths: Sequence[str], limit: int) -> tuple[str, ...]:
    selected: list[str] = []
    seen_roles: set[str] = set()
    for path in paths:
        role = file_role(path)
        if role in seen_roles:
            continue
        seen_roles.add(role)
        selected.append(path)
        if len(selected) >= limit:
            return tuple(selected)

    for path in paths:
        if path in selected:
            continue
        selected.append(path)
        if len(selected) >= limit:
            break
    return tuple(selected)


def _identifier_tokens(text: str) -> tuple[str, ...]:
    return tuple(IDENTIFIER_PATTERN.findall(text))


def _is_query_token(token: str) -> bool:
    lowered = token.lower()
    if lowered in STOPWORDS:
        return False
    if len(token) < 3 and token not in {"JS", "TS"}:
        return False
    return True


def _ordered_unique(values: Sequence[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        output.append(value)
    return tuple(output)


def _file_role_sort_key(role: str) -> int:
    order = {
        "implementation": 0,
        "other": 1,
        "test": 2,
        "documentation": 3,
        "baseline_or_generated": 4,
    }
    return order.get(role, 5)


def _normalize_path(value: str) -> str:
    normalized = value.strip().replace("\\", "/")
    normalized = re.sub(r"/+", "/", normalized)
    return normalized.strip("/")


def _looks_like_absolute_path(value: str) -> bool:
    normalized = value.replace("\\", "/")
    return normalized.startswith("/") or re.match(r"^[A-Za-z]:/", normalized) is not None


def _bounded_int(value: object, *, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def _normalized_paths(value: object) -> tuple[str, ...]:
    if not isinstance(value, list | tuple):
        return ()
    output: list[str] = []
    seen: set[str] = set()
    for item in value:
        normalized = _normalize_path(str(item))
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        output.append(normalized)
    return tuple(output)
