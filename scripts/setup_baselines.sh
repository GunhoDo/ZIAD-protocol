#!/usr/bin/env bash
# Setup baseline clone directories for CLIP ZSAD P0 experiments.
# Repo URLs and commits are TBD — this script creates directory slots
# and prints clone instructions; it does NOT pretend URLs are pinned.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "=== Baseline Setup: CLIP ZSAD P0 ==="
echo ""
echo "Expected baseline directories (external/ is gitignored):"
echo ""

for BASELINE in RareCLIP PatchCore WinCLIP AnomalyCLIP; do
  TARGET="external/${BASELINE}"
  if [ -d "$TARGET" ]; then
    echo "  [FOUND]   ${TARGET}"
  else
    echo "  [MISSING] ${TARGET}"
    echo "            Repo URL/commit: TBD — see experiments/configs/baselines.yaml"
    echo "            Once URL is pinned, clone with:"
    echo "              git clone <REPO_URL> ${TARGET}"
    echo "              cd ${TARGET} && git checkout <COMMIT_HASH>"
    echo ""
  fi
done

echo ""
echo "NOTE: Repo URLs and commit hashes remain TBD until explicitly researched and"
echo "      pinned. Do not clone from unverified sources."
echo ""
echo "See experiments/configs/baselines.yaml for the full registry."
echo "See docs/experiment-prd.md for the Runnable now / TBD later status."
