from contextlib import asynccontextmanager
from importlib.metadata import version

from alembic import command
from alembic.config import Config
from fastapi import FastAPI

from app.routers import auth, households, persons


@asynccontextmanager
async def lifespan(app: FastAPI):
    command.upgrade(Config("alembic.ini"), "head")
    yield


app = FastAPI(
    title="Tout Pris API",
    description="Backend API of the Tout Pris project: manage households and their persons.",
    version=version("tout-pris-back"),
    lifespan=lifespan,
)
app.include_router(auth.router)
app.include_router(households.router)
app.include_router(persons.router)


@app.get("/health", summary="Health check", tags=["monitoring"])
def health():
    return {"status": "ok"}
