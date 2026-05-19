# external/

Baseline model repositories are NOT committed to this repository. Clone them here locally.

## Expected layout

```
external/
  RareCLIP/        # RareCLIP baseline — repo URL TBD
  PatchCore/       # PatchCore baseline — repo URL TBD
  WinCLIP/         # WinCLIP baseline — repo URL TBD
  AnomalyCLIP/     # AnomalyCLIP baseline — repo URL TBD
```

## Baseline registry

See `experiments/configs/baselines.yaml` for the full registry including `local_path`, `repo_url`, `commit_hash`, `checkpoint_path`, `setup_command`, and `smoke_command`.

All `repo_url` and `commit_hash` values are **TBD** until explicitly researched and pinned in a later step.

## Notes

- All paths under `external/` are gitignored except this README.
- Do not commit cloned baseline repositories.
- Wrapper stubs live in `experiments/baselines/` and will raise a clear setup error until a real baseline is cloned and configured.
- Use `bash scripts/setup_baselines.sh` to see per-baseline clone instructions.
