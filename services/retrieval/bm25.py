from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from core.source_policy import SourceCategory


TOKEN_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|[0-9]+")
DECLARATION_START_PATTERN = re.compile(
    r"^\s*(?:export\s+)?(?:default\s+)?(?:declare\s+)?(?:async\s+)?(?:abstract\s+)?"
    r"(?:class|interface|enum|namespace|module|type|function)\b"
)
DECLARATION_SYMBOL_PATTERN = re.compile(
    r"\b(?:class|interface|enum|namespace|module|type|function)\s+([A-Za-z_][A-Za-z0-9_]*)\b"
)
DEFAULT_EXCLUDED_PATHS = (
    ".git",
    ".guided-intelligence",
    ".codegraphcontext",
    ".venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    ".cache",
    "coverage",
)
TEXT_EXTENSIONS = {
    ".c",
    ".cc",
    ".cpp",
    ".cs",
    ".css",
    ".go",
    ".h",
    ".hpp",
    ".html",
    ".java",
    ".js",
    ".json",
    ".jsx",
    ".md",
    ".py",
    ".rs",
    ".tsx",
    ".ts",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
DOCUMENTATION_EXTENSIONS = {".md", ".txt"}


@dataclass(frozen=True)
class IndexedChunk:
    chunk_id: str
    source_category: SourceCategory
    snapshot: str
    commit: str
    path: str
    line_start: int | None
    line_end: int | None
    text: str
    symbols: tuple[str, ...]
    metadata: Mapping[str, str]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["source_category"] = self.source_category.value
        data["metadata"] = dict(self.metadata)
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "IndexedChunk":
        return cls(
            chunk_id=str(data["chunk_id"]),
            source_category=SourceCategory(str(data["source_category"])),
            snapshot=str(data["snapshot"]),
            commit=str(data["commit"]),
            path=str(data["path"]),
            line_start=data.get("line_start"),
            line_end=data.get("line_end"),
            text=str(data["text"]),
            symbols=tuple(str(item) for item in data.get("symbols", ())),
            metadata={str(key): str(value) for key, value in dict(data.get("metadata", {})).items()},
        )


@dataclass(frozen=True)
class BM25Document:
    chunk: IndexedChunk
    tokens: tuple[str, ...]


@dataclass(frozen=True)
class BM25SearchResult:
    chunk: IndexedChunk
    score: float
    matched_terms: tuple[str, ...]


@dataclass(frozen=True)
class BM25Index:
    documents: tuple[BM25Document, ...]
    average_document_length: float
    document_frequency: Mapping[str, int]

    def search(self, query: str, *, limit: int = 20) -> tuple[BM25SearchResult, ...]:
        query_terms = tuple(tokenize(query))
        if not query_terms or not self.documents:
            return ()

        query_counts = Counter(query_terms)
        results: list[BM25SearchResult] = []
        document_count = len(self.documents)
        k1 = 1.5
        b = 0.75

        for document in self.documents:
            frequencies = Counter(document.tokens)
            document_length = len(document.tokens)
            score = 0.0
            matched_terms: list[str] = []
            for term in query_counts:
                frequency = frequencies.get(term, 0)
                if frequency == 0:
                    continue
                matched_terms.append(term)
                doc_frequency = self.document_frequency.get(term, 0)
                idf = math.log(1 + (document_count - doc_frequency + 0.5) / (doc_frequency + 0.5))
                denominator = frequency + k1 * (
                    1 - b + b * document_length / max(self.average_document_length, 1.0)
                )
                score += idf * (frequency * (k1 + 1)) / denominator

            if score > 0:
                results.append(
                    BM25SearchResult(
                        chunk=document.chunk,
                        score=score,
                        matched_terms=tuple(sorted(set(matched_terms))),
                    )
                )

        return tuple(sorted(results, key=lambda result: result.score, reverse=True)[:limit])

    def to_dict(self) -> dict[str, Any]:
        return {
            "average_document_length": self.average_document_length,
            "document_frequency": dict(self.document_frequency),
            "documents": [
                {"chunk": document.chunk.to_dict(), "tokens": list(document.tokens)}
                for document in self.documents
            ],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "BM25Index":
        return cls(
            average_document_length=float(data["average_document_length"]),
            document_frequency={str(key): int(value) for key, value in data["document_frequency"].items()},
            documents=tuple(
                BM25Document(
                    chunk=IndexedChunk.from_dict(item["chunk"]),
                    tokens=tuple(str(token) for token in item["tokens"]),
                )
                for item in data["documents"]
            ),
        )


def tokenize(text: str) -> list[str]:
    return [match.group(0).lower() for match in TOKEN_PATTERN.finditer(text)]


def build_index_from_repo(
    *,
    repo_path: str | Path,
    commit: str,
    chunk_line_count: int = 40,
    chunk_line_overlap: int = 10,
    snapshot: str = "pre_resolution",
    visibility: str = "visible_initial",
    origin: str = "repo_index",
    exclude_paths: tuple[str, ...] | None = None,
) -> BM25Index:
    root = Path(repo_path).resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError(f"repo-pre path does not exist or is not a directory: {root}")
    if chunk_line_count <= 0:
        raise ValueError("chunk_line_count must be greater than zero.")
    if chunk_line_overlap < 0:
        raise ValueError("chunk_line_overlap must be zero or greater.")
    if chunk_line_overlap >= chunk_line_count:
        raise ValueError("chunk_line_overlap must be smaller than chunk_line_count.")

    chunks: list[IndexedChunk] = []
    for file_path in sorted(_iter_source_files(root, exclude_paths=exclude_paths)):
        relative_path = file_path.relative_to(root).as_posix()
        text = _read_text_file(file_path)
        if text is None:
            continue
        chunks.extend(
            _build_chunks_for_file(
                relative_path=relative_path,
                text=text,
                commit=commit,
                snapshot=snapshot,
                visibility=visibility,
                origin=origin,
                chunk_line_count=chunk_line_count,
                chunk_line_overlap=chunk_line_overlap,
            )
        )

    documents = tuple(
        BM25Document(chunk=chunk, tokens=tuple(tokenize(_document_text(chunk)))) for chunk in chunks
    )
    document_frequency: dict[str, int] = {}
    for document in documents:
        for token in set(document.tokens):
            document_frequency[token] = document_frequency.get(token, 0) + 1
    average_document_length = (
        sum(len(document.tokens) for document in documents) / len(documents) if documents else 0.0
    )
    return BM25Index(
        documents=documents,
        average_document_length=average_document_length,
        document_frequency=document_frequency,
    )


def estimate_indexing_scope(
    repo_path: str | Path,
    *,
    exclude_paths: tuple[str, ...] | None = None,
    chunk_line_count: int = 40,
    chunk_line_overlap: int = 10,
) -> dict[str, Any]:
    root = Path(repo_path).resolve()
    if not root.exists() or not root.is_dir():
        return {"file_count": 0, "total_bytes": 0, "estimated_chunks": 0, "sample_paths": []}
    if chunk_line_count <= 0:
        raise ValueError("chunk_line_count must be greater than zero.")
    if chunk_line_overlap < 0:
        raise ValueError("chunk_line_overlap must be zero or greater.")
    if chunk_line_overlap >= chunk_line_count:
        raise ValueError("chunk_line_overlap must be smaller than chunk_line_count.")
    files = tuple(sorted(_iter_source_files(root, exclude_paths=exclude_paths)))
    total_bytes = 0
    estimated_chunks = 0
    for path in files:
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        total_bytes += size
        text = _read_text_file(path)
        if text is None:
            continue
        estimated_chunks += _estimate_chunk_count_for_text(
            text,
            chunk_line_count=chunk_line_count,
            chunk_line_overlap=chunk_line_overlap,
        )
    return {
        "file_count": len(files),
        "total_bytes": total_bytes,
        "estimated_chunks": estimated_chunks,
        "sample_paths": [path.relative_to(root).as_posix() for path in files[:20]],
    }


def save_index(index: BM25Index, index_dir: str | Path) -> None:
    path = Path(index_dir)
    path.mkdir(parents=True, exist_ok=True)
    (path / "bm25-index.json").write_text(
        json.dumps(index.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )


def load_index(index_dir: str | Path) -> BM25Index:
    index_path = Path(index_dir) / "bm25-index.json"
    if not index_path.exists():
        raise FileNotFoundError(f"Missing BM25 index: {index_path}")
    return BM25Index.from_dict(json.loads(index_path.read_text(encoding="utf-8")))


def _document_text(chunk: IndexedChunk) -> str:
    basename = Path(chunk.path).name
    return f"{chunk.path}\n{basename}\n{chunk.text}"


def _iter_source_files(
    root: Path,
    *,
    exclude_paths: tuple[str, ...] | None = None,
) -> Iterable[Path]:
    effective_exclude_paths = DEFAULT_EXCLUDED_PATHS if exclude_paths is None else exclude_paths
    exclude_prefixes = _normalize_scope_paths(effective_exclude_paths)
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative_path = path.relative_to(root).as_posix()
        if _matches_scope(relative_path, exclude_prefixes):
            continue
        if path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        if _should_skip_indexing(relative_path):
            continue
        yield path


def _normalize_scope_paths(values: tuple[str, ...]) -> tuple[str, ...]:
    normalized: list[str] = []
    for value in values:
        item = value.strip().replace("\\", "/").strip("/")
        if not item or item == ".":
            continue
        if item not in normalized:
            normalized.append(item)
    return tuple(normalized)


def _matches_scope(relative_path: str, prefixes: tuple[str, ...]) -> bool:
    normalized = relative_path.replace("\\", "/").strip("/")
    for prefix in prefixes:
        if normalized == prefix or normalized.startswith(prefix.rstrip("/") + "/"):
            return True
    return False


def _build_chunks_for_file(
    *,
    relative_path: str,
    text: str,
    commit: str,
    snapshot: str,
    visibility: str,
    origin: str,
    chunk_line_count: int,
    chunk_line_overlap: int,
) -> list[IndexedChunk]:
    lines = text.splitlines()
    if not lines:
        return []
    source_category = _classify_source_category(relative_path)
    metadata = {
        "file_role": _file_role(relative_path),
        "visibility": visibility,
        "origin": origin,
    }
    spans = _structure_aware_spans(lines, chunk_line_count=chunk_line_count)
    chunks: list[IndexedChunk] = []
    for start, end in spans:
        span_lines = lines[start:end]
        symbol_names = tuple(_extract_chunk_symbols(span_lines))
        chunks.extend(
            _subdivide_span(
                relative_path=relative_path,
                source_category=source_category,
                commit=commit,
                snapshot=snapshot,
                metadata=metadata,
                lines=lines,
                start=start,
                end=end,
                chunk_line_count=chunk_line_count,
                chunk_line_overlap=chunk_line_overlap,
                symbols=symbol_names,
            )
        )
    return chunks


def _structure_aware_spans(lines: list[str], *, chunk_line_count: int) -> list[tuple[int, int]]:
    declaration_starts: list[int] = []
    for index, line in enumerate(lines):
        if DECLARATION_START_PATTERN.match(line):
            declaration_starts.append(index)
    if not declaration_starts:
        return [(0, len(lines))]

    spans: list[tuple[int, int]] = []
    first_declaration = declaration_starts[0]
    if any(line.strip() for line in lines[:first_declaration]):
        spans.append((0, first_declaration))

    for offset, start in enumerate(declaration_starts):
        end = declaration_starts[offset + 1] if offset + 1 < len(declaration_starts) else len(lines)
        if end <= start:
            continue
        spans.append((start, end))

    filtered = [(start, end) for start, end in spans if any(line.strip() for line in lines[start:end])]
    return filtered or [(0, len(lines))]


def _subdivide_span(
    *,
    relative_path: str,
    source_category: SourceCategory,
    commit: str,
    snapshot: str,
    metadata: Mapping[str, str],
    lines: list[str],
    start: int,
    end: int,
    chunk_line_count: int,
    chunk_line_overlap: int,
    symbols: tuple[str, ...],
) -> list[IndexedChunk]:
    step = max(1, chunk_line_count - chunk_line_overlap)
    chunks: list[IndexedChunk] = []
    for window_start in range(start, end, step):
        window_end = min(end, window_start + chunk_line_count)
        chunk_lines = lines[window_start:window_end]
        if not any(line.strip() for line in chunk_lines):
            continue
        line_start = window_start + 1
        line_end = window_end
        chunk_id = f"repo-pre:{relative_path}:L{line_start}-L{line_end}"
        chunks.append(
            IndexedChunk(
                chunk_id=chunk_id,
                source_category=source_category,
                snapshot=snapshot,
                commit=commit,
                path=relative_path,
                line_start=line_start,
                line_end=line_end,
                text="\n".join(chunk_lines),
                symbols=symbols,
                metadata=dict(metadata),
            )
        )
    return chunks


def _estimate_chunk_count_for_text(
    text: str,
    *,
    chunk_line_count: int,
    chunk_line_overlap: int,
) -> int:
    lines = text.splitlines()
    if not lines:
        return 0
    step = max(1, chunk_line_count - chunk_line_overlap)
    count = 0
    for start, end in _structure_aware_spans(lines, chunk_line_count=chunk_line_count):
        for window_start in range(start, end, step):
            window_end = min(end, window_start + chunk_line_count)
            if any(line.strip() for line in lines[window_start:window_end]):
                count += 1
    return count


def _extract_chunk_symbols(lines: Iterable[str]) -> tuple[str, ...]:
    symbols: list[str] = []
    for line in lines:
        match = DECLARATION_SYMBOL_PATTERN.search(line)
        if match is None:
            continue
        symbols.append(match.group(1))
        if len(symbols) >= 4:
            break
    return tuple(symbols)


def _classify_source_category(relative_path: str) -> SourceCategory:
    normalized = relative_path.lower().replace("\\", "/")
    suffix = Path(relative_path).suffix.lower()
    parts = set(Path(normalized).parts)
    if suffix in DOCUMENTATION_EXTENSIONS or "docs" in parts or "documentation" in parts:
        return SourceCategory.DOCUMENTATION
    return SourceCategory.SOURCE_CODE


def _file_role(path: str) -> str:
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
    if any(part in normalized for part in ("/src/", "/lib/", "/app/", "/packages/", "/pkg/", "/core/", "/compiler/")):
        return "implementation"
    return "other"


def _should_skip_indexing(relative_path: str) -> bool:
    role = _file_role(relative_path)
    if role == "baseline_or_generated":
        return True
    normalized = relative_path.lower().replace("\\", "/")
    if "/bin/" in f"/{normalized}" or normalized.startswith("bin/"):
        return True
    return False


def _read_text_file(path: Path) -> str | None:
    for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1", "utf-16", "utf-16-le", "utf-16-be"):
        try:
            text = path.read_text(encoding=encoding)
        except UnicodeError:
            continue
        if _looks_like_bad_text_decode(text):
            continue
        return text
    return None


def _looks_like_bad_text_decode(text: str) -> bool:
    nul_count = text.count("\x00")
    return nul_count > max(1, len(text) // 200)
