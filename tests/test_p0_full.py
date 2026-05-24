import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from experiments import p0_full, run_p0_execution_plan


class P0FullSkeletonTest(unittest.TestCase):
    def test_build_manifest_defines_separate_full_outputs_and_matrix_count(self):
        manifest = p0_full.build_manifest(Path("experiments/configs/p0_full/compact.yaml"))

        self.assertEqual("p0_full_skeleton_ready", manifest["status"])
        self.assertEqual("p0_full", manifest["run_tier"])
        self.assertFalse(manifest["paper_allowed"])
        self.assertFalse(manifest["claim_allowed"])
        self.assertEqual("not_reviewed", manifest["review_status"])
        self.assertEqual("p0_full", manifest["source_tier"])
        self.assertEqual(288, manifest["matrix_count"])
        self.assertEqual(24, manifest["step_count"])
        self.assertEqual(["0", "1", "2"], manifest["matrix_axes"]["seeds"])
        self.assertEqual(
            ["default/SCS", "Reservoir"],
            manifest["matrix_axes"]["memory_policies"]["PatchCore"],
        )
        self.assertEqual(
            ["default/no-memory"],
            manifest["matrix_axes"]["memory_policies"]["WinCLIP"],
        )

        for step in manifest["steps"]:
            self.assertEqual("p0_full", step["run_tier"])
            self.assertEqual("p0_full", step["source_tier"])
            self.assertFalse(step["paper_allowed"])
            self.assertFalse(step["claim_allowed"])
            self.assertEqual(12, step["expected_full_run_count"])
            for output in step["outputs"].values():
                self.assertTrue(output.startswith("results/latest/p0_full/"))
                self.assertNotIn("results/latest/p0_shards", output)

    def test_smoke_outputs_do_not_satisfy_full_execution_plan(self):
        plan = p0_full.build_execution_plan(Path("experiments/configs/p0_full/compact.yaml"))
        first_step = plan["steps"][0]

        validation = run_p0_execution_plan.validate_step_outputs(first_step)

        self.assertFalse(validation.valid)
        self.assertEqual([], validation.errors)
        self.assertTrue(validation.missing_outputs)
        for missing in validation.missing_outputs:
            self.assertIn("results/latest/p0_full/", missing)

    def test_full_execution_plan_is_dry_run_compatible(self):
        plan = p0_full.build_execution_plan(Path("experiments/configs/p0_full/compact.yaml"))
        calls = []

        summary = run_p0_execution_plan.run_execution_plan(
            plan,
            dry_run=True,
            command_runner=lambda command: calls.append(command) or 0,
        )

        self.assertTrue(summary.ok)
        self.assertEqual(24, summary.total_steps)
        self.assertEqual(24, summary.selected_steps)
        self.assertEqual(0, summary.skipped_steps)
        self.assertEqual(24, summary.pending_steps)
        self.assertEqual(24, summary.dry_run_steps)
        self.assertEqual(0, summary.executed_steps)
        self.assertEqual([], calls)

    def test_main_writes_manifest_and_execution_plan(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            manifest_path = root / "manifest.json"
            plan_path = root / "execution_plan.json"
            with mock.patch(
                "sys.argv",
                [
                    "p0_full.py",
                    "--config",
                    "experiments/configs/p0_full/compact.yaml",
                    "--manifest",
                    str(manifest_path),
                    "--execution-plan",
                    str(plan_path),
                ],
            ):
                p0_full.main()

            manifest = json.loads(manifest_path.read_text())
            plan = json.loads(plan_path.read_text())
            self.assertEqual(288, manifest["matrix_count"])
            self.assertEqual(24, plan["step_count"])
            self.assertFalse(plan["paper_allowed"])
            self.assertFalse(plan["claim_allowed"])


if __name__ == "__main__":
    unittest.main()
