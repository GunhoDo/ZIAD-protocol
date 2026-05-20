import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image
import torch

from experiments.baselines import anomalyclip


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


class FakeAnomalyCLIPModel:
    def encode_image(self, tensor, features_list, DPAM_layer):
        batch = tensor.shape[0]
        image_features = torch.tensor([[0.0, 1.0]], dtype=torch.float32).repeat(batch, 1)
        patch_features = [
            torch.ones((batch, 5, 2), dtype=torch.float32),
            torch.full((batch, 5, 2), 2.0, dtype=torch.float32),
        ]
        return image_features, patch_features


class FakeAnomalyCLIPLib:
    @staticmethod
    def compute_similarity(patch_feature, text_feature):
        return torch.zeros((patch_feature.shape[0], patch_feature.shape[1], 2)), None

    @staticmethod
    def get_similarity_map(similarity, image_size):
        return torch.zeros((similarity.shape[0], image_size, image_size, 2), dtype=torch.float32)


def fake_preprocess(_image):
    return torch.zeros((3, 8, 8), dtype=torch.float32)


def fake_gaussian_filter(frame, sigma):
    return frame.numpy()


class AnomalyCLIPWrapperHelpersTest(unittest.TestCase):
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
                anomalyclip._load_stream_items(str(stream))

    def test_resolve_stream_image_path_rejects_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "mvtec_ad"
            outside = Path(tmp) / "outside.png"
            root.mkdir()
            image(outside)
            with self.assertRaisesRegex(RuntimeError, "outside dataset_root"):
                anomalyclip._resolve_stream_image_path(str(outside), root)

    def test_predict_rows_uses_stream_order_and_text_probability_score(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "mvtec_ad"
            image(root / "bottle" / "test" / "good" / "000.png")
            image(root / "bottle" / "test" / "scratch" / "001.png")
            items = [
                stream_item(0, "bottle/test/good/000.png"),
                stream_item(1, "bottle/test/scratch/001.png", 1, "scratch"),
            ]
            text_features = torch.tensor([[[1.0, 0.0], [0.0, 1.0]]], dtype=torch.float32)
            rows = anomalyclip.AnomalyCLIPWrapper._predict_rows(
                model=FakeAnomalyCLIPModel(),
                preprocess=fake_preprocess,
                text_features=text_features,
                stream_items=items,
                dataset_root=root,
                category="bottle",
                image_size=8,
                features_list=(6, 12),
                feature_map_start=0,
                sigma=4,
                dpam_layer=20,
                score_source="text_prob",
                device=torch.device("cpu"),
                torch=torch,
                anomalyclip_lib=FakeAnomalyCLIPLib,
                gaussian_filter=fake_gaussian_filter,
            )
        self.assertEqual([row["stream_index"] for row in rows], [0, 1])
        self.assertEqual([row["image_path"] for row in rows], [item["image_path"] for item in items])
        self.assertEqual([row["label"] for row in rows], [0, 1])
        self.assertEqual([row["status"] for row in rows], ["measured", "measured"])
        self.assertEqual(rows[0]["anomaly_score"], "0.9999994040")
        self.assertEqual(rows[1]["anomaly_score"], "0.9999994040")


if __name__ == "__main__":
    unittest.main()
