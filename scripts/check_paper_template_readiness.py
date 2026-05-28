#!/usr/bin/env python3
"""Check paper source readiness for ACCV/LNCS template migration.

This script intentionally does not run inference and does not write result
artifacts. It validates that the dependency-light article draft has the inputs
needed for a later official LNCS migration.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


REQUIRED_ARTIFACTS = (
    Path("paper/paper.tex"),
    Path("paper/refs.bib"),
    Path("results/latest/tables/paper_candidate_baseline_comparison_all_datasets_none.tex"),
    Path("results/latest/tables/paper_candidate_ranking_summary.tex"),
    Path("results/latest/figures/paper_candidate_accuracy_latency_tradeoff.png"),
    Path("results/latest/paper_candidate/metric_audit_report.json"),
    Path("results/latest/tables/paper_candidate_metric_audit_summary.tex"),
)

APPROVED_TODO_MARKERS = (
    "TODO before submission:",
)


@dataclass(frozen=True)
class ReadinessReport:
    errors: tuple[str, ...]
    llncs_files: tuple[str, ...]
    accv_like_files: tuple[str, ...]
    document_class: str

    @property
    def ok(self) -> bool:
        return not self.errors


def _relative_paths(paths: Iterable[Path], root: Path) -> tuple[str, ...]:
    out = []
    for path in paths:
        try:
            out.append(path.relative_to(root).as_posix())
        except ValueError:
            out.append(path.as_posix())
    return tuple(sorted(out))


def _find_document_class(source: str) -> str:
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith(r"\documentclass"):
            return stripped
    return ""


def check_readiness(root: Path) -> ReadinessReport:
    root = root.resolve()
    errors: list[str] = []

    for rel_path in REQUIRED_ARTIFACTS:
        path = root / rel_path
        if not path.exists():
            errors.append(f"missing required artifact: {rel_path.as_posix()}")

    paper_tex = root / "paper/paper.tex"
    source = paper_tex.read_text(encoding="utf-8") if paper_tex.exists() else ""
    document_class = _find_document_class(source)

    todo_lines = [
        (idx, line.strip())
        for idx, line in enumerate(source.splitlines(), start=1)
        if "TODO" in line
    ]
    for idx, line in todo_lines:
        if not any(marker in line for marker in APPROVED_TODO_MARKERS):
            errors.append(f"unexpected TODO in paper/paper.tex:{idx}: {line}")

    llncs_files = tuple(root.rglob("llncs.cls"))
    accv_like_files = tuple(
        path
        for path in root.rglob("*")
        if path.is_file()
        and "accv" in path.name.lower()
        and path.relative_to(root).as_posix() != "docs/accv_template_migration.md"
    )

    if llncs_files:
        if "llncs" not in document_class:
            errors.append(
                "official llncs.cls is present but paper/paper.tex is not using an llncs document class"
            )
    else:
        if r"\documentclass[10pt]{article}" not in source:
            errors.append(
                "llncs.cls is absent, so paper/paper.tex should keep the documented article fallback"
            )

    return ReadinessReport(
        errors=tuple(errors),
        llncs_files=_relative_paths(llncs_files, root),
        accv_like_files=_relative_paths(accv_like_files, root),
        document_class=document_class,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        default=".",
        help="repository root to check (default: current directory)",
    )
    args = parser.parse_args()

    report = check_readiness(Path(args.root))
    print(f"document_class={report.document_class or 'missing'}")
    print(f"llncs_cls_files={len(report.llncs_files)}")
    if report.llncs_files:
        for path in report.llncs_files:
            print(f"  {path}")
    print(f"accv_like_template_files={len(report.accv_like_files)}")
    if report.accv_like_files:
        for path in report.accv_like_files:
            print(f"  {path}")

    if report.ok:
        print("paper template readiness: OK")
        return 0

    print("paper template readiness: FAILED")
    for error in report.errors:
        print(f"ERROR: {error}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
