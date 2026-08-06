import pytest

from harness.persistence.db import Database


@pytest.fixture
async def db() -> Database:
    database = Database(":memory:")
    await database.migrate()
    try:
        yield database
    finally:
        await database.close()
