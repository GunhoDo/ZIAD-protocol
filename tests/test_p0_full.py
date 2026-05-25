import csv
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

from experiments import p0_full, run_p0_execution_plan, run_p0_full_step


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
        self.assertEqual(3888, manifest["production_matrix_count"])
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
            self.assertEqual(12, step["expected_lightweight_run_count"])
            if step["dataset"] == "MVTec AD":
                self.assertEqual(15, step["category_count"])
                self.assertEqual(180, step["expected_full_run_count"])
            if step["dataset"] == "VisA":
                self.assertEqual(12, step["category_count"])
                self.assertEqual(144, step["expected_full_run_count"])
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
        plan = dict(plan)
        plan["steps"] = [dict(step) for step in plan["steps"]]
        for index, step in enumerate(plan["steps"]):
            root = Path("results/latest/p0_full/unit_test_missing_all") / str(index)
            step["output_root"] = str(root)
            step["outputs"] = {
                "aggregate_metrics": str(root / "metrics.csv"),
                "aggregate_manifest": str(root / "manifest.json"),
                "crd_lite_summary": str(root / "crd_lite.csv"),
            }
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


class P0FullStepExecutorTest(unittest.TestCase):
    def _plan(self):
        return p0_full.build_execution_plan(Path("experiments/configs/p0_full/compact.yaml"))

    def _fake_full_step_runner(self, command):
        if command[:2] == ["bash", "scripts/run_smoke.sh"]:
            cfg = yaml.safe_load(Path(command[2]).read_text())
            outputs = cfg["outputs"]
            scores_path = Path(outputs["scores_csv"])
            latest_run_path = Path(outputs["latest_run"])
            manifest_path = Path(outputs["manifest"])
            scores_path.parent.mkdir(parents=True, exist_ok=True)
            scores_path.write_text(
                "stream_index,image_path,label,category,anomaly_score,latency_ms,peak_vram_mb,status\n"
                f"0,{cfg['category']}/good.png,0,{cfg['category']},0.1,1,0,measured\n"
                f"1,{cfg['category']}/bad.png,1,{cfg['category']},0.9,1,0,measured\n"
            )
            latest_run_path.write_text(
                json.dumps(
                    {
                        "dataset": cfg["dataset"],
                        "stream_type": cfg["stream_type"],
                        "prevalence": cfg["prevalence"],
                        "contamination_epsilon": cfg["contamination_epsilon"],
                        "baseline": cfg["baseline"],
                        "memory_policy": cfg["memory_policy"],
                        "calibration": cfg["calibration"],
                        "paper_allowed": False,
                    }
                )
            )
            manifest_path.write_text(json.dumps({"paper_allowed": False}))
            return 0
        if command[:2] == ["python3", "experiments/evaluate.py"]:
            args = {command[i]: command[i + 1] for i in range(2, len(command), 2)}
            latest_run = json.loads(Path(args["--latest-run"]).read_text())
            metrics_path = Path(args["--output"])
            manifest_path = Path(args["--manifest"])
            metrics_path.write_text(
                "dataset,stream_type,prevalence,contamination_epsilon,baseline,memory_policy,calibration,"
                "image_auroc,aupr,ece,latency_ms,crd_lite,status\n"
                f"{latest_run['dataset']},{latest_run['stream_type']},{latest_run['prevalence']},"
                f"{latest_run['contamination_epsilon']},{latest_run['baseline']},"
                f"{latest_run['memory_policy']},{latest_run['calibration']},"
                "1.000000,1.000000,0.000000,1.000000,NA,measured_smoke\n"
            )
            manifest_path.write_text(json.dumps({"paper_allowed": False}))
            return 0
        return 99

    def test_selected_step_is_resolved_by_id_and_index(self):
        plan = self._plan()

        index, by_index = run_p0_full_step.resolve_step(plan, "0")
        by_id_index, by_id = run_p0_full_step.resolve_step(plan, by_index["step_id"])

        self.assertEqual(0, index)
        self.assertEqual(0, by_id_index)
        self.assertEqual(by_index["step_id"], by_id["step_id"])

    def test_output_root_is_under_p0_full(self):
        plan = self._plan()
        _, step = run_p0_full_step.resolve_step(plan, "0")

        run_p0_full_step.validate_step_contract(
            step,
            output_root=Path(step["output_root"]),
        )

        for output in step["outputs"].values():
            self.assertTrue(output.startswith("results/latest/p0_full/"))

    def test_smoke_output_paths_are_rejected(self):
        plan = self._plan()
        _, step = run_p0_full_step.resolve_step(plan, "0")
        step = dict(step)
        step["outputs"] = dict(step["outputs"])
        step["outputs"]["aggregate_metrics"] = "results/latest/p0_shards/metrics.csv"

        with self.assertRaisesRegex(run_p0_full_step.FullP0StepError, "outside"):
            run_p0_full_step.validate_step_contract(step)

    def test_metadata_fields_are_enforced(self):
        plan = self._plan()
        _, step = run_p0_full_step.resolve_step(plan, "0")

        manifest = run_p0_full_step.build_manifest_metadata(step)
        latest_run = run_p0_full_step.build_latest_run_metadata(step)

        for payload in [manifest, latest_run]:
            self.assertEqual("p0_full", payload["run_tier"])
            self.assertFalse(payload["paper_allowed"])
            self.assertFalse(payload["claim_allowed"])
            self.assertEqual("not_reviewed", payload["review_status"])

        bad_step = dict(step)
        bad_step["paper_allowed"] = True
        with self.assertRaisesRegex(run_p0_full_step.FullP0StepError, "paper_allowed"):
            run_p0_full_step.validate_step_contract(bad_step)

    def test_dry_run_creates_no_outputs(self):
        plan = self._plan()
        _, step = run_p0_full_step.resolve_step(plan, "0")
        output_paths = [Path(value) for value in step["outputs"].values()]
        for path in output_paths:
            self.assertFalse(path.exists())

        index, selected = run_p0_full_step.run_step(plan, selector="0", dry_run=True)

        self.assertEqual(0, index)
        self.assertEqual(step["step_id"], selected["step_id"])
        for path in output_paths:
            self.assertFalse(path.exists())

    def test_missing_unknown_step_fails_clearly(self):
        plan = self._plan()

        with self.assertRaisesRegex(run_p0_full_step.FullP0StepError, "Unknown"):
            run_p0_full_step.resolve_step(plan, "missing:step")
        with self.assertRaisesRegex(run_p0_full_step.FullP0StepError, "out of range"):
            run_p0_full_step.resolve_step(plan, "999")

    def test_non_dry_run_refuses_smoke_output_roots(self):
        plan = self._plan()
        _, step = run_p0_full_step.resolve_step(plan, "0")

        with self.assertRaisesRegex(run_p0_full_step.FullP0StepError, "outside"):
            run_p0_full_step.run_step(
                plan,
                selector=step["step_id"],
                output_root=Path("results/latest/p0_shards/not_allowed"),
                validation_mode="lightweight",
                command_runner=lambda command: 0,
            )

    def test_lightweight_run_writes_metadata_but_production_dry_run_stays_pending(self):
        plan = self._plan()
        _, step = run_p0_full_step.resolve_step(plan, "4")
        output_root = Path("results/latest/p0_full/unit_test_winclip_step")
        if output_root.exists():
            shutil.rmtree(output_root)
        step = dict(step)
        step["output_root"] = str(output_root)
        step["outputs"] = {
            "aggregate_metrics": str(output_root / "metrics.csv"),
            "aggregate_manifest": str(output_root / "manifest.json"),
            "crd_lite_summary": str(output_root / "crd_lite.csv"),
        }
        plan = dict(plan)
        plan["steps"] = [step]

        try:
            index, selected = run_p0_full_step.run_step(
                plan,
                selector=step["step_id"],
                output_root=output_root,
                validation_mode="lightweight",
                command_runner=self._fake_full_step_runner,
            )
            self.assertEqual(0, index)
            self.assertEqual(step["step_id"], selected["step_id"])

            manifest = json.loads(Path(step["outputs"]["aggregate_manifest"]).read_text())
            self.assertEqual("p0_full", manifest["run_tier"])
            self.assertFalse(manifest["paper_allowed"])
            self.assertFalse(manifest["claim_allowed"])
            self.assertEqual("not_reviewed", manifest["review_status"])
            self.assertEqual(12, manifest["run_count"])

            summary = run_p0_execution_plan.run_execution_plan(plan, dry_run=True)
            self.assertEqual(0, summary.skipped_steps)
            self.assertEqual(1, summary.pending_steps)
            self.assertEqual(1, summary.dry_run_steps)
        finally:
            if output_root.exists():
                shutil.rmtree(output_root)

    def test_production_run_writes_category_complete_outputs_and_skips(self):
        plan = self._plan()
        _, step = run_p0_full_step.resolve_step(plan, "4")
        output_root = Path("results/latest/p0_full/unit_test_production_execution")
        if output_root.exists():
            shutil.rmtree(output_root)
        step = dict(step)
        step["output_root"] = str(output_root)
        step["outputs"] = {
            "aggregate_metrics": str(output_root / "metrics.csv"),
            "aggregate_manifest": str(output_root / "manifest.json"),
            "crd_lite_summary": str(output_root / "crd_lite.csv"),
        }
        plan = dict(plan)
        plan["steps"] = [step]
        try:
            index, selected = run_p0_full_step.run_step(
                plan,
                selector=step["step_id"],
                output_root=output_root,
                command_runner=self._fake_full_step_runner,
            )
            run_p0_full_step.verify_completed_step(selected)
            self.assertEqual(0, index)

            manifest = json.loads(Path(step["outputs"]["aggregate_manifest"]).read_text())
            self.assertEqual("production", manifest["execution_mode"])
            self.assertEqual("p0_full", manifest["run_tier"])
            self.assertFalse(manifest["paper_allowed"])
            self.assertFalse(manifest["claim_allowed"])
            self.assertEqual("not_reviewed", manifest["review_status"])
            self.assertEqual(15, manifest["category_count"])
            self.assertEqual(180, manifest["run_count"])

            with Path(step["outputs"]["aggregate_metrics"]).open() as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(180, len(rows))
            self.assertEqual({"measured_full_p0"}, {row["status"] for row in rows})
            self.assertEqual(15, len({row["category"] for row in rows}))

            summary = run_p0_execution_plan.run_execution_plan(plan, dry_run=True)
            self.assertEqual(1, summary.skipped_steps)
            self.assertEqual(0, summary.pending_steps)
        finally:
            if output_root.exists():
                shutil.rmtree(output_root)

    def test_temperature_scaling_production_run_is_allowed(self):
        plan = self._plan()
        _, step = run_p0_full_step.resolve_step(
            plan,
            "mvtec_ad:winclip:default_no_memory:temperature_scaling",
        )
        output_root = Path("results/latest/p0_full/unit_test_production_temperature")
        if output_root.exists():
            shutil.rmtree(output_root)
        step = dict(step)
        step["output_root"] = str(output_root)
        step["outputs"] = {
            "aggregate_metrics": str(output_root / "metrics.csv"),
            "aggregate_manifest": str(output_root / "manifest.json"),
            "crd_lite_summary": str(output_root / "crd_lite.csv"),
        }
        plan = dict(plan)
        plan["steps"] = [step]
        try:
            _, selected = run_p0_full_step.run_step(
                plan,
                selector=step["step_id"],
                output_root=output_root,
                command_runner=self._fake_full_step_runner,
            )
            run_p0_full_step.verify_completed_step(selected)

            manifest = json.loads(Path(step["outputs"]["aggregate_manifest"]).read_text())
            self.assertEqual("production", manifest["execution_mode"])
            self.assertEqual("temperature_scaling", manifest["calibration"])
            self.assertEqual(180, manifest["run_count"])

            with Path(step["outputs"]["aggregate_metrics"]).open() as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(180, len(rows))
            self.assertEqual({"temperature_scaling"}, {row["calibration"] for row in rows})
        finally:
            if output_root.exists():
                shutil.rmtree(output_root)

    def test_visa_winclip_production_run_is_allowed(self):
        plan = self._plan()
        _, step = run_p0_full_step.resolve_step(
            plan,
            "visa:winclip:default_no_memory:none",
        )
        output_root = Path("results/latest/p0_full/unit_test_production_visa")
        if output_root.exists():
            shutil.rmtree(output_root)
        step = dict(step)
        step["output_root"] = str(output_root)
        step["outputs"] = {
            "aggregate_metrics": str(output_root / "metrics.csv"),
            "aggregate_manifest": str(output_root / "manifest.json"),
            "crd_lite_summary": str(output_root / "crd_lite.csv"),
        }
        plan = dict(plan)
        plan["steps"] = [step]
        try:
            _, selected = run_p0_full_step.run_step(
                plan,
                selector=step["step_id"],
                output_root=output_root,
                command_runner=self._fake_full_step_runner,
            )
            run_p0_full_step.verify_completed_step(selected)

            manifest = json.loads(Path(step["outputs"]["aggregate_manifest"]).read_text())
            self.assertEqual("production", manifest["execution_mode"])
            self.assertEqual("VisA", manifest["dataset"])
            self.assertEqual(12, manifest["category_count"])
            self.assertEqual(144, manifest["run_count"])

            with Path(step["outputs"]["aggregate_metrics"]).open() as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(144, len(rows))
            self.assertEqual(12, len({row["category"] for row in rows}))
        finally:
            if output_root.exists():
                shutil.rmtree(output_root)

    def test_visa_winclip_temperature_production_run_is_allowed(self):
        plan = self._plan()
        _, step = run_p0_full_step.resolve_step(
            plan,
            "visa:winclip:default_no_memory:temperature_scaling",
        )
        output_root = Path("results/latest/p0_full/unit_test_production_visa_temperature")
        if output_root.exists():
            shutil.rmtree(output_root)
        step = dict(step)
        step["output_root"] = str(output_root)
        step["outputs"] = {
            "aggregate_metrics": str(output_root / "metrics.csv"),
            "aggregate_manifest": str(output_root / "manifest.json"),
            "crd_lite_summary": str(output_root / "crd_lite.csv"),
        }
        plan = dict(plan)
        plan["steps"] = [step]
        try:
            _, selected = run_p0_full_step.run_step(
                plan,
                selector=step["step_id"],
                output_root=output_root,
                command_runner=self._fake_full_step_runner,
            )
            run_p0_full_step.verify_completed_step(selected)

            manifest = json.loads(Path(step["outputs"]["aggregate_manifest"]).read_text())
            self.assertEqual("production", manifest["execution_mode"])
            self.assertEqual("VisA", manifest["dataset"])
            self.assertEqual("temperature_scaling", manifest["calibration"])
            self.assertEqual(12, manifest["category_count"])
            self.assertEqual(144, manifest["run_count"])

            with Path(step["outputs"]["aggregate_metrics"]).open() as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(144, len(rows))
            self.assertEqual({"temperature_scaling"}, {row["calibration"] for row in rows})
            self.assertEqual(12, len({row["category"] for row in rows}))
        finally:
            if output_root.exists():
                shutil.rmtree(output_root)

    def test_anomalyclip_production_run_is_allowed(self):
        plan = self._plan()
        _, step = run_p0_full_step.resolve_step(
            plan,
            "mvtec_ad:anomalyclip:default_no_memory:none",
        )
        output_root = Path("results/latest/p0_full/unit_test_production_anomalyclip")
        if output_root.exists():
            shutil.rmtree(output_root)
        step = dict(step)
        step["output_root"] = str(output_root)
        step["outputs"] = {
            "aggregate_metrics": str(output_root / "metrics.csv"),
            "aggregate_manifest": str(output_root / "manifest.json"),
            "crd_lite_summary": str(output_root / "crd_lite.csv"),
        }
        plan = dict(plan)
        plan["steps"] = [step]
        try:
            _, selected = run_p0_full_step.run_step(
                plan,
                selector=step["step_id"],
                output_root=output_root,
                command_runner=self._fake_full_step_runner,
            )
            run_p0_full_step.verify_completed_step(selected)

            manifest = json.loads(Path(step["outputs"]["aggregate_manifest"]).read_text())
            self.assertEqual("production", manifest["execution_mode"])
            self.assertEqual("AnomalyCLIP", manifest["baseline"])
            self.assertEqual("none", manifest["calibration"])
            self.assertEqual("MVTec AD", manifest["dataset"])
            self.assertEqual(15, manifest["category_count"])
            self.assertEqual(180, manifest["run_count"])

            with Path(step["outputs"]["aggregate_metrics"]).open() as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(180, len(rows))
            self.assertEqual({"AnomalyCLIP"}, {row["baseline"] for row in rows})
            self.assertEqual({"none"}, {row["calibration"] for row in rows})
            self.assertEqual({"measured_full_p0"}, {row["status"] for row in rows})
            self.assertEqual(15, len({row["category"] for row in rows}))
        finally:
            if output_root.exists():
                shutil.rmtree(output_root)

    def test_production_run_is_guarded_to_selected_step(self):
        plan = self._plan()
        _, step = run_p0_full_step.resolve_step(plan, "0")

        with self.assertRaisesRegex(run_p0_full_step.FullP0StepError, "enabled only"):
            run_p0_full_step.run_step(
                plan,
                selector=step["step_id"],
                output_root=Path(step["output_root"]),
                command_runner=self._fake_full_step_runner,
            )

    def test_production_manifest_is_required_for_execution_plan_skip(self):
        plan = self._plan()
        _, step = run_p0_full_step.resolve_step(plan, "4")
        output_root = Path("results/latest/p0_full/unit_test_production_step")
        if output_root.exists():
            shutil.rmtree(output_root)
        step = dict(step)
        step["output_root"] = str(output_root)
        step["outputs"] = {
            "aggregate_metrics": str(output_root / "metrics.csv"),
            "aggregate_manifest": str(output_root / "manifest.json"),
            "crd_lite_summary": str(output_root / "crd_lite.csv"),
        }
        plan = dict(plan)
        plan["steps"] = [step]
        try:
            output_root.mkdir(parents=True)
            Path(step["outputs"]["aggregate_manifest"]).write_text(
                json.dumps(
                    {
                        "run_tier": "p0_full",
                        "paper_allowed": False,
                        "claim_allowed": False,
                        "review_status": "not_reviewed",
                        "execution_mode": "production",
                        "category_count": step["category_count"],
                    }
                )
            )
            Path(step["outputs"]["crd_lite_summary"]).write_text("status\nmeasured_full_p0\n")
            with Path(step["outputs"]["aggregate_metrics"]).open("w") as handle:
                handle.write("dataset,status\n")
                for _ in range(step["expected_full_run_count"]):
                    handle.write("MVTec AD,measured_full_p0\n")

            summary = run_p0_execution_plan.run_execution_plan(plan, dry_run=True)
            self.assertEqual(1, summary.skipped_steps)
            self.assertEqual(0, summary.pending_steps)
        finally:
            if output_root.exists():
                shutil.rmtree(output_root)

    def test_production_manifest_category_count_mismatch_fails_validation(self):
        plan = self._plan()
        _, step = run_p0_full_step.resolve_step(plan, "4")
        output_root = Path("results/latest/p0_full/unit_test_bad_category_count")
        if output_root.exists():
            shutil.rmtree(output_root)
        step = dict(step)
        step["output_root"] = str(output_root)
        step["outputs"] = {
            "aggregate_metrics": str(output_root / "metrics.csv"),
            "aggregate_manifest": str(output_root / "manifest.json"),
            "crd_lite_summary": str(output_root / "crd_lite.csv"),
        }
        try:
            output_root.mkdir(parents=True)
            Path(step["outputs"]["aggregate_manifest"]).write_text(
                json.dumps(
                    {
                        "paper_allowed": False,
                        "claim_allowed": False,
                        "execution_mode": "production",
                        "category_count": step["category_count"] - 1,
                    }
                )
            )
            Path(step["outputs"]["crd_lite_summary"]).write_text("status\nmeasured_full_p0\n")
            Path(step["outputs"]["aggregate_metrics"]).write_text("dataset,status\n")

            validation = run_p0_execution_plan.validate_step_outputs(step)
            self.assertFalse(validation.valid)
            self.assertTrue(any("category_count" in error for error in validation.errors))
        finally:
            if output_root.exists():
                shutil.rmtree(output_root)

    def test_failed_subprocess_stops_clearly(self):
        plan = self._plan()
        _, step = run_p0_full_step.resolve_step(plan, "4")
        output_root = Path("results/latest/p0_full/unit_test_failure_step")
        step = dict(step)
        step["output_root"] = str(output_root)
        step["outputs"] = {
            "aggregate_metrics": str(output_root / "metrics.csv"),
            "aggregate_manifest": str(output_root / "manifest.json"),
            "crd_lite_summary": str(output_root / "crd_lite.csv"),
        }
        plan = dict(plan)
        plan["steps"] = [step]

        try:
            with self.assertRaisesRegex(run_p0_full_step.FullP0StepError, "Command failed"):
                run_p0_full_step.run_step(
                    plan,
                    selector=step["step_id"],
                    output_root=output_root,
                    validation_mode="lightweight",
                    command_runner=lambda command: 7,
                )
        finally:
            if output_root.exists():
                shutil.rmtree(output_root)


if __name__ == "__main__":
    unittest.main()
