"""Bounded owner-specific source for comparison, independent of qualification and ranking."""
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Sequence

from .discovery_observations import DiscoveryObservation, RetrievedSourceView


_SOURCE_ENCODINGS = ("utf-8", "utf-8-sig", "cp1252", "latin-1")


def _read_source_lines(path: Path) -> list[str]:
    """Decode repository source with the same legacy-text tolerance as indexing."""

    for encoding in _SOURCE_ENCODINGS:
        try:
            return path.read_text(encoding=encoding).splitlines()
        except UnicodeError:
            continue
    raise UnicodeError(f"repository_source_decode_failed:{path}")


@dataclass(frozen=True)
class OwnerSourcePreparation:
    observations: tuple[DiscoveryObservation, ...]
    rows: tuple[dict[str, Any], ...]
    file_reads: int
    layout_requests: int


def prepare_initial_owner_sources(observations: Sequence[DiscoveryObservation], *, config: Any,
                                 trace: Any) -> OwnerSourcePreparation:
    from services.retrieval.workspace.tools.codegraph import codegraph_tools
    from services.retrieval.workspace.source_ast.router import SourceAstRouter
    _, bridge = codegraph_tools(config)
    return prepare_owner_sources(observations, workspace_root=config.workspace_root,
        source_ast=SourceAstRouter(config.workspace_root, codegraph_bridge=bridge),
        mode='consistent', max_chars=1024, trace=trace)


def _segments(lines: Sequence[str], selected: set[int]) -> tuple[tuple[int, int, str], ...]:
    groups: list[list[int]] = []
    for number in sorted(selected):
        if not groups or groups[-1][-1] + 1 != number:
            groups.append([])
        groups[-1].append(number)
    return tuple((g[0], g[-1], '\n'.join(lines[n-1] for n in g)) for g in groups)


def render_owner_source(lines: Sequence[str], *, start: int, end: int, signature_end: int,
                        body_ranges: Sequence[Sequence[int]], focus: tuple[int, int],
                        max_chars: int, max_lines: int = 16, focus_lines: int = 8,
                        context_lines: int = 2) -> tuple[str, tuple[tuple[int, int], ...]]:
    """Budget includes line labels and explicit gaps; never pretend disjoint source is contiguous."""
    def render(selected: set[int]) -> str:
        groups = _segments(lines, selected)
        parts = []
        if groups and groups[0][0] > start:
            parts.append(f"... lines {start}-{groups[0][0]-1} omitted ...")
        for index, (a, b, text) in enumerate(groups):
            if index:
                parts.append(f"... lines {groups[index-1][1]+1}-{a-1} omitted ...")
            parts.append(f"[lines {a}-{b}]\n{text}")
        if groups and groups[-1][1] < end:
            parts.append(f"... lines {groups[-1][1]+1}-{end} omitted ...")
        return '\n'.join(parts)

    if (start < 1 or end > len(lines) or end < start or max_chars < 100
            or max_lines < 2 or focus_lines < 1 or context_lines < 0):
        raise ValueError('invalid_owner_source_bounds_or_budget')
    body_lines = {n for a,b in body_ranges for n in range(max(start,a),min(end,b)+1)
                  if lines[n-1].strip()}
    focus_body = sorted(n for n in body_lines if focus[0] <= n <= focus[1])
    center = focus_body[len(focus_body)//2] if focus_body else min(body_lines, default=start)
    # A bounded signature segment leaves room for the focus even for long declarations.
    signature = list(range(start, min(signature_end, end, start+3)+1))
    selected: set[int] = set()
    # Keep a body line before spending the remaining allowance on a long signature.
    if len(render({center})) <= max_chars:
        selected.add(center)
    for n in signature:
        if len(selected | {n}) <= max_lines and len(render(selected | {n})) <= max_chars:
            selected.add(n)
    # Focus is a window, not a target to fill with the whole owner. Extra capacity stays unused.
    body_floor = min(body_lines, default=start)
    low = max(body_floor, focus_body[0]) if focus_body else center
    high = min(end, focus_body[-1]) if focus_body else min(end, center+focus_lines-1)
    window_start = max(low, min(center-(focus_lines-1)//2, high-focus_lines+1))
    window_end = min(high, window_start+focus_lines-1)
    focused = sorted(range(window_start, window_end+1), key=lambda n: (abs(n-center), n))
    surrounding = [n for distance in range(1, context_lines+1)
                   for n in (window_start-distance, window_end+distance)
                   if body_floor <= n <= end]
    for n in (*focused, *surrounding):
        if len(selected | {n}) <= max_lines and len(render(selected | {n})) <= max_chars:
            selected.add(n)
    if not selected:
        # A single overlong source line is explicitly clipped, never silently treated as complete.
        prefix=f"[line {center}; clipped, partial source]\n"
        return prefix + lines[center-1][:max_chars-len(prefix)-3] + '...', ((center,center),)
    return render(selected), tuple((a,b) for a,b,_ in _segments(lines, selected))


def prepare_owner_sources(observations: Sequence[DiscoveryObservation], *, workspace_root: str,
                          source_ast: Any, mode: str, max_chars: int, trace: Any = None) -> OwnerSourcePreparation:
    if mode not in {'targeted', 'consistent'}:
        raise ValueError('unknown_owner_source_mode')
    # Local import avoids a cycle between the renderer and source preparation.
    from .initial_owner_comparison import _compact_source_view
    root=Path(workspace_root).resolve()
    files, layouts, rows, result = {}, {}, [], []
    for item in observations:
        h=item.handle
        row=dict(observation_id=item.id,path=h.path,symbol=h.symbol,mode=mode,max_chars=max_chars,
                 rendering_policy='signature_focused_window',max_lines=16,focus_lines=8,context_lines=2)
        prepared=item
        if not h.node_id or not h.full_line_start or not h.full_line_end:
            row['reason']='unresolved_owner_unchanged'
        else:
            if h.path not in files:
                path=(root/h.path).resolve()
                if not path.is_relative_to(root):
                    raise ValueError('owner_source_outside_workspace')
                files[h.path]=_read_source_lines(path)
                layouts[h.path]=source_ast.owner_source_layouts(h.path)
            lines=files[h.path]
            response=layouts[h.path]
            if response.get('status') != 'ok':
                row['reason']='source_layout_unavailable'
                row['layout_status']=response.get('status')
                row['layout_reason']=response.get('reason')
            else:
                matches=[v for v in response['owners'] if v['line_end']==h.full_line_end
                         and abs(v['line_start']-h.full_line_start)<=1]
                layout=min(matches,key=lambda v:abs(v['line_start']-h.full_line_start)) if matches else None
                if layout is None:
                    row['reason']='owner_layout_identity_unmatched'
                else:
                    ranges=layout['body_ranges']
                    old_views=item.source_views or (RetrievedSourceView(h.path,h.line_start,h.line_end,item.observed_text),)
                    for view in old_views:
                        if view.text.strip() and view.text.strip() != '\n'.join(lines[view.line_start-1:view.line_end]).strip():
                            raise ValueError(f'owner_source_snapshot_mismatch:{h.path}:{view.line_start}-{view.line_end}')
                    old='\n'.join(_compact_source_view(v.text) for v in old_views)
                    body_lines={lines[n-1].strip() for a,b in ranges
                                for n in range(a,min(b,len(lines))+1) if lines[n-1].strip()}
                    visible_body=any(line.strip() in body_lines for line in old.splitlines())
                    row.update(old_chars=len(old),old_body_visible=visible_body)
                    if mode=='targeted' and (visible_body or not ranges):
                        row['reason']='existing_body_or_noncallable_unchanged'
                    else:
                        focus=(h.line_start,h.line_end)
                        text, segments=render_owner_source(lines,start=h.full_line_start,end=h.full_line_end,
                            signature_end=layout['signature_end'],body_ranges=ranges,focus=focus,max_chars=max_chars)
                        prepared=replace(item, comparison_source_views=(RetrievedSourceView(h.path,h.full_line_start,h.full_line_end,text),))
                        row.update(reason='owner_source_prepared',source_text=text,segments=segments,
                                   source_chars=len(text),source_lines=sum(b-a+1 for a,b in segments),
                                   original_focus=focus,owner_range=(h.full_line_start,h.full_line_end),
                                   new_body_visible=any(a<=n<=b for a,b in segments for c,d in ranges for n in range(c,d+1)))
        result.append(prepared)
        rows.append(row)
    output=OwnerSourcePreparation(tuple(result),tuple(rows),len(files),len(layouts))
    if trace is not None:
        trace.record('owner_comparison_source_prepared',dict(mode=mode,max_chars=max_chars,file_reads=len(files),
            layout_requests=len(layouts),candidate_count=len(result),prepared_count=sum(r['reason']=='owner_source_prepared' for r in rows),rows=rows))
    return output
