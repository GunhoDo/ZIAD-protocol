# data/

Real datasets are NOT committed to this repository. Place them here locally.

## Expected layout

```
data/
  mvtec_ad/        # MVTec Anomaly Detection dataset
    bottle/
    cable/
    ...            # one subdirectory per category
  visa/            # VisA dataset
    candle/
    capsules/
    ...            # one subdirectory per category
```

## Download

- **MVTec AD**: https://www.mvtec.com/company/research/datasets/mvtec-ad
- **VisA**: https://github.com/amazon-science/spot-diff (follow dataset release instructions)

## Notes

- All paths under `data/` are gitignored except this README.
- The smoke run targets `data/mvtec_ad/bottle/` by default (configurable in `experiments/configs/smoke.yaml`).
- Real data must be present before running first success gate A.
