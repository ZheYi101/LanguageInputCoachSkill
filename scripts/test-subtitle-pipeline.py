#!/usr/bin/env python3
"""Fixture tests for the Python subtitle pipeline."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from subtitle_pipeline import build_normalized_payload, ingest_single_file, render_single_file


FIXTURES_DIR = Path(__file__).resolve().parent / "test-fixtures"
SCRIPTS_DIR = Path(__file__).resolve().parent


def test_basic_srt() -> None:
    payload = build_normalized_payload(FIXTURES_DIR / "basic-srt.srt")
    assert payload["source"]["subtitle_format"] == "srt"
    assert payload["stats"]["rawCueCount"] == 2
    assert payload["stats"]["cleanedUtteranceCount"] == 2
    assert payload["stats"]["droppedNoiseCount"] == 1
    assert "Hello there." in payload["paragraphs"][0]


def test_rolling_vtt() -> None:
    payload = build_normalized_payload(FIXTURES_DIR / "rolling-vtt.vtt")
    assert payload["source"]["subtitle_format"] == "vtt"
    assert payload["stats"]["rawCueCount"] == 3
    assert payload["stats"]["cleanedUtteranceCount"] == 2
    assert "1796 at the height of the French" in payload["cleaned_utterances"][0]["text"]


def test_multiline_vtt() -> None:
    payload = build_normalized_payload(FIXTURES_DIR / "multiline-vtt.vtt")
    assert payload["source"]["subtitle_format"] == "vtt"
    assert "Hello there. General Kenobi." in payload["cleaned_utterances"][0]["text"]


def test_basic_ass() -> None:
    payload = build_normalized_payload(FIXTURES_DIR / "basic-ass.ass")
    assert payload["source"]["subtitle_format"] == "ass"
    assert payload["stats"]["cleanedUtteranceCount"] == 2
    assert "This is styled text and a second line." in payload["cleaned_utterances"][0]["text"]


def test_render_from_normalized() -> None:
    with tempfile.TemporaryDirectory(prefix="subtitle-render-") as temp_dir:
        payload = build_normalized_payload(FIXTURES_DIR / "rolling-vtt.vtt")
        normalized_path = Path(temp_dir) / "rolling-vtt.normalized-subtitle.json"
        normalized_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        summary = render_single_file(normalized_path, track="article_reading", emit_txt=False, output_dir=temp_dir)
        markdown_path = Path(summary["markdown"])
        assert markdown_path.exists()
        markdown = markdown_path.read_text(encoding="utf-8")
        assert "## Cleaned Text" in markdown
        assert "track: article_reading" in markdown


def test_ingest_into_learning_root() -> None:
    with tempfile.TemporaryDirectory(prefix="subtitle-ingest-") as temp_dir:
        learning_root = Path(temp_dir) / "learning-root"
        learning_root.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "init-learning-root.py"), str(learning_root)],
            check=True,
            capture_output=True,
            text=True,
        )
        summary = ingest_single_file(
            FIXTURES_DIR / "basic-srt.srt",
            learning_root=learning_root,
            track="live_chat",
            creator=None,
            source_url=None,
            title=None,
            emit_txt=True,
        )
        assert summary["segment_count"] >= 1
        assert (learning_root / ".language-coach" / "state.db").exists()
        assert any((learning_root / "languages" / "en" / "segments").iterdir())


def main() -> int:
    test_basic_srt()
    test_rolling_vtt()
    test_multiline_vtt()
    test_basic_ass()
    test_render_from_normalized()
    test_ingest_into_learning_root()
    print("Python subtitle pipeline tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
