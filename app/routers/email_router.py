from fastapi import APIRouter, HTTPException, Query, Depends, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from typing import Optional, List
from datetime import datetime
import os
import tempfile
import logging

from app.models.email_models import (
    EmailListResponse, EmailDetail, EmailSearchRequest, 
    DownloadRequest, EmailFormat
)
from app.services.email_service import EmailService
from app.services.file_service import FileService
from app.config import settings
from app.security.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/emails", tags=["emails"], dependencies=[Depends(get_current_user)])

# Dependency to get email service
def get_email_service() -> EmailService:
    return EmailService()

@router.get("/", response_model=EmailListResponse)
async def list_emails(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=settings.MAX_PAGE_SIZE, description="Items per page"),
    email_service: EmailService = Depends(get_email_service)
):
    """Get paginated list of emails"""
    try:
        emails, total_count = email_service.get_emails_summary(page, page_size)
        total_pages = (total_count + page_size - 1) // page_size
        
        return EmailListResponse(
            emails=emails,
            total_count=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )
    except Exception as e:
        logger.error(f"Error listing emails: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/search", response_model=EmailListResponse)
async def search_emails(
    search_request: EmailSearchRequest,
    email_service: EmailService = Depends(get_email_service)
):
    """Search emails with filters"""
    try:
        emails, total_count = email_service.search_emails(search_request)
        total_pages = (total_count + search_request.page_size - 1) // search_request.page_size
        
        return EmailListResponse(
            emails=emails,
            total_count=total_count,
            page=search_request.page,
            page_size=search_request.page_size,
            total_pages=total_pages
        )
    except Exception as e:
        logger.error(f"Error searching emails: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{filename}", response_model=EmailDetail)
async def get_email_detail(
    filename: str,
    email_service: EmailService = Depends(get_email_service)
):
    """Get detailed information for a specific email"""
    try:
        email_detail = email_service.get_email_detail(filename)
        if not email_detail:
            raise HTTPException(status_code=404, detail="Email not found")
        
        return email_detail
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting email detail: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/download")
async def download_emails(
    download_request: DownloadRequest,
    background_tasks: BackgroundTasks,
    email_service: EmailService = Depends(get_email_service)
):
    """Download selected emails in specified format"""
    try:
        if not download_request.filenames:
            raise HTTPException(status_code=400, detail="No files specified for download")
        
        # If format is ORIGINAL, zip and return raw .msg files without parsing
        if download_request.format == EmailFormat.ORIGINAL:
            # Resolve full paths for requested filenames
            file_paths: list[str] = []
            for name in download_request.filenames:
                full = email_service._find_email_file(name)
                if full:
                    file_paths.append(full)
            if not file_paths:
                raise HTTPException(status_code=404, detail="No emails found for download")
            temp_file_path = FileService.create_original_zip(file_paths)
            media_type = "application/zip"
            filename = "emails_original.zip"
        else:
            # Get email data (parsed) for json/text exports
            emails_data = email_service.get_emails_for_download(
                download_request.filenames,
                download_request.format.value,
                download_request.include_attachments
            )
            
            if not emails_data:
                raise HTTPException(status_code=404, detail="No emails found for download")
            
            # Create download file
            if download_request.format == EmailFormat.JSON:
                temp_file_path = FileService.create_json_download(emails_data)
                media_type = "application/json"
                filename = "emails_export.json"
            else:
                temp_file_path = FileService.create_text_download(emails_data)
                media_type = "text/plain"
                filename = "emails_export.txt"
        
        # Schedule cleanup of temporary file
        background_tasks.add_task(cleanup_temp_file, temp_file_path)
        
        return FileResponse(
            path=temp_file_path,
            media_type=media_type,
            filename=filename
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading emails: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/stats/summary")
async def get_email_stats(
    email_service: EmailService = Depends(get_email_service)
):
    """Get email statistics summary"""
    try:
        msg_files = email_service.get_email_files()
        total_count = len(msg_files)
        
        # Calculate basic stats
        total_size = 0
        emails_with_attachments = 0
        
        for file_path in msg_files[:100]:  # Sample first 100 for performance
            try:
                file_size = os.path.getsize(file_path)
                total_size += file_size
                
                summary = email_service.msg_parser.get_msg_summary(file_path)
                if summary and summary.get('has_attachments'):
                    emails_with_attachments += 1
            except Exception:
                continue
        
        return {
            "total_emails": total_count,
            "total_size_bytes": total_size,
            "emails_with_attachments": emails_with_attachments,
            "email_folder": settings.EMAIL_FOLDER_PATH
        }
    except Exception as e:
        logger.error(f"Error getting email stats: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

def cleanup_temp_file(file_path: str):
    """Background task to cleanup temporary files"""
    try:
        if os.path.exists(file_path):
            os.unlink(file_path)
    except Exception as e:
        logger.error(f"Error cleaning up temp file {file_path}: {str(e)}")
