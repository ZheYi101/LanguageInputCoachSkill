#!/usr/bin/env python3
"""Initialize a long-term learning workspace for english-input-coach."""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


CURRENT_SCHEMA_VERSION = 1


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def dump_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def create_schema(connection: sqlite3.Connection) -> None:
    statements = [
        """
        CREATE TABLE IF NOT EXISTS schema_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS sources (
            id TEXT PRIMARY KEY,
            language TEXT NOT NULL,
            material_type TEXT NOT NULL,
            track TEXT NOT NULL,
            title TEXT NOT NULL,
            source_url TEXT,
            creator TEXT,
            raw_path TEXT NOT NULL,
            cleaned_path TEXT,
            imported_at TEXT NOT NULL,
            status TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS segments (
            id TEXT PRIMARY KEY,
            source_id TEXT NOT NULL,
            material_type TEXT NOT NULL,
            track TEXT NOT NULL,
            segment_index INTEGER NOT NULL,
            segment_path TEXT NOT NULL,
            start_ref TEXT,
            end_ref TEXT,
            context_before_summary TEXT,
            context_after_summary TEXT,
            scene_or_argument_summary TEXT,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL,
            FOREIGN KEY(source_id) REFERENCES sources(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            language TEXT NOT NULL,
            track TEXT,
            session_type TEXT NOT NULL,
            source_id TEXT,
            segment_id TEXT,
            lesson_path TEXT,
            answers_path TEXT,
            feedback_path TEXT,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            status TEXT NOT NULL,
            FOREIGN KEY(source_id) REFERENCES sources(id),
            FOREIGN KEY(segment_id) REFERENCES segments(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS review_items (
            id TEXT PRIMARY KEY,
            language TEXT NOT NULL,
            track TEXT,
            review_category TEXT NOT NULL,
            item_type TEXT NOT NULL,
            content TEXT NOT NULL,
            normalized_key TEXT NOT NULL,
            source_id TEXT,
            segment_id TEXT,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            last_reviewed_at TEXT,
            due_at TEXT,
            interval_days REAL,
            stability REAL,
            priority_score REAL,
            status TEXT NOT NULL,
            FOREIGN KEY(source_id) REFERENCES sources(id),
            FOREIGN KEY(segment_id) REFERENCES segments(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS profile_events (
            id TEXT PRIMARY KEY,
            language TEXT NOT NULL,
            session_id TEXT,
            event_type TEXT NOT NULL,
            signal TEXT NOT NULL,
            evidence TEXT,
            strength REAL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(session_id) REFERENCES sessions(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS user_actions (
            id TEXT PRIMARY KEY,
            target_type TEXT NOT NULL,
            target_id TEXT NOT NULL,
            action_type TEXT NOT NULL,
            reason TEXT,
            created_at TEXT NOT NULL
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_sources_language_status ON sources(language, status)",
        "CREATE INDEX IF NOT EXISTS idx_segments_source_status ON segments(source_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_sessions_language_finished ON sessions(language, finished_at)",
        "CREATE INDEX IF NOT EXISTS idx_review_items_language_status_due ON review_items(language, status, due_at)",
        "CREATE INDEX IF NOT EXISTS idx_review_items_category ON review_items(review_category, status)",
        "CREATE INDEX IF NOT EXISTS idx_profile_events_language_type ON profile_events(language, event_type)",
    ]
    for statement in statements:
        connection.execute(statement)
    connection.execute(
        """
        INSERT INTO schema_meta(key, value)
        VALUES('schema_version', ?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """,
        (str(CURRENT_SCHEMA_VERSION),),
    )


def copy_helper_scripts(skill_scripts_dir: Path, target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    for script_path in skill_scripts_dir.glob("*.py"):
        target_path = target_dir / script_path.name
        if script_path.resolve() == target_path.resolve():
            continue
        shutil.copy2(script_path, target_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize a long-term learning root.")
    parser.add_argument("learning_root", help="Workspace root path.")
    parser.add_argument("--learner-id", default="default")
    parser.add_argument("--native-language", default="zh-CN")
    parser.add_argument("--default-language", default="en")
    parser.add_argument("--feedback-language", default="zh-CN")
    args = parser.parse_args()

    root = Path(args.learning_root)
    coach_dir = root / ".language-coach"
    languages_dir = root / "languages"
    skill_scripts_dir = Path(__file__).resolve().parent
    now = utc_now_iso()

    for path in [
        coach_dir / "migrations",
        coach_dir / "scripts",
        languages_dir / "en" / "raw",
        languages_dir / "en" / "cleaned",
        languages_dir / "en" / "segments",
        languages_dir / "en" / "lessons",
        languages_dir / "en" / "sessions",
        languages_dir / "en" / "exports",
        languages_dir / "ja",
    ]:
        path.mkdir(parents=True, exist_ok=True)

    config = {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "learner_id": args.learner_id,
        "default_language": args.default_language,
        "default_feedback_language": args.feedback_language,
        "auto_write": True,
        "review_policy": {
            "mode": "summary_first",
            "max_focus_groups": 3,
            "max_item_details_on_demand": 5,
        },
        "paths": {
            "languages_dir": "languages",
            "coach_dir": ".language-coach",
        },
        "created_at": now,
        "updated_at": now,
    }
    profile = {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "learner_id": args.learner_id,
        "native_language": args.native_language,
        "active_languages": [args.default_language],
        "preferences": {
            "feedback_language": args.feedback_language,
            "auto_write": True,
        },
        "language_profiles": {
            args.default_language: {
                "baseline_summary": None,
                "comprehension_strengths": [],
                "output_fragilities": [],
                "reusable_chunks": [],
                "recurring_vocab_gaps": [],
                "track_bias": [],
                "recent_priorities": [],
                "last_updated_at": None,
            }
        },
        "created_at": now,
        "updated_at": now,
    }

    dump_json(coach_dir / "config.json", config)
    dump_json(coach_dir / "learner_profile.json", profile)

    db_path = coach_dir / "state.db"
    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")
    with connection:
        create_schema(connection)
    connection.close()

    copy_helper_scripts(skill_scripts_dir, coach_dir / "scripts")
    print(str(root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
