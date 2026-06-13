#!/usr/bin/env python3
"""Rebuild learner_profile.json from state.db evidence."""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def dump_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def top_signals(connection: sqlite3.Connection, language: str, event_type: str, limit: int = 5) -> list[str]:
    rows = connection.execute(
        """
        SELECT signal, COALESCE(SUM(strength), 0) AS total_strength, COUNT(*) AS hits
        FROM profile_events
        WHERE language = ? AND event_type = ?
        GROUP BY signal
        ORDER BY total_strength DESC, hits DESC, signal ASC
        LIMIT ?
        """,
        (language, event_type, limit),
    ).fetchall()
    return [row["signal"] for row in rows if row["signal"]]


def top_reusable_chunks(connection: sqlite3.Connection, language: str, limit: int = 8) -> list[str]:
    rows = connection.execute(
        """
        SELECT content
        FROM review_items
        WHERE language = ? AND item_type = 'chunk' AND status IN ('active', 'mastered')
        ORDER BY COALESCE(priority_score, 0) DESC, COALESCE(last_seen_at, first_seen_at) DESC
        LIMIT ?
        """,
        (language, limit),
    ).fetchall()
    return [row["content"] for row in rows if row["content"]]


def top_vocab_gaps(connection: sqlite3.Connection, language: str, limit: int = 6) -> list[str]:
    event_signals = top_signals(connection, language, "vocab_gap", limit)
    if event_signals:
        return event_signals
    rows = connection.execute(
        """
        SELECT content
        FROM review_items
        WHERE language = ? AND item_type IN ('vocab', 'term') AND status = 'active'
        ORDER BY COALESCE(priority_score, 0) DESC, COALESCE(last_seen_at, first_seen_at) DESC
        LIMIT ?
        """,
        (language, limit),
    ).fetchall()
    return [row["content"] for row in rows if row["content"]]


def track_bias(connection: sqlite3.Connection, language: str, limit: int = 3) -> list[str]:
    rows = connection.execute(
        """
        SELECT track, COUNT(*) AS hits
        FROM sessions
        WHERE language = ?
        GROUP BY track
        ORDER BY hits DESC, track ASC
        LIMIT ?
        """,
        (language, limit),
    ).fetchall()
    return [row["track"] for row in rows if row["track"]]


def recent_priorities(connection: sqlite3.Connection, language: str, limit: int = 3) -> list[str]:
    rows = connection.execute(
        """
        SELECT review_category, COUNT(*) AS hits, MAX(COALESCE(priority_score, 0)) AS max_priority
        FROM review_items
        WHERE language = ? AND status = 'active'
        GROUP BY review_category
        ORDER BY max_priority DESC, hits DESC, review_category ASC
        LIMIT ?
        """,
        (language, limit),
    ).fetchall()
    return [row["review_category"] for row in rows if row["review_category"]]


def active_languages(connection: sqlite3.Connection) -> list[str]:
    rows = connection.execute(
        """
        SELECT language
        FROM sources
        WHERE status = 'active'
        UNION
        SELECT language
        FROM sessions
        """
    ).fetchall()
    return sorted({row["language"] for row in rows if row["language"]})


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild learner_profile.json from state.db.")
    parser.add_argument("learning_root", help="Workspace root path.")
    args = parser.parse_args()

    root = Path(args.learning_root)
    coach_dir = root / ".language-coach"
    profile_path = coach_dir / "learner_profile.json"
    db_path = coach_dir / "state.db"

    profile = load_json(profile_path)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row

    languages = active_languages(connection) or profile.get("active_languages", [])
    profile["active_languages"] = languages
    language_profiles = profile.setdefault("language_profiles", {})

    for language in languages:
        snapshot = language_profiles.setdefault(language, {})
        snapshot["comprehension_strengths"] = top_signals(connection, language, "comprehension_strength")
        snapshot["output_fragilities"] = top_signals(connection, language, "output_fragility")
        snapshot["reusable_chunks"] = top_reusable_chunks(connection, language)
        snapshot["recurring_vocab_gaps"] = top_vocab_gaps(connection, language)
        snapshot["track_bias"] = track_bias(connection, language)
        snapshot["recent_priorities"] = recent_priorities(connection, language)
        snapshot["last_updated_at"] = utc_now_iso()
        snapshot.setdefault("baseline_summary", None)

    profile["updated_at"] = utc_now_iso()
    dump_json(profile_path, profile)
    connection.close()
    print(str(profile_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
