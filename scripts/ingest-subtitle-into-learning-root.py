#!/usr/bin/env python3
"""Import subtitle files or normalized subtitle JSON into a learning root."""

from __future__ import annotations

import argparse
import json
import sys

from subtitle_pipeline import collect_input_files, ingest_single_file


sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import subtitle files into a persistent learning root.")
    parser.add_argument("inputs", nargs="*", help="Subtitle files, normalized JSON files, directories, or nothing when --manifest is used.")
    parser.add_argument("--learning-root", required=True)
    parser.add_argument("--track", default="live_chat", choices=["live_chat", "article_reading"])
    parser.add_argument("--creator")
    parser.add_argument("--source-url")
    parser.add_argument("--title")
    parser.add_argument("--manifest")
    parser.add_argument("--recursive", action="store_true")
    parser.add_argument("--emit-txt", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        raw_inputs = collect_input_files(
            input_paths=args.inputs,
            manifest_path=args.manifest,
            recursive=args.recursive,
            normalized=False,
        )
        normalized_inputs = collect_input_files(
            input_paths=args.inputs,
            manifest_path=args.manifest,
            recursive=args.recursive,
            normalized=True,
        )
        input_files = []
        seen = set()
        for path in [*raw_inputs, *normalized_inputs]:
            if path not in seen:
                seen.add(path)
                input_files.append(path)
        if not input_files:
            raise ValueError("No subtitle files found to ingest.")
        summaries = [
            ingest_single_file(
                path,
                learning_root=args.learning_root,
                track=args.track,
                creator=args.creator,
                source_url=args.source_url,
                title=args.title,
                emit_txt=args.emit_txt,
            )
            for path in input_files
        ]
        print(json.dumps(summaries, ensure_ascii=False, indent=2))
        return 0
    except Exception as error:  # noqa: BLE001
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
