from fastapi import APIRouter, Body, Depends, HTTPException, status

from app.core.auth import create_access_token, require_authenticated_user, verify_login_credentials

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login")
def login(
    username: str = Body(..., embed=True),
    password: str = Body(..., embed=True),
):
    if not verify_login_credentials(username=username, password=password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    token = create_access_token(username=username)
    return token


@router.get("/me")
def me(current_user=Depends(require_authenticated_user)):
    return {
        "username": current_user.get("username"),
        "auth_enabled": current_user.get("auth_enabled", True),
        "token_exp": current_user.get("exp"),
    }
