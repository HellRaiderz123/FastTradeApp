from fastapi import FastAPI
from app.api.option_spread import router as option_spread_router

app = FastAPI(title="Algo Trading Backend")

app.include_router(
    option_spread_router,
    prefix="/api/strategy",
    tags=["Option Spread 15m"]
)
