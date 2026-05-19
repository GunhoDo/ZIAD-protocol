#!/usr/bin/env python3
"""Minimal metadata placeholder/validator for the CLIP ZSAD paper pipeline.

This script intentionally does not fabricate dataset contents. It only writes a
schema placeholder so the reduced pipeline has a stable contract before real
MVTec AD / VisA paths are configured.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

REQUIRED_KEYS = {"image_path", "label", "category", "mask_path"}


def write_placeholder(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": "placeholder",
        "note": "TODO: replace with real MVTec AD / VisA metadata before measuring results.",
        "schema": sorted(REQUIRED_KEYS),
        "records": [],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def validate(path: Path) -> None:
    payload = json.loads(path.read_text())
    records = payload.get("records", []) if isinstance(payload, dict) else payload
    if not isinstance(records, list):
        raise SystemExit(f"metadata records must be a list: {path}")
    for idx, record in enumerate(records):
        missing = REQUIRED_KEYS - set(record)
        if missing:
            raise SystemExit(f"record {idx} missing keys: {sorted(missing)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="results/latest/metadata.json")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    path = Path(args.output)
    if args.validate and path.exists():
        validate(path)
    else:
        write_placeholder(path)
    print(path)


if __name__ == "__main__":
    main()
