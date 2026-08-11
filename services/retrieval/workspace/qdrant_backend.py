from __future__ import annotations

import concurrent.futures
import hashlib
import json
import math
import time
import urllib.error
import urllib.request
import uuid
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from services.retrieval.workspace.bm25 import BM25Index, IndexedChunk, tokenize
from services.retrieval.config import RetrievalEmbeddingConfig, RetrievalQdrantConfig


QDRANT_DENSE_VECTOR_NAME = "dense"
QDRANT_SPARSE_VECTOR_NAME = "sparse"
_BM25_K1 = 1.5
_BM25_B = 0.75
_EMBEDDING_REQUEST_RETRIES = 5
_MAX_EMBEDDING_INPUT_TOKENS = 1200
_MAX_EMBEDDING_INPUT_CHARS = 4000
_EMBEDDING_CACHE_FLUSH_BATCHES = 1


@dataclass(frozen=True)
class QdrantSearchResult:
    chunk: IndexedChunk
    score: float
    matched_terms: tuple[str, ...]
    retrieval_path: str = "qdrant_hybrid_search"


@dataclass(frozen=True)
class SparseSchema:
    token_to_index: Mapping[str, int]
    idf_by_token: Mapping[str, float]
    average_document_length: float
    document_count: int


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
        self._sparse_schema = _build_sparse_schema(index)
        self._embedding_cache = self._load_embedding_cache()
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
        deadline = time.monotonic() + timeout_seconds if timeout_seconds is not None and timeout_seconds > 0 else None
        self.ensure_available()
        dense_batches = self._embed_documents(
            [document.chunk for document in self.index.documents],
            log_event=log_event,
            deadline=deadline,
        )
        _raise_if_rebuild_timed_out(deadline)
        dense_size = len(dense_batches[0][0]) if dense_batches and dense_batches[0] else 0
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
        documents = list(self.index.documents)
        point_batches: list[list[dict[str, Any]]] = []
        batch_size = self.embedding_config.batch_size
        for batch_start in range(0, len(documents), batch_size):
            batch_documents = documents[batch_start : batch_start + batch_size]
            batch_dense_vectors = dense_batches[batch_start // batch_size]
            points: list[dict[str, Any]] = []
            for document, dense_vector in zip(batch_documents, batch_dense_vectors):
                chunk = document.chunk
                sparse_vector = _document_sparse_vector(
                    document.tokens,
                    token_to_index=self._sparse_schema.token_to_index,
                    average_document_length=self._sparse_schema.average_document_length,
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
            point_batches.append(points)

        for batch in point_batches:
            _raise_if_rebuild_timed_out(deadline)
            self._request(
                "PUT",
                f"/collections/{self.qdrant_config.collection_name}/points?wait=true",
                {"points": batch},
            )
        return len(documents)

    def search(
        self,
        query: str,
        *,
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
        sparse_vector = _query_sparse_vector(query, self._sparse_schema)
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
        results = self._rows_to_results(rows, query=query, min_score=min_score)
        if include_breakdown:
            self._last_search_breakdown = {
                "sparse": self._search_single_vector(
                    query=query,
                    query_vector=sparse_vector,
                    vector_name=QDRANT_SPARSE_VECTOR_NAME,
                    qdrant_filter=qdrant_filter,
                    limit=limit,
                    min_score=min_score,
                ),
                "dense": self._search_single_vector(
                    query=query,
                    query_vector=dense_vector,
                    vector_name=QDRANT_DENSE_VECTOR_NAME,
                    qdrant_filter=qdrant_filter,
                    limit=limit,
                    min_score=min_score,
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
        return self._rows_to_results(rows, query=query, min_score=min_score)

    def _rows_to_results(
        self,
        rows: Iterable[Any],
        *,
        query: str,
        min_score: float,
    ) -> tuple[QdrantSearchResult, ...]:
        results: list[QdrantSearchResult] = []
        query_terms = set(tokenize(query))
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            point_id = str(row.get("id", ""))
            chunk = self._chunks_by_point_id.get(point_id)
            if chunk is None:
                continue
            score = float(row.get("score", 0.0) or 0.0)
            if score < min_score:
                continue
            matched_terms = tuple(sorted(query_terms.intersection(tokenize(chunk.text))))
            results.append(QdrantSearchResult(chunk=chunk, score=score, matched_terms=matched_terms))
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

        for index, text in enumerate(texts):
            cache_key = _embedding_cache_key(model=self.embedding_config.model, text=text)
            cached_vector = self._embedding_cache.get(cache_key)
            if cached_vector is not None:
                dense_vectors[index] = cached_vector
            else:
                uncached_positions.append(index)
                uncached_inputs.append(text)

        pending_batches: list[tuple[int, list[str]]] = []
        for batch_start in range(0, len(uncached_inputs), batch_size):
            pending_batches.append((batch_start, uncached_inputs[batch_start : batch_start + batch_size]))

        if pending_batches:
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.embedding_config.concurrency) as executor:
                pending_iter = iter(pending_batches)
                in_flight: dict[concurrent.futures.Future[list[list[float]]], tuple[int, list[str]]] = {}
                completed_since_flush = 0

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
                    future = executor.submit(self._embedding_request, batch_inputs)
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
                        text = batch_inputs[offset]
                        cache_key = _embedding_cache_key(model=self.embedding_config.model, text=text)
                        dense_vectors[position] = vector
                        self._embedding_cache[cache_key] = vector
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
                    if completed_since_flush >= _EMBEDDING_CACHE_FLUSH_BATCHES:
                        self._save_embedding_cache()
                        completed_since_flush = 0
                    submit_next()
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

    def _save_embedding_cache(self) -> None:
        if self.cache_path is None:
            return
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "model": self.embedding_config.model,
            "entries": self._embedding_cache,
        }
        self.cache_path.write_text(json.dumps(payload), encoding="utf-8")


def _json_request(
    *,
    url: str,
    method: str,
    timeout_seconds: int,
    payload: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
) -> Mapping[str, Any]:
    last_error: Exception | None = None
    for attempt in range(_EMBEDDING_REQUEST_RETRIES):
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request_headers = {"Content-Type": "application/json"}
        if headers:
            request_headers.update(headers)
        request = urllib.request.Request(url, data=body, headers=request_headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                text = response.read().decode("utf-8")
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
            if exc.code < 500 or attempt == _EMBEDDING_REQUEST_RETRIES - 1:
                raise last_error from exc
        except urllib.error.URLError as exc:
            last_error = RuntimeError(f"Request to {url} failed: {exc}")
            if attempt == _EMBEDDING_REQUEST_RETRIES - 1:
                raise last_error from exc
        except TimeoutError as exc:
            last_error = RuntimeError(f"Request to {url} timed out after {timeout_seconds} seconds.")
            if attempt == _EMBEDDING_REQUEST_RETRIES - 1:
                raise last_error from exc
        time.sleep(min(8.0, 1.25 * (2**attempt)))
    if last_error is not None:
        raise last_error
    raise RuntimeError(f"Request to {url} failed unexpectedly.")


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
    )


def _document_sparse_vector(
    tokens: Sequence[str],
    *,
    token_to_index: Mapping[str, int],
    average_document_length: float,
) -> dict[str, list[float] | list[int]]:
    frequencies = Counter(tokens)
    document_length = len(tokens)
    indices: list[int] = []
    values: list[float] = []
    for token in sorted(frequencies):
        frequency = frequencies[token]
        denominator = frequency + _BM25_K1 * (1 - _BM25_B + _BM25_B * document_length / max(average_document_length, 1.0))
        weight = (frequency * (_BM25_K1 + 1)) / denominator
        indices.append(token_to_index[token])
        values.append(weight)
    return {"indices": indices, "values": values}


def _query_sparse_vector(query: str, schema: SparseSchema) -> dict[str, list[float] | list[int]]:
    query_counts = Counter(tokenize(query))
    indices: list[int] = []
    values: list[float] = []
    for token, count in sorted(query_counts.items()):
        index = schema.token_to_index.get(token)
        if index is None:
            continue
        indices.append(index)
        values.append(float(count) * schema.idf_by_token[token])
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


def _point_id_for_chunk_id(chunk_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))

