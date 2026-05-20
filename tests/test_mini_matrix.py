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


if __name__ == "__main__":
    unittest.main()
