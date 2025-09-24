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

    # Treat RELAYDOMAINS_PATH as a single file to append lines to
    relay_file = settings.RELAYDOMAINS_PATH
    relay_dir = os.path.dirname(relay_file) or "."
    try:
        if relay_dir and not os.path.isdir(relay_dir):
            if settings.DEBUG:
                os.makedirs(relay_dir, exist_ok=True)
            else:
                raise HTTPException(status_code=500, detail=f"Relay domains directory not found: {relay_dir}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error ensuring relay directory exists: {e}")
        raise HTTPException(status_code=500, detail="Failed to access relay domains directory")

    # Check for duplicates if file exists
    existing_matches = False
    line_re = re.compile(r"^\s*relay-domain\s+\*\." + re.escape(domain_raw) + r"\s*$", re.IGNORECASE)
    try:
        if os.path.exists(relay_file):
            with open(relay_file, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if line_re.match(line.strip()):
                        existing_matches = True
                        break
    except Exception as e:
        logger.error(f"Failed reading relay file {relay_file}: {e}")
        raise HTTPException(status_code=500, detail="Failed to read relay domains file")

    if existing_matches:
        raise HTTPException(status_code=409, detail="Domain already exists")

    content = f"relay-domain *.{domain_raw}\n"

    try:
        with open(relay_file, "a", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"Appended relay domain: {domain_raw} -> {relay_file}")
        return {"message": "Domain added", "domain": domain_raw}
    except Exception as e:
        logger.error(f"Failed to append to relay file {relay_file}: {e}")
        raise HTTPException(status_code=500, detail="Failed to write relay domains file")
