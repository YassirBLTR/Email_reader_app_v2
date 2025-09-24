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

@router.get("/test")
async def test_endpoint():
    """Simple test endpoint to verify admin routing works"""
    return {"status": "ok", "message": "Admin endpoint working"}

@router.get("/debug")
async def debug_endpoint():
    """Debug endpoint to check settings and basic functionality"""
    try:
        relay_file = settings.RELAYDOMAINS_PATH
        exists = os.path.exists(relay_file)
        return {
            "relay_file": relay_file,
            "exists": exists,
            "cwd": os.getcwd(),
            "settings_available": hasattr(settings, 'RELAYDOMAINS_PATH')
        }
    except Exception as e:
        return {
            "error": str(e),
            "type": type(e).__name__
        }

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
        # If the file exists and doesn't end with a newline, insert one before appending
        needs_leading_newline = False
        if os.path.exists(relay_file) and os.path.getsize(relay_file) > 0:
            try:
                with open(relay_file, "rb") as rf:
                    rf.seek(-1, os.SEEK_END)
                    last_byte = rf.read(1)
                if last_byte != b"\n":
                    needs_leading_newline = True
            except Exception:
                # If we fail to inspect last byte, just append normally
                needs_leading_newline = False

        with open(relay_file, "a", encoding="utf-8", newline="") as f:
            if needs_leading_newline:
                f.write("\n")
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
    logger.info(f"[_load_meta] Meta path: {path}")
    if not os.path.exists(path):
        logger.info(f"[_load_meta] Meta file does not exist, returning empty dict")
        return {}
    try:
        import json
        logger.info(f"[_load_meta] Reading meta file...")
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            data = json.load(f)
            if isinstance(data, dict):
                logger.info(f"[_load_meta] Loaded meta data with {len(data)} entries")
                return data
            logger.warning(f"[_load_meta] Meta data is not a dict: {type(data)}")
            return {}
    except Exception as e:
        logger.error(f"[_load_meta] Error loading meta file: {e}")
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
    logger.info(f"[_read_domains] Starting with file: {relay_file}")
    
    # More robust pattern that works even if multiple entries are concatenated without newlines
    pattern = re.compile(r"relay-domain\s+\*\.([A-Za-z0-9.-]+)", re.IGNORECASE)
    
    if not os.path.exists(relay_file):
        logger.info(f"[_read_domains] File does not exist: {relay_file}")
        return domains
        
    try:
        logger.info(f"[_read_domains] Opening file for reading...")
        with open(relay_file, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        logger.info(f"[_read_domains] Read {len(content)} characters")
        
        matches = list(pattern.finditer(content))
        logger.info(f"[_read_domains] Found {len(matches)} regex matches")
        
        for m in matches:
            domain = m.group(1).lower()
            domains.append(domain)
            logger.info(f"[_read_domains] Added domain: {domain}")
            
    except Exception as e:
        logger.error(f"[_read_domains] Failed reading relay file {relay_file}: {e}", exc_info=True)
        # Tolerate read errors by returning an empty list so the UI can load
        return domains
        
    logger.info(f"[_read_domains] Returning {len(domains)} domains: {domains}")
    return domains


@router.get("/domains")
async def list_domains() -> Dict:
    try:
        relay_file = settings.RELAYDOMAINS_PATH
        logger.info(f"[list_domains] Starting with relay_file: {relay_file}")
        
        items: list[Dict[str, str]] = []
        
        logger.info(f"[list_domains] Calling _read_domains...")
        domains = _read_domains(relay_file)
        logger.info(f"[list_domains] Found {len(domains)} domains: {domains}")
        
        logger.info(f"[list_domains] Loading meta...")
        meta = _load_meta(relay_file)
        logger.info(f"[list_domains] Meta keys: {list(meta.keys())}")
        
        for d in domains:
            added_at = (meta.get(d) or {}).get("added_at")
            items.append({"domain": d, "added_at": added_at})
            
        # Sort by added_at desc if available
        items.sort(key=lambda x: x.get("added_at") or "", reverse=True)
        
        try:
            exists = os.path.exists(relay_file)
            size = os.path.getsize(relay_file) if exists else 0
        except Exception as e:
            logger.warning(f"[list_domains] Error checking file stats: {e}")
            exists, size = False, 0
            
        result = {"domains": items, "relay_file": relay_file, "exists": exists, "size": size}
        logger.info(f"[list_domains] Returning: {result}")
        return result
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"[list_domains] Unexpected error: {e}", exc_info=True)
        # Return a proper JSON error response
        raise HTTPException(
            status_code=500, 
            detail={
                "error": "Internal server error",
                "message": str(e),
                "relay_file": getattr(settings, 'RELAYDOMAINS_PATH', 'unknown')
            }
        )


@router.delete("/domains/{domain}")
async def delete_domain(domain: str) -> Dict[str, str]:
    domain = (domain or "").strip().lower()
    if not domain or not DOMAIN_REGEX.match(domain):
        raise HTTPException(status_code=400, detail="Invalid domain")
    relay_file = settings.RELAYDOMAINS_PATH
    if not os.path.exists(relay_file):
        raise HTTPException(status_code=404, detail="Relay file not found")
    # Robust rewrite from parsed domain list
    try:
        domains = _read_domains(relay_file)
        if domain not in domains:
            raise HTTPException(status_code=404, detail="Domain not found")
        new_domains = [d for d in domains if d != domain]
        with open(relay_file, "w", encoding="utf-8", newline="") as f:
            for d in new_domains:
                f.write(f"relay-domain *.{d}\n")
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
    try:
        domains = _read_domains(relay_file)
        if new_domain in domains and new_domain != old_domain:
            raise HTTPException(status_code=409, detail="New domain already exists")
        if old_domain not in domains:
            raise HTTPException(status_code=404, detail="Old domain not found")
        new_domains = [new_domain if d == old_domain else d for d in domains]
        with open(relay_file, "w", encoding="utf-8", newline="") as f:
            for d in new_domains:
                f.write(f"relay-domain *.{d}\n")
        # Update meta: move added_at under new key
        meta = _load_meta(relay_file)
        if old_domain in meta:
            meta[new_domain] = meta.pop(old_domain)
            _save_meta(relay_file, meta)
        else:
            _update_meta_added(relay_file, new_domain)
        return {"message": "Domain updated", "domain": new_domain}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update domain {old_domain} -> {new_domain}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update relay domains file")
