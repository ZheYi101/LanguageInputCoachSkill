#!/usr/bin/env python3
"""Repair or migrate an english-input-coach learning root to the current schema."""

from __future__ import annotations

import argparse
import sqlite3
import shutil
from datetime import datetime, timezone
import json
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
    parser = argparse.ArgumentParser(description="Repair or migrate a learning root.")
    parser.add_argument("learning_root", help="Workspace root path.")
    args = parser.parse_args()

    root = Path(args.learning_root)
    coach_dir = root / ".language-coach"
    db_path = coach_dir / "state.db"
    config_path = coach_dir / "config.json"
    profile_path = coach_dir / "learner_profile.json"

    if not db_path.exists():
        raise SystemExit(f"Missing database: {db_path}")

    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")
    with connection:
        create_schema(connection)
    connection.close()

    if config_path.exists():
        config = json.loads(config_path.read_text(encoding="utf-8-sig"))
        config["schema_version"] = CURRENT_SCHEMA_VERSION
        config["updated_at"] = utc_now_iso()
        dump_json(config_path, config)

    if profile_path.exists():
        profile = json.loads(profile_path.read_text(encoding="utf-8-sig"))
        profile["schema_version"] = CURRENT_SCHEMA_VERSION
        profile["updated_at"] = utc_now_iso()
        dump_json(profile_path, profile)

    copy_helper_scripts(Path(__file__).resolve().parent, coach_dir / "scripts")
    print(f"Migrated or verified learning root at {root} to schema {CURRENT_SCHEMA_VERSION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
