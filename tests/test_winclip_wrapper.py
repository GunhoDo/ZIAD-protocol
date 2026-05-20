import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image
import torch

from experiments.baselines import winclip


def image(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (8, 8), color=(128, 64, 32)).save(path)


def stream_item(index, image_path, label=0, anomaly_type="good"):
    return {
        "stream_index": index,
        "image_path": image_path,
        "label": label,
        "category": "bottle",
        "source_split": "test",
        "anomaly_type": anomaly_type,
    }


class FakeWinClipModel:
    def transform(self, image_obj):
        self.last_image_size = image_obj.size
        return torch.zeros((3, 8, 8), dtype=torch.float32)

    def __call__(self, batch):
        return [np.full((2, 2), float(i + 1), dtype=np.float32) for i in range(batch.shape[0])]


class WinCLIPWrapperHelpersTest(unittest.TestCase):
    def test_load_stream_items_requires_contiguous_indices(self):
        with tempfile.TemporaryDirectory() as tmp:
            stream = Path(tmp) / "stream.json"
            stream.write_text(
                json.dumps(
                    {
                        "items": [
                            stream_item(0, "bottle/test/good/000.png"),
                            stream_item(2, "bottle/test/good/001.png"),
                        ]
                    }
                )
            )
            with self.assertRaisesRegex(RuntimeError, "contiguous"):
                winclip._load_stream_items(str(stream))

    def test_resolve_stream_image_path_rejects_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "mvtec_ad"
            outside = Path(tmp) / "outside.png"
            root.mkdir()
            image(outside)
            with self.assertRaisesRegex(RuntimeError, "outside dataset_root"):
                winclip._resolve_stream_image_path(str(outside), root)

    def test_predict_rows_uses_stream_order_and_max_map_score(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "mvtec_ad"
            image(root / "bottle" / "test" / "good" / "000.png")
            image(root / "bottle" / "test" / "scratch" / "001.png")
            items = [
                stream_item(0, "bottle/test/good/000.png"),
                stream_item(1, "bottle/test/scratch/001.png", 1, "scratch"),
            ]
            rows = winclip.WinCLIPWrapper._predict_rows(
                model=FakeWinClipModel(),
                stream_items=items,
                dataset_root=root,
                category="bottle",
                batch_size=2,
                device=torch.device("cpu"),
                torch=torch,
            )
        self.assertEqual([row["stream_index"] for row in rows], [0, 1])
        self.assertEqual([row["image_path"] for row in rows], [item["image_path"] for item in items])
        self.assertEqual([row["label"] for row in rows], [0, 1])
        self.assertEqual([row["status"] for row in rows], ["measured", "measured"])
        self.assertEqual(rows[0]["anomaly_score"], "1.0000000000")
        self.assertEqual(rows[1]["anomaly_score"], "2.0000000000")


if __name__ == "__main__":
    unittest.main()
