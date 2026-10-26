from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.models.carta_model import Base
from motor.motor_asyncio import AsyncIOMotorClient
import redis.asyncio as redis

DATABASE_URL = "postgresql+asyncpg://poke_user:poke_password@postgres:5432/pokearena_db"
REDIS_URL = "redis://redis:6379/0"
MONGO_URL = "mongodb://mongodb:27017"

# Configuración PostgreSQL
engine = create_async_engine(DATABASE_URL, echo=True)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Configuración Redis
redis_client = redis.from_url(REDIS_URL, decode_responses=True)
mongo_client = AsyncIOMotorClient(MONGO_URL)

mongo_db = mongo_client.pokearena_db

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_db():
    async with async_session() as session:
        yield session

async def get_mongo():
    yield mongo_db