# Runtime Environment

This document records the local runtime context for the current
paper-candidate artifacts. It is a pre-promotion checklist item, not evidence
that the current metrics are final paper claims.

## Detected Audit/Build Environment

- CPU: Intel(R) Core(TM) i5-14500
- CPU topology: 1 socket, 14 cores, 20 logical CPUs
- GPU: unconfirmed for the original compact evaluation runs. In the current
  audit shell, `nvidia-smi -L` cannot communicate with an NVIDIA driver.
- RAM: 31 GiB total detected by `free -h`
- OS: Ubuntu 22.04.5 LTS, Linux 6.8.0-111-generic, x86_64
- Python: 3.10.12
- PyTorch: 1.13.1+cu116
- torchvision: 0.14.1+cu116
- NumPy: 1.26.4
- scikit-learn: 1.6.1
- matplotlib: 3.10.1
- Pillow: 11.1.0
- PyYAML: 6.0.2

## Timing Semantics for the Current Manuscript

- Latency device: the exact CPU/GPU path for each baseline's compact evaluation
  latency is not fully reconstructed from the artifacts. Current audit evidence
  should be treated as local-runtime dependent.
- Model loading: the artifacts do not fully establish whether reported latency
  excludes initial model loading, checkpoint loading, and one-time
  preprocessing. The manuscript therefore avoids device-independent latency
  claims.
- Timing granularity: current summary tables report `mean_latency_ms` aggregated
  from category-sharded paper-candidate metrics. The safest interpretation is
  wrapper-emitted local timing aggregated through the repository summaries.
- Batch/concurrency settings: batch size, worker count, thread settings, and
  baseline-specific caching are not fully reconstructed from the current
  artifacts; this is a runtime-validity limitation rather than a promoted
  hardware claim.
- Reproducibility note: current results retain `paper_allowed=false`,
  `claim_allowed=false`, and `review_status=review_pending`. This runtime
  document does not change those gates.
