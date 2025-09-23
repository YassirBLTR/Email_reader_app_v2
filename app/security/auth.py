from datetime import datetime, timedelta, timezone
from typing import Optional, Dict

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from passlib.context import CryptContext

from app.config import settings

# OAuth2 scheme (we'll use Bearer token in Authorization header)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# Password hashing context (optional; if AUTH_PASSWORD is plaintext we still work)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# For this app we keep a single user from env variables
STATIC_USERNAME = settings.AUTH_USERNAME
STATIC_PASSWORD = settings.AUTH_PASSWORD  # expected as plaintext; if you want bcrypt, set AUTH_PASSWORD_BCRYPT
STATIC_PASSWORD_BCRYPT = None
try:
    # If user provides a bcrypt hash in env, prefer it
    import os
    STATIC_PASSWORD_BCRYPT = os.environ.get("AUTH_PASSWORD_BCRYPT")
except Exception:
    pass


def verify_password(plain_password: str) -> bool:
    """Verify provided password against env. Supports bcrypt hash if provided."""
    if STATIC_PASSWORD_BCRYPT:
        try:
            return pwd_context.verify(plain_password, STATIC_PASSWORD_BCRYPT)
        except Exception:
            return False
    # Fallback to plain text compare
    return plain_password == STATIC_PASSWORD


def create_access_token(data: Dict, expires_minutes: Optional[int] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes or settings.JWT_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def get_current_user(token: str = Depends(oauth2_scheme)) -> Dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    # Only one static user is valid
    if username != STATIC_USERNAME:
        raise credentials_exception

    return {"username": username}
