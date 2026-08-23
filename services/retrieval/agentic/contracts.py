from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class AgentObligation:
    id: str
    description: str
    required: bool = True
    anchors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RetrievalView:
    channel: str
    query_id: str
    obligation_ids: tuple[str, ...] = ()
    ranks: tuple[int, ...] = ()
    scores: tuple[float, ...] = ()


@dataclass(frozen=True)
class StructuralHandle:
    node_id: str
    symbol: str
    path: str
    line_start: int
    line_end: int
    kind: str = ""


@dataclass(frozen=True)
class InitialLead:
    id: str
    path: str
    line_start: int
    line_end: int
    preview: str
    artifact_kind: str
    obligation_ids: tuple[str, ...] = ()
    retrieval_views: tuple[RetrievalView, ...] = ()
    structural_handles: tuple[StructuralHandle, ...] = ()

    def to_dict(self, *, include_preview: bool = True) -> dict[str, Any]:
        value = asdict(self)
        if not include_preview:
            value.pop("preview", None)
        return value


@dataclass(frozen=True)
class AgentScope:
    excluded_paths: tuple[str, ...] = ()
    allowed_source_kinds: tuple[str, ...] = ("source_code", "documentation", "tests", "config")
    dense_search_enabled: bool = True


@dataclass(frozen=True)
class AgentBudget:
    max_iterations: int = 8
    max_tool_calls: int = 20
    max_tool_calls_per_iteration: int = 3
    max_context_chars: int = 30000
    max_source_lines: int = 120
    max_no_gain_iterations: int = 2


@dataclass(frozen=True)
class AgentRetrievalRequest:
    request_id: str
    question: str
    workspace_root: str
    obligations: tuple[AgentObligation, ...]
    initial_leads: tuple[InitialLead, ...]
    scope: AgentScope
    budget: AgentBudget


@dataclass
class ArtifactRecord:
    id: str
    path: str
    line_start: int
    line_end: int
    source_text: str
    symbol: str = ""
    artifact_kind: str = "other"
    obligation_ids: tuple[str, ...] = ()
    node_id: str = ""
    discovery_origin: str = "initial_lead"
    parent_ids: tuple[str, ...] = ()
    inspected: bool = False
    status: str = "uninspected"

    def summary(self, *, preview_chars: int = 240) -> dict[str, Any]:
        compact = " ".join(self.source_text.split())[:preview_chars]
        return {
            "id": self.id,
            "path": self.path,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "symbol": self.symbol,
            "artifact_kind": self.artifact_kind,
            "obligation_ids": list(self.obligation_ids),
            "origin": self.discovery_origin,
            "inspected": self.inspected,
            "status": self.status,
            "preview": compact,
        }


@dataclass(frozen=True)
class AgentToolCall:
    tool: str
    purpose: str
    expected_signal: str = ""
    lead_id: str = ""
    path: str = ""
    line_start: int = 0
    line_end: int = 0
    node_id: str = ""
    direction: str = "outgoing"
    query: str = ""
    limit: int = 12

    def fingerprint(self) -> str:
        return "|".join(
            str(value).casefold()
            for value in (
                self.tool, self.lead_id, self.path, self.line_start, self.line_end,
                self.node_id, self.direction, self.query, self.limit,
            )
        )


@dataclass(frozen=True)
class ProposedFinding:
    statement: str
    evidence_ids: tuple[str, ...]
    obligation_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class AgentDecision:
    kind: str
    summary: str
    open_questions: tuple[str, ...]
    tool_calls: tuple[AgentToolCall, ...] = ()
    findings: tuple[ProposedFinding, ...] = ()
    final_evidence_ids: tuple[str, ...] = ()
    reason: str = ""


@dataclass(frozen=True)
class GroundedFinding:
    id: str
    statement: str
    evidence_ids: tuple[str, ...]
    obligation_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class AgentEvidence:
    id: str
    path: str
    line_start: int
    line_end: int
    source_text: str
    symbol: str
    artifact_kind: str
    obligation_ids: tuple[str, ...]
    discovery_origin: str
    parent_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class AgentRetrievalReport:
    request_id: str
    status: str
    sufficient: bool
    stop_reason: str
    findings: tuple[GroundedFinding, ...]
    evidence: tuple[AgentEvidence, ...]
    unresolved_questions: tuple[str, ...]
    execution: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentToolOutcome:
    iteration: int
    tool: str
    status: str
    fingerprint: str
    result_summary: str
    new_artifact_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AgentState:
    request: AgentRetrievalRequest
    artifacts: dict[str, ArtifactRecord]
    initial_lead_ids: tuple[str, ...]
    attempted_operations: set[str] = field(default_factory=set)
    accepted_evidence_ids: set[str] = field(default_factory=set)
    findings: list[GroundedFinding] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    recent_artifact_ids: list[str] = field(default_factory=list)
    iteration: int = 0
    tool_calls: int = 0
    no_gain_iterations: int = 0
    protocol_errors: list[str] = field(default_factory=list)
    tool_outcomes: list[AgentToolOutcome] = field(default_factory=list)
    referenced_lead_reminders: dict[str, int] = field(default_factory=dict)
    usage: dict[str, int] = field(default_factory=lambda: {
        "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
    })
