# Overleaf supervisor-feedback audit — 27 October 2026

## Scope and result

Review the live Overleaf project `6aa153cea718ddbe28a32b64` against the approved manuscript and Overleaf repository commits `6eb8881`, `6e5f606`, and `f1cfea0`. Resolve addressed comments rather than deleting their history. Keep unfinished requests open.

The initial project-wide overview contains 94 comment threads and 28 tracked-edit entries. At completion, 91 threads are resolved, all 28 tracked edits are accepted, and three Chapter 5 requests remain open. No other file appears with unresolved feedback in the project-wide overview.

| Chapter | Initial comment threads | Resolved | Still open | Accepted tracked edits |
|---|---:|---:|---:|---:|
| 1 | 21 | 21 | 0 | 1 |
| 2 | 10 | 10 | 0 | 1 |
| 3 | 15 | 15 | 0 | 13 |
| 4 | 34 | 34 | 0 | 10 |
| 5 | 5 | 2 | 3 | 0 |
| 6 | 9 | 9 | 0 | 3 |
| **Total** | **94** | **91** | **3** | **28** |

The resolved threads cover the previously approved wording, definitions, citations, typography, evaluation-method clarifications, and deliberate removals. Positive acknowledgements are also resolved. The Chapter 4 review includes the older September comments as well as the October feedback.

## Requests left open

- **Pipeline diagram** — 7 October, 2:01 pm: “can you maybe make / simulate / use GenAI to make a diagram for this pipeline?” The sketch does not yet constitute an incorporated thesis figure.
- **Worked example / visual explanation** — 7 October, 2:03 pm: “can you add a toy example in the main body? i think more exemplifications/visualisations would help follow through; if it's too much text (like bulks of text) a reader can easily get lost in it”. No worked example is incorporated yet.
- **Motivation for parameter choices** — 7 October, 2:00 pm: “you make a few decisions in this chapter but you don't motivate why, especially why you chose the hyperparameters you use; for example why 3 rounds and not 10?” The manuscript includes the approved general rationale for the normal three-round limit, but this does not fully answer the broader request. Keep the thread open for a focused review of remaining choices.

## Citation cleanup and synchronization

Remove 50 literal parenthesis pairs surrounding `\textcite{...}`: Chapter 1 (8), Chapter 2 (13), Chapter 3 (21), Chapter 4 (1), Chapter 5 (3), and Chapter 8 (4). Preserve the command, citation keys, surrounding wording, and all table layouts. Resolve the new 27 October citation-parentheses comment after pulling the correction into Overleaf.

Update the Markdown exporter, conversion convention, and regression test so bracketed Markdown citations also produce bare `\textcite{...}`. All 13 exporter checks pass. A programmatic comparison confirms that every changed chapter is exactly its previous text with these wrappers removed.

Accepting the old tracked edits produces no exported source difference: Overleaf-to-GitHub synchronization and a subsequent fetch leave the source at `f1cfea0`. This preserves the approved “ground-truth repository files” definition and superseding citation/wording edits.

The citation correction is committed and pushed in the separate Overleaf repository as `c7b4c80` (`Remove extra parentheses around text citations`), then pulled successfully through the Overleaf GitHub integration. The local checkout and remote main point to the same commit.

## Verification and remaining formatting diagnostics

Overleaf recompiles the thesis with **0 errors**, **4 font-substitution warnings**, and **22 typesetting information entries**. These include overfull and underfull boxes; this task does not claim that the document is free of layout issues. The local built-in compiler cannot run this LuaLaTeX-only template because the required TeX Live runtime is unavailable; the successful compile check is performed in Overleaf.

Do not re-resolve the three open requests until their actual deliverables or motivations are incorporated and checked.
