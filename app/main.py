from contextlib import asynccontextmanager
from importlib.metadata import version

from fastapi import FastAPI

from app.database import Base, engine
from app.routers import stufflists


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Tout Pris API",
    description="Backend API of the Tout Pris project: manage stufflists.",
    version=version("tout-pris-back"),
    lifespan=lifespan,
)
app.include_router(stufflists.router)


@app.get("/health", summary="Health check", tags=["monitoring"])
def health():
    return {"status": "ok"}
