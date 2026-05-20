import json
import tempfile
import unittest
from pathlib import Path

from experiments import render_paper_tables


class RenderPaperTablesTest(unittest.TestCase):
    def test_render_smoke_evidence_table_marks_paper_ineligible_and_escapes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            metrics = root / "metrics.csv"
            manifest = root / "manifest.json"
            output = root / "table.tex"
            metrics.write_text(
                "dataset,category,stream_type,prevalence,contamination_epsilon,"
                "baseline,memory_policy,calibration,image_auroc,aupr,ece,"
                "latency_ms,crd_lite,status,run_dir\n"
                "MVTec AD,metal_nut,iid,0.05,0.0,WinCLIP & Patch,"
                "default/SCS,none,0.900000,0.800000,0.100000,12.300000,"
                "0.000000,measured_smoke,run\n"
            )
            manifest.write_text(
                json.dumps(
                    {
                        "status": "category_quick_sweep_complete",
                        "paper_allowed": False,
                    }
                )
            )

            body = render_paper_tables.render_smoke_evidence_table(
                metrics, manifest, output
            )

            self.assertTrue(output.exists())
            self.assertIn("paper_allowed=false", body)
            self.assertIn("non-final, paper-ineligible smoke evidence", body)
            self.assertIn("metal\\_nut", body)
            self.assertIn("WinCLIP \\& Patch", body)

    def test_missing_metrics_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit):
                render_paper_tables.render_smoke_evidence_table(
                    Path(tmp) / "missing.csv",
                    Path(tmp) / "manifest.json",
                    Path(tmp) / "table.tex",
                )


if __name__ == "__main__":
    unittest.main()
