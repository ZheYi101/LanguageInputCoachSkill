#!/usr/bin/env python3
"""Safely write a JSON state file for english-input-coach."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")


def read_payload(input_file: str | None) -> str:
    if input_file:
        return Path(input_file).read_text(encoding="utf-8-sig")
    return sys.stdin.read().lstrip("\ufeff")


def validate_json_file(path: Path) -> None:
    with path.open("r", encoding="utf-8-sig") as handle:
        json.load(handle)


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely write a JSON state file.")
    parser.add_argument("target", help="Target JSON file path.")
    parser.add_argument("--input-file", help="Read JSON payload from a UTF-8 file instead of stdin.")
    args = parser.parse_args()

    target = Path(args.target)
    payload = read_payload(args.input_file)
    data = json.loads(payload)

    target.parent.mkdir(parents=True, exist_ok=True)
    backup = target.with_suffix(target.suffix + ".bak")
    temp = target.with_suffix(target.suffix + ".tmp")

    with temp.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    validate_json_file(temp)

    if target.exists():
        os.replace(target, backup)
    os.replace(temp, target)
    validate_json_file(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
