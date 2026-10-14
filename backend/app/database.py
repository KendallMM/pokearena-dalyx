from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Credenciales alineadas con el docker-compose
DATABASE_URL = "postgresql+asyncpg://poke_user:poke_password@postgres:5432/pokearena_db"

engine = create_async_engine(DATABASE_URL, echo=True)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db():
    """Generador de sesiones asíncronas para inyección de dependencias."""
    async with async_session() as session:
        yield session