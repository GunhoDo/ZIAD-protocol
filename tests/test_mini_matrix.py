import csv
import json
import tempfile
import unittest
from pathlib import Path

import yaml

from experiments import mini_matrix


class MiniMatrixTest(unittest.TestCase):
    def test_generate_run_configs_is_baseline_parametric_and_preserves_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            matrix = root / "winclip_matrix.yaml"
            matrix.write_text(
                yaml.safe_dump(
                    {
                        "baseline": "WinCLIP",
                        "baseline_path": "external/WinClip",
                        "dataset": "MVTec AD",
                        "dataset_root": "data/mvtec_ad",
                        "category": "bottle",
                        "prevalence": 0.05,
                        "stream_types": ["iid", "bursty"],
                        "contamination_epsilon": [0, 0.05],
                        "stream": {"seed": 7, "length": None, "burst_length": 5},
                        "outputs": {"root": str(root / "mini_matrix")},
                        "provenance": {
                            "scoring_mode": "stream_ordered_zero_shot",
                            "latency_semantics": "wrapper_batch_amortized",
                            "training_source": "zero_shot_text_prompts",
                            "stream_source": "test/*",
                        },
                    },
                    sort_keys=False,
                )
            )

            paths = mini_matrix.generate_run_configs(matrix)

            self.assertEqual(len(paths), 4)
            self.assertTrue(
                all(path.name.startswith("winclip_bottle_") for path in paths)
            )
            generated = yaml.safe_load(paths[0].read_text())
            self.assertEqual(generated["baseline"], "WinCLIP")
            self.assertEqual(generated["stream"]["seed"], 7)
            self.assertEqual(
                generated["provenance"]["scoring_mode"], "stream_ordered_zero_shot"
            )
            self.assertTrue(
                generated["outputs"]["scores_csv"].endswith("/scores.csv")
            )

    def test_generate_run_configs_preserves_visa_dataset_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            matrix = root / "visa_winclip_matrix.yaml"
            matrix.write_text(
                yaml.safe_dump(
                    {
                        "baseline": "WinCLIP",
                        "baseline_path": "external/WinClip",
                        "dataset": "VisA",
                        "dataset_root": "data/visa/1cls",
                        "category": "candle",
                        "stream_types": ["iid"],
                        "contamination_epsilon": [0],
                        "stream": {"seed": 0, "length": 20, "burst_length": 5},
                        "outputs": {"root": str(root / "visa_mini_matrix")},
                    },
                    sort_keys=False,
                )
            )

            paths = mini_matrix.generate_run_configs(matrix)

            self.assertEqual(len(paths), 1)
            generated = yaml.safe_load(paths[0].read_text())
            self.assertEqual(generated["dataset"], "VisA")
            self.assertEqual(generated["dataset_root"], "data/visa/1cls")
            self.assertEqual(generated["category"], "candle")
            self.assertEqual(generated["stream"]["length"], 20)

    def test_aggregate_metrics_filters_to_requested_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            matrix_root = root / "mini_matrix"
            matrix = root / "matrix.yaml"
            matrix.write_text(
                yaml.safe_dump(
                    {
                        "baseline": "WinCLIP",
                        "dataset": "MVTec AD",
                        "category": "bottle",
                        "stream_types": ["iid"],
                        "contamination_epsilon": [0],
                        "outputs": {
                            "root": str(matrix_root),
                            "aggregate_metrics": str(root / "metrics_winclip.csv"),
                            "aggregate_manifest": str(root / "manifest_winclip.json"),
                        },
                    },
                    sort_keys=False,
                )
            )
            winclip_run = matrix_root / "winclip_bottle_iid_eps_0"
            patchcore_run = matrix_root / "patchcore_bottle_iid_eps_0"
            winclip_run.mkdir(parents=True)
            patchcore_run.mkdir(parents=True)
            fields = ["baseline", "status"]
            for run_dir, baseline in [(winclip_run, "WinCLIP"), (patchcore_run, "PatchCore")]:
                with (run_dir / "metrics.csv").open("w", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=fields)
                    writer.writeheader()
                    writer.writerow({"baseline": baseline, "status": "measured_smoke"})

            metrics_path, manifest_path, rows = mini_matrix.aggregate_metrics(matrix)

            self.assertEqual(metrics_path, root / "metrics_winclip.csv")
            self.assertEqual(manifest_path, root / "manifest_winclip.json")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["baseline"], "WinCLIP")
            manifest = json.loads(manifest_path.read_text())
            self.assertEqual(manifest["status"], "winclip_mini_matrix_complete")
            self.assertFalse(manifest["paper_allowed"])
            self.assertEqual(
                manifest["crd_lite_summary"],
                str(matrix_root / "crd_lite_winclip_bottle.csv"),
            )

    def test_compute_crd_lite_uses_epsilon_zero_drop_by_stream(self):
        rows = [
            {
                "dataset": "MVTec AD",
                "stream_type": "iid",
                "prevalence": "0.05",
                "contamination_epsilon": "0.0",
                "baseline": "WinCLIP",
                "memory_policy": "default/SCS",
                "calibration": "none",
                "image_auroc": "0.900000",
                "aupr": "0.800000",
                "crd_lite": "NA",
                "status": "measured_smoke",
                "run_dir": "iid_0",
            },
            {
                "dataset": "MVTec AD",
                "stream_type": "iid",
                "prevalence": "0.05",
                "contamination_epsilon": "0.05",
                "baseline": "WinCLIP",
                "memory_policy": "default/SCS",
                "calibration": "none",
                "image_auroc": "0.850000",
                "aupr": "0.740000",
                "crd_lite": "NA",
                "status": "measured_smoke",
                "run_dir": "iid_005",
            },
            {
                "dataset": "MVTec AD",
                "stream_type": "bursty",
                "prevalence": "0.05",
                "contamination_epsilon": "0.05",
                "baseline": "WinCLIP",
                "memory_policy": "default/SCS",
                "calibration": "none",
                "image_auroc": "0.700000",
                "aupr": "0.600000",
                "crd_lite": "NA",
                "status": "measured_smoke",
                "run_dir": "bursty_missing_base",
            },
        ]

        summary, by_run_dir = mini_matrix.compute_crd_lite(rows, category="bottle")

        self.assertEqual(by_run_dir["iid_0"], "0.000000")
        self.assertEqual(by_run_dir["iid_005"], "0.055000")
        self.assertEqual(by_run_dir["bursty_missing_base"], "NA")
        self.assertEqual(summary[1]["image_auroc_drop"], "0.050000")
        self.assertEqual(summary[1]["aupr_drop"], "0.060000")
        self.assertEqual(summary[1]["status"], "derived_smoke")
        self.assertEqual(summary[2]["status"], "not_available")


if __name__ == "__main__":
    unittest.main()
