from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Dict

from app.security.auth import create_access_token, verify_password, STATIC_USERNAME

router = APIRouter(prefix="/api/auth", tags=["auth"])

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/login")
async def login(req: Request, body: LoginRequest) -> Dict[str, str]:
    # Validate username
    if body.username != STATIC_USERNAME or not verify_password(body.password):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    access_token = create_access_token({"sub": body.username})
    return {"access_token": access_token, "token_type": "bearer"}
