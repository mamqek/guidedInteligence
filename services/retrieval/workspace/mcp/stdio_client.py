from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


class MCPStdioError(RuntimeError):
    """Raised when a stdio MCP server cannot complete a JSON-RPC request."""


@dataclass(frozen=True)
class MCPServerCommand:
    command: str
    args: tuple[str, ...] = ()
    env: Mapping[str, str] | None = None
    cwd: str | None = None
    timeout_seconds: int = 20


class MCPStdioClient:
    """Minimal JSON-RPC client for query-time stdio MCP tool calls."""

    def __init__(
        self,
        *,
        command: str,
        args: Sequence[str] = (),
        env: Mapping[str, str] | None = None,
        cwd: str | None = None,
        timeout_seconds: int = 20,
    ) -> None:
        self.command = command
        self.args = tuple(args)
        self.env = dict(env or {})
        self.cwd = cwd
        self.timeout_seconds = timeout_seconds
        self._process: subprocess.Popen[str] | None = None
        self._next_id = 1

    def __enter__(self) -> "MCPStdioClient":
        self._start()
        self._initialize()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def call_tool(self, name: str, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        response = self._request(
            "tools/call",
            {
                "name": name,
                "arguments": dict(arguments),
            },
        )
        result = response.get("result")
        if not isinstance(result, Mapping):
            raise MCPStdioError(f"MCP tool {name!r} returned a non-object result.")
        return result

    def list_tools(self) -> tuple[Mapping[str, Any], ...]:
        response = self._request("tools/list", {})
        result = response.get("result")
        if not isinstance(result, Mapping):
            raise MCPStdioError("MCP tools/list returned a non-object result.")
        tools = result.get("tools", ())
        if not isinstance(tools, Sequence) or isinstance(tools, (str, bytes)):
            return ()
        return tuple(tool for tool in tools if isinstance(tool, Mapping))

    def close(self) -> None:
        process = self._process
        if process is None:
            return
        try:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)
        finally:
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream is not None:
                    try:
                        stream.close()
                    except OSError:
                        pass
            self._process = None

    def _start(self) -> None:
        if self._process is not None:
            return
        try:
            self._process = subprocess.Popen(
                [self.command, *self.args],
                cwd=self.cwd,
                env=None if not self.env else {**os.environ, **dict(self.env)},
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                bufsize=1,
            )
        except OSError as exc:
            raise MCPStdioError(f"Failed to start MCP server {self.command!r}: {exc}") from exc

    def _initialize(self) -> None:
        self._request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "guided-intelligence-retrieval", "version": "0.1"},
            },
        )
        self._notify("notifications/initialized", {})

    def _request(self, method: str, params: Mapping[str, Any]) -> Mapping[str, Any]:
        process = self._require_process()
        request_id = self._next_id
        self._next_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": dict(params),
        }
        self._write(payload)
        response = self._read_matching_response(request_id)
        error = response.get("error")
        if isinstance(error, Mapping):
            message = str(error.get("message", "MCP request failed"))
            raise MCPStdioError(message)
        if process.poll() is not None and "result" not in response:
            raise MCPStdioError(f"MCP server exited with code {process.returncode}.")
        return response

    def _notify(self, method: str, params: Mapping[str, Any]) -> None:
        self._write({"jsonrpc": "2.0", "method": method, "params": dict(params)})

    def _write(self, payload: Mapping[str, Any]) -> None:
        process = self._require_process()
        if process.stdin is None:
            raise MCPStdioError("MCP server stdin is unavailable.")
        process.stdin.write(json.dumps(dict(payload), separators=(",", ":")) + "\n")
        process.stdin.flush()

    def _read_matching_response(self, request_id: int) -> Mapping[str, Any]:
        process = self._require_process()
        if process.stdout is None:
            raise MCPStdioError("MCP server stdout is unavailable.")
        deadline = time.monotonic() + self.timeout_seconds
        while time.monotonic() < deadline:
            remaining = max(0.01, deadline - time.monotonic())
            line = self._readline_with_timeout(process.stdout, timeout=remaining)
            if line is None:
                break
            if not line:
                stderr = self._read_stderr_tail(process)
                raise MCPStdioError(f"MCP server closed stdout before response. {stderr}".strip())
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(message, Mapping) and message.get("id") == request_id:
                return message
        raise MCPStdioError(f"MCP request {request_id} timed out after {self.timeout_seconds}s.")

    def _require_process(self) -> subprocess.Popen[str]:
        if self._process is None:
            raise MCPStdioError("MCP server process is not started.")
        return self._process

    @staticmethod
    def _read_stderr_tail(process: subprocess.Popen[str]) -> str:
        if process.stderr is None:
            return ""
        try:
            return process.stderr.read(800)
        except OSError:
            return ""

    @staticmethod
    def _readline_with_timeout(stream: Any, *, timeout: float) -> str | None:
        output: queue.Queue[str] = queue.Queue(maxsize=1)

        def read_line() -> None:
            try:
                output.put(stream.readline())
            except OSError:
                output.put("")

        thread = threading.Thread(target=read_line, daemon=True)
        thread.start()
        try:
            return output.get(timeout=timeout)
        except queue.Empty:
            return None
