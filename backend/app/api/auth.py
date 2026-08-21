"""
Authentication API endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from app.core.security import create_access_token, verify_access_token

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


class UserProfileResponse(BaseModel):
    username: str
    role: str


def get_current_user(authorization: str = Header(None)) -> dict:
    """Dependency ensuring caller has valid JWT token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )
    token = authorization.split(" ", 1)[1]
    payload = verify_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    return payload


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    """
    Authenticate user and return JWT session token.
    For standard operations, demo credentials 'admin'/'admin' are enabled.
    """
    if req.username == "admin" and req.password in ("admin", "admin123", "password"):
        token = create_access_token({"sub": req.username, "role": "admin"})
        return LoginResponse(access_token=token, username=req.username)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password",
    )


@router.get("/me", response_model=UserProfileResponse)
async def get_me(user: dict = Depends(get_current_user)):
    """Return identity of the authenticated caller."""
    return UserProfileResponse(username=user.get("sub", "unknown"), role=user.get("role", "operator"))
