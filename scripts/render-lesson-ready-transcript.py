#!/usr/bin/env python3
"""Render lesson-ready Markdown from normalized subtitle JSON files."""

from __future__ import annotations

import argparse
import json
import sys

from subtitle_pipeline import collect_input_files, render_single_file


sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render lesson-ready transcript artifacts from normalized subtitle JSON.")
    parser.add_argument("inputs", nargs="*", help="Normalized JSON files, directories, or nothing when --manifest is used.")
    parser.add_argument("--track", required=True, choices=["live_chat", "article_reading"])
    parser.add_argument("--emit-txt", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--manifest")
    parser.add_argument("--recursive", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        input_files = collect_input_files(
            input_paths=args.inputs,
            manifest_path=args.manifest,
            recursive=args.recursive,
            normalized=True,
        )
        if not input_files:
            raise ValueError("No normalized subtitle files found to render.")
        summaries = [
            render_single_file(path, track=args.track, emit_txt=args.emit_txt, output_dir=args.output_dir)
            for path in input_files
        ]
        for summary in summaries:
            if summary["plain_text"]:
                print(f"Wrote {summary['plain_text']}")
            print(f"Wrote {summary['markdown']}")
        print(json.dumps(summaries, ensure_ascii=False, indent=2))
        return 0
    except Exception as error:  # noqa: BLE001
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
