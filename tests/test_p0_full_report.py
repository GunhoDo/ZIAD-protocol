import csv
import json
import tempfile
import unittest
from pathlib import Path

from experiments import p0_full_report


class P0FullReportTest(unittest.TestCase):
    def _write_step_fixture(self, root: Path, *, metric_value: str = "0.5") -> Path:
        output_root = root / "p0_full" / "mvtec_ad" / "winclip" / "default_no_memory" / "none"
        output_root.mkdir(parents=True)
        metrics = output_root / "metrics.csv"
        manifest = output_root / "manifest.json"
        crd = output_root / "crd_lite.csv"

        with metrics.open("w", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "dataset",
                    "category",
                    "baseline",
                    "memory_policy",
                    "calibration",
                    "image_auroc",
                    "aupr",
                    "ece",
                    "latency_ms",
                    "crd_lite",
                    "status",
                ],
                lineterminator="\n",
            )
            writer.writeheader()
            writer.writerow(
                {
                    "dataset": "MVTec AD",
                    "category": "bottle",
                    "baseline": "WinCLIP",
                    "memory_policy": "default/no-memory",
                    "calibration": "none",
                    "image_auroc": metric_value,
                    "aupr": "0.5",
                    "ece": "0.0",
                    "latency_ms": "1.0",
                    "crd_lite": "NA",
                    "status": "measured_full_p0",
                }
            )
        manifest.write_text(
            json.dumps(
                {
                    "status": "measured_full_p0_production_complete",
                    "run_tier": "p0_full",
                    "execution_mode": "production",
                    "dataset": "MVTec AD",
                    "baseline": "WinCLIP",
                    "memory_policy": "default/no-memory",
                    "calibration": "none",
                    "category_count": 1,
                    "run_count": 1,
                    "expected_full_run_count": 1,
                    "stream_length": 2,
                    "paper_allowed": False,
                    "claim_allowed": False,
                    "review_status": "not_reviewed",
                }
            )
        )
        crd.write_text("status\nmeasured_full_p0\n")

        plan = {
            "steps": [
                {
                    "step_id": "mvtec_ad:winclip:default_no_memory:none",
                    "dataset": "MVTec AD",
                    "baseline": "WinCLIP",
                    "memory_policy": "default/no-memory",
                    "calibration": "none",
                    "category_count": 1,
                    "expected_full_run_count": 1,
                    "outputs": {
                        "aggregate_metrics": str(metrics),
                        "aggregate_manifest": str(manifest),
                        "crd_lite_summary": str(crd),
                    },
                    "validation": {
                        "expected_row_count_field": "expected_full_run_count",
                    },
                }
            ]
        }
        plan_path = root / "execution_plan.json"
        plan_path.write_text(json.dumps(plan))
        return plan_path

    def test_build_report_summarizes_step_and_keeps_gates_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self._write_step_fixture(root)

            report = p0_full_report.build_report(plan)

            self.assertEqual("p0_full_validation_report_complete", report["status"])
            self.assertFalse(report["paper_allowed"])
            self.assertFalse(report["claim_allowed"])
            self.assertEqual(1, report["step_count"])
            self.assertEqual([], report["row_count_mismatches"])
            self.assertEqual([], report["category_count_mismatches"])
            self.assertEqual([], report["gate_violations"])
            step = report["steps"][0]
            self.assertEqual(1, step["row_count"])
            self.assertEqual(1, step["expected_row_count"])
            self.assertEqual(["measured_full_p0"], step["status_values"])
            self.assertEqual(2, step["stream_length"])

    def test_report_records_non_finite_metric_blocker(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = self._write_step_fixture(Path(tmp), metric_value="nan")

            report = p0_full_report.build_report(plan)

            self.assertEqual(
                ["mvtec_ad:winclip:default_no_memory:none"],
                report["non_finite_metric_steps"],
            )
            self.assertEqual(1, report["steps"][0]["non_finite_metric_count"])

    def test_writes_json_csv_and_tex(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self._write_step_fixture(root)
            report = p0_full_report.build_report(plan)
            report_path = root / "validation_report.json"
            csv_path = root / "summary.csv"
            tex_path = root / "summary.tex"

            p0_full_report.write_report(report_path, report)
            p0_full_report.write_summary_csv(csv_path, report)
            body = p0_full_report.render_summary_table(
                tex_path, report, summary_csv=csv_path
            )

            self.assertTrue(report_path.exists())
            self.assertTrue(csv_path.exists())
            self.assertTrue(tex_path.exists())
            with csv_path.open(newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(1, len(rows))
            self.assertEqual("false", rows[0]["paper_allowed"])
            self.assertIn("not paper results", body)


if __name__ == "__main__":
    unittest.main()
