from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool

from app.api.router import api_router
from app.services.stt_service import get_stt_service


@asynccontextmanager
async def lifespan(_: FastAPI):
    await run_in_threadpool(get_stt_service().warm_up)
    yield


app = FastAPI(
    title="MedMap API",
    version="0.1.0",
    description="Diagnostic safety-net prototype API",
    lifespan=lifespan,
)
app.include_router(api_router)
