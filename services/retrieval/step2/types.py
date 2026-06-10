from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

from core.source_policy import SourceCategory


@dataclass(frozen=True)
class RoleDirectedSubquery:
    role: str
    query: str

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "query": self.query}


@dataclass(frozen=True)
class PromptEvidence:
    raw_prompt_evidence: tuple[str, ...]
    grounded_entities: tuple[str, ...]
    grounded_file_hints: tuple[str, ...]
    source_priorities: tuple[SourceCategory, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_prompt_evidence": list(self.raw_prompt_evidence),
            "grounded_entities": list(self.grounded_entities),
            "grounded_file_hints": list(self.grounded_file_hints),
            "source_priorities": [category.value for category in self.source_priorities],
        }


@dataclass(frozen=True)
class WorkspaceRetrievalPlan:
    conversation_id: str
    raw_prompt: str
    raw_prompt_evidence: tuple[str, ...]
    prompt_summary: str
    retrieval_terms: tuple[str, ...]
    grounded_entities: tuple[str, ...]
    confirmed_entities: tuple[str, ...]
    grounded_file_hints: tuple[str, ...]
    confirmed_file_hints: tuple[str, ...]
    llm_concept_terms: tuple[str, ...]
    llm_subqueries: tuple[RoleDirectedSubquery, ...]
    speculative_entities: tuple[str, ...]
    source_priorities: tuple[SourceCategory, ...]
    negative_filters: tuple[str, ...]
    required_roles: tuple[str, ...]
    supporting_roles: tuple[str, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["llm_subqueries"] = [subquery.to_dict() for subquery in self.llm_subqueries]
        data["source_priorities"] = [category.value for category in self.source_priorities]
        data["metadata"] = dict(self.metadata)
        return data
