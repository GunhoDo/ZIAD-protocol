import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from experiments import p0_shards


class P0ShardsTest(unittest.TestCase):
    def test_build_manifest_maps_current_smoke_shards_and_keeps_paper_false(self):
        manifest = p0_shards.build_manifest(Path("experiments/configs/p0.yaml"))

        self.assertEqual("p0_shard_plan_ready_memory_partial", manifest["status"])
        self.assertFalse(manifest["paper_allowed"])
        self.assertEqual(8, manifest["shard_count"])
        self.assertEqual(8, manifest["ready_shard_count"])
        self.assertEqual(8, manifest["ready_calibration_shard_count"])
        self.assertEqual([], manifest["missing_shards"])
        self.assertEqual(1, len(manifest["missing_memory_policy_shards"]))
        self.assertNotIn(
            "mvtec_ad_rareclip_stream_epsilon_smoke:FIFO",
            manifest["missing_memory_policy_shards"],
        )
        self.assertNotIn(
            "mvtec_ad_rareclip_stream_epsilon_smoke:Reservoir",
            manifest["missing_memory_policy_shards"],
        )
        self.assertNotIn(
            "mvtec_ad_rareclip_stream_epsilon_smoke:Prototype-EMA",
            manifest["missing_memory_policy_shards"],
        )
        self.assertNotIn(
            "visa_rareclip_stream_epsilon_smoke:FIFO",
            manifest["missing_memory_policy_shards"],
        )
        self.assertNotIn(
            "visa_rareclip_stream_epsilon_smoke:Reservoir",
            manifest["missing_memory_policy_shards"],
        )
        self.assertNotIn(
            "visa_rareclip_stream_epsilon_smoke:Prototype-EMA",
            manifest["missing_memory_policy_shards"],
        )
        self.assertNotIn(
            "visa_patchcore_stream_epsilon_smoke:Prototype-EMA",
            manifest["missing_memory_policy_shards"],
        )
        self.assertNotIn(
            "visa_patchcore_stream_epsilon_smoke:FIFO",
            manifest["missing_memory_policy_shards"],
        )
        self.assertNotIn(
            "visa_patchcore_stream_epsilon_smoke:Reservoir",
            manifest["missing_memory_policy_shards"],
        )
        self.assertNotIn(
            "mvtec_ad_patchcore_stream_epsilon_smoke:FIFO",
            manifest["missing_memory_policy_shards"],
        )
        self.assertNotIn(
            "mvtec_ad_patchcore_stream_epsilon_smoke:Reservoir",
            manifest["missing_memory_policy_shards"],
        )
        self.assertEqual([], manifest["missing_calibration_shards"])
        self.assertEqual([], manifest["unsupported_calibration"])
        self.assertEqual([], manifest["unsupported_memory_policies"])

        shards = {(shard["dataset"], shard["baseline"]): shard for shard in manifest["shards"]}
        self.assertEqual(90, shards[("MVTec AD", "PatchCore")]["current_smoke_run_count"])
        self.assertEqual(72, shards[("VisA", "PatchCore")]["current_smoke_run_count"])
        self.assertEqual(
            ["default/SCS", "FIFO", "Reservoir", "Prototype-EMA"],
            shards[("MVTec AD", "RareCLIP")]["current_supported_memory_policies"],
        )
        self.assertEqual(
            ["default/SCS", "FIFO", "Reservoir", "Prototype-EMA"],
            shards[("MVTec AD", "RareCLIP")]["current_implemented_memory_policies"],
        )
        self.assertEqual([], shards[("MVTec AD", "RareCLIP")]["missing_memory_policies"])
        mvtec_rareclip_fifo = shards[("MVTec AD", "RareCLIP")]["memory_policy_shards"][0]
        self.assertEqual("FIFO", mvtec_rareclip_fifo["memory_policy"])
        self.assertTrue(mvtec_rareclip_fifo["config"].endswith("_fifo.yaml"))
        self.assertTrue(mvtec_rareclip_fifo["runner"].endswith("_fifo.sh"))
        self.assertEqual(90, mvtec_rareclip_fifo["current_smoke_run_count"])
        mvtec_rareclip_reservoir = shards[("MVTec AD", "RareCLIP")][
            "memory_policy_shards"
        ][1]
        self.assertEqual("Reservoir", mvtec_rareclip_reservoir["memory_policy"])
        self.assertTrue(mvtec_rareclip_reservoir["config"].endswith("_reservoir.yaml"))
        self.assertTrue(mvtec_rareclip_reservoir["runner"].endswith("_reservoir.sh"))
        self.assertEqual(90, mvtec_rareclip_reservoir["current_smoke_run_count"])
        mvtec_rareclip_prototype = shards[("MVTec AD", "RareCLIP")][
            "memory_policy_shards"
        ][2]
        self.assertEqual("Prototype-EMA", mvtec_rareclip_prototype["memory_policy"])
        self.assertTrue(mvtec_rareclip_prototype["config"].endswith("_prototype_ema.yaml"))
        self.assertTrue(mvtec_rareclip_prototype["runner"].endswith("_prototype_ema.sh"))
        self.assertEqual(90, mvtec_rareclip_prototype["current_smoke_run_count"])
        self.assertEqual(
            ["default/SCS", "FIFO", "Reservoir", "Prototype-EMA"],
            shards[("VisA", "RareCLIP")]["current_implemented_memory_policies"],
        )
        self.assertEqual([], shards[("VisA", "RareCLIP")]["missing_memory_policies"])
        self.assertEqual(
            72,
            shards[("VisA", "RareCLIP")]["memory_policy_shards"][0][
                "current_smoke_run_count"
            ],
        )
        self.assertEqual(
            72,
            shards[("VisA", "RareCLIP")]["memory_policy_shards"][1][
                "current_smoke_run_count"
            ],
        )
        prototype_shard = shards[("VisA", "RareCLIP")]["memory_policy_shards"][2]
        self.assertEqual("Prototype-EMA", prototype_shard["memory_policy"])
        self.assertTrue(prototype_shard["config"].endswith("_prototype_ema.yaml"))
        self.assertTrue(prototype_shard["runner"].endswith("_prototype_ema.sh"))
        self.assertEqual(72, prototype_shard["current_smoke_run_count"])
        self.assertEqual([], shards[("MVTec AD", "RareCLIP")]["unsupported_memory_policies"])
        self.assertEqual(
            ["default/SCS", "FIFO", "Reservoir", "Prototype-EMA"],
            shards[("MVTec AD", "PatchCore")]["current_supported_memory_policies"],
        )
        self.assertEqual(
            ["default/SCS", "FIFO", "Reservoir"],
            shards[("MVTec AD", "PatchCore")]["current_implemented_memory_policies"],
        )
        self.assertEqual(
            ["Prototype-EMA"],
            shards[("MVTec AD", "PatchCore")]["missing_memory_policies"],
        )
        mvtec_patchcore_fifo = shards[("MVTec AD", "PatchCore")]["memory_policy_shards"][
            0
        ]
        self.assertEqual("FIFO", mvtec_patchcore_fifo["memory_policy"])
        self.assertTrue(mvtec_patchcore_fifo["config"].endswith("_fifo.yaml"))
        self.assertTrue(mvtec_patchcore_fifo["runner"].endswith("_fifo.sh"))
        self.assertEqual(90, mvtec_patchcore_fifo["current_smoke_run_count"])
        mvtec_patchcore_reservoir = shards[("MVTec AD", "PatchCore")][
            "memory_policy_shards"
        ][1]
        self.assertEqual("Reservoir", mvtec_patchcore_reservoir["memory_policy"])
        self.assertTrue(mvtec_patchcore_reservoir["config"].endswith("_reservoir.yaml"))
        self.assertTrue(mvtec_patchcore_reservoir["runner"].endswith("_reservoir.sh"))
        self.assertEqual(90, mvtec_patchcore_reservoir["current_smoke_run_count"])
        self.assertEqual([], shards[("MVTec AD", "PatchCore")]["unsupported_memory_policies"])
        self.assertEqual(
            ["default/SCS", "FIFO", "Reservoir", "Prototype-EMA"],
            shards[("VisA", "PatchCore")]["current_implemented_memory_policies"],
        )
        self.assertEqual([], shards[("VisA", "PatchCore")]["missing_memory_policies"])
        self.assertEqual(
            72,
            shards[("VisA", "PatchCore")]["memory_policy_shards"][0][
                "current_smoke_run_count"
            ],
        )
        reservoir_shard = shards[("VisA", "PatchCore")]["memory_policy_shards"][1]
        self.assertEqual("Reservoir", reservoir_shard["memory_policy"])
        self.assertTrue(reservoir_shard["config"].endswith("_reservoir.yaml"))
        self.assertTrue(reservoir_shard["runner"].endswith("_reservoir.sh"))
        self.assertEqual(72, reservoir_shard["current_smoke_run_count"])
        prototype_shard = shards[("VisA", "PatchCore")]["memory_policy_shards"][2]
        self.assertEqual("Prototype-EMA", prototype_shard["memory_policy"])
        self.assertTrue(prototype_shard["config"].endswith("_prototype_ema.yaml"))
        self.assertTrue(prototype_shard["runner"].endswith("_prototype_ema.sh"))
        self.assertEqual(72, prototype_shard["current_smoke_run_count"])
        self.assertEqual(
            ["default/SCS"],
            shards[("MVTec AD", "WinCLIP")]["current_implemented_memory_policies"],
        )
        self.assertEqual([], shards[("MVTec AD", "WinCLIP")]["missing_memory_policies"])
        self.assertEqual(
            ["none", "temperature_scaling"],
            shards[("MVTec AD", "WinCLIP")]["current_supported_calibration"],
        )
        self.assertEqual(
            ["none", "temperature_scaling"],
            shards[("MVTec AD", "WinCLIP")]["current_implemented_calibration"],
        )
        self.assertEqual(
            ["none", "temperature_scaling"],
            shards[("VisA", "WinCLIP")]["current_implemented_calibration"],
        )
        self.assertEqual(
            144,
            shards[("VisA", "WinCLIP")]["calibration_shards"][0][
                "current_smoke_run_count"
            ],
        )
        self.assertEqual(
            180,
            shards[("MVTec AD", "WinCLIP")]["calibration_shards"][0][
                "current_smoke_run_count"
            ],
        )
        for shard in manifest["shards"]:
            self.assertFalse(shard["paper_allowed"])
            self.assertEqual("ready_smoke_shard", shard["status"])
            self.assertTrue(Path(shard["config"]).exists())
            self.assertTrue(Path(shard["runner"]).exists())
            for calibration_shard in shard["calibration_shards"]:
                self.assertFalse(calibration_shard["paper_allowed"])

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
                    "calibration_shards": [],
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
            self.assertEqual(8, payload["ready_calibration_shard_count"])
            self.assertEqual(1, len(payload["missing_memory_policy_shards"]))


if __name__ == "__main__":
    unittest.main()
