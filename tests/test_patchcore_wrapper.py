import json
import tempfile
import unittest
from pathlib import Path

from experiments.baselines import patchcore


class PatchCoreWrapperHelpersTest(unittest.TestCase):
    def test_apply_stream_order_reorders_measured_rows(self):
        rows = [
            {"image_path": "data/mvtec_ad/bottle/test/good/001.png", "stream_index": 0},
            {"image_path": "data/mvtec_ad/bottle/test/good/000.png", "stream_index": 1},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            stream = Path(tmp) / "stream.json"
            stream.write_text(
                json.dumps(
                    {
                        "items": [
                            {"image_path": "data/mvtec_ad/bottle/test/good/000.png"},
                            {"image_path": "data/mvtec_ad/bottle/test/good/001.png"},
                        ]
                    }
                )
            )
            ordered = patchcore._apply_stream_order(rows, str(stream))
        self.assertEqual([row["image_path"] for row in ordered], [
            "data/mvtec_ad/bottle/test/good/000.png",
            "data/mvtec_ad/bottle/test/good/001.png",
        ])

    def test_apply_stream_order_rejects_unknown_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            stream = Path(tmp) / "stream.json"
            stream.write_text(json.dumps({"items": ["missing.png"]}))
            with self.assertRaisesRegex(RuntimeError, "outside the evaluated PatchCore split"):
                patchcore._apply_stream_order([], str(stream))

    def test_score_to_float_accepts_numpy_like_values(self):
        self.assertEqual(patchcore._score_to_float([[1.25]]), 1.25)


if __name__ == "__main__":
    unittest.main()
