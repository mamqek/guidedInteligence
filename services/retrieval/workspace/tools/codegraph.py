from __future__ import annotations

import atexit
import json
import queue
import subprocess
import threading
import uuid
from pathlib import Path
from typing import Any, Mapping

from services.retrieval.config import WorkspaceRetrievalConfig
from services.retrieval.workspace.codegraph_config import (
    install_temporary_codegraph_excludes,
    restore_codegraph_config,
)
from services.retrieval.workspace.tools.contracts import ToolObservation, ToolRequest


BRIDGE_PATH = Path(__file__).resolve().parents[2] / "codegraph" / "workspace_graph.mjs"
_BRIDGES: dict[tuple[str, int], "CodeGraphBridge"] = {}
_BRIDGES_LOCK = threading.Lock()


class CodeGraphBridge:
    def __init__(self, config: WorkspaceRetrievalConfig) -> None:
        self.config = config
        self._process: subprocess.Popen[str] | None = None
        self._responses: queue.Queue[Mapping[str, Any] | None] = queue.Queue()
        self._stderr: list[str] = []
        self._lock = threading.Lock()
        atexit.register(self.close)

    def request(self, operation: str, arguments: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        with self._lock:
            config_snapshot = None
            if operation == "index":
                config_snapshot = install_temporary_codegraph_excludes(
                    Path(self.config.workspace_root).resolve(),
                    tuple(self.config.index_exclude_paths or ()),
                )
            try:
                process = self._ensure_process()
                request_id = uuid.uuid4().hex
                assert process.stdin is not None
                process.stdin.write(json.dumps({"id": request_id, "operation": operation, "arguments": dict(arguments or {})}) + "\n")
                process.stdin.flush()
                try:
                    response = self._responses.get(timeout=self.config.structural_graph_timeout_seconds or None)
                except queue.Empty as exc:
                    self.close()
                    raise TimeoutError(
                        f"CodeGraph {operation} did not complete within {self.config.structural_graph_timeout_seconds}s."
                    ) from exc
                if response is None:
                    detail = "\n".join(self._stderr[-20:]) or "bridge process exited"
                    raise RuntimeError(f"CodeGraph bridge stopped unexpectedly: {detail}")
                if response.get("id") != request_id:
                    raise RuntimeError("CodeGraph bridge returned an out-of-order response.")
                if not response.get("ok"):
                    raise RuntimeError(str(response.get("error") or "CodeGraph operation failed."))
                result = response.get("result")
                if not isinstance(result, Mapping):
                    raise RuntimeError("CodeGraph bridge returned a non-object result.")
                return result
            finally:
                if config_snapshot is not None:
                    restore_codegraph_config(config_snapshot)

    def close(self) -> None:
        process = self._process
        self._process = None
        if process is None or process.poll() is not None:
            return
        try:
            if process.stdin is not None:
                process.stdin.write(json.dumps({"id": uuid.uuid4().hex, "operation": "close", "arguments": {}}) + "\n")
                process.stdin.flush()
            process.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        finally:
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream is not None:
                    stream.close()

    def _ensure_process(self) -> subprocess.Popen[str]:
        if self._process is not None and self._process.poll() is None:
            return self._process
        workspace_root = Path(self.config.workspace_root).resolve()
        process = subprocess.Popen(
            ("node", str(BRIDGE_PATH), str(workspace_root)),
            cwd=str(Path(__file__).resolve().parents[4]),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        self._process = process
        threading.Thread(target=self._read_stdout, args=(process,), daemon=True).start()
        threading.Thread(target=self._read_stderr, args=(process,), daemon=True).start()
        return process

    def _read_stdout(self, process: subprocess.Popen[str]) -> None:
        assert process.stdout is not None
        for line in process.stdout:
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                self._stderr.append(f"non-JSON bridge output: {line.strip()}")
                continue
            self._responses.put(value if isinstance(value, Mapping) else None)
        self._responses.put(None)

    def _read_stderr(self, process: subprocess.Popen[str]) -> None:
        assert process.stderr is not None
        for line in process.stderr:
            self._stderr.append(line.rstrip())
            if len(self._stderr) > 100:
                del self._stderr[:-100]


class CodeGraphIndexRepoTool:
    name = "structural_index_repo"

    def __init__(self, bridge: CodeGraphBridge) -> None:
        self.bridge = bridge

    def run(self, request: ToolRequest) -> ToolObservation:
        try:
            result = self.bridge.request("index")
        except Exception as exc:
            return _error(self.name, f"structural_index_failed:{exc}")
        stats = result.get("stats") if isinstance(result.get("stats"), Mapping) else {}
        healthy = result.get("index_state") == "complete" and int(result.get("pending_references") or 0) == 0
        if not healthy:
            return _error(self.name, "structural_index_incomplete", payload=result)
        return ToolObservation(
            tool_name=self.name,
            status="ok",
            payload=dict(result),
            metadata={"result_count": str(stats.get("files") or stats.get("fileCount") or 0), "command": "codegraph embedded sync"},
        )


class CodeGraphFindExactSymbolTool:
    name = "structural_find_exact_symbol"

    def __init__(self, bridge: CodeGraphBridge) -> None:
        self.bridge = bridge

    def run(self, request: ToolRequest) -> ToolObservation:
        query = str(request.arguments.get("query") or "").strip()
        if not query:
            return _error(self.name, "empty_exact_symbol")
        try:
            result = self.bridge.request(
                "find_exact_symbol",
                {"query": query, "limit": int(request.arguments.get("limit") or 20)},
            )
        except Exception as exc:
            return _error(self.name, f"structural_exact_symbol_failed:{exc}")
        files = result.get("files") if isinstance(result.get("files"), list) else []
        return ToolObservation(
            tool_name=self.name,
            status="ok",
            payload=dict(result),
            source_refs=tuple(str(item.get("path") or "") for item in files if isinstance(item, Mapping)),
            metadata={"result_count": str(len(files)), "match": "exact_symbol"},
        )


class CodeGraphAnalyzeCallsTool:
    def __init__(self, bridge: CodeGraphBridge, *, direction: str) -> None:
        self.bridge = bridge
        self.direction = direction
        self.name = f"structural_{direction}"

    def run(self, request: ToolRequest) -> ToolObservation:
        path = str(request.arguments.get("file") or "").strip()
        line = int(request.arguments.get("line") or 0)
        if not path or line <= 0:
            return _error(self.name, "missing_source_location")
        try:
            result = self.bridge.request(
                self.direction,
                {"file": path, "line": line, "limit": 50},
            )
        except Exception as exc:
            return _error(self.name, f"structural_{self.direction}_failed:{exc}")
        files = result.get("files") if isinstance(result.get("files"), list) else []
        return ToolObservation(
            tool_name=self.name,
            status="ok",
            payload=dict(result),
            source_refs=tuple(str(item.get("path") or "") for item in files if isinstance(item, Mapping)),
            metadata={"result_count": str(len(files)), "relationship": self.direction},
        )


class CodeGraphRelationshipTool:
    name = "structural_relationship"

    def __init__(self, bridge: CodeGraphBridge) -> None:
        self.bridge = bridge

    def run(self, request: ToolRequest) -> ToolObservation:
        arguments = {
            "source_path": str(request.arguments.get("source_path") or ""),
            "target_path": str(request.arguments.get("target_path") or ""),
            "limit": 25,
        }
        try:
            result = self.bridge.request("relationship_between_files", arguments)
        except Exception as exc:
            return _error(self.name, f"structural_relationship_failed:{exc}")
        edges = result.get("edges") if isinstance(result.get("edges"), list) else []
        related = bool(edges or result.get("source_depends_on_target") or result.get("target_depends_on_source"))
        return ToolObservation(
            tool_name=self.name,
            status="ok",
            payload={**dict(result), "related": related},
            metadata={"result_count": str(len(edges)), "relationship": "verified_graph_edge"},
        )


def codegraph_tools(config: WorkspaceRetrievalConfig) -> tuple[dict[str, Any], CodeGraphBridge]:
    workspace_root = str(Path(config.workspace_root).resolve())
    key = (workspace_root.casefold(), int(config.structural_graph_timeout_seconds))
    with _BRIDGES_LOCK:
        bridge = _BRIDGES.get(key)
        if bridge is None:
            bridge = CodeGraphBridge(config)
            _BRIDGES[key] = bridge
    return (
        {
            "structural_index_repo": CodeGraphIndexRepoTool(bridge),
            "structural_find_exact_symbol": CodeGraphFindExactSymbolTool(bridge),
            "structural_callers": CodeGraphAnalyzeCallsTool(bridge, direction="callers"),
            "structural_callees": CodeGraphAnalyzeCallsTool(bridge, direction="callees"),
            "structural_relationship": CodeGraphRelationshipTool(bridge),
        },
        bridge,
    )


def close_codegraph_bridge(config: WorkspaceRetrievalConfig) -> None:
    workspace_root = str(Path(config.workspace_root).resolve())
    key = (workspace_root.casefold(), int(config.structural_graph_timeout_seconds))
    with _BRIDGES_LOCK:
        bridge = _BRIDGES.pop(key, None)
    if bridge is not None:
        bridge.close()


def _error(name: str, reason: str, *, payload: Mapping[str, Any] | None = None) -> ToolObservation:
    return ToolObservation(
        tool_name=name,
        status="failed",
        payload={"reason": reason, **dict(payload or {})},
        metadata={"result_count": "0"},
    )
