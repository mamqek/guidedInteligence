from __future__ import annotations

import atexit
from concurrent.futures import ThreadPoolExecutor, as_completed
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
from services.retrieval.workspace.source_ast import SourceAstRouter


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


class CodeGraphResolveLocationsTool:
    name = "structural_resolve_locations"

    def __init__(self, bridge: CodeGraphBridge) -> None:
        self.bridge = bridge

    def run(self, request: ToolRequest) -> ToolObservation:
        locations = request.arguments.get("locations")
        if not isinstance(locations, list) or not locations:
            return _error(self.name, "empty_locations")
        try:
            result = self.bridge.request("resolve_locations", {"locations": locations[:80]})
        except Exception as exc:
            return _error(self.name, f"structural_location_resolution_failed:{exc}")
        results = result.get("results") if isinstance(result.get("results"), list) else []
        node_count = sum(len(item.get("nodes", ())) for item in results if isinstance(item, Mapping))
        return ToolObservation(
            tool_name=self.name,
            status="ok",
            payload=dict(result),
            metadata={"result_count": str(node_count), "match": "source_location"},
        )


class CodeGraphResolveRangesTool:
    name = "structural_resolve_ranges"
    batch_size = 80

    def __init__(self, bridge: CodeGraphBridge, *, bridge_factory: Any = CodeGraphBridge) -> None:
        self.bridge = bridge
        self._bridge_factory = bridge_factory

    def run(self, request: ToolRequest) -> ToolObservation:
        ranges = request.arguments.get("ranges")
        if not isinstance(ranges, list) or not ranges:
            return _error(self.name, "empty_ranges")
        batches = [ranges[index : index + self.batch_size] for index in range(0, len(ranges), self.batch_size)]
        batch_results: list[Mapping[str, Any] | None] = [None] * len(batches)
        temporary_bridges: list[CodeGraphBridge] = []

        def resolve(batch_index: int) -> tuple[int, Mapping[str, Any]]:
            bridge = self.bridge
            if batch_index > 0:
                bridge = self._bridge_factory(self.bridge.config)
                temporary_bridges.append(bridge)
            return batch_index, bridge.request("resolve_ranges", {"ranges": batches[batch_index]})

        try:
            # CodeGraph's stdin bridge intentionally serializes requests. Separate
            # read-only bridge processes make the batches genuinely concurrent.
            with ThreadPoolExecutor(max_workers=len(batches), thread_name_prefix="codegraph-ranges") as executor:
                futures = [executor.submit(resolve, index) for index in range(len(batches))]
                for future in as_completed(futures):
                    batch_index, batch_result = future.result()
                    batch_results[batch_index] = batch_result
        except Exception as exc:
            return _error(
                self.name,
                f"structural_range_resolution_failed:{exc}",
                payload={
                    "submitted_range_count": len(ranges),
                    "batch_count": len(batches),
                    "batch_size": self.batch_size,
                },
            )
        finally:
            for bridge in temporary_bridges:
                bridge.close()

        if any(result is None for result in batch_results):
            return _error(self.name, "structural_range_resolution_incomplete_batch")
        combined_results = [
            item
            for batch_result in batch_results
            for item in batch_result.get("results", ())  # type: ignore[union-attr]
            if isinstance(item, Mapping)
        ]
        result = dict(batch_results[0] or {})
        result["results"] = combined_results
        result["batch_diagnostics"] = {
            "submitted_range_count": len(ranges),
            "processed_range_count": sum(len(batch) for batch in batches),
            "returned_range_count": len(combined_results),
            "batch_count": len(batches),
            "batch_size": self.batch_size,
            "batch_range_counts": [len(batch) for batch in batches],
            "parallel": len(batches) > 1,
            "complete": len(combined_results) == len(ranges),
        }
        results = result.get("results") if isinstance(result.get("results"), list) else []
        node_count = sum(len(item.get("nodes", ())) for item in results if isinstance(item, Mapping))
        return ToolObservation(
            tool_name=self.name,
            status="ok",
            payload=dict(result),
            metadata={
                "result_count": str(node_count),
                "match": "source_range",
                "submitted_range_count": str(len(ranges)),
                "returned_range_count": str(len(results)),
                "batch_count": str(len(batches)),
                "batch_size": str(self.batch_size),
                "parallel": str(len(batches) > 1).lower(),
                "complete": str(len(results) == len(ranges)).lower(),
            },
        )


class CodeGraphExpandNodesTool:
    name = "structural_expand_nodes"

    def __init__(self, bridge: CodeGraphBridge) -> None:
        self.bridge = bridge

    def run(self, request: ToolRequest) -> ToolObservation:
        node_ids = request.arguments.get("node_ids")
        if not isinstance(node_ids, list) or not node_ids:
            return _error(self.name, "empty_node_ids")
        try:
            result = self.bridge.request(
                "expand_nodes",
                {
                    "node_ids": node_ids[:80],
                    "depth": int(request.arguments.get("depth") or 1),
                    "limit": int(request.arguments.get("limit") or 120),
                },
            )
        except Exception as exc:
            return _error(self.name, f"structural_node_expansion_failed:{exc}")
        nodes = result.get("nodes") if isinstance(result.get("nodes"), list) else []
        edges = result.get("edges") if isinstance(result.get("edges"), list) else []
        return ToolObservation(
            tool_name=self.name,
            status="ok",
            payload=dict(result),
            metadata={"result_count": str(len(nodes)), "edge_count": str(len(edges))},
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


class CodeGraphFileNeighborsTool:
    name = "structural_file_neighbors"

    def __init__(self, bridge: CodeGraphBridge) -> None:
        self.bridge = bridge

    def run(self, request: ToolRequest) -> ToolObservation:
        paths = request.arguments.get("paths")
        if not isinstance(paths, list) or not paths:
            return _error(self.name, "empty_paths")
        try:
            result = self.bridge.request(
                "file_neighbors",
                {
                    "paths": [str(path) for path in paths[:8]],
                    "limit": int(request.arguments.get("limit") or 20),
                },
            )
        except Exception as exc:
            return _error(self.name, f"structural_file_neighbors_failed:{exc}")
        neighbors = result.get("neighbors") if isinstance(result.get("neighbors"), list) else []
        return ToolObservation(
            tool_name=self.name,
            status="ok",
            payload=dict(result),
            source_refs=tuple(str(item.get("path") or "") for item in neighbors if isinstance(item, Mapping)),
            metadata={"result_count": str(len(neighbors)), "relationship": "file_neighbors"},
        )


class CodeGraphFileOutlineTool:
    name = "structural_file_outline"

    def __init__(self, bridge: CodeGraphBridge) -> None:
        self.bridge = bridge

    def run(self, request: ToolRequest) -> ToolObservation:
        path = str(request.arguments.get("path") or "").strip().replace("\\", "/")
        if not path:
            return _error(self.name, "empty_path")
        try:
            result = self.bridge.request(
                "file_outline",
                {
                    "path": path,
                    "max_entries": int(request.arguments.get("max_entries") or 120),
                    "line_start": int(request.arguments.get("line_start") or 0),
                    "line_end": int(request.arguments.get("line_end") or 0),
                },
            )
        except Exception as exc:
            return _error(self.name, f"structural_file_outline_failed:{exc}")
        nodes = result.get("nodes") if isinstance(result.get("nodes"), list) else []
        return ToolObservation(
            tool_name=self.name,
            status="ok",
            payload=dict(result),
            source_refs=(path,),
            metadata={"result_count": str(len(nodes)), "match": "file_outline"},
        )


class CodeGraphResolveFileNodesTool:
    name = "structural_resolve_file_nodes"

    def __init__(self, bridge: CodeGraphBridge) -> None:
        self.bridge = bridge

    def run(self, request: ToolRequest) -> ToolObservation:
        paths = request.arguments.get("paths")
        if not isinstance(paths, list) or not paths:
            return _error(self.name, "empty_paths")
        try:
            result = self.bridge.request(
                "resolve_file_nodes",
                {"paths": [str(path).strip().replace("\\", "/") for path in paths[:16] if str(path).strip()]},
            )
        except Exception as exc:
            return _error(self.name, f"structural_resolve_file_nodes_failed:{exc}")
        nodes = result.get("nodes") if isinstance(result.get("nodes"), list) else []
        return ToolObservation(
            tool_name=self.name,
            status="ok",
            payload=dict(result),
            source_refs=tuple(str(item.get("path") or "") for item in nodes if isinstance(item, Mapping)),
            metadata={"result_count": str(len(nodes)), "match": "file_node"},
        )


class CodeGraphRelationshipsWithinNodesTool:
    name = "structural_relationships_within_nodes"

    def __init__(self, bridge: CodeGraphBridge) -> None:
        self.bridge = bridge

    def run(self, request: ToolRequest) -> ToolObservation:
        node_ids = request.arguments.get("node_ids")
        if not isinstance(node_ids, list) or not node_ids:
            return _error(self.name, "empty_node_ids")
        edge_kinds = request.arguments.get("edge_kinds")
        arguments: dict[str, Any] = {"node_ids": [str(value) for value in node_ids[:80]]}
        if isinstance(edge_kinds, list):
            arguments["edge_kinds"] = [str(value) for value in edge_kinds if str(value)]
        connector_edge_kinds = request.arguments.get("connector_edge_kinds")
        if isinstance(connector_edge_kinds, list):
            arguments["connector_edge_kinds"] = [
                str(value) for value in connector_edge_kinds if str(value)
            ]
        try:
            result = self.bridge.request("relationships_within_nodes", arguments)
        except Exception as exc:
            return _error(self.name, f"structural_closed_relationships_failed:{exc}")
        edges = result.get("edges") if isinstance(result.get("edges"), list) else []
        connector_paths = (
            result.get("connector_paths") if isinstance(result.get("connector_paths"), list) else []
        )
        return ToolObservation(
            tool_name=self.name,
            status="ok",
            payload=dict(result),
            metadata={
                "result_count": str(len(edges)),
                "connector_path_count": str(len(connector_paths)),
                "relationship": "closed_set",
            },
        )


class SourceOwnerCallsTool:
    name = "structural_source_owner_calls"

    def __init__(self, config: WorkspaceRetrievalConfig, bridge: CodeGraphBridge) -> None:
        self.router = SourceAstRouter(config.workspace_root, codegraph_bridge=bridge)

    def run(self, request: ToolRequest) -> ToolObservation:
        node = request.arguments.get("node")
        if not isinstance(node, Mapping) or not str(node.get("id") or ""):
            return _error(self.name, "missing_source_node")
        try:
            result = self.router.source_owner_calls(node)
        except Exception as exc:
            return _error(self.name, f"source_ast_adapter_failed:{exc}")
        status = str(result.get("status") or "")
        calls = result.get("calls") if isinstance(result.get("calls"), list) else []
        return ToolObservation(
            tool_name=self.name,
            status="ok" if status in {"ok", "unsupported"} else "failed",
            payload=dict(result),
            source_refs=(str(node.get("path") or ""),),
            metadata={
                "adapter": str(result.get("adapter") or "unsupported"),
                "result_count": str(len(calls)),
                "match": "source_owner_calls",
            },
        )


class CodeGraphEdgeCapabilitiesTool:
    name = "structural_edge_capabilities"

    def __init__(self, bridge: CodeGraphBridge) -> None:
        self.bridge = bridge

    def run(self, request: ToolRequest) -> ToolObservation:
        node_ids = request.arguments.get("node_ids")
        if not isinstance(node_ids, list) or not node_ids:
            return _error(self.name, "empty_node_ids")
        try:
            result = self.bridge.request("edge_capabilities", {"node_ids": [str(value) for value in node_ids[:16]]})
        except Exception as exc:
            return _error(self.name, f"structural_edge_capabilities_failed:{exc}")
        nodes = result.get("nodes") if isinstance(result.get("nodes"), list) else []
        return ToolObservation(
            tool_name=self.name,
            status="ok",
            payload=dict(result),
            metadata={"result_count": str(len(nodes)), "relationship": "edge_capabilities"},
        )


class CodeGraphExpandRelationshipsTool:
    name = "structural_expand_relationships"

    def __init__(self, bridge: CodeGraphBridge) -> None:
        self.bridge = bridge

    def run(self, request: ToolRequest) -> ToolObservation:
        node_ids = request.arguments.get("node_ids")
        edge_kinds = request.arguments.get("edge_kinds")
        direction = str(request.arguments.get("direction") or "")
        if not isinstance(node_ids, list) or not node_ids:
            return _error(self.name, "empty_node_ids")
        if direction not in {"incoming", "outgoing"}:
            return _error(self.name, "invalid_direction")
        if not isinstance(edge_kinds, list) or not edge_kinds:
            return _error(self.name, "empty_edge_kinds")
        try:
            result = self.bridge.request(
                "expand_relationships",
                {
                    "node_ids": [str(value) for value in node_ids[:16]],
                    "direction": direction,
                    "edge_kinds": [str(value) for value in edge_kinds if str(value)],
                    "target_symbols": [
                        str(value) for value in request.arguments.get("target_symbols", ()) if str(value)
                    ][:12],
                    "target_terms": [
                        str(value) for value in request.arguments.get("target_terms", ()) if str(value)
                    ][:32],
                    "cross_file_only": bool(request.arguments.get("cross_file_only")),
                    "limit": int(request.arguments.get("limit") or 3),
                },
            )
        except Exception as exc:
            return _error(self.name, f"structural_relationship_expansion_failed:{exc}")
        nodes = result.get("nodes") if isinstance(result.get("nodes"), list) else []
        edges = result.get("edges") if isinstance(result.get("edges"), list) else []
        return ToolObservation(
            tool_name=self.name,
            status="ok",
            payload=dict(result),
            source_refs=tuple(str(item.get("path") or "") for item in nodes if isinstance(item, Mapping)),
            metadata={"result_count": str(len(nodes)), "edge_count": str(len(edges))},
        )


class CodeGraphQualifiedReferencesTool:
    name = "structural_qualified_references"

    def __init__(self, bridge: CodeGraphBridge) -> None:
        self.bridge = bridge

    def run(self, request: ToolRequest) -> ToolObservation:
        paths = request.arguments.get("paths")
        if not isinstance(paths, list) or not paths:
            return _error(self.name, "empty_source_paths")
        try:
            result = self.bridge.request(
                "qualified_references",
                {
                    "paths": paths[:12],
                    "limit": int(request.arguments.get("limit") or 40),
                    "exclude_paths": list(self.bridge.config.index_exclude_paths or ()),
                },
            )
        except Exception as exc:
            return _error(self.name, f"structural_qualified_references_failed:{exc}")
        nodes = result.get("nodes") if isinstance(result.get("nodes"), list) else []
        return ToolObservation(
            tool_name=self.name,
            status="ok",
            payload=dict(result),
            source_refs=tuple(
                dict.fromkeys(str(item.get("path") or "") for item in nodes if isinstance(item, Mapping))
            ),
            metadata={"result_count": str(len(nodes)), "relationship": "qualified_reference"},
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
            "structural_resolve_locations": CodeGraphResolveLocationsTool(bridge),
            "structural_resolve_ranges": CodeGraphResolveRangesTool(bridge),
            "structural_file_outline": CodeGraphFileOutlineTool(bridge),
            "structural_resolve_file_nodes": CodeGraphResolveFileNodesTool(bridge),
            "structural_relationships_within_nodes": CodeGraphRelationshipsWithinNodesTool(bridge),
            "structural_source_owner_calls": SourceOwnerCallsTool(config, bridge),
            "structural_edge_capabilities": CodeGraphEdgeCapabilitiesTool(bridge),
            "structural_expand_relationships": CodeGraphExpandRelationshipsTool(bridge),
            "structural_expand_nodes": CodeGraphExpandNodesTool(bridge),
            "structural_callers": CodeGraphAnalyzeCallsTool(bridge, direction="callers"),
            "structural_callees": CodeGraphAnalyzeCallsTool(bridge, direction="callees"),
            "structural_file_neighbors": CodeGraphFileNeighborsTool(bridge),
            "structural_qualified_references": CodeGraphQualifiedReferencesTool(bridge),
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
