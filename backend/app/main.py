from fastapi import FastAPI
from app.api.option_spread import router as option_spread_router
from app.api.routes import journal
from app.api.routes import intent
from app.api.routes import execute
from app.api.routes.paper_mtm import router as paper_mtm_router
from app.api.routes.exit import router as exit_router
from app.api.routes.auto_exit import router as auto_exit_router
from app.api.system_control import router as system_router
from dotenv import load_dotenv
load_dotenv()

app = FastAPI(
    title="AI ML Trading Backend",
    version="1.0.0",
    description="Backend engine for option spread strategies",
)

# Register routers
app.include_router(
    option_spread_router,
    prefix="/strategy",
    tags=["Option Spreads"],
)

@app.get("/")
def health_check():
    return {"status": "ok", "service": "trading-backend"}

app.include_router(journal.router)
app.include_router(intent.router)
app.include_router(execute.router)
app.include_router(paper_mtm_router)

app.include_router(exit_router)
app.include_router(auto_exit_router)

app.include_router(system_router)