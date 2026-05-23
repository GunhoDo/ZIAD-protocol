import csv
import json
import tempfile
import unittest
from pathlib import Path

import yaml

from experiments import materialize_calibration_matrix


SCORE_FIELDS = [
    "stream_index",
    "image_path",
    "label",
    "category",
    "anomaly_score",
    "latency_ms",
    "peak_vram_mb",
    "status",
]


class MaterializeCalibrationMatrixTest(unittest.TestCase):
    def test_materializes_calibration_axis_from_measured_source_scores(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_root = root / "source"
            target_root = root / "target"
            source_cfg = root / "source.yaml"
            target_cfg = root / "target.yaml"
            source_cfg.write_text(
                yaml.safe_dump(
                    {
                        "dataset": "VisA",
                        "dataset_root": "data/visa/1cls",
                        "categories": ["candle"],
                        "baselines": [
                            {
                                "name": "WinCLIP",
                                "baseline_path": "external/WinClip",
                                "provenance": {
                                    "scoring_mode": "stream_ordered_zero_shot",
                                    "latency_semantics": "wrapper_batch_amortized",
                                    "training_source": "zero_shot_text_prompts",
                                    "stream_source": "test/*",
                                },
                            }
                        ],
                        "stream_types": ["iid"],
                        "contamination_epsilon": [0],
                        "outputs": {"root": str(source_root)},
                    },
                    sort_keys=False,
                )
            )
            target_cfg.write_text(
                yaml.safe_dump(
                    {
                        "dataset": "VisA",
                        "dataset_root": "data/visa/1cls",
                        "categories": ["candle"],
                        "baselines": [
                            {
                                "name": "WinCLIP",
                                "baseline_path": "external/WinClip",
                                "provenance": {
                                    "scoring_mode": "stream_ordered_zero_shot_temperature_matrix",
                                    "latency_semantics": "wrapper_batch_amortized",
                                    "training_source": "zero_shot_text_prompts",
                                    "stream_source": "test/*",
                                },
                            }
                        ],
                        "stream_types": ["iid"],
                        "contamination_epsilon": [0],
                        "calibration": ["none", "temperature_scaling"],
                        "calibration_temperature": 2.0,
                        "outputs": {
                            "root": str(target_root),
                            "aggregate_metrics": str(target_root / "metrics.csv"),
                            "aggregate_manifest": str(target_root / "manifest.json"),
                            "crd_lite_summary": str(target_root / "crd_lite.csv"),
                        },
                    },
                    sort_keys=False,
                )
            )
            source_dir = (
                source_root
                / "details"
                / "winclip_candle"
                / "winclip_candle_iid_eps_0"
            )
            source_dir.mkdir(parents=True)
            self._write_scores(source_dir / "scores.csv")
            (source_dir / "stream.json").write_text(
                json.dumps({"metadata": {"warnings": []}, "items": []}) + "\n"
            )
            (source_dir / "latest_run.json").write_text(
                json.dumps(
                    {
                        "status": "success",
                        "baseline": "WinCLIP",
                        "dataset": "VisA",
                        "category": "candle",
                        "stream_type": "iid",
                        "prevalence": 0.05,
                        "contamination_epsilon": 0.0,
                        "paper_allowed": False,
                    }
                )
                + "\n"
            )

            summary = materialize_calibration_matrix.materialize_category_sweep(
                source_cfg, target_cfg
            )

            self.assertEqual(
                {"matrix_configs": 1, "materialized_runs": 2, "calibrated_runs": 1},
                summary,
            )
            with (target_root / "metrics.csv").open(newline="") as handle:
                metrics_rows = list(csv.DictReader(handle))
            self.assertEqual(2, len(metrics_rows))
            self.assertEqual(
                ["none", "temperature_scaling"],
                sorted(row["calibration"] for row in metrics_rows),
            )
            self.assertTrue(
                (
                    target_root
                    / "details"
                    / "winclip_candle"
                    / "winclip_candle_iid_eps_0_cal_temperature_scaling"
                    / "scores_calibration.json"
                ).exists()
            )
            manifest = json.loads((target_root / "manifest.json").read_text())
            self.assertFalse(manifest["paper_allowed"])
            self.assertEqual(2, manifest["run_count"])

    def _write_scores(self, path: Path) -> None:
        with path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=SCORE_FIELDS)
            writer.writeheader()
            writer.writerows(
                [
                    {
                        "stream_index": "0",
                        "image_path": "good/0.png",
                        "label": "0",
                        "category": "candle",
                        "anomaly_score": "0.1",
                        "latency_ms": "1.0",
                        "peak_vram_mb": "0",
                        "status": "measured",
                    },
                    {
                        "stream_index": "1",
                        "image_path": "bad/1.png",
                        "label": "1",
                        "category": "candle",
                        "anomaly_score": "0.9",
                        "latency_ms": "1.0",
                        "peak_vram_mb": "0",
                        "status": "measured",
                    },
                ]
            )


if __name__ == "__main__":
    unittest.main()
