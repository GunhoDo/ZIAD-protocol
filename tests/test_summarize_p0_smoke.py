import csv
import json
import tempfile
import unittest
from pathlib import Path

from experiments import summarize_p0_smoke


class SummarizeP0SmokeTest(unittest.TestCase):
    def test_summarizes_measured_smoke_by_dataset_baseline_and_calibration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            metrics = root / "metrics.csv"
            metrics.write_text(
                "dataset,category,stream_type,prevalence,contamination_epsilon,"
                "baseline,memory_policy,calibration,image_auroc,aupr,ece,"
                "latency_ms,crd_lite,status,run_dir\n"
                "MVTec AD,bottle,iid,0.05,0.0,WinCLIP,default/SCS,none,"
                "1.0,0.8,0.1,10.0,0.0,measured_smoke,run1\n"
                "MVTec AD,cable,bursty,0.05,0.05,WinCLIP,default/SCS,none,"
                "0.5,0.4,0.3,30.0,0.2,measured_smoke,run2\n"
                "MVTec AD,bottle,iid,0.05,0.0,WinCLIP,default/SCS,"
                "temperature_scaling,1.0,0.9,0.2,10.0,0.0,measured_smoke,run3\n"
            )

            rows = summarize_p0_smoke.summarize_metrics([metrics])

            self.assertEqual(2, len(rows))
            none_row = next(row for row in rows if row["calibration"] == "none")
            self.assertEqual("MVTec AD", none_row["dataset"])
            self.assertEqual("WinCLIP", none_row["baseline"])
            self.assertEqual("2", none_row["category_count"])
            self.assertEqual("2", none_row["run_count"])
            self.assertEqual("2", none_row["stream_type_count"])
            self.assertEqual("2", none_row["epsilon_count"])
            self.assertEqual("0.750000", none_row["mean_image_auroc"])
            self.assertEqual("0.600000", none_row["mean_aupr"])
            self.assertEqual("0.200000", none_row["mean_ece"])
            self.assertEqual("20.000000", none_row["mean_latency_ms"])
            self.assertEqual("0.100000", none_row["mean_crd_lite"])
            self.assertEqual("false", none_row["paper_allowed"])

    def test_writes_csv_manifest_and_paper_ineligible_tex(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rows = [
                {
                    "dataset": "VisA",
                    "baseline": "PatchCore",
                    "calibration": "temperature_scaling",
                    "category_count": "12",
                    "run_count": "72",
                    "stream_type_count": "2",
                    "epsilon_count": "3",
                    "mean_image_auroc": "0.700000",
                    "mean_aupr": "0.500000",
                    "mean_ece": "0.200000",
                    "mean_latency_ms": "1.000000",
                    "mean_crd_lite": "0.000000",
                    "status": "measured_smoke_summary",
                    "paper_allowed": "false",
                }
            ]
            csv_path = root / "summary.csv"
            manifest_path = root / "manifest.json"
            tex_path = root / "summary.tex"

            summarize_p0_smoke.write_summary_csv(csv_path, rows)
            manifest = summarize_p0_smoke.write_manifest(
                manifest_path,
                metrics_paths=[root / "metrics.csv"],
                summary_csv=csv_path,
                table_tex=tex_path,
                rows=rows,
            )
            body = summarize_p0_smoke.render_summary_table(
                rows,
                tex_path,
                summary_csv=csv_path,
                manifest_path=manifest_path,
            )

            with csv_path.open(newline="") as handle:
                written = list(csv.DictReader(handle))
            self.assertEqual(rows, written)
            self.assertFalse(manifest["paper_allowed"])
            self.assertFalse(json.loads(manifest_path.read_text())["paper_allowed"])
            self.assertIn("paper_allowed=false", body)
            self.assertIn("P0 smoke matrix summary", body)
            self.assertIn("temperature\\_scaling", body)

    def test_rejects_non_measured_smoke_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            metrics = Path(tmp) / "metrics.csv"
            metrics.write_text(
                "dataset,category,stream_type,contamination_epsilon,baseline,"
                "calibration,image_auroc,aupr,ece,latency_ms,crd_lite,status\n"
                "VisA,candle,iid,0.0,WinCLIP,none,1,1,0,1,0,placeholder\n"
            )

            with self.assertRaises(SystemExit):
                summarize_p0_smoke.summarize_metrics([metrics])


if __name__ == "__main__":
    unittest.main()
