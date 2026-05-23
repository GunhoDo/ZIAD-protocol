import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from experiments import p0_shards


class P0ShardsTest(unittest.TestCase):
    def test_build_manifest_maps_current_smoke_shards_and_keeps_paper_false(self):
        manifest = p0_shards.build_manifest(Path("experiments/configs/p0.yaml"))

        self.assertEqual("p0_shard_plan_ready", manifest["status"])
        self.assertFalse(manifest["paper_allowed"])
        self.assertEqual(8, manifest["shard_count"])
        self.assertEqual(8, manifest["ready_shard_count"])
        self.assertEqual([], manifest["missing_shards"])
        self.assertEqual(["temperature_scaling"], manifest["unsupported_calibration"])
        self.assertEqual(
            ["Prototype-EMA"],
            manifest["unsupported_memory_policies"],
        )

        shards = {(shard["dataset"], shard["baseline"]): shard for shard in manifest["shards"]}
        self.assertEqual(90, shards[("MVTec AD", "PatchCore")]["current_smoke_run_count"])
        self.assertEqual(72, shards[("VisA", "PatchCore")]["current_smoke_run_count"])
        self.assertEqual(
            ["default/SCS", "FIFO", "Reservoir"],
            shards[("MVTec AD", "RareCLIP")]["current_supported_memory_policies"],
        )
        self.assertEqual(
            ["Prototype-EMA"],
            shards[("MVTec AD", "RareCLIP")]["unsupported_memory_policies"],
        )
        self.assertEqual(
            ["default/SCS", "FIFO", "Reservoir", "Prototype-EMA"],
            shards[("MVTec AD", "PatchCore")]["current_supported_memory_policies"],
        )
        self.assertEqual([], shards[("MVTec AD", "PatchCore")]["unsupported_memory_policies"])
        for shard in manifest["shards"]:
            self.assertFalse(shard["paper_allowed"])
            self.assertEqual("ready_smoke_shard", shard["status"])
            self.assertTrue(Path(shard["config"]).exists())
            self.assertTrue(Path(shard["runner"]).exists())

    def test_verify_manifest_can_require_existing_smoke_outputs(self):
        manifest = p0_shards.build_manifest(Path("experiments/configs/p0.yaml"))

        errors = p0_shards.verify_manifest(manifest, require_outputs=True)

        self.assertEqual([], errors)

    def test_verify_manifest_reports_missing_required_output(self):
        manifest = {
            "paper_allowed": False,
            "shards": [
                {
                    "shard_id": "example",
                    "paper_allowed": False,
                    "config": "experiments/configs/p0.yaml",
                    "runner": "scripts/run_p0.sh",
                    "outputs": {"aggregate_metrics": "missing.csv"},
                }
            ],
        }

        errors = p0_shards.verify_manifest(manifest, require_outputs=True)

        self.assertEqual(
            ["example: missing output aggregate_metrics: missing.csv"],
            errors,
        )

    def test_plan_command_writes_manifest(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "manifest.json"
            with mock.patch(
                "sys.argv",
                [
                    "p0_shards.py",
                    "plan",
                    "experiments/configs/p0.yaml",
                    "--output",
                    str(output),
                ],
            ):
                p0_shards.main()

            payload = json.loads(output.read_text())
            self.assertFalse(payload["paper_allowed"])
            self.assertEqual(8, payload["ready_shard_count"])


if __name__ == "__main__":
    unittest.main()
