#!/usr/bin/env python3
"""Shared subtitle cleaning and import helpers for input-driven-language-coach."""

from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


SUPPORTED_EXTENSIONS = {".srt", ".vtt", ".ass", ".ssa"}
NORMALIZED_SUFFIX_RE = re.compile(
    r"\.normalized-subtitle(?:\.[a-z]{2}(?:-[A-Za-z]+)?)?\.json$",
    re.IGNORECASE,
)


def ensure_directory(directory_path: str | Path) -> None:
    Path(directory_path).mkdir(parents=True, exist_ok=True)


def sort_paths(paths: Iterable[Path]) -> list[Path]:
    return sorted(paths, key=lambda item: str(item).lower())


def is_supported_subtitle_file(file_path: str | Path) -> bool:
    return Path(file_path).suffix.lower() in SUPPORTED_EXTENSIONS


def is_supported_normalized_file(file_path: str | Path) -> bool:
    return bool(NORMALIZED_SUFFIX_RE.search(Path(file_path).name))


def read_manifest(manifest_path: str | Path) -> list[Path]:
    manifest_path = Path(manifest_path).resolve()
    manifest_dir = manifest_path.parent
    entries: list[Path] = []
    for raw_line in manifest_path.read_text(encoding="utf-8").replace("\r\n", "\n").split("\n"):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        candidate = Path(line)
        entries.append(candidate if candidate.is_absolute() else (manifest_dir / candidate).resolve())
    return entries


def collect_files_from_directory(directory_path: str | Path, recursive: bool, *, normalized: bool = False) -> list[Path]:
    directory = Path(directory_path).resolve()
    collected: list[Path] = []
    for entry in sort_paths(directory.iterdir()):
        if entry.is_dir():
            if recursive:
                collected.extend(collect_files_from_directory(entry, recursive, normalized=normalized))
            continue
        if normalized:
            if is_supported_normalized_file(entry):
                collected.append(entry.resolve())
        else:
            if is_supported_subtitle_file(entry):
                collected.append(entry.resolve())
    return collected


def collect_input_files(
    *,
    input_paths: list[str],
    manifest_path: str | None,
    recursive: bool,
    normalized: bool = False,
) -> list[Path]:
    collected: list[Path] = []
    seen: set[Path] = set()

    def add_file(candidate_path: str | Path) -> None:
        resolved_path = Path(candidate_path).resolve()
        if not resolved_path.exists():
            raise FileNotFoundError(f"Input does not exist: {resolved_path}")
        if resolved_path.is_dir():
            for nested_file in collect_files_from_directory(resolved_path, recursive, normalized=normalized):
                add_file(nested_file)
            return
        if normalized:
            if not is_supported_normalized_file(resolved_path):
                return
        else:
            if not is_supported_subtitle_file(resolved_path):
                return
        if resolved_path not in seen:
            seen.add(resolved_path)
            collected.append(resolved_path)

    if manifest_path:
        for manifest_entry in read_manifest(manifest_path):
            add_file(manifest_entry)

    for input_path in input_paths:
        add_file(input_path)

    return collected


def decode_html_entities(text: str) -> str:
    return (
        text.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
    )


def strip_cue_markup(text: str) -> str:
    cleaned = decode_html_entities(
        re.sub(r"<[^>]+>", " ",
            re.sub(r"</?(?:i|b|u|ruby|rt|lang)[^>]*>", " ",
                re.sub(r"</v>", " ",
                    re.sub(r"<v\s+([^>]+)>", r"\1: ",
                        re.sub(r"</?c(?:\.[^>]*)?>", " ",
                            re.sub(r"<\d{2}:\d{2}:\d{2}\.\d{3}>", " ", text)
                        ),
                    ),
                ),
            ),
        )
    )
    return re.sub(r"\s+", " ", cleaned).strip()


def strip_ass_markup(text: str) -> str:
    cleaned = decode_html_entities(
        re.sub(r"\\[Nnh]", " ",
            re.sub(r"\{[^}]*\}", " ", text),
        )
    )
    return re.sub(r"\s+", " ", cleaned).strip()


def normalize_cue_text(lines: list[str]) -> str:
    uses_rolling_markup = any(
        re.search(r"<\d{2}:\d{2}:\d{2}\.\d{3}>", line) or re.search(r"</?c(?:\.[^>]*)?>", line, re.IGNORECASE)
        for line in lines
    )
    normalized_lines = [strip_cue_markup(line) for line in lines]
    normalized_lines = [line for line in normalized_lines if line]
    if not normalized_lines:
        return ""
    if uses_rolling_markup and len(normalized_lines) > 1:
        current_text = normalized_lines[0]
        for line in normalized_lines[1:]:
            current_text = merge_texts(current_text, line)
        return current_text
    return re.sub(r"\s+", " ", " ".join(normalized_lines)).strip()


def is_ignorable_noise(text: str) -> bool:
    normalized = text.strip().lower()
    return normalized in {"[music]", "(music)", "[applause]", "(applause)", "[laughter]", "(laughter)"}


def parse_timestamp(timestamp: str) -> float | None:
    match = re.match(
        r"^(?:(?P<hours>\d{2,}):)?(?P<minutes>\d{2}):(?P<seconds>\d{2})[,.](?P<millis>\d{3})$",
        timestamp.strip(),
    )
    if not match:
        return None
    hours = int(match.group("hours") or "0")
    minutes = int(match.group("minutes"))
    seconds = int(match.group("seconds"))
    millis = int(match.group("millis"))
    return hours * 3600 + minutes * 60 + seconds + millis / 1000


def parse_ass_timestamp(timestamp: str) -> float | None:
    match = re.match(r"^(?P<hours>\d+):(?P<minutes>\d{2}):(?P<seconds>\d{2})\.(?P<centis>\d{2})$", timestamp.strip())
    if not match:
        return None
    hours = int(match.group("hours"))
    minutes = int(match.group("minutes"))
    seconds = int(match.group("seconds"))
    centis = int(match.group("centis"))
    return hours * 3600 + minutes * 60 + seconds + centis / 100


def parse_time_line(time_line: str) -> tuple[float, float] | None:
    if "-->" not in time_line:
        return None
    start_raw, end_and_settings_raw = time_line.split("-->", 1)
    end_raw = end_and_settings_raw.strip().split()[0]
    start = parse_timestamp(start_raw)
    end = parse_timestamp(end_raw)
    if start is None or end is None:
        return None
    return start, end


def ends_with_strong_stop(text: str) -> bool:
    return bool(re.search(r"[.!?][\"')\]]*$", text))


def ends_with_soft_stop(text: str) -> bool:
    return bool(re.search(r"[,;:][\"')\]]*$", text))


def starts_with_continuation(text: str) -> bool:
    return bool(
        re.match(
            r"^(and|but|so|because|if|when|which|that|to|or|then|than|as|while|though|although|unless|until|for|with|without|where|who|whose|whom|what|how)\b",
            text,
            re.IGNORECASE,
        )
    )


def tokenize_for_overlap(text: str) -> list[str]:
    return [token.strip() for token in re.split(r"\s+", text) if token.strip()]


def find_leading_word_overlap(previous_text: str, current_text: str) -> int:
    previous_words = tokenize_for_overlap(previous_text)
    current_words = tokenize_for_overlap(current_text)
    max_overlap = min(len(previous_words), len(current_words))
    for size in range(max_overlap, 0, -1):
        previous_slice = " ".join(previous_words[-size:]).lower()
        current_slice = " ".join(current_words[:size]).lower()
        if previous_slice == current_slice:
            return size
    return 0


def remove_leading_overlap(previous_text: str, current_text: str) -> str:
    if not previous_text:
        return current_text
    if previous_text.lower().endswith(current_text.lower()):
        return ""
    overlap_size = find_leading_word_overlap(previous_text, current_text)
    if overlap_size == 0:
        return current_text
    return " ".join(tokenize_for_overlap(current_text)[overlap_size:]).strip()


def should_merge_across_cues(previous_text: str, current_text: str) -> bool:
    if not previous_text:
        return False
    if ends_with_strong_stop(previous_text):
        return False
    if ends_with_soft_stop(previous_text):
        return True
    if re.match(r"^[a-z]", current_text):
        return True
    if starts_with_continuation(current_text):
        return True
    previous_word_count = len([token for token in re.split(r"\s+", previous_text) if token])
    return previous_word_count <= 4 and bool(re.match(r"^[a-zA-Z]", current_text))


def merge_texts(previous_text: str, current_text: str) -> str:
    incremental_text = remove_leading_overlap(previous_text, current_text)
    if not incremental_text:
        return previous_text
    return re.sub(r"\s+", " ", f"{previous_text} {incremental_text}").strip()


def format_seconds(total_seconds: float) -> str:
    whole_seconds = int(total_seconds)
    hours = str(whole_seconds // 3600).zfill(2)
    minutes = str((whole_seconds % 3600) // 60).zfill(2)
    seconds = str(whole_seconds % 60).zfill(2)
    return f"{hours}:{minutes}:{seconds}"


@dataclass
class Utterance:
    start: float
    end: float
    text: str


def parse_ass_dialogue_fields(content: str, format_fields: list[str]) -> list[str]:
    values: list[str] = []
    remaining = content
    for _ in range(len(format_fields) - 1):
        comma_index = remaining.find(",")
        if comma_index == -1:
            values.append(remaining.strip())
            remaining = ""
        else:
            values.append(remaining[:comma_index].strip())
            remaining = remaining[comma_index + 1 :]
    values.append(remaining.strip())
    return values


def build_parsed_utterances_from_ass(raw_text: str) -> tuple[list[Utterance], int]:
    lines = raw_text.replace("\r\n", "\n").split("\n")
    in_events_section = False
    event_format: list[str] | None = None
    parsed_utterances: list[Utterance] = []
    dropped_noise_count = 0
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        if re.match(r"^\[events\]$", line, re.IGNORECASE):
            in_events_section = True
            continue
        if re.match(r"^\[.+\]$", line) and not re.match(r"^\[events\]$", line, re.IGNORECASE):
            in_events_section = False
            continue
        if not in_events_section:
            continue
        if re.match(r"^format:", line, re.IGNORECASE):
            event_format = [field.strip().lower() for field in re.sub(r"^format:", "", line, flags=re.IGNORECASE).split(",")]
            continue
        if not re.match(r"^dialogue:", line, re.IGNORECASE) or not event_format:
            continue
        values = parse_ass_dialogue_fields(re.sub(r"^dialogue:", "", line, flags=re.IGNORECASE).strip(), event_format)
        if len(values) != len(event_format):
            continue
        field_map = dict(zip(event_format, values))
        start = parse_ass_timestamp(field_map.get("start", ""))
        end = parse_ass_timestamp(field_map.get("end", ""))
        if start is None or end is None:
            continue
        text = strip_ass_markup(field_map.get("text", ""))
        if not text or is_ignorable_noise(text):
            dropped_noise_count += 1
            continue
        parsed_utterances.append(Utterance(start=start, end=end, text=text))
    return parsed_utterances, dropped_noise_count


def build_parsed_utterances_from_srt_or_vtt(raw_text: str) -> tuple[list[Utterance], int]:
    blocks = re.split(r"\n{2,}", raw_text.replace("\r\n", "\n"))
    parsed_utterances: list[Utterance] = []
    dropped_noise_count = 0
    for block in blocks:
        lines = [line.strip() for line in block.split("\n")]
        lines = [line for line in lines if line]
        if len(lines) < 2:
            continue
        pointer = 0
        if re.match(r"^\d+$", lines[pointer]):
            pointer += 1
        if pointer + 1 < len(lines) and "-->" not in lines[pointer] and "-->" in lines[pointer + 1]:
            pointer += 1
        time_line = lines[pointer]
        parsed_time = parse_time_line(time_line)
        if not parsed_time:
            continue
        text_lines = lines[pointer + 1 :]
        if not text_lines:
            continue
        text = normalize_cue_text(text_lines)
        if not text or is_ignorable_noise(text):
            dropped_noise_count += 1
            continue
        parsed_utterances.append(Utterance(start=parsed_time[0], end=parsed_time[1], text=text))
    return parsed_utterances, dropped_noise_count


def detect_subtitle_format(raw_text: str, input_path: str | Path = "") -> str:
    extension = Path(input_path).suffix.lower()
    if extension == ".vtt":
        return "vtt"
    if extension == ".ass":
        return "ass"
    if extension == ".ssa":
        return "ssa"
    if re.match(r"^\ufeff?WEBVTT\b", raw_text.lstrip(), re.IGNORECASE):
        return "vtt"
    return "srt"


def build_paragraph_records(cleaned_utterances: list[Utterance]) -> list[dict]:
    paragraphs: list[dict] = []
    current: list[Utterance] = []
    current_word_count = 0
    for index, utterance in enumerate(cleaned_utterances):
        previous = cleaned_utterances[index - 1] if index > 0 else None
        gap = utterance.start - previous.end if previous else 0
        if current and gap >= 8:
            paragraphs.append(
                {
                    "start": current[0].start,
                    "end": current[-1].end,
                    "text": " ".join(item.text for item in current),
                    "wordCount": current_word_count,
                }
            )
            current = []
            current_word_count = 0
        current.append(utterance)
        current_word_count += len([token for token in re.split(r"\s+", utterance.text) if token])
        if current_word_count >= 85 and ends_with_strong_stop(utterance.text):
            paragraphs.append(
                {
                    "start": current[0].start,
                    "end": current[-1].end,
                    "text": " ".join(item.text for item in current),
                    "wordCount": current_word_count,
                }
            )
            current = []
            current_word_count = 0
            continue
        if current_word_count >= 140:
            paragraphs.append(
                {
                    "start": current[0].start,
                    "end": current[-1].end,
                    "text": " ".join(item.text for item in current),
                    "wordCount": current_word_count,
                }
            )
            current = []
            current_word_count = 0
    if current:
        paragraphs.append(
            {
                "start": current[0].start,
                "end": current[-1].end,
                "text": " ".join(item.text for item in current),
                "wordCount": current_word_count,
            }
        )
    return paragraphs


def build_paragraphs(cleaned_utterances: list[Utterance]) -> list[str]:
    return [paragraph["text"] for paragraph in build_paragraph_records(cleaned_utterances)]


def clean_subtitle(raw_text: str, *, format_name: str | None = None) -> dict:
    format_name = format_name or "srt"
    if format_name in {"ass", "ssa"}:
        parsed_utterances, dropped_noise_count = build_parsed_utterances_from_ass(raw_text)
    else:
        parsed_utterances, dropped_noise_count = build_parsed_utterances_from_srt_or_vtt(raw_text)

    cleaned_utterances: list[Utterance] = []
    deduped_count = 0
    merged_cue_count = 0
    for utterance in parsed_utterances:
        previous = cleaned_utterances[-1] if cleaned_utterances else None
        if previous is None:
            cleaned_utterances.append(Utterance(**utterance.__dict__))
            continue
        if previous.text.lower() == utterance.text.lower():
            previous.end = utterance.end
            deduped_count += 1
            continue
        overlap_size = find_leading_word_overlap(previous.text, utterance.text)
        incremental_text = remove_leading_overlap(previous.text, utterance.text)
        if not incremental_text:
            previous.end = utterance.end
            deduped_count += 1
            continue
        if (overlap_size > 0 and not ends_with_strong_stop(previous.text)) or should_merge_across_cues(previous.text, incremental_text):
            previous.text = merge_texts(previous.text, incremental_text)
            previous.end = utterance.end
            merged_cue_count += 1
            continue
        cleaned_utterances.append(Utterance(start=utterance.start, end=utterance.end, text=incremental_text))

    paragraph_records = build_paragraph_records(cleaned_utterances)
    paragraphs = [paragraph["text"] for paragraph in paragraph_records]
    return {
        "cleanedUtterances": [utterance.__dict__ for utterance in cleaned_utterances],
        "paragraphRecords": paragraph_records,
        "paragraphs": paragraphs,
        "stats": {
            "format": format_name,
            "rawCueCount": len(parsed_utterances),
            "cleanedUtteranceCount": len(cleaned_utterances),
            "dedupedCount": deduped_count,
            "mergedCueCount": merged_cue_count,
            "droppedNoiseCount": dropped_noise_count,
            "start": cleaned_utterances[0].start if cleaned_utterances else 0,
            "end": cleaned_utterances[-1].end if cleaned_utterances else 0,
        },
    }


def extract_source_id(file_name: str) -> str:
    match = re.search(r"\[([A-Za-z0-9_-]+)\](?=[^\[]*$)", file_name)
    if match:
        return match.group(1)
    return re.sub(r"(?:\.[a-z]{2}(?:-[A-Za-z]+)?)+$", "", Path(file_name).stem, flags=re.IGNORECASE)


def to_ascii_label(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\x20-\x7E]+", " ", text)).strip()


def strip_subtitle_extension(file_name: str) -> str:
    return re.sub(r"(?:\.[a-z]{2}(?:-[A-Za-z]+)?)?\.(?:srt|vtt|ass|ssa)$", "", file_name, flags=re.IGNORECASE)


def build_markdown(metadata: dict, paragraphs: list[str], stats: dict) -> str:
    lines = [
        "# Lesson-Ready Transcript",
        "",
        "- input_type: transcript",
        f"- track: {metadata.get('track', 'live_chat')}",
        f"- material_type: {metadata.get('materialType', 'subtitle_transcript')}",
        f"- title: {metadata['title']}",
        f"- source_id: {metadata['sourceId']}",
        f"- source_label: {metadata['sourceLabel']}",
        f"- cleaned_span: {format_seconds(stats.get('start', 0))}-{format_seconds(stats.get('end', 0))}",
        f"- cleaning_summary: {metadata.get('cleaningSummary', 'removed subtitle indices, timestamps, and subtitle markup; merged wrapped lines; merged likely cross-cue continuations; dropped exact duplicate cue repeats where present')}",
        "",
        "## Cleaned Text",
        "",
    ]
    for paragraph in paragraphs:
        lines.append(paragraph)
        lines.append("")
    lines.extend(
        [
            "## Cleaning Stats",
            "",
            f"- subtitle_format: {stats.get('format')}",
            f"- raw_cues: {stats.get('rawCueCount')}",
            f"- cleaned_utterances: {stats.get('cleanedUtteranceCount')}",
            f"- merged_cross_cue_continuations: {stats.get('mergedCueCount')}",
            f"- removed_exact_repeats: {stats.get('dedupedCount')}",
            f"- dropped_noise_cues: {stats.get('droppedNoiseCount')}",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def build_cleaning_summary() -> str:
    return "removed subtitle indices, timestamps, and subtitle markup; merged wrapped lines; merged likely cross-cue continuations; dropped exact duplicate cue repeats where present"


def build_normalized_payload(input_path: str | Path) -> dict:
    resolved_input = Path(input_path).resolve()
    input_file_name = resolved_input.name
    raw_text = resolved_input.read_text(encoding="utf-8")
    format_name = detect_subtitle_format(raw_text, resolved_input)
    cleaned = clean_subtitle(raw_text, format_name=format_name)
    stem = strip_subtitle_extension(input_file_name)
    source_id = extract_source_id(input_file_name)
    return {
        "schema_version": 1,
        "kind": "normalized_subtitle_transcript",
        "source": {
            "input_path": str(resolved_input),
            "file_name": input_file_name,
            "stem": stem,
            "source_id": source_id,
            "source_label": to_ascii_label(stem) or source_id,
            "subtitle_format": format_name,
        },
        "cleaning_summary": build_cleaning_summary(),
        "cleaned_utterances": cleaned["cleanedUtterances"],
        "paragraph_records": cleaned["paragraphRecords"],
        "paragraphs": cleaned["paragraphs"],
        "stats": cleaned["stats"],
    }


def load_normalized_payload(input_path: str | Path) -> dict:
    resolved_input = Path(input_path).resolve()
    payload = json.loads(resolved_input.read_text(encoding="utf-8"))
    if payload.get("kind") != "normalized_subtitle_transcript":
        raise ValueError(f"Unsupported normalized payload: {resolved_input}")
    return payload


def lesson_ready_base_prefix(input_path: str | Path, payload: dict, output_dir: str | None) -> Path:
    resolved_input = Path(input_path).resolve()
    input_file_name = resolved_input.name
    default_stem = (
        payload.get("source", {}).get("stem")
        or strip_subtitle_extension(payload.get("source", {}).get("file_name", ""))
        or NORMALIZED_SUFFIX_RE.sub("", input_file_name)
    )
    output_base_dir = Path(output_dir).resolve() if output_dir else resolved_input.parent
    ensure_directory(output_base_dir)
    return output_base_dir / default_stem


def render_single_file(input_path: str | Path, *, track: str, emit_txt: bool, output_dir: str | None) -> dict:
    resolved_input = Path(input_path).resolve()
    payload = load_normalized_payload(resolved_input)
    source_id = payload.get("source", {}).get("source_id") or extract_source_id(
        payload.get("source", {}).get("file_name", resolved_input.name)
    )
    source_label = payload.get("source", {}).get("source_label") or to_ascii_label(payload.get("source", {}).get("stem", "")) or source_id
    title = payload.get("source", {}).get("stem") or source_label or source_id
    base_prefix = lesson_ready_base_prefix(resolved_input, payload, output_dir)
    markdown_path = Path(f"{base_prefix}.lesson-ready.en.md")
    markdown = build_markdown(
        {
            "title": title,
            "sourceId": source_id,
            "sourceLabel": source_label,
            "track": track,
            "materialType": "subtitle_transcript",
            "cleaningSummary": payload.get("cleaning_summary") or build_cleaning_summary(),
        },
        payload.get("paragraphs", []),
        payload.get("stats", {}),
    )
    markdown_path.write_text(markdown, encoding="utf-8")

    plain_text_path: str | None = None
    if emit_txt:
        plain_text_path = f"{base_prefix}.lesson-ready.en.txt"
        Path(plain_text_path).write_text(f"{chr(10).join(payload.get('paragraphs', [])).strip()}\n", encoding="utf-8")

    return {
        "normalized": str(resolved_input),
        "markdown": str(markdown_path),
        "plain_text": plain_text_path,
        "track": track,
    }


def clip_summary(text: str, limit: int = 160) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 1].rstrip()}..."


def summarize_live_chat_segment(text: str, index: int) -> str:
    lower = text.lower()
    if "youtube" in lower and "twitch" in lower and any(
        marker in lower for marker in ("get along", "cellmates", "behind the bars", "introduce them to each other")
    ):
        return "Opening dual-stream setup where chat platforms are framed as needing to get along."
    if any(marker in lower for marker in ("house", "mortgage", "save money")):
        return "Practical tangent about money, housing, and stream-related upgrades."
    if any(marker in lower for marker in ("illustrations", "artist", "subathon")):
        return "Planning segment about art commissions, stream events, and pending rewards."
    if any(marker in lower for marker in ("support everyone", "be nice", "penguins")):
        return "Community-values segment focused on friendliness and audience culture."
    first_sentence = re.search(r".*?[.!?](?:\s|$)", text)
    fallback = first_sentence.group(0).strip() if first_sentence else clip_summary(text, 120)
    return f"Live-chat segment {str(index).zfill(2)}: {fallback}"


def summarize_article_segment(text: str, index: int) -> str:
    first_sentence = re.search(r".*?[.!?](?:\s|$)", text)
    if first_sentence:
        return f"Argument unit {str(index).zfill(2)}: {clip_summary(first_sentence.group(0).strip(), 150)}"
    return f"Argument unit {str(index).zfill(2)}: {clip_summary(text, 150)}"


def summarize_segment(text: str, track: str, index: int) -> str:
    return summarize_article_segment(text, index) if track == "article_reading" else summarize_live_chat_segment(text, index)


def starts_with_topic_shift(text: str) -> bool:
    return bool(
        re.match(
            r"^(anyway|also|yeah,\s*so|okay|wait|but|pilates|what kind of games|there's an ankh test|are streams this time of day)",
            text,
            re.IGNORECASE,
        )
    )


def should_split_live_chat(current: list[dict], current_words: int, next_paragraph: dict, gap_seconds: float) -> bool:
    return bool(
        current
        and (
            current_words >= 460
            or (
                current_words >= 340
                and (len(current) >= 4 or gap_seconds >= 40 or (starts_with_topic_shift(next_paragraph["text"]) and len(current) >= 4))
            )
            or (current_words >= 260 and gap_seconds >= 90)
        )
    )


def should_split_article(current: list[dict], current_words: int, gap_seconds: float) -> bool:
    return bool(
        current
        and (
            current_words >= 560
            or (current_words >= 340 and len(current) >= 3)
            or (current_words >= 260 and len(current) >= 2 and gap_seconds >= 20)
        )
    )


def build_segments(paragraph_records: list[dict], *, track: str) -> list[dict]:
    segments: list[list[dict]] = []
    current: list[dict] = []
    current_words = 0
    for paragraph in paragraph_records:
        previous = current[-1] if current else None
        gap_seconds = paragraph["start"] - previous["end"] if previous else 0
        should_split = (
            should_split_article(current, current_words, gap_seconds)
            if track == "article_reading"
            else should_split_live_chat(current, current_words, paragraph, gap_seconds)
        )
        if should_split:
            segments.append(current)
            current = []
            current_words = 0
        current.append(paragraph)
        current_words += int(paragraph["wordCount"])
    if current:
        segments.append(current)
    output: list[dict] = []
    for index, group in enumerate(segments, start=1):
        text = "\n\n".join(paragraph["text"] for paragraph in group)
        output.append(
            {
                "segmentIndex": index,
                "start": group[0]["start"],
                "end": group[-1]["end"],
                "startRef": format_seconds(group[0]["start"]),
                "endRef": format_seconds(group[-1]["end"]),
                "wordCount": len([token for token in re.split(r"\s+", text) if token]),
                "text": text,
                "sceneSummary": summarize_segment(text, track, index),
            }
        )
    return output


def build_segment_markdown(segment: dict, previous_summary: str, next_summary: str, track: str) -> str:
    lines = [
        "# Transcript Segment",
        "",
        f"- track: {track}",
        f"- segment_index: {segment['segmentIndex']}",
        f"- start_ref: {segment['startRef']}",
        f"- end_ref: {segment['endRef']}",
        f"- scene_or_argument_summary: {segment['sceneSummary']}",
        f"- context_before_summary: {previous_summary}",
        f"- context_after_summary: {next_summary}",
        "",
        "## Text",
        "",
        segment["text"],
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"


def get_track_profile_update(track: str) -> dict:
    if track == "article_reading":
        return {
            "baselineSummary": "Learning profile initialized from cleaned reading-style subtitle transcript imports.",
            "priorities": [
                "argument comprehension",
                "written connector accuracy",
                "claim-support mapping",
                "summary paraphrase precision",
            ],
        }
    return {
        "baselineSummary": "Learning profile initialized from cleaned live-chat transcript imports.",
        "priorities": [
            "live_chat chunk integrity",
            "spoken scene management",
            "dual-platform chat humor",
        ],
    }


def read_json(json_path: str | Path) -> dict:
    return json.loads(Path(json_path).read_text(encoding="utf-8"))


def write_json(json_path: str | Path, payload: dict) -> None:
    Path(json_path).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update_learner_profile(profile_path: str | Path, track: str, source_summary: dict) -> None:
    profile = read_json(profile_path)
    existing = profile.get("language_profiles", {}).get("en")
    if not existing:
        return
    track_update = get_track_profile_update(track)
    existing["track_bias"] = list(dict.fromkeys([track, *(existing.get("track_bias") or [])]))
    existing["recent_priorities"] = list(dict.fromkeys([*(track_update.get("priorities") or []), *(existing.get("recent_priorities") or [])]))[:6]
    existing["last_updated_at"] = utc_now_iso()
    existing["baseline_summary"] = existing.get("baseline_summary") or track_update["baselineSummary"]
    profile["updated_at"] = utc_now_iso()
    profile["last_imported_source"] = source_summary
    write_json(profile_path, profile)


def utc_now_iso() -> str:
    import datetime as _dt

    return _dt.datetime.now(_dt.timezone.utc).isoformat().replace("+00:00", "Z")


def upsert_source(connection: sqlite3.Connection, source: dict) -> None:
    connection.execute(
        """
        INSERT INTO sources (
          id, language, material_type, track, title, source_url, creator,
          raw_path, cleaned_path, imported_at, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
          language = excluded.language,
          material_type = excluded.material_type,
          track = excluded.track,
          title = excluded.title,
          source_url = excluded.source_url,
          creator = excluded.creator,
          raw_path = excluded.raw_path,
          cleaned_path = excluded.cleaned_path,
          imported_at = excluded.imported_at,
          status = excluded.status
        """,
        (
            source["id"],
            source["language"],
            source["materialType"],
            source["track"],
            source["title"],
            source.get("sourceUrl"),
            source.get("creator"),
            source.get("rawPath"),
            source["cleanedPath"],
            source["importedAt"],
            source["status"],
        ),
    )


def replace_segments(connection: sqlite3.Connection, source_id: str, material_type: str, track: str, segments: list[dict]) -> None:
    connection.execute("DELETE FROM segments WHERE source_id = ?", (source_id,))
    for index, segment in enumerate(segments):
        previous_summary = (
            segments[index - 1]["sceneSummary"]
            if index > 0
            else ("Opening of the source argument." if track == "article_reading" else "Stream opening.")
        )
        next_summary = (
            segments[index + 1]["sceneSummary"]
            if index < len(segments) - 1
            else ("End of the current source argument sequence." if track == "article_reading" else "Segment sequence ends here.")
        )
        connection.execute(
            """
            INSERT INTO segments (
              id, source_id, material_type, track, segment_index, segment_path,
              start_ref, end_ref, context_before_summary, context_after_summary,
              scene_or_argument_summary, created_at, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                source_id,
                material_type,
                track,
                segment["segmentIndex"],
                segment["segmentPath"],
                segment["startRef"],
                segment["endRef"],
                previous_summary,
                next_summary,
                segment["sceneSummary"],
                utc_now_iso(),
                "ready",
            ),
        )


def remove_existing_segment_files(segments_dir: str | Path, source_id: str) -> None:
    segments_dir = Path(segments_dir)
    if not segments_dir.exists():
        return
    for file_path in segments_dir.iterdir():
        if file_path.is_file() and file_path.name.startswith(f"{source_id}--seg-"):
            file_path.unlink()


def copy_file(source_path: str | Path, target_path: str | Path) -> None:
    ensure_directory(Path(target_path).parent)
    shutil.copy2(source_path, target_path)


def build_ingest_source_data_from_input(input_path: str | Path) -> dict:
    resolved_input = Path(input_path).resolve()
    if is_supported_normalized_file(resolved_input):
        payload = load_normalized_payload(resolved_input)
        return {
            "sourceId": payload.get("source", {}).get("source_id") or extract_source_id(resolved_input.name),
            "stem": payload.get("source", {}).get("stem")
            or strip_subtitle_extension(payload.get("source", {}).get("file_name", ""))
            or NORMALIZED_SUFFIX_RE.sub("", resolved_input.name),
            "sourceLabel": payload.get("source", {}).get("source_label")
            or to_ascii_label(payload.get("source", {}).get("stem", ""))
            or extract_source_id(resolved_input.name),
            "subtitleFormat": payload.get("source", {}).get("subtitle_format", "unknown"),
            "cleaned": {
                "cleanedUtterances": payload.get("cleaned_utterances", []),
                "paragraphRecords": payload.get("paragraph_records", []),
                "paragraphs": payload.get("paragraphs", []),
                "stats": payload.get("stats", {}),
            },
            "rawInputPath": payload.get("source", {}).get("input_path"),
            "normalizedInputPath": str(resolved_input),
            "cleaningSummary": payload.get("cleaning_summary") or build_cleaning_summary(),
        }

    raw_text = resolved_input.read_text(encoding="utf-8")
    format_name = detect_subtitle_format(raw_text, resolved_input)
    cleaned = clean_subtitle(raw_text, format_name=format_name)
    stem = strip_subtitle_extension(resolved_input.name)
    source_id = extract_source_id(resolved_input.name)
    return {
        "sourceId": source_id,
        "stem": stem,
        "sourceLabel": to_ascii_label(stem) or source_id,
        "subtitleFormat": format_name,
        "cleaned": cleaned,
        "rawInputPath": str(resolved_input),
        "normalizedInputPath": None,
        "cleaningSummary": build_cleaning_summary(),
    }


def build_default_title(stem: str, source_id: str, track: str) -> str:
    if track == "article_reading":
        return stem or f"Article-style subtitle transcript [{source_id}]"
    return stem or f"Live chat transcript [{source_id}]"


def ingest_single_file(
    input_path: str | Path,
    *,
    learning_root: str | Path,
    track: str,
    creator: str | None,
    source_url: str | None,
    title: str | None,
    emit_txt: bool,
) -> dict:
    resolved_input = Path(input_path).resolve()
    resolved_root = Path(learning_root).resolve()
    coach_dir = resolved_root / ".language-coach"
    db_path = coach_dir / "state.db"
    if not db_path.exists():
        raise FileNotFoundError(f"Missing learning root DB: {db_path}")

    source_data = build_ingest_source_data_from_input(resolved_input)
    source_id = source_data["sourceId"]
    stem = source_data["stem"]
    source_label = source_data["sourceLabel"]
    effective_title = title or build_default_title(stem, source_id, track)
    cleaned = source_data["cleaned"]
    segments = build_segments(cleaned["paragraphRecords"], track=track)
    raw_input_path = source_data["rawInputPath"]
    raw_target_path: Path | None = None
    if raw_input_path and Path(raw_input_path).exists():
        raw_extension = Path(raw_input_path).suffix.lower() or ".txt"
        raw_target_path = resolved_root / "languages" / "en" / "raw" / f"{source_id}.en{raw_extension}"
        copy_file(raw_input_path, raw_target_path)
    cleaned_markdown_path = resolved_root / "languages" / "en" / "cleaned" / f"{source_id}.lesson-ready.en.md"
    segments_dir = resolved_root / "languages" / "en" / "segments"
    ensure_directory(cleaned_markdown_path.parent)
    cleaned_markdown_path.write_text(
        build_markdown(
            {
                "title": effective_title,
                "sourceId": source_id,
                "sourceLabel": source_label,
                "track": track,
                "materialType": "subtitle_transcript",
                "cleaningSummary": source_data["cleaningSummary"],
            },
            cleaned["paragraphs"],
            cleaned["stats"],
        ),
        encoding="utf-8",
    )
    if emit_txt:
        cleaned_text_path = resolved_root / "languages" / "en" / "cleaned" / f"{source_id}.lesson-ready.en.txt"
        cleaned_text_path.write_text(f"{chr(10).join(cleaned['paragraphs']).strip()}\n", encoding="utf-8")
    remove_existing_segment_files(segments_dir, source_id)
    persisted_segments: list[dict] = []
    for index, segment in enumerate(segments):
        previous_summary = segments[index - 1]["sceneSummary"] if index > 0 else (
            "Opening of the source argument." if track == "article_reading" else "Stream opening."
        )
        next_summary = segments[index + 1]["sceneSummary"] if index < len(segments) - 1 else (
            "End of the current source argument sequence." if track == "article_reading" else "Segment sequence ends here."
        )
        segment_file_name = f"{source_id}--seg-{str(segment['segmentIndex']).zfill(2)}.md"
        segment_path = segments_dir / segment_file_name
        ensure_directory(segment_path.parent)
        segment_path.write_text(build_segment_markdown(segment, previous_summary, next_summary, track), encoding="utf-8")
        persisted_segments.append({**segment, "segmentPath": str(segment_path)})

    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        with connection:
            upsert_source(
                connection,
                {
                    "id": source_id,
                    "language": "en",
                    "materialType": "subtitle_transcript",
                    "track": track,
                    "title": effective_title,
                    "sourceUrl": source_url,
                    "creator": creator,
                    "rawPath": str(raw_target_path) if raw_target_path else None,
                    "cleanedPath": str(cleaned_markdown_path),
                    "importedAt": utc_now_iso(),
                    "status": "active",
                },
            )
            replace_segments(connection, source_id, "subtitle_transcript", track, persisted_segments)
    finally:
        connection.close()

    update_learner_profile(
        coach_dir / "learner_profile.json",
        track,
        {
            "source_id": source_id,
            "title": effective_title,
            "track": track,
            "imported_at": utc_now_iso(),
            "segment_count": len(persisted_segments),
        },
    )
    return {
        "learning_root": str(resolved_root),
        "source_id": source_id,
        "source_title": effective_title,
        "track": track,
        "raw_cues": cleaned["stats"]["rawCueCount"],
        "cleaned_utterances": cleaned["stats"]["cleanedUtteranceCount"],
        "segment_count": len(persisted_segments),
        "first_segment": {
            "start_ref": persisted_segments[0]["startRef"] if persisted_segments else None,
            "end_ref": persisted_segments[0]["endRef"] if persisted_segments else None,
            "summary": persisted_segments[0]["sceneSummary"] if persisted_segments else None,
        },
    }
