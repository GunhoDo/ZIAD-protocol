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
    pad_x = 0.18
    pad_top = 0.17
    box = patches.FancyBboxPatch(
        (x, y),
        width,
        height,
        boxstyle="round,pad=0.04,rounding_size=0.045",
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
        y + height - pad_top - 0.28,
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
            "linewidth": 1.35,
            "color": "#374151",
            "shrinkA": 0,
            "shrinkB": 0,
            "mutation_scale": 12,
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

    fig, ax = plt.subplots(figsize=(7.3, 2.75), dpi=220)
    ax.set_xlim(0, 10.4)
    ax.set_ylim(0, 3.55)
    ax.axis("off")

    main_y = 1.52
    main_h = 1.20
    widths = [1.78, 1.84, 2.20, 2.52]
    xs = [0.22, 2.36, 4.64, 7.46]

    # --- Alignment anchors (derived, not hardcoded) ---------------------
    left_edge = xs[0]                 # left edge of the top pipeline
    right_edge = xs[3] + widths[3]    # right edge of the top pipeline

    # Bottom box spans the full top-pipeline width => no empty right margin.
    # To right-align only (keep it starting under "Baseline families"),
    # set bottom_x = 4.64 instead of left_edge.
    bottom_x = left_edge
    bottom_w = right_edge - bottom_x
    bottom_y = 0.26
    bottom_h = 0.78

    boxes = [
        ((xs[0], main_y), widths[0], main_h, "Datasets",
         ["MVTec AD, VisA", "category splits"], "#e0f2fe"),
        ((xs[1], main_y), widths[1], main_h, "Stream gen.",
         ["IID arrivals", "bursty blocks", r"$\epsilon$ contamination"], "#dcfce7"),
        ((xs[2], main_y), widths[2], main_h, "Baseline families",
         ["PatchCore reference", "WinCLIP, AnomalyCLIP", "RareCLIP"], "#fef3c7"),
        ((xs[3], main_y), widths[3], main_h, "Metrics and audit",
         ["AUROC, AUPR, ECE", "latency, CRD-lite", "category-sharded checks"], "#fee2e2"),
        ((bottom_x, bottom_y), bottom_w, bottom_h, "Optional protocol axes",
         ["memory policy  |  calibration  |  stream length"], "#fae8ff"),
    ]
    for xy, width, height, title, lines, color in boxes:
        _draw_box(ax, xy, width, height, title, lines, color)

    # Horizontal arrows: centred in the gap between consecutive top boxes.
    mid_y = main_y + main_h / 2
    gap_pad = 0.06
    _draw_arrow(ax, (xs[0] + widths[0] + gap_pad, mid_y), (xs[1] - gap_pad, mid_y))
    _draw_arrow(ax, (xs[1] + widths[1] + gap_pad, mid_y), (xs[2] - gap_pad, mid_y))
    _draw_arrow(ax, (xs[2] + widths[2] + gap_pad, mid_y), (xs[3] - gap_pad, mid_y))

    # Dashed connector under "Baseline families" -> bottom box.
    connector_x = xs[2] + widths[2] / 2.0
    ax.plot(
        [connector_x, connector_x],
        [bottom_y + bottom_h + 0.02, main_y - 0.08],
        color="#6b7280",
        linewidth=0.9,
        linestyle="--",
    )
    ax.text(
        connector_x + 0.15,
        (bottom_y + bottom_h + main_y) / 2.0 + 0.02,
        "configured per slice",
        ha="left",
        va="center",
        fontsize=6.2,
        color="#4b5563",
    )

    # Title centred over the top pipeline.
    title_cx = (left_edge + right_edge) / 2.0
    ax.text(
        title_cx,
        3.20,
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