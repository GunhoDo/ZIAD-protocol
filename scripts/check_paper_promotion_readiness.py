#!/usr/bin/env python3
"""Build a paper-candidate promotion readiness report.

The report is deliberately fail-closed. It reads existing artifacts and writes
a review summary, but it never changes paper_allowed or claim_allowed.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.check_paper_template_readiness import check_readiness as check_template_readiness


DEFAULT_OUTPUT = Path("results/latest/paper_candidate/promotion_readiness_report.json")

COMBINED_CSV = Path("results/latest/paper_candidate/baseline_comparison_all_datasets_none.csv")
COMBINED_JSON = Path("results/latest/paper_candidate/baseline_comparison_all_datasets_none.json")
COMBINED_TEX = Path("results/latest/tables/paper_candidate_baseline_comparison_all_datasets_none.tex")
RANKING_JSON = Path("results/latest/paper_candidate/baseline_ranking_summary.json")
RANKING_TEX = Path("results/latest/tables/paper_candidate_ranking_summary.tex")
TRADEOFF_PNG = Path("results/latest/figures/paper_candidate_accuracy_latency_tradeoff.png")
TRADEOFF_PDF = Path("results/latest/figures/paper_candidate_accuracy_latency_tradeoff.pdf")
METRIC_AUDIT_JSON = Path("results/latest/paper_candidate/metric_audit_report.json")
RUNTIME_DOC = Path("docs/runtime_environment.md")
TEMPLATE_DOC = Path("docs/accv_template_migration.md")
PROMOTION_CHECKLIST = Path("docs/paper_promotion_checklist.md")
BASELINES_YAML = Path("experiments/configs/baselines.yaml")
PAPER_TEX = Path("paper/paper.tex")

REQUIRED_ARTIFACTS = (
    COMBINED_CSV,
    COMBINED_JSON,
    COMBINED_TEX,
    RANKING_JSON,
    RANKING_TEX,
    TRADEOFF_PNG,
    METRIC_AUDIT_JSON,
    RUNTIME_DOC,
    TEMPLATE_DOC,
    PROMOTION_CHECKLIST,
    BASELINES_YAML,
    PAPER_TEX,
)

EXPECTED_DATASETS = {"MVTec AD": 15, "VisA": 12}
EXPECTED_BASELINES = {"PatchCore", "WinCLIP", "AnomalyCLIP", "RareCLIP"}
EXPECTED_TOTAL_ROWS = {"MVTec AD": 180, "VisA": 144}
EXPECTED_STREAM_LENGTH = "64"
EXPECTED_SEEDS = "0|1|2"


def _load_json(path: Path) -> tuple[dict[str, Any], str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except FileNotFoundError:
        return {}, f"missing JSON artifact: {path}"
    except json.JSONDecodeError as exc:
        return {}, f"invalid JSON artifact {path}: {exc}"


def _read_csv_rows(path: Path) -> tuple[list[dict[str, str]], str | None]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            return [dict(row) for row in csv.DictReader(handle)], None
    except FileNotFoundError:
        return [], f"missing CSV artifact: {path}"


def _is_false(value: Any) -> bool:
    if isinstance(value, bool):
        return value is False
    return str(value).strip().lower() == "false"


def _extract_baseline_blocks(source: str) -> dict[str, str]:
    blocks: dict[str, list[str]] = {}
    current: str | None = None
    for line in source.splitlines():
        match = re.match(r"\s{2}([A-Za-z0-9_]+):\s*$", line)
        if match:
            current = match.group(1)
            blocks[current] = []
            continue
        if current:
            if line.startswith("  ") or not line.strip():
                blocks[current].append(line)
            else:
                current = None
    return {name: "\n".join(lines) for name, lines in blocks.items()}


def _check_baseline_provenance(root: Path) -> tuple[list[str], list[str], dict[str, Any]]:
    blocking: list[str] = []
    warnings: list[str] = []
    path = root / BASELINES_YAML
    if not path.exists():
        return [f"baseline provenance file missing: {BASELINES_YAML}"], warnings, {}

    source = path.read_text(encoding="utf-8")
    blocks = _extract_baseline_blocks(source)
    summary: dict[str, Any] = {}
    for baseline in sorted(EXPECTED_BASELINES):
        block = blocks.get(baseline, "")
        repo_url = re.search(r"repo_url:\s*(\S+)", block)
        commit_hash = re.search(r"commit_hash:\s*([0-9a-fA-F]{7,40})", block)
        summary[baseline] = {
            "repo_url_present": bool(repo_url),
            "commit_hash_present": bool(commit_hash),
            "commit_hash": commit_hash.group(1) if commit_hash else None,
        }
        if not repo_url:
            blocking.append(f"missing repo_url for baseline {baseline}")
        if not commit_hash:
            blocking.append(f"missing pinned commit_hash for baseline {baseline}")
    if "Do not fabricate" not in source:
        warnings.append("baseline registry does not include the no-fabricated-provenance warning")
    return blocking, warnings, summary


def _check_combined_rows(rows: list[dict[str, str]]) -> tuple[list[str], list[str], dict[str, Any]]:
    blocking: list[str] = []
    warnings: list[str] = []
    datasets = sorted({row.get("dataset", "") for row in rows})
    baselines_by_dataset = {
        dataset: sorted({row.get("baseline", "") for row in rows if row.get("dataset") == dataset})
        for dataset in datasets
    }

    if set(datasets) != set(EXPECTED_DATASETS):
        blocking.append(f"combined table datasets mismatch: expected {sorted(EXPECTED_DATASETS)}, found {datasets}")
    if len(rows) != 8:
        blocking.append(f"combined table row count mismatch: expected 8, found {len(rows)}")

    for dataset, expected_categories in EXPECTED_DATASETS.items():
        dataset_rows = [row for row in rows if row.get("dataset") == dataset]
        baselines = {row.get("baseline") for row in dataset_rows}
        if baselines != EXPECTED_BASELINES:
            blocking.append(
                f"{dataset} baseline set mismatch: expected {sorted(EXPECTED_BASELINES)}, found {sorted(baselines)}"
            )
        for row in dataset_rows:
            row_id = f"{dataset}/{row.get('baseline')}"
            if row.get("completed_categories") != str(expected_categories):
                blocking.append(f"{row_id} completed_categories mismatch: {row.get('completed_categories')}")
            if row.get("expected_categories") != str(expected_categories):
                blocking.append(f"{row_id} expected_categories mismatch: {row.get('expected_categories')}")
            if row.get("total_rows") != str(EXPECTED_TOTAL_ROWS[dataset]):
                blocking.append(f"{row_id} total_rows mismatch: {row.get('total_rows')}")
            if row.get("stream_length") != EXPECTED_STREAM_LENGTH:
                blocking.append(f"{row_id} stream_length mismatch: {row.get('stream_length')}")
            if row.get("seeds") != EXPECTED_SEEDS:
                blocking.append(f"{row_id} seeds mismatch: {row.get('seeds')}")
            if not _is_false(row.get("paper_allowed")):
                blocking.append(f"{row_id} paper_allowed must remain false before promotion")
            if not _is_false(row.get("claim_allowed")):
                blocking.append(f"{row_id} claim_allowed must remain false before promotion")
            if row.get("review_status") != "review_pending":
                blocking.append(f"{row_id} review_status must be review_pending")

    return blocking, warnings, {
        "row_count": len(rows),
        "datasets": datasets,
        "baselines_by_dataset": baselines_by_dataset,
    }


def _check_metric_audit(root: Path) -> tuple[list[str], list[str], dict[str, Any]]:
    blocking: list[str] = []
    warnings: list[str] = []
    payload, error = _load_json(root / METRIC_AUDIT_JSON)
    if error:
        return [error], warnings, {}

    if payload.get("status") != "paper_candidate_metric_audit_passed":
        blocking.append(f"metric audit status is not passing: {payload.get('status')}")
    if payload.get("error_count") not in (0, None):
        blocking.append(f"metric audit reports errors: {payload.get('error_count')}")
    combined = payload.get("combined_csv", {})
    if combined.get("missing_value_count") != 0:
        blocking.append(f"metric audit missing values: {combined.get('missing_value_count')}")
    if combined.get("non_finite_value_count") != 0:
        blocking.append(f"metric audit non-finite values: {combined.get('non_finite_value_count')}")
    if combined.get("negative_latency_count") != 0:
        blocking.append(f"metric audit negative latencies: {combined.get('negative_latency_count')}")
    if payload.get("category_summary_count") != 8:
        blocking.append(f"metric audit category_summary_count mismatch: {payload.get('category_summary_count')}")

    return blocking, warnings, {
        "status": payload.get("status"),
        "error_count": payload.get("error_count"),
        "missing_value_count": combined.get("missing_value_count"),
        "non_finite_value_count": combined.get("non_finite_value_count"),
        "negative_latency_count": combined.get("negative_latency_count"),
        "category_summary_count": payload.get("category_summary_count"),
    }


def _check_runtime_doc(root: Path) -> tuple[list[str], list[str], dict[str, Any]]:
    path = root / RUNTIME_DOC
    if not path.exists():
        return [f"runtime document missing: {RUNTIME_DOC}"], [], {}
    source = path.read_text(encoding="utf-8")
    todo_count = source.count("TODO")
    blocking: list[str] = []
    if todo_count:
        blocking.append(f"runtime/timing semantics still have TODO markers: {todo_count}")
    required_phrases = ["Latency device", "Model loading", "Timing granularity", "Batch/concurrency"]
    for phrase in required_phrases:
        if phrase not in source:
            blocking.append(f"runtime document missing required timing field: {phrase}")
    return blocking, [], {"todo_count": todo_count, "path": RUNTIME_DOC.as_posix()}


def _check_paper_text(root: Path) -> tuple[list[str], list[str], dict[str, Any]]:
    path = root / PAPER_TEX
    if not path.exists():
        return [f"paper source missing: {PAPER_TEX}"], [], {}
    source = path.read_text(encoding="utf-8")
    blocking: list[str] = []
    warnings: list[str] = []
    if "stream length 64" not in source:
        blocking.append("paper limitations/setup must mention stream length 64")
    if "local-runtime dependent" not in source:
        blocking.append("paper limitations must mention local-runtime latency caveat")
    if "candidate evidence" not in source:
        warnings.append("paper text should retain candidate-evidence wording until promotion")
    overclaim_markers = ["final paper claim", "camera-ready claims", "final reviewed paper claims"]
    if any(marker in source for marker in overclaim_markers):
        warnings.append("paper source contains final-claim phrasing; verify it is in limitations/governance context")
    return blocking, warnings, {
        "mentions_stream_length_64": "stream length 64" in source,
        "mentions_local_runtime_latency": "local-runtime dependent" in source,
        "mentions_candidate_evidence": "candidate evidence" in source,
    }


def _check_template(root: Path) -> tuple[list[str], list[str], dict[str, Any]]:
    report = check_template_readiness(root)
    blocking = list(report.errors)
    warnings: list[str] = []
    if not report.llncs_files:
        blocking.append("official ACCV/LNCS template is not present; llncs migration remains pending")
    elif "llncs" not in report.document_class:
        blocking.append("official template exists but paper source is not using llncs")
    return blocking, warnings, {
        "document_class": report.document_class,
        "llncs_cls_files": list(report.llncs_files),
        "accv_like_template_files": list(report.accv_like_files),
        "template_readiness_ok": report.ok,
    }


def build_promotion_readiness_report(root: Path) -> dict[str, Any]:
    root = root.resolve()
    blocking_items: list[str] = []
    warning_items: list[str] = []
    checked_artifacts: dict[str, bool] = {}
    checks: dict[str, Any] = {}

    for rel_path in REQUIRED_ARTIFACTS:
        exists = (root / rel_path).exists()
        checked_artifacts[rel_path.as_posix()] = exists
        if not exists:
            blocking_items.append(f"missing required artifact: {rel_path.as_posix()}")
    checked_artifacts[TRADEOFF_PDF.as_posix()] = (root / TRADEOFF_PDF).exists()
    if not checked_artifacts[TRADEOFF_PDF.as_posix()]:
        warning_items.append(f"optional PDF trade-off figure missing: {TRADEOFF_PDF.as_posix()}")

    rows, csv_error = _read_csv_rows(root / COMBINED_CSV)
    if csv_error:
        blocking_items.append(csv_error)
    else:
        blocking, warnings, summary = _check_combined_rows(rows)
        blocking_items.extend(blocking)
        warning_items.extend(warnings)
        checks["combined_table"] = summary

    for name, check in (
        ("metric_audit", _check_metric_audit),
        ("baseline_provenance", _check_baseline_provenance),
        ("runtime_documentation", _check_runtime_doc),
        ("paper_text", _check_paper_text),
        ("template_status", _check_template),
    ):
        blocking, warnings, summary = check(root)
        blocking_items.extend(blocking)
        warning_items.extend(warnings)
        checks[name] = summary

    blocking_items.append("manual reviewer approval has not been recorded")
    ready_for_promotion = not blocking_items

    return {
        "status": "paper_candidate_promotion_review_ready"
        if ready_for_promotion
        else "paper_candidate_promotion_review_blocked",
        "ready_for_promotion": ready_for_promotion,
        "run_tier": "paper_candidate",
        "candidate_scope": "promotion_readiness",
        "paper_allowed": False,
        "claim_allowed": False,
        "review_status": "review_pending",
        "checked_artifacts": checked_artifacts,
        "checks": checks,
        "blocking_items": blocking_items,
        "warning_items": warning_items,
        "notes": (
            "This report is a read-only promotion checklist. It does not change "
            "paper_allowed or claim_allowed."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help=f"output JSON path (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()

    root = Path(args.root)
    output = root / args.output
    report = build_promotion_readiness_report(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(output.as_posix())
    print(
        "status={status} ready_for_promotion={ready} blockers={blockers} warnings={warnings} "
        "paper_allowed={paper_allowed} claim_allowed={claim_allowed}".format(
            status=report["status"],
            ready=str(report["ready_for_promotion"]).lower(),
            blockers=len(report["blocking_items"]),
            warnings=len(report["warning_items"]),
            paper_allowed=str(report["paper_allowed"]).lower(),
            claim_allowed=str(report["claim_allowed"]).lower(),
        )
    )
    for item in report["blocking_items"]:
        print(f"BLOCKER: {item}")
    for item in report["warning_items"]:
        print(f"WARNING: {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
