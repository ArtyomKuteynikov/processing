from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from sqlalchemy.orm import sessionmaker

from config.main import DB_HOST, DB_NAME, DB_PASS, DB_PORT, DB_USER

# postgres
DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


engine = create_async_engine(DATABASE_URL)
async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# sqlite
# DATABASE_URL = f"sqlite+aiosqlite:///{DB_NAME}"
# Base = declarative_base()
#
#
# engine = create_async_engine(DATABASE_URL)
# async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session
