import csv
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

from experiments import (
    audit_paper_candidate_metrics,
    paper_candidate,
    render_paper_candidate_analysis,
    run_p0_execution_plan,
    run_paper_candidate_step,
    summarize_paper_candidate_all_datasets,
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
            ("patchcore", "default_scs", "default/SCS", "PatchCore", 0.3, 0.2),
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
            self.assertEqual("MVTec AD", summary["dataset"])
            self.assertEqual(4, summary["baseline_count"])
            self.assertFalse(summary["paper_allowed"])
            self.assertFalse(summary["claim_allowed"])
            self.assertEqual("review_pending", summary["review_status"])
            self.assertEqual(
                ["WinCLIP", "AnomalyCLIP", "RareCLIP", "PatchCore"],
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


class PaperCandidateCombinedComparisonTest(unittest.TestCase):
    def test_combined_comparison_ranks_each_dataset_and_keeps_gates_closed(self):
        root = Path("results/latest/paper_candidate/unit_test_combined_compare")
        if root.exists():
            shutil.rmtree(root)
        try:
            mvtec_csv = root / "mvtec_ad" / "baseline_comparison_none.csv"
            visa_csv = root / "visa" / "baseline_comparison_none.csv"
            header = ",".join(summarize_paper_candidate_all_datasets.OUTPUT_COLUMNS)
            mvtec_csv.parent.mkdir(parents=True)
            visa_csv.parent.mkdir(parents=True)
            mvtec_csv.write_text(
                header
                + "\n"
                + "MVTec AD,WinCLIP,default/no-memory,none,15,15,180,64,0|1|2,"
                "0.70,0.80,0.20,10.0,0.01,False,False,review_pending\n"
                + "MVTec AD,PatchCore,default/SCS,none,15,15,180,64,0|1|2,"
                "0.90,0.75,0.10,20.0,0.02,False,False,review_pending\n"
            )
            visa_csv.write_text(
                header
                + "\n"
                + "VisA,RareCLIP,default/SCS,none,12,12,144,64,0|1|2,"
                "0.85,0.60,0.30,30.0,0.03,False,False,review_pending\n"
                + "VisA,PatchCore,default/SCS,none,12,12,144,64,0|1|2,"
                "0.95,0.90,0.05,15.0,0.04,False,False,review_pending\n"
            )

            summary = summarize_paper_candidate_all_datasets.summarize_all_datasets(
                [mvtec_csv, visa_csv]
            )
            self.assertEqual(
                "paper_candidate_combined_baseline_comparison_complete",
                summary["status"],
            )
            self.assertEqual(["MVTec AD", "VisA"], summary["datasets"])
            self.assertEqual(4, summary["baseline_row_count"])
            self.assertFalse(summary["paper_allowed"])
            self.assertFalse(summary["claim_allowed"])
            self.assertEqual("review_pending", summary["review_status"])
            self.assertEqual(
                "PatchCore",
                summary["rankings"]["MVTec AD"]["best_auroc"]["baseline"],
            )
            self.assertEqual(
                "WinCLIP",
                summary["rankings"]["MVTec AD"]["lowest_latency"]["baseline"],
            )
            self.assertEqual(
                "PatchCore",
                summary["rankings"]["VisA"]["best_aupr"]["baseline"],
            )
            self.assertEqual(
                "PatchCore",
                summary["rankings"]["VisA"]["lowest_ece"]["baseline"],
            )
            self.assertIn("trade-off", summary["accuracy_latency_tradeoff_notes"][0])

            csv_path, json_path, tex_path = (
                summarize_paper_candidate_all_datasets.write_outputs(
                    summary,
                    csv_path=root / "combined.csv",
                    json_path=root / "combined.json",
                    tex_path=root / "combined.tex",
                )
            )
            self.assertTrue(csv_path.exists())
            self.assertTrue(json_path.exists())
            self.assertTrue(tex_path.exists())
        finally:
            if root.exists():
                shutil.rmtree(root)


class PaperCandidateMetricAuditTest(unittest.TestCase):
    def _write_combined_csv(self, path: Path, *, negative_latency: bool = False) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        rows = []
        for dataset, expected_categories, total_rows in [
            ("MVTec AD", 15, 180),
            ("VisA", 12, 144),
        ]:
            for baseline, memory_policy in [
                ("PatchCore", "default/SCS"),
                ("WinCLIP", "default/no-memory"),
                ("AnomalyCLIP", "default/no-memory"),
                ("RareCLIP", "default/SCS"),
            ]:
                latency = -1.0 if negative_latency and baseline == "WinCLIP" else 10.0
                rows.append(
                    {
                        "dataset": dataset,
                        "baseline": baseline,
                        "memory_policy": memory_policy,
                        "calibration": "none",
                        "completed_categories": str(expected_categories),
                        "expected_categories": str(expected_categories),
                        "total_rows": str(total_rows),
                        "stream_length": "64",
                        "seeds": "0|1|2",
                        "mean_image_auroc": "0.9",
                        "mean_aupr": "0.8",
                        "mean_ece": "0.1",
                        "mean_latency_ms": str(latency),
                        "mean_crd_lite": "0.01",
                        "paper_allowed": "False",
                        "claim_allowed": "False",
                        "review_status": "review_pending",
                    }
                )
        with path.open("w", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=audit_paper_candidate_metrics.REQUIRED_COLUMNS,
                lineterminator="\n",
            )
            writer.writeheader()
            writer.writerows(rows)

    def test_metric_audit_passes_closed_gate_combined_table(self):
        root = Path("results/latest/paper_candidate/unit_test_metric_audit")
        if root.exists():
            shutil.rmtree(root)
        try:
            csv_path = root / "combined.csv"
            self._write_combined_csv(csv_path)
            report = audit_paper_candidate_metrics.build_metric_audit(
                combined_csv=csv_path,
                category_summary_glob=None,
            )
            self.assertEqual("paper_candidate_metric_audit_passed", report["status"])
            self.assertEqual(8, report["combined_csv"]["row_count"])
            self.assertEqual(2, report["combined_csv"]["dataset_count"])
            self.assertFalse(report["paper_allowed"])
            self.assertFalse(report["claim_allowed"])
            self.assertEqual("review_pending", report["review_status"])
            json_path, tex_path = audit_paper_candidate_metrics.write_outputs(
                report,
                json_path=root / "metric_audit_report.json",
                tex_path=root / "metric_audit_summary.tex",
            )
            self.assertTrue(json_path.exists())
            self.assertTrue(tex_path.exists())
        finally:
            if root.exists():
                shutil.rmtree(root)

    def test_metric_audit_fails_negative_latency(self):
        root = Path("results/latest/paper_candidate/unit_test_metric_audit_fail")
        if root.exists():
            shutil.rmtree(root)
        try:
            csv_path = root / "combined.csv"
            self._write_combined_csv(csv_path, negative_latency=True)
            report = audit_paper_candidate_metrics.build_metric_audit(
                combined_csv=csv_path,
                category_summary_glob=None,
            )
            self.assertEqual("paper_candidate_metric_audit_failed", report["status"])
            self.assertEqual(2, report["combined_csv"]["negative_latency_count"])
            self.assertGreater(report["error_count"], 0)
        finally:
            if root.exists():
                shutil.rmtree(root)


class PaperCandidateAnalysisRenderTest(unittest.TestCase):
    def test_renders_ranking_summary_and_tradeoff_figure_with_closed_gates(self):
        root = Path("results/latest/paper_candidate/unit_test_analysis_render")
        if root.exists():
            shutil.rmtree(root)
        try:
            csv_path = root / "combined.csv"
            json_path = root / "combined.json"
            summary = {
                "status": "paper_candidate_combined_baseline_comparison_complete",
                "dataset_count": 2,
                "baseline_row_count": 4,
                "paper_allowed": False,
                "claim_allowed": False,
                "review_status": "review_pending",
                "accuracy_latency_tradeoff_notes": [
                    "MVTec AD: PatchCore leads AUROC, while WinCLIP has the lowest latency.",
                    "VisA: PatchCore leads AUROC and latency in this review-pending slice.",
                ],
            }
            rows = [
                {
                    "dataset": "MVTec AD",
                    "baseline": "WinCLIP",
                    "memory_policy": "default/no-memory",
                    "calibration": "none",
                    "completed_categories": "15",
                    "expected_categories": "15",
                    "total_rows": "180",
                    "stream_length": "64",
                    "seeds": "0|1|2",
                    "mean_image_auroc": "0.70",
                    "mean_aupr": "0.80",
                    "mean_ece": "0.20",
                    "mean_latency_ms": "10.0",
                    "mean_crd_lite": "0.01",
                    "paper_allowed": "False",
                    "claim_allowed": "False",
                    "review_status": "review_pending",
                },
                {
                    "dataset": "MVTec AD",
                    "baseline": "PatchCore",
                    "memory_policy": "default/SCS",
                    "calibration": "none",
                    "completed_categories": "15",
                    "expected_categories": "15",
                    "total_rows": "180",
                    "stream_length": "64",
                    "seeds": "0|1|2",
                    "mean_image_auroc": "0.90",
                    "mean_aupr": "0.75",
                    "mean_ece": "0.10",
                    "mean_latency_ms": "20.0",
                    "mean_crd_lite": "0.02",
                    "paper_allowed": "False",
                    "claim_allowed": "False",
                    "review_status": "review_pending",
                },
                {
                    "dataset": "VisA",
                    "baseline": "RareCLIP",
                    "memory_policy": "default/SCS",
                    "calibration": "none",
                    "completed_categories": "12",
                    "expected_categories": "12",
                    "total_rows": "144",
                    "stream_length": "64",
                    "seeds": "0|1|2",
                    "mean_image_auroc": "0.85",
                    "mean_aupr": "0.60",
                    "mean_ece": "0.30",
                    "mean_latency_ms": "30.0",
                    "mean_crd_lite": "0.03",
                    "paper_allowed": "False",
                    "claim_allowed": "False",
                    "review_status": "review_pending",
                },
                {
                    "dataset": "VisA",
                    "baseline": "PatchCore",
                    "memory_policy": "default/SCS",
                    "calibration": "none",
                    "completed_categories": "12",
                    "expected_categories": "12",
                    "total_rows": "144",
                    "stream_length": "64",
                    "seeds": "0|1|2",
                    "mean_image_auroc": "0.95",
                    "mean_aupr": "0.90",
                    "mean_ece": "0.05",
                    "mean_latency_ms": "15.0",
                    "mean_crd_lite": "0.04",
                    "paper_allowed": "False",
                    "claim_allowed": "False",
                    "review_status": "review_pending",
                },
            ]
            csv_path.parent.mkdir(parents=True)
            with csv_path.open("w", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=summarize_paper_candidate_all_datasets.OUTPUT_COLUMNS,
                    lineterminator="\n",
                )
                writer.writeheader()
                writer.writerows(rows)
            json_path.write_text(json.dumps(summary) + "\n")

            outputs = render_paper_candidate_analysis.write_outputs(
                combined_csv=csv_path,
                combined_json=json_path,
                ranking_json=root / "ranking.json",
                ranking_tex=root / "ranking.tex",
                figure_png=root / "tradeoff.png",
                figure_pdf=root / "tradeoff.pdf",
            )
            ranking = outputs["ranking_summary"]
            self.assertEqual("paper_candidate_ranking_summary_complete", ranking["status"])
            self.assertFalse(ranking["paper_allowed"])
            self.assertFalse(ranking["claim_allowed"])
            self.assertEqual("review_pending", ranking["review_status"])
            self.assertEqual(
                "PatchCore",
                ranking["rankings"]["MVTec AD"]["best_auroc"]["baseline"],
            )
            self.assertEqual(
                "WinCLIP",
                ranking["rankings"]["MVTec AD"]["lowest_latency"]["baseline"],
            )
            self.assertTrue(outputs["ranking_json"].exists())
            self.assertTrue(outputs["ranking_tex"].exists())
            self.assertTrue(outputs["figure_png"].exists())
            self.assertGreater(outputs["figure_png"].stat().st_size, 0)
            self.assertTrue(outputs["figure_pdf"].exists())
            self.assertGreater(outputs["figure_pdf"].stat().st_size, 0)
        finally:
            if root.exists():
                shutil.rmtree(root)

    def test_ranking_summary_rejects_open_claim_gate(self):
        root = Path("results/latest/paper_candidate/unit_test_analysis_gate")
        if root.exists():
            shutil.rmtree(root)
        try:
            csv_path = root / "combined.csv"
            json_path = root / "combined.json"
            csv_path.parent.mkdir(parents=True)
            csv_path.write_text(
                "dataset,baseline,memory_policy,calibration,completed_categories,"
                "expected_categories,total_rows,stream_length,seeds,mean_image_auroc,"
                "mean_aupr,mean_ece,mean_latency_ms,mean_crd_lite,paper_allowed,"
                "claim_allowed,review_status\n"
                "VisA,WinCLIP,default/no-memory,none,12,12,144,64,0|1|2,"
                "0.7,0.8,0.2,10,0.01,False,False,review_pending\n"
            )
            json_path.write_text(
                json.dumps(
                    {
                        "status": "paper_candidate_combined_baseline_comparison_complete",
                        "dataset_count": 1,
                        "baseline_row_count": 1,
                        "paper_allowed": False,
                        "claim_allowed": True,
                        "review_status": "review_pending",
                    }
                )
                + "\n"
            )
            with self.assertRaises(
                render_paper_candidate_analysis.CombinedComparisonError
            ):
                render_paper_candidate_analysis.build_ranking_summary(
                    combined_csv=csv_path,
                    combined_json=json_path,
                )
        finally:
            if root.exists():
                shutil.rmtree(root)

    def test_combined_comparison_rejects_open_paper_gate(self):
        root = Path("results/latest/paper_candidate/unit_test_combined_gate")
        if root.exists():
            shutil.rmtree(root)
        try:
            path = root / "baseline_comparison_none.csv"
            path.parent.mkdir(parents=True)
            path.write_text(
                ",".join(summarize_paper_candidate_all_datasets.OUTPUT_COLUMNS)
                + "\n"
                + "VisA,WinCLIP,default/no-memory,none,12,12,144,64,0|1|2,"
                "0.70,0.80,0.20,10.0,0.01,True,False,review_pending\n"
            )
            with self.assertRaises(
                summarize_paper_candidate_all_datasets.CombinedComparisonError
            ):
                summarize_paper_candidate_all_datasets.summarize_all_datasets([path])
        finally:
            if root.exists():
                shutil.rmtree(root)

    def test_baseline_comparison_uses_dataset_from_category_summaries(self):
        root = Path("results/latest/paper_candidate/unit_test_visa_baseline_compare")
        if root.exists():
            shutil.rmtree(root)
        try:
            category_root = root / "winclip" / "default_no_memory" / "none" / "candle"
            category_root.mkdir(parents=True)
            metrics_path = category_root / "metrics.csv"
            metrics_path.write_text(
                "dataset,stream_type,prevalence,contamination_epsilon,baseline,"
                "memory_policy,calibration,image_auroc,aupr,ece,latency_ms,"
                "crd_lite,status,category\n"
                "VisA,iid,0.05,0,WinCLIP,default/no-memory,none,"
                "0.9,0.8,0.1,10,0.2,measured_paper_candidate,candle\n"
            )
            (category_root / "manifest.json").write_text("{}\n")
            (category_root / "crd_lite.csv").write_text("category,crd_lite\ncandle,0.2\n")
            summary_root = root / "winclip" / "default_no_memory" / "none"
            (summary_root / "category_summary.json").write_text(
                json.dumps(
                    {
                        "status": "category_shards_complete",
                        "dataset": "VisA",
                        "baseline": "WinCLIP",
                        "memory_policy": "default/no-memory",
                        "calibration": "none",
                        "category_count": 1,
                        "complete_category_count": 1,
                        "paper_allowed": False,
                        "claim_allowed": False,
                        "review_status": "review_pending",
                        "categories": [
                            {
                                "category": "candle",
                                "complete": True,
                                "row_count": 1,
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
                baselines=["winclip:default_no_memory"],
            )
            self.assertEqual("VisA", summary["dataset"])
            self.assertEqual(1, summary["baseline_count"])
            self.assertEqual("WinCLIP", summary["baselines"][0]["baseline"])
        finally:
            if root.exists():
                shutil.rmtree(root)


if __name__ == "__main__":
    unittest.main()
