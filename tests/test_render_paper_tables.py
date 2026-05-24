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
            self.assertIn("Stream & $\\epsilon$ & Calibration", body)
            self.assertIn("iid & 0.0 & none", body)

    def test_render_smoke_evidence_table_accepts_caption_and_label(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            metrics = root / "metrics.csv"
            manifest = root / "manifest.json"
            output = root / "table.tex"
            metrics.write_text(
                "category,baseline,image_auroc,aupr,ece,latency_ms,crd_lite\n"
                "candle,WinCLIP,1.000000,1.000000,0.100000,1.000000,0.000000\n"
            )
            manifest.write_text(json.dumps({"paper_allowed": False}))

            body = render_paper_tables.render_smoke_evidence_table(
                metrics,
                manifest,
                output,
                caption="VisA WinCLIP calibration smoke",
                label="tab:visa-winclip-calibration-smoke",
            )

            self.assertIn("VisA WinCLIP calibration smoke", body)
            self.assertIn(r"\label{tab:visa-winclip-calibration-smoke}", body)
            self.assertNotIn("Calibration", body)

    def test_missing_metrics_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit):
                render_paper_tables.render_smoke_evidence_table(
                    Path(tmp) / "missing.csv",
                    Path(tmp) / "manifest.json",
                    Path(tmp) / "table.tex",
                )

    def test_write_paper_input_contract_records_sources_and_claim_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tex = root / "table.tex"
            metrics = root / "metrics.csv"
            manifest = root / "manifest.json"
            output = root / "paper_input_contract.json"
            tex.write_text("\\begin{table}\\end{table}\n")
            metrics.write_text("dataset,baseline,status\nMVTec AD,WinCLIP,measured_smoke\n")
            manifest.write_text(
                json.dumps({"status": "measured_smoke_complete", "paper_allowed": False})
            )

            contract = render_paper_tables.write_paper_input_contract(
                output,
                table_inputs=[
                    {
                        "name": "unit_table",
                        "kind": "smoke_table",
                        "tex": str(tex),
                        "source_csv": str(metrics),
                        "manifest": str(manifest),
                        "included_in_paper_tex": True,
                        "paper_label": "tab:unit",
                        "interpretation": "unit smoke evidence",
                    }
                ],
            )

            written = json.loads(output.read_text())
            self.assertEqual(contract, written)
            self.assertEqual("paper_input_contract_ready_smoke_only", contract["status"])
            self.assertFalse(contract["paper_allowed"])
            self.assertFalse(contract["claim_allowed"])
            self.assertEqual(1, contract["table_count"])
            self.assertEqual(1, contract["included_table_count"])
            self.assertEqual(0, contract["missing_input_count"])
            self.assertEqual(1, contract["tables"][0]["row_count"])
            self.assertFalse(contract["tables"][0]["eligible_for_claims"])
            self.assertFalse(contract["tables"][0]["source_paper_allowed"])


if __name__ == "__main__":
    unittest.main()
