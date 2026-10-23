import csv
import sqlite3
from pathlib import Path


def import_articles(source: Path, database: Path) -> None:
    rows: list[tuple[str | int | None, ...]] = []
    seen: set[str] = set()
    fields = ["article_id", "topic", "audience", "keywords", "content", "request_limit", "limit_window"]
    with source.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames != fields:
            raise ValueError(f"{source}:1: invalid columns")
        for line, row in enumerate(reader, 2):
            try:
                if None in row or any(not row[key] or not row[key].strip() for key in fields[:5]):
                    raise ValueError()
                if row["article_id"] in seen or row["audience"] not in {"student", "teacher", "all"}:
                    raise ValueError()
                value = row["request_limit"]
                window = row["limit_window"]
                if bool(value) != bool(window):
                    raise ValueError()
                if value and (not value.isascii() or not value.isdecimal() or not 0 <= int(value) <= 1_000_000 or window not in {"minute", "day"}):
                    raise ValueError()
                seen.add(row["article_id"])
                rows.append(tuple(row[key] for key in fields[:5]) + (int(value) if value else None, window or None))
            except (ValueError, TypeError):
                raise ValueError(f"{source}:{line}: invalid article") from None
    if len(rows) < 8:
        raise ValueError(f"{source}: at least 8 articles required")
    database.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS help_articles (article_id TEXT PRIMARY KEY, topic TEXT NOT NULL, audience TEXT NOT NULL, keywords TEXT NOT NULL, content TEXT NOT NULL, request_limit INTEGER, limit_window TEXT)")
        conn.execute("DELETE FROM help_articles")
        conn.executemany("INSERT INTO help_articles VALUES (?, ?, ?, ?, ?, ?, ?)", rows)
