from __future__ import annotations

import re
import shutil
import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
THESIS = ROOT / "thesis"
TEMPLATE = THESIS / "template"
MANUSCRIPT = THESIS / "manuscript"
OUTPUT = THESIS / "overleaf"


CHAPTERS = {
    "01-introduction.md": "01-introduction.tex",
    "02-background.md": "02-background.tex",
    "03-related-work.md": "03-related-work.tex",
    "04-research-method.md": "04-research-method.tex",
    "05-guided-intelligence-architecture.md": "05-guided-intelligence-architecture.tex",
    "06-retrieval-design-rationale-and-evolution.md": "06-retrieval-design-rationale-and-evolution.tex",
    "07-evaluation.md": "07-evaluation.tex",
    "08-discussion.md": "08-discussion.tex",
    "09-conclusion.md": "09-conclusion.tex",
}


PLACEHOLDERS = {
    "01-introduction.md": "Introduction",
    "02-background.md": "Background",
    "03-related-work.md": "Related Work",
    "09-conclusion.md": "Conclusion",
}

APPENDICES = {
    "appendix-implemented-intent-contract-registry.md": "implemented-intent-contract-registry.tex",
    "appendix-required-evidence-audit.md": "required-evidence-audit.tex",
}


MAIN_TEX = r"""% !TeX program = lualatex
\RequirePackage[l2tabu]{nag}
\documentclass{mscthesis}
\let\cleardoublepage\clearpage

\usepackage{import}
\usepackage[final]{microtype}
\usepackage{polyglossia}
\setmainlanguage[variant=british]{english}
\usepackage[backend=biber,
            hyperref=true,
            isbn=true,
            backref=false,
            maxcitenames=3,
            maxbibnames=100,
            block=none,
            style=numeric-comp,
            giveninits=true,
            sortlocale=auto]{biblatex}
\addbibresource{references.bib}
\DefineBibliographyStrings{english}{bibliography={References},references={References}}

\usepackage[svgnames]{xcolor}
\usepackage{graphicx}
\graphicspath{{./figures/}}
\setkeys{Gin}{width=0.9\linewidth}
\usepackage{subcaption}
\captionsetup{margin=1pt}
\usepackage[colorlinks=false,pdfborder={0 0 0},pdfusetitle]{hyperref}
\urlstyle{same}
\usepackage{booktabs}
\usepackage{mathtools}
\usepackage{cleveref}
\usepackage[british,xlatin,abbreviations]{foreign}
\usepackage[cachedir=_minted-\jobname,chapter]{minted}
\setminted{style=tango,frame=lines,framesep=2mm,fontsize=\small,linenos,breaklines,breakafter=-/,tabsize=2}
\usepackage[colorinlistoftodos]{todonotes}
\usepackage[acronym,shortcuts=ac,nomain,nonumberlist]{glossaries-extra}
\makeglossaries{}
\setabbreviationstyle[acronym]{long-short}
\loadglsentries{acronyms}
\usepackage[shortlabels,inline]{enumitem}
\setlist{noitemsep}
\usepackage{etoolbox}
\AtBeginEnvironment{tabular}{\addfontfeatures{Numbers={Lining}}}

\usepackage{array}
\usepackage{longtable}
\usepackage{pdflscape}
\usepackage{ragged2e}
\newcolumntype{L}[1]{>{\RaggedRight\arraybackslash}p{#1}}
\setlength{\LTpre}{0.5\baselineskip}
\setlength{\LTpost}{0.5\baselineskip}

\title{Guided Intelligence}
\subtitle{Controlled and Auditable Repository Evidence Construction}
\date{\today}
\author{Vladislav Mukhachev}
\examiner{Academic Supervisor}{University of Amsterdam}
\reviewer{Second Reviewer}{University of Amsterdam}
\begin{document}
\frontmatter
\makecoverpage
\makeformaltitlepages

\tableofcontents{}
\listoftables{}

\mainmatter
\import{chapters/}{01-introduction.tex}
\import{chapters/}{02-background.tex}
\import{chapters/}{03-related-work.tex}
\import{chapters/}{04-research-method.tex}
\import{chapters/}{05-guided-intelligence-architecture.tex}
\import{chapters/}{06-retrieval-design-rationale-and-evolution.tex}
\import{chapters/}{07-evaluation.tex}
\import{chapters/}{08-discussion.tex}
\import{chapters/}{09-conclusion.tex}

\appendix
\import{appendix/}{implemented-intent-contract-registry.tex}
\import{appendix/}{required-evidence-audit.tex}

\backmatter
\printbibliography{}
\cleardoublepage{}
\printacronyms[style=long,title={Acronyms}]
\cleardoublepage{}
\end{document}
"""


README = """# Guided Intelligence thesis - Overleaf project

This directory follows the official UvA MSc Software Engineering LaTeX template.
Upload the accompanying ZIP to Overleaf and set `main.tex` as the main document.
In Overleaf, open **Menu**, set **Compiler** to **LuaLaTeX**, and recompile.
Bibliography processing uses Biber.

Current manuscript state:

- Chapters 1--9 contain the converted thesis manuscript.
- The implemented intent-contract registry and required-evidence audit are included as appendices.
- Author, examiner, and reviewer remain placeholders. Empty abstract,
  declaration, acknowledgements, and figure-list pages are omitted until they
  contain thesis content.

The `source-markdown` directory contains a snapshot of the Markdown manuscript and thesis plan used for this export. Re-run `thesis/tools/build_overleaf_project.py` from the repository when a fresh export is needed.
"""


def slug(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return value or "section"


def escape_latex(value: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(char, char) for char in value)


def normalise_punctuation(value: str) -> str:
    return (
        value.replace("\u2014", "---")
        .replace("\u2013", "--")
        .replace("\u2011", "-")
        .replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u201c", "``")
        .replace("\u201d", "''")
    )


def inline(value: str, *, repository_footnotes: bool = False) -> str:
    value = normalise_punctuation(value.strip())
    protected: list[str] = []

    def token(content: str) -> str:
        index = len(protected)
        protected.append(content)
        return f"ZZPROTECTED{index}ZZ"

    def link(match: re.Match[str]) -> str:
        label, target = match.groups()
        if repository_footnotes and target in {
            "https://github.com/microsoft/TypeScript",
            "https://github.com/pandas-dev/pandas",
            "https://github.com/vuejs/vue",
        }:
            return token(escape_latex(label) + rf"\footnote{{\url{{{target}}}}}")
        if target.endswith(".md"):
            return token(
                rf"\hyperref[ch:{slug(Path(target).stem.removeprefix('appendix-'))}]"
                + "{" + escape_latex(label) + "}"
            )
        return token(rf"\href{{{escape_latex(target)}}}{{{escape_latex(label)}}}")

    value = value.replace("<br>", token(r"\newline{}"))
    value = re.sub(
        r"`([^`]+)`",
        lambda match: token(r"\texttt{" + escape_latex(match.group(1)) + "}"),
        value,
    )
    value = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        link,
        value,
    )
    value = re.sub(
        r"\[(@[A-Za-z0-9_:-]+(?:\s*;\s*@[A-Za-z0-9_:-]+)*)\]",
        lambda match: token(
            r"\textcite{" + ",".join(part.strip().removeprefix("@") for part in match.group(1).split(";")) + "}"
        ),
        value,
    )
    value = re.sub(
        r"(?<![A-Za-z0-9_])@([A-Za-z0-9_:-]+)",
        lambda match: token(r"\textcite{" + match.group(1) + "}"),
        value,
    )
    value = re.sub(r"\$([^$]+)\$", lambda match: token("$" + match.group(1) + "$"), value)
    value = re.sub(
        r"\*\*([^*]+)\*\*",
        lambda match: token(r"\textbf{" + escape_latex(match.group(1)) + "}"),
        value,
    )
    value = re.sub(
        r"(?<!\*)\*([^*]+)\*(?!\*)",
        lambda match: token(r"\emph{" + escape_latex(match.group(1)) + "}"),
        value,
    )
    rendered = escape_latex(value)
    for index in range(len(protected) - 1, -1, -1):
        content = protected[index]
        rendered = rendered.replace(f"ZZPROTECTED{index}ZZ", content)
    return rendered


def split_table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def table_layout(headers: list[str], caption: str) -> str:
    columns = len(headers)
    if columns >= 8 and headers[:2] == ["Condition", "Repetition / run ID"]:
        unit_columns = columns - 7
        return (
            r"@{}L{0.12\linewidth}L{0.16\linewidth}"
            + rf"*{{{unit_columns}}}{{L{{0.025\linewidth}}}}"
            + r"L{0.055\linewidth}L{0.055\linewidth}L{0.095\linewidth}"
            + r"L{0.095\linewidth}L{0.24\linewidth}@{}"
        )
    if columns == 2:
        return r"@{}L{0.19\linewidth}L{0.75\linewidth}@{}"
    if columns == 3:
        return r"@{}L{0.18\linewidth}L{0.36\linewidth}L{0.38\linewidth}@{}"
    if "retrieval conditions" in caption.casefold():
        return r"@{}L{0.28\linewidth}L{0.14\linewidth}L{0.14\linewidth}L{0.34\linewidth}@{}"
    if columns == 6:
        return r"@{}L{0.16\linewidth}L{0.16\linewidth}L{0.16\linewidth}L{0.16\linewidth}L{0.16\linewidth}L{0.16\linewidth}@{}"
    if columns == 7:
        return r"@{}L{0.19\linewidth}L{0.125\linewidth}L{0.125\linewidth}L{0.125\linewidth}L{0.125\linewidth}L{0.125\linewidth}L{0.125\linewidth}@{}"
    return r"@{}L{0.13\linewidth}L{0.25\linewidth}L{0.31\linewidth}L{0.23\linewidth}@{}"


def render_table(rows: list[list[str]], caption: str, label: str, *, landscape: bool) -> str:
    headers = rows[0]
    body = rows[1:]
    layout = table_layout(headers, caption)
    header = " & ".join(r"\textbf{" + inline(cell) + "}" for cell in headers) + r" \\"
    output: list[str] = []
    if landscape:
        output.append(r"\begin{landscape}")
    output.extend(
        [
            r"\begingroup",
            r"\scriptsize" if len(headers) >= 8 else r"\small",
            rf"\begin{{longtable}}{{{layout}}}",
            rf"\caption{{{inline(caption)}}}\label{{{label}}}\\",
            r"\toprule",
            header,
            r"\midrule",
            r"\endfirsthead",
            rf"\multicolumn{{{len(headers)}}}{{c}}{{\tablename\ \thetable\ -- continued}}\\",
            r"\toprule",
            header,
            r"\midrule",
            r"\endhead",
            r"\midrule",
            rf"\multicolumn{{{len(headers)}}}{{r}}{{Continued on next page}}\\",
            r"\endfoot",
            r"\bottomrule",
            r"\endlastfoot",
        ]
    )
    output.extend(" & ".join(inline(cell) for cell in row) + r" \\" for row in body)
    output.extend([r"\end{longtable}", r"\endgroup"])
    if landscape:
        output.append(r"\end{landscape}")
    return "\n".join(output)


def markdown_to_latex(source: str, *, appendix: bool = False) -> str:
    lines = source.splitlines()
    rendered: list[str] = []
    section_name = ""
    table_number = 0
    index = 0
    in_comment = False
    comment_parts: list[str] = []
    def render_inline(value: str) -> str:
        return inline(value, repository_footnotes=source.startswith("# Introduction\n"))

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if in_comment:
            if "-->" in stripped:
                comment_parts.append(stripped.split("-->", 1)[0])
                rendered.append("% " + " ".join(part.strip() for part in comment_parts if part.strip()))
                in_comment = False
                comment_parts = []
            else:
                comment_parts.append(stripped)
            index += 1
            continue

        if stripped.startswith("<!--"):
            content = stripped.removeprefix("<!--")
            if "-->" in content:
                rendered.append("% " + content.split("-->", 1)[0].strip())
            else:
                in_comment = True
                comment_parts = [content]
            index += 1
            continue

        if stripped.startswith("# "):
            title = stripped[2:].strip()
            display_title = re.sub(r"^Appendix:\s*", "", title, flags=re.IGNORECASE) if appendix else title
            rendered.extend([rf"\chapter{{{render_inline(display_title)}}}\label{{ch:{slug(display_title)}}}", ""])
            section_name = display_title
            index += 1
            continue
        if stripped.startswith("## "):
            title = stripped[3:].strip()
            rendered.extend([rf"\section{{{render_inline(title)}}}\label{{sec:{slug(title)}}}", ""])
            section_name = title
            index += 1
            continue
        if stripped.startswith("### "):
            title = stripped[4:].strip()
            rendered.extend([rf"\subsection{{{render_inline(title)}}}\label{{subsec:{slug(title)}}}", ""])
            section_name = title
            index += 1
            continue

        if stripped.startswith("|"):
            raw_rows: list[list[str]] = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                raw_rows.append(split_table_row(lines[index]))
                index += 1
            if len(raw_rows) >= 2 and all(re.fullmatch(r":?-+:?", cell.replace(" ", "")) for cell in raw_rows[1]):
                raw_rows.pop(1)
            table_number += 1
            caption = section_name if appendix else {
                ("Evaluated Systems and Comparison Design", 1): "Evaluated retrieval conditions",
                ("Intent Classification, Retrieval Context, and Source Policy", 1): "Implemented task-intent taxonomy",
                ("Controller Evidence Completion", 2): "Controller action families and scheduling dependencies",
                ("Decision Ownership, Provenance, and Operational Boundaries", 3): "Decision ownership and validation boundaries",
                ("Overall Retrieval Performance", 1): "Aggregate file-ranking results",
                ("Overall Retrieval Performance", 2): "File-ranking results by data partition",
                ("Component Effects and Mechanism Coverage", 3): "Factorial capability contrasts",
                ("Operational Cost and Stability", 4): "Operational cost and repeated-run stability",
            }.get((section_name, table_number), section_name)
            rendered.extend(
                [
                    render_table(
                        raw_rows,
                        caption,
                        f"tab:{slug(caption)}-{table_number}",
                        landscape=(appendix and len(raw_rows[0]) >= 3) or len(raw_rows[0]) >= 6,
                    ),
                    "",
                ]
            )
            continue

        if stripped.startswith("- "):
            items: list[str] = []
            while index < len(lines) and lines[index].strip().startswith("- "):
                items.append(lines[index].strip()[2:])
                index += 1
            rendered.append(r"\begin{itemize}")
            rendered.extend(r"\item " + render_inline(item) for item in items)
            rendered.extend([r"\end{itemize}", ""])
            continue

        if stripped == "$$":
            equation: list[str] = []
            index += 1
            while index < len(lines) and lines[index].strip() != "$$":
                equation.append(lines[index].strip())
                index += 1
            if index >= len(lines):
                raise ValueError("Unclosed display-math block")
            rendered.extend([r"\[", "\n".join(equation), r"\]", ""])
            index += 1
            continue

        if re.match(r"\d+\.\s+", stripped):
            rendered.append(r"\begin{enumerate}")
            while index < len(lines) and re.match(r"\d+\.\s+", lines[index].strip()):
                rendered.append(r"\item " + render_inline(re.sub(r"^\d+\.\s+", "", lines[index].strip())))
                index += 1
                while index < len(lines):
                    continuation = lines[index]
                    continuation_stripped = continuation.strip()
                    if re.match(r"\d+\.\s+", continuation_stripped):
                        break
                    if continuation_stripped and not continuation.startswith((" ", "\t")):
                        break
                    if not continuation_stripped:
                        index += 1
                        continue
                    if continuation_stripped == "$$":
                        equation = []
                        index += 1
                        while index < len(lines) and lines[index].strip() != "$$":
                            equation.append(lines[index].strip())
                            index += 1
                        if index >= len(lines):
                            raise ValueError("Unclosed display-math block in ordered list")
                        rendered.extend([r"\[", "\n".join(equation), r"\]"])
                        index += 1
                    else:
                        rendered.extend([render_inline(continuation_stripped), ""])
                        index += 1
            rendered.extend([r"\end{enumerate}", ""])
            continue

        if stripped:
            rendered.extend([render_inline(stripped), ""])
        elif rendered and rendered[-1] != "":
            rendered.append("")
        index += 1

    return "\n".join(rendered).rstrip() + "\n"


def build(output: Path = OUTPUT) -> None:
    if output.exists():
        raise RuntimeError(f"Refusing to overwrite existing output directory: {output}")
    shutil.copytree(TEMPLATE, output)

    for example_path in (
        output / "figures" / "hilbert.pdf",
        output / "figures" / "maze.pdf",
        output / "frontmatter" / "epigraph.tex",
    ):
        example_path.unlink(missing_ok=True)

    shutil.rmtree(output / "chapters")
    shutil.rmtree(output / "appendix")
    (output / "chapters").mkdir()
    (output / "appendix").mkdir()
    (output / "source-markdown").mkdir()

    (output / "main.tex").write_text(MAIN_TEX, encoding="utf-8")
    (output / "README.md").write_text(README, encoding="utf-8")
    (output / "acronyms.tex").write_text("", encoding="utf-8")
    (output / "frontmatter" / "abstract.tex").write_text("", encoding="utf-8")
    (output / "frontmatter" / "acknowledgement.tex").write_text("", encoding="utf-8")
    (output / "frontmatter" / "declaration.tex").write_text("", encoding="utf-8")

    for markdown_name, tex_name in CHAPTERS.items():
        source_path = MANUSCRIPT / markdown_name
        if source_path.exists():
            markdown = source_path.read_text(encoding="utf-8")
        else:
            title = PLACEHOLDERS[markdown_name]
            markdown = f"# {title}\n"
        (output / "chapters" / tex_name).write_text(markdown_to_latex(markdown), encoding="utf-8")
        (output / "source-markdown" / markdown_name).write_text(markdown, encoding="utf-8")

    for appendix_name, tex_name in APPENDICES.items():
        appendix_markdown = (MANUSCRIPT / appendix_name).read_text(encoding="utf-8")
        (output / "appendix" / tex_name).write_text(
            markdown_to_latex(appendix_markdown, appendix=True), encoding="utf-8"
        )
        (output / "source-markdown" / appendix_name).write_text(appendix_markdown, encoding="utf-8")
    shutil.copy2(THESIS / "sources" / "thesis-plan.md", output / "source-markdown" / "thesis-plan.md")

    bibliography = (MANUSCRIPT / "references.bib").read_text(encoding="utf-8").rstrip()
    template_bibliography = (TEMPLATE / "references.bib").read_text(encoding="utf-8")
    code_repo_entry = re.search(
        r"@inproceedings\{Hu2025CodeRepoQA,.*?\n\}", template_bibliography, flags=re.DOTALL
    )
    if code_repo_entry and "Hu2025CodeRepoQA" not in bibliography:
        bibliography += "\n\n" + code_repo_entry.group(0)
    (output / "references.bib").write_text(bibliography + "\n", encoding="utf-8")


TABLE_BLOCK = re.compile(
    r"(?:\\begin\{landscape\}\s*)?"
    r"(?:\\Needspace\{[^}]+\}\s*)?"
    r"(?:\\begin\{table\}.*?\\end\{table\}"
    r"|\\begingroup(?:(?!\\begingroup).)*?\\begin\{longtable\}"
    r".*?\\end\{longtable\}\s*\\endgroup)"
    r"(?:\s*\\(?:FloatBarrier|Needspace\{[^}]+\}))*"
    r"(?:\s*\\end\{landscape\})?",
    re.DOTALL,
)


def reviewed_terminology(value: str) -> str:
    """Only the approved prose-label changes; never rewrite source identifiers."""
    for before, after in (
        ("Implementation-Oracle", "Implementation-oracle"),
        ("implementation Oracle", "implementation oracle"),
        ("implementation-Oracle", "implementation-oracle"),
        ("file Oracle", "file oracle"),
        ("Required units", "Required snippets"),
        ("required units", "required snippets"),
        ("Required source units", "Required source snippets"),
        ("exact source units", "exact source snippets"),
        ("required unit", "required snippet"),
        ("Unit unavailability", "Snippet unavailability"),
        ("unit is unavailable", "snippet is unavailable"),
        ("each unit", "each snippet"),
        (r"\textbf{Unit}", r"\textbf{Snippet}"),
        ("| Unit |", "| Snippet |"),
    ):
        value = value.replace(before, after)
    return value


def md_tables(source: str) -> list[str]:
    return re.findall(r"(?:^\|.*(?:\n|$))+", source, re.MULTILINE)


def preserve_tables(rendered: str, existing: str, old_markdown: str, markdown: str) -> str:
    """Refresh prose without discarding the reviewed, hand-typeset tables."""
    old_tables, current_tables = md_tables(old_markdown), md_tables(markdown)
    if len(old_tables) != len(current_tables):
        raise ValueError("Table count changed: review layouts before syncing")
    for old, current in zip(old_tables, current_tables):
        if reviewed_terminology(old) != current:
            raise ValueError("Table content changed beyond approved labels: review before syncing")
    retained = list(TABLE_BLOCK.finditer(existing))
    generated = list(TABLE_BLOCK.finditer(rendered))
    if len(retained) != len(current_tables) or len(generated) != len(current_tables):
        raise ValueError("Could not identify every existing table; refusing a destructive re-export")
    for new, old in reversed(list(zip(generated, retained))):
        rendered = rendered[:new.start()] + reviewed_terminology(old.group()) + rendered[new.end():]
    # Keep the same paragraph together, not simply the chapter's last paragraph.
    if r"\begin{samepage}" in existing:
        if existing.count(r"\begin{samepage}") != 1 or not retained:
            raise ValueError("Unrecognised samepage layout; review before syncing")
        paragraph = existing.split(r"\begin{samepage}", 1)[1].split(r"\end{samepage}", 1)[0].strip()
        anchor = paragraph[:60]
        if rendered.count(anchor) != 1:
            raise ValueError("Cannot anchor the samepage paragraph after editing; review before syncing")
        start = rendered.index(anchor)
        end = rendered.find("\n\n", start)
        if end < 0:
            end = len(rendered.rstrip())
        rendered = (rendered[:start] + "\\begin{samepage}\n" + rendered[start:end]
                    + "\n\\end{samepage}" + rendered[end:])
    return rendered


def sync_existing(output: Path, *, dry_run: bool = False) -> None:
    """Update an existing checkout, preserving its template and table layouts."""
    changes: dict[Path, str] = {}
    snapshot = output / "source-markdown"
    for markdown_name, tex_name in CHAPTERS.items():
        markdown = (MANUSCRIPT / markdown_name).read_text(encoding="utf-8")
        old_markdown = (snapshot / markdown_name).read_text(encoding="utf-8")
        destination = output / "chapters" / tex_name
        existing = destination.read_text(encoding="utf-8")
        changes[destination] = preserve_tables(
            markdown_to_latex(markdown), existing, old_markdown, markdown
        )
        changes[snapshot / markdown_name] = markdown

    # The separately submitted audit has custom numbering and wrapping. Apply
    # only the reviewed terminology, rather than regenerating its 70 tables.
    audit_name = "appendix-required-evidence-audit.md"
    old_audit = (snapshot / audit_name).read_text(encoding="utf-8")
    audit = (MANUSCRIPT / audit_name).read_text(encoding="utf-8")
    old_audit = old_audit.replace("# Appendix: Required-Evidence Audit", "# Required-Evidence Audit")
    old_audit = old_audit.replace("This appendix reports", "This separately submitted companion file reports")
    if reviewed_terminology(old_audit) != audit:
        raise ValueError("Audit changes exceed terminology: review its custom layout before syncing")
    audit_tex = output / "appendix" / "required-evidence-audit.tex"
    changes[audit_tex] = reviewed_terminology(audit_tex.read_text(encoding="utf-8"))
    changes[snapshot / audit_name] = audit
    changes[output / "references.bib"] = (MANUSCRIPT / "references.bib").read_text(encoding="utf-8")
    changes[snapshot / "README.md"] = (MANUSCRIPT / "README.md").read_text(encoding="utf-8")

    # The full audit is a companion, not part of the thesis PDF or its contents.
    main_path = output / "main.tex"
    main = main_path.read_text(encoding="utf-8")
    main = main.replace("\\import{appendix/}{required-evidence-audit.tex}\n", "")
    changes[main_path] = main
    # Validate every conversion before writing any file.
    for path, content in changes.items():
        if path.suffix == ".tex" and re.search(
            r"\\(?:cite|parencite|autocite)\{|(?<![A-Za-z0-9_])@[A-Z][A-Za-z0-9_:-]{2,}", content
        ):
            raise ValueError(f"Unconverted citation in {path}")
    for path, content in changes.items():
        if path.exists() and path.read_text(encoding="utf-8") == content:
            continue
        print(f"{'Would update' if dry_run else 'Updated'} {path}")
        if not dry_run:
            path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build the Overleaf thesis project from Markdown sources.")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--sync-existing", action="store_true", help="Preserve an existing checkout's table layouts")
    parser.add_argument("--dry-run", action="store_true", help="Validate sync and list changes without writing")
    args = parser.parse_args()
    if args.sync_existing:
        sync_existing(args.output.resolve(), dry_run=args.dry_run)
    elif args.dry_run:
        parser.error("--dry-run requires --sync-existing")
    else:
        build(args.output.resolve())
