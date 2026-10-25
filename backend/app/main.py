from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.routers import cartas
from app.database import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Se ejecuta al iniciar el servidor
    await init_db()
    yield

app = FastAPI(title="Poké-Arena API", lifespan=lifespan)

app.include_router(cartas.router)