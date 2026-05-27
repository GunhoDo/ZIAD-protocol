import csv
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

from experiments import (
    paper_candidate,
    run_p0_execution_plan,
    run_paper_candidate_step,
    summarize_paper_candidate_baselines,
    summarize_paper_candidate_categories,
)


class PaperCandidatePlanTest(unittest.TestCase):
    def test_build_manifest_defines_candidate_outputs_and_settings(self):
        manifest = paper_candidate.build_manifest(
            Path("experiments/configs/paper_candidate/compact.yaml")
        )

        self.assertEqual("paper_candidate_skeleton_ready", manifest["status"])
        self.assertEqual("paper_candidate", manifest["run_tier"])
        self.assertFalse(manifest["paper_allowed"])
        self.assertFalse(manifest["claim_allowed"])
        self.assertEqual("review_pending", manifest["review_status"])
        self.assertEqual(64, manifest["paper_candidate_stream_length"])
        self.assertEqual(0.1, manifest["patchcore_sampler_percentage"])
        self.assertEqual("category_shard", manifest["candidate_scope"])
        self.assertEqual(288, manifest["matrix_count"])
        self.assertEqual(3888, manifest["production_matrix_count"])
        self.assertEqual(24, manifest["step_count"])

        for step in manifest["steps"]:
            self.assertEqual("paper_candidate", step["run_tier"])
            self.assertEqual("paper_candidate", step["source_tier"])
            self.assertFalse(step["paper_allowed"])
            self.assertFalse(step["claim_allowed"])
            self.assertEqual("review_pending", step["review_status"])
            self.assertEqual(64, step["paper_candidate_stream_length"])
            self.assertEqual("category_shard", step["candidate_scope"])
            self.assertIn(step["category_count"], {12, 15})
            self.assertEqual(12, step["expected_category_shard_run_count"])
            for output in step["outputs"].values():
                self.assertTrue(output.startswith("results/latest/paper_candidate/"))
                self.assertNotIn("results/latest/p0_full", output)

    def test_main_writes_manifest_and_execution_plan(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            manifest_path = root / "manifest.json"
            plan_path = root / "execution_plan.json"
            with mock.patch(
                "sys.argv",
                [
                    "paper_candidate.py",
                    "--config",
                    "experiments/configs/paper_candidate/compact.yaml",
                    "--manifest",
                    str(manifest_path),
                    "--execution-plan",
                    str(plan_path),
                ],
            ):
                paper_candidate.main()

            manifest = json.loads(manifest_path.read_text())
            plan = json.loads(plan_path.read_text())
            self.assertEqual(288, manifest["matrix_count"])
            self.assertEqual(3888, manifest["production_matrix_count"])
            self.assertEqual(24, plan["step_count"])
            self.assertFalse(plan["paper_allowed"])
            self.assertFalse(plan["claim_allowed"])
            self.assertEqual("review_pending", plan["review_status"])


class PaperCandidateStepTest(unittest.TestCase):
    def _selected_step(self, *, category="bottle", output_root=None):
        plan = paper_candidate.build_execution_plan(
            Path("experiments/configs/paper_candidate/compact.yaml")
        )
        _, step = run_paper_candidate_step.run_p0_full_step.resolve_step(
            plan,
            "mvtec_ad:winclip:default_no_memory:none",
        )
        selected = run_paper_candidate_step.prepare_category_shard_step(
            step,
            category=category,
            output_root=output_root,
        )
        return plan, selected

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

    def test_category_shard_output_path_validation(self):
        plan = paper_candidate.build_execution_plan(
            Path("experiments/configs/paper_candidate/compact.yaml")
        )
        _, step = run_paper_candidate_step.run_p0_full_step.resolve_step(
            plan,
            "mvtec_ad:winclip:default_no_memory:none",
        )
        selected = run_paper_candidate_step.prepare_category_shard_step(
            step,
            category="bottle",
        )
        self.assertTrue(selected["output_root"].endswith("/none/bottle"))
        self.assertEqual(["bottle"], selected["categories"])
        self.assertEqual(1, selected["category_count"])
        self.assertEqual(12, selected["expected_full_run_count"])

        with self.assertRaises(run_paper_candidate_step.PaperCandidateStepError):
            run_paper_candidate_step.prepare_category_shard_step(
                step,
                category="bottle",
                output_root=Path("results/latest/paper_candidate/missing_category"),
            )

    def test_paper_candidate_category_shard_writes_metadata_and_candidate_status(self):
        output_root = Path(
            "results/latest/paper_candidate/unit_test_winclip/default_no_memory/none/bottle"
        )
        if output_root.exists():
            shutil.rmtree(output_root)
        plan, step = self._selected_step(category="bottle")
        step["output_root"] = str(output_root)
        step["outputs"] = run_paper_candidate_step._step_outputs(output_root)
        plan = dict(plan)
        plan["steps"] = [step]
        try:
            _, selected = run_paper_candidate_step.run_step(
                plan,
                selector=step["step_id"],
                category="bottle",
                output_root=output_root,
                command_runner=self._fake_step_runner,
            )
            run_paper_candidate_step.verify_completed_step(selected)

            manifest = json.loads(Path(step["outputs"]["aggregate_manifest"]).read_text())
            self.assertEqual("paper_candidate", manifest["run_tier"])
            self.assertEqual("production", manifest["execution_mode"])
            self.assertFalse(manifest["paper_allowed"])
            self.assertFalse(manifest["claim_allowed"])
            self.assertEqual("review_pending", manifest["review_status"])
            self.assertEqual(64, manifest["paper_candidate_stream_length"])
            self.assertEqual("category_shard", manifest["candidate_scope"])
            self.assertEqual("bottle", manifest["category"])
            self.assertEqual([0, 1, 2], manifest["seeds"])
            self.assertEqual(1, manifest["category_count"])
            self.assertEqual(15, manifest["full_p0_category_count"])
            self.assertEqual(12, manifest["run_count"])

            with Path(step["outputs"]["aggregate_metrics"]).open() as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(12, len(rows))
            self.assertEqual({"measured_paper_candidate"}, {row["status"] for row in rows})

            summary = run_p0_execution_plan.run_execution_plan(plan, dry_run=True)
            self.assertEqual(1, summary.skipped_steps)
            self.assertEqual(0, summary.pending_steps)

            with self.assertRaises(run_paper_candidate_step.PaperCandidateStepError):
                run_paper_candidate_step.verify_full_category_candidate(selected)
        finally:
            if output_root.exists():
                shutil.rmtree(output_root)

    def test_completed_category_shard_skips(self):
        output_root = Path(
            "results/latest/paper_candidate/unit_test_winclip/default_no_memory/none/cable"
        )
        if output_root.exists():
            shutil.rmtree(output_root)
        plan, step = self._selected_step(category="cable")
        step["output_root"] = str(output_root)
        step["outputs"] = run_paper_candidate_step._step_outputs(output_root)
        plan = dict(plan)
        plan["steps"] = [step]
        try:
            run_paper_candidate_step.run_step(
                plan,
                selector=step["step_id"],
                category="cable",
                output_root=output_root,
                command_runner=self._fake_step_runner,
            )

            def fail_runner(command):
                raise AssertionError(f"runner should not be called: {command}")

            _, selected = run_paper_candidate_step.run_step(
                plan,
                selector=step["step_id"],
                category="cable",
                output_root=output_root,
                command_runner=fail_runner,
            )
            self.assertEqual("cable", selected["category"])
        finally:
            if output_root.exists():
                shutil.rmtree(output_root)

    def test_stale_partial_category_shard_fails_closed(self):
        output_root = Path(
            "results/latest/paper_candidate/unit_test_winclip/default_no_memory/none/grid"
        )
        if output_root.exists():
            shutil.rmtree(output_root)
        plan, step = self._selected_step(category="grid")
        step["output_root"] = str(output_root)
        step["outputs"] = run_paper_candidate_step._step_outputs(output_root)
        plan = dict(plan)
        plan["steps"] = [step]
        try:
            (output_root / "production_runs" / "stale").mkdir(parents=True)
            with self.assertRaises(run_paper_candidate_step.PaperCandidateStepError):
                run_paper_candidate_step.run_step(
                    plan,
                    selector=step["step_id"],
                    category="grid",
                    output_root=output_root,
                    command_runner=self._fake_step_runner,
                )
        finally:
            if output_root.exists():
                shutil.rmtree(output_root)


class PaperCandidateCategorySummaryTest(unittest.TestCase):
    def test_summary_reports_complete_and_pending_category_shards(self):
        output_root = Path("results/latest/paper_candidate/unit_test_summary/none")
        if output_root.exists():
            shutil.rmtree(output_root)
        plan = paper_candidate.build_execution_plan(
            Path("experiments/configs/paper_candidate/compact.yaml")
        )
        _, step = run_paper_candidate_step.run_p0_full_step.resolve_step(
            plan,
            "mvtec_ad:winclip:default_no_memory:none",
        )
        step = dict(step)
        step["output_root"] = str(output_root)
        plan = dict(plan)
        plan["steps"] = [step]

        cable_root = output_root / "cable"
        cable_root.mkdir(parents=True)
        (cable_root / "metrics.csv").write_text(
            "status\n" + "\n".join(["measured_paper_candidate"] * 12) + "\n"
        )
        (cable_root / "crd_lite.csv").write_text("category,crd_lite\ncable,0\n")
        (cable_root / "manifest.json").write_text(
            json.dumps(
                {
                    "candidate_scope": "category_shard",
                    "category": "cable",
                    "category_count": 1,
                    "stream_length": 64,
                    "seeds": [0, 1, 2],
                    "paper_allowed": False,
                    "claim_allowed": False,
                    "review_status": "review_pending",
                }
            )
        )
        try:
            summary = summarize_paper_candidate_categories.summarize_step(
                plan,
                "mvtec_ad:winclip:default_no_memory:none",
            )
            self.assertEqual("category_shards_incomplete", summary["status"])
            self.assertEqual(15, summary["category_count"])
            self.assertEqual(1, summary["complete_category_count"])
            self.assertEqual(14, summary["pending_category_count"])
            csv_path, json_path = summarize_paper_candidate_categories.write_summary(
                summary,
                output_root,
            )
            self.assertTrue(csv_path.exists())
            self.assertTrue(json_path.exists())
        finally:
            if output_root.exists():
                shutil.rmtree(output_root)


class PaperCandidateBaselineComparisonTest(unittest.TestCase):
    def test_baseline_comparison_summarizes_completed_category_sets(self):
        root = Path("results/latest/paper_candidate/unit_test_baseline_compare")
        if root.exists():
            shutil.rmtree(root)
        baselines = [
            ("winclip", "default_no_memory", "default/no-memory", "WinCLIP", 0.9, 0.8),
            ("anomalyclip", "default_no_memory", "default/no-memory", "AnomalyCLIP", 0.7, 0.6),
            ("rareclip", "default_scs", "default/SCS", "RareCLIP", 0.5, 0.4),
        ]
        try:
            for slug, memory_policy_slug, memory_policy, baseline, auroc, aupr in baselines:
                category_root = root / slug / memory_policy_slug / "none" / "bottle"
                category_root.mkdir(parents=True)
                metrics_path = category_root / "metrics.csv"
                metrics_path.write_text(
                    "dataset,stream_type,prevalence,contamination_epsilon,baseline,"
                    "memory_policy,calibration,image_auroc,aupr,ece,latency_ms,"
                    "crd_lite,status,category\n"
                    f"MVTec AD,iid,0.05,0,{baseline},{memory_policy},none,"
                    f"{auroc},{aupr},0.1,10,0.2,measured_paper_candidate,bottle\n"
                    f"MVTec AD,bursty,0.05,0.05,{baseline},{memory_policy},none,"
                    f"{auroc + 0.1},{aupr + 0.1},0.3,20,NA,measured_paper_candidate,bottle\n"
                )
                (category_root / "manifest.json").write_text("{}\n")
                (category_root / "crd_lite.csv").write_text("category,crd_lite\nbottle,0.2\n")
                summary_root = root / slug / memory_policy_slug / "none"
                (summary_root / "category_summary.json").write_text(
                    json.dumps(
                        {
                            "status": "category_shards_complete",
                            "dataset": "MVTec AD",
                            "baseline": baseline,
                            "memory_policy": memory_policy,
                            "calibration": "none",
                            "category_count": 1,
                            "complete_category_count": 1,
                            "paper_allowed": False,
                            "claim_allowed": False,
                            "review_status": "review_pending",
                            "categories": [
                                {
                                    "category": "bottle",
                                    "complete": True,
                                    "row_count": 2,
                                    "stream_length": 64,
                                    "seeds": [0, 1, 2],
                                    "metrics_csv": str(metrics_path),
                                }
                            ],
                        }
                    )
                    + "\n"
                )

            summary = summarize_paper_candidate_baselines.summarize_baselines(
                input_root=root,
            )
            self.assertEqual("paper_candidate_baseline_comparison_complete", summary["status"])
            self.assertEqual(3, summary["baseline_count"])
            self.assertFalse(summary["paper_allowed"])
            self.assertFalse(summary["claim_allowed"])
            self.assertEqual("review_pending", summary["review_status"])
            self.assertEqual(
                ["WinCLIP", "AnomalyCLIP", "RareCLIP"],
                [row["baseline"] for row in summary["baselines"]],
            )
            first = summary["baselines"][0]
            self.assertEqual("WinCLIP", first["baseline"])
            self.assertEqual(1, first["completed_categories"])
            self.assertEqual(2, first["total_rows"])
            self.assertEqual("64", first["stream_length"])
            self.assertEqual("0|1|2", first["seeds"])
            self.assertAlmostEqual(0.95, first["mean_image_auroc"])
            self.assertAlmostEqual(0.85, first["mean_aupr"])
            self.assertAlmostEqual(0.2, first["mean_ece"])
            self.assertAlmostEqual(15.0, first["mean_latency_ms"])
            self.assertAlmostEqual(0.2, first["mean_crd_lite"])

            csv_path, json_path, tex_path = summarize_paper_candidate_baselines.write_outputs(
                summary,
                csv_path=root / "baseline_comparison_none.csv",
                json_path=root / "baseline_comparison_none.json",
                tex_path=root / "baseline_comparison_none.tex",
            )
            self.assertTrue(csv_path.exists())
            self.assertTrue(json_path.exists())
            self.assertTrue(tex_path.exists())
        finally:
            if root.exists():
                shutil.rmtree(root)


if __name__ == "__main__":
    unittest.main()
