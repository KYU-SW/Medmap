from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware

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
# The Android app's web view (origin http://localhost) calls the API through adb reverse.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost"],
    allow_methods=["POST", "GET"],
    allow_headers=["Content-Type"],
)
app.include_router(api_router)
