from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import re
from typing import Any, Mapping, Sequence

from services.retrieval.workspace.pipeline.execution_flow.coverage_evaluation import ObligationCoverage
from services.retrieval.workspace.pipeline.execution_flow.discovery_observations import DiscoveryObservation
from services.retrieval.workspace.pipeline.execution_flow.evidence_qualification import QualificationDecision
from services.retrieval.workspace.pipeline.execution_flow.source_disclosure import DisclosureCard
from services.retrieval.workspace.pipeline.execution_flow.actions.models import InspectVerifiedLead
from services.retrieval.workspace.pipeline.execution_flow.actions.policy import ActionPurpose
from services.retrieval.workspace.tools import ToolRequest
from services.retrieval.workspace.pipeline.execution_flow.island_connectors import _call_can_target


MAX_VERIFIED_LEAD_EXECUTIONS = 2


@dataclass(frozen=True)
class VerifiedLead:
    source_observation_id: str
    obligation_id: str
    target: str
    target_node_id: str
    target_path: str
    target_line_start: int
    target_line_end: int
    target_symbol: str
    reason: str
    discovered_round: int
    source_rank: int
    qualified_target: bool
    structural_child: bool = False
    origin: str = "qualification_followup"
    source_call_path: str = ""
    source_call_line: int = 0
    known_incoming_calls: int | None = None
    source_file_literal_calls: int | None = None
    inspection_basis: str = "qualification_followup"
    request_text: str = ""
    source_callable_kind: str = ""


def _inspection_request(target: str, decision: QualificationDecision, claims: Sequence[str], source: str) -> tuple[str, str]:
    for basis, text in (("qualification_followup", decision.local_follow_up),
                        *(("missing_information", claim) for claim in claims)):
        if any(_target_leaf(value) == _target_leaf(target)
               and (not ("." in value or "::" in value) or value.replace("::", ".") == target.replace("::", "."))
               for value in _followup_called_targets(text, source)):
            return basis, text
    return "incidental_visible_call", ""


def verified_lead_priority(lead: VerifiedLead) -> tuple[Any, ...]:
    # A real call is an exploration lead, not proof that its target fills a gap.
    return (0 if lead.inspection_basis != "incidental_visible_call" else 1,
            0 if lead.structural_child else 1, 0 if lead.qualified_target else 1,
            lead.discovered_round, lead.source_rank, lead.target_path.casefold(), lead.target_node_id)


def retain_verified_lead(pending: dict[str, VerifiedLead], lead: VerifiedLead) -> None:
    previous = pending.get(lead.target_node_id)
    if previous is None or verified_lead_priority(lead) < verified_lead_priority(previous):
        pending[lead.target_node_id] = lead


def discover_qualified_file_leads(
    *, round_index: int, changed_observation_ids: Sequence[str],
    observations: Mapping[str, DiscoveryObservation], decisions: Mapping[str, QualificationDecision],
    cards: Mapping[str, DisclosureCard], coverage: Sequence[ObligationCoverage],
    pending_node_ids: set[str], executed_node_ids: set[str],
    structural_tools: Mapping[str, Any], workspace_root: str, trace: Any | None,
    pending_leads: Mapping[str, VerifiedLead] | None = None,
) -> tuple[tuple[VerifiedLead, ...], list[dict[str, Any]], int]:
    """Expose unqualified cross-file targets, never evidence, from visible qualified calls."""
    unresolved = {item.obligation_id for item in coverage if item.status not in {"covered", "external"}}
    accepted: list[VerifiedLead] = []
    audit: list[dict[str, Any]] = []
    tool_calls = 0
    resolutions = 0
    resolved: dict[str, list[Mapping[str, Any]]] = {}
    unavailable = set(pending_node_ids) | set(executed_node_ids)
    qualified_nodes = {item.handle.node_id for key, item in observations.items() if key in decisions}

    def request(name: str, arguments: dict[str, Any]) -> Mapping[str, Any]:
        nonlocal tool_calls
        tool_request = ToolRequest(name, arguments, "Resolve a qualified visible cross-file lead without admitting evidence.")
        response = structural_tools[name].run(tool_request)
        tool_calls += 1
        if trace is not None:
            trace.record_tool(tool_request, response, round_index=round_index)
        if response.status != "ok":
            raise RuntimeError(f"required_tool_failed: {name}")
        return response.payload

    for identifier in dict.fromkeys(changed_observation_ids):
        observation, decision, card = observations.get(identifier), decisions.get(identifier), cards.get(identifier)
        if observation is None or decision is None or card is None:
            continue
        if decision.disposition != "promote" or decision.support_level != "direct_evidence":
            continue
        obligations = tuple(value for value in decision.supported_obligation_ids if value in unresolved)
        if not obligations:
            continue
        source = {
            "id": observation.handle.node_id, "path": observation.handle.path,
            "name": card.owner_name.split("::")[-1].split(".")[-1],
            "qualified_name": card.owner_name or observation.handle.symbol,
            "line_start": card.owner_line_start, "line_end": card.owner_line_end,
        }
        base = {"source_observation_id": identifier, "supported_obligation_ids": list(obligations), "round": round_index}
        ast_owned = str(source["id"] or "").startswith("source_owner:")
        if not source["id"] or (not ast_owned and card.owner_kind not in {"function", "method", "constructor", "assigned_function"}):
            audit.append({**base, "status": "rejected", "reason": "source_not_resolved_callable"})
            continue
        root = Path(workspace_root).resolve()
        path = (root / observation.handle.path).resolve()
        if not path.is_relative_to(root):
            raise RuntimeError("qualified_file_lead_source_outside_workspace")
        source_text = path.read_text(encoding="utf-8")
        lines = source_text.splitlines()
        call_result = request("structural_source_owner_calls", {"node": source})
        source_kind = str(call_result.get("source_kind") or ("" if ast_owned else card.owner_kind))
        if source_kind not in {"function", "method", "constructor", "assigned_function"}:
            audit.append({**base, "status": "rejected", "reason": "source_not_validated_callable", "source_callable_kind": source_kind})
            continue
        calls = call_result.get("calls", ())
        base["source_callable_kind"] = source_kind
        seen_calls: set[tuple[str, str]] = set()
        for call in calls:
            name, qualifier = str(call.get("name") or ""), str(call.get("qualifier") or "")
            if not re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", qualifier) or qualifier in {"self", "cls", "this"}:
                continue
            key = (qualifier, name)
            if key in seen_calls:
                continue
            seen_calls.add(key)
            line = int(call.get("line_start") or 0)
            row = {**base, "target": f"{qualifier}.{name}", "source_path": source["path"], "source_line": line}
            visible_line = lines[line - 1].strip() if 0 < line <= len(lines) else ""
            if not visible_line or visible_line not in card.source_text:
                audit.append({**row, "status": "rejected", "reason": "call_not_in_fitted_source"})
                continue
            # Conservative source-local repetition signal, not resolved caller count.
            # Comments/strings can inflate it; never use it to establish a relationship.
            literal_calls = len(re.findall(
                rf"\b{re.escape(qualifier)}\s*\.\s*{re.escape(name)}\s*(?:<[^;{{}}()]*>)?\s*\(", source_text,
            ))
            row["source_file_literal_calls"] = literal_calls
            if literal_calls > 12:
                audit.append({**row, "status": "rejected", "reason": "high_source_file_call_repetition"})
                continue
            if name not in resolved:
                if resolutions >= 8:
                    audit.append({**row, "status": "rejected", "reason": "batch_resolution_budget"})
                    continue
                resolutions += 1
                resolved[name] = list(request("structural_find_exact_symbol", {"query": name, "limit": 20}).get("nodes", ()))
            if len(resolved[name]) >= 20:
                audit.append({**row, "status": "rejected", "reason": "symbol_result_limit_cannot_prove_unique"})
                continue
            matches = {str(node.get("id")): node for node in resolved[name]
                       if str(node.get("name") or "") == name
                       and node.get("kind") in {"function", "method", "constructor"}
                       and _call_can_target(source, call, node)}
            if len(matches) != 1:
                audit.append({**row, "status": "rejected", "reason": "target_not_unique", "match_count": len(matches)})
                continue
            target_id, target = next(iter(matches.items()))
            row.update(target_node_id=target_id, target_path=target.get("path"))
            basis, request_text = _inspection_request(row["target"], decision,
                [item.missing_claim for item in coverage if item.obligation_id in obligations], card.source_text)
            previous = (pending_leads or {}).get(target_id)
            upgrade = (previous is not None and previous.inspection_basis == "incidental_visible_call"
                       and basis != "incidental_visible_call" and target_id not in executed_node_ids)
            if str(target.get("path") or "").casefold() == observation.handle.path.casefold():
                audit.append({**row, "status": "rejected", "reason": "same_file_target"})
                continue
            if (target_id in unavailable and not upgrade) or target_id in qualified_nodes:
                audit.append({**row, "status": "rejected", "reason": "target_qualified_pending_or_executed"})
                continue
            capabilities = request("structural_edge_capabilities", {"node_ids": [target_id]})
            node_caps = next((value for value in capabilities.get("nodes", ()) if value.get("node_id") == target_id), None)
            if node_caps is None:
                audit.append({**row, "status": "rejected", "reason": "utility_metrics_unavailable"})
                continue
            incoming = sum(int(value.get("count") or 0) for value in node_caps.get("incoming", ()) if value.get("kind") == "calls")
            row["known_incoming_calls"] = incoming
            if incoming > 12:
                audit.append({**row, "status": "rejected", "reason": "high_static_call_indegree"})
                continue
            lead = VerifiedLead(
                source_observation_id=identifier, obligation_id=obligations[0], target=f"{qualifier}.{name}",
                target_node_id=target_id, target_path=str(target["path"]),
                target_line_start=int(target["line_start"]), target_line_end=int(target["line_end"]),
                target_symbol=str(target.get("qualified_name") or name),
                reason=f"Qualified source calls {qualifier}.{name} at {source['path']}:{line}; inspect target for unresolved {obligations[0]}; no semantic support inherited.",
                discovered_round=round_index, source_rank=observation.best_rank, qualified_target=True,
                structural_child=True, origin="qualified_structural_file_lead", source_call_path=str(source["path"]),
                source_call_line=line, known_incoming_calls=incoming, source_file_literal_calls=literal_calls,
                inspection_basis=basis, request_text=request_text,
                source_callable_kind=source_kind,
            )
            accepted.append(lead)
            unavailable.add(target_id)
            audit.append({**row, "status": "accepted", "reason": "pending_lead_priority_upgraded" if upgrade else "qualified_visible_cross_file_call",
                          "inspection_basis": basis, "request_text": request_text,
                          "target_previously_canonical": any(value.handle.node_id == target_id for value in observations.values())})
            break
    return tuple(accepted), audit, tool_calls


def _discover_verified_leads(
    *,
    round_index: int,
    changed_observation_ids: Sequence[str],
    observations: Mapping[str, DiscoveryObservation],
    decisions: Mapping[str, QualificationDecision],
    cards: Mapping[str, DisclosureCard],
    coverage: Sequence[ObligationCoverage],
    pending_node_ids: set[str],
    executed_node_ids: set[str],
    exact_symbol_tool: Any,
    trace: Any | None,
    maturation_observation_ids: set[str] | None = None,
) -> tuple[tuple[VerifiedLead, ...], list[dict[str, Any]], int]:
    """Validate newly disclosed, literal call targets before granting a reserved action."""
    coverage_by_id = {item.obligation_id: item for item in coverage}
    accepted: list[VerifiedLead] = []
    audit: list[dict[str, Any]] = []
    tool_calls = 0
    seen_targets: set[tuple[str, str]] = set()
    matured_ids = maturation_observation_ids or set()
    for observation_id in dict.fromkeys(changed_observation_ids):
        observation = observations.get(observation_id)
        decision = decisions.get(observation_id)
        card = cards.get(observation_id)
        base = {
            "observation_id": observation_id,
            "round": round_index,
            "follow_up": decision.local_follow_up if decision is not None else "",
        }
        if observation is None or decision is None or card is None:
            audit.append({**base, "status": "rejected", "reason": "missing_observation_decision_or_card"})
            continue
        is_matured = observation_id in matured_ids
        if decision.disposition != "promote" or (
            decision.support_level != "navigation_only" and not is_matured
        ):
            continue
        unresolved = [
            value
            for value in observation.obligation_ids
            if coverage_by_id.get(value) is not None
            and coverage_by_id[value].status not in {"covered", "external"}
        ]
        if not unresolved:
            audit.append({**base, "status": "rejected", "reason": "no_compatible_unresolved_obligation"})
            continue
        target_context = decision.local_follow_up
        if is_matured:
            target_context = " ".join((
                target_context,
                *(coverage_by_id[value].missing_claim for value in unresolved),
            ))
        targets = _followup_called_targets(target_context, card.source_text)
        if not targets:
            audit.append({
                **base,
                "status": "rejected",
                "reason": "no_source_called_target_named_in_followup_or_unresolved_claim",
                "maturation_source": is_matured,
            })
            continue
        target = targets[0]
        target_key = (observation_id, target.casefold())
        if target_key in seen_targets:
            continue
        seen_targets.add(target_key)
        leaf = _target_leaf(target)
        request = ToolRequest(
            tool_name="structural_find_exact_symbol",
            arguments={"query": leaf, "limit": 8},
            reason=f"Validate visible direct follow-up target {target} before reserving retrieval work.",
        )
        response = exact_symbol_tool.run(request)
        if trace is not None:
            trace.record_tool(request, response, round_index=round_index)
        tool_calls += 1
        if response.status != "ok":
            raise RuntimeError("required_tool_failed: structural_find_exact_symbol")
        nodes = _matching_target_nodes(target, response.payload.get("nodes", ()))
        if len(nodes) != 1:
            audit.append({
                **base,
                "target": target,
                "status": "rejected",
                "reason": "target_not_resolved" if not nodes else "target_resolution_ambiguous",
                "match_count": len(nodes),
            })
            continue
        node = nodes[0]
        node_id = str(node.get("id") or "")
        target_path = str(node.get("path") or "")
        structural_child = bool(
            is_matured
            and target_path
            and target_path.casefold() != observation.handle.path.casefold()
        )
        if is_matured and not structural_child and decision.support_level != "navigation_only":
            audit.append({
                **base,
                "target": target,
                "target_node_id": node_id,
                "status": "rejected",
                "reason": "maturation_direct_target_not_cross_file",
            })
            continue
        if not node_id or node_id in pending_node_ids or node_id in executed_node_ids:
            audit.append({
                **base,
                "target": target,
                "target_node_id": node_id,
                "status": "rejected",
                "reason": "target_already_pending_or_executed",
            })
            continue
        if any(item.handle.node_id == node_id for item in observations.values()):
            audit.append({
                **base,
                "target": target,
                "target_node_id": node_id,
                "status": "rejected",
                "reason": "target_already_observed",
            })
            continue
        lead = VerifiedLead(
            source_observation_id=observation_id,
            obligation_id=unresolved[0],
            target=target,
            target_node_id=node_id,
            target_path=target_path,
            target_line_start=max(1, int(node.get("line_start") or 1)),
            target_line_end=max(1, int(node.get("line_end") or node.get("line_start") or 1)),
            target_symbol=str(node.get("qualified_name") or node.get("name") or leaf),
            reason=decision.local_follow_up,
            discovered_round=round_index,
            source_rank=observation.best_rank,
            qualified_target=("." in target or "::" in target),
            structural_child=structural_child,
            inspection_basis=_inspection_request(target, decision,
                [coverage_by_id[value].missing_claim for value in unresolved] if is_matured else (), card.source_text)[0],
            request_text=target_context,
        )
        accepted.append(lead)
        pending_node_ids.add(node_id)
        audit.append({**base, **_verified_lead_to_dict(lead), "status": "accepted", "reason": "visible_call_resolved"})
    return tuple(accepted), audit, tool_calls


def _literal_followup_targets(value: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(
        match.group(1).strip()
        for match in re.finditer(r"`([^`]+)`", value or "")
        if re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*(?:(?:::|\.)[A-Za-z_$][A-Za-z0-9_$]*)*", match.group(1).strip())
    ))


def _followup_called_targets(follow_up: str, source: str) -> tuple[str, ...]:
    """Find follow-up identifiers that are also literal calls in the disclosed source.

    Backticks are presentation, not semantics: an LLM may emit either
    ``Inspect `Series._binop``` or ``Inspect Series._binop`` for the same lead.
    """
    visible_calls = tuple(dict.fromkeys(
        match.group(1)
        for match in re.finditer(
            r"(?:\bself\.|\bthis\.|\b[A-Za-z_$][A-Za-z0-9_$]*\.)?([A-Za-z_$][A-Za-z0-9_$]*)\s*\(",
            source or "",
        )
    ))
    candidates: list[str] = []
    for literal in _literal_followup_targets(follow_up):
        if _target_leaf(literal) in visible_calls:
            candidates.append(literal)
    for leaf in visible_calls:
        qualified = re.search(
            rf"\b([A-Za-z_$][A-Za-z0-9_$]*(?:(?:::|\.){re.escape(leaf)}))\b",
            follow_up or "",
        )
        if qualified:
            candidates.append(qualified.group(1))
        elif re.search(rf"(?<![A-Za-z0-9_$]){re.escape(leaf)}(?![A-Za-z0-9_$])", follow_up or ""):
            candidates.append(leaf)
    return tuple(dict.fromkeys(candidates))


def _target_leaf(target: str) -> str:
    return re.split(r"::|\.", target)[-1]


def _source_visibly_calls(source: str, target: str) -> bool:
    leaf = _target_leaf(target)
    return bool(re.search(rf"\b{re.escape(leaf)}\s*\(", source or ""))


def _matching_target_nodes(target: str, values: Sequence[Any]) -> list[dict[str, Any]]:
    leaf = _target_leaf(target).casefold()
    normalized_target = target.replace("::", ".").casefold()
    qualified = "." in normalized_target
    matches: dict[str, dict[str, Any]] = {}
    for value in values:
        if not isinstance(value, Mapping):
            continue
        name = str(value.get("name") or "").casefold()
        qualified_name = str(value.get("qualified_name") or value.get("name") or "").replace("::", ".").casefold()
        if name != leaf and qualified_name.split(".")[-1] != leaf:
            continue
        if qualified and not (qualified_name == normalized_target or qualified_name.endswith(f".{normalized_target}")):
            continue
        node_id = str(value.get("id") or "")
        if node_id and value.get("path"):
            matches[node_id] = dict(value)
    return list(matches.values())


def _verified_lead_to_dict(lead: VerifiedLead) -> dict[str, Any]:
    return {
        "source_observation_id": lead.source_observation_id,
        "obligation_id": lead.obligation_id,
        "target": lead.target,
        "target_node_id": lead.target_node_id,
        "target_path": lead.target_path,
        "target_range": [lead.target_line_start, lead.target_line_end],
        "target_symbol": lead.target_symbol,
        "reason": lead.reason,
        "discovered_round": lead.discovered_round,
        "structural_child": lead.structural_child,
        "origin": lead.origin,
        "source_call_path": lead.source_call_path,
        "source_call_line": lead.source_call_line,
        "known_incoming_calls": lead.known_incoming_calls,
        "source_file_literal_calls": lead.source_file_literal_calls,
        "inspection_basis": lead.inspection_basis,
        "request_text": lead.request_text,
        "source_callable_kind": lead.source_callable_kind,
        "source_rank": lead.source_rank,
        "qualified_target": lead.qualified_target,
        "priority_key": list(verified_lead_priority(lead)),
    }


def _select_verified_lead_actions(
    leads: Sequence[VerifiedLead],
    *,
    executed_count: int,
    observation_to_island: Mapping[str, str],
    limit: int = 1,
) -> tuple[InspectVerifiedLead, ...]:
    if not leads or executed_count >= MAX_VERIFIED_LEAD_EXECUTIONS:
        return ()
    ranked = sorted(
        leads,
        key=verified_lead_priority,
    )
    return tuple(_lead_action(lead, observation_to_island) for lead in ranked[:limit])


def _lead_action(lead: VerifiedLead, observation_to_island: Mapping[str, str]) -> InspectVerifiedLead:
    digest = hashlib.sha1(
        f"{lead.source_observation_id}\0{lead.target_node_id}".encode("utf-8")
    ).hexdigest()[:16]
    return InspectVerifiedLead(
            id=f"action_{digest}",
            obligation_id=lead.obligation_id,
            source_observation_id=lead.source_observation_id,
            target=lead.target,
            target_node_id=lead.target_node_id,
            target_path=lead.target_path,
            target_line_start=lead.target_line_start,
            target_line_end=lead.target_line_end,
            target_symbol=lead.target_symbol,
            reason=lead.reason,
            discovered_round=lead.discovered_round,
            scope_id=observation_to_island.get(lead.source_observation_id, ""),
            purpose=(
                ActionPurpose.STRUCTURAL_CHILD_HANDOFF
                if lead.structural_child
                else ActionPurpose.VERIFIED_SOURCE_LEAD
            ),
        )
