"""Async SQLite database with a sequential SQL migration runner (DECISIONS.md D-003/D-004)."""

from __future__ import annotations

import re
from importlib import resources
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

_MIGRATION_NAME = re.compile(r"^(\d{4})_[a-z0-9_]+\.sql$")


def _load_migrations() -> list[tuple[int, str, str]]:
    """Return (number, name, sql) for every packaged migration, ordered."""
    migrations: list[tuple[int, str, str]] = []
    package = resources.files("harness.persistence") / "migrations"
    for entry in package.iterdir():
        match = _MIGRATION_NAME.match(entry.name)
        if match:
            migrations.append((int(match.group(1)), entry.name, entry.read_text()))
    migrations.sort()
    if [n for n, _, _ in migrations] != list(range(1, len(migrations) + 1)):
        raise RuntimeError("migrations must be numbered sequentially from 0001")
    return migrations


class Database:
    def __init__(self, path: Path | str) -> None:
        self.path = str(path)
        url = (
            "sqlite+aiosqlite:///:memory:"
            if self.path == ":memory:"
            else (f"sqlite+aiosqlite:///{self.path}")
        )
        self.engine: AsyncEngine = create_async_engine(url)

    async def migrate(self) -> None:
        async with self.engine.begin() as conn:
            await conn.execute(text("PRAGMA journal_mode=WAL"))
            await conn.execute(text("PRAGMA foreign_keys=ON"))
            await conn.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS schema_migrations ("
                    "number INTEGER PRIMARY KEY, name TEXT NOT NULL, "
                    "applied_at TEXT NOT NULL DEFAULT (datetime('now')))"
                )
            )
            applied = {
                row[0]
                for row in (
                    await conn.execute(text("SELECT number FROM schema_migrations"))
                ).fetchall()
            }
            for number, name, sql in _load_migrations():
                if number in applied:
                    continue
                for statement in _split_statements(sql):
                    await conn.execute(text(statement))
                await conn.execute(
                    text("INSERT INTO schema_migrations (number, name) VALUES (:n, :m)"),
                    {"n": number, "m": name},
                )

    async def close(self) -> None:
        await self.engine.dispose()

    async def fetch_all(self, sql: str, params: dict[str, Any] | None = None) -> list[Any]:
        async with self.engine.connect() as conn:
            result = await conn.execute(text(sql), params or {})
            return list(result.mappings().all())

    async def fetch_one(self, sql: str, params: dict[str, Any] | None = None) -> Any | None:
        rows = await self.fetch_all(sql, params)
        return rows[0] if rows else None

    async def execute(self, sql: str, params: dict[str, Any] | None = None) -> None:
        async with self.engine.begin() as conn:
            await conn.execute(text(sql), params or {})

    async def execute_returning_rowid(self, sql: str, params: dict[str, Any] | None = None) -> int:
        async with self.engine.begin() as conn:
            result = await conn.execute(text(sql), params or {})
            rowid = result.lastrowid
            assert rowid is not None
            return int(rowid)

    def begin(self) -> Any:
        """Transactional connection context manager for multi-statement operations."""
        return self.engine.begin()


async def exec_in(conn: AsyncConnection, sql: str, params: dict[str, Any] | None = None) -> Any:
    return await conn.execute(text(sql), params or {})


def _split_statements(sql: str) -> list[str]:
    """Split a migration file on semicolons at end of line (no triggers/procs in schema)."""
    statements = []
    for chunk in re.split(r";\s*\n", sql):
        chunk = chunk.strip()
        if chunk and not all(line.strip().startswith("--") for line in chunk.splitlines()):
            statements.append(chunk)
    return statements
