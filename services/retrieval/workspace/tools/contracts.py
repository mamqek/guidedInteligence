from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Protocol, Sequence


ALLOWED_TOOL_NAMES = frozenset(
    {
        "qdrant_hybrid_search",
        "codegraph_search",
        "open_file",
        "cgc_index_repo",
        "cgc_find_code",
        "cgc_analyze_callers",
        "cgc_analyze_callees",
        "cgc_query_graph",
        "cgc_analyze_deps",
        "cgc_run_cli",
    }
)


@dataclass(frozen=True)
class ToolSpec:
    name: str
    title: str
    description: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
    examples: Sequence[Mapping[str, Any]] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.name not in ALLOWED_TOOL_NAMES:
            raise ValueError(f"Unknown retrieval tool spec: {self.name}")

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["arguments"] = dict(self.arguments)
        data["examples"] = [dict(example) for example in self.examples]
        return data


@dataclass(frozen=True)
class ToolRequest:
    tool_name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
    reason: str = ""

    def __post_init__(self) -> None:
        if self.tool_name not in ALLOWED_TOOL_NAMES:
            raise ValueError(f"Unknown retrieval tool: {self.tool_name}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "ToolRequest":
        return cls(
            tool_name=str(data.get("tool_name", "")),
            arguments=dict(data.get("arguments", {})) if isinstance(data.get("arguments", {}), Mapping) else {},
            reason=str(data.get("reason", "")),
        )


@dataclass(frozen=True)
class ToolObservation:
    tool_name: str
    status: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    source_refs: Sequence[str] = field(default_factory=tuple)
    metadata: Mapping[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["source_refs"] = list(self.source_refs)
        data["metadata"] = dict(self.metadata)
        return data


class RetrievalTool(Protocol):
    name: str

    def run(self, request: ToolRequest) -> ToolObservation:
        ...
