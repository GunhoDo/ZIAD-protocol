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
        self.assertEqual(8, manifest["ready_calibration_shard_count"])
        self.assertEqual([], manifest["missing_shards"])
        self.assertEqual(0, len(manifest["missing_memory_policy_shards"]))
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
        self.assertNotIn(
            "mvtec_ad_patchcore_stream_epsilon_smoke:Prototype-EMA",
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
            ["default/SCS", "FIFO", "Reservoir", "Prototype-EMA"],
            shards[("MVTec AD", "PatchCore")]["current_implemented_memory_policies"],
        )
        self.assertEqual([], shards[("MVTec AD", "PatchCore")]["missing_memory_policies"])
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
        mvtec_patchcore_prototype = shards[("MVTec AD", "PatchCore")][
            "memory_policy_shards"
        ][2]
        self.assertEqual("Prototype-EMA", mvtec_patchcore_prototype["memory_policy"])
        self.assertTrue(mvtec_patchcore_prototype["config"].endswith("_prototype_ema.yaml"))
        self.assertTrue(mvtec_patchcore_prototype["runner"].endswith("_prototype_ema.sh"))
        self.assertEqual(90, mvtec_patchcore_prototype["current_smoke_run_count"])
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
            self.assertEqual(0, len(payload["missing_memory_policy_shards"]))

    def test_build_execution_plan_orders_restartable_smoke_steps(self):
        plan = p0_shards.build_execution_plan(Path("experiments/configs/p0.yaml"))

        self.assertEqual("p0_execution_plan_ready", plan["status"])
        self.assertFalse(plan["paper_allowed"])
        self.assertFalse(plan["claim_allowed"])
        self.assertEqual("p0_shard_plan_ready", plan["source_manifest_status"])
        self.assertEqual(28, plan["step_count"])
        self.assertEqual(28, plan["ready_step_count"])
        self.assertEqual(0, plan["pending_step_count"])
        self.assertEqual(
            {
                "base_stream_epsilon": 8,
                "memory_policy": 12,
                "calibration": 8,
            },
            plan["phase_counts"],
        )
        self.assertEqual(plan["step_count"], len(plan["execution_order"]))
        self.assertEqual(plan["execution_order"], [step["step_id"] for step in plan["steps"]])

        first_step = plan["steps"][0]
        self.assertEqual("base_stream_epsilon", first_step["phase"])
        self.assertEqual("MVTec AD", first_step["dataset"])
        self.assertEqual("RareCLIP", first_step["baseline"])
        self.assertEqual("default/SCS", first_step["memory_policy"])
        self.assertEqual("none", first_step["calibration"])
        self.assertEqual([], first_step["depends_on"])
        self.assertEqual("outputs_present_smoke", first_step["current_status"])
        self.assertFalse(first_step["paper_allowed"])
        self.assertFalse(first_step["claim_allowed"])
        self.assertIn("aggregate_metrics", first_step["outputs"])

        memory_step = next(
            step
            for step in plan["steps"]
            if step["step_id"]
            == "mvtec_ad_rareclip_stream_epsilon_smoke:memory:fifo"
        )
        self.assertEqual("memory_policy", memory_step["phase"])
        self.assertEqual("FIFO", memory_step["memory_policy"])
        self.assertEqual(["mvtec_ad_rareclip_stream_epsilon_smoke:base"], memory_step["depends_on"])
        self.assertIn("Skip this step", memory_step["resume_policy"])

        calibration_step = next(
            step
            for step in plan["steps"]
            if step["step_id"]
            == "mvtec_ad_rareclip_stream_epsilon_smoke:calibration:temperature_scaling"
        )
        self.assertEqual("calibration", calibration_step["phase"])
        self.assertEqual("temperature_scaling", calibration_step["calibration"])
        self.assertEqual(
            ["mvtec_ad_rareclip_stream_epsilon_smoke:base"],
            calibration_step["depends_on"],
        )
        self.assertEqual("measured_smoke", calibration_step["validation"]["required_status"])
        self.assertFalse(calibration_step["validation"]["paper_allowed"])

    def test_execution_plan_command_writes_manifest(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "execution_plan.json"
            with mock.patch(
                "sys.argv",
                [
                    "p0_shards.py",
                    "execution-plan",
                    "experiments/configs/p0.yaml",
                    "--output",
                    str(output),
                ],
            ):
                p0_shards.main()

            payload = json.loads(output.read_text())
            self.assertEqual("p0_execution_plan_ready", payload["status"])
            self.assertFalse(payload["paper_allowed"])
            self.assertFalse(payload["claim_allowed"])
            self.assertEqual(28, payload["step_count"])


if __name__ == "__main__":
    unittest.main()
