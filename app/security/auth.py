from datetime import datetime, timedelta, timezone
from typing import Optional, Dict

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from passlib.context import CryptContext

import os
from app.config import settings

# OAuth2 scheme (we'll use Bearer token in Authorization header)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

# Password hashing context (optional; if AUTH_PASSWORD is plaintext we still work)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Built-in accounts: admin and normal user
ADMIN_USERNAME = settings.AUTH_USERNAME
ADMIN_PASSWORD = settings.AUTH_PASSWORD  # plaintext unless AUTH_PASSWORD_BCRYPT is provided
USER_USERNAME = settings.AUTH_USER_USERNAME
USER_PASSWORD = settings.AUTH_USER_PASSWORD  # plaintext unless AUTH_USER_PASSWORD_BCRYPT is provided

# Optional bcrypt hashes via env
ADMIN_PASSWORD_BCRYPT = os.environ.get("AUTH_PASSWORD_BCRYPT")
USER_PASSWORD_BCRYPT = os.environ.get("AUTH_USER_PASSWORD_BCRYPT")


def verify_password(username: str, plain_password: str) -> bool:
    """Verify provided password for the given username.

    Supports bcrypt if AUTH_PASSWORD_BCRYPT / AUTH_USER_PASSWORD_BCRYPT are provided, otherwise
    falls back to plaintext comparison from settings.
    """
    # Admin account
    if username == ADMIN_USERNAME:
        if ADMIN_PASSWORD_BCRYPT:
            try:
                return pwd_context.verify(plain_password, ADMIN_PASSWORD_BCRYPT)
            except Exception:
                return False
        return plain_password == ADMIN_PASSWORD
    # Normal user account
    if username == USER_USERNAME:
        if USER_PASSWORD_BCRYPT:
            try:
                return pwd_context.verify(plain_password, USER_PASSWORD_BCRYPT)
            except Exception:
                return False
        return plain_password == USER_PASSWORD
    return False


def create_access_token(data: Dict, expires_minutes: Optional[int] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes or settings.JWT_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def get_current_user(request: Request, token: Optional[str] = Depends(oauth2_scheme)) -> Dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    cookie_token = request.cookies.get("access_token")
    candidates = [t for t in [cookie_token, token] if t]
    if not candidates:
        raise credentials_exception
    last_error: Optional[Exception] = None
    username = None
    role: Optional[str] = None
    for candidate in candidates:
        try:
            payload = jwt.decode(candidate, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
            username = payload.get("sub")
            role = payload.get("role")
            if username is None:
                continue
            # successful decode
            break
        except JWTError as e:
            last_error = e
            continue
    if username is None:
        raise credentials_exception

    # Validate username and determine role if missing (backward compatibility)
    if username == ADMIN_USERNAME:
        expected_role = "admin"
    elif username == USER_USERNAME:
        expected_role = "user"
    else:
        raise credentials_exception

    if role is None:
        role = expected_role
    if role != expected_role:
        # Token role mismatch
        raise credentials_exception

    return {"username": username, "role": role}


def require_admin(current_user: Dict = Depends(get_current_user)) -> Dict:
    """Dependency to ensure the current user has admin role."""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")
    return current_user
