from fastapi import FastAPI

from app.api.router import api_router


app = FastAPI(
    title="MedMap API",
    version="0.1.0",
    description="Diagnostic safety-net prototype API",
)
app.include_router(api_router)
