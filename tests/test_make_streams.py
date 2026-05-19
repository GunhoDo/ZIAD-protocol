import json
import tempfile
import unittest
from pathlib import Path

from experiments import make_streams


def touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")


class MakeStreamsTest(unittest.TestCase):
    def _fixture(self):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        for name in ["000.png", "001.png", "002.png", "003.png"]:
            touch(root / "bottle" / "test" / "good" / name)
        for name in ["000.png", "001.png"]:
            touch(root / "bottle" / "test" / "scratch" / name)
        touch(root / "bottle" / "test" / "crack" / "000.png")
        touch(root / "bottle" / "train" / "good" / "train_only.png")
        return tmp, root

    def test_enumerates_test_split_with_labels(self):
        tmp, root = self._fixture()
        with tmp:
            samples = make_streams.enumerate_mvtec_samples(root, "bottle")
            rels = {sample.rel_path for sample in samples}
            self.assertIn("bottle/test/good/000.png", rels)
            self.assertNotIn("bottle/train/good/train_only.png", rels)
            labels = {sample.anomaly_type: sample.label for sample in samples}
            self.assertEqual(labels["good"], 0)
            self.assertEqual(labels["scratch"], 1)
            self.assertEqual(labels["crack"], 1)

    def test_build_iid_stream_schema_and_determinism(self):
        tmp, root = self._fixture()
        with tmp:
            one = make_streams.build_stream(
                dataset_root=root,
                category="bottle",
                stream_type="iid",
                prevalence="0.25",
                contamination_epsilon="0",
                seed="7",
                length="4",
                burst_length="2",
            )
            two = make_streams.build_stream(
                dataset_root=root,
                category="bottle",
                stream_type="iid",
                prevalence="0.25",
                contamination_epsilon="0",
                seed="7",
                length="4",
                burst_length="2",
            )
            make_streams.validate_stream_payload(one)
            self.assertEqual(one, two)
            self.assertEqual(len(one["items"]), 4)
            self.assertEqual(len({item["image_path"] for item in one["items"]}), 4)
            self.assertEqual(one["metadata"]["scoring_mode"], "stream_ordered_offline")
            self.assertEqual(one["metadata"]["training_source"], "train/good")
            self.assertEqual(one["metadata"]["stream_source"], "test/*")
            self.assertEqual(one["metadata"]["latency_semantics"], "offline_batch_amortized")
            for item in one["items"]:
                self.assertEqual(
                    item["label"], 0 if item["anomaly_type"] == "good" else 1
                )

    def test_length_clamps_without_duplicates_and_warns(self):
        tmp, root = self._fixture()
        with tmp:
            payload = make_streams.build_stream(
                dataset_root=root,
                category="bottle",
                stream_type="iid",
                prevalence="0.1",
                contamination_epsilon="0",
                seed="1",
                length="999",
                burst_length="2",
            )
            self.assertEqual(payload["metadata"]["applied_stream_length"], 7)
            codes = {warning["code"] for warning in payload["metadata"]["warnings"]}
            self.assertIn("requested_length_clamped_no_duplicates", codes)
            self.assertEqual(len({item["image_path"] for item in payload["items"]}), 7)

    def test_omitted_length_prioritizes_closest_ratio(self):
        tmp, root = self._fixture()
        with tmp:
            payload = make_streams.build_stream(
                dataset_root=root,
                category="bottle",
                stream_type="iid",
                prevalence="0.5",
                contamination_epsilon="0",
                seed="1",
                burst_length="2",
            )
            self.assertEqual(payload["metadata"]["applied_anomaly_fraction"], 0.5)
            # Exact ratio wins first, then the longest feasible exact-ratio stream.
            self.assertEqual(payload["metadata"]["applied_stream_length"], 6)
            self.assertEqual(payload["metadata"]["selected_anomaly_count"], 3)

    def test_bursty_contiguous_blocks_and_merge_warning(self):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        with tmp:
            touch(root / "bottle" / "test" / "good" / "000.png")
            for idx in range(5):
                touch(root / "bottle" / "test" / "scratch" / f"{idx:03d}.png")
            payload = make_streams.build_stream(
                dataset_root=root,
                category="bottle",
                stream_type="bursty",
                prevalence="0.8",
                contamination_epsilon="0",
                seed="3",
                length="6",
                burst_length="2",
            )
            labels = [item["label"] for item in payload["items"]]
            lengths = []
            current = 0
            for label in labels:
                if label == 1:
                    current += 1
                elif current:
                    lengths.append(current)
                    current = 0
            if current:
                lengths.append(current)
            self.assertEqual(lengths, payload["metadata"]["applied_burst_lengths"])
            self.assertTrue(all(length > 0 for length in lengths))
            codes = {warning["code"] for warning in payload["metadata"]["warnings"]}
            self.assertIn("burst_blocks_merged_insufficient_normals", codes)

    def test_invalid_config_fails(self):
        tmp, root = self._fixture()
        with tmp:
            with self.assertRaisesRegex(ValueError, "contamination_epsilon"):
                make_streams.build_stream(
                    dataset_root=root,
                    category="bottle",
                    stream_type="iid",
                    prevalence="0.9",
                    contamination_epsilon="0.2",
                    seed="1",
                    burst_length="1",
                )
            with self.assertRaisesRegex(ValueError, "positive integer"):
                make_streams.build_stream(
                    dataset_root=root,
                    category="bottle",
                    stream_type="bursty",
                    prevalence="0.1",
                    contamination_epsilon="0",
                    seed="1",
                    burst_length="0",
                )

    def test_cli_writes_valid_json(self):
        tmp, root = self._fixture()
        with tmp:
            output = root / "stream.json"
            make_streams.main(
                [
                    "--dataset-root",
                    str(root),
                    "--category",
                    "bottle",
                    "--stream-type",
                    "iid",
                    "--prevalence",
                    "0.25",
                    "--contamination-epsilon",
                    "0",
                    "--seed",
                    "4",
                    "--length",
                    "4",
                    "--output",
                    str(output),
                ]
            )
            payload = json.loads(output.read_text())
            make_streams.validate_stream_payload(payload)

    def test_placeholder_p0_mode_writes_empty_placeholder_contracts(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "streams"
            make_streams.write_placeholder_streams(out)
            files = sorted(out.glob("*.json"))
            self.assertEqual(len(files), 6)
            payload = json.loads(files[0].read_text())
            self.assertEqual(payload["status"], "placeholder")
            self.assertEqual(payload["items"], [])
            self.assertEqual(
                payload["metadata"]["warnings"][0]["code"], "placeholder_not_measured"
            )


if __name__ == "__main__":
    unittest.main()
