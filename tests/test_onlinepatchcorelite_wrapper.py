import csv
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from experiments.baselines import onlinepatchcorelite


class OnlinePatchCoreLiteTest(unittest.TestCase):
    def test_fifo_update_evicts_oldest_feature(self):
        memory: list[list[float]] = []

        onlinepatchcorelite.fifo_update(memory, [1.0], max_size=2)
        onlinepatchcorelite.fifo_update(memory, [2.0], max_size=2)
        onlinepatchcorelite.fifo_update(memory, [3.0], max_size=2)

        self.assertEqual([[2.0], [3.0]], memory)

    def test_score_uses_memory_before_update(self):
        memory = [[0.0], [4.0]]

        score = onlinepatchcorelite.score_against_memory([3.0], memory, metric="l2")
        onlinepatchcorelite.fifo_update(memory, [3.0], max_size=3)

        self.assertEqual(1.0, score)
        self.assertEqual([[0.0], [4.0], [3.0]], memory)

    def test_stream_order_changes_scores_and_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset_root = root / "data"
            category = dataset_root / "bottle" / "test" / "good"
            category.mkdir(parents=True)
            for index, value in enumerate([20, 80, 160, 220]):
                Image.new("L", (8, 8), color=value).save(category / f"{index}.png")

            def write_stream(path: Path, order: list[int]) -> None:
                items = []
                for stream_index, image_index in enumerate(order):
                    items.append(
                        {
                            "stream_index": stream_index,
                            "image_path": f"bottle/test/good/{image_index}.png",
                            "label": 0 if image_index < 2 else 1,
                            "category": "bottle",
                            "source_split": "test",
                            "anomaly_type": "good" if image_index < 2 else "synthetic",
                        }
                    )
                path.write_text(json.dumps({"items": items, "metadata": {}}))

            stream_a = root / "stream_a.json"
            stream_b = root / "stream_b.json"
            write_stream(stream_a, [0, 1, 2, 3])
            write_stream(stream_b, [0, 2, 1, 3])
            config = {
                "memory_policy": "FIFO",
                "calibration": "none",
                "memory_size": 2,
                "descriptor_size": 4,
                "distance_metric": "l2",
            }

            def run_scores(stream: Path, output: Path) -> list[float]:
                onlinepatchcorelite.run(str(stream), str(dataset_root), str(output), config)
                with output.open(newline="") as handle:
                    rows = list(csv.DictReader(handle))
                self.assertEqual(["measured"], sorted({row["status"] for row in rows}))
                return [float(row["anomaly_score"]) for row in rows]

            scores_a = run_scores(stream_a, root / "scores_a.csv")
            scores_b = run_scores(stream_b, root / "scores_b.csv")
            scores_a_again = run_scores(stream_a, root / "scores_a_again.csv")

            self.assertNotEqual(scores_a, scores_b)
            self.assertEqual(scores_a, scores_a_again)


if __name__ == "__main__":
    unittest.main()
