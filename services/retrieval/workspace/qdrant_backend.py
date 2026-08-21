from __future__ import annotations

import concurrent.futures
import hashlib
import json
import math
import re
import sqlite3
import struct
import threading
import time
import urllib.error
import urllib.request
import uuid
from collections import Counter
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from services.retrieval.workspace.bm25 import (
    BM25Document,
    BM25Index,
    IndexedChunk,
    bm25f_field_length_normalization,
    bm25f_field_match_trace,
    bm25f_field_weights,
    is_bm25f_profile,
    sparse_query_term_weights,
    tokenize,
)
from services.retrieval.config import RetrievalEmbeddingConfig, RetrievalQdrantConfig


QDRANT_DENSE_VECTOR_NAME = "dense"
QDRANT_SPARSE_VECTOR_NAME = "sparse"
_BM25_K1 = 1.5
_BM25_B = 0.75
_EMBEDDING_REQUEST_RETRIES = 8
_MAX_EMBEDDING_INPUT_TOKENS = 1200
_MAX_EMBEDDING_INPUT_CHARS = 4000
# Large repositories can produce multi-gigabyte JSON caches. Persist bounded
# progress without rewriting the complete cache after every embedding batch.
# A mandatory final flush still saves every successful build; this checkpoint
# protects long first-time builds without repeatedly serializing several GB.
_EMBEDDING_CACHE_FLUSH_BATCHES = 512
_EMBEDDING_CACHE_MIN_BATCHES_AFTER_CHECKPOINT = 64
_EMBEDDING_TOKEN_ESTIMATE_SAFETY_FACTOR = 1.15


class _EmbeddingTokenRateGate:
    """Coordinate concurrent embedding requests against one shared TPM budget."""

    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._remaining_tokens: int | None = None
        self._reset_at = 0.0
        self._blocked_until = 0.0
        self._reserved_tokens = 0
        self._calibrated = False
        self._recovering = False

    def acquire(self, estimated_tokens: int) -> int:
        reservation = max(1, estimated_tokens)
        with self._condition:
            while True:
                now = time.monotonic()
                wait_until = self._blocked_until
                if self._remaining_tokens is not None and reservation > self._remaining_tokens:
                    wait_until = max(wait_until, self._reset_at)
                # Until the first provider response, and after a 429, send one
                # probe at a time so two workers cannot race on unknown headroom.
                serialized_probe = (not self._calibrated or self._recovering) and self._reserved_tokens > 0
                if wait_until > now:
                    self._condition.wait(timeout=wait_until - now)
                    continue
                if serialized_probe:
                    self._condition.wait()
                    continue
                if self._remaining_tokens is not None and reservation > self._remaining_tokens:
                    # The advertised reset passed. Treat the next request as a
                    # serialized probe and learn the refreshed budget from it.
                    self._remaining_tokens = None
                    self._calibrated = False
                    continue
                if self._remaining_tokens is not None:
                    self._remaining_tokens = max(0, self._remaining_tokens - reservation)
                self._reserved_tokens += reservation
                return reservation

    def complete(self, reservation: int, headers: Mapping[str, str]) -> None:
        with self._condition:
            self._reserved_tokens = max(0, self._reserved_tokens - reservation)
            remaining = _integer_header(headers, "x-ratelimit-remaining-tokens")
            reset_seconds = _rate_limit_reset_seconds(headers.get("x-ratelimit-reset-tokens", ""))
            if remaining is not None:
                # The response may not yet reflect another request currently in
                # flight, so retain a conservative reservation for that work.
                self._remaining_tokens = max(0, remaining - self._reserved_tokens)
                self._calibrated = True
            if reset_seconds is not None:
                self._reset_at = time.monotonic() + reset_seconds
            self._recovering = False
            self._condition.notify_all()

    def release(self, reservation: int) -> None:
        with self._condition:
            self._reserved_tokens = max(0, self._reserved_tokens - reservation)
            self._condition.notify_all()

    def rate_limited(self, reservation: int, headers: Mapping[str, str], retry_delay: float) -> None:
        with self._condition:
            self._reserved_tokens = max(0, self._reserved_tokens - reservation)
            now = time.monotonic()
            reset_seconds = _rate_limit_reset_seconds(headers.get("x-ratelimit-reset-tokens", ""))
            wait_seconds = max(retry_delay, reset_seconds or 0.0)
            self._blocked_until = max(self._blocked_until, now + wait_seconds)
            self._reset_at = max(self._reset_at, self._blocked_until)
            self._remaining_tokens = 0
            self._recovering = True
            self._condition.notify_all()


@dataclass(frozen=True)
class QdrantSearchResult:
    chunk: IndexedChunk
    score: float
    matched_terms: tuple[str, ...]
    retrieval_path: str = "qdrant_hybrid_search"
    lexical_field_matches: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)


@dataclass(frozen=True)
class SparseSchema:
    token_to_index: Mapping[str, int]
    idf_by_token: Mapping[str, float]
    average_document_length: float
    document_count: int
    lexical_ranking_profile: str
    average_field_lengths: Mapping[str, float]


class QdrantHybridBackend:
    def __init__(
        self,
        *,
        index: BM25Index,
        qdrant_config: RetrievalQdrantConfig,
        embedding_config: RetrievalEmbeddingConfig,
        cache_path: str | Path | None = None,
    ) -> None:
        self.index = index
        self.qdrant_config = qdrant_config
        self.embedding_config = embedding_config
        self.cache_path = Path(cache_path) if cache_path else None
        self._chunks_by_point_id = {
            _point_id_for_chunk_id(document.chunk.chunk_id): document.chunk for document in index.documents
        }
        self._documents_by_point_id = {
            _point_id_for_chunk_id(document.chunk.chunk_id): document for document in index.documents
        }
        self._sparse_schema = _build_sparse_schema(index)
        self._embedding_cache_lock = threading.RLock()
        self._sqlite_embedding_cache = bool(
            self.cache_path is not None
            and self.cache_path.suffix.lower() in {".db", ".sqlite", ".sqlite3"}
        )
        if self._sqlite_embedding_cache:
            self._initialize_sqlite_embedding_cache()
        self._embedding_cache = self._load_embedding_cache()
        self._embedding_rate_gate = _EmbeddingTokenRateGate()
        self._last_search_breakdown: Mapping[str, tuple[QdrantSearchResult, ...]] | None = None

    def collection_exists(self) -> bool:
        try:
            response = self._request("GET", f"/collections/{self.qdrant_config.collection_name}")
        except RuntimeError:
            return False
        result = response.get("result", {})
        return isinstance(result, Mapping) and bool(result)

    def point_count(self) -> int:
        response = self._request("POST", f"/collections/{self.qdrant_config.collection_name}/points/count", {"exact": True})
        result = response.get("result", {})
        if not isinstance(result, Mapping):
            return 0
        return int(result.get("count", 0) or 0)

    def index_signature(self) -> str:
        digest = hashlib.sha256()
        digest.update(self.embedding_config.model.encode("utf-8"))
        digest.update(b"\n")
        digest.update(self.index.lexical_ranking_profile.encode("utf-8"))
        digest.update(b"\n")
        digest.update(json.dumps(dict(bm25f_field_weights(self.index.lexical_ranking_profile)), sort_keys=True).encode("utf-8"))
        digest.update(b"\n")
        digest.update(json.dumps(dict(bm25f_field_length_normalization(self.index.lexical_ranking_profile)), sort_keys=True).encode("utf-8"))
        digest.update(b"\n")
        digest.update(json.dumps(dict(self.index.average_field_lengths), sort_keys=True).encode("utf-8"))
        digest.update(b"\n")
        for document in self.index.documents:
            chunk = document.chunk
            digest.update(chunk.chunk_id.encode("utf-8"))
            digest.update(b"\n")
            digest.update(chunk.path.encode("utf-8"))
            digest.update(b"\n")
            digest.update(str(chunk.line_start).encode("utf-8"))
            digest.update(b":")
            digest.update(str(chunk.line_end).encode("utf-8"))
            digest.update(b"\n")
            digest.update(chunk.text.encode("utf-8"))
            digest.update(b"\n")
            digest.update(chunk.source_category.value.encode("utf-8"))
            digest.update(b"\n")
            digest.update(json.dumps(dict(chunk.metadata), sort_keys=True, separators=(",", ":")).encode("utf-8"))
            digest.update(b"\n")
        return digest.hexdigest()

    def ensure_available(self) -> None:
        self._request("GET", "/collections")

    def rebuild_collection(
        self,
        *,
        log_event: Callable[[str, Mapping[str, Any]], None] | None = None,
        timeout_seconds: int | None = None,
    ) -> int:
        rebuild_deadline = (
            time.monotonic() + (timeout_seconds * 2)
            if timeout_seconds is not None and timeout_seconds > 0
            else None
        )
        self.ensure_available()
        documents = self.index.documents
        if not documents:
            raise RuntimeError("Cannot build a Qdrant collection from an empty repository index.")
        batch_size = self.embedding_config.batch_size
        first_documents = documents[:batch_size]
        first_dense_batches = self._embed_documents(
            [document.chunk for document in first_documents],
            log_event=log_event,
            deadline=rebuild_deadline,
        )
        _raise_if_rebuild_timed_out(rebuild_deadline)
        first_dense_vectors = first_dense_batches[0] if first_dense_batches else []
        dense_size = len(first_dense_vectors[0]) if first_dense_vectors else 0
        if dense_size <= 0:
            raise RuntimeError("Embedding backend returned no vectors for repository chunks.")
        try:
            self._request("DELETE", f"/collections/{self.qdrant_config.collection_name}")
        except RuntimeError:
            pass
        self._request(
            "PUT",
            f"/collections/{self.qdrant_config.collection_name}",
            {
                "vectors": {
                    QDRANT_DENSE_VECTOR_NAME: {
                        "size": dense_size,
                        "distance": "Cosine",
                    }
                },
                "sparse_vectors": {
                    QDRANT_SPARSE_VECTOR_NAME: {}
                },
            },
        )
        total_batches = math.ceil(len(documents) / batch_size)
        for batch_start in range(0, len(documents), batch_size):
            _raise_if_rebuild_timed_out(rebuild_deadline)
            batch_documents = documents[batch_start : batch_start + batch_size]
            if batch_start == 0:
                batch_dense_vectors = first_dense_vectors
            else:
                dense_batches = self._embed_documents(
                    [document.chunk for document in batch_documents],
                    log_event=log_event,
                    deadline=rebuild_deadline,
                )
                batch_dense_vectors = dense_batches[0] if dense_batches else []
            if len(batch_dense_vectors) != len(batch_documents):
                raise RuntimeError("Embedding backend returned an incomplete vector batch during Qdrant rebuild.")
            points: list[dict[str, Any]] = []
            for document, dense_vector in zip(batch_documents, batch_dense_vectors):
                chunk = document.chunk
                sparse_vector = _document_sparse_vector(
                    document,
                    token_to_index=self._sparse_schema.token_to_index,
                    average_document_length=self._sparse_schema.average_document_length,
                    lexical_ranking_profile=self._sparse_schema.lexical_ranking_profile,
                    average_field_lengths=self._sparse_schema.average_field_lengths,
                )
                points.append(
                    {
                        "id": _point_id_for_chunk_id(chunk.chunk_id),
                        "vector": {
                            QDRANT_DENSE_VECTOR_NAME: dense_vector,
                            QDRANT_SPARSE_VECTOR_NAME: sparse_vector,
                        },
                        "payload": _chunk_payload(chunk),
                    }
                )
            self._request(
                "PUT",
                f"/collections/{self.qdrant_config.collection_name}/points?wait=true",
                {"points": points},
            )
            completed_batch = batch_start // batch_size + 1
            if log_event is not None and (completed_batch == total_batches or completed_batch % 25 == 0):
                log_event(
                    "qdrant_upsert_progress",
                    {
                        "completed_batches": completed_batch,
                        "total_batches": total_batches,
                        "indexed_points": min(batch_start + len(points), len(documents)),
                        "document_count": len(documents),
                    },
                )
        return len(documents)

    def search(
        self,
        query: str,
        *,
        sparse_query: str | None = None,
        limit: int,
        path: str = "",
        paths: Sequence[str] = (),
        min_score: float = 0.0,
        source_category: str = "",
        file_role: str = "",
        include_breakdown: bool = False,
    ) -> tuple[QdrantSearchResult, ...]:
        self.ensure_available()
        dense_vector = self._embed_query(query)
        sparse_query_text = sparse_query if sparse_query is not None else query
        sparse_vector = _query_sparse_vector(sparse_query_text, self._sparse_schema)
        qdrant_filter = _build_qdrant_filter(
            path=path,
            paths=paths,
            source_category=source_category,
            file_role=file_role,
        )
        prefetch: list[dict[str, Any]] = []
        if sparse_vector["indices"]:
            prefetch.append(
                {
                    "query": sparse_vector,
                    "using": QDRANT_SPARSE_VECTOR_NAME,
                    "limit": max(limit * 3, limit),
                    "filter": qdrant_filter,
                }
            )
        prefetch.append(
            {
                "query": dense_vector,
                "using": QDRANT_DENSE_VECTOR_NAME,
                "limit": max(limit * 3, limit),
                "filter": qdrant_filter,
            }
        )
        response = self._request(
            "POST",
            f"/collections/{self.qdrant_config.collection_name}/points/query",
            {
                "prefetch": prefetch,
                "query": {"fusion": "rrf"},
                "limit": limit,
                "with_payload": True,
                "with_vector": False,
            },
        )
        rows = response.get("result", {}).get("points", ())
        results = self._rows_to_results(
            rows,
            query=query,
            lexical_query=sparse_query_text,
            min_score=min_score,
        )
        if include_breakdown:
            self._last_search_breakdown = {
                "sparse": self._search_single_vector(
                    query=sparse_query_text,
                    query_vector=sparse_vector,
                    vector_name=QDRANT_SPARSE_VECTOR_NAME,
                    qdrant_filter=qdrant_filter,
                    limit=limit,
                    min_score=min_score,
                    include_lexical_trace=True,
                ),
                "dense": self._search_single_vector(
                    query=query,
                    query_vector=dense_vector,
                    vector_name=QDRANT_DENSE_VECTOR_NAME,
                    qdrant_filter=qdrant_filter,
                    limit=limit,
                    min_score=min_score,
                    include_lexical_trace=False,
                ),
                "hybrid": results,
            }
        else:
            self._last_search_breakdown = None
        return tuple(results)

    def last_search_breakdown(self) -> Mapping[str, tuple[QdrantSearchResult, ...]] | None:
        return self._last_search_breakdown

    def _search_single_vector(
        self,
        *,
        query: str,
        query_vector: Any,
        vector_name: str,
        qdrant_filter: Mapping[str, Any] | None,
        limit: int,
        min_score: float,
        include_lexical_trace: bool,
    ) -> tuple[QdrantSearchResult, ...]:
        if vector_name == QDRANT_SPARSE_VECTOR_NAME and not query_vector.get("indices"):
            return ()
        response = self._request(
            "POST",
            f"/collections/{self.qdrant_config.collection_name}/points/query",
            {
                "query": query_vector,
                "using": vector_name,
                "limit": limit,
                "filter": qdrant_filter,
                "with_payload": True,
                "with_vector": False,
            },
        )
        rows = response.get("result", {}).get("points", ())
        return self._rows_to_results(
            rows,
            query=query,
            lexical_query=query if include_lexical_trace else None,
            min_score=min_score,
        )

    def _rows_to_results(
        self,
        rows: Iterable[Any],
        *,
        query: str,
        lexical_query: str | None,
        min_score: float,
    ) -> tuple[QdrantSearchResult, ...]:
        results: list[QdrantSearchResult] = []
        query_terms = set(tokenize(query))
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            point_id = str(row.get("id", ""))
            chunk = self._chunks_by_point_id.get(point_id)
            document = self._documents_by_point_id.get(point_id)
            if chunk is None or document is None:
                continue
            score = float(row.get("score", 0.0) or 0.0)
            if score < min_score:
                continue
            matched_terms = tuple(sorted(query_terms.intersection(tokenize(chunk.text))))
            field_matches = (
                bm25f_field_match_trace(
                    document,
                    lexical_query,
                    average_field_lengths=self.index.average_field_lengths,
                    lexical_ranking_profile=self.index.lexical_ranking_profile,
                )
                if lexical_query
                else {}
            )
            results.append(
                QdrantSearchResult(
                    chunk=chunk,
                    score=score,
                    matched_terms=matched_terms,
                    lexical_field_matches=field_matches,
                )
            )
        return tuple(results)

    def _embed_documents(
        self,
        chunks: Sequence[IndexedChunk],
        *,
        log_event: Callable[[str, Mapping[str, Any]], None] | None = None,
        deadline: float | None = None,
    ) -> list[list[list[float]]]:
        texts = [_chunk_embedding_text(chunk) for chunk in chunks]
        batch_size = self.embedding_config.batch_size
        dense_vectors: list[list[float] | None] = [None] * len(texts)
        uncached_positions: list[int] = []
        uncached_inputs: list[str] = []

        cache_keys = [
            _embedding_cache_key(model=self.embedding_config.model, text=text)
            for text in texts
        ]
        cached_vectors = self._cached_embedding_vectors(cache_keys)
        for index, (text, cache_key) in enumerate(zip(texts, cache_keys)):
            cached_vector = cached_vectors.get(cache_key)
            if cached_vector is not None:
                dense_vectors[index] = cached_vector
            else:
                uncached_positions.append(index)
                uncached_inputs.append(text)

        pending_batches: list[tuple[int, list[str]]] = []
        for batch_start in range(0, len(uncached_inputs), batch_size):
            pending_batches.append((batch_start, uncached_inputs[batch_start : batch_start + batch_size]))

        if pending_batches:
            completed_since_flush = 0
            successful_batch_count = 0
            successful_batch_count_lock = threading.Lock()
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=self.embedding_config.concurrency) as executor:
                    pending_iter = iter(pending_batches)
                    in_flight: dict[concurrent.futures.Future[list[list[float]]], tuple[int, list[str]]] = {}

                    def submit_next() -> bool:
                        _raise_if_rebuild_timed_out(deadline)
                        try:
                            batch_start, batch_inputs = next(pending_iter)
                        except StopIteration:
                            return False
                        if log_event is not None:
                            log_event(
                                "embedding_batch_sent",
                                {
                                    "model": self.embedding_config.model,
                                    "endpoint_url": self.embedding_config.endpoint_url,
                                    "batch_size": len(batch_inputs),
                                },
                            )
                        def embed_and_cache() -> list[list[float]]:
                            nonlocal successful_batch_count
                            vectors = self._embedding_request(batch_inputs)
                            self._store_embedding_vectors(
                                {
                                    _embedding_cache_key(model=self.embedding_config.model, text=text): vector
                                    for text, vector in zip(batch_inputs, vectors)
                                }
                            )
                            with successful_batch_count_lock:
                                successful_batch_count += 1
                            return vectors

                        future = executor.submit(embed_and_cache)
                        in_flight[future] = (batch_start, batch_inputs)
                        return True

                    for _ in range(self.embedding_config.concurrency):
                        if not submit_next():
                            break

                    while in_flight:
                        _raise_if_rebuild_timed_out(deadline)
                        completed_future = next(concurrent.futures.as_completed(tuple(in_flight.keys())))
                        batch_start, batch_inputs = in_flight.pop(completed_future)
                        batch_vectors = completed_future.result()
                        for offset, vector in enumerate(batch_vectors):
                            position = uncached_positions[batch_start + offset]
                            dense_vectors[position] = vector
                        completed_since_flush += 1
                        if log_event is not None:
                            log_event(
                                "embedding_batch_completed",
                                {
                                    "batch_size": len(batch_inputs),
                                    "model": self.embedding_config.model,
                                    "endpoint_url": self.embedding_config.endpoint_url,
                                },
                            )
                        remaining_batches = len(pending_batches) - successful_batch_count
                        if (
                            completed_since_flush >= _EMBEDDING_CACHE_FLUSH_BATCHES
                            and remaining_batches > _EMBEDDING_CACHE_MIN_BATCHES_AFTER_CHECKPOINT
                        ):
                            self._save_embedding_cache()
                            completed_since_flush = 0
                        submit_next()
            except BaseException as exc:
                # The executor waits for already-running requests to finish.
                # Persist every successful batch, including one that completed
                # after a different in-flight batch raised the original error.
                if successful_batch_count > 0:
                    try:
                        self._save_embedding_cache()
                    except Exception as cache_exc:
                        raise RuntimeError(
                            f"{exc} Additionally failed to persist completed embedding cache entries: {cache_exc}"
                        ) from exc
                raise
            if completed_since_flush > 0:
                self._save_embedding_cache()

        dense_batches: list[list[list[float]]] = []
        for batch_start in range(0, len(dense_vectors), batch_size):
            batch_vectors = dense_vectors[batch_start : batch_start + batch_size]
            if any(vector is None for vector in batch_vectors):
                raise RuntimeError("Embedding cache population failed for one or more repository chunks.")
            dense_batches.append([[float(number) for number in vector] for vector in batch_vectors if vector is not None])
        return dense_batches

    def _embed_query(self, query: str) -> list[float]:
        return self._embedding_request(query)[0]

    def _embedding_request(self, value: str | Sequence[str]) -> list[list[float]]:
        payload = {"model": self.embedding_config.model, "input": value}
        response = _json_request(
            url=self.embedding_config.endpoint_url,
            method="POST",
            payload=payload,
            headers={"Authorization": f"Bearer {self.embedding_config.api_key}"},
            timeout_seconds=self.embedding_config.timeout_seconds,
            rate_gate=self._embedding_rate_gate,
            estimated_tokens=_estimated_embedding_tokens(value),
        )
        data = response.get("data", ())
        if not isinstance(data, Sequence):
            raise RuntimeError("Embedding response missing data array.")
        vectors: list[list[float]] = []
        for item in data:
            if not isinstance(item, Mapping):
                continue
            embedding = item.get("embedding", ())
            if not isinstance(embedding, Sequence):
                continue
            vectors.append([float(number) for number in embedding])
        if not vectors:
            raise RuntimeError("Embedding response returned no vectors.")
        return vectors

    def _request(self, method: str, path: str, payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        base = self.qdrant_config.url.rstrip("/")
        return _json_request(
            url=f"{base}{path}",
            method=method,
            payload=payload,
            timeout_seconds=self.qdrant_config.timeout_seconds,
        )

    def _load_embedding_cache(self) -> dict[str, list[float]]:
        if self._sqlite_embedding_cache:
            return {}
        if self.cache_path is None or not self.cache_path.exists():
            return {}
        try:
            payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        entries = payload.get("entries", {})
        if not isinstance(entries, Mapping):
            return {}
        cache: dict[str, list[float]] = {}
        for key, value in entries.items():
            if not isinstance(key, str) or not isinstance(value, Sequence):
                continue
            cache[key] = [float(number) for number in value]
        return cache

    def _initialize_sqlite_embedding_cache(self) -> None:
        if self.cache_path is None:
            return
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.cache_path)) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS embeddings ("
                "cache_key TEXT PRIMARY KEY, vector BLOB NOT NULL)"
            )
            connection.commit()

    def _cached_embedding_vectors(self, cache_keys: Sequence[str]) -> dict[str, list[float]]:
        if not self._sqlite_embedding_cache:
            return {
                cache_key: vector
                for cache_key in cache_keys
                if (vector := self._embedding_cache.get(cache_key)) is not None
            }
        if self.cache_path is None or not cache_keys:
            return {}
        cached: dict[str, list[float]] = {}
        with self._embedding_cache_lock, closing(sqlite3.connect(self.cache_path)) as connection:
            for start in range(0, len(cache_keys), 500):
                batch = cache_keys[start : start + 500]
                placeholders = ",".join("?" for _ in batch)
                rows = connection.execute(
                    f"SELECT cache_key, vector FROM embeddings WHERE cache_key IN ({placeholders})",
                    batch,
                )
                for cache_key, payload in rows:
                    cached[str(cache_key)] = _decode_embedding_vector(payload)
        return cached

    def _store_embedding_vectors(self, entries: Mapping[str, Sequence[float]]) -> None:
        if not entries:
            return
        if not self._sqlite_embedding_cache:
            with self._embedding_cache_lock:
                self._embedding_cache.update(
                    (cache_key, [float(value) for value in vector])
                    for cache_key, vector in entries.items()
                )
            return
        if self.cache_path is None:
            return
        rows = [
            (cache_key, _encode_embedding_vector(vector))
            for cache_key, vector in entries.items()
        ]
        with self._embedding_cache_lock, closing(sqlite3.connect(self.cache_path)) as connection:
            connection.executemany(
                "INSERT OR REPLACE INTO embeddings(cache_key, vector) VALUES (?, ?)",
                rows,
            )
            connection.commit()

    def _save_embedding_cache(self) -> None:
        if self.cache_path is None or self._sqlite_embedding_cache:
            return
        with self._embedding_cache_lock:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "model": self.embedding_config.model,
                "entries": self._embedding_cache,
            }
            temporary_path = self.cache_path.with_name(
                f".{self.cache_path.name}.{uuid.uuid4().hex}.tmp"
            )
            try:
                temporary_path.write_text(json.dumps(payload), encoding="utf-8")
                temporary_path.replace(self.cache_path)
            finally:
                temporary_path.unlink(missing_ok=True)


def _json_request(
    *,
    url: str,
    method: str,
    timeout_seconds: int,
    payload: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
    rate_gate: _EmbeddingTokenRateGate | None = None,
    estimated_tokens: int = 0,
) -> Mapping[str, Any]:
    last_error: Exception | None = None
    for attempt in range(_EMBEDDING_REQUEST_RETRIES):
        reservation = rate_gate.acquire(estimated_tokens) if rate_gate is not None else 0
        retry_delay = min(8.0, 1.25 * (2**attempt))
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request_headers = {"Content-Type": "application/json"}
        if headers:
            request_headers.update(headers)
        request = urllib.request.Request(url, data=body, headers=request_headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                text = response.read().decode("utf-8")
                response_headers = response.headers
            if rate_gate is not None:
                rate_gate.complete(reservation, response_headers)
            parsed = json.loads(text) if text.strip() else {}
            if isinstance(parsed, Mapping):
                status = parsed.get("status")
                if status not in (None, "ok"):
                    raise RuntimeError(f"Request to {url} failed: {parsed}")
                return dict(parsed)
            raise RuntimeError(f"Unexpected JSON response from {url}: {parsed!r}")
        except urllib.error.HTTPError as exc:
            error_text = exc.read().decode("utf-8", errors="replace")
            last_error = RuntimeError(f"HTTP {exc.code} from {url}: {error_text}")
            exhausted = "credit_balance_exhausted" in error_text or "insufficient_quota" in error_text
            retryable = exc.code == 429 or exc.code >= 500
            if exhausted or not retryable or attempt == _EMBEDDING_REQUEST_RETRIES - 1:
                if rate_gate is not None:
                    rate_gate.release(reservation)
                raise last_error from exc
            if exc.code == 429:
                retry_delay = _rate_limit_retry_delay(exc, error_text, fallback=retry_delay)
                if rate_gate is not None:
                    rate_gate.rate_limited(reservation, exc.headers or {}, retry_delay)
            elif rate_gate is not None:
                rate_gate.release(reservation)
        except urllib.error.URLError as exc:
            if rate_gate is not None:
                rate_gate.release(reservation)
            last_error = RuntimeError(f"Request to {url} failed: {exc}")
            if attempt == _EMBEDDING_REQUEST_RETRIES - 1:
                raise last_error from exc
        except TimeoutError as exc:
            if rate_gate is not None:
                rate_gate.release(reservation)
            last_error = RuntimeError(f"Request to {url} timed out after {timeout_seconds} seconds.")
            if attempt == _EMBEDDING_REQUEST_RETRIES - 1:
                raise last_error from exc
        time.sleep(retry_delay)
    if last_error is not None:
        raise last_error
    raise RuntimeError(f"Request to {url} failed unexpectedly.")


def _rate_limit_retry_delay(exc: urllib.error.HTTPError, error_text: str, *, fallback: float) -> float:
    retry_after = exc.headers.get("Retry-After", "") if exc.headers is not None else ""
    try:
        if retry_after:
            return min(60.0, max(0.1, float(retry_after)))
    except ValueError:
        pass
    match = re.search(r"try again in\s+([0-9]+(?:\.[0-9]+)?)\s*(ms|s)", error_text, re.IGNORECASE)
    if match:
        delay = float(match.group(1))
        if match.group(2).lower() == "ms":
            delay /= 1000.0
        return min(60.0, max(0.1, delay + 0.25))
    return min(60.0, max(0.1, fallback))


def _estimated_embedding_tokens(value: str | Sequence[str]) -> int:
    values = (value,) if isinstance(value, str) else value
    character_estimate = sum(max(1, math.ceil(len(text) / 4)) for text in values)
    return max(1, math.ceil(character_estimate * _EMBEDDING_TOKEN_ESTIMATE_SAFETY_FACTOR))


def _integer_header(headers: Mapping[str, str], name: str) -> int | None:
    value = headers.get(name, "")
    try:
        return max(0, int(value)) if value else None
    except (TypeError, ValueError):
        return None


def _rate_limit_reset_seconds(value: str) -> float | None:
    if not value:
        return None
    matches = re.findall(r"([0-9]+(?:\.[0-9]+)?)(ms|s|m|h)", value.strip().lower())
    if not matches:
        return None
    multipliers = {"ms": 0.001, "s": 1.0, "m": 60.0, "h": 3600.0}
    return sum(float(amount) * multipliers[unit] for amount, unit in matches)


def _build_sparse_schema(index: BM25Index) -> SparseSchema:
    ordered_tokens = sorted(index.document_frequency.keys())
    token_to_index = {token: index for index, token in enumerate(ordered_tokens)}
    document_count = len(index.documents)
    idf_by_token: dict[str, float] = {}
    for token, doc_frequency in index.document_frequency.items():
        idf_by_token[token] = math.log(1 + (document_count - doc_frequency + 0.5) / (doc_frequency + 0.5))
    return SparseSchema(
        token_to_index=token_to_index,
        idf_by_token=idf_by_token,
        average_document_length=index.average_document_length,
        document_count=document_count,
        lexical_ranking_profile=index.lexical_ranking_profile,
        average_field_lengths=index.average_field_lengths,
    )


def _document_sparse_vector(
    document: BM25Document,
    *,
    token_to_index: Mapping[str, int],
    average_document_length: float,
    lexical_ranking_profile: str,
    average_field_lengths: Mapping[str, float],
) -> dict[str, list[float] | list[int]]:
    frequencies: Mapping[str, float]
    if is_bm25f_profile(lexical_ranking_profile):
        weighted: dict[str, float] = {}
        field_weights = bm25f_field_weights(lexical_ranking_profile)
        length_normalization = bm25f_field_length_normalization(lexical_ranking_profile)
        for field_name, field_weight in field_weights.items():
            field_tokens = document.fields.get(field_name, ())
            field_counts = Counter(field_tokens)
            b = length_normalization[field_name]
            average_length = max(average_field_lengths.get(field_name, 0.0), 1.0)
            normalization = 1.0 - b + b * len(field_tokens) / average_length
            for token, count in field_counts.items():
                weighted[token] = weighted.get(token, 0.0) + field_weight * count / max(normalization, 0.01)
        frequencies = weighted
        document_length = 0
    else:
        frequencies = Counter(document.tokens)
        document_length = len(document.tokens)
    indices: list[int] = []
    values: list[float] = []
    for token in sorted(frequencies):
        frequency = frequencies[token]
        denominator = (
            frequency + _BM25_K1
            if is_bm25f_profile(lexical_ranking_profile)
            else frequency + _BM25_K1 * (1 - _BM25_B + _BM25_B * document_length / max(average_document_length, 1.0))
        )
        weight = (frequency * (_BM25_K1 + 1)) / denominator
        indices.append(token_to_index[token])
        values.append(weight)
    return {"indices": indices, "values": values}


def _query_sparse_vector(query: str, schema: SparseSchema) -> dict[str, list[float] | list[int]]:
    query_weights = sparse_query_term_weights(query, schema.lexical_ranking_profile)
    indices: list[int] = []
    values: list[float] = []
    for token, query_weight in sorted(query_weights.items()):
        index = schema.token_to_index.get(token)
        if index is None:
            continue
        indices.append(index)
        values.append(float(query_weight) * schema.idf_by_token[token])
    return {"indices": indices, "values": values}


def _build_qdrant_filter(
    *,
    path: str,
    paths: Sequence[str],
    source_category: str,
    file_role: str,
) -> Mapping[str, Any] | None:
    must: list[Mapping[str, Any]] = []
    should: list[Mapping[str, Any]] = []
    if source_category:
        must.append({"key": "source_category", "match": {"value": source_category}})
    if file_role:
        must.append({"key": "file_role", "match": {"value": file_role}})
    normalized_path = path.replace("\\", "/").strip()
    if normalized_path:
        must.append({"key": "path", "match": {"value": normalized_path}})
    elif paths:
        for item in paths:
            normalized = str(item).replace("\\", "/").strip()
            if normalized:
                should.append({"key": "path", "match": {"value": normalized}})
    if not must and not should:
        return None
    filter_payload: dict[str, Any] = {}
    if must:
        filter_payload["must"] = must
    if should:
        filter_payload["should"] = should
    return filter_payload


def _chunk_payload(chunk: IndexedChunk) -> dict[str, Any]:
    metadata = dict(chunk.metadata)
    return {
        "chunk_id": chunk.chunk_id,
        "source_category": chunk.source_category.value,
        "snapshot": chunk.snapshot,
        "commit": chunk.commit,
        "path": chunk.path,
        "line_start": chunk.line_start,
        "line_end": chunk.line_end,
        "file_role": metadata.get("file_role", ""),
        "visibility": metadata.get("visibility", ""),
        "origin": metadata.get("origin", ""),
    }


def _chunk_embedding_text(chunk: IndexedChunk) -> str:
    basename = chunk.path.split("/")[-1]
    prefix = f"{chunk.path}\n{basename}\n"
    content_tokens = tokenize(chunk.text)
    if len(content_tokens) > _MAX_EMBEDDING_INPUT_TOKENS:
        content_text = " ".join(content_tokens[:_MAX_EMBEDDING_INPUT_TOKENS])
    else:
        content_text = chunk.text
    if len(content_text) > _MAX_EMBEDDING_INPUT_CHARS:
        content_text = content_text[:_MAX_EMBEDDING_INPUT_CHARS]
    return f"{prefix}{content_text}"


def _raise_if_rebuild_timed_out(deadline: float | None) -> None:
    if deadline is None or time.monotonic() <= deadline:
        return
    raise RuntimeError(
        "Qdrant indexing timed out before all repository chunks were embedded. "
        "The indexed directory set is too broad for this run; narrow indexed directories "
        "or add repo-specific indexing exclusions before retrying."
    )


def _embedding_cache_key(*, model: str, text: str) -> str:
    digest = hashlib.sha256()
    digest.update(model.encode("utf-8"))
    digest.update(b"\n")
    digest.update(text.encode("utf-8"))
    return digest.hexdigest()


def _encode_embedding_vector(vector: Sequence[float]) -> bytes:
    values = [float(value) for value in vector]
    return struct.pack(f"<{len(values)}f", *values)


def _decode_embedding_vector(payload: bytes) -> list[float]:
    if len(payload) % 4 != 0:
        raise RuntimeError("SQLite embedding cache contains a malformed vector payload.")
    return list(struct.unpack(f"<{len(payload) // 4}f", payload))


def _point_id_for_chunk_id(chunk_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))

