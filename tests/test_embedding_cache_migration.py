import json
import sqlite3
import unittest
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from services.retrieval.workspace.qdrant_backend import _decode_embedding_vector
from testing.codeRepoQA.migrate_embedding_cache import migrate_cache


class EmbeddingCacheMigrationTests(unittest.TestCase):
    def test_migrates_legacy_json_without_overwriting_destination(self) -> None:
        with TemporaryDirectory() as root:
            directory = Path(root)
            source = directory / "cache.json"
            destination = directory / "cache.sqlite3"
            source.write_text(
                json.dumps(
                    {
                        "model": "embedding-test",
                        "entries": {
                            "a" * 64: [0.1, 0.2],
                            "b" * 64: [0.3, 0.4],
                        },
                    }
                ),
                encoding="utf-8",
            )

            migrated = migrate_cache(source, destination, batch_size=1)

            self.assertEqual(migrated, 2)
            with closing(sqlite3.connect(destination)) as connection:
                rows = connection.execute(
                    "SELECT cache_key, vector FROM embeddings ORDER BY cache_key"
                ).fetchall()
            self.assertEqual([row[0] for row in rows], ["a" * 64, "b" * 64])
            self.assertAlmostEqual(_decode_embedding_vector(rows[0][1])[0], 0.1, places=6)
            with self.assertRaises(FileExistsError):
                migrate_cache(source, destination)


if __name__ == "__main__":
    unittest.main()
