from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


CANONICAL_FILE_PATTERN = re.compile(
    r"(?:canonical_file|canonical file|owner file|preferred file)\s*:\s*`?([A-Za-z0-9_./\\-]+\.[A-Za-z0-9_]+)`?",
    re.IGNORECASE,
)
PATH_PATTERN = re.compile(r"\b(?:src|lib|app|packages|core|services|testing|tests)/[A-Za-z0-9_./\\-]+\.[A-Za-z0-9_]+\b")


@dataclass(frozen=True)
class ObsidianSearchResult:
    path: str
    title: str
    snippet: str
    score: float
    content: str = ""
    metadata: Mapping[str, str] | None = None


class ObsidianSearchError(RuntimeError):
    pass


class ObsidianHybridSearchAdapter:
    """Thin CLI adapter around obsidian-hybrid-search.

    Obsidian owns note indexing. This adapter only consumes search/read output and
    converts matching notes into retrieval guidance.
    """

    def __init__(
        self,
        *,
        vault_path: str,
        command: Sequence[str],
        db_path: str | None = None,
        mode: str = "fulltext",
        timeout_seconds: int = 20,
    ) -> None:
        self.vault_path = Path(vault_path).resolve()
        self.command = tuple(command)
        self.db_path = str(Path(db_path or self.vault_path / ".obsidian-hybrid-search.db").resolve())
        self.mode = mode
        self.timeout_seconds = timeout_seconds

    def search(self, query: str, *, limit: int = 5) -> tuple[ObsidianSearchResult, ...]:
        if not self.vault_path.exists() or not self.command:
            return ()
        args = [
            *self.command,
            "--db",
            self.db_path,
            "search",
            query,
            "--mode",
            self.mode,
            "--limit",
            str(max(1, min(limit, 20))),
            "--json",
        ]
        raw_results = self._run_json(args)
        if not isinstance(raw_results, list):
            return ()
        results = tuple(self._result_from_mapping(item) for item in raw_results if isinstance(item, Mapping))
        if not results:
            return ()
        return self._hydrate_results(results)

    def _hydrate_results(self, results: Sequence[ObsidianSearchResult]) -> tuple[ObsidianSearchResult, ...]:
        paths = [result.path for result in results if result.path]
        if not paths:
            return tuple(results)
        args = [*self.command, "--db", self.db_path, "read", *paths, "--json"]
        try:
            raw_notes = self._run_json(args)
        except ObsidianSearchError:
            return tuple(results)
        notes_by_path: dict[str, str] = {}
        if isinstance(raw_notes, list):
            for item in raw_notes:
                if not isinstance(item, Mapping):
                    continue
                if item.get("found") is False:
                    continue
                path = str(item.get("path", "")).strip()
                content = str(item.get("content", "")).strip()
                if path and content:
                    notes_by_path[path] = content
        return tuple(
            ObsidianSearchResult(
                path=result.path,
                title=result.title,
                snippet=result.snippet,
                score=result.score,
                content=notes_by_path.get(result.path, result.content),
                metadata=result.metadata,
            )
            for result in results
        )

    def _run_json(self, args: Sequence[str]) -> object:
        completed = subprocess.run(
            list(args),
            cwd=str(self.vault_path),
            env={**os.environ, "OBSIDIAN_VAULT_PATH": str(self.vault_path)},
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=self.timeout_seconds,
            check=False,
        )
        if completed.returncode != 0:
            raise ObsidianSearchError((completed.stderr or completed.stdout).strip())
        try:
            return json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise ObsidianSearchError("obsidian-hybrid-search returned non-JSON output") from exc

    def _result_from_mapping(self, item: Mapping[str, object]) -> ObsidianSearchResult:
        return ObsidianSearchResult(
            path=str(item.get("path", "")).strip(),
            title=str(item.get("title", "")).strip(),
            snippet=str(item.get("snippet", "")).strip(),
            score=float(item.get("score", 0.0) or 0.0),
            metadata={"matched_by": ",".join(str(value) for value in item.get("matchedBy", []) if value)}
            if isinstance(item.get("matchedBy"), list)
            else {},
        )


def trusted_file_hints_from_obsidian_results(results: Sequence[ObsidianSearchResult]) -> tuple[str, ...]:
    hints: list[str] = []
    for result in results:
        text = "\n".join(part for part in (result.title, result.snippet, result.content) if part)
        hints.extend(match.group(1) for match in CANONICAL_FILE_PATTERN.finditer(text))
        hints.extend(PATH_PATTERN.findall(text))
    return tuple(_ordered_unique(_normalize_path(item) for item in hints if item))


def _normalize_path(value: str) -> str:
    return value.strip().strip("`'\"").replace("\\", "/")


def _ordered_unique(values: Sequence[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    selected: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        selected.append(value)
    return tuple(selected)
