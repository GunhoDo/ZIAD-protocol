# ACCV/LNCS Template Migration Notes

## Current status

No official ACCV or Springer LNCS template is currently vendored in this
repository. The paper source therefore keeps a dependency-light build path:

- `paper/paper.tex` uses `\documentclass[10pt]{article}`.
- `scripts/build_paper.sh` builds with `pdflatex` when available.
- If LaTeX is unavailable, the build script writes a small placeholder PDF so
  repository checks can still run without external template files.

This is intentional for development. It is not a substitute for the official
submission template.

## Before ACCV submission

Add the official ACCV/Springer LNCS files before the final submission-format
pass. Do not create or modify a fake `llncs.cls`. Use only the class and
support files distributed by the venue or Springer.

Expected source changes once the official template is present:

- Replace `\documentclass[10pt]{article}` with
  `\documentclass[runningheads]{llncs}`.
- Remove article-only layout packages such as `geometry` unless the official
  template explicitly permits them.
- Check `hyperref`, `url`, `xcolor`, `graphicx`, and `booktabs` compatibility
  with the official instructions.
- Convert the title block to LNCS form, including `\title`,
  `\titlerunning`, `\author`, `\authorrunning`, and `\institute` as required.
- Keep the anonymous author block while the venue requires anonymity.
- Switch the bibliography style to the official LNCS style, commonly
  `splncs04`, only after the official `.bst` file is available.
- Rebuild the bibliography with the normal LaTeX/BibTeX sequence.

## Table and figure checks

The current paper includes generated artifacts by relative paths from
`paper/`:

- `../results/latest/tables/paper_candidate_baseline_comparison_all_datasets_none.tex`
- `../results/latest/tables/paper_candidate_ranking_summary.tex`
- `../results/latest/figures/paper_candidate_accuracy_latency_tradeoff.png`

After switching to `llncs`, verify that:

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

Run the repository readiness check before template migration or paper builds:

```bash
python3 scripts/check_paper_template_readiness.py
```

The check verifies that the bibliography exists, required paper-candidate
tables and figures exist, and no unexpected TODO markers are present. The
currently approved submission TODO is the final pre-submission checklist in
`paper/paper.tex`.
