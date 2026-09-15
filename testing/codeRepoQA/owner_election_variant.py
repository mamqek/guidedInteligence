"""Qualified per-file/obligation primary election, independent of candidate retention.

Uses this checkpoint's explicit supported-obligation contract. It does not infer the
later partial-contribution contract, nominate inspections, or grant final evidence.
"""
from collections import Counter


def elect_owner_primaries(observations, decisions):
    groups = {}
    for oid, observation in observations.items():
        decision = decisions.get(oid)
        if decision is None or decision.disposition != 'promote':
            continue
        for obligation in decision.supported_obligation_ids:
            groups.setdefault((observation.handle.path.casefold(), obligation), []).append(oid)
    elections = []
    for (path, obligation), ids in sorted(groups.items()):
        def key(oid):
            observation, decision = observations[oid], decisions[oid]
            return (0 if decision.support_level == 'direct_evidence' else 1,
                    0 if observation.exact_anchor_matches else 1,
                    -len(set(decision.supported_obligation_ids)),
                    -observation.recurrence, observation.best_rank,
                    observation.handle.line_start, oid)
        ordered = sorted(ids, key=key)
        elections.append({'path': path, 'obligation_id': obligation, 'primary': ordered[0],
                          'complements': ordered[1:]})
    return dict(Counter(row['primary'] for row in elections)), elections
