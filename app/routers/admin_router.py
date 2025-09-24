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
        # Update meta file with added_at timestamp
        try:
            _update_meta_added(relay_file, domain_raw)
        except Exception as me:
            logger.warning(f"Failed to update meta for domain {domain_raw}: {me}")
        return {"message": "Domain added", "domain": domain_raw}
    except Exception as e:
        logger.error(f"Failed to append to relay file {relay_file}: {e}")
        raise HTTPException(status_code=500, detail="Failed to write relay domains file")


def _get_meta_path(relay_file: str) -> str:
    return relay_file + ".meta.json"


def _load_meta(relay_file: str) -> Dict[str, Dict[str, str]]:
    path = _get_meta_path(relay_file)
    if not os.path.exists(path):
        return {}
    try:
        import json
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
            return {}
    except Exception:
        return {}


def _save_meta(relay_file: str, meta: Dict[str, Dict[str, str]]) -> None:
    path = _get_meta_path(relay_file)
    try:
        import json
        with open(path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Failed saving meta file {path}: {e}")


def _update_meta_added(relay_file: str, domain: str) -> None:
    from datetime import datetime, timezone
    meta = _load_meta(relay_file)
    meta[domain] = meta.get(domain, {})
    meta[domain]["added_at"] = datetime.now(timezone.utc).isoformat()
    _save_meta(relay_file, meta)


def _read_domains(relay_file: str) -> list[str]:
    domains: list[str] = []
    line_re = re.compile(r"^\s*relay-domain\s+\*\.([A-Za-z0-9.-]+)\s*$", re.IGNORECASE)
    if not os.path.exists(relay_file):
        return domains
    try:
        with open(relay_file, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                m = line_re.match(line.strip())
                if m:
                    domains.append(m.group(1).lower())
    except Exception as e:
        logger.error(f"Failed reading relay file {relay_file}: {e}")
        raise HTTPException(status_code=500, detail="Failed to read relay domains file")
    return domains


@router.get("/domains")
async def list_domains() -> Dict[str, list[Dict[str, str]]]:
    relay_file = settings.RELAYDOMAINS_PATH
    items: list[Dict[str, str]] = []
    domains = _read_domains(relay_file)
    meta = _load_meta(relay_file)
    for d in domains:
        added_at = (meta.get(d) or {}).get("added_at")
        items.append({"domain": d, "added_at": added_at})
    # Sort by added_at desc if available
    items.sort(key=lambda x: x.get("added_at") or "", reverse=True)
    return {"domains": items}


@router.delete("/domains/{domain}")
async def delete_domain(domain: str) -> Dict[str, str]:
    domain = (domain or "").strip().lower()
    if not domain or not DOMAIN_REGEX.match(domain):
        raise HTTPException(status_code=400, detail="Invalid domain")
    relay_file = settings.RELAYDOMAINS_PATH
    if not os.path.exists(relay_file):
        raise HTTPException(status_code=404, detail="Relay file not found")
    # Rewrite file without matching line(s)
    line_to_remove_re = re.compile(r"^\s*relay-domain\s+\*\." + re.escape(domain) + r"\s*$", re.IGNORECASE)
    try:
        with open(relay_file, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        new_lines = [ln for ln in lines if not line_to_remove_re.match(ln.strip())]
        if len(new_lines) == len(lines):
            raise HTTPException(status_code=404, detail="Domain not found")
        with open(relay_file, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        # Update meta
        meta = _load_meta(relay_file)
        if domain in meta:
            meta.pop(domain, None)
            _save_meta(relay_file, meta)
        return {"message": "Domain deleted", "domain": domain}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete domain {domain}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update relay domains file")


class UpdateDomainRequest(BaseModel):
    new_domain: str


@router.put("/domains/{domain}")
async def update_domain(domain: str, body: UpdateDomainRequest) -> Dict[str, str]:
    old_domain = (domain or "").strip().lower()
    new_domain = (body.new_domain or "").strip().lower()
    if not old_domain or not DOMAIN_REGEX.match(old_domain):
        raise HTTPException(status_code=400, detail="Invalid old domain")
    if not new_domain or not DOMAIN_REGEX.match(new_domain):
        raise HTTPException(status_code=400, detail="Invalid new domain")
    if old_domain == new_domain:
        return {"message": "No changes", "domain": new_domain}

    relay_file = settings.RELAYDOMAINS_PATH
    if not os.path.exists(relay_file):
        raise HTTPException(status_code=404, detail="Relay file not found")

    # Ensure new domain not already present
    domains = set(_read_domains(relay_file))
    if new_domain in domains:
        raise HTTPException(status_code=409, detail="New domain already exists")

    old_line_re = re.compile(r"^\s*relay-domain\s+\*\." + re.escape(old_domain) + r"\s*$", re.IGNORECASE)
    try:
        with open(relay_file, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        replaced = False
        with open(relay_file, "w", encoding="utf-8") as f:
            for ln in lines:
                if not replaced and old_line_re.match(ln.strip()):
                    f.write(f"relay-domain *.{new_domain}\n")
                    replaced = True
                else:
                    f.write(ln)
        if not replaced:
            raise HTTPException(status_code=404, detail="Old domain not found")
        # Update meta: move added_at under new key
        meta = _load_meta(relay_file)
        if old_domain in meta:
            meta[new_domain] = meta.pop(old_domain)
            _save_meta(relay_file, meta)
        else:
            # No meta existed for old domain; write a new added_at timestamp
            _update_meta_added(relay_file, new_domain)
        return {"message": "Domain updated", "domain": new_domain}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update domain {old_domain} -> {new_domain}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update relay domains file")
