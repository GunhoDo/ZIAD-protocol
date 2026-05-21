import csv
import json
import tempfile
import unittest
from pathlib import Path

from experiments import evaluate


def score_row(index, label, score, latency="10", status="measured"):
    return {
        "stream_index": str(index),
        "image_path": f"image_{index}.png",
        "label": str(label),
        "category": "bottle",
        "anomaly_score": str(score),
        "latency_ms": str(latency),
        "peak_vram_mb": "100",
        "status": status,
    }


class EvaluateSmokeMetricsTest(unittest.TestCase):
    def _write_scores(self, path: Path, rows):
        with path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=evaluate.SCORE_FIELDS)
            writer.writeheader()
            writer.writerows(rows)

    def test_compute_metric_row_from_measured_scores(self):
        metric = evaluate.compute_metric_row(
            [score_row(0, 0, 0.1, latency=10), score_row(1, 1, 0.9, latency=20)],
            {
                "dataset": "MVTec AD",
                "stream_type": "iid",
                "prevalence": 0.05,
                "contamination_epsilon": 0,
                "baseline": "PatchCore",
            },
        )
        self.assertEqual(metric["status"], "measured_smoke")
        self.assertEqual(metric["image_auroc"], "1.000000")
        self.assertEqual(metric["aupr"], "1.000000")
        self.assertEqual(metric["latency_ms"], "15.000000")
        self.assertEqual(metric["crd_lite"], "NA")

    def test_placeholder_scores_stay_placeholder(self):
        metric = evaluate.compute_metric_row(
            [
                score_row(
                    "TODO",
                    "TODO",
                    "TODO",
                    latency="TODO",
                    status="placeholder_not_measured",
                )
            ],
            {},
        )
        self.assertEqual(metric["status"], "placeholder_not_measured")
        self.assertEqual(metric["image_auroc"], "TODO")

    def test_unknown_status_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "Unknown score row status"):
            evaluate.compute_metric_row([score_row(0, 1, 0.9, status="failed")], {})

    def test_evaluate_writes_metrics_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scores = root / "scores.csv"
            latest = root / "latest_run.json"
            metrics = root / "metrics.csv"
            manifest = root / "manifest.json"
            self._write_scores(
                scores,
                [score_row(0, 0, 0.1, latency=10), score_row(1, 1, 0.9, latency=20)],
            )
            latest.write_text(
                json.dumps({"baseline": "PatchCore", "dataset": "MVTec AD"})
            )
            manifest.write_text(json.dumps({}))
            row = evaluate.evaluate(scores, latest, metrics, manifest)
            self.assertEqual(row["status"], "measured_smoke")
            with metrics.open(newline="") as handle:
                metric_rows = list(csv.DictReader(handle))
            self.assertEqual(metric_rows[0]["baseline"], "PatchCore")
            manifest_payload = json.loads(manifest.read_text())
            self.assertEqual(manifest_payload["status"], "evaluated_smoke")
            self.assertEqual(manifest_payload["scores_csv"], str(scores))
            self.assertEqual(manifest_payload["metrics_csv"], str(metrics))
            self.assertFalse(manifest_payload["paper_allowed"])

    def test_visa_evaluate_manifest_keeps_paper_allowed_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scores = root / "scores_visa.csv"
            latest = root / "latest_run_visa.json"
            metrics = root / "metrics_visa.csv"
            manifest = root / "manifest_visa.json"
            self._write_scores(
                scores,
                [score_row(0, 0, 0.1, latency=10), score_row(1, 1, 0.9, latency=20)],
            )
            latest.write_text(json.dumps({"baseline": "WinCLIP", "dataset": "VisA"}))
            manifest.write_text(json.dumps({"paper_allowed": True}))

            row = evaluate.evaluate(scores, latest, metrics, manifest)

            self.assertEqual(row["dataset"], "VisA")
            manifest_payload = json.loads(manifest.read_text())
            self.assertEqual(manifest_payload["status"], "evaluated_smoke")
            self.assertFalse(manifest_payload["paper_allowed"])


if __name__ == "__main__":
    unittest.main()
