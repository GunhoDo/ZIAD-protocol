import csv
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from experiments.baselines import onlineprototypeema


class OnlinePrototypeEMATest(unittest.TestCase):
    def test_stream_order_changes_scores_after_online_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset_root = root / "data"
            category = dataset_root / "bottle" / "test" / "good"
            category.mkdir(parents=True)
            for index, value in enumerate([20, 80, 160]):
                Image.new("L", (8, 8), color=value).save(category / f"{index}.png")

            def write_stream(path: Path, order: list[int]) -> None:
                items = []
                for stream_index, image_index in enumerate(order):
                    items.append(
                        {
                            "stream_index": stream_index,
                            "image_path": f"bottle/test/good/{image_index}.png",
                            "label": 0 if image_index != 2 else 1,
                            "category": "bottle",
                            "source_split": "test",
                            "anomaly_type": "good" if image_index != 2 else "synthetic",
                        }
                    )
                path.write_text(json.dumps({"items": items, "metadata": {}}))

            stream_a = root / "stream_a.json"
            stream_b = root / "stream_b.json"
            write_stream(stream_a, [0, 1, 2])
            write_stream(stream_b, [0, 2, 1])
            out_a = root / "scores_a.csv"
            out_b = root / "scores_b.csv"
            config = {
                "memory_policy": "Prototype-EMA",
                "calibration": "none",
                "prototype_ema_alpha": 0.5,
                "descriptor_size": 4,
            }

            onlineprototypeema.run(str(stream_a), str(dataset_root), str(out_a), config)
            onlineprototypeema.run(str(stream_b), str(dataset_root), str(out_b), config)

            with out_a.open(newline="") as handle:
                rows_a = list(csv.DictReader(handle))
            with out_b.open(newline="") as handle:
                rows_b = list(csv.DictReader(handle))
            self.assertEqual(["measured"], sorted({row["status"] for row in rows_a}))
            self.assertEqual(["measured"], sorted({row["status"] for row in rows_b}))
            scores_a = [float(row["anomaly_score"]) for row in rows_a]
            scores_b = [float(row["anomaly_score"]) for row in rows_b]
            self.assertNotEqual(scores_a, scores_b)


if __name__ == "__main__":
    unittest.main()
