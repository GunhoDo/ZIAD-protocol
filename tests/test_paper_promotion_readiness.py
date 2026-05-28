import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts.check_paper_promotion_readiness import build_promotion_readiness_report


def _write(path: Path, text: str = "x\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_combined_csv(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "dataset",
        "baseline",
        "memory_policy",
        "calibration",
        "completed_categories",
        "expected_categories",
        "total_rows",
        "stream_length",
        "seeds",
        "mean_image_auroc",
        "mean_aupr",
        "mean_ece",
        "mean_latency_ms",
        "mean_crd_lite",
        "paper_allowed",
        "claim_allowed",
        "review_status",
    ]
    rows = []
    for dataset, categories, total_rows in (("MVTec AD", 15, 180), ("VisA", 12, 144)):
        for baseline, memory_policy in (
            ("WinCLIP", "default/no-memory"),
            ("AnomalyCLIP", "default/no-memory"),
            ("RareCLIP", "default/SCS"),
            ("PatchCore", "default/SCS"),
        ):
            rows.append(
                {
                    "dataset": dataset,
                    "baseline": baseline,
                    "memory_policy": memory_policy,
                    "calibration": "none",
                    "completed_categories": str(categories),
                    "expected_categories": str(categories),
                    "total_rows": str(total_rows),
                    "stream_length": "64",
                    "seeds": "0|1|2",
                    "mean_image_auroc": "0.9",
                    "mean_aupr": "0.8",
                    "mean_ece": "0.2",
                    "mean_latency_ms": "10.0",
                    "mean_crd_lite": "0.0",
                    "paper_allowed": "False",
                    "claim_allowed": "False",
                    "review_status": "review_pending",
                }
            )
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_minimal_repo(root: Path, *, runtime_todos: bool = True, include_llncs: bool = False) -> None:
    _write_combined_csv(root / "results/latest/paper_candidate/baseline_comparison_all_datasets_none.csv")
    _write(root / "results/latest/paper_candidate/baseline_comparison_all_datasets_none.json", "{}\n")
    _write(root / "results/latest/tables/paper_candidate_baseline_comparison_all_datasets_none.tex")
    _write(root / "results/latest/paper_candidate/baseline_ranking_summary.json", "{}\n")
    _write(root / "results/latest/tables/paper_candidate_ranking_summary.tex")
    _write(root / "results/latest/figures/paper_candidate_accuracy_latency_tradeoff.png")
    _write(root / "results/latest/figures/paper_candidate_accuracy_latency_tradeoff.pdf")
    _write(
        root / "results/latest/paper_candidate/metric_audit_report.json",
        json.dumps(
            {
                "status": "paper_candidate_metric_audit_passed",
                "error_count": 0,
                "category_summary_count": 8,
                "combined_csv": {
                    "missing_value_count": 0,
                    "non_finite_value_count": 0,
                    "negative_latency_count": 0,
                },
            }
        ),
    )
    runtime_suffix = "TODO confirm device\n" if runtime_todos else "confirmed\n"
    _write(
        root / "docs/runtime_environment.md",
        "Latency device\nModel loading\nTiming granularity\nBatch/concurrency\n" + runtime_suffix,
    )
    _write(root / "docs/accv_template_migration.md")
    _write(root / "docs/paper_promotion_checklist.md")
    _write(
        root / "experiments/configs/baselines.yaml",
        """
baselines:
  AnomalyCLIP:
    repo_url: https://example.com/a.git
    commit_hash: 1111111
  PatchCore:
    repo_url: https://example.com/p.git
    commit_hash: 2222222
  RareCLIP:
    repo_url: https://example.com/r.git
    commit_hash: 3333333
  WinCLIP:
    repo_url: https://example.com/w.git
    commit_hash: 4444444
# Do not fabricate replacement URLs or commit hashes.
""",
    )
    document_class = "\\documentclass[runningheads]{llncs}" if include_llncs else "\\documentclass[10pt]{article}"
    _write(
        root / "paper/paper.tex",
        document_class
        + "\n\\begin{document}\n"
        + "candidate evidence stream length 64 local-runtime dependent\n"
        + "TODO before submission: final review.\n"
        + "\\end{document}\n",
    )
    _write(root / "paper/refs.bib")
    if include_llncs:
        _write(root / "paper/llncs.cls")


class PaperPromotionReadinessTests(unittest.TestCase):
    def test_current_expected_blockers_keep_promotion_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_minimal_repo(root, runtime_todos=True, include_llncs=False)

            report = build_promotion_readiness_report(root)

            self.assertFalse(report["ready_for_promotion"])
            self.assertIn("paper_allowed", report)
            self.assertFalse(report["paper_allowed"])
            self.assertTrue(
                any("runtime/timing semantics" in item for item in report["blocking_items"])
            )
            self.assertTrue(
                any("official ACCV/LNCS template" in item for item in report["blocking_items"])
            )
            self.assertTrue(
                any("manual reviewer approval" in item for item in report["blocking_items"])
            )

    def test_open_metric_gate_blocks_readiness(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_minimal_repo(root, runtime_todos=False, include_llncs=True)
            rows = (root / "results/latest/paper_candidate/baseline_comparison_all_datasets_none.csv").read_text()
            rows = rows.replace("False,False,review_pending", "True,False,review_pending", 1)
            (root / "results/latest/paper_candidate/baseline_comparison_all_datasets_none.csv").write_text(
                rows, encoding="utf-8"
            )

            report = build_promotion_readiness_report(root)

            self.assertFalse(report["ready_for_promotion"])
            self.assertTrue(any("paper_allowed must remain false" in item for item in report["blocking_items"]))


if __name__ == "__main__":
    unittest.main()
