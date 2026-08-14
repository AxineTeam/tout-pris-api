from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import Base, engine
from app.routers import stufflists


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Tout Pris API", lifespan=lifespan)
app.include_router(stufflists.router)


@app.get("/health")
def health():
    return {"status": "ok"}
