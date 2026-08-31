from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from knowledge_assistant.storage.database import engine


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession]:
    """Requires local Postgres/pgvector (`docker compose up postgres` in docker/) with
    migrations applied (`alembic upgrade head`).

    Wraps the test in an outer transaction that's always rolled back, and binds the session to
    it via `join_transaction_mode="create_savepoint"` so the test's own `session.commit()` calls
    (used throughout tests/integration/) commit to a SAVEPOINT instead of the real transaction -
    nothing the test writes ever persists past this fixture, regardless of what else lands in
    the table from other tests, parallel workers, or local seed data. Standard SQLAlchemy
    "join a Session into an external transaction" pattern for test isolation.
    """
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        )
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()
