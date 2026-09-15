"""Archived narrow visibility experiment; not imported by live retrieval."""
from dataclasses import dataclass, replace
import re
from typing import Callable, Sequence

from services.retrieval.workspace.pipeline.execution_flow.discovery_observations import DiscoveryObservation, RetrievedSourceView


@dataclass(frozen=True)
class HiddenAnchorSource:
    views: tuple[RetrievedSourceView, ...]
    reason: str
    anchor: str = ''
    witness_range: tuple[int, int] = ()


def request_code_names(request: str) -> tuple[str, ...]:
    """Conservative lexical names; no lower-case prose expansion or case guessing."""
    return tuple(dict.fromkeys(word for word in re.findall(r'(?<![\w$])[A-Za-z_$][\w$]{2,}(?![\w$])', request)
                              if word[0].isupper() or '_' in word or re.search(r'[a-z][A-Z]', word)))


def prepare_hidden_anchor_source(observation: DiscoveryObservation, *, names: Sequence[str],
                                 compact: Callable[[str], str], max_chars: int = 1024) -> HiddenAnchorSource:
    handle = observation.handle
    if handle.node_id and handle.full_line_start and handle.full_line_end:
        return HiddenAnchorSource((), 'resolved_owner_unchanged')
    views = observation.source_views or (RetrievedSourceView(
        handle.path, handle.line_start, handle.line_end, observation.observed_text),)
    old = tuple(replace(v, text=compact(v.text)) for v in views)
    old_chars = sum(len(v.text) for v in old)
    remaining = min(512, max_chars - old_chars - 1)
    if remaining <= 0:
        return HiddenAnchorSource((), 'candidate_source_budget_full')
    matched = {t.casefold() for p in observation.provenance for t in p.matched_terms}
    witnesses = []
    for name in names:
        if name.casefold() not in matched:
            continue
        pattern = re.compile(r'(?<![\w$])' + re.escape(name) + r'(?![\w$])')
        if any(pattern.search(v.text) for v in old):
            continue
        code_use = re.compile(pattern.pattern + r'(?=\s*(?:\(|\.))')
        for index, view in enumerate(views):
            for line_index, line in enumerate(view.text.splitlines()):
                if code_use.search(line):
                    witnesses.append((name, index, line_index))
    if not witnesses:
        return HiddenAnchorSource((), 'no_hidden_request_name')
    # Prefer the longer exact name, then original view/line order. No relevance score.
    for name, index, center in sorted(witnesses, key=lambda w: (-len(w[0]), w[1], w[2], w[0])):
        view = views[index]
        lines = view.text.splitlines()
        start = end = center

        def render(a: int, b: int) -> str:
            return f'[additional source lines {view.line_start+a}-{view.line_start+b}]\n' + '\n'.join(lines[a:b+1])

        if len(render(start, end)) > remaining:
            continue
        for radius in range(1, 4):
            a, b = max(0, center-radius), min(len(lines)-1, center+radius)
            if len(render(a, b)) > remaining:
                break
            start, end = a, b
        enriched = list(old)
        enriched[index] = replace(old[index], text=old[index].text + '\n' + render(start, end))
        return HiddenAnchorSource(tuple(enriched), 'hidden_request_name_restored', name,
                                  (view.line_start+start, view.line_start+end))
    return HiddenAnchorSource((), 'anchor_context_does_not_fit')
