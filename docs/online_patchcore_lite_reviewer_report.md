# OnlinePatchCoreLite Reviewer Diagnostic

This report summarizes a lightweight true-online PatchCore-style FIFO memory-bank detector.
The detector scores each descriptor against the current memory bank before inserting it, so future scores depend on the previous stream prefix.

## Per-K Results

| K | Delta B-I | 95% CI | CI excludes zero | SE | MDE95 | Rows | Strata | Latency ms |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 8 | +0.014361 | [+0.005801, +0.023007] | True | 0.004502 | 0.008823 | 120 | 60 | 23.876073 |
| 16 | +0.013522 | [+0.005100, +0.021573] | True | 0.004214 | 0.008259 | 120 | 60 | 26.518164 |
| 32 | +0.010842 | [+0.001741, +0.020604] | True | 0.004808 | 0.009423 | 120 | 60 | 25.757986 |
| 64 | +0.010237 | [+0.000719, +0.020296] | True | 0.004891 | 0.009587 | 120 | 60 | 26.111800 |

## Best Reviewer-Facing Result

Best K: `8` with Delta B-I `+0.014361` and 95% CI `[+0.005801, +0.023007]`.
CI excludes zero: `True`.

## Detector Comparison

| Detector | Delta B-I | 95% CI | CI excludes zero | Rows | Strata | Latency ms |
|---|---:|---:|---:|---:|---:|---:|
| OnlinePrototypeEMA | +0.003971 | [-0.008195, +0.015609] | False | 60 | 30 | 23.444812 |
| OnlineWindowKNN | +0.013522 | [+0.005100, +0.021573] | True | 120 | 60 | 23.460406 |
| OnlinePatchCoreLite K=8 | +0.014361 | [+0.005801, +0.023007] | True | 120 | 60 | 23.876073 |

## Reviewer-Facing Conclusion

Success: at least one OnlinePatchCoreLite configuration has a bootstrap 95% CI excluding zero.
All outputs remain paper_allowed=false and claim_allowed=false.
