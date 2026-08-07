"""Concurrency sanity check for `Database` (D-030): interleaved writers/readers on
the shared in-memory connection must all complete with correct data. This doesn't
reliably reproduce the original hang on its own — that needed the denser,
longer-chained interleaving of a real `JobManager` background task racing live HTTP
polling (see `tests/api/test_permissions.py`'s ask/deny flows, which did hang
non-deterministically before D-030's fix and are the actual regression coverage) —
but it pins the basic safety property `Database._lock` provides.
"""

import asyncio

import pytest

from harness.persistence.db import Database


@pytest.mark.asyncio
async def test_concurrent_writers_all_complete(db: Database) -> None:
    await db.execute(
        "CREATE TABLE concurrency_probe (id INTEGER PRIMARY KEY, value INTEGER NOT NULL)"
    )

    async def writer(value: int) -> None:
        await db.execute(
            "INSERT INTO concurrency_probe (id, value) VALUES (:id, :value)",
            {"id": value, "value": value * 10},
        )

    async def reader_interleaved_with_writers() -> None:
        for _ in range(20):
            await db.fetch_all("SELECT * FROM concurrency_probe")
            await asyncio.sleep(0)

    await asyncio.wait_for(
        asyncio.gather(*(writer(i) for i in range(20)), reader_interleaved_with_writers()),
        timeout=5.0,
    )

    rows = await db.fetch_all("SELECT id, value FROM concurrency_probe ORDER BY id")
    assert [(r["id"], r["value"]) for r in rows] == [(i, i * 10) for i in range(20)]
