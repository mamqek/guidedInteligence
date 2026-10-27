"""Conversion contracts for reviewed prose and hand-typeset Overleaf tables."""

import re
import unittest

import build_overleaf_project as exporter


class ConversionTests(unittest.TestCase):
    def test_narrative_citation(self):
        self.assertEqual(exporter.inline("@Ko2007InformationNeeds find"), r"\textcite{Ko2007InformationNeeds} find")

    def test_bracketed_citations_use_textcite_without_outer_parentheses(self):
        self.assertEqual(exporter.inline("findings [@Ko2007InformationNeeds; @Sillito2008ProgrammingQuestions]"),
                         r"findings \textcite{Ko2007InformationNeeds,Sillito2008ProgrammingQuestions}")

    def test_citations_do_not_consume_metric_notation(self):
        self.assertEqual(exporter.inline("$IDCG@k$ and R@10"), "$IDCG@k$ and R@10")

    def test_definition_italics(self):
        self.assertEqual(exporter.inline("*source observations*"), r"\emph{source observations}")

    def test_repository_introduction_footnotes(self):
        source = "# Introduction\n\n[TypeScript](https://github.com/microsoft/TypeScript)"
        self.assertIn(r"TypeScript\footnote{\url{https://github.com/microsoft/TypeScript}}", exporter.markdown_to_latex(source))
        self.assertIn(r"\href", exporter.markdown_to_latex(source.replace("Introduction", "Background")))

    def test_appendix_link(self):
        self.assertEqual(exporter.inline("[Registry](appendix-implemented-intent-contract-registry.md)"),
                         r"\hyperref[ch:implemented-intent-contract-registry]{Registry}")

    def test_formula_and_continuation_stay_in_list(self):
        source = "# Measures\n\n1. **Precision.**\n\n   $$\n   P@k = \\frac{TP_k}{k}.\n   $$\n\n   The denominator stays $k$.\n\n2. **Recall.**"
        result = exporter.markdown_to_latex(source)
        self.assertLess(result.index(r"\["), result.index(r"\end{enumerate}"))
        self.assertIn(r"P@k = \frac{TP_k}{k}.", result)
        self.assertNotIn(r"\textbackslash", result)

    def test_table_layout_preserved(self):
        source = "# Example\n\nBefore.\n\n| A | B |\n|---|---|\n| x | y |\n\nAfter."
        generated = exporter.markdown_to_latex(source)
        custom = generated.replace(r"L{0.19\linewidth}L{0.75\linewidth}", r"L{0.24\linewidth}L{0.70\linewidth}")
        result = exporter.preserve_tables(exporter.markdown_to_latex(source.replace("Before.", "Updated.")), custom, source, source)
        self.assertIn(r"L{0.24\linewidth}L{0.70\linewidth}", result)
        self.assertIn("Updated.", result)

    def test_unreviewed_table_data_change_refused(self):
        source = "# Example\n\n| A | B |\n|---|---|\n| x | 700 |"
        with self.assertRaises(ValueError):
            exporter.preserve_tables(exporter.markdown_to_latex(source), exporter.markdown_to_latex(source), source, source.replace("700", "701"))

    def test_landscape_does_not_return_around_portrait_table(self):
        source = "# Example\n\n| A | B | C | D | E | F |\n|---|---|---|---|---|---|\n| 1 | 2 | 3 | 4 | 5 | 6 |\n\nAfter."
        generated = exporter.markdown_to_latex(source)
        custom = generated.replace("\\begin{landscape}\n", "").replace("\\end{landscape}\n", "")
        custom = custom.replace("\\endgroup", "\\endgroup\n\\FloatBarrier\n\\Needspace{6\\baselineskip}")
        result = exporter.preserve_tables(generated, custom, source, source)
        self.assertNotIn("landscape", result)
        self.assertIn(r"\FloatBarrier", result)
        self.assertIn(r"\Needspace{6\baselineskip}", result)

    def test_samepage_stays_on_its_original_paragraph(self):
        source = "# Example\n\n| A | B |\n|---|---|\n| x | y |\n\nKeep this paragraph together.\n\nFinal paragraph."
        generated = exporter.markdown_to_latex(source)
        custom = generated.replace("Keep this paragraph together.", "\\begin{samepage}\nKeep this paragraph together.\n\\end{samepage}")
        result = exporter.preserve_tables(generated, custom, source, source)
        self.assertIn("\\begin{samepage}\nKeep this paragraph together.\n\\end{samepage}", result)
        self.assertNotIn("\\begin{samepage}\nFinal paragraph.", result)

    def test_approved_table_label_changes(self):
        source = "# Example\n\n| Unit | B |\n|---|---|\n| x | y |"
        updated = source.replace("| Unit |", "| Snippet |")
        result = exporter.preserve_tables(exporter.markdown_to_latex(updated), exporter.markdown_to_latex(source), source, updated)
        self.assertIn(r"\textbf{Snippet}", result)

    def test_current_manuscript_has_no_raw_or_numeric_only_citations(self):
        bibliography = (exporter.MANUSCRIPT / "references.bib").read_text(encoding="utf-8")
        keys = set(re.findall(r"@\w+\{([^,]+),", bibliography))
        for source_name in exporter.CHAPTERS:
            source = (exporter.MANUSCRIPT / source_name).read_text(encoding="utf-8")
            result = exporter.markdown_to_latex(source)
            self.assertNotRegex(result, r"\\(?:cite|autocite|parencite)\{")
            self.assertNotRegex(result, r"(?<![A-Za-z0-9_])@[A-Z][A-Za-z0-9_:-]{2,}")
            for group in re.findall(r"\\textcite\{([^}]+)\}", result):
                self.assertTrue(set(group.split(",")) <= keys, group)


if __name__ == "__main__":
    unittest.main()
