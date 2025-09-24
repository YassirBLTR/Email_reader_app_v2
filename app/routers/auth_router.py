from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Dict

from app.security.auth import (
    create_access_token,
    verify_password,
    get_current_user,
    ADMIN_USERNAME,
    USER_USERNAME,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
async def login(req: Request, body: LoginRequest) -> Dict[str, str]:
    """Authenticate a user (admin or normal user) and return a JWT access token with role claim."""
    username = body.username
    password = body.password

    if not verify_password(username, password):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    # Determine role by username
    if username == ADMIN_USERNAME:
        role = "admin"
    elif username == USER_USERNAME:
        role = "user"
    else:
        # Should not happen due to verify_password, but guard anyway
        raise HTTPException(status_code=401, detail="Invalid username or password")

    access_token = create_access_token({"sub": username, "role": role})
    return {"access_token": access_token, "token_type": "bearer", "role": role, "username": username}


@router.get("/me")
async def me(current_user: Dict = Depends(get_current_user)) -> Dict:
    """Return the current authenticated user's info (username and role)."""
    return current_user


@router.post("/logout")
async def logout() -> Dict[str, str]:
    """Stateless logout endpoint. Clients should delete the stored token.
    Provided for UI symmetry; no server-side token store is used.
    """
    return {"status": "ok"}
