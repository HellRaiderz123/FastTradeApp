from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.auth import create_access_token, require_authenticated_user, require_admin, verify_login_credentials
from app.db.session import SessionLocal
from app.db.user_repo import authenticate_user, create_user, get_all_users, get_user_by_username, update_user_password

router = APIRouter(prefix="/auth", tags=["Authentication"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class RegisterRequest(BaseModel):
    username: str
    password: str
    email: str | None = None
    role: str = "user"


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/login")
def login(
    username: str = Body(..., embed=True),
    password: str = Body(..., embed=True),
    db: Session = Depends(get_db),
):
    # Try DB auth first
    user = authenticate_user(db, username, password)

    if not user:
        # Fallback: env-based auth for backward compatibility
        # (works on first boot before admin is seeded)
        if not verify_login_credentials(username=username, password=password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
            )
        # Env login succeeded — return token without user_id
        return create_access_token(username=username, role="admin")

    return create_access_token(username=user.username, user_id=user.id, role=user.role)


@router.get("/me")
def me(current_user=Depends(require_authenticated_user)):
    return {
        "username": current_user.get("username"),
        "user_id": current_user.get("user_id"),
        "role": current_user.get("role", "user"),
        "auth_enabled": current_user.get("auth_enabled", True),
        "token_exp": current_user.get("exp"),
    }


@router.post("/register")
def register(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),   # only admins can create users
):
    if get_user_by_username(db, payload.username):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")

    if len(payload.password) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 8 characters")

    user = create_user(
        db,
        username=payload.username,
        password=payload.password,
        email=payload.email,
        role=payload.role,
    )
    return {"id": user.id, "username": user.username, "role": user.role}


@router.get("/users")
def list_users(
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    users = get_all_users(db)
    return [{"id": u.id, "username": u.username, "email": u.email, "role": u.role, "created_at": u.created_at} for u in users]


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_authenticated_user),
):
    user = authenticate_user(db, current_user["username"], payload.current_password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Current password is incorrect")

    if len(payload.new_password) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 8 characters")

    update_user_password(db, user.id, payload.new_password)
    return {"status": "success", "message": "Password updated"}
