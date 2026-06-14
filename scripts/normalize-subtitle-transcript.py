#!/usr/bin/env python3
"""Normalize subtitle files into structured JSON artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from subtitle_pipeline import build_normalized_payload, collect_input_files, ensure_directory, strip_subtitle_extension


sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Normalize subtitle files into normalized-subtitle JSON artifacts."
    )
    parser.add_argument("inputs", nargs="*", help="Subtitle files, directories, or nothing when --manifest is used.")
    parser.add_argument("--output-dir")
    parser.add_argument("--manifest")
    parser.add_argument("--recursive", action="store_true")
    return parser.parse_args(argv)


def normalize_single_file(input_path: Path, output_dir: str | None) -> dict:
    payload = build_normalized_payload(input_path)
    output_base_dir = Path(output_dir).resolve() if output_dir else input_path.resolve().parent
    ensure_directory(output_base_dir)
    output_path = output_base_dir / f"{strip_subtitle_extension(input_path.name)}.normalized-subtitle.json"
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "input": str(input_path.resolve()),
        "normalized": str(output_path),
        "subtitle_format": payload["source"]["subtitle_format"],
        "raw_cues": payload["stats"]["rawCueCount"],
        "cleaned_utterances": payload["stats"]["cleanedUtteranceCount"],
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        input_files = collect_input_files(
            input_paths=args.inputs,
            manifest_path=args.manifest,
            recursive=args.recursive,
            normalized=False,
        )
        if not input_files:
            raise ValueError("No subtitle files found to normalize.")
        summaries = [normalize_single_file(path, args.output_dir) for path in input_files]
        for summary in summaries:
            print(f"Wrote {summary['normalized']}")
        print(json.dumps(summaries, ensure_ascii=False, indent=2))
        return 0
    except Exception as error:  # noqa: BLE001
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
