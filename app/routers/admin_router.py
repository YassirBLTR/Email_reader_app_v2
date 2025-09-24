from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Dict
import os
import re
import logging

from app.security.auth import require_admin
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)

# Regex for domain validation: labels of [a-z0-9-], no leading/trailing hyphen, TLD letters only 2-24
DOMAIN_REGEX = re.compile(r"^(?=.{1,253}$)(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,24}$")


class AddDomainRequest(BaseModel):
    domain: str


@router.post("/domains", status_code=201)
async def add_domain(body: AddDomainRequest) -> Dict[str, str]:
    domain_raw = (body.domain or "").strip().lower()

    if not domain_raw:
        raise HTTPException(status_code=400, detail="Domain is required")

    # Basic validation: only valid domain names, TLD alpha 2-24
    if not DOMAIN_REGEX.match(domain_raw):
        raise HTTPException(status_code=400, detail="Invalid domain name. Use a valid domain like example.com")

    relay_dir = settings.RELAYDOMAINS_PATH
    try:
        if not os.path.isdir(relay_dir):
            if settings.DEBUG:
                os.makedirs(relay_dir, exist_ok=True)
            else:
                raise HTTPException(status_code=500, detail=f"Relay domains path not found: {relay_dir}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error ensuring relay directory exists: {e}")
        raise HTTPException(status_code=500, detail="Failed to access relay domains directory")

    # Filename is the domain itself (e.g., /etc/pmta/relaydomains-c/example.com)
    file_path = os.path.join(relay_dir, domain_raw)

    if os.path.exists(file_path):
        raise HTTPException(status_code=409, detail="Domain already exists")

    content = f"relay-domain *.{domain_raw}\n"

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"Added relay domain: {domain_raw} -> {file_path}")
        return {"message": "Domain added", "domain": domain_raw}
    except Exception as e:
        logger.error(f"Failed to write domain file {file_path}: {e}")
        raise HTTPException(status_code=500, detail="Failed to write domain file")
