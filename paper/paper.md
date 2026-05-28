# ZIAD: A Streaming Evaluation Protocol for Industrial Anomaly Detection

## Abstract

TODO: Replace this placeholder abstract after real P0 results exist. This paper targets a streaming industrial anomaly detection evaluation protocol for zero-shot and training-light baselines. The current build intentionally avoids measured-result claims until `results/latest/manifest.json` is marked `final`.

## 1 Introduction

Industrial anomaly detection is often evaluated on static test sets, but practical inspection systems receive images over time. This scaffold focuses on the paper pipeline for a streaming evaluation study that includes PatchCore as a training-light reference and WinCLIP, AnomalyCLIP, and RareCLIP as CLIP-style baselines.

TODO: Add evidence-backed motivation and citations.

## 2 Evaluation Protocol

The minimal P0 protocol covers MVTec AD and VisA, i.i.d. and bursty streams, prevalence 0.05, contamination levels 0, 0.01, and 0.05, and the baselines RareCLIP, PatchCore, WinCLIP, and AnomalyCLIP.

## 3 Results

TODO: Results are intentionally placeholders. Do not report measured AUROC, AUPR, ECE, latency, or CRD-lite until `results/latest/manifest.json` has `status: "final"` and `paper_allowed: true`.

The paper may only consume result files from `results/latest/`.

The manuscript build may include generated smoke evidence tables from
`results/latest/tables/`, but they remain explicitly paper-ineligible until the
manifest is final and `paper_allowed` is true.

## 4 Limitations

TODO: Replace this section after real P0 runs. Expected interpretations from the protocol are not findings until validated by generated outputs.

## References

Current bibliography source: `paper/refs.bib`; the ACCV/LNCS-oriented LaTeX
draft consumes it from `paper/paper.tex`.
