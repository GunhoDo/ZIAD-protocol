import csv
import json
import tempfile
import unittest
from pathlib import Path

from experiments import run_p0_execution_plan


class P0ExecutionPlanRunnerTest(unittest.TestCase):
    def _write_csv(self, path: Path, rows: int) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["dataset", "status"])
            writer.writeheader()
            for index in range(rows):
                writer.writerow({"dataset": "MVTec AD", "status": f"measured_{index}"})

    def _write_manifest(
        self,
        path: Path,
        *,
        paper_allowed: bool = False,
        claim_allowed: bool | None = None,
    ) -> None:
        payload = {"status": "complete", "paper_allowed": paper_allowed}
        if claim_allowed is not None:
            payload["claim_allowed"] = claim_allowed
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload))

    def _step(self, root: Path, *, step_id: str = "step-0", command: str = "true") -> dict:
        metrics = root / f"{step_id}-metrics.csv"
        manifest = root / f"{step_id}-manifest.json"
        crd = root / f"{step_id}-crd.csv"
        self._write_csv(metrics, 2)
        self._write_manifest(manifest)
        self._write_csv(crd, 1)
        return {
            "step_id": step_id,
            "paper_allowed": False,
            "claim_allowed": False,
            "command": command,
            "outputs": {
                "aggregate_metrics": str(metrics),
                "aggregate_manifest": str(manifest),
                "crd_lite_summary": str(crd),
            },
            "expected_smoke_run_count": 2,
            "validation": {
                "required_outputs": [
                    "aggregate_manifest",
                    "aggregate_metrics",
                    "crd_lite_summary",
                ],
                "required_status": "measured_smoke",
                "paper_allowed": False,
            },
        }

    def _plan(self, steps: list[dict]) -> dict:
        return {
            "paper_allowed": False,
            "claim_allowed": False,
            "steps": steps,
        }

    def test_all_ready_plan_skips_all_steps(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            calls = []
            plan = self._plan([self._step(root, step_id="a"), self._step(root, step_id="b")])

            summary = run_p0_execution_plan.run_execution_plan(
                plan, command_runner=lambda command: calls.append(command) or 0
            )

            self.assertTrue(summary.ok)
            self.assertEqual(2, summary.skipped_steps)
            self.assertEqual(0, summary.pending_steps)
            self.assertEqual(0, summary.executed_steps)
            self.assertEqual([], calls)

    def test_missing_aggregate_output_marks_step_pending_and_executes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            step = self._step(root)
            Path(step["outputs"]["crd_lite_summary"]).unlink()

            def runner(command: str) -> int:
                self._write_csv(Path(step["outputs"]["crd_lite_summary"]), 1)
                return 0

            summary = run_p0_execution_plan.run_execution_plan(
                self._plan([step]), command_runner=runner
            )

            self.assertTrue(summary.ok)
            self.assertEqual(1, summary.pending_steps)
            self.assertEqual(1, summary.executed_steps)
            self.assertEqual(0, summary.skipped_steps)

    def test_dry_run_does_not_execute_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            step = self._step(root)
            Path(step["outputs"]["aggregate_metrics"]).unlink()
            calls = []

            summary = run_p0_execution_plan.run_execution_plan(
                self._plan([step]),
                dry_run=True,
                command_runner=lambda command: calls.append(command) or 0,
            )

            self.assertTrue(summary.ok)
            self.assertEqual(1, summary.pending_steps)
            self.assertEqual(1, summary.dry_run_steps)
            self.assertEqual(0, summary.executed_steps)
            self.assertEqual([], calls)

    def test_failed_command_stops_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = self._step(root, step_id="first", command="fail")
            Path(first["outputs"]["aggregate_metrics"]).unlink()
            second = self._step(root, step_id="second")
            calls = []

            summary = run_p0_execution_plan.run_execution_plan(
                self._plan([first, second]),
                command_runner=lambda command: calls.append(command) or 7,
            )

            self.assertFalse(summary.ok)
            self.assertEqual("first", summary.failed_step)
            self.assertEqual(1, summary.pending_steps)
            self.assertEqual(0, summary.executed_steps)
            self.assertEqual(["fail"], calls)

    def test_paper_allowed_true_in_manifest_fails_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            step = self._step(root)
            self._write_manifest(Path(step["outputs"]["aggregate_manifest"]), paper_allowed=True)

            validation = run_p0_execution_plan.validate_step_outputs(step)

            self.assertFalse(validation.valid)
            self.assertIn("paper_allowed", validation.errors[0])

    def test_claim_allowed_true_in_manifest_fails_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            step = self._step(root)
            self._write_manifest(
                Path(step["outputs"]["aggregate_manifest"]),
                paper_allowed=False,
                claim_allowed=True,
            )

            validation = run_p0_execution_plan.validate_step_outputs(step)

            self.assertFalse(validation.valid)
            self.assertIn("claim_allowed", validation.errors[0])

    def test_step_and_range_selection_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            steps = [
                self._step(root, step_id="a"),
                self._step(root, step_id="b"),
                self._step(root, step_id="c"),
            ]

            by_id = run_p0_execution_plan.run_execution_plan(
                self._plan(steps), step_selector="b"
            )
            by_index = run_p0_execution_plan.run_execution_plan(
                self._plan(steps), step_selector="2"
            )
            by_range = run_p0_execution_plan.run_execution_plan(
                self._plan(steps), start_index=1, end_index=2
            )

            self.assertEqual(1, by_id.selected_steps)
            self.assertEqual(1, by_id.skipped_steps)
            self.assertEqual(1, by_index.selected_steps)
            self.assertEqual(1, by_index.skipped_steps)
            self.assertEqual(2, by_range.selected_steps)
            self.assertEqual(2, by_range.skipped_steps)


if __name__ == "__main__":
    unittest.main()
