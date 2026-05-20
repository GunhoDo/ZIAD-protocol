import csv
import json
import tempfile
import unittest
from pathlib import Path

import yaml

from experiments import category_sweep


class CategorySweepTest(unittest.TestCase):
    def test_generate_matrix_configs_expands_baselines_and_categories(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "category_sweep.yaml"
            config.write_text(
                yaml.safe_dump(
                    {
                        "dataset": "MVTec AD",
                        "dataset_root": "data/mvtec_ad",
                        "categories": ["bottle", "capsule"],
                        "baselines": [
                            {
                                "name": "PatchCore",
                                "baseline_path": "external/patchcore-inspection",
                            },
                            {
                                "name": "WinCLIP",
                                "baseline_path": "external/WinClip",
                                "provenance": {"scoring_mode": "stream_ordered_zero_shot"},
                            },
                        ],
                        "stream_types": ["iid"],
                        "contamination_epsilon": [0],
                        "stream": {"seed": 3, "length": 20, "burst_length": 5},
                        "outputs": {"root": str(root / "category_quick_sweep")},
                    },
                    sort_keys=False,
                )
            )

            paths = category_sweep.generate_matrix_configs(config)

            self.assertEqual(len(paths), 4)
            names = sorted(path.name for path in paths)
            self.assertIn("patchcore_bottle_matrix.yaml", names)
            self.assertIn("winclip_capsule_matrix.yaml", names)
            winclip = yaml.safe_load((root / "category_quick_sweep" / "configs" / "winclip_capsule_matrix.yaml").read_text())
            self.assertEqual(winclip["category"], "capsule")
            self.assertEqual(winclip["stream"]["length"], 20)
            self.assertEqual(winclip["provenance"]["scoring_mode"], "stream_ordered_zero_shot")

    def test_aggregate_sweep_combines_metrics_and_crd_with_category(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sweep_root = root / "category_quick_sweep"
            config = root / "category_sweep.yaml"
            config.write_text(
                yaml.safe_dump(
                    {
                        "dataset": "MVTec AD",
                        "categories": ["bottle", "capsule"],
                        "baselines": [{"name": "WinCLIP", "baseline_path": "external/WinClip"}],
                        "stream_types": ["iid"],
                        "contamination_epsilon": [0],
                        "outputs": {
                            "root": str(sweep_root),
                            "aggregate_metrics": str(root / "metrics.csv"),
                            "aggregate_manifest": str(root / "manifest.json"),
                            "crd_lite_summary": str(root / "crd.csv"),
                        },
                    },
                    sort_keys=False,
                )
            )
            for category in ["bottle", "capsule"]:
                detail = sweep_root / "details" / f"winclip_{category}"
                detail.mkdir(parents=True)
                metrics_path = detail / f"metrics_winclip_{category}.csv"
                with metrics_path.open("w", newline="") as handle:
                    writer = csv.DictWriter(
                        handle,
                        fieldnames=["dataset", "stream_type", "baseline", "status", "run_dir"],
                    )
                    writer.writeheader()
                    writer.writerow(
                        {
                            "dataset": "MVTec AD",
                            "stream_type": "iid",
                            "baseline": "WinCLIP",
                            "status": "measured_smoke",
                            "run_dir": str(detail / "run"),
                        }
                    )
                crd_path = detail / f"crd_lite_winclip_{category}.csv"
                with crd_path.open("w", newline="") as handle:
                    writer = csv.DictWriter(
                        handle,
                        fieldnames=["dataset", "category", "baseline", "crd_lite", "status"],
                    )
                    writer.writeheader()
                    writer.writerow(
                        {
                            "dataset": "MVTec AD",
                            "category": category,
                            "baseline": "WinCLIP",
                            "crd_lite": "0.000000",
                            "status": "derived_smoke",
                        }
                    )
                (detail / f"manifest_winclip_{category}.json").write_text(
                    json.dumps({"status": "winclip_mini_matrix_complete", "paper_allowed": False})
                )

            metrics, manifest, crd, rows = category_sweep.aggregate_sweep(config)

            self.assertEqual(metrics, root / "metrics.csv")
            self.assertEqual(manifest, root / "manifest.json")
            self.assertEqual(crd, root / "crd.csv")
            self.assertEqual(len(rows), 2)
            self.assertEqual({row["category"] for row in rows}, {"bottle", "capsule"})
            manifest_payload = json.loads(manifest.read_text())
            self.assertEqual(manifest_payload["status"], "category_quick_sweep_complete")
            self.assertFalse(manifest_payload["paper_allowed"])
            self.assertEqual(manifest_payload["run_count"], 2)


if __name__ == "__main__":
    unittest.main()
