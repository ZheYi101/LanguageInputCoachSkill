#!/usr/bin/env python3
"""One-command shortcut to clean subtitle files into lesson-ready transcript artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from subtitle_pipeline import (
    build_markdown,
    clean_subtitle,
    collect_input_files,
    detect_subtitle_format,
    ensure_directory,
    extract_source_id,
    strip_subtitle_extension,
    to_ascii_label,
)


sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean subtitle files into lesson-ready transcript artifacts.")
    parser.add_argument("inputs", nargs="*", help="Subtitle files, directories, or nothing when --manifest is used.")
    parser.add_argument("--track", default="live_chat", choices=["live_chat", "article_reading"])
    parser.add_argument("--output-dir")
    parser.add_argument("--manifest")
    parser.add_argument("--recursive", action="store_true")
    parser.add_argument("--emit-txt", action="store_true")
    return parser.parse_args(argv)


def clean_single_file(input_path: Path, args: argparse.Namespace) -> dict:
    resolved_input = input_path.resolve()
    stem = strip_subtitle_extension(resolved_input.name)
    output_base_dir = Path(args.output_dir).resolve() if args.output_dir else resolved_input.parent
    ensure_directory(output_base_dir)
    base_prefix = output_base_dir / stem
    raw_text = resolved_input.read_text(encoding="utf-8")
    format_name = detect_subtitle_format(raw_text, resolved_input)
    result = clean_subtitle(raw_text, format_name=format_name)
    source_id = extract_source_id(resolved_input.name)
    source_label = to_ascii_label(stem) or source_id
    markdown = build_markdown(
        {
            "title": stem,
            "sourceId": source_id,
            "sourceLabel": source_label,
            "track": args.track,
            "materialType": "subtitle_transcript",
        },
        result["paragraphs"],
        result["stats"],
    )
    markdown_path = Path(f"{base_prefix}.lesson-ready.en.md")
    markdown_path.write_text(markdown, encoding="utf-8")
    plain_text_path: str | None = None
    if args.emit_txt:
        plain_text_path = f"{base_prefix}.lesson-ready.en.txt"
        Path(plain_text_path).write_text(f"{chr(10).join(result['paragraphs']).strip()}\n", encoding="utf-8")
    return {
        "input": str(resolved_input),
        "plain_text": plain_text_path,
        "markdown": str(markdown_path),
        "track": args.track,
        "raw_cues": result["stats"]["rawCueCount"],
        "cleaned_utterances": result["stats"]["cleanedUtteranceCount"],
        "merged_cross_cue_continuations": result["stats"]["mergedCueCount"],
        "removed_exact_repeats": result["stats"]["dedupedCount"],
        "dropped_noise_cues": result["stats"]["droppedNoiseCount"],
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
            raise ValueError("No subtitle files found to clean.")
        summaries = [clean_single_file(path, args) for path in input_files]
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
