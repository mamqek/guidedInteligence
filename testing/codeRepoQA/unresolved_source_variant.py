"""Archived renderer experiment. Not imported by live retrieval."""
import re
from typing import Sequence
from services.retrieval.workspace.pipeline.execution_flow.discovery_observations import RetrievedSourceView


def render_unresolved_source(view: RetrievedSourceView, *, matched_terms: Sequence[str],
                             max_chars: int) -> str:
    """Preserve a contiguous portion of retrieved text, never synthesize an owner."""
    if max_chars < 100:
        raise ValueError('invalid_unresolved_source_budget')
    lines = view.text.splitlines()
    if not lines:
        return ''

    def render(start: int, end: int) -> str:
        parts = []
        if start:
            parts.append(f'... lines {view.line_start}-{view.line_start+start-1} omitted ...')
        parts.append(f'[lines {view.line_start+start}-{view.line_start+end}]\n' + '\n'.join(lines[start:end+1]))
        if end < len(lines)-1:
            parts.append(f'... lines {view.line_start+end+1}-{view.line_start+len(lines)-1} omitted ...')
        return '\n'.join(parts)

    full = render(0, len(lines)-1)
    if len(full) <= max_chars:
        return full
    terms = {term.casefold() for term in matched_terms if len(term.strip()) >= 3}
    patterns = [re.compile(r'(?<!\w)' + re.escape(term) + r'(?!\w)', re.I) for term in sorted(terms)]
    scores = [sum(bool(pattern.search(line)) for pattern in patterns) for line in lines]
    center = max(range(len(lines)), key=lambda i: (scores[i], -i))
    start = end = center
    if len(render(start, end)) > max_chars:
        label = f'[line {view.line_start+center}; clipped, partial source]\n'
        return label + lines[center][:max_chars-len(label)-3] + '...'
    while True:
        options = [(start-1, end)] if start else []
        if end < len(lines)-1:
            options.append((start, end+1))
        # Balance neighboring context around the match while keeping one contiguous window.
        options.sort(key=lambda bounds: (abs((center-bounds[0])-(bounds[1]-center)), bounds[0]))
        chosen = next((bounds for bounds in options if len(render(*bounds)) <= max_chars), None)
        if chosen is None:
            break
        start, end = chosen
    return render(start, end)
