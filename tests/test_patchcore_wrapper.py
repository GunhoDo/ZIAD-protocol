import json
import tempfile
import unittest
from pathlib import Path

from experiments.baselines import patchcore


def touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")


def stream_item(index, image_path, label=0, anomaly_type="good"):
    return {
        "stream_index": index,
        "image_path": image_path,
        "label": label,
        "category": "bottle",
        "source_split": "test",
        "anomaly_type": anomaly_type,
    }


class PatchCoreWrapperHelpersTest(unittest.TestCase):
    def test_filter_test_dataset_to_stream_restricts_and_orders_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "mvtec_ad"
            img0 = root / "bottle" / "test" / "good" / "000.png"
            img1 = root / "bottle" / "test" / "scratch" / "001.png"
            extra = root / "bottle" / "test" / "good" / "extra.png"
            for path in [img0, img1, extra]:
                touch(path)

            class Dataset:
                data_to_iterate = [
                    ["bottle", "good", str(extra), None],
                    ["bottle", "scratch", str(img1), None],
                    ["bottle", "good", str(img0), None],
                ]

            dataset = Dataset()
            items = [
                stream_item(0, "bottle/test/good/000.png"),
                stream_item(1, "bottle/test/scratch/001.png", label=1, anomaly_type="scratch"),
            ]

            patchcore._filter_test_dataset_to_stream(dataset, items, root)

        self.assertEqual(
            [Path(entry[2]).name for entry in dataset.data_to_iterate],
            ["000.png", "001.png"],
        )

    def test_apply_stream_order_reorders_and_filters_measured_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "mvtec_ad"
            img0 = root / "bottle" / "test" / "good" / "000.png"
            img1 = root / "bottle" / "test" / "good" / "001.png"
            extra = root / "bottle" / "test" / "good" / "extra.png"
            for path in [img0, img1, extra]:
                touch(path)
            rows = [
                {"image_path": str(img1), "stream_index": 0, "label": 0, "category": "bottle"},
                {"image_path": str(extra), "stream_index": 1, "label": 0, "category": "bottle"},
                {"image_path": str(img0), "stream_index": 2, "label": 0, "category": "bottle"},
            ]
            stream = Path(tmp) / "stream.json"
            stream.write_text(
                json.dumps(
                    {
                        "items": [
                            stream_item(0, "bottle/test/good/000.png"),
                            stream_item(1, "bottle/test/good/001.png"),
                        ]
                    }
                )
            )
            ordered = patchcore._apply_stream_order(rows, str(stream), root)
        self.assertEqual(
            [row["image_path"] for row in ordered],
            ["bottle/test/good/000.png", "bottle/test/good/001.png"],
        )
        self.assertEqual([row["stream_index"] for row in ordered], [0, 1])
        self.assertEqual(len(ordered), 2)

    def test_apply_stream_order_rejects_unknown_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "mvtec_ad"
            root.mkdir()
            stream = Path(tmp) / "stream.json"
            stream.write_text(json.dumps({"items": [stream_item(0, "bottle/test/good/missing.png")]}))
            with self.assertRaisesRegex(RuntimeError, "missing image"):
                patchcore._apply_stream_order([], str(stream), root)

    def test_apply_stream_order_can_require_stream_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RuntimeError, "required but missing"):
                patchcore._apply_stream_order(
                    [], str(Path(tmp) / "missing.json"), tmp, require_stream=True
                )

    def test_apply_stream_order_can_require_non_empty_stream(self):
        with tempfile.TemporaryDirectory() as tmp:
            stream = Path(tmp) / "stream.json"
            stream.write_text(json.dumps({"items": []}))
            with self.assertRaisesRegex(RuntimeError, "no items"):
                patchcore._apply_stream_order([], str(stream), tmp, require_stream=True)

    def test_apply_stream_order_rejects_missing_required_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            stream = Path(tmp) / "stream.json"
            stream.write_text(json.dumps({"items": [{"image_path": "x.png"}]}))
            with self.assertRaisesRegex(RuntimeError, "missing required"):
                patchcore._apply_stream_order([], str(stream), tmp)

    def test_apply_stream_order_rejects_path_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "mvtec_ad"
            outside = Path(tmp) / "outside.png"
            root.mkdir()
            touch(outside)
            stream = Path(tmp) / "stream.json"
            stream.write_text(json.dumps({"items": [stream_item(0, str(outside))]}))
            with self.assertRaisesRegex(RuntimeError, "outside dataset_root"):
                patchcore._apply_stream_order([], str(stream), root)

    def test_apply_stream_order_rejects_label_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "mvtec_ad"
            img = root / "bottle" / "test" / "scratch" / "000.png"
            touch(img)
            rows = [{"image_path": str(img), "stream_index": 0, "label": 0, "category": "bottle"}]
            stream = Path(tmp) / "stream.json"
            stream.write_text(json.dumps({"items": [stream_item(0, "bottle/test/scratch/000.png", label=1, anomaly_type="scratch")]}))
            with self.assertRaisesRegex(RuntimeError, "label mismatch"):
                patchcore._apply_stream_order(rows, str(stream), root)

    def test_score_to_float_accepts_numpy_like_values(self):
        self.assertEqual(patchcore._score_to_float([[1.25]]), 1.25)

    def test_fifo_sampler_keeps_newest_features(self):
        sampler = patchcore._FIFOSampler(0.4)

        sampled = sampler.run([0, 1, 2, 3, 4])

        self.assertEqual([3, 4], sampled)

    def test_fifo_sampler_keeps_at_least_one_feature(self):
        sampler = patchcore._FIFOSampler(0.01)

        sampled = sampler.run([0, 1, 2])

        self.assertEqual([2], sampled)

    def test_make_sampler_supports_fifo_memory_policy_sampler(self):
        sampler = patchcore.PatchCoreWrapper._make_sampler(
            sampler_module=None,
            name="fifo",
            percentage=0.5,
            device=None,
        )

        self.assertEqual([2, 3], sampler.run([0, 1, 2, 3]))


if __name__ == "__main__":
    unittest.main()
