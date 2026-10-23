from pathlib import Path

import pytest

from backend.database import import_articles
from backend.tools.help_articles import create_registry


def test_assumption_calculation_does_not_need_database(tmp_path: Path) -> None:
    limit = {"name": "每日", "window": "day", "maximum": 20, "used": 8, "source": "user_assumption"}
    result = create_registry(tmp_path / "missing.db").execute("calculate_remaining_requests", {"limits": [limit]})
    assert result == {"ok": True, "data": {"limits": [{**limit, "remaining": 12, "over_limit": False}], "sendable_now": 12, "unit": "requests", "simulated": True}}


def test_policy_source_and_trimmed_names(tmp_path: Path) -> None:
    db = tmp_path / "demo.db"
    import_articles(Path("data/help_articles.csv"), db)
    registry = create_registry(db)
    limit = {"name": " 每日 ", "window": "day", "maximum": 20, "used": 8, "source": "help_article", "article_id": " H04 "}
    result = registry.execute("calculate_remaining_requests", {"limits": [limit]})
    assert result["ok"] is True
    assert result["data"]["limits"][0]["article_id"] == "H04"
    assert result["data"]["limits"][0]["name"] == "每日"
    for changed, code in [({"article_id": "H99"}, "NOT_FOUND"), ({"maximum": 21}, "INVALID_ARGUMENT"), ({"window": "minute"}, "INVALID_ARGUMENT"), ({"article_id": "H01"}, "INVALID_ARGUMENT")]:
        failure = registry.execute("calculate_remaining_requests", {"limits": [{**limit, **changed}]})
        assert failure["ok"] is False
        assert failure["error"]["code"] == code
    db.unlink()
    assert registry.execute("calculate_remaining_requests", {"limits": [limit]})["error"]["code"] == "INTERNAL_ERROR"


@pytest.mark.parametrize("maximum,used,remaining,over", [(20, 20, 0, False), (20, 21, 0, True), (0, 0, 0, False), (1_000_000, 0, 1_000_000, False)])
def test_independently_worked_boundaries(tmp_path: Path, maximum: int, used: int, remaining: int, over: bool) -> None:
    result = create_registry(tmp_path / "unused.db").execute("calculate_remaining_requests", {"limits": [{"name": "每日", "window": "day", "maximum": maximum, "used": used, "source": "user_assumption"}]})
    assert result["data"]["sendable_now"] == remaining
    assert result["data"]["limits"][0]["over_limit"] is over


def test_multiple_limits_use_smallest_remaining(tmp_path: Path) -> None:
    result = create_registry(tmp_path / "unused.db").execute("calculate_remaining_requests", {"limits": [
        {"name": "每日", "window": "day", "maximum": 20, "used": 8, "source": "user_assumption"},
        {"name": "每分鐘", "window": "minute", "maximum": 5, "used": 4, "source": "user_assumption"},
    ]})
    assert [item["remaining"] for item in result["data"]["limits"]] == [12, 1]
    assert result["data"]["sendable_now"] == 1


@pytest.mark.parametrize("changes", [
    {"maximum": -1}, {"used": -1}, {"used": 1_000_001}, {"maximum": 1_000_001},
    {"used": 1.0}, {"maximum": 20.0}, {"used": True}, {"maximum": False},
    {"used": "8"}, {"window": "hour"}, {"name": " "}, {"name": "a" * 41},
    {"source": "account"}, {"source": "help_article"}, {"article_id": "H04"}, {"extra": 1},
])
def test_invalid_limit(tmp_path: Path, changes: dict[str, object]) -> None:
    limit = {"name": "每日", "window": "day", "maximum": 20, "used": 8, "source": "user_assumption"}
    result = create_registry(tmp_path / "unused.db").execute("calculate_remaining_requests", {"limits": [{**limit, **changes}]})
    assert result["ok"] is False
    assert result["error"]["code"] == "INVALID_ARGUMENT"


def test_missing_duplicate_and_array_constraints(tmp_path: Path) -> None:
    registry = create_registry(tmp_path / "unused.db")
    limit = {"name": "每日", "window": "day", "maximum": 20, "used": 8, "source": "user_assumption"}
    invalid: list[object] = [{}, {"limits": []}, {"limits": [limit] * 5}, {"limits": [limit, {**limit, "name": " 每日 "}]}, {"limits": [limit], "extra": 1}]
    invalid.extend({"limits": [{key: value for key, value in limit.items() if key != missing}]} for missing in limit)
    for arguments in invalid:
        assert registry.execute("calculate_remaining_requests", arguments)["error"]["code"] == "INVALID_ARGUMENT"


def test_nested_strings_trim_before_validation(tmp_path: Path) -> None:
    result = create_registry(tmp_path / "unused.db").execute("calculate_remaining_requests", {"limits": [{"name": " " + "a" * 40 + " ", "window": " day ", "maximum": 20, "used": 8, "source": " user_assumption "}]})
    assert result["ok"] is True
    assert result["data"]["limits"][0]["window"] == "day"
