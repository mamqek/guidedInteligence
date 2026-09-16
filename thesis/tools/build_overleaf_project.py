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


MAIN_TEX = r"""% !TeX program = lualatex
\RequirePackage[l2tabu]{nag}
\documentclass{mscthesis}

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
\cleartorecto{}
\makeformaltitlepages

\cleartorecto{}
\chapter{Abstract}
\import{frontmatter/}{abstract.tex}
\glsresetall{}

\cleartorecto{}
\chapter{Declaration on GenAI Use}
\import{frontmatter/}{declaration.tex}
\clearpage{}

\cleartorecto{}
\tableofcontents{}
\clearpage{}
\listoffigures{}
\clearpage{}
\listoftables{}
\clearpage{}

\cleartorecto{}
\chapter{Acknowledgements}
\import{frontmatter/}{acknowledgement.tex}

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

- Chapters 4--7 contain the converted Markdown prose.
- Chapter 8 contains the current discussion-planning note.
- Chapters 1, 2, 3, and 9 are structural placeholders so chapter numbering remains stable.
- The implemented intent-contract registry is included as an appendix.
- Author, examiner, reviewer, abstract, declaration, and acknowledgements remain placeholders.

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


def inline(value: str) -> str:
    value = normalise_punctuation(value.strip())
    protected: list[str] = []

    def token(content: str) -> str:
        index = len(protected)
        protected.append(content)
        return f"ZZPROTECTED{index}ZZ"

    value = value.replace("<br>", token(r"\newline{}"))
    value = re.sub(
        r"`([^`]+)`",
        lambda match: token(r"\texttt{" + escape_latex(match.group(1)) + "}"),
        value,
    )
    value = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda match: token(
            (
                rf"\hyperref[ch:{slug(Path(match.group(2)).stem.removeprefix('appendix-'))}]{{{escape_latex(match.group(1))}}}"
                if match.group(2).endswith(".md")
                else rf"\href{{{escape_latex(match.group(2))}}}{{{escape_latex(match.group(1))}}}"
            )
        ),
        value,
    )
    value = re.sub(
        r"\[(@[A-Za-z0-9_:-]+(?:\s*;\s*@[A-Za-z0-9_:-]+)*)\]",
        lambda match: token(
            r"\cite{" + ",".join(part.strip().removeprefix("@") for part in match.group(1).split(";")) + "}"
        ),
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


def table_layout(columns: int, caption: str) -> str:
    if columns == 2:
        return r"@{}L{0.19\linewidth}L{0.75\linewidth}@{}"
    if columns == 3:
        return r"@{}L{0.18\linewidth}L{0.36\linewidth}L{0.38\linewidth}@{}"
    if "retrieval conditions" in caption.casefold():
        return r"@{}L{0.28\linewidth}L{0.12\linewidth}L{0.16\linewidth}L{0.34\linewidth}@{}"
    if columns == 6:
        return r"@{}L{0.16\linewidth}L{0.16\linewidth}L{0.16\linewidth}L{0.16\linewidth}L{0.16\linewidth}L{0.16\linewidth}@{}"
    if columns == 7:
        return r"@{}L{0.19\linewidth}L{0.125\linewidth}L{0.125\linewidth}L{0.125\linewidth}L{0.125\linewidth}L{0.125\linewidth}L{0.125\linewidth}@{}"
    return r"@{}L{0.13\linewidth}L{0.25\linewidth}L{0.31\linewidth}L{0.23\linewidth}@{}"


def render_table(rows: list[list[str]], caption: str, label: str, *, landscape: bool) -> str:
    headers = rows[0]
    body = rows[1:]
    layout = table_layout(len(headers), caption)
    header = " & ".join(r"\textbf{" + inline(cell) + "}" for cell in headers) + r" \\"
    output: list[str] = []
    if landscape:
        output.append(r"\begin{landscape}")
    output.extend(
        [
            r"\begingroup",
            r"\small",
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
            rendered.extend([rf"\chapter{{{inline(title)}}}\label{{ch:{slug(title)}}}", ""])
            section_name = title
            index += 1
            continue
        if stripped.startswith("## "):
            title = stripped[3:].strip()
            rendered.extend([rf"\section{{{inline(title)}}}\label{{sec:{slug(title)}}}", ""])
            section_name = title
            index += 1
            continue
        if stripped.startswith("### "):
            title = stripped[4:].strip()
            rendered.extend([rf"\subsection{{{inline(title)}}}\label{{subsec:{slug(title)}}}", ""])
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
            rendered.extend(r"\item " + inline(item) for item in items)
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
                rendered.append(r"\item " + inline(re.sub(r"^\d+\.\s+", "", lines[index].strip())))
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
                        rendered.extend([inline(continuation_stripped), ""])
                        index += 1
            rendered.extend([r"\end{enumerate}", ""])
            continue

        if stripped:
            rendered.extend([inline(stripped), ""])
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

    appendix_name = "appendix-implemented-intent-contract-registry.md"
    appendix_markdown = (MANUSCRIPT / appendix_name).read_text(encoding="utf-8")
    (output / "appendix" / "implemented-intent-contract-registry.tex").write_text(
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build the Overleaf thesis project from Markdown sources.")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    build(args.output.resolve())
