"""Database session management."""
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:
    """Enable SQLite FK enforcement for app/test engines.

    SQLite leaves foreign-key enforcement disabled by default, unlike
    PostgreSQL. Enabling it globally keeps SQLite-backed tests consistent with
    the production schema's ON DELETE/FOREIGN KEY behavior.
    """
    module = type(dbapi_connection).__module__
    if "sqlite" not in module:
        return

    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


engine = create_async_engine(
    settings.database_url,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    echo=settings.debug,
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""
    pass


async def init_db() -> None:
    """Initialize database connection."""
    async with engine.begin() as conn:
        # In development, create all tables
        # In production, use Alembic migrations
        pass


async def get_db() -> AsyncSession:
    """Get database session dependency."""
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()