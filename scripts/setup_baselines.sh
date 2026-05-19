#!/usr/bin/env bash
# Report baseline clone directories for CLIP ZSAD P0 experiments.
# The current project registry pins repo URLs and commits from local clones, but
# this script does not clone, checkout, or modify external repositories.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "=== Baseline Setup: CLIP ZSAD P0 ==="
echo ""
echo "Expected baseline directories (external/ is gitignored):"
echo ""

BASELINES=(RareCLIP PatchCore WinCLIP AnomalyCLIP)
PATHS=(external/RareCLIP external/patchcore-inspection external/WinClip external/AnomalyCLIP)
URLS=(
  https://github.com/hjf02/RareCLIP.git
  https://github.com/amazon-science/patchcore-inspection.git
  https://github.com/caoyunkang/WinClip.git
  https://github.com/zqhang/AnomalyCLIP.git
)
COMMITS=(
  a8e6d46ee2612a0edbf48c3b88e9998497e2b422
  fcaa92f124fb1ad74a7acf56726decd4b27cbcad
  a2ee822d77d01fb7beaed54314e61fe34d5027a4
  3911738c0867544f545a076ad78f3f11d9ecbfdf
)

for i in "${!BASELINES[@]}"; do
  BASELINE="${BASELINES[$i]}"
  TARGET="${PATHS[$i]}"
  URL="${URLS[$i]}"
  COMMIT="${COMMITS[$i]}"
  if [ -d "$TARGET/.git" ]; then
    ORIGIN="$(git -C "$TARGET" remote get-url origin 2>/dev/null || echo unknown)"
    HEAD="$(git -C "$TARGET" rev-parse HEAD 2>/dev/null || echo unknown)"
    echo "  [FOUND]   ${BASELINE}: ${TARGET}"
    echo "            origin: ${ORIGIN}"
    echo "            HEAD:   ${HEAD}"
  elif [ -d "$TARGET" ]; then
    echo "  [FOUND]   ${BASELINE}: ${TARGET} (not a git clone)"
  else
    echo "  [MISSING] ${BASELINE}: ${TARGET}"
    echo "            git clone ${URL} ${TARGET}"
    echo "            cd ${TARGET} && git checkout ${COMMIT}"
  fi
  echo ""
done

echo "See experiments/configs/baselines.yaml for the full registry."
echo "See docs/experiment-prd.md for gates and remaining wrapper/data/checkpoint status."
