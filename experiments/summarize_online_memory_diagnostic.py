#!/usr/bin/env python3
"""Summarize true-online memory diagnostic pilots."""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

DEFAULT_ROOT = Path("results/latest/paper_candidate/diagnostic_online_prototype_ema")
DEFAULT_TABLE = Path("results/latest/tables/online_prototype_ema_delta_bi.tex")
PILOT_CATEGORIES = ["bottle", "cable", "capsule"]
BOOTSTRAP_ITERATIONS = 5000
RANDOM_SEED = 1701


class OnlineMemorySummaryError(ValueError):
    """Raised when online-memory diagnostic outputs are incomplete."""


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise OnlineMemorySummaryError(f"Missing JSON file: {path}")
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise OnlineMemorySummaryError(f"JSON file must contain an object: {path}")
    return payload


def _read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise OnlineMemorySummaryError(f"Missing metrics file: {path}")
    with path.open(newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _as_float(row: dict[str, str], key: str) -> float:
    value = float(row[key])
    if not math.isfinite(value):
        raise OnlineMemorySummaryError(f"Non-finite {key}: {value!r}")
    return value


def _seed(row: dict[str, str]) -> int:
    if row.get("seed") not in {None, ""}:
        return int(str(row["seed"]))
    match = re.search(r"_seed_(\d+)(?:/)?$", str(row.get("run_dir", "")))
    if not match:
        raise OnlineMemorySummaryError(f"Cannot parse seed from row: {row}")
    return int(match.group(1))


def _mean(values: list[float]) -> float:
    if not values:
        raise OnlineMemorySummaryError("Cannot average an empty sequence")
    return sum(values) / len(values)


def _sample_standard_deviation(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = _mean(values)
    return math.sqrt(sum((value - mean) ** 2 for value in values) / (len(values) - 1))


def _quantile(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        raise OnlineMemorySummaryError("Cannot compute quantile of empty values")
    position = (len(sorted_values) - 1) * q
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return sorted_values[lower]
    fraction = position - lower
    return sorted_values[lower] * (1 - fraction) + sorted_values[upper] * fraction


def _bootstrap_ci(values: list[float]) -> tuple[float, float]:
    rng = random.Random(RANDOM_SEED)
    estimates: list[float] = []
    for _ in range(BOOTSTRAP_ITERATIONS):
        sample = [values[rng.randrange(len(values))] for _ in values]
        estimates.append(_mean(sample))
    estimates.sort()
    return _quantile(estimates, 0.025), _quantile(estimates, 0.975)


def _format_ci(mean: float, low: float, high: float) -> str:
    return f"{mean:+.3f} [{low:+.3f},{high:+.3f}]"


def _escape_latex(value: Any) -> str:
    text = str(value)
    replacements = {
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return text


def _slug(value: str) -> str:
    return value.strip().lower().replace("/", "_").replace("-", "_").replace(" ", "_")


def _category_root(
    root: Path,
    category: str,
    *,
    dataset_slug: str,
    baseline_slug: str,
    memory_policy_slug: str,
    calibration_slug: str,
) -> Path:
    return root / dataset_slug / baseline_slug / memory_policy_slug / calibration_slug / category


def _expected_rows_from_manifest(manifest: dict[str, Any]) -> int:
    seeds = manifest.get("seeds")
    if isinstance(seeds, list) and seeds:
        return len(seeds) * 2 * 2
    expected = manifest.get("expected_full_run_count") or manifest.get("run_count")
    if expected is not None:
        return int(expected)
    raise OnlineMemorySummaryError("Cannot infer expected row count from manifest")


def _read_category(
    root: Path,
    category: str,
    *,
    dataset_slug: str,
    baseline_slug: str,
    memory_policy_slug: str,
    calibration_slug: str,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    category_root = _category_root(
        root,
        category,
        dataset_slug=dataset_slug,
        baseline_slug=baseline_slug,
        memory_policy_slug=memory_policy_slug,
        calibration_slug=calibration_slug,
    )
    metrics_path = category_root / "metrics.csv"
    manifest_path = category_root / "manifest.json"
    crd_path = category_root / "crd_lite.csv"
    rows = _read_rows(metrics_path)
    manifest = _load_json(manifest_path)
    if not crd_path.exists():
        raise OnlineMemorySummaryError(f"Missing CRD-lite file: {crd_path}")
    expected_rows = _expected_rows_from_manifest(manifest)
    if len(rows) != expected_rows:
        raise OnlineMemorySummaryError(
            f"{category} row count {len(rows)} != expected {expected_rows}"
        )
    if {row.get("status") for row in rows} != {"measured_paper_candidate"}:
        raise OnlineMemorySummaryError(f"{category} status values are not measured_paper_candidate")
    for key, expected in {
        "paper_allowed": False,
        "claim_allowed": False,
        "review_status": "review_pending",
        "candidate_scope": "category_shard",
        "category_count": 1,
    }.items():
        if manifest.get(key) != expected:
            raise OnlineMemorySummaryError(
                f"{category} manifest {key}={manifest.get(key)!r}, expected {expected!r}"
            )
    if manifest.get("category") != category:
        raise OnlineMemorySummaryError(
            f"{category} manifest category={manifest.get('category')!r}, expected {category!r}"
        )
    return rows, manifest


def summarize(
    root: Path = DEFAULT_ROOT,
    *,
    categories: list[str] | None = None,
    dataset: str = "MVTec AD",
    baseline: str = "OnlinePrototypeEMA",
    memory_policy: str = "Prototype-EMA",
    calibration: str = "none",
) -> dict[str, Any]:
    categories = categories or PILOT_CATEGORIES
    dataset_slug = _slug(dataset)
    baseline_slug = _slug(baseline)
    memory_policy_slug = _slug(memory_policy)
    calibration_slug = _slug(calibration)
    all_rows: list[dict[str, str]] = []
    manifests: list[dict[str, Any]] = []
    expected_row_count = 0
    for category in categories:
        rows, manifest = _read_category(
            root,
            category,
            dataset_slug=dataset_slug,
            baseline_slug=baseline_slug,
            memory_policy_slug=memory_policy_slug,
            calibration_slug=calibration_slug,
        )
        all_rows.extend(rows)
        manifests.append(manifest)
        expected_row_count += _expected_rows_from_manifest(manifest)

    groups: dict[tuple[str, int, float, str], list[dict[str, str]]] = defaultdict(list)
    for row in all_rows:
        groups[
            (
                row["category"],
                _seed(row),
                float(row["contamination_epsilon"]),
                row["stream_type"],
            )
        ].append(row)

    strata: list[dict[str, Any]] = []
    for category in categories:
        seeds = sorted({_seed(row) for row in all_rows if row["category"] == category})
        epsilons = sorted(
            {float(row["contamination_epsilon"]) for row in all_rows if row["category"] == category}
        )
        for seed in seeds:
            for epsilon in epsilons:
                iid_rows = groups.get((category, seed, epsilon, "iid"), [])
                bursty_rows = groups.get((category, seed, epsilon, "bursty"), [])
                if len(iid_rows) != 1 or len(bursty_rows) != 1:
                    raise OnlineMemorySummaryError(
                        f"Missing matched iid/bursty row for {category} seed={seed} epsilon={epsilon}"
                    )
                iid = _as_float(iid_rows[0], "image_auroc")
                bursty = _as_float(bursty_rows[0], "image_auroc")
                strata.append(
                    {
                        "category": category,
                        "seed": seed,
                        "epsilon": epsilon,
                        "iid_image_auroc": iid,
                        "bursty_image_auroc": bursty,
                        "delta_b_i": bursty - iid,
                    }
                )

    deltas = [float(row["delta_b_i"]) for row in strata]
    delta_mean = _mean(deltas)
    delta_low, delta_high = _bootstrap_ci(deltas)
    delta_sd = _sample_standard_deviation(deltas)
    delta_standard_error = delta_sd / math.sqrt(len(deltas))
    minimum_detectable_effect_95 = 1.96 * delta_standard_error
    aurocs = [_as_float(row, "image_auroc") for row in all_rows]
    aupr = [_as_float(row, "aupr") for row in all_rows]
    ece = [_as_float(row, "ece") for row in all_rows]
    latency = [_as_float(row, "latency_ms") for row in all_rows]
    crd = [
        _as_float(row, "crd_lite")
        for row in all_rows
        if row.get("crd_lite") not in {"", "NA", None}
    ]

    stream_lengths = sorted({manifest.get("stream_length") for manifest in manifests})
    applied_lengths = sorted(
        {
            row.get("stream_length")
            for row in all_rows
            if row.get("stream_length") not in {"", None}
        }
    )
    if baseline == "OnlineWindowKNN":
        notes = (
            "Lightweight true-online diagnostic only. The detector uses image "
            "descriptors and a FIFO nearest-neighbor memory bank updated after "
            "each stream observation; it is not a leaderboard baseline."
        )
    else:
        notes = (
            "Lightweight true-online diagnostic only. The detector uses image "
            "descriptors and an EMA-updated prototype; it is not a leaderboard baseline."
        )
    return {
        "status": "online_memory_diagnostic_complete",
        "run_tier": "paper_candidate",
        "diagnostic": baseline,
        "dataset": dataset,
        "baseline": baseline,
        "memory_policy": memory_policy,
        "calibration": calibration,
        "categories": categories,
        "category_count": len(categories),
        "row_count": len(all_rows),
        "expected_row_count": expected_row_count,
        "strata_count": len(strata),
        "stream_lengths": stream_lengths,
        "applied_stream_lengths": applied_lengths,
        "delta_b_i_mean": delta_mean,
        "delta_b_i_ci_low": delta_low,
        "delta_b_i_ci_high": delta_high,
        "delta_b_i_ci_excludes_zero": delta_low > 0 or delta_high < 0,
        "delta_b_i_empirical_sd": delta_sd,
        "delta_b_i_standard_error": delta_standard_error,
        "minimum_detectable_effect_95": minimum_detectable_effect_95,
        "mean_image_auroc": _mean(aurocs),
        "mean_aupr": _mean(aupr),
        "mean_ece": _mean(ece),
        "mean_latency_ms": _mean(latency),
        "mean_crd_lite": _mean(crd) if crd else None,
        "bootstrap_iterations": BOOTSTRAP_ITERATIONS,
        "bootstrap_unit": "category_seed_epsilon",
        "paper_allowed": False,
        "claim_allowed": False,
        "review_status": "review_pending",
        "strata": strata,
        "notes": notes,
    }


def write_outputs(
    summary: dict[str, Any],
    *,
    root: Path = DEFAULT_ROOT,
    table_path: Path = DEFAULT_TABLE,
) -> tuple[Path, Path, Path]:
    root.mkdir(parents=True, exist_ok=True)
    csv_path = root / "online_memory_delta_bi_summary.csv"
    json_path = root / "online_memory_delta_bi_summary.json"
    table_path.parent.mkdir(parents=True, exist_ok=True)

    columns = [
        "dataset",
        "baseline",
        "memory_policy",
        "categories",
        "rows",
        "strata",
        "mean_image_auroc",
        "delta_b_i_ci",
        "delta_b_i_standard_error",
        "minimum_detectable_effect_95",
        "mean_ece",
        "mean_latency_ms",
        "paper_allowed",
        "claim_allowed",
        "review_status",
    ]
    row = {
        "dataset": summary["dataset"],
        "baseline": summary["baseline"],
        "memory_policy": summary["memory_policy"],
        "categories": "|".join(summary["categories"]),
        "rows": summary["row_count"],
        "strata": summary["strata_count"],
        "mean_image_auroc": f"{summary['mean_image_auroc']:.6f}",
        "delta_b_i_ci": _format_ci(
            summary["delta_b_i_mean"],
            summary["delta_b_i_ci_low"],
            summary["delta_b_i_ci_high"],
        ),
        "delta_b_i_standard_error": f"{summary['delta_b_i_standard_error']:.6f}",
        "minimum_detectable_effect_95": f"{summary['minimum_detectable_effect_95']:.6f}",
        "mean_ece": f"{summary['mean_ece']:.6f}",
        "mean_latency_ms": f"{summary['mean_latency_ms']:.6f}",
        "paper_allowed": "false",
        "claim_allowed": "false",
        "review_status": summary["review_status"],
    }
    with csv_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerow(row)
    json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")

    significant = summary["delta_b_i_ci_excludes_zero"]
    delta_text = _format_ci(
        summary["delta_b_i_mean"],
        summary["delta_b_i_ci_low"],
        summary["delta_b_i_ci_high"],
    )
    if significant:
        delta_text = r"\textbf{" + delta_text + "}"
    table = "\n".join(
        [
            r"\begin{tabular}{llccccccc}",
            r"\toprule",
            (
                r"Dataset & Detector & Cat. & Rows & Strata & AUROC & "
                r"$\Delta$B-I [95\% CI] & SE & MDE$_{95}$ \\"
            ),
            r"\midrule",
            (
                f"{_escape_latex(summary['dataset'])} & "
                f"{_escape_latex(summary['baseline'])} & "
                f"{summary['category_count']} & {summary['row_count']} & "
                f"{summary['strata_count']} & {summary['mean_image_auroc']:.3f} & "
                f"{delta_text} & {summary['delta_b_i_standard_error']:.3f} & "
                f"{summary['minimum_detectable_effect_95']:.3f} \\\\"
            ),
            r"\bottomrule",
            r"\end{tabular}",
            "",
        ]
    )
    table_path.write_text(table)
    return csv_path, json_path, table_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--table", type=Path, default=DEFAULT_TABLE)
    parser.add_argument("--categories", nargs="*", default=PILOT_CATEGORIES)
    parser.add_argument("--dataset", default="MVTec AD")
    parser.add_argument("--baseline", default="OnlinePrototypeEMA")
    parser.add_argument("--memory-policy", default="Prototype-EMA")
    parser.add_argument("--calibration", default="none")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = summarize(
        args.root,
        categories=[str(value) for value in args.categories],
        dataset=args.dataset,
        baseline=args.baseline,
        memory_policy=args.memory_policy,
        calibration=args.calibration,
    )
    csv_path, json_path, table_path = write_outputs(summary, root=args.root, table_path=args.table)
    print(csv_path)
    print(json_path)
    print(table_path)
    print(
        "status="
        f"{summary['status']} rows={summary['row_count']} strata={summary['strata_count']} "
        f"delta_b_i={summary['delta_b_i_mean']:+.6f} "
        f"ci=[{summary['delta_b_i_ci_low']:+.6f},{summary['delta_b_i_ci_high']:+.6f}] "
        f"excludes_zero={summary['delta_b_i_ci_excludes_zero']} "
        f"se={summary['delta_b_i_standard_error']:.6f} "
        f"mde95={summary['minimum_detectable_effect_95']:.6f} "
        "paper_allowed=false claim_allowed=false"
    )


if __name__ == "__main__":
    main()
