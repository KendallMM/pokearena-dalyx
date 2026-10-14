from fastapi import FastAPI
from app.routers import cartas

app = FastAPI(title="Poké-Arena API")

# Registrar los endpoints
app.include_router(cartas.router)