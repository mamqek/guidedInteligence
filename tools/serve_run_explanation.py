from __future__ import annotations

import argparse
import html
import json
import shutil
import re
import socket
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse


DEFAULT_PORT = 8765
LINE_REF_RE = re.compile(r"^(?:(?P<prefix>[^:]+):)?(?P<path>.+):L(?P<start>\d+)(?:-L?(?P<end>\d+))?$")
MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
INLINE_CODE_RE = re.compile(r"`([^`]+)`")
STRONG_RE = re.compile(r"\*\*([^*]+)\*\*")
INLINE_TOKEN_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)|`([^`]+)`|\*\*([^*]+)\*\*")
ORDERED_LIST_RE = re.compile(r"^\d+\.\s+")


def _load_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def _infer_repo_root(run_dir: Path) -> Path | None:
    metadata = _load_json(run_dir / "run-metadata.json", {})
    repo_pre_path = str(metadata.get("repo_pre_path") or "").strip()
    if repo_pre_path:
        candidate = Path(repo_pre_path)
        if candidate.exists():
            return candidate
    case_dir = run_dir.parent.parent
    repo_dir = case_dir / "repo"
    return repo_dir if repo_dir.exists() else None


def _parse_source_ref(ref: str) -> tuple[str, int | None, int | None]:
    match = LINE_REF_RE.match(ref)
    if not match:
        return ref, None, None
    return match.group("path"), int(match.group("start")), int(match.group("end") or match.group("start"))


def _source_key(path: str, start: int | None, end: int | None) -> str:
    if start is None:
        return path
    return f"{path}#L{start}-L{end or start}"


def _editor_uri(repo_root: Path | None, rel_path: str, line: int | None) -> str:
    if repo_root is None:
        return "#"
    absolute = (repo_root / rel_path).resolve()
    query = {"path": str(absolute)}
    if line:
        query["line"] = str(line)
    return "/open?" + urlencode(query)


def _launch_editor(path: str, line: int | None) -> tuple[bool, str]:
    editor = shutil.which("code.cmd") or shutil.which("code")
    if not editor:
        return False, "VS Code command-line launcher `code` was not found on PATH."
    target = f"{path}:{line}:1" if line else path
    try:
        subprocess.Popen([editor, "--goto", target], shell=False)
    except OSError as exc:
        return False, f"Failed to launch VS Code: {exc}"
    return True, target


def _shorten(text: str, limit: int = 2400) -> str:
    text = text.strip("\n")
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n..."


class RunExplanationPage:
    def __init__(self, run_dir: Path, repo_root: Path | None) -> None:
        self.run_dir = run_dir
        self.repo_root = repo_root
        self.result = _load_json(run_dir / "orchestration-result.json", {})
        self.evidence = _load_json(run_dir / "evidence-items.json", [])
        self.evidence_by_ref = self._build_evidence_lookup()
        self._snippet_card_counter = 0

    def _build_evidence_lookup(self) -> dict[str, dict[str, Any]]:
        lookup: dict[str, dict[str, Any]] = {}
        for item in self.evidence:
            source_id = str(item.get("source_id") or "")
            path, start, end = _parse_source_ref(source_id)
            keys = {source_id, _source_key(path, start, end)}
            if source_id.startswith("repo-pre:"):
                keys.add(source_id.removeprefix("repo-pre:"))
            if source_id.startswith("workspace:"):
                keys.add(source_id.removeprefix("workspace:"))
            for key in keys:
                lookup[key] = item
        return lookup

    def render(self) -> str:
        retrieval = self.result.get("retrieval_result") or {}
        summary = retrieval.get("retrieval_summary") or {}
        plan = summary.get("retrieval_plan") or retrieval.get("retrieval_plan") or {}
        response_payload = self.result.get("response_payload") or {}
        response_metadata = response_payload.get("metadata") or {}
        used_evidence_refs = response_metadata.get("used_evidence_refs") or response_payload.get("evidence_refs") or []
        title = self.result.get("conversation_id") or self.run_dir.name
        coverage = retrieval.get("coverage_status", "unknown")
        sufficient = self.result.get("sufficient", retrieval.get("sufficient", "unknown"))
        selected_count = summary.get("selected_count", retrieval.get("selected_count", len(self.evidence)))
        raw_prompt = str(plan.get("raw_prompt") or "").strip()
        explanation_markdown = str(response_payload.get("content") or "").strip()
        explanation_html = self._render_markdown(explanation_markdown, used_evidence_refs=used_evidence_refs) if explanation_markdown else "<p>No explanation content was generated.</p>"
        prompt_html = self._render_prompt(raw_prompt)

        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(str(title))}</title>
  <style>{CSS}</style>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <div>
        <p class="eyebrow">Retrieval Explanation Demo</p>
        <h1>{html.escape(str(title))}</h1>
        <p class="subtle">{html.escape(str(self.run_dir))}</p>
      </div>
      <div class="badges">
        <span class="badge">coverage: {html.escape(str(coverage))}</span>
        <span class="badge">sufficient: {html.escape(str(sufficient))}</span>
        <span class="badge">evidence: {html.escape(str(selected_count))}</span>
      </div>
    </section>

    <section class="panel">
      <h2>Issue Prompt</h2>
      {prompt_html}
    </section>

    <section class="panel chat">
      <h2>Explanation</h2>
      {explanation_html}
    </section>
  </main>
  <script>
    function openEvidenceLink(event, href) {{
      event.preventDefault();
      fetch(href, {{ method: "GET", credentials: "same-origin" }})
        .catch((error) => console.error("Failed to open editor link", error));
      return false;
    }}

    function toggleSnippetPanel(button) {{
      const card = button.closest(".snippetCard");
      if (!card) return;
      const code = card.querySelector(".snippetViewport code");
      const collapsed = card.querySelector("template[data-snippet-view='collapsed']");
      const expandedTemplate = card.querySelector("template[data-snippet-view='expanded']");
      if (!code || !collapsed || !expandedTemplate) return;
      const expanded = button.getAttribute("aria-expanded") === "true";
      button.setAttribute("aria-expanded", expanded ? "false" : "true");
      const text = button.querySelector(".snippetToggle span:last-child");
      const icon = button.querySelector(".snippetToggleIcon");
      if (expanded) {{
        code.innerHTML = collapsed.innerHTML;
        card.classList.remove("snippetCardExpanded");
        if (text) text.textContent = "Show full";
        if (icon) icon.textContent = "+";
      }} else {{
        code.innerHTML = expandedTemplate.innerHTML;
        card.classList.add("snippetCardExpanded");
        if (text) text.textContent = "Hide full";
        if (icon) icon.textContent = "-";
      }}
    }}
  </script>
</body>
</html>"""

    def _render_markdown(self, markdown_text: str, *, used_evidence_refs: Any) -> str:
        lines = markdown_text.splitlines()
        parts: list[str] = []
        ordered_refs = self._ordered_evidence_refs(used_evidence_refs)
        index = 0
        while index < len(lines):
            line = lines[index]
            stripped = line.strip()
            if not stripped:
                index += 1
                continue
            if stripped.startswith("```"):
                language = stripped[3:].strip()
                block: list[str] = []
                index += 1
                while index < len(lines) and not lines[index].strip().startswith("```"):
                    block.append(lines[index])
                    index += 1
                if index < len(lines):
                    index += 1
                block_text = chr(10).join(block)
                explicit_ref, next_index = self._detect_following_standalone_ref(lines, index)
                matched_ref = explicit_ref or self._match_code_block_ref(block_text, ordered_refs)
                if matched_ref:
                    index = next_index if explicit_ref else self._consume_following_standalone_ref(lines, index, matched_ref)
                    parts.append(self._render_snippet_card(block_text, language, matched_ref))
                else:
                    class_attr = f' class="language-{html.escape(language)}"' if language else ""
                    parts.append(f"<pre><code{class_attr}>{html.escape(block_text)}</code></pre>")
                continue
            if stripped.startswith(">"):
                block: list[str] = []
                while index < len(lines) and lines[index].strip().startswith(">"):
                    block.append(lines[index].strip()[1:].lstrip())
                    index += 1
                quoted = "<br>".join(self._render_inline(item) for item in block if item.strip())
                parts.append(f"<blockquote>{quoted}</blockquote>")
                continue
            if stripped.startswith("#"):
                level = min(len(stripped) - len(stripped.lstrip("#")), 6)
                content = stripped[level:].strip()
                parts.append(f"<h{level}>{self._render_inline(content)}</h{level}>")
                index += 1
                continue
            if stripped.startswith(("- ", "* ")):
                items: list[str] = []
                while index < len(lines) and lines[index].strip().startswith(("- ", "* ")):
                    items.append(lines[index].strip()[2:].strip())
                    index += 1
                parts.append("<ul>" + "".join(f"<li>{self._render_inline(item)}</li>" for item in items) + "</ul>")
                continue
            if ORDERED_LIST_RE.match(stripped):
                list_html, index = self._render_ordered_list(lines, index, ordered_refs)
                parts.append(list_html)
                continue

            paragraph_lines = [stripped]
            index += 1
            while index < len(lines):
                next_line = lines[index].strip()
                if not next_line:
                    break
                if next_line.startswith(("```", ">", "#", "- ", "* ")) or ORDERED_LIST_RE.match(next_line):
                    break
                paragraph_lines.append(next_line)
                index += 1
            parts.append(f"<p>{self._render_inline(' '.join(paragraph_lines))}</p>")
        return "\n".join(parts)

    def _render_inline(self, text: str) -> str:
        parts: list[str] = []
        cursor = 0
        for match in INLINE_TOKEN_RE.finditer(text):
            start, end = match.span()
            parts.append(html.escape(text[cursor:start]))
            if match.group(1) is not None:
                parts.append(self._render_ref_link(match.group(2), match.group(1)))
            elif match.group(3) is not None:
                parts.append(f"<code>{html.escape(match.group(3))}</code>")
            elif match.group(4) is not None:
                parts.append(f"<strong>{self._render_inline(match.group(4))}</strong>")
            cursor = end
        parts.append(html.escape(text[cursor:]))
        return "".join(parts)

    def _render_prompt(self, text: str) -> str:
        if not text:
            return '<p class="promptText">No prompt was captured for this run.</p>'
        paragraphs = [segment.strip() for segment in re.split(r"\n\s*\n", text) if segment.strip()]
        if not paragraphs:
            paragraphs = [text.strip()]
        return '<div class="promptCard">' + "".join(
            f'<p class="promptText">{html.escape(paragraph)}</p>' for paragraph in paragraphs
        ) + "</div>"

    def _render_ordered_list(self, lines: list[str], start_index: int, ordered_refs: list[str]) -> tuple[str, int]:
        items_html: list[str] = []
        index = start_index
        while index < len(lines):
            stripped = lines[index].strip()
            if not ORDERED_LIST_RE.match(stripped):
                break

            title_text = ORDERED_LIST_RE.sub("", stripped, count=1)
            index += 1
            body_lines: list[str] = []

            while index < len(lines):
                next_raw = lines[index]
                next_stripped = next_raw.strip()
                if ORDERED_LIST_RE.match(next_stripped):
                    break
                if next_stripped.startswith("#") or next_stripped.startswith("```") or next_stripped.startswith(">"):
                    break
                body_lines.append(next_raw)
                index += 1

            inner_parts = [f"<p>{self._render_inline(title_text)}</p>"]
            if any(line.strip() for line in body_lines):
                inner_body = self._render_markdown("\n".join(body_lines), used_evidence_refs=ordered_refs)
                if inner_body:
                    inner_parts.append(inner_body)
            items_html.append("<li>" + "".join(inner_parts) + "</li>")

            while index < len(lines) and not lines[index].strip():
                lookahead = index
                while lookahead < len(lines) and not lines[lookahead].strip():
                    lookahead += 1
                if lookahead < len(lines) and ORDERED_LIST_RE.match(lines[lookahead].strip()):
                    index = lookahead
                    break
                index += 1

        return "<ol>" + "".join(items_html) + "</ol>", index

    def _render_ref_link(self, ref_or_target: str, label: str | None = None, *, with_preview: bool = True) -> str:
        item = self._find_evidence_item(ref_or_target)
        target_label = label or self._display_ref_label(ref_or_target)
        if item:
            source_id = str(item.get("source_id") or ref_or_target)
            path, start, _end = _parse_source_ref(source_id)
            href = _editor_uri(self.repo_root, path, start)
            link_attrs = (
                f'class="evidenceLink" href="{html.escape(href)}" '
                f'onclick="return openEvidenceLink(event, this.href)"'
            )
            if with_preview:
                preview = html.escape(str(item.get("snippet") or "").strip())
                return (
                    f'<a {link_attrs}>{html.escape(target_label)}'
                    f'<span class="tooltip"><pre>{preview}</pre></span></a>'
                )
            return f'<a {link_attrs}>{html.escape(target_label)}</a>'
        if ref_or_target.startswith("http://") or ref_or_target.startswith("https://"):
            return f'<a href="{html.escape(ref_or_target)}">{html.escape(target_label)}</a>'
        return html.escape(target_label)

    def _ordered_evidence_refs(self, refs: Any) -> list[str]:
        if not isinstance(refs, list):
            refs = list(refs) if isinstance(refs, tuple) else []
        unique_refs: list[str] = []
        for ref in refs:
            ref_text = str(ref).strip()
            if ref_text and ref_text not in unique_refs:
                unique_refs.append(ref_text)
        return unique_refs

    def _match_code_block_ref(self, block_text: str, refs: list[str]) -> str | None:
        normalized_block = self._normalize_snippet_text(block_text)
        if len(normalized_block) < 24:
            return None
        for ref in refs:
            item = self._find_evidence_item(ref)
            if not item:
                continue
            snippet = str(item.get("snippet") or "")
            normalized_snippet = self._normalize_snippet_text(snippet)
            if normalized_block in normalized_snippet:
                return ref
        return None

    def _normalize_snippet_text(self, text: str) -> str:
        return re.sub(r"\s+", "", text or "")

    def _consume_following_standalone_ref(self, lines: list[str], index: int, ref: str) -> int:
        explicit_ref, next_index = self._detect_following_standalone_ref(lines, index)
        if explicit_ref and self._same_evidence_ref(explicit_ref, ref):
            return next_index
        return index

    def _detect_following_standalone_ref(self, lines: list[str], index: int) -> tuple[str | None, int]:
        probe = index
        while probe < len(lines) and not lines[probe].strip():
            probe += 1
        if probe >= len(lines):
            return None, index
        match = MARKDOWN_LINK_RE.fullmatch(lines[probe].strip())
        if match is None:
            return None, index
        target = match.group(2).strip()
        if not self._find_evidence_item(target):
            return None, index
        return target, probe + 1

    def _same_evidence_ref(self, left: str, right: str) -> bool:
        left_item = self._find_evidence_item(left)
        right_item = self._find_evidence_item(right)
        if not left_item or not right_item:
            return False
        return str(left_item.get("source_id") or "") == str(right_item.get("source_id") or "")

    def _render_snippet_card(self, block_text: str, language: str, ref: str) -> str:
        self._snippet_card_counter += 1
        card_id = f"snippet-full-{self._snippet_card_counter}"
        class_attr = f' class="language-{html.escape(language)}"' if language else ""
        item = self._find_evidence_item(ref) or {}
        full_snippet = str(item.get("snippet") or "").strip()
        has_full_panel = bool(full_snippet) and self._normalize_snippet_text(full_snippet) != self._normalize_snippet_text(block_text)
        toggle_html = ""
        template_html = ""
        collapsed_html = html.escape(block_text)
        if has_full_panel:
            toggle_html = (
                f'<button type="button" class="snippetToggle" aria-expanded="false" '
                f'aria-controls="{card_id}" onclick="toggleSnippetPanel(this)">'
                f'<span class="snippetToggleIcon" aria-hidden="true">+</span>'
                f'<span>Show full</span>'
                f"</button>"
            )
            expanded_html = self._render_expanded_snippet_html(full_snippet, block_text)
            template_html = (
                f'<template data-snippet-view="collapsed">{collapsed_html}</template>'
                f'<template data-snippet-view="expanded">{expanded_html}</template>'
            )
        return (
            '<div class="snippetCard">'
            '<div class="snippetHeader">'
            f'<p class="snippetSource">{self._render_ref_link(ref, self._display_ref_label(ref), with_preview=False)}</p>'
            f"{toggle_html}"
            "</div>"
            f"<pre class=\"snippetViewport\"><code{class_attr}>{collapsed_html}</code></pre>"
            f"{template_html}"
            "</div>"
        )

    def _render_expanded_snippet_html(self, full_snippet: str, selected_excerpt: str) -> str:
        match = self._find_excerpt_line_range(full_snippet, selected_excerpt)
        if match is None:
            return html.escape(full_snippet)
        start_line, end_line = match
        rendered_lines: list[str] = []
        full_lines = full_snippet.splitlines()
        trailing_newline = full_snippet.endswith("\n")
        for index, line in enumerate(full_lines):
            escaped_line = html.escape(line)
            if start_line <= index <= end_line:
                rendered_lines.append(f'<span class="snippetHighlight">{escaped_line}</span>')
            else:
                rendered_lines.append(escaped_line)
        rendered = "\n".join(rendered_lines)
        if trailing_newline:
            rendered += "\n"
        return rendered

    def _find_excerpt_line_range(self, full_snippet: str, selected_excerpt: str) -> tuple[int, int] | None:
        full_lines = full_snippet.splitlines()
        excerpt_lines = selected_excerpt.splitlines()
        if not full_lines or not excerpt_lines:
            return None
        meaningful_excerpt = [
            line for line in excerpt_lines
            if line.strip() and line.strip() not in {"...", "// ..."}
        ]
        if not meaningful_excerpt:
            return None

        first_match: int | None = None
        last_match: int | None = None
        search_start = 0
        for excerpt_line in meaningful_excerpt:
            found_index = None
            for candidate in range(search_start, len(full_lines)):
                if full_lines[candidate].strip() == excerpt_line.strip():
                    found_index = candidate
                    break
            if found_index is None:
                return None
            if first_match is None:
                first_match = found_index
            last_match = found_index
            search_start = found_index + 1
        if first_match is None or last_match is None:
            return None
        return first_match, last_match

    def _find_evidence_item(self, ref_or_target: str) -> dict[str, Any] | None:
        path_part, _, fragment = ref_or_target.partition("#")
        ref_key = f"{path_part}#{fragment}" if fragment else ref_or_target
        item = self.evidence_by_ref.get(ref_key)
        if item is None and fragment:
            item = self.evidence_by_ref.get("repo-pre:" + path_part + ":" + fragment.replace("-", "-L"))
        if item is None and fragment:
            item = self.evidence_by_ref.get("workspace:" + path_part + ":" + fragment.replace("-", "-L"))
        if item is None and ref_or_target in self.evidence_by_ref:
            item = self.evidence_by_ref.get(ref_or_target)
        return item

    def _display_ref_label(self, ref_or_target: str) -> str:
        item = self._find_evidence_item(ref_or_target)
        source_id = str(item.get("source_id") if item else ref_or_target)
        path, start, end = _parse_source_ref(source_id)
        if start is None:
            return path
        return f"{path}:L{start}-L{end or start}"


class Handler(BaseHTTPRequestHandler):
    page: RunExplanationPage

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/open":
            params = parse_qs(parsed.query)
            path = params.get("path", [""])[0]
            line_raw = params.get("line", [""])[0]
            line = int(line_raw) if line_raw.isdigit() else None
            if not path:
                self.send_error(400, "Missing path query parameter.")
                return
            if not Path(path).exists():
                self.send_error(404, f"Path does not exist: {path}")
                return
            ok, detail = _launch_editor(path, line)
            if not ok:
                self.send_error(500, detail)
                return
            body = (
                "<!doctype html><html><body>"
                "<script>window.close();</script>"
                f"<p>Opened {html.escape(detail)} in VS Code.</p>"
                "</body></html>"
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path not in {"/", "/index.html"}:
            self.send_error(404)
            return
        body = self.page.render().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"{self.address_string()} - {fmt % args}")


CSS = """
:root {
  color-scheme: light;
  --bg: #f7f4ed;
  --ink: #20201d;
  --muted: #6d675d;
  --line: #ded6c8;
  --panel: #fffdf8;
  --accent: #1f6f68;
  --accent-2: #a34b2d;
  --code: #17201f;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background:
    radial-gradient(circle at 20% 0%, rgba(31, 111, 104, 0.14), transparent 32rem),
    linear-gradient(180deg, #fbf8f0 0%, var(--bg) 70%);
  color: var(--ink);
  font: 16px/1.55 Georgia, "Times New Roman", serif;
}
a { color: var(--accent); text-decoration-thickness: 1px; text-underline-offset: 3px; }
.shell { width: min(1120px, calc(100% - 32px)); margin: 0 auto; padding: 32px 0 64px; }
.hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 24px;
  align-items: end;
  padding: 28px 0 22px;
  border-bottom: 1px solid var(--line);
}
.eyebrow {
  margin: 0 0 8px;
  color: var(--accent-2);
  font: 700 12px/1.2 Verdana, sans-serif;
  letter-spacing: .08em;
  text-transform: uppercase;
}
h1 { margin: 0; font-size: clamp(28px, 4vw, 48px); line-height: 1.05; font-weight: 700; }
h2, h3, h4, h5, h6 { font-family: Verdana, sans-serif; letter-spacing: 0; }
h2 { margin: 0 0 18px; font-size: 18px; }
h3 { margin: 22px 0 8px; font-size: 15px; }
.subtle { margin: 10px 0 0; color: var(--muted); font-size: 14px; overflow-wrap: anywhere; }
.badges { display: flex; flex-wrap: wrap; gap: 8px; justify-content: flex-end; }
.badge {
  border: 1px solid var(--line);
  background: rgba(255,255,255,.58);
  padding: 7px 10px;
  border-radius: 999px;
  color: var(--muted);
  font: 12px/1 Verdana, sans-serif;
}
.panel {
  margin-top: 24px;
  padding: 22px;
  background: rgba(255,253,248,.86);
  border: 1px solid var(--line);
  border-radius: 8px;
  box-shadow: 0 18px 45px rgba(74, 58, 37, .08);
}
.promptCard {
  padding: 18px 20px;
  border: 1px solid #e7dece;
  border-radius: 8px;
  background: #faf6ee;
}
.promptText {
  margin: 0;
  max-width: 88ch;
  color: #2f2b25;
  font-size: 18px;
  line-height: 1.65;
  white-space: pre-wrap;
}
.promptText + .promptText {
  margin-top: 14px;
}
.chat p, .chat li { max-width: 84ch; }
.chat ol { padding-left: 24px; }
.chat ul { padding-left: 22px; }
.snippetCard { margin: 14px 0 18px; }
.snippetHeader {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 6px;
}
pre {
  margin: 12px 0;
  padding: 14px;
  overflow: auto;
  border-radius: 8px;
  background: var(--code);
  color: #edf7f4;
  font: 13px/1.45 Consolas, "Courier New", monospace;
}
code {
  padding: 1px 4px;
  border-radius: 4px;
  background: #eee4d4;
  font-family: Consolas, "Courier New", monospace;
}
pre code {
  display: block;
  padding: 0;
  border-radius: 0;
  background: transparent;
  color: inherit;
}
blockquote {
  margin: 10px 0 18px;
  padding: 12px 14px;
  border-left: 4px solid var(--accent);
  background: #f2ece0;
  border-radius: 0 6px 6px 0;
  white-space: pre-wrap;
  font: 13px/1.5 Consolas, "Courier New", monospace;
}
.evidenceLink { position: relative; font-weight: 700; }
.evidenceLink::after {
  content: "";
  display: none;
  position: absolute;
  left: 0;
  top: 100%;
  width: min(680px, 80vw);
  height: 14px;
}
.tooltip {
  position: absolute;
  left: 0;
  top: calc(100% + 14px);
  width: min(680px, 80vw);
  z-index: 30;
  opacity: 0;
  visibility: hidden;
  pointer-events: none;
  transform: translateY(4px);
  transition:
    opacity 120ms ease,
    transform 120ms ease,
    visibility 0s linear 180ms;
}
.tooltip pre {
  max-height: 360px;
  border: 1px solid #263432;
  box-shadow: 0 20px 50px rgba(0,0,0,.28);
  white-space: pre-wrap;
}
.evidenceLink:hover::after,
.evidenceLink:focus-within::after {
  display: block;
}
.evidenceLink:hover .tooltip,
.evidenceLink:focus-within .tooltip {
  opacity: 1;
  visibility: visible;
  pointer-events: auto;
  transform: translateY(0);
  transition-delay: 0s;
}
.snippetSource {
  margin: 0;
  font: 12px/1.4 Verdana, sans-serif;
  color: var(--muted);
}
.snippetToggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border: 1px solid #314543;
  border-radius: 999px;
  background: rgba(23, 32, 31, 0.96);
  color: #edf7f4;
  font: 12px/1 Verdana, sans-serif;
  cursor: pointer;
}
.snippetToggle:hover {
  background: #20302e;
}
.snippetToggleIcon {
  display: inline-grid;
  place-items: center;
  width: 14px;
  height: 14px;
  font-weight: 700;
}
.snippetViewport {
  transition: max-height 180ms ease;
}
.snippetCardExpanded .snippetViewport {
  box-shadow: inset 0 0 0 1px rgba(124, 255, 161, 0.08);
}
.snippetHighlight {
  color: #7cff9e;
  font-weight: 700;
}
@media (max-width: 760px) {
  .hero { grid-template-columns: 1fr; }
  .badges { justify-content: flex-start; }
  .panel { padding: 16px; }
  .snippetHeader {
    align-items: flex-start;
    flex-direction: column;
  }
}
"""


def _find_free_port(preferred: int) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        if sock.connect_ex(("127.0.0.1", preferred)) != 0:
            return preferred
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve a human-readable retrieval run explanation.")
    parser.add_argument("--run-dir", required=True, type=Path, help="Run directory containing orchestration-result.json.")
    parser.add_argument("--repo-root", type=Path, help="Repository root used for editor links.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()

    run_dir = args.run_dir.resolve()
    repo_root = args.repo_root.resolve() if args.repo_root else _infer_repo_root(run_dir)
    if not (run_dir / "orchestration-result.json").exists():
        raise SystemExit(f"Missing orchestration-result.json in {run_dir}")

    Handler.page = RunExplanationPage(run_dir, repo_root)
    port = _find_free_port(args.port)
    server = ThreadingHTTPServer((args.host, port), Handler)
    print(f"Serving {run_dir}")
    if repo_root:
        print(f"Editor links resolve through {repo_root}")
    print(f"http://{args.host}:{port}/")
    server.serve_forever()


if __name__ == "__main__":
    main()
