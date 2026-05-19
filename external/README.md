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

The current `repo_url`, `commit_hash`, and `local_path` values are pinned from the local clones. Wrapper integration and checkpoint/setup commands may still be **TBD**.

## Notes

- All paths under `external/` are gitignored except this README.
- Do not commit cloned baseline repositories.
- Wrapper stubs live in `experiments/baselines/` and will raise a clear setup error until a real baseline is cloned and configured.
- Use `bash scripts/setup_baselines.sh` to see per-baseline clone instructions.
