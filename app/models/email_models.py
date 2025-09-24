from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class EmailFormat(str, Enum):
    JSON = "json"
    TEXT = "text"
    ORIGINAL = "original"  # original .msg files zipped without parsing

class FilterType(str, Enum):
    DATE = "date"
    SUBJECT = "subject"
    SENDER = "sender"
    RECIPIENT = "recipient"

class EmailSummary(BaseModel):
    filename: str
    subject: Optional[str] = None
    sender: Optional[str] = None
    recipients: Optional[List[str]] = None
    date: Optional[datetime] = None
    size: int
    has_attachments: bool = False
    attachment_count: int = 0

class EmailDetail(BaseModel):
    filename: str
    subject: Optional[str] = None
    sender: Optional[str] = None
    recipients: Optional[List[str]] = None
    cc: Optional[List[str]] = None
    bcc: Optional[List[str]] = None
    date: Optional[datetime] = None
    body: Optional[str] = None
    html_body: Optional[str] = None
    attachments: Optional[List[Dict[str, Any]]] = None
    headers: Optional[Dict[str, str]] = None
    size: int
    message_id: Optional[str] = None

class EmailListResponse(BaseModel):
    emails: List[EmailSummary]
    total_count: int
    page: int
    page_size: int
    total_pages: int

class EmailSearchRequest(BaseModel):
    query: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    sender: Optional[str] = None
    subject: Optional[str] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    
    # Add aliases for backward compatibility
    @property
    def start_date(self) -> Optional[datetime]:
        return self.date_from
    
    @property
    def end_date(self) -> Optional[datetime]:
        return self.date_to

class DownloadRequest(BaseModel):
    filenames: List[str]
    format: EmailFormat = EmailFormat.JSON
    include_attachments: bool = False
