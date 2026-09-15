"""Trace existing owner elections without changing retrieval decisions or prompts."""
from typing import Any, Mapping, Sequence


def audit_owner_elections(result: Any, previous: Any, observations: Mapping[str, Any],
                          decisions: Mapping[str, Any], cards: Mapping[str, Any],
                          root_key: Any) -> list[dict[str, Any]]:
    old_islands = previous.islands if previous else ()
    old_ids = {oid for island in old_islands for oid in island.observation_ids}
    rows = []
    for island in result.islands:
        members = set(island.observation_ids)
        predecessors = [old for old in old_islands if members.intersection(old.observation_ids)]
        previous_primaries = [old.representative_observation_id for old in predecessors]
        newly_promoted = sorted(members - old_ids) if previous else []
        winner = island.representative_observation_id
        candidates = []
        for oid in island.observation_ids:
            observation, decision = observations[oid], decisions[oid]
            card = cards.get(oid)
            candidates.append({
                'id': oid, 'handle': observation.to_dict(include_text=False)['handle'],
                'ranking_key': list(root_key(observation, decision)),
                'qualification': decision.to_dict(),
                'source_text': card.source_text if card else '',
                'source_mode': card.mode if card else '',
                'truncation_reason': card.truncation_reason if card else '',
                'retrieved_obligation_ids': list(observation.obligation_ids),
            })
        paths = {observations[oid].handle.path.casefold() for oid in members}
        outside = [oid for oid, observation in observations.items()
                   if oid not in members and observation.handle.path.casefold() in paths]
        rows.append({
            'island_id': island.id, 'active': island.id in result.active_island_ids,
            'winner': winner, 'previous_primaries': previous_primaries,
            'newly_promoted_ids': newly_promoted,
            'kind': ('initial' if not predecessors else 'merge' if len(predecessors) > 1
                     else 'preserved' if winner == previous_primaries[0] else 'replaced'),
            'new_owner_competition': bool(newly_promoted and predecessors and len(members) > 1),
            'candidates': candidates, 'same_file_outside_island': outside,
        })
    return rows
