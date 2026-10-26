from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.routers import cartas, ubicaciones
from app.database import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(title="Poké-Arena API", lifespan=lifespan)

app.include_router(cartas.router)
app.include_router(ubicaciones.router)