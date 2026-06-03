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
EXCLUDED_DIRS = {".git", "node_modules", "dist", "build", ".cache", "coverage"}
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
    for file_path in sorted(_iter_source_files(root)):
        relative_path = file_path.relative_to(root).as_posix()
        text = _read_text_file(file_path)
        if text is None:
            continue
        lines = text.splitlines()
        step = chunk_line_count - chunk_line_overlap
        for start in range(0, len(lines), step):
            chunk_lines = lines[start : start + chunk_line_count]
            if not any(line.strip() for line in chunk_lines):
                continue
            line_start = start + 1
            line_end = start + len(chunk_lines)
            chunk_id = f"repo-pre:{relative_path}:L{line_start}-L{line_end}"
            chunks.append(
                IndexedChunk(
                    chunk_id=chunk_id,
                    source_category=_classify_source_category(relative_path),
                    snapshot=snapshot,
                    commit=commit,
                    path=relative_path,
                    line_start=line_start,
                    line_end=line_end,
                    text="\n".join(chunk_lines),
                    symbols=(),
                    metadata={
                        "visibility": visibility,
                        "origin": origin,
                    },
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


def _iter_source_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in EXCLUDED_DIRS for part in path.relative_to(root).parts):
            continue
        if path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        yield path


def _classify_source_category(relative_path: str) -> SourceCategory:
    normalized = relative_path.lower().replace("\\", "/")
    suffix = Path(relative_path).suffix.lower()
    parts = set(Path(normalized).parts)
    if suffix in DOCUMENTATION_EXTENSIONS or "docs" in parts or "documentation" in parts:
        return SourceCategory.DOCUMENTATION
    return SourceCategory.SOURCE_CODE


def _read_text_file(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            return None
