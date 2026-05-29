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


def _draw_box(
    ax,
    xy,
    width,
    height,
    title: str,
    lines: Iterable[str],
    color: str,
    *,
    title_size: float = 7.6,
    body_size: float = 6.8,
) -> None:
    import matplotlib.patches as patches

    x, y = xy
    pad_x = 0.14
    box = patches.FancyBboxPatch(
        (x, y),
        width,
        height,
        boxstyle="round,pad=0.025,rounding_size=0.045",
        linewidth=0.9,
        edgecolor="#1f2937",
        facecolor=color,
    )
    ax.add_patch(box)
    ax.text(
        x + pad_x,
        y + height - 0.15,
        title,
        ha="left",
        va="top",
        fontsize=title_size,
        fontweight="bold",
        color="#111827",
    )
    ax.text(
        x + pad_x,
        y + height - 0.42,
        "\n".join(lines),
        ha="left",
        va="top",
        fontsize=body_size,
        color="#111827",
        linespacing=1.18,
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

    fig, ax = plt.subplots(figsize=(7.2, 2.65), dpi=220)
    ax.set_xlim(0, 10.2)
    ax.set_ylim(0, 3.45)
    ax.axis("off")

    main_y = 1.42
    main_h = 1.28
    widths = [1.78, 1.86, 2.28, 2.30]
    xs = [0.18, 2.35, 4.65, 7.48]
    boxes = [
        ((xs[0], main_y), widths[0], main_h, "Static datasets", ["MVTec AD, VisA", "category splits"], "#e0f2fe"),
        ((xs[1], main_y), widths[1], main_h, "Stream generator", ["IID arrivals", "bursty blocks", r"$\epsilon$ contamination"], "#dcfce7"),
        ((xs[2], main_y), widths[2], main_h, "Baseline families", ["PatchCore reference", "WinCLIP, AnomalyCLIP", "RareCLIP"], "#fef3c7"),
        ((xs[3], main_y), widths[3], main_h, "Metrics and audit", ["AUROC, AUPR, ECE", "latency, CRD-lite", "category-sharded checks"], "#fee2e2"),
        ((2.28, 0.34), 5.55, 0.62, "Optional protocol axes", ["memory policy  |  calibration  |  stream length"], "#fae8ff"),
    ]
    for xy, width, height, title, lines, color in boxes:
        _draw_box(ax, xy, width, height, title, lines, color)

    mid_y = main_y + main_h / 2
    _draw_arrow(ax, (xs[0] + widths[0] + 0.04, mid_y), (xs[1] - 0.04, mid_y))
    _draw_arrow(ax, (xs[1] + widths[1] + 0.04, mid_y), (xs[2] - 0.04, mid_y))
    _draw_arrow(ax, (xs[2] + widths[2] + 0.04, mid_y), (xs[3] - 0.04, mid_y))

    ax.plot([5.05, 5.05], [0.96, main_y - 0.09], color="#6b7280", linewidth=0.9, linestyle="--")
    ax.text(
        5.16,
        1.16,
        "configured when studied",
        ha="left",
        va="center",
        fontsize=6.2,
        color="#4b5563",
    )

    ax.text(
        5.1,
        3.14,
        "ZIAD converts static IAD benchmarks into auditable streaming evaluations",
        ha="center",
        va="center",
        fontsize=9.0,
        fontweight="bold",
        color="#111827",
    )

    fig.savefig(output_png, bbox_inches="tight", pad_inches=0.04)
    if output_pdf is not None:
        fig.savefig(output_pdf, bbox_inches="tight", pad_inches=0.04)
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
