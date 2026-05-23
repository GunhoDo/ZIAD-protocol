import csv
import tempfile
import unittest
from pathlib import Path

from experiments.calibration import (
    SCORE_FIELDS,
    apply_calibration_from_config,
    apply_temperature_scaling_to_scores_csv,
)


class CalibrationTest(unittest.TestCase):
    def _write_scores(self, path: Path, scores: list[float]) -> None:
        with path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=SCORE_FIELDS)
            writer.writeheader()
            for index, score in enumerate(scores):
                writer.writerow(
                    {
                        "stream_index": index,
                        "image_path": f"image_{index}.png",
                        "label": int(index == len(scores) - 1),
                        "category": "candle",
                        "anomaly_score": score,
                        "latency_ms": "1.0",
                        "peak_vram_mb": "0.0",
                        "status": "measured",
                    }
                )

    def _read_scores(self, path: Path) -> list[float]:
        with path.open(newline="") as handle:
            return [
                float(row["anomaly_score"])
                for row in csv.DictReader(handle)
                if row["status"] == "measured"
            ]

    def test_temperature_scaling_is_monotonic_and_records_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            scores_csv = Path(tmpdir) / "scores.csv"
            self._write_scores(scores_csv, [1.0, 2.0, 5.0])

            metadata = apply_temperature_scaling_to_scores_csv(
                scores_csv, temperature=2.0
            )

            calibrated = self._read_scores(scores_csv)
            self.assertEqual("temperature_scaling", metadata["method"])
            self.assertEqual(3, metadata["rows_calibrated"])
            self.assertEqual([], metadata["warnings"])
            self.assertLess(calibrated[0], calibrated[1])
            self.assertLess(calibrated[1], calibrated[2])
            self.assertGreaterEqual(calibrated[0], 0.0)
            self.assertLessEqual(calibrated[-1], 1.0)

    def test_constant_scores_get_neutral_probability_warning(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            scores_csv = Path(tmpdir) / "scores.csv"
            self._write_scores(scores_csv, [4.0, 4.0])

            metadata = apply_temperature_scaling_to_scores_csv(
                scores_csv, temperature=1.0
            )

            self.assertEqual([0.5, 0.5], self._read_scores(scores_csv))
            self.assertEqual(
                ["constant_scores_temperature_scaled_to_0p5"],
                metadata["warnings"],
            )

    def test_rejects_invalid_temperature(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            scores_csv = Path(tmpdir) / "scores.csv"
            self._write_scores(scores_csv, [1.0])

            with self.assertRaisesRegex(ValueError, "temperature"):
                apply_temperature_scaling_to_scores_csv(scores_csv, temperature=0.0)

    def test_none_calibration_is_metadata_only(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            scores_csv = Path(tmpdir) / "scores.csv"
            metadata_path = Path(tmpdir) / "calibration.json"
            self._write_scores(scores_csv, [1.0, 3.0])

            metadata = apply_calibration_from_config(
                scores_csv,
                {"calibration": "none"},
                metadata_output=metadata_path,
            )

            self.assertEqual("none", metadata["method"])
            self.assertEqual([1.0, 3.0], self._read_scores(scores_csv))
            self.assertTrue(metadata_path.exists())


if __name__ == "__main__":
    unittest.main()
