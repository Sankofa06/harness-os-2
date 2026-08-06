import pytest

from harness.persistence.db import Database


@pytest.mark.asyncio
async def test_migrate_creates_schema_and_is_idempotent() -> None:
    db = Database(":memory:")
    await db.migrate()
    await db.migrate()  # re-running must be a no-op
    rows = await db.fetch_all("SELECT number FROM schema_migrations ORDER BY number")
    assert [r["number"] for r in rows] == [1]
    tables = await db.fetch_all(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'contacts'"
    )
    assert len(tables) == 1
    await db.close()
