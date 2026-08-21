from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

from core.source_policy import SourceCategory


TOKEN_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|[0-9]+")
DECLARATION_START_PATTERN = re.compile(
    r"^\s*(?:export\s+)?(?:default\s+)?(?:declare\s+)?(?:async\s+)?(?:abstract\s+)?"
    r"(?:class|interface|enum|namespace|module|type|function)\b"
)
DECLARATION_SYMBOL_PATTERN = re.compile(
    r"^\s*(?:export\s+)?(?:default\s+)?(?:declare\s+)?(?:async\s+)?(?:abstract\s+)?"
    r"(?:class|interface|enum|namespace|module|type|function)\s+([A-Za-z_][A-Za-z0-9_]*)\b"
)
DEFAULT_EXCLUDED_PATHS = (
    ".git",
    ".guided-intelligence",
    ".codegraph",
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
IMPLEMENTATION_EXTENSIONS = {
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
    ".jsx",
    ".py",
    ".rs",
    ".ts",
    ".tsx",
}
MAX_INDEXED_FILE_CHARACTERS = 3_000_000
BM25_INDEX_SCHEMA_VERSION = 3
BM25F_INDEX_SCHEMA_VERSION = 4
BM25F_V2_INDEX_SCHEMA_VERSION = 5
LEXICAL_RANKING_FLAT_BM25 = "flat_bm25"
LEXICAL_RANKING_BM25F_V1 = "bm25f_v1"
LEXICAL_RANKING_BM25F_V2 = "bm25f_v2"
SUPPORTED_LEXICAL_RANKING_PROFILES = (
    LEXICAL_RANKING_FLAT_BM25,
    LEXICAL_RANKING_BM25F_V1,
    LEXICAL_RANKING_BM25F_V2,
)
BM25F_FIELD_WEIGHTS: Mapping[str, float] = {
    "body": 1.0,
    "directory_path": 2.0,
    "basename": 5.0,
    "definitions": 5.0,
}
BM25F_V2_FIELD_WEIGHTS: Mapping[str, float] = {
    "body": 1.0,
    "directory_path": 1.5,
    "basename": 3.0,
    "definitions": 3.0,
    "comment_phrases": 1.0,
}
BM25F_FIELD_LENGTH_NORMALIZATION: Mapping[str, float] = {
    "body": 0.75,
    "directory_path": 0.0,
    "basename": 0.0,
    "definitions": 0.0,
}
BM25F_V2_FIELD_LENGTH_NORMALIZATION: Mapping[str, float] = {
    "body": 0.75,
    "directory_path": 0.0,
    "basename": 0.0,
    "definitions": 0.0,
    "comment_phrases": 0.0,
}
COMMENT_PHRASE_PREFIX = "__comment_phrase__"
COMMENT_PHRASE_QUERY_WEIGHT = 0.25
COMMENT_PHRASE_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "if", "in", "into",
    "is", "it", "of", "on", "or", "that", "the", "this", "to", "was", "we", "when", "with",
}
TEST_DIRECTORY_TOKENS = {
    "test",
    "tests",
    "testing",
    "unittest",
    "unittests",
    "spec",
    "specs",
    "fixture",
    "fixtures",
    "testcase",
    "testcases",
    "testdata",
}


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
    fields: Mapping[str, tuple[str, ...]] = field(default_factory=dict)


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
    lexical_ranking_profile: str = LEXICAL_RANKING_FLAT_BM25
    average_field_lengths: Mapping[str, float] = field(default_factory=dict)

    def search(self, query: str, *, limit: int = 20) -> tuple[BM25SearchResult, ...]:
        query_weights = (
            sparse_query_term_weights(query, self.lexical_ranking_profile)
            if self.lexical_ranking_profile == LEXICAL_RANKING_BM25F_V2
            else {term: 1.0 for term in tokenize(query)}
        )
        if not query_weights or not self.documents:
            return ()

        results: list[BM25SearchResult] = []
        document_count = len(self.documents)
        k1 = 1.5
        b = 0.75

        for document in self.documents:
            frequencies = Counter(document.tokens)
            document_length = len(document.tokens)
            score = 0.0
            matched_terms: list[str] = []
            for term, query_weight in query_weights.items():
                frequency = (
                    _bm25f_term_frequency(
                        document,
                        term,
                        self.average_field_lengths,
                        self.lexical_ranking_profile,
                    )
                    if is_bm25f_profile(self.lexical_ranking_profile)
                    else float(frequencies.get(term, 0))
                )
                if frequency == 0:
                    continue
                matched_terms.append(term)
                doc_frequency = self.document_frequency.get(term, 0)
                idf = math.log(1 + (document_count - doc_frequency + 0.5) / (doc_frequency + 0.5))
                denominator = (
                    frequency + k1
                    if is_bm25f_profile(self.lexical_ranking_profile)
                    else frequency + k1 * (
                        1 - b + b * document_length / max(self.average_document_length, 1.0)
                    )
                )
                score += query_weight * idf * (frequency * (k1 + 1)) / denominator

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
            "lexical_ranking_profile": self.lexical_ranking_profile,
            "average_document_length": self.average_document_length,
            "average_field_lengths": dict(self.average_field_lengths),
            "document_frequency": dict(self.document_frequency),
            "documents": [
                {
                    "chunk": document.chunk.to_dict(),
                    "tokens": list(document.tokens),
                    "fields": {name: list(tokens) for name, tokens in document.fields.items()},
                }
                for document in self.documents
            ],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "BM25Index":
        return cls(
            average_document_length=float(data["average_document_length"]),
            lexical_ranking_profile=str(data.get("lexical_ranking_profile") or LEXICAL_RANKING_FLAT_BM25),
            average_field_lengths={
                str(key): float(value) for key, value in dict(data.get("average_field_lengths", {})).items()
            },
            document_frequency={str(key): int(value) for key, value in data["document_frequency"].items()},
            documents=tuple(
                BM25Document(
                    chunk=IndexedChunk.from_dict(item["chunk"]),
                    tokens=tuple(str(token) for token in item["tokens"]),
                    fields={
                        str(name): tuple(str(token) for token in tokens)
                        for name, tokens in dict(item.get("fields", {})).items()
                    },
                )
                for item in data["documents"]
            ),
        )


def tokenize(text: str) -> list[str]:
    return [match.group(0).lower() for match in TOKEN_PATTERN.finditer(text)]


def is_bm25f_profile(lexical_ranking_profile: str) -> bool:
    return lexical_ranking_profile in {LEXICAL_RANKING_BM25F_V1, LEXICAL_RANKING_BM25F_V2}


def bm25f_field_weights(lexical_ranking_profile: str) -> Mapping[str, float]:
    if lexical_ranking_profile == LEXICAL_RANKING_BM25F_V2:
        return BM25F_V2_FIELD_WEIGHTS
    return BM25F_FIELD_WEIGHTS


def bm25f_field_length_normalization(lexical_ranking_profile: str) -> Mapping[str, float]:
    if lexical_ranking_profile == LEXICAL_RANKING_BM25F_V2:
        return BM25F_V2_FIELD_LENGTH_NORMALIZATION
    return BM25F_FIELD_LENGTH_NORMALIZATION


def sparse_query_term_weights(query: str, lexical_ranking_profile: str) -> Mapping[str, float]:
    tokens = tuple(tokenize(query))
    if lexical_ranking_profile != LEXICAL_RANKING_BM25F_V2:
        # Preserve the existing Qdrant policy for flat BM25 and BM25F v1.
        return {term: float(count) for term, count in Counter(tokens).items()}
    weights: dict[str, float] = {term: 1.0 for term in tokens}
    for phrase in _meaningful_phrase_features(tokens):
        weights[phrase] = COMMENT_PHRASE_QUERY_WEIGHT
    return weights


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
    lexical_ranking_profile: str = LEXICAL_RANKING_FLAT_BM25,
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
    if lexical_ranking_profile not in SUPPORTED_LEXICAL_RANKING_PROFILES:
        raise ValueError(f"Unsupported lexical ranking profile: {lexical_ranking_profile}.")

    chunks: list[IndexedChunk] = []
    for file_path in sorted(_iter_source_files(root, exclude_paths=exclude_paths)):
        relative_path = file_path.relative_to(root).as_posix()
        if file_role(relative_path) == "baseline_or_generated":
            continue
        text = _read_text_file(file_path)
        if text is None or len(text) > MAX_INDEXED_FILE_CHARACTERS:
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

    documents = tuple(_bm25_document(chunk, lexical_ranking_profile) for chunk in chunks)
    document_frequency: dict[str, int] = {}
    for document in documents:
        vocabulary = set(document.tokens)
        if lexical_ranking_profile == LEXICAL_RANKING_BM25F_V2:
            vocabulary.update(token for tokens in document.fields.values() for token in tokens)
        for token in vocabulary:
            document_frequency[token] = document_frequency.get(token, 0) + 1
    average_document_length = (
        sum(len(document.tokens) for document in documents) / len(documents) if documents else 0.0
    )
    field_weights = bm25f_field_weights(lexical_ranking_profile)
    average_field_lengths = {
        name: sum(len(document.fields.get(name, ())) for document in documents) / len(documents)
        for name in field_weights
    } if documents and is_bm25f_profile(lexical_ranking_profile) else {}
    return BM25Index(
        documents=documents,
        average_document_length=average_document_length,
        document_frequency=document_frequency,
        lexical_ranking_profile=lexical_ranking_profile,
        average_field_lengths=average_field_lengths,
    )


def bm25_index_schema_version(lexical_ranking_profile: str) -> int:
    if lexical_ranking_profile == LEXICAL_RANKING_BM25F_V2:
        return BM25F_V2_INDEX_SCHEMA_VERSION
    if lexical_ranking_profile == LEXICAL_RANKING_BM25F_V1:
        return BM25F_INDEX_SCHEMA_VERSION
    return BM25_INDEX_SCHEMA_VERSION


def _bm25_document(chunk: IndexedChunk, lexical_ranking_profile: str) -> BM25Document:
    tokens = tuple(tokenize(_document_text(chunk)))
    if not is_bm25f_profile(lexical_ranking_profile):
        return BM25Document(chunk=chunk, tokens=tokens)
    path = Path(chunk.path)
    definitions = chunk.symbols
    if lexical_ranking_profile == LEXICAL_RANKING_BM25F_V2:
        definitions = tuple(symbol for symbol in definitions if _is_specific_definition(symbol))
    fields = {
        "body": tuple(tokenize(chunk.text)),
        "directory_path": tuple(tokenize(path.parent.as_posix())) if path.parent.as_posix() != "." else (),
        "basename": tuple(tokenize(path.name)),
        "definitions": tuple(token for symbol in definitions for token in tokenize(symbol)),
    }
    if lexical_ranking_profile == LEXICAL_RANKING_BM25F_V2:
        body_tokens = tuple(tokenize(chunk.text))
        fields["comment_phrases"] = (
            _meaningful_phrase_features(body_tokens) if _is_comment_only_chunk(chunk.text) else ()
        )
    return BM25Document(chunk=chunk, tokens=tokens, fields=fields)


def _bm25f_term_frequency(
    document: BM25Document,
    term: str,
    average_field_lengths: Mapping[str, float],
    lexical_ranking_profile: str,
) -> float:
    frequency = 0.0
    field_weights = bm25f_field_weights(lexical_ranking_profile)
    length_normalization = bm25f_field_length_normalization(lexical_ranking_profile)
    for name, weight in field_weights.items():
        tokens = document.fields.get(name, ())
        term_frequency = tokens.count(term)
        if not term_frequency:
            continue
        b = length_normalization[name]
        average_length = max(average_field_lengths.get(name, 0.0), 1.0)
        normalization = 1.0 - b + b * len(tokens) / average_length
        frequency += weight * term_frequency / max(normalization, 0.01)
    return frequency


def bm25f_field_match_trace(
    document: BM25Document,
    query: str,
    *,
    average_field_lengths: Mapping[str, float],
    lexical_ranking_profile: str,
) -> Mapping[str, Mapping[str, Any]]:
    if lexical_ranking_profile != LEXICAL_RANKING_BM25F_V2:
        return {}
    query_weights = sparse_query_term_weights(query, lexical_ranking_profile)
    field_weights = bm25f_field_weights(lexical_ranking_profile)
    length_normalization = bm25f_field_length_normalization(lexical_ranking_profile)
    trace: dict[str, Mapping[str, Any]] = {}
    for name, field_weight in field_weights.items():
        tokens = document.fields.get(name, ())
        counts = Counter(tokens)
        matched = tuple(sorted(term for term in counts if term in query_weights))
        if not matched:
            continue
        b = length_normalization[name]
        average_length = max(average_field_lengths.get(name, 0.0), 1.0)
        normalization = 1.0 - b + b * len(tokens) / average_length
        weighted_frequency = sum(
            query_weights[term] * field_weight * counts[term] / max(normalization, 0.01)
            for term in matched
        )
        trace[name] = {
            "matched_terms": [
                term.removeprefix(COMMENT_PHRASE_PREFIX).replace("__", " ")
                if term.startswith(COMMENT_PHRASE_PREFIX)
                else term
                for term in matched
            ],
            "weighted_frequency": round(weighted_frequency, 6),
        }
    return trace


def _is_specific_definition(symbol: str) -> bool:
    return bool(
        re.search(r"[a-z0-9][A-Z]", symbol)
        or "_" in symbol
        or re.search(r"\d", symbol)
    )


def _meaningful_phrase_features(tokens: Iterable[str]) -> tuple[str, ...]:
    values = tuple(tokens)
    return tuple(
        f"{COMMENT_PHRASE_PREFIX}{left}__{right}"
        for left, right in zip(values, values[1:])
        if len(left) > 2
        and len(right) > 2
        and left not in COMMENT_PHRASE_STOPWORDS
        and right not in COMMENT_PHRASE_STOPWORDS
    )


def _is_comment_only_chunk(text: str) -> bool:
    in_block_comment = False
    saw_comment = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if in_block_comment:
            saw_comment = True
            if "*/" in line:
                in_block_comment = False
            continue
        if line.startswith(("//", "#")):
            saw_comment = True
            continue
        if line.startswith("/*"):
            saw_comment = True
            in_block_comment = "*/" not in line
            continue
        return False
    return saw_comment


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
    indexed_file_count = 0
    content_digest = hashlib.sha256()
    total_bytes = 0
    estimated_chunks = 0
    oversized_file_count = 0
    oversized_total_bytes = 0
    oversized_sample_paths: list[str] = []
    for path in files:
        relative_path = path.relative_to(root).as_posix()
        if file_role(relative_path) == "baseline_or_generated":
            continue
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        text = _read_text_file(path)
        if text is None:
            continue
        if len(text) > MAX_INDEXED_FILE_CHARACTERS:
            oversized_file_count += 1
            oversized_total_bytes += size
            if len(oversized_sample_paths) < 12:
                oversized_sample_paths.append(relative_path)
            continue
        content_digest.update(relative_path.encode("utf-8"))
        content_digest.update(b"\0")
        content_digest.update(text.encode("utf-8"))
        content_digest.update(b"\0")
        indexed_file_count += 1
        total_bytes += size
        estimated_chunks += _estimate_chunk_count_for_text(
            text,
            chunk_line_count=chunk_line_count,
            chunk_line_overlap=chunk_line_overlap,
        )
    return {
        "file_count": indexed_file_count,
        "total_bytes": total_bytes,
        "estimated_chunks": estimated_chunks,
        "content_signature": content_digest.hexdigest(),
        "sample_paths": [path.relative_to(root).as_posix() for path in files[:20]],
        "oversized_file_count": oversized_file_count,
        "oversized_total_bytes": oversized_total_bytes,
        "oversized_sample_paths": oversized_sample_paths,
        "max_indexed_file_characters": MAX_INDEXED_FILE_CHARACTERS,
    }


def indexable_content_signature(
    repo_path: str | Path,
    *,
    exclude_paths: tuple[str, ...] | None = None,
) -> str:
    """Hash the exact repository text eligible for BM25/Qdrant indexing."""
    root = Path(repo_path).resolve()
    digest = hashlib.sha256()
    for path in sorted(_iter_source_files(root, exclude_paths=exclude_paths)):
        relative_path = path.relative_to(root).as_posix()
        if file_role(relative_path) == "baseline_or_generated":
            continue
        text = _read_text_file(path)
        if text is None or len(text) > MAX_INDEXED_FILE_CHARACTERS:
            continue
        digest.update(relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(text.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


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
    declaration_lines: list[int] = []
    for index, line in enumerate(lines):
        if DECLARATION_START_PATTERN.match(line):
            declaration_lines.append(index)
    if not declaration_lines:
        return [(0, len(lines))]

    declaration_starts = [_leading_comment_start(lines, index) for index in declaration_lines]

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


def _leading_comment_start(lines: list[str], declaration_start: int) -> int:
    cursor = declaration_start - 1
    while cursor >= 0 and not lines[cursor].strip():
        cursor -= 1
    if cursor < 0:
        return declaration_start

    line = lines[cursor].strip()
    if line.startswith("//"):
        while cursor >= 0 and lines[cursor].strip().startswith("//"):
            cursor -= 1
        return cursor + 1
    if not line.endswith("*/"):
        return declaration_start

    while cursor >= 0:
        current = lines[cursor].strip()
        if current.startswith("/*"):
            return cursor
        if current and not current.startswith("*") and not current.endswith("*/"):
            return declaration_start
        cursor -= 1
    return declaration_start


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
        match = DECLARATION_SYMBOL_PATTERN.match(line)
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


def file_role(path: str) -> str:
    raw_normalized_path = path.replace("\\", "/")
    normalized_path = raw_normalized_path.lower()
    normalized = f"/{normalized_path}"
    parts = tuple(part for part in normalized.split("/") if part)
    raw_parts = tuple(part for part in raw_normalized_path.split("/") if part)
    name = parts[-1] if parts else ""
    suffix = Path(name).suffix.lower()
    directory_tokens = {
        token
        for part in raw_parts[:-1]
        for token in _path_segment_tokens(part)
    }

    if suffix in {".md", ".rst", ".adoc"} or "docs" in parts or "documentation" in parts:
        return "documentation"
    if (
        suffix in {".yml", ".yaml", ".toml", ".ini", ".cfg"}
        or ".github" in parts
        or ".circleci" in parts
        or "config" in parts
        or "configs" in parts
        or name.startswith(".env")
    ):
        return "configuration"
    if (
        "bin" in parts
        or normalized.startswith("/bin/")
        or "dist" in parts
        or "baseline" in normalized
        or "baselines" in parts
        or "snapshot" in normalized
        or "snapshots" in parts
        or "golden" in normalized
        or "generated" in normalized
        or name.endswith(".generated.ts")
        or name.endswith(".generated.js")
        or re.fullmatch(
            r"(?:build|bundle)(?:[.-](?:dev|prod|production|development|min))?(?:\.min)?\.(?:js|css)",
            name,
        )
    ):
        return "baseline_or_generated"
    if (
        bool(directory_tokens & TEST_DIRECTORY_TOKENS)
        or name.endswith(".test.ts")
        or name.endswith(".spec.ts")
        or name.endswith(".test.js")
        or name.endswith(".spec.js")
    ):
        return "test"
    if suffix in IMPLEMENTATION_EXTENSIONS:
        return "implementation"
    return "other"


def _path_segment_tokens(value: str) -> tuple[str, ...]:
    camel_split = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", value)
    return tuple(token.casefold() for token in re.findall(r"[A-Za-z0-9]+", camel_split))


def _should_skip_indexing(relative_path: str) -> bool:
    role = file_role(relative_path)
    if role == "baseline_or_generated":
        return True
    normalized = relative_path.lower().replace("\\", "/")
    if "/bin/" in f"/{normalized}" or normalized.startswith("bin/"):
        return True
    return False


_file_role = file_role


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
