from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import uuid
from contextlib import closing
from pathlib import Path
from typing import Iterator, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.retrieval.workspace.qdrant_backend import _encode_embedding_vector


class _StreamingJsonReader:
    def __init__(self, path: Path, *, chunk_chars: int = 1024 * 1024) -> None:
        self._stream = path.open("r", encoding="utf-8")
        self._chunk_chars = chunk_chars
        self._buffer = ""
        self._position = 0
        self._eof = False
        self._decoder = json.JSONDecoder()

    def close(self) -> None:
        self._stream.close()

    def seek_text(self, marker: str) -> None:
        while True:
            index = self._buffer.find(marker, self._position)
            if index >= 0:
                self._position = index + len(marker)
                return
            if self._eof:
                raise ValueError(f"Embedding cache is missing {marker!r}.")
            keep = max(0, len(self._buffer) - len(marker) + 1)
            self._buffer = self._buffer[keep:]
            self._position = 0
            self._read_more()

    def skip_whitespace(self) -> None:
        while True:
            while self._position < len(self._buffer) and self._buffer[self._position].isspace():
                self._position += 1
            if self._position < len(self._buffer) or self._eof:
                return
            self._discard_consumed()
            self._read_more()

    def peek(self) -> str:
        self.skip_whitespace()
        if self._position >= len(self._buffer):
            raise ValueError("Unexpected end of embedding cache JSON.")
        return self._buffer[self._position]

    def expect(self, character: str) -> None:
        if self.peek() != character:
            raise ValueError(f"Expected {character!r} in embedding cache JSON.")
        self._position += 1

    def decode_value(self) -> object:
        self.skip_whitespace()
        self._discard_consumed()
        while True:
            try:
                value, end = self._decoder.raw_decode(self._buffer, self._position)
            except json.JSONDecodeError:
                if self._eof:
                    raise
                self._read_more()
                continue
            self._position = end
            return value

    def _discard_consumed(self) -> None:
        if self._position <= 0:
            return
        self._buffer = self._buffer[self._position :]
        self._position = 0

    def _read_more(self) -> None:
        chunk = self._stream.read(self._chunk_chars)
        if chunk:
            self._buffer += chunk
        else:
            self._eof = True


def iter_legacy_embedding_entries(path: Path) -> Iterator[tuple[str, Sequence[float]]]:
    reader = _StreamingJsonReader(path)
    try:
        reader.seek_text('"entries"')
        reader.expect(":")
        reader.expect("{")
        first = True
        while reader.peek() != "}":
            if not first:
                reader.expect(",")
            key = reader.decode_value()
            if not isinstance(key, str):
                raise ValueError("Embedding cache key must be a string.")
            reader.expect(":")
            vector = reader.decode_value()
            if not isinstance(vector, list):
                raise ValueError(f"Embedding cache entry {key} is not an array.")
            yield key, vector
            first = False
        reader.expect("}")
    finally:
        reader.close()


def migrate_cache(source: Path, destination: Path, *, batch_size: int = 500) -> int:
    if destination.exists():
        raise FileExistsError(f"Refusing to overwrite existing cache: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    migrated = 0
    try:
        with closing(sqlite3.connect(temporary)) as connection:
            connection.execute(
                "CREATE TABLE embeddings (cache_key TEXT PRIMARY KEY, vector BLOB NOT NULL)"
            )
            rows: list[tuple[str, bytes]] = []
            for cache_key, vector in iter_legacy_embedding_entries(source):
                rows.append((cache_key, _encode_embedding_vector(vector)))
                if len(rows) < batch_size:
                    continue
                connection.executemany(
                    "INSERT INTO embeddings(cache_key, vector) VALUES (?, ?)",
                    rows,
                )
                connection.commit()
                migrated += len(rows)
                rows.clear()
                if migrated % 5000 == 0:
                    print(f"Migrated {migrated} embeddings.", flush=True)
            if rows:
                connection.executemany(
                    "INSERT INTO embeddings(cache_key, vector) VALUES (?, ?)",
                    rows,
                )
                connection.commit()
                migrated += len(rows)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return migrated


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate a legacy JSON embedding cache to incremental SQLite.")
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    migrated = migrate_cache(args.source, args.destination)
    print(f"Migration complete: {migrated} embeddings -> {args.destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
