from decouple import config
import os

class Settings:
    # Email folder configuration
    EMAIL_FOLDER_PATH: str = config("EMAIL_FOLDER_PATH", default="./emails")
    
    # API configuration
    API_TITLE: str = "Email Reader API"
    API_VERSION: str = "1.0.0"
    API_DESCRIPTION: str = "FastAPI application for reading and managing .msg email files"
    
    # Server configuration
    HOST: str = config("HOST", default="0.0.0.0")
    PORT: int = config("PORT", default=8000, cast=int)
    DEBUG: bool = config("DEBUG", default=True, cast=bool)
    
    # File download limits
    MAX_DOWNLOAD_SIZE: int = config("MAX_DOWNLOAD_SIZE", default=100 * 1024 * 1024, cast=int)  # 100MB
    
    # Pagination
    DEFAULT_PAGE_SIZE: int = config("DEFAULT_PAGE_SIZE", default=20, cast=int)
    MAX_PAGE_SIZE: int = config("MAX_PAGE_SIZE", default=100, cast=int)

    # Authentication settings
    AUTH_USERNAME: str = config("AUTH_USERNAME", default="admin")
    AUTH_PASSWORD: str = config("AUTH_PASSWORD", default="admin123")
    JWT_SECRET_KEY: str = config("JWT_SECRET_KEY", default="change_this_secret")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = config("JWT_EXPIRE_MINUTES", default=60, cast=int)

settings = Settings()
