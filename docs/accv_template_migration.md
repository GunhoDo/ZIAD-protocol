# ACCV/LNCS Template Integration Notes

## Current status

The unpacked ACCV/Springer LNCS template is vendored under `paper/template/`.
The original template example remains at `paper/template/main.tex`; it is not
used as the real manuscript.

- `paper/paper.tex` uses `\documentclass[runningheads]{llncs}`.
- Review mode is enabled with `\usepackage[review,year=2026,ID=*****]{accv}`.
- Common ACCV abbreviations are enabled with `\usepackage{accvabbrv}`.
- Bibliography style is `splncs04`.
- Required template source files are available both in `paper/template/` and
  copied into `paper/` so the existing `cd paper && pdflatex paper.tex` build
  path can find them without absolute paths.
- `scripts/build_paper.sh` builds with `pdflatex` when available.
- If LaTeX is unavailable, the build script writes a small placeholder PDF so
  repository checks can still run without committing generated PDFs.

Generated PDFs and LaTeX build files remain ignored by Git.

## Integrated template files

- `paper/template/llncs.cls`
- `paper/template/accv.sty`
- `paper/template/accvabbrv.sty`
- `paper/template/splncs04.bst`
- `paper/template/main.tex`
- `paper/llncs.cls`
- `paper/accv.sty`
- `paper/accvabbrv.sty`
- `paper/splncs04.bst`

The manuscript should keep anonymous review metadata until camera-ready review:
`Anonymous ACCV Submission`, `Paper ID *****`, and review package options.

## Table and figure checks

The current paper includes generated artifacts by relative paths from
`paper/`:

- `../results/latest/tables/paper_candidate_baseline_comparison_all_datasets_none.tex`
- `../results/latest/tables/paper_candidate_ranking_summary.tex`
- `../results/latest/figures/paper_candidate_accuracy_latency_tradeoff.png`

After edits to paper tables or figures, verify that:

- table widths still fit the LNCS text block;
- `\resizebox{\textwidth}{!}{...}` is acceptable under the template;
- captions follow venue style;
- figure paths still resolve from the `paper/` build directory;
- the optional PDF figure is available if the camera-ready build prefers PDF;
- generated tables and figures still come only from `results/latest/`.

## Result-governance checklist

The current paper uses candidate evidence. Before promoting any result to a
final paper claim, complete the separate promotion review:

- non-validation stream length confirmed;
- PatchCore sampler and memory settings reviewed;
- row-count and category-count checks pass;
- metric audit has no missing, NaN, Inf, or invalid latency values;
- runtime environment and timing semantics are manually confirmed;
- baseline provenance is reviewed;
- manual claim-promotion approval is recorded.

Until that review is complete, keep paper-facing wording cautious and do not
change `paper_allowed` or `claim_allowed`.

## Readiness check

Run the repository readiness check before paper builds:

```bash
python3 scripts/check_paper_template_readiness.py
```

The check verifies that the bibliography exists, required paper-candidate
tables and figures exist, and no unexpected TODO markers are present. The
currently approved submission TODO is the final pre-submission checklist in
`paper/paper.tex`.
