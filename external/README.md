# external/

Baseline model repositories are NOT committed to this repository. Clone them here locally.

## Expected layout

```
external/
  RareCLIP/              # RareCLIP baseline — https://github.com/hjf02/RareCLIP.git
  patchcore-inspection/  # PatchCore baseline — https://github.com/amazon-science/patchcore-inspection.git
  WinClip/               # WinCLIP baseline — https://github.com/caoyunkang/WinClip.git
  AnomalyCLIP/           # AnomalyCLIP baseline — https://github.com/zqhang/AnomalyCLIP.git
```

## Baseline registry

See `experiments/configs/baselines.yaml` for the full registry including `local_path`, `repo_url`, `commit_hash`, `checkpoint_path`, `setup_command`, and `smoke_command`.

The current `repo_url`, `commit_hash`, and `local_path` values are pinned from the local clones. Clone each baseline at its pinned `commit_hash` for a faithful reproduction.

## Checkpoints

Two baselines need pretrained weights placed at the `checkpoint_path` recorded in `baselines.yaml`:

- **RareCLIP** → `external/RareCLIP/weights/mvtec_pretrained.pth` — obtain from the upstream RareCLIP repository's release/instructions (https://github.com/hjf02/RareCLIP).
- **AnomalyCLIP** → `external/AnomalyCLIP/checkpoints/9_12_4_multiscale/epoch_15.pth` — obtain from the upstream AnomalyCLIP repository (https://github.com/zqhang/AnomalyCLIP).

PatchCore and WinCLIP do not require a separately downloaded checkpoint in this setup (`checkpoint_path: TBD_or_not_required`); they build their feature memory / use their CLIP backbone at run time. Verify the exact checkpoint links against each upstream repo, since release URLs change over time.

## Notes

- All paths under `external/` are gitignored except this README.
- Do not commit cloned baseline repositories.
- Wrapper stubs live in `experiments/baselines/` and will raise a clear setup error until a real baseline is cloned and configured.
- Use `bash scripts/setup_baselines.sh` to see per-baseline clone instructions.
