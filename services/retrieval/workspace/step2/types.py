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
    surface_context_terms: tuple[str, ...]
    owner_artifact_terms: tuple[str, ...]
    grounded_entities: tuple[str, ...]
    confirmed_entities: tuple[str, ...]
    grounded_file_hints: tuple[str, ...]
    confirmed_file_hints: tuple[str, ...]
    llm_concept_terms: tuple[str, ...]
    llm_subqueries: tuple[RoleDirectedSubquery, ...]
    owner_subqueries: tuple[RoleDirectedSubquery, ...]
    support_subqueries: tuple[RoleDirectedSubquery, ...]
    speculative_entities: tuple[str, ...]
    source_priorities: tuple[SourceCategory, ...]
    negative_filters: tuple[str, ...]
    required_roles: tuple[str, ...]
    supporting_roles: tuple[str, ...]
    primary_intent: str = ""
    secondary_intents: tuple[str, ...] = ()
    specificity: str = ""
    active_objectives: tuple[str, ...] = ()
    deferred_objectives: tuple[str, ...] = ()
    preferred_relations: tuple[str, ...] = ()
    stop_contract: Mapping[str, Any] = field(default_factory=dict)
    expansion_policy: Mapping[str, Any] = field(default_factory=dict)
    prompt_signal_flags: Mapping[str, bool] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["llm_subqueries"] = [subquery.to_dict() for subquery in self.llm_subqueries]
        data["source_priorities"] = [category.value for category in self.source_priorities]
        data["secondary_intents"] = list(self.secondary_intents)
        data["active_objectives"] = list(self.active_objectives)
        data["deferred_objectives"] = list(self.deferred_objectives)
        data["preferred_relations"] = list(self.preferred_relations)
        data["stop_contract"] = dict(self.stop_contract)
        data["expansion_policy"] = dict(self.expansion_policy)
        data["prompt_signal_flags"] = dict(self.prompt_signal_flags)
        data["metadata"] = dict(self.metadata)
        return data
