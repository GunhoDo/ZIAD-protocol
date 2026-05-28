# Runtime Environment

This document records the local runtime context for the current
paper-candidate artifacts. It is a pre-promotion checklist item, not evidence
that the current metrics are final paper claims.

## Detected Audit/Build Environment

- CPU: Intel(R) Core(TM) i5-14500
- CPU topology: 1 socket, 14 cores, 20 logical CPUs
- GPU: TODO confirm for the original paper-candidate runs. In the current
  shell, `nvidia-smi -L` cannot communicate with an NVIDIA driver.
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

## Timing Semantics To Confirm Before Claim Promotion

- Latency device: TODO confirm whether each baseline's paper-candidate latency
  was measured on CPU, CUDA GPU, or a mixed path. Current audit evidence should
  be treated as local-runtime dependent.
- Model loading: TODO confirm whether reported latency excludes initial model
  loading, checkpoint loading, and one-time preprocessing. The intended paper
  claim should report per-image inference latency after setup.
- Timing granularity: current summary tables report `mean_latency_ms` aggregated
  from category-sharded paper-candidate metrics. TODO confirm whether each
  baseline wrapper records per-image, per-stream, or per-category timing at the
  source row level before promoting latency claims.
- Batch/concurrency settings: TODO document batch size, worker count, thread
  settings, and any baseline-specific caching used during candidate execution.
- Reproducibility note: current results retain `paper_allowed=false`,
  `claim_allowed=false`, and `review_status=review_pending`. This runtime
  document does not change those gates.
