"""Async SQLAlchemy engine/session factory.

Per docs/CODING-GUIDELINES.md section 4: async where the underlying I/O is async-capable.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from knowledge_assistant.config import settings

engine = create_async_engine(settings.database_url)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession]:
    """FastAPI dependency: yields a request-scoped async session."""
    async with async_session_factory() as session:
        yield session
