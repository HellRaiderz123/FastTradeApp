from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
import os
import logging
from pathlib import Path
from dotenv import load_dotenv, set_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["Settings"])

# Get the .env file path
ENV_FILE = Path(__file__).resolve().parent.parent.parent.parent / ".env"


class ZerodhaCredentials(BaseModel):
    """Model for Zerodha API credentials"""
    api_key: str
    api_secret: str


class ZerodhaAccessToken(BaseModel):
    """Model for Zerodha access token response"""
    access_token: str


class ZerodhaRequestToken(BaseModel):
    """Model for Zerodha request token (from OAuth login)"""
    request_token: str


class SettingsResponse(BaseModel):
    """Response for current settings"""
    api_key_set: bool
    access_token_set: bool
    execution_mode: str


def get_env_value(key: str) -> str:
    """Get environment variable value"""
    return os.getenv(key, "")


@router.get("/zerodha", response_model=SettingsResponse)
def get_zerodha_settings():
    """
    Get current Zerodha settings status.
    
    Returns:
        - api_key_set: Boolean indicating if API key is configured
        - access_token_set: Boolean indicating if access token is set
        - execution_mode: Current execution mode (ZERODHA_LIVE, ZERODHA_DRY_RUN, etc.)
    """
    return SettingsResponse(
        api_key_set=bool(get_env_value("ZERODHA_API_KEY")),
        access_token_set=bool(get_env_value("ZERODHA_ACCESS_TOKEN")),
        execution_mode=get_env_value("EXECUTION_MODE") or "ZERODHA_DRY_RUN"
    )


@router.post("/zerodha/credentials")
def save_zerodha_credentials(credentials: ZerodhaCredentials):
    """
    Save Zerodha API credentials to .env file.
    
    Args:
        api_key: Zerodha API key
        api_secret: Zerodha API secret
        
    Returns:
        {"status": "success", "message": "Credentials saved"}
    """
    try:
        if not credentials.api_key or not credentials.api_secret:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="API key and secret cannot be empty"
            )
        
        # Save to .env file
        set_key(str(ENV_FILE), "ZERODHA_API_KEY", credentials.api_key)
        set_key(str(ENV_FILE), "ZERODHA_API_SECRET", credentials.api_secret)
        
        # Update environment variables
        os.environ["ZERODHA_API_KEY"] = credentials.api_key
        os.environ["ZERODHA_API_SECRET"] = credentials.api_secret
        
        logger.info("Zerodha credentials updated successfully")
        return {
            "status": "success",
            "message": "Zerodha credentials saved successfully"
        }
    except Exception as e:
        logger.error(f"Error saving credentials: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error saving credentials: {str(e)}"
        )


@router.post("/zerodha/generate-token", response_model=ZerodhaAccessToken)
def generate_zerodha_token(request_body: ZerodhaRequestToken):
    """
    Generate Zerodha access token using request token.
    
    This exchanges a request token (from Zerodha OAuth login) for an access token.
    
    Requires ZERODHA_API_KEY and ZERODHA_API_SECRET to be already configured.
    
    Args:
        request_token: Request token obtained from Zerodha login
        
    Returns:
        {"access_token": "token_value"}
    """
    try:
        from kiteconnect import KiteConnect
        
        if not request_body.request_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Request token is required"
            )
        
        api_key = os.getenv("ZERODHA_API_KEY")
        api_secret = os.getenv("ZERODHA_API_SECRET")
        
        if not api_key or not api_secret:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="API Key and Secret must be configured first"
            )
        
        # Initialize KiteConnect
        kite = KiteConnect(api_key=api_key)
        
        # Exchange request token for access token
        session_data = kite.generate_session(
            request_body.request_token,
            api_secret=api_secret
        )
        
        access_token = session_data.get("access_token")
        
        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate access token"
            )
        
        # Save the access token to .env
        set_key(str(ENV_FILE), "ZERODHA_ACCESS_TOKEN", access_token)
        os.environ["ZERODHA_ACCESS_TOKEN"] = access_token
        
        logger.info("Zerodha access token generated successfully")
        return ZerodhaAccessToken(access_token=access_token)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating token: {str(e)}"
        )


@router.post("/zerodha/token")
def save_zerodha_token(token: ZerodhaAccessToken):
    """
    Save a manually obtained Zerodha access token to .env file.
    
    Args:
        access_token: The access token obtained from Zerodha login
        
    Returns:
        {"status": "success", "message": "Token saved"}
    """
    try:
        if not token.access_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Access token cannot be empty"
            )
        
        # Save to .env file
        set_key(str(ENV_FILE), "ZERODHA_ACCESS_TOKEN", token.access_token)
        
        # Update environment variable
        os.environ["ZERODHA_ACCESS_TOKEN"] = token.access_token
        
        logger.info("Zerodha access token updated successfully")
        return {
            "status": "success",
            "message": "Zerodha access token saved successfully"
        }
    except Exception as e:
        logger.error(f"Error saving token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error saving token: {str(e)}"
        )


@router.post("/execution-mode")
def set_execution_mode(mode: str):
    """
    Set the execution mode (ZERODHA_LIVE, ZERODHA_DRY_RUN, PAPER_TRADING, etc.)
    
    Args:
        mode: The execution mode to set
        
    Returns:
        {"status": "success", "mode": "mode_value"}
    """
    try:
        valid_modes = ["ZERODHA_LIVE", "ZERODHA_DRY_RUN", "PAPER_TRADING", "BACKTEST"]
        
        if mode not in valid_modes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid execution mode. Valid modes: {', '.join(valid_modes)}"
            )
        
        set_key(str(ENV_FILE), "EXECUTION_MODE", mode)
        os.environ["EXECUTION_MODE"] = mode
        
        logger.info(f"Execution mode changed to {mode}")
        return {
            "status": "success",
            "mode": mode
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting execution mode: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error setting execution mode: {str(e)}"
        )
