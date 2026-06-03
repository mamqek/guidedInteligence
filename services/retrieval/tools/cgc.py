from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from services.retrieval.config import WorkspaceRetrievalConfig
from services.retrieval.tools.contracts import ToolObservation, ToolRequest, ToolSpec


SAFE_CGC_SUBCOMMANDS = frozenset(
    {
        ("index",),
        ("find", "content"),
        ("find", "name"),
        ("analyze", "callers"),
        ("analyze", "calls"),
        ("list",),
        ("registry",),
    }
)
WINDOWS_LOCATION_PATTERN = re.compile(r"[A-Za-z]:\\[^\r\n|]+?\.[A-Za-z0-9_+-]+(?::\d+)?")


@dataclass(frozen=True)
class CGCCommandResult:
    command: tuple[str, ...]
    stdout: str
    stderr: str
    returncode: int


class CGCBaseTool:
    name: str

    def __init__(self, config: WorkspaceRetrievalConfig) -> None:
        self.config = config

    def _run_command(self, args: Sequence[str]) -> CGCCommandResult:
        command = tuple(self.config.cgc_command) + tuple(args)
        env = os.environ.copy()
        env.setdefault("COLUMNS", "400")
        env.setdefault("PYTHONIOENCODING", "utf-8")
        env.setdefault("PYTHONUTF8", "1")
        env["CGC_RUNTIME_DB_TYPE"] = "kuzudb"
        env["CGC_RUNTIME_DB_PATH"] = self.config.cgc_db_path
        completed = subprocess.run(
            list(command),
            cwd=str(Path(self.config.cgc_repo_path or self.config.workspace_root)),
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=self.config.cgc_timeout_seconds,
            env=env,
            check=False,
        )
        return CGCCommandResult(
            command=command,
            stdout=completed.stdout,
            stderr=completed.stderr,
            returncode=completed.returncode,
        )

    def _error_observation(self, result: CGCCommandResult | None, reason: str) -> ToolObservation:
        payload = {"reason": reason}
        metadata = {"result_count": "0"}
        if result is not None:
            payload.update(
                {
                    "command": list(result.command),
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "returncode": result.returncode,
                }
            )
            metadata["command"] = " ".join(result.command)
        return ToolObservation(tool_name=self.name, status="failed", payload=payload, metadata=metadata)


class CGCIndexRepoTool(CGCBaseTool):
    name = "cgc_index_repo"

    def run(self, request: ToolRequest) -> ToolObservation:
        repo_path = str(self.config.cgc_repo_path or self.config.workspace_root)
        try:
            result = self._run_command(["index", "--force", repo_path])
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            return self._error_observation(None, f"cgc_unavailable:{exc}")
        if _command_failed(result):
            return self._error_observation(result, "cgc_index_failed")
        return ToolObservation(
            tool_name=self.name,
            status="ok",
            payload={
                "command": list(result.command),
                "repo_path": repo_path,
                "forced": True,
                "stdout": result.stdout,
                "stderr": result.stderr,
            },
            metadata={"result_count": "1", "command": " ".join(result.command)},
        )


class CGCFindCodeTool(CGCBaseTool):
    name = "cgc_find_code"

    def run(self, request: ToolRequest) -> ToolObservation:
        query = str(request.arguments.get("query", "")).strip()
        args = ["find", "name" if _looks_like_symbol_query(query) else "content", query]
        try:
            result = self._run_command(args)
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            return self._error_observation(None, f"cgc_unavailable:{exc}")
        if _command_failed(result):
            return self._error_observation(result, "cgc_find_code_failed")
        files = _extract_files(_combined_output(result), workspace_root=self.config.workspace_root)
        return ToolObservation(
            tool_name=self.name,
            status="ok",
            payload={"query": query, "files": files, "command": list(result.command)},
            source_refs=tuple(str(item.get("path", "")) for item in files),
            metadata={"result_count": str(len(files)), "command": " ".join(result.command)},
        )


class CGCAnalyzeCallersTool(CGCBaseTool):
    name = "cgc_analyze_callers"

    def run(self, request: ToolRequest) -> ToolObservation:
        symbol = str(request.arguments.get("symbol", "")).strip()
        args = ["analyze", "callers", symbol]
        file_path = str(request.arguments.get("file", "")).strip()
        if file_path:
            args.extend(["--file", file_path])
        try:
            result = self._run_command(args)
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            return self._error_observation(None, f"cgc_unavailable:{exc}")
        if _command_failed(result):
            return self._error_observation(result, "cgc_analyze_callers_failed")
        files = _extract_files(_combined_output(result), workspace_root=self.config.workspace_root)
        return ToolObservation(
            tool_name=self.name,
            status="ok",
            payload={"symbol": symbol, "files": files, "command": list(result.command)},
            source_refs=tuple(str(item.get("path", "")) for item in files),
            metadata={"result_count": str(len(files)), "command": " ".join(result.command)},
        )


class CGCAnalyzeCalleesTool(CGCBaseTool):
    name = "cgc_analyze_callees"

    def run(self, request: ToolRequest) -> ToolObservation:
        symbol = str(request.arguments.get("symbol", "")).strip()
        args = ["analyze", "calls", symbol]
        file_path = str(request.arguments.get("file", "")).strip()
        if file_path:
            args.extend(["--file", file_path])
        try:
            result = self._run_command(args)
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            return self._error_observation(None, f"cgc_unavailable:{exc}")
        if _command_failed(result):
            return self._error_observation(result, "cgc_analyze_callees_failed")
        files = _extract_files(_combined_output(result), workspace_root=self.config.workspace_root)
        return ToolObservation(
            tool_name=self.name,
            status="ok",
            payload={"symbol": symbol, "files": files, "command": list(result.command)},
            source_refs=tuple(str(item.get("path", "")) for item in files),
            metadata={"result_count": str(len(files)), "command": " ".join(result.command)},
        )


class CGCAnalyzeDepsTool(CGCBaseTool):
    name = "cgc_analyze_deps"

    def run(self, request: ToolRequest) -> ToolObservation:
        path = str(request.arguments.get("path", "")).strip().replace("\\", "/")
        module = str(request.arguments.get("module", "")).strip()
        module_candidates = [module] if module else list(_module_candidates_for_path(path))
        if not module_candidates:
            return ToolObservation(
                tool_name=self.name,
                status="ok",
                payload={"path": path, "module_candidates": [], "mapping_status": "unresolved", "files": []},
                metadata={"result_count": "0"},
            )
        attempted_commands: list[list[str]] = []
        for module_name in module_candidates:
            args = ["analyze", "deps", module_name]
            try:
                result = self._run_command(args)
            except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
                return self._error_observation(None, f"cgc_unavailable:{exc}")
            attempted_commands.append(list(result.command))
            if _command_failed(result):
                continue
            files = _extract_files(_combined_output(result), workspace_root=self.config.workspace_root)
            if files:
                return ToolObservation(
                    tool_name=self.name,
                    status="ok",
                    payload={
                        "path": path,
                        "module_candidates": module_candidates,
                        "used_module": module_name,
                        "mapping_status": "resolved",
                        "files": files,
                        "command": list(result.command),
                    },
                    source_refs=tuple(str(item.get("path", "")) for item in files),
                    metadata={"result_count": str(len(files)), "command": " ".join(result.command)},
                )
        return ToolObservation(
            tool_name=self.name,
            status="ok",
            payload={
                "path": path,
                "module_candidates": module_candidates,
                "mapping_status": "ambiguous_unconfirmed" if len(module_candidates) > 1 else "no_dependency_hits",
                "files": [],
                "command_attempts": attempted_commands,
            },
            metadata={"result_count": "0"},
        )


class CGCQueryGraphTool(CGCBaseTool):
    name = "cgc_query_graph"

    def run(self, request: ToolRequest) -> ToolObservation:
        query = str(request.arguments.get("query", "")).strip()
        if not query:
            return ToolObservation(
                tool_name=self.name,
                status="rejected",
                payload={"reason": "empty_query"},
                metadata={"result_count": "0"},
            )
        args = ["query", query]
        context = str(request.arguments.get("context", "")).strip()
        if context:
            args = ["query", "--context", context, query]
        try:
            result = self._run_command(args)
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            return self._error_observation(None, f"cgc_unavailable:{exc}")
        if _command_failed(result):
            return self._error_observation(result, "cgc_query_graph_failed")
        rows = _extract_query_rows(_combined_output(result))
        return ToolObservation(
            tool_name=self.name,
            status="ok",
            payload={"query": query, "rows": rows, "command": list(result.command)},
            metadata={"result_count": str(len(rows)), "command": " ".join(result.command)},
        )


class CGCRunCliTool(CGCBaseTool):
    name = "cgc_run_cli"

    def run(self, request: ToolRequest) -> ToolObservation:
        subcommand = tuple(str(item).strip() for item in request.arguments.get("subcommand", ()) if str(item).strip())
        if not subcommand or subcommand not in SAFE_CGC_SUBCOMMANDS:
            return ToolObservation(
                tool_name=self.name,
                status="rejected",
                payload={
                    "reason": "unsupported_subcommand",
                    "allowed_subcommands": [list(value) for value in sorted(SAFE_CGC_SUBCOMMANDS)],
                },
                metadata={"result_count": "0"},
            )
        extra_args = [str(item) for item in request.arguments.get("args", ()) if str(item).strip()]
        try:
            result = self._run_command(list(subcommand) + extra_args)
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            return self._error_observation(None, f"cgc_unavailable:{exc}")
        if _command_failed(result):
            return self._error_observation(result, "cgc_cli_failed")
        files = _extract_files(_combined_output(result), workspace_root=self.config.workspace_root)
        return ToolObservation(
            tool_name=self.name,
            status="ok",
            payload={
                "subcommand": list(subcommand),
                "args": extra_args,
                "command": list(result.command),
                "stdout": result.stdout,
                "files": files,
            },
            source_refs=tuple(str(item.get("path", "")) for item in files),
            metadata={"result_count": str(len(files)), "command": " ".join(result.command)},
        )


def cgc_tool_specs() -> tuple[ToolSpec, ...]:
    return (
        ToolSpec(
            name="cgc_index_repo",
            title="CGC Index Repository",
            description=(
                "Run CodeGraphContext indexing before retrieval. This maps to `cgc index --force <repo>`. "
                "Use it first when the retrieval cycle begins so later CGC queries operate on a fresh code graph."
            ),
            arguments={},
            examples=(
                {
                    "tool_name": "cgc_index_repo",
                    "arguments": {},
                    "reason": "Refresh the code graph before structural narrowing.",
                },
            ),
        ),
        ToolSpec(
            name="cgc_find_code",
            title="CGC Find Code",
            description=(
                "Use CodeGraphContext first for broad structural narrowing. This maps to "
                "`cgc find name <symbol>` for symbol-like queries and `cgc find content <query>` for broader text "
                "queries. Prefer it before BM25 when you need likely files or symbol neighborhoods. After it returns "
                "files, use BM25 only inside those files."
            ),
            arguments={
                "query": "Required string. Symbol-like or keyword query for CGC structural narrowing.",
            },
            examples=(
                {
                    "tool_name": "cgc_find_code",
                    "arguments": {"query": "retry coordinator stage transition", "limit": 8},
                    "reason": "Use CGC first to narrow candidate files before BM25 snippet search.",
                },
            ),
        ),
        ToolSpec(
            name="cgc_analyze_callers",
            title="CGC Analyze Callers",
            description=(
                "Use when the question is about impact, call flow, or who uses a symbol. This maps to "
                "`cgc analyze callers <symbol>`. Prefer this over BM25 for caller tracing, then search inside the "
                "returned files with BM25 if you need exact snippets."
            ),
            arguments={
                "symbol": "Required string. Function, method, or symbol to trace callers for.",
                "file": "Optional file path to scope the caller analysis more tightly.",
            },
            examples=(
                {
                    "tool_name": "cgc_analyze_callers",
                    "arguments": {"symbol": "process_file", "all": True},
                    "reason": "Find who depends on a function before searching exact snippets.",
                },
            ),
        ),
        ToolSpec(
            name="cgc_analyze_callees",
            title="CGC Analyze Callees",
            description=(
                "Use when the question is about what a function calls or what execution path it expands into. "
                "This maps to `cgc analyze calls <symbol>`. Prefer this for flow questions before BM25."
            ),
            arguments={
                "symbol": "Required string. Function or method to trace callees for.",
                "file": "Optional file path to scope the callee analysis more tightly.",
            },
            examples=(
                {
                    "tool_name": "cgc_analyze_callees",
                    "arguments": {"symbol": "processInternationalPayment"},
                    "reason": "Trace downstream execution before reading snippets.",
                },
            ),
        ),
        ToolSpec(
            name="cgc_query_graph",
            title="CGC Query Graph",
            description=(
                "Execute a read-only Cypher query against the indexed code graph. Use this when file-to-file "
                "support depends on symbol-reference evidence that is not represented as import or call edges. "
                "Prefer this for confirming parser-to-types or checker-to-types structural links."
            ),
            arguments={
                "query": "Required read-only Cypher query string.",
                "context": "Optional explicit CGC context when the caller must override automatic repo resolution.",
            },
            examples=(
                {
                    "tool_name": "cgc_query_graph",
                    "arguments": {
                        "query": "MATCH (f:File)-[:CONTAINS]->(n) RETURN f.name, n.name LIMIT 10",
                    },
                    "reason": "Inspect the graph directly when wrapped analyses do not express the needed relation.",
                },
            ),
        ),
        ToolSpec(
            name="cgc_analyze_deps",
            title="CGC Analyze Dependencies",
            description=(
                "Use file-anchored dependency confirmation after you already have a plausible implementation file. "
                "This maps to `cgc analyze deps <module>` using path-to-module conversion when needed. Prefer this "
                "for representation and cross-role confirmation instead of symbol-level caller tracing."
            ),
            arguments={
                "path": "Repository-relative file path to convert into a CGC module target.",
                "module": "Optional explicit CGC module target when the caller already knows it.",
            },
            examples=(
                {
                    "tool_name": "cgc_analyze_deps",
                    "arguments": {"path": "src/compiler/parser.ts"},
                    "reason": "Confirm representation or checker files relative to an accepted parser anchor.",
                },
            ),
        ),
        ToolSpec(
            name="cgc_run_cli",
            title="CGC Raw CLI Escape Hatch",
            description=(
                "Restricted escape hatch for uncommon CGC queries. This is not arbitrary shell execution. "
                "Only safe CGC subcommands are allowed: `index`, `find content`, `find name`, `analyze callers`, "
                "`analyze calls`, `list`, and `registry`. Use wrapped CGC tools first. Use this only when the "
                "wrapped tools are insufficient."
            ),
            arguments={
                "subcommand": "Required list of CGC command tokens, such as ['find', 'code'] or ['list'].",
                "args": "Optional list of additional CLI arguments for the allowed subcommand.",
            },
            examples=(
                {
                    "tool_name": "cgc_run_cli",
                    "arguments": {"subcommand": ["list"], "args": []},
                    "reason": "Check which repositories CGC currently knows about.",
                },
                {
                    "tool_name": "cgc_run_cli",
                    "arguments": {"subcommand": ["find", "content"], "args": ["auth middleware"]},
                    "reason": "Fallback to a raw CGC query only if wrapped tools are too narrow.",
                },
            ),
        ),
    )


def _extract_files(stdout: str, *, workspace_root: str) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    root = Path(workspace_root).resolve()
    for match in WINDOWS_LOCATION_PATTERN.findall(stdout):
        entry = _file_entry_from_location(match, root)
        if entry is not None:
            files.append(entry)
    if files:
        return _dedupe_files(files)
    for line in stdout.splitlines():
        if "|" not in line:
            continue
        columns = [part.strip() for part in line.strip().strip("|").split("|")]
        if len(columns) < 3:
            continue
        location = columns[-1]
        entry = _file_entry_from_location(location, root)
        if entry is not None:
            files.append(entry)
    if files:
        return _dedupe_files(files)
    for line in stdout.splitlines():
        entry = _file_entry_from_location(line.strip(), root)
        if entry is not None:
            files.append(entry)
    return _dedupe_files(files)


def _parse_json(value: str) -> Any:
    value = value.strip()
    if not value:
        return {}
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {}


def _bounded_int(value: object, *, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def _command_failed(result: CGCCommandResult) -> bool:
    if result.returncode != 0:
        return True
    combined = _combined_output(result).lower()
    return "an error occurred" in combined or "no such option" in combined


def _looks_like_symbol_query(query: str) -> bool:
    token = query.strip()
    return bool(token) and " " not in token and any(character.isupper() for character in token)


def _module_candidates_for_path(path: str) -> tuple[str, ...]:
    normalized = path.strip().replace("\\", "/")
    if not normalized:
        return ()
    pure_path = Path(normalized)
    without_suffix = pure_path.with_suffix("").as_posix()
    parts = [part for part in Path(without_suffix).parts if part not in {".", ""}]
    candidates: list[str] = []
    if without_suffix:
        candidates.append(without_suffix)
    if parts:
        candidates.append(".".join(parts))
    if len(parts) > 1:
        candidates.append("/".join(parts[1:]))
        candidates.append(".".join(parts[1:]))
    if parts:
        candidates.append(parts[-1])
    ordered: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized_candidate = candidate.strip().strip("/")
        if not normalized_candidate or normalized_candidate in seen:
            continue
        seen.add(normalized_candidate)
        ordered.append(normalized_candidate)
    return tuple(ordered)


def _file_entry_from_location(location: str, workspace_root: Path) -> dict[str, Any] | None:
    value = location.strip()
    if not value or value.lower() == "location":
        return None
    line_number: int | None = None
    path_text = value
    if ":" in value:
        maybe_path, maybe_line = value.rsplit(":", 1)
        if maybe_line.isdigit():
            path_text = maybe_path
            line_number = int(maybe_line)
    path = Path(path_text)
    if not path.is_absolute():
        return None
    try:
        relative_path = path.resolve().relative_to(workspace_root)
    except ValueError:
        return None
    entry: dict[str, Any] = {"path": relative_path.as_posix()}
    if line_number is not None:
        entry["line"] = line_number
    return entry


def _dedupe_files(files: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, int | None]] = set()
    for item in files:
        path = str(item.get("path", "")).strip()
        line = item.get("line")
        key = (path, int(line) if isinstance(line, int) else None)
        if not path or key in seen:
            continue
        seen.add(key)
        entry = {"path": path}
        if key[1] is not None:
            entry["line"] = key[1]
        deduped.append(entry)
    return deduped


def _combined_output(result: CGCCommandResult) -> str:
    return f"{result.stdout}\n{result.stderr}"


def _extract_query_rows(stdout: str) -> list[dict[str, Any]]:
    start = stdout.find("[")
    end = stdout.rfind("]")
    if start == -1 or end <= start:
        return []
    try:
        payload = json.loads(stdout[start : end + 1])
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in payload:
        if isinstance(item, Mapping):
            rows.append(dict(item))
    return rows
