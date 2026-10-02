from fastapi import APIRouter

from app.api.routes import health, intake, stt


api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(stt.router, prefix="/v1/stt", tags=["stt"])
api_router.include_router(intake.router, prefix="/v1/intake", tags=["intake"])
