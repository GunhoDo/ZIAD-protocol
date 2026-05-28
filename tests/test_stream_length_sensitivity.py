import csv
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

from experiments import (
    run_stream_length_sensitivity_step,
    stream_length_sensitivity,
    summarize_stream_length_sensitivity,
)


class StreamLengthSensitivityPlanTest(unittest.TestCase):
    def test_build_plan_defines_compact_appendix_scope(self):
        manifest = stream_length_sensitivity.build_manifest()
        plan = stream_length_sensitivity.build_execution_plan()

        self.assertEqual("stream_length_sensitivity_manifest_ready", manifest["status"])
        self.assertEqual("stream_length_sensitivity", manifest["run_tier"])
        self.assertEqual("appendix_sanity_check", manifest["evidence_scope"])
        self.assertFalse(manifest["paper_allowed"])
        self.assertFalse(manifest["claim_allowed"])
        self.assertEqual("review_pending", manifest["review_status"])
        self.assertEqual(["PatchCore", "WinCLIP"], manifest["baselines"])
        self.assertEqual(["bottle", "cable", "capsule"], manifest["categories"])
        self.assertEqual([64, 128, 256], manifest["stream_lengths"])
        self.assertEqual(18, manifest["step_count"])
        self.assertEqual(216, manifest["row_count_if_complete"])
        self.assertEqual(12, manifest["expected_rows_per_step"])
        self.assertEqual(18, plan["step_count"])

        for step in plan["steps"]:
            self.assertEqual("stream_length_sensitivity", step["run_tier"])
            self.assertEqual("appendix_sanity_check", step["evidence_scope"])
            self.assertFalse(step["paper_allowed"])
            self.assertFalse(step["claim_allowed"])
            self.assertEqual("review_pending", step["review_status"])
            self.assertTrue(step["output_root"].startswith("results/latest/sensitivity/stream_length/"))
            self.assertEqual(1, step["category_count"])
            self.assertEqual(12, step["expected_full_run_count"])
            for output in step["outputs"].values():
                self.assertTrue(output.startswith("results/latest/sensitivity/stream_length/"))

    def test_main_writes_manifest_and_execution_plan(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            manifest_path = root / "manifest.json"
            plan_path = root / "execution_plan.json"
            with mock.patch(
                "sys.argv",
                [
                    "stream_length_sensitivity.py",
                    "--manifest",
                    str(manifest_path),
                    "--execution-plan",
                    str(plan_path),
                ],
            ):
                stream_length_sensitivity.main()

            manifest = json.loads(manifest_path.read_text())
            plan = json.loads(plan_path.read_text())
            self.assertEqual(18, manifest["step_count"])
            self.assertEqual(216, manifest["row_count_if_complete"])
            self.assertEqual(18, plan["step_count"])
            self.assertFalse(plan["paper_allowed"])
            self.assertFalse(plan["claim_allowed"])


class StreamLengthSensitivityRunnerTest(unittest.TestCase):
    def _selected_step(self, *, selector="mvtec_ad:winclip:default_no_memory:none:bottle:len_128"):
        plan = stream_length_sensitivity.build_execution_plan()
        _, step = run_stream_length_sensitivity_step.run_p0_full_step.resolve_step(
            plan,
            selector,
        )
        return plan, dict(step)

    def _fake_step_runner(self, command):
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
                "dataset,stream_type,prevalence,contamination_epsilon,baseline,memory_policy,"
                "calibration,image_auroc,aupr,ece,latency_ms,crd_lite,status\n"
                f"{latest_run['dataset']},{latest_run['stream_type']},{latest_run['prevalence']},"
                f"{latest_run['contamination_epsilon']},{latest_run['baseline']},"
                f"{latest_run['memory_policy']},{latest_run['calibration']},"
                "1.000000,1.000000,0.000000,1.000000,NA,measured_smoke\n"
            )
            manifest_path.write_text(json.dumps({"paper_allowed": False}))
            return 0
        return 99

    def test_dry_run_creates_no_outputs(self):
        output_root = Path(
            "results/latest/sensitivity/stream_length/mvtec_ad/winclip/default_no_memory/none/bottle/len_128"
        )
        if output_root.exists():
            shutil.rmtree(output_root)
        plan, step = self._selected_step()
        _, selected = run_stream_length_sensitivity_step.run_step(
            plan,
            selector=step["step_id"],
            dry_run=True,
        )
        self.assertEqual(step["step_id"], selected["step_id"])
        self.assertFalse(output_root.exists())

    def test_mocked_run_writes_closed_gate_sensitivity_outputs_and_skips(self):
        output_root = Path(
            "results/latest/sensitivity/stream_length/unit_test/winclip/default_no_memory/none/bottle/len_128"
        )
        if output_root.exists():
            shutil.rmtree(output_root)
        plan, step = self._selected_step()
        step["output_root"] = str(output_root)
        step["outputs"] = {
            "aggregate_metrics": str(output_root / "metrics.csv"),
            "aggregate_manifest": str(output_root / "manifest.json"),
            "crd_lite_summary": str(output_root / "crd_lite.csv"),
        }
        plan = dict(plan)
        plan["steps"] = [step]
        try:
            run_stream_length_sensitivity_step.run_step(
                plan,
                selector=step["step_id"],
                command_runner=self._fake_step_runner,
            )
            run_stream_length_sensitivity_step.verify_completed_step(step)

            manifest = json.loads(Path(step["outputs"]["aggregate_manifest"]).read_text())
            self.assertEqual("stream_length_sensitivity", manifest["run_tier"])
            self.assertEqual("production", manifest["execution_mode"])
            self.assertEqual("appendix_sanity_check", manifest["evidence_scope"])
            self.assertFalse(manifest["paper_allowed"])
            self.assertFalse(manifest["claim_allowed"])
            self.assertEqual("review_pending", manifest["review_status"])
            self.assertEqual("bottle", manifest["category"])
            self.assertEqual(128, manifest["stream_length"])
            self.assertEqual(12, manifest["run_count"])

            with Path(step["outputs"]["aggregate_metrics"]).open(newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(12, len(rows))
            self.assertEqual(
                {"measured_stream_length_sensitivity"},
                {row["status"] for row in rows},
            )

            def fail_runner(command):
                raise AssertionError(f"runner should not be called: {command}")

            run_stream_length_sensitivity_step.run_step(
                plan,
                selector=step["step_id"],
                command_runner=fail_runner,
            )
        finally:
            if output_root.exists():
                shutil.rmtree(output_root)

    def test_stale_partial_output_fails_closed(self):
        output_root = Path(
            "results/latest/sensitivity/stream_length/unit_test_partial/winclip/default_no_memory/none/bottle/len_128"
        )
        if output_root.exists():
            shutil.rmtree(output_root)
        plan, step = self._selected_step()
        step["output_root"] = str(output_root)
        step["outputs"] = {
            "aggregate_metrics": str(output_root / "metrics.csv"),
            "aggregate_manifest": str(output_root / "manifest.json"),
            "crd_lite_summary": str(output_root / "crd_lite.csv"),
        }
        plan = dict(plan)
        plan["steps"] = [step]
        try:
            (output_root / "production_runs" / "stale").mkdir(parents=True)
            with self.assertRaises(run_stream_length_sensitivity_step.StreamLengthSensitivityError):
                run_stream_length_sensitivity_step.run_step(
                    plan,
                    selector=step["step_id"],
                    command_runner=self._fake_step_runner,
                )
        finally:
            if output_root.exists():
                shutil.rmtree(output_root)


class StreamLengthSensitivitySummaryTest(unittest.TestCase):
    def test_summary_groups_completed_shards_by_baseline_and_length(self):
        root = Path("results/latest/sensitivity/stream_length/unit_test_summary")
        if root.exists():
            shutil.rmtree(root)
        try:
            shard_root = root / "mvtec_ad" / "winclip" / "default_no_memory" / "none" / "bottle" / "len_128"
            shard_root.mkdir(parents=True)
            metrics_path = shard_root / "metrics.csv"
            metrics_path.write_text(
                "dataset,baseline,memory_policy,calibration,image_auroc,aupr,ece,latency_ms,crd_lite,status\n"
                "MVTec AD,WinCLIP,default/no-memory,none,0.8,0.7,0.1,5.0,0.01,measured_stream_length_sensitivity\n"
                "MVTec AD,WinCLIP,default/no-memory,none,0.9,0.8,0.2,7.0,0.03,measured_stream_length_sensitivity\n"
            )
            (shard_root / "crd_lite.csv").write_text("category,crd_lite\nbottle,0.02\n")
            (shard_root / "manifest.json").write_text(
                json.dumps(
                    {
                        "status": "measured_stream_length_sensitivity_complete",
                        "run_tier": "stream_length_sensitivity",
                        "evidence_scope": "appendix_sanity_check",
                        "dataset": "MVTec AD",
                        "baseline": "WinCLIP",
                        "memory_policy": "default/no-memory",
                        "calibration": "none",
                        "category": "bottle",
                        "stream_length": 128,
                        "run_count": 2,
                        "expected_full_run_count": 2,
                        "aggregate_metrics": str(metrics_path),
                        "paper_allowed": False,
                        "claim_allowed": False,
                        "review_status": "review_pending",
                    }
                )
                + "\n"
            )
            summary = summarize_stream_length_sensitivity.summarize(root)
            self.assertEqual("stream_length_sensitivity_summary_complete", summary["status"])
            self.assertEqual(1, summary["group_count"])
            row = summary["rows"][0]
            self.assertEqual("MVTec AD", row["dataset"])
            self.assertEqual("WinCLIP", row["baseline"])
            self.assertEqual(128, row["stream_length"])
            self.assertEqual(1, row["completed_categories"])
            self.assertEqual(2, row["total_rows"])
            self.assertAlmostEqual(0.85, row["mean_image_auroc"])
            self.assertAlmostEqual(6.0, row["mean_latency_ms"])
            csv_path, json_path, tex_path = summarize_stream_length_sensitivity.write_outputs(
                summary,
                csv_path=root / "summary.csv",
                json_path=root / "summary.json",
                tex_path=root / "summary.tex",
            )
            self.assertTrue(csv_path.exists())
            self.assertTrue(json_path.exists())
            self.assertTrue(tex_path.exists())
        finally:
            if root.exists():
                shutil.rmtree(root)

    def test_empty_summary_still_writes_placeholder_table(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            summary = summarize_stream_length_sensitivity.summarize(root)
            self.assertEqual("stream_length_sensitivity_summary_empty", summary["status"])
            csv_path, json_path, tex_path = summarize_stream_length_sensitivity.write_outputs(
                summary,
                csv_path=root / "summary.csv",
                json_path=root / "summary.json",
                tex_path=root / "summary.tex",
            )
            self.assertTrue(csv_path.exists())
            self.assertTrue(json_path.exists())
            self.assertIn("Pending", tex_path.read_text())


if __name__ == "__main__":
    unittest.main()
