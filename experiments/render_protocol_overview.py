#!/usr/bin/env python3
"""Render the ZIAD protocol overview figure.

This script is deliberately result-free: it draws the protocol structure used
by the paper and does not read metrics or run inference.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Iterable


def _configure_matplotlib() -> None:
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/ziad_matplotlib")


def _draw_box(ax, xy, width, height, title: str, lines: Iterable[str], color: str) -> None:
    import matplotlib.patches as patches

    x, y = xy
    box = patches.FancyBboxPatch(
        (x, y),
        width,
        height,
        boxstyle="round,pad=0.02,rounding_size=0.04",
        linewidth=1.1,
        edgecolor="#1f2937",
        facecolor=color,
    )
    ax.add_patch(box)
    ax.text(
        x + width / 2,
        y + height - 0.12,
        title,
        ha="center",
        va="top",
        fontsize=8.0,
        fontweight="bold",
        color="#111827",
    )
    ax.text(
        x + 0.06,
        y + height - 0.34,
        "\n".join(lines),
        ha="left",
        va="top",
        fontsize=7.2,
        color="#111827",
        linespacing=1.22,
    )


def _draw_arrow(ax, start, end) -> None:
    ax.annotate(
        "",
        xy=end,
        xytext=start,
        arrowprops={
            "arrowstyle": "-|>",
            "linewidth": 1.25,
            "color": "#374151",
            "shrinkA": 4,
            "shrinkB": 4,
        },
    )


def render(output_png: Path, output_pdf: Path | None = None) -> None:
    _configure_matplotlib()
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    output_png.parent.mkdir(parents=True, exist_ok=True)
    if output_pdf is not None:
        output_pdf.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(7.2, 3.0), dpi=220)
    ax.set_xlim(0, 10.6)
    ax.set_ylim(0, 4)
    ax.axis("off")

    boxes = [
        ((0.15, 1.65), 1.75, 1.35, "Static datasets", ["MVTec AD", "VisA", "category splits"], "#e0f2fe"),
        ((2.35, 1.65), 1.95, 1.35, "Stream generator", ["iid arrivals", "bursty blocks", "epsilon contamination"], "#dcfce7"),
        ((4.75, 1.45), 2.25, 1.75, "Baseline families", ["PatchCore", "WinCLIP / AnomalyCLIP", "RareCLIP"], "#fef3c7"),
        ((7.55, 1.45), 2.65, 1.75, "Metrics and audit", ["AUROC, AUPR, ECE", "latency, CRD-lite", "category-sharded checks"], "#fee2e2"),
        ((2.8, 0.35), 3.75, 0.72, "Optional protocol axes", ["memory policy   |   calibration   |   stream length"], "#fae8ff"),
    ]
    for xy, width, height, title, lines, color in boxes:
        _draw_box(ax, xy, width, height, title, lines, color)

    _draw_arrow(ax, (1.9, 2.32), (2.35, 2.32))
    _draw_arrow(ax, (4.3, 2.32), (4.75, 2.32))
    _draw_arrow(ax, (7.0, 2.32), (7.55, 2.32))
    _draw_arrow(ax, (4.9, 1.45), (4.9, 1.07))
    _draw_arrow(ax, (6.55, 0.71), (7.55, 1.58))

    ax.text(
        5.3,
        3.62,
        "ZIAD converts static IAD benchmarks into auditable streaming evaluations",
        ha="center",
        va="center",
        fontsize=9.3,
        color="#111827",
    )

    fig.savefig(output_png, bbox_inches="tight", pad_inches=0.03)
    if output_pdf is not None:
        fig.savefig(output_pdf, bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-png",
        default="results/latest/figures/ziad_protocol_overview.png",
        help="PNG output path.",
    )
    parser.add_argument(
        "--output-pdf",
        default="results/latest/figures/ziad_protocol_overview.pdf",
        help="PDF output path. Use an empty value to skip PDF output.",
    )
    args = parser.parse_args()

    output_pdf = Path(args.output_pdf) if args.output_pdf else None
    render(Path(args.output_png), output_pdf)
    print(Path(args.output_png))
    if output_pdf is not None:
        print(output_pdf)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
