import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image
import torch

from experiments.baselines import rareclip


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


class FakeRareCLIPModel:
    def __init__(self):
        self.device = torch.device("cpu")
        self.calls = 0
        self.updates = []
        self.score_memory = torch.empty((0, 1), dtype=torch.float32)
        self.IF_memory = torch.empty((0, 2), dtype=torch.float32)
        self.AAIF_memory = {6: torch.empty((0, 3), dtype=torch.float32)}
        self.PFM = [{6: torch.empty((0, 2), dtype=torch.float32)}]
        self.PSM = [{6: torch.empty((0, 0), dtype=torch.float32)}]
        self.k_shot = 0

    def preprocess(self, image_obj):
        self.last_image_size = image_obj.size
        return torch.zeros((3, 8, 8), dtype=torch.float32)

    def process_image_and_update(self, tensor, update=True):
        self.calls += 1
        self.updates.append(update)
        if update:
            row = torch.tensor([[float(self.calls)]], dtype=torch.float32)
            self.score_memory = torch.cat((self.score_memory, row), dim=0)
            self.IF_memory = torch.cat((self.IF_memory, row.repeat(1, 2)), dim=0)
            self.AAIF_memory[6] = torch.cat((self.AAIF_memory[6], row.repeat(1, 3)), dim=0)
            self.PFM[0][6] = torch.cat((self.PFM[0][6], row.repeat(1, 2)), dim=0)
            old = self.PSM[0][6]
            next_size = int(old.shape[0]) + 1
            self.PSM[0][6] = torch.arange(
                next_size * next_size,
                dtype=torch.float32,
            ).reshape(next_size, next_size)
        score = torch.tensor([float(self.calls)], dtype=torch.float32)
        return torch.zeros((1, 1, 8, 8), dtype=torch.float32), score


class RareCLIPWrapperHelpersTest(unittest.TestCase):
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
                rareclip._load_stream_items(str(stream))

    def test_resolve_stream_image_path_rejects_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "mvtec_ad"
            outside = Path(tmp) / "outside.png"
            root.mkdir()
            image(outside)
            with self.assertRaisesRegex(RuntimeError, "outside dataset_root"):
                rareclip._resolve_stream_image_path(str(outside), root)

    def test_predict_rows_uses_stream_order_and_online_score(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "mvtec_ad"
            image(root / "bottle" / "test" / "good" / "000.png")
            image(root / "bottle" / "test" / "scratch" / "001.png")
            items = [
                stream_item(0, "bottle/test/good/000.png"),
                stream_item(1, "bottle/test/scratch/001.png", 1, "scratch"),
            ]
            model = FakeRareCLIPModel()
            rows = rareclip.RareCLIPWrapper._predict_rows(
                model=model,
                stream_items=items,
                dataset_root=root,
                category="bottle",
                update_memory=True,
                device=torch.device("cpu"),
                torch=torch,
            )
        self.assertEqual([row["stream_index"] for row in rows], [0, 1])
        self.assertEqual([row["image_path"] for row in rows], [item["image_path"] for item in items])
        self.assertEqual([row["label"] for row in rows], [0, 1])
        self.assertEqual([row["status"] for row in rows], ["measured", "measured"])
        self.assertEqual([row["anomaly_score"] for row in rows], ["1.0000000000", "2.0000000000"])
        self.assertEqual(model.updates, [True, True])

    def test_fifo_sampler_keeps_newest_patch_features(self):
        model = type("Model", (), {"sample_num": 2})()
        rareclip._install_fifo_sampler(model)

        features = torch.tensor([[1.0], [2.0], [3.0], [4.0]])
        similarity = torch.arange(16, dtype=torch.float32).reshape(4, 4)

        sampled_features, sampled_similarity, normal_fnum = model.sample(
            F_ref=features,
            S_ref=similarity,
            normal_fnum=4,
        )

        self.assertEqual([[3.0], [4.0]], sampled_features.tolist())
        self.assertEqual([[10.0, 11.0], [14.0, 15.0]], sampled_similarity.tolist())
        self.assertEqual(2, normal_fnum)

    def test_fifo_memory_policy_trims_online_memories(self):
        model = FakeRareCLIPModel()
        for index in range(4):
            model.process_image_and_update(torch.zeros((1, 3, 8, 8)), update=True)

        rareclip._apply_fifo_memory_policy(model, 2)

        self.assertEqual([[3.0], [4.0]], model.score_memory.tolist())
        self.assertEqual([[3.0, 3.0], [4.0, 4.0]], model.IF_memory.tolist())
        self.assertEqual([[3.0, 3.0, 3.0], [4.0, 4.0, 4.0]], model.AAIF_memory[6].tolist())
        self.assertEqual([[3.0, 3.0], [4.0, 4.0]], model.PFM[0][6].tolist())
        self.assertEqual((2, 2), tuple(model.PSM[0][6].shape))

    def test_fifo_memory_policy_handles_upstream_list_memory_layout(self):
        model = type("Model", (), {})()
        model.k_shot = 0
        model.score_memory = torch.tensor([[1.0], [2.0], [3.0], [4.0]])
        model.IF_memory = torch.tensor([[1.0], [2.0], [3.0], [4.0]])
        model.AAIF_memory = [torch.tensor([[1.0], [2.0], [3.0], [4.0]])]
        model.PFM = [[torch.tensor([[1.0], [2.0], [3.0], [4.0]])]]
        model.PSM = [[torch.arange(16, dtype=torch.float32).reshape(4, 4)]]

        rareclip._apply_fifo_memory_policy(model, 2)

        self.assertEqual([[3.0], [4.0]], model.AAIF_memory[0].tolist())
        self.assertEqual([[3.0], [4.0]], model.PFM[0][0].tolist())
        self.assertEqual([[10.0, 11.0], [14.0, 15.0]], model.PSM[0][0].tolist())

    def test_predict_rows_applies_fifo_policy_after_updates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "mvtec_ad"
            for index in range(4):
                image(root / "bottle" / "test" / "good" / f"{index:03d}.png")
            items = [
                stream_item(index, f"bottle/test/good/{index:03d}.png")
                for index in range(4)
            ]
            model = FakeRareCLIPModel()
            rows = rareclip.RareCLIPWrapper._predict_rows(
                model=model,
                stream_items=items,
                dataset_root=root,
                category="bottle",
                update_memory=True,
                device=torch.device("cpu"),
                torch=torch,
                memory_policy="FIFO",
                memory_limit=2,
            )

        self.assertEqual(4, len(rows))
        self.assertEqual([[3.0], [4.0]], model.score_memory.tolist())
        self.assertEqual([[3.0, 3.0], [4.0, 4.0]], model.PFM[0][6].tolist())


if __name__ == "__main__":
    unittest.main()
