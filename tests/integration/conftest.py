from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from knowledge_assistant.storage.database import async_session_factory


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession]:
    """Requires local Postgres/pgvector (`docker compose up postgres` in docker/) with
    migrations applied (`alembic upgrade head`)."""
    async with async_session_factory() as session:
        yield session
