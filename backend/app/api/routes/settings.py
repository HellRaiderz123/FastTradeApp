from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
import os
import json
import logging
from pathlib import Path
from typing import Dict, List
from dotenv import load_dotenv, set_key

from app.core.broker.indmoney.client import INDMoneyClient
from app.core.broker.indmoney.instruments import INDMoneyInstrumentsResolver
from app.core.execution.mode import normalize_execution_mode
from app.services.notifications import NotificationService
from app.db.session import SessionLocal
from app.db.risk_repo import get_or_create_risk_limits, update_risk_limits
from app.db.models_risk import default_iv_limits

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


class BrokerSettingsResponse(BaseModel):
    """Response for active broker settings"""
    active_broker: str
    supported_brokers: List[str]


class BrokerUpdateRequest(BaseModel):
    """Payload for broker switch"""
    broker: str

class INDMoneyAccessToken(BaseModel):
    """Model for INDMoney access token"""
    access_token: str


class INDMoneySecurityLookupRequest(BaseModel):
    """Model for INDMoney symbol lookup"""
    symbol: str


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


class IVRegimeLimit(BaseModel):
    min_atm_dist_pct: float
    max_risk_pct_capital: float


class RiskLimitsPayload(BaseModel):
    max_portfolio_loss_pct: float
    max_trades_per_day: int
    iv_regime_limits: Dict[str, IVRegimeLimit]


def get_env_value(key: str) -> str:
    """Get environment variable value"""
    return os.getenv(key, "")


SUPPORTED_BROKERS = ["ZERODHA", "INDMONEY"]


def normalize_broker_name(broker: str | None) -> str:
    raw = (broker or "").strip().upper().replace(" ", "")
    aliases = {
        "IND_MONEY": "INDMONEY",
        "IND-MONEY": "INDMONEY",
    }
    normalized = aliases.get(raw, raw)
    if normalized in SUPPORTED_BROKERS:
        return normalized
    return "ZERODHA"


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


@router.get("/broker", response_model=BrokerSettingsResponse)
def get_broker_settings():
    """Get currently active broker and supported brokers."""
    active = normalize_broker_name(get_env_value("ACTIVE_BROKER"))
    return BrokerSettingsResponse(
        active_broker=active,
        supported_brokers=SUPPORTED_BROKERS,
    )


@router.post("/broker")
def set_active_broker(payload: BrokerUpdateRequest):
    """Set active broker for execution routing."""
    raw = (payload.broker or "").strip().upper().replace(" ", "")
    aliases = {
        "IND_MONEY": "INDMONEY",
        "IND-MONEY": "INDMONEY",
    }
    broker = aliases.get(raw, raw)

    if broker not in SUPPORTED_BROKERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid broker. Valid brokers: {', '.join(SUPPORTED_BROKERS)}"
        )

    set_key(str(ENV_FILE), "ACTIVE_BROKER", broker)
    os.environ["ACTIVE_BROKER"] = broker

    logger.info("Active broker changed to %s", broker)
    return {
        "status": "success",
        "active_broker": broker,
    }


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


# ─── Zerodha OAuth Flow ───────────────────────────────────────────────────

@router.get("/zerodha/login-url")
def get_zerodha_login_url(callback_url: str = "http://localhost:5173/settings"):
    """
    Get Zerodha OAuth login URL.
    
    User clicks link to open login, then Zerodha redirects to callback_url
    with request_token parameter.
    
    Args:
        callback_url: Where Zerodha redirects after login (default: frontend settings page)
        
    Returns:
        {"login_url": "https://kite.zerodha.com/connect/..."}
    """
    try:
        from app.core.broker.zerodha.oauth import get_login_url
        
        login_url = get_login_url(callback_url)
        logger.info(f"Generated Zerodha login URL")
        return {"login_url": login_url}
        
    except Exception as e:
        logger.error(f"Error generating login URL: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating login URL: {str(e)}"
        )


@router.get("/zerodha/callback")
def zerodha_oauth_callback(request_token: str):
    """
    OAuth callback endpoint — Zerodha redirects here with request_token.
    
    Exchanges request_token for access_token and stores in DB.
    No app restart needed after this.
    
    Args:
        request_token: Token from Zerodha after user login
        
    Returns:
        {"status": "success", "access_token": "token", "user_id": "id"}
    """
    try:
        from app.core.broker.zerodha.oauth import exchange_request_token_for_access_token
        
        if not request_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="request_token is required"
            )
        
        db = SessionLocal()
        try:
            access_token = exchange_request_token_for_access_token(db, request_token)
            if not access_token:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to generate access token"
                )
            
            # Get session to return user_id
            from app.core.broker.zerodha.oauth import get_active_session
            session = get_active_session(db)
            
            logger.info("✅ Zerodha OAuth callback successful")
            return {
                "status": "success",
                "access_token": access_token,
                "user_id": session.user_id if session else None,
                "message": "You are now logged in! No restart needed."
            }
        finally:
            db.close()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in OAuth callback: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OAuth callback failed: {str(e)}"
        )


@router.get("/zerodha/session-status")
def get_zerodha_session_status():
    """
    Check if user has an active Zerodha session in DB.
    
    Returns:
        {"has_active_session": bool, "user_id": str, "expires_at": datetime}
    """
    try:
        from app.core.broker.zerodha.oauth import get_active_session
        
        db = SessionLocal()
        try:
            session = get_active_session(db)
            if session:
                return {
                    "has_active_session": True,
                    "user_id": session.user_id,
                    "expires_at": session.expires_at.isoformat() if session.expires_at else None,
                    "created_at": session.created_at.isoformat() if session.created_at else None,
                }
            else:
                # No active session in DB, check .env fallback
                env_token = os.getenv("ZERODHA_ACCESS_TOKEN")
                return {
                    "has_active_session": False,
                    "fallback_to_env": bool(env_token),
                    "message": "No active DB session. Using .env fallback." if env_token else "No active session found."
                }
        finally:
            db.close()
        
    except Exception as e:
        logger.error(f"Error checking session status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error checking session: {str(e)}"
        )


@router.post("/zerodha/logout")
def zerodha_logout():
    """
    Logout current Zerodha session (mark as inactive in DB).
    
    Returns:
        {"status": "success", "message": "Logged out"}
    """
    try:
        from app.core.broker.zerodha.oauth import get_active_session
        
        db = SessionLocal()
        try:
            session = get_active_session(db)
            if session:
                session.is_active = 0
                db.commit()
                logger.info("Zerodha session deactivated")
                return {"status": "success", "message": "Logged out"}
            else:
                return {"status": "success", "message": "No active session to logout"}
        finally:
            db.close()
        
    except Exception as e:
        logger.error(f"Error logging out: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error logging out: {str(e)}"
        )


# ─── INDMoney Settings ────────────────────────────────────────────────────

@router.get("/indmoney", response_model=SettingsResponse)
def get_indmoney_settings():
    """
    Get current INDMoney settings status.
    
    Returns:
        - api_key_set: Boolean indicating if API key is configured (always False for INDMoney)
        - access_token_set: Boolean indicating if access token is set
        - execution_mode: Current execution mode
    """
    return SettingsResponse(
        api_key_set=bool(get_env_value("INDMONEY_API_KEY")),
        access_token_set=bool(get_env_value("INDMONEY_ACCESS_TOKEN")),
        execution_mode=normalize_execution_mode(get_env_value("EXECUTION_MODE"))
    )


@router.post("/indmoney/token")
def save_indmoney_token(token: INDMoneyAccessToken):
    """
    Save INDMoney access token to .env file.
    
    Get your token from: https://indstocks.com/app/api-trading
    
    Args:
        access_token: The access token from INDstocks API portal
        
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
        set_key(str(ENV_FILE), "INDMONEY_ACCESS_TOKEN", token.access_token)
        
        # Update environment variable
        os.environ["INDMONEY_ACCESS_TOKEN"] = token.access_token
        
        logger.info("INDMoney access token updated successfully")
        return {
            "status": "success",
            "message": "INDMoney access token saved successfully"
        }
    except Exception as e:
        logger.error(f"Error saving INDMoney token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error saving token: {str(e)}"
        )


@router.post("/indmoney/resolve-security")
def resolve_indmoney_security(payload: INDMoneySecurityLookupRequest):
    """Resolve INDMoney security_id from a trading symbol using instruments API cache."""
    symbol = (payload.symbol or "").strip()
    if not symbol:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Symbol is required"
        )

    try:
        normalized = symbol.upper().replace(" ", "")

        env_map_raw = os.getenv("INDMONEY_SECURITY_MAP_JSON", "{}")
        env_map: Dict[str, str] = {}
        try:
            parsed = json.loads(env_map_raw)
            if isinstance(parsed, dict):
                env_map = {str(k).upper().replace(" ", ""): str(v) for k, v in parsed.items()}
        except Exception:
            env_map = {}

        if normalized in env_map:
            return {
                "symbol": symbol,
                "normalized_symbol": normalized,
                "security_id": env_map[normalized],
                "source": "env_map",
            }

        resolver = INDMoneyInstrumentsResolver(INDMoneyClient())
        security_id = resolver.resolve_security_id(symbol)
        if security_id:
            return {
                "symbol": symbol,
                "normalized_symbol": normalized,
                "security_id": str(security_id),
                "source": "instruments_api",
            }

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No security_id found for symbol '{symbol}'. "
                "Check symbol spelling or add it in INDMONEY_SECURITY_MAP_JSON."
            ),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error resolving INDMoney security_id for symbol %s: %s", symbol, str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error resolving security_id: {str(e)}"
        )


@router.get("/trading")
def get_trading_settings():
    """Get current trading settings (risk per trade, max trades per day)"""
    db = SessionLocal()
    try:
        record = get_or_create_risk_limits(db)
        return {
            "risk_per_trade": record.max_portfolio_loss_pct,
            "max_trades_per_day": record.max_trades_per_day,
        }
    finally:
        db.close()


@router.post("/trading")
def save_trading_settings(settings: TradingSettings):
    """Save trading settings to the DB (no restart needed)."""
    try:
        if settings.risk_per_trade < 0.1 or settings.risk_per_trade > 15:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Risk per trade must be between 0.1% and 15%",
            )

        if settings.max_trades_per_day < 1 or settings.max_trades_per_day > 50:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Max trades per day must be between 1 and 50",
            )

        db = SessionLocal()
        record = get_or_create_risk_limits(db)
        update_risk_limits(
            db,
            max_portfolio_loss_pct=settings.risk_per_trade,
            max_trades_per_day=settings.max_trades_per_day,
            iv_regime_limits=record.iv_regime_limits or default_iv_limits(),
        )

        # Keep process env in sync for legacy fallbacks (but don't touch .env)
        os.environ["RISK_PER_TRADE"] = str(settings.risk_per_trade)
        os.environ["MAX_TRADES_PER_DAY"] = str(settings.max_trades_per_day)

        logger.info(
            f"Trading settings updated in DB: risk={settings.risk_per_trade}%, max_trades={settings.max_trades_per_day}"
        )
        return {
            "status": "success",
            "message": "Trading settings saved successfully",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving trading settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error saving trading settings: {str(e)}",
        )
    finally:
        try:
            db.close()
        except Exception:
            pass


@router.get("/risk")
def get_risk_limits_settings():
    """Return full risk limits including IV-regime caps from the DB."""
    db = SessionLocal()
    try:
        record = get_or_create_risk_limits(db)
        return {
            "max_portfolio_loss_pct": record.max_portfolio_loss_pct,
            "max_trades_per_day": record.max_trades_per_day,
            "iv_regime_limits": record.iv_regime_limits or default_iv_limits(),
        }
    except Exception as e:
        logger.error(f"Error fetching risk limits: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching risk limits: {e}",
        )
    finally:
        db.close()


@router.post("/risk")
def save_risk_limits(settings: RiskLimitsPayload):
    """Persist risk limits (portfolio + IV regimes) to the DB."""
    try:
        if settings.max_portfolio_loss_pct < 0.1 or settings.max_portfolio_loss_pct > 25:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Max portfolio loss per trade must be between 0.1% and 25%",
            )

        if settings.max_trades_per_day < 1 or settings.max_trades_per_day > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Max trades per day must be between 1 and 100",
            )

        iv_limits_models = settings.iv_regime_limits or {}
        # Convert Pydantic models to plain dicts for JSON storage
        iv_limits: Dict[str, dict] = {}
        for regime, limits in iv_limits_models.items():
            if limits.min_atm_dist_pct < 0 or limits.min_atm_dist_pct > 5:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"min_atm_dist_pct for {regime} must be between 0 and 5",
                )
            if limits.max_risk_pct_capital < 0.1 or limits.max_risk_pct_capital > 50:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"max_risk_pct_capital for {regime} must be between 0.1 and 50",
                )
            iv_limits[regime] = limits.dict()

        db = SessionLocal()
        update_risk_limits(
            db,
            max_portfolio_loss_pct=settings.max_portfolio_loss_pct,
            max_trades_per_day=settings.max_trades_per_day,
            iv_regime_limits=iv_limits or default_iv_limits(),
        )

        # Sync process env for legacy callers
        os.environ["RISK_PER_TRADE"] = str(settings.max_portfolio_loss_pct)
        os.environ["MAX_TRADES_PER_DAY"] = str(settings.max_trades_per_day)

        logger.info(
            "Risk limits updated in DB: loss_pct=%s, max_trades=%s",
            settings.max_portfolio_loss_pct,
            settings.max_trades_per_day,
        )
        return {"status": "success", "message": "Risk limits saved"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving risk limits: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error saving risk limits: {e}",
        )
    finally:
        try:
            db.close()
        except Exception:
            pass

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

# ============ ML Settings ============

@router.get("/ml")
def get_ml_settings():
    """Get ML settings from localStorage-like storage"""
    try:
        settings_file = Path("data/ml_settings.json")
        if settings_file.exists():
            with open(settings_file, "r", encoding="utf-8") as f:
                return json.load(f)
        
        # Default settings
        return {
            "enabled": True,
            "confidence_threshold": 0.65,
            "auto_train_enabled": False,
            "retraining_frequency": "weekly"
        }
    except Exception as e:
        logger.error(f"Error loading ML settings: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/ml")
def save_ml_settings(data: dict):
    """Save ML settings"""
    try:
        settings_dir = Path("data")
        settings_dir.mkdir(parents=True, exist_ok=True)
        
        settings_file = settings_dir / "ml_settings.json"
        with open(settings_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        
        return {"status": "success", "message": "ML settings saved"}
    except Exception as e:
        logger.error(f"Error saving ML settings: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))