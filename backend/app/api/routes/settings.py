from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
import os
import logging
from pathlib import Path
from dotenv import load_dotenv, set_key

from app.core.execution.mode import normalize_execution_mode
from app.services.notifications import NotificationService
from app.db.session import SessionLocal

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

class GmailSettings(BaseModel):
    """Model for Gmail notification settings"""
    gmail_user: str
    gmail_app_password: str
    alert_email: str

class GmailToggle(BaseModel):
    enabled: bool

class TradingSettings(BaseModel):

    risk_per_trade: float
    max_trades_per_day: int


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
        execution_mode=normalize_execution_mode(get_env_value("EXECUTION_MODE"))
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
        normalized = normalize_execution_mode(mode)
        valid_modes = ["ZERODHA_LIVE", "ZERODHA_DRY_RUN", "PAPER_TRADING", "BACKTEST"]

        if normalized not in valid_modes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid execution mode. Valid modes: {', '.join(valid_modes)}"
            )

        set_key(str(ENV_FILE), "EXECUTION_MODE", normalized)
        os.environ["EXECUTION_MODE"] = normalized

        logger.info(f"Execution mode changed to {normalized}")
        return {
            "status": "success",
            "mode": normalized
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting execution mode: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error setting execution mode: {str(e)}"
        )

@router.get("/trading")
def get_trading_settings():
    """Get current trading settings (risk per trade, max trades per day)"""
    risk_per_trade = float(get_env_value("RISK_PER_TRADE") or "2.0")
    max_trades_per_day = int(get_env_value("MAX_TRADES_PER_DAY") or "3")
    
    return {
        "risk_per_trade": risk_per_trade,
        "max_trades_per_day": max_trades_per_day
    }


@router.post("/trading")
def save_trading_settings(settings: TradingSettings):
    """Save trading settings to .env"""
    try:
        if settings.risk_per_trade < 0.5 or settings.risk_per_trade > 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Risk per trade must be between 0.5% and 10%"
            )
        
        if settings.max_trades_per_day < 1 or settings.max_trades_per_day > 20:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Max trades per day must be between 1 and 20"
            )
        
        set_key(str(ENV_FILE), "RISK_PER_TRADE", str(settings.risk_per_trade))
        set_key(str(ENV_FILE), "MAX_TRADES_PER_DAY", str(settings.max_trades_per_day))
        
        os.environ["RISK_PER_TRADE"] = str(settings.risk_per_trade)
        os.environ["MAX_TRADES_PER_DAY"] = str(settings.max_trades_per_day)
        
        logger.info(f"Trading settings updated: risk={settings.risk_per_trade}%, max_trades={settings.max_trades_per_day}")
        return {
            "status": "success",
            "message": "Trading settings saved successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving trading settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error saving trading settings: {str(e)}"
        )

@router.get("/notifications")
def get_notification_settings():
    """Get current notification settings status"""
    gmail_user = get_env_value("GMAIL_USER")
    alert_email = get_env_value("ALERT_EMAIL")
    enabled = get_env_value("NOTIFY_GMAIL_ENABLED").lower() if get_env_value("NOTIFY_GMAIL_ENABLED") else "true"

    # Mask user for display
    masked_user = (
        gmail_user[:2] + "***" + gmail_user[-10:] if gmail_user else ""
    )

    return {
        "gmail_configured": bool(gmail_user and get_env_value("GMAIL_APP_PASSWORD")),
        "gmail_enabled": enabled in ["1", "true", "yes"],
        "gmail_user": masked_user,
        "alert_email": alert_email or gmail_user or ""
    }


@router.post("/notifications/gmail")
def save_gmail_settings(settings: GmailSettings):
    """Save Gmail notification credentials and alert email to .env"""
    try:
        if not settings.gmail_user or not settings.gmail_app_password:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Gmail user and app password are required")

        set_key(str(ENV_FILE), "GMAIL_USER", settings.gmail_user)
        set_key(str(ENV_FILE), "GMAIL_APP_PASSWORD", settings.gmail_app_password)
        set_key(str(ENV_FILE), "ALERT_EMAIL", settings.alert_email or settings.gmail_user)

        os.environ["GMAIL_USER"] = settings.gmail_user
        os.environ["GMAIL_APP_PASSWORD"] = settings.gmail_app_password
        os.environ["ALERT_EMAIL"] = settings.alert_email or settings.gmail_user

        logger.info("Gmail notification settings updated")
        return {"status": "success", "message": "Gmail settings saved"}
    except Exception as e:
        logger.error(f"Error saving Gmail settings: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/notifications/gmail/enabled")
def set_gmail_enabled(toggle: GmailToggle):
    """Enable or disable Gmail notifications"""
    try:
        val = "true" if toggle.enabled else "false"
        set_key(str(ENV_FILE), "NOTIFY_GMAIL_ENABLED", val)
        os.environ["NOTIFY_GMAIL_ENABLED"] = val
        return {"status": "success", "gmail_enabled": toggle.enabled}
    except Exception as e:
        logger.error(f"Error toggling Gmail notifications: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/notifications/gmail/test")
def send_test_email(subject: str = "FastTrade Test", body: str = "This is a test email from FastTrade"):
    """Send a test email using current Gmail settings"""
    try:
        # Use DB session for NotificationService
        db = SessionLocal()
        service = NotificationService(db)
        # Call internal email sender
        service._send_email(subject, body)  # noqa: SLF001
        db.close()
        return {"status": "success", "message": "Test email sent"}
    except Exception as e:
        logger.error(f"Error sending test email: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
