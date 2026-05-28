import tempfile
import unittest
from pathlib import Path

from scripts.check_paper_template_readiness import check_readiness


REQUIRED_RESULT_FILES = (
    "results/latest/tables/paper_candidate_baseline_comparison_all_datasets_none.tex",
    "results/latest/tables/paper_candidate_ranking_summary.tex",
    "results/latest/figures/paper_candidate_accuracy_latency_tradeoff.png",
    "results/latest/paper_candidate/metric_audit_report.json",
    "results/latest/tables/paper_candidate_metric_audit_summary.tex",
)


def _write_minimal_tree(root: Path, paper_source: str) -> None:
    (root / "paper").mkdir(parents=True)
    (root / "paper/paper.tex").write_text(paper_source, encoding="utf-8")
    (root / "paper/refs.bib").write_text("% refs\n", encoding="utf-8")
    for rel_path in REQUIRED_RESULT_FILES:
        path = root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("placeholder\n", encoding="utf-8")


class PaperTemplateReadinessTests(unittest.TestCase):
    def test_article_fallback_with_approved_todo_passes_without_llncs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_minimal_tree(
                root,
                "\\documentclass[10pt]{article}\n"
                "\\begin{document}\n"
                "TODO before submission: final venue check.\n"
                "\\end{document}\n",
            )

            report = check_readiness(root)

            self.assertTrue(report.ok, report.errors)
            self.assertEqual(report.llncs_files, ())

    def test_unexpected_todo_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_minimal_tree(
                root,
                "\\documentclass[10pt]{article}\n"
                "\\begin{document}\n"
                "TODO fix this later.\n"
                "\\end{document}\n",
            )

            report = check_readiness(root)

            self.assertFalse(report.ok)
            self.assertTrue(any("unexpected TODO" in error for error in report.errors))

    def test_present_llncs_requires_llncs_document_class(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_minimal_tree(
                root,
                "\\documentclass[10pt]{article}\n\\begin{document}\\end{document}\n",
            )
            (root / "paper/llncs.cls").write_text("% official class placeholder for test\n")

            report = check_readiness(root)

            self.assertFalse(report.ok)
            self.assertTrue(any("llncs document class" in error for error in report.errors))


if __name__ == "__main__":
    unittest.main()
