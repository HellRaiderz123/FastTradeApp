from fastapi import APIRouter
from app.core.option_spread_15m.engine import run_option_spread

router = APIRouter()

@router.post("/scan/option-spread-15m")
def scan_strategy(payload: dict):
    """
    This replaces your Streamlit button click
    """
    result = run_option_spread(payload)
    return result
