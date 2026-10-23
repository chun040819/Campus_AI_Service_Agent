import csv
import sqlite3
import io
from pathlib import Path


def _csv_text(source: Path) -> io.StringIO:
    raw = source.read_bytes()
    try:
        return io.StringIO(raw.decode("utf-8-sig"), newline="")
    except UnicodeDecodeError as exc:
        line = len(raw[:exc.start].splitlines()) + (not raw[:exc.start] or raw[:exc.start].endswith((b"\n", b"\r")))
        raise ValueError(f"{source}:{line}: invalid UTF-8 encoding") from None


def import_articles(source: Path, database: Path) -> None:
    rows: list[tuple[str | int | None, ...]] = []
    seen: set[str] = set()
    fields = ["article_id", "topic", "audience", "keywords", "content", "request_limit", "limit_window"]
    with _csv_text(source) as file:
        reader = csv.DictReader(file)
        if reader.fieldnames != fields:
            raise ValueError(f"{source}:1: invalid columns")
        for line, row in enumerate(reader, 2):
            try:
                if None in row or any(value is None for value in row.values()) or any(not row[key] or not row[key].strip() for key in fields[:5]):
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


def import_records(source: Path, database: Path) -> None:
    import re
    from datetime import datetime, timezone

    fields = ["issue_id", "title", "service", "symptom", "status", "available", "affected_requests", "workaround", "updated_at"]
    rows: list[tuple[str | int, ...]] = []
    seen: set[str] = set()
    with _csv_text(source) as file:
        reader = csv.DictReader(file)
        if reader.fieldnames != fields:
            raise ValueError(f"{source}:1: invalid columns")
        for line, row in enumerate(reader, 2):
            try:
                if None in row or any(value is None for value in row.values()) or any(not row[key] or not row[key].strip() for key in fields):
                    raise ValueError()
                if not re.fullmatch(r"INC-[0-9]{3}", row["issue_id"]) or row["issue_id"] in seen:
                    raise ValueError()
                if row["status"] not in {"investigating", "identified", "monitoring", "resolved"} or row["available"] not in {"true", "false"}:
                    raise ValueError()
                count = row["affected_requests"]
                if not count.isascii() or not count.isdecimal() or int(count) > 9223372036854775807:
                    raise ValueError()
                timestamp = row["updated_at"]
                if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?(?:Z|\+00:00)", timestamp):
                    raise ValueError()
                updated = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                if updated.utcoffset() != timezone.utc.utcoffset(updated):
                    raise ValueError()
                fraction = timestamp.split(".", 1)[1].split("Z", 1)[0].split("+", 1)[0].rstrip("0") if "." in timestamp else ""
                normalized = timestamp[:19] + ("." + fraction if fraction else "") + "Z"
                seen.add(row["issue_id"])
                rows.append(tuple(row[key] for key in fields[:5]) + (int(row["available"] == "true"), int(count), row["workaround"], normalized))
            except (ValueError, TypeError, OverflowError):
                raise ValueError(f"{source}:{line}: invalid issue record") from None
    if len(rows) < 15:
        raise ValueError(f"{source}: at least 15 records required")
    database.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS issue_records (issue_id TEXT PRIMARY KEY, title TEXT NOT NULL, service TEXT NOT NULL, symptom TEXT NOT NULL, status TEXT NOT NULL, available INTEGER NOT NULL, affected_requests INTEGER NOT NULL, workaround TEXT NOT NULL, updated_at TEXT NOT NULL)")
        conn.execute("DELETE FROM issue_records")
        conn.executemany("INSERT INTO issue_records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
