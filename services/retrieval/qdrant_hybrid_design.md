# Qdrant Hybrid Retrieval Decisions

## Locked decisions

- Dense embeddings use the UVA OpenAI-compatible embeddings endpoint.
- Dense embedding model is `text-embedding-3-large`.
- `RETRIEVAL_ENABLE_INDEXING` is the single switch that controls whether fresh CGC/Qdrant indexing work is allowed.
- Embedding requests are sent in conservative batches to reduce transient proxy failures during repository sync.
- Current recommended embedding sync settings for the UVA proxy are `batch_size=16` and `concurrency=4`.
- Document embeddings are cached locally under the retrieval index directory so unchanged repositories do not need full re-embedding on every run.
- Qdrant sync now reuses the existing local collection when the indexed chunk signature matches the saved manifest.
- CGC forced reindexing is disabled for the CodeRepoQA snapshot harness so existing graph indexes can be reused across repeated runs.
- Sparse retrieval is moved into Qdrant as stored sparse vectors.
- Qdrant is mandatory at runtime; there is no fallback to the old local BM25 search path.
- CGC remains a separate structural layer for narrowing, graph confirmation, and anchor expansion.
- Chunking stays unchanged for the first version.

## Why Qdrant replaces the old backend

- Dense and sparse retrieval now live in one retrieval backend.
- Hybrid search uses Qdrant fusion instead of custom merge logic over separate lexical and semantic retrievers.
- Metadata filtering is pushed down into retrieval where possible.
- The old local BM25 JSON index is retained only as a local chunk store for `open_file` and repo sketching, not as the active search backend.

## Why CGC remains separate

- CGC is used for structural narrowing and graph-oriented confirmation.
- Qdrant is used for text/embedding retrieval over chunk payloads.
- These subsystems serve different purposes and are coordinated in the retrieval flow rather than merged.

## Chunking note

- Current chunk line count and overlap are preserved deliberately to reduce migration risk.
- Chunking may be revisited later to improve semantic retrieval quality, especially for function/class-aligned snippet selection.

## Local runtime

- Local Docker Qdrant is expected through `docker-compose.qdrant.yml`.
- Use a named Docker volume for Windows-friendly persistence.
