import os
import json
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
import logging
from pathlib import Path

from app.config import settings
from app.utils.msg_parser import MSGParser
from app.models.email_models import EmailSummary, EmailDetail, EmailSearchRequest

logger = logging.getLogger(__name__)

class EmailService:
    """Service class for handling email operations"""
    
    def __init__(self):
        self.email_folder = settings.EMAIL_FOLDER_PATH
        self.msg_parser = MSGParser()
    
    def get_email_files(self) -> List[str]:
        """Get list of all .msg files in the email folder"""
        try:
            email_folder = Path(self.email_folder)
            if not email_folder.exists():
                logger.warning(f"Email folder does not exist: {self.email_folder}")
                return []
            
            msg_files = []
            for file_path in email_folder.rglob("*.msg"):
                msg_files.append(str(file_path))
            
            return sorted(msg_files)
        except Exception as e:
            logger.error(f"Error getting email files: {str(e)}")
            return []
    
    def get_emails_summary(self, page: int = 1, page_size: int = 20) -> Tuple[List[EmailSummary], int]:
        """
        Get a paginated list of email summaries with parsed content
        
        Args:
            page: Page number (1-based)
            page_size: Number of emails per page
            
        Returns:
            Tuple of (email_summaries, total_count)
        """
        msg_files = self.get_email_files()
        total_count = len(msg_files)
        
        # Calculate pagination
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_files = msg_files[start_idx:end_idx]
        
        email_summaries = []
        for file_path in paginated_files:
            try:
                # Parse email content to get actual metadata
                summary_data = self.msg_parser.get_msg_summary(file_path)
                
                if summary_data:
                    email_summary = EmailSummary(**summary_data)
                    email_summaries.append(email_summary)
                else:
                    # Fallback to file metadata if parsing fails
                    file_stats = os.stat(file_path)
                    filename = os.path.basename(file_path)
                    
                    fallback_data = {
                        'filename': filename,
                        'subject': f"[Parse Error] {filename}",
                        'sender': 'Unknown',
                        'date': datetime.fromtimestamp(file_stats.st_mtime),
                        'size': file_stats.st_size,
                        'has_attachments': False,
                        'attachment_count': 0,
                        'recipients': []
                    }
                    
                    email_summary = EmailSummary(**fallback_data)
                    email_summaries.append(email_summary)
                
            except Exception as e:
                logger.error(f"Error processing email summary for {file_path}: {str(e)}")
                continue
        
        return email_summaries, total_count
    
    def get_email_detail(self, filename: str) -> Optional[EmailDetail]:
        """
        Get detailed information for a specific email
        
        Args:
            filename: Name of the email file
            
        Returns:
            EmailDetail object or None if not found
        """
        try:
            file_path = self._find_email_file(filename)
            if not file_path:
                return None
            
            email_data = self.msg_parser.parse_msg_file(file_path)
            if email_data:
                return EmailDetail(**email_data)
            return None
        except Exception as e:
            logger.error(f"Error getting email detail for {filename}: {str(e)}")
            return None
    
    def search_emails(self, search_request: EmailSearchRequest) -> Tuple[List[EmailSummary], int]:
        """
        Search emails based on criteria
        
        Args:
            search_request: Search parameters
            
        Returns:
            Tuple of (matching email summaries, total count)
        """
        try:
            logger.info(f"[search_emails] Starting search with params: query={search_request.query}, "
                       f"sender={search_request.sender}, subject={search_request.subject}, "
                       f"date_from={search_request.date_from}, date_to={search_request.date_to}")
            
            msg_files = self.get_email_files()
            logger.info(f"[search_emails] Found {len(msg_files)} total email files")
            
            if not msg_files:
                logger.warning("[search_emails] No email files found")
                return [], 0
            
            # If no search criteria provided, return all emails with pagination
            if not any([search_request.query, search_request.sender, search_request.subject, 
                       search_request.date_from, search_request.date_to]):
                logger.info("[search_emails] No search criteria, returning paginated results")
                return self.get_emails_summary(search_request.page, search_request.page_size)
            
            matching_files = []
            processed_count = 0
            
            for file_path in msg_files:
                try:
                    processed_count += 1
                    if processed_count % 100 == 0:
                        logger.info(f"[search_emails] Processed {processed_count}/{len(msg_files)} files")
                    
                    if self._matches_search_criteria(file_path, search_request):
                        matching_files.append(file_path)
                except Exception as e:
                    logger.error(f"[search_emails] Error checking file {file_path}: {str(e)}")
                    continue
            
            total_count = len(matching_files)
            logger.info(f"[search_emails] Found {total_count} matching files")
            
            # Apply pagination
            start_idx = (search_request.page - 1) * search_request.page_size
            end_idx = start_idx + search_request.page_size
            paginated_files = matching_files[start_idx:end_idx]
            
            email_summaries = []
            for file_path in paginated_files:
                try:
                    # Parse email content to get actual metadata
                    summary_data = self.msg_parser.get_msg_summary(file_path)
                    
                    if summary_data:
                        email_summary = EmailSummary(**summary_data)
                        email_summaries.append(email_summary)
                    else:
                        # Fallback to file metadata if parsing fails
                        file_stats = os.stat(file_path)
                        filename = os.path.basename(file_path)
                        
                        fallback_data = {
                            'filename': filename,
                            'subject': f"[Parse Error] {filename}",
                            'sender': 'Unknown',
                            'date': datetime.fromtimestamp(file_stats.st_mtime),
                            'size': file_stats.st_size,
                            'has_attachments': False,
                            'attachment_count': 0,
                            'recipients': []
                        }
                        
                        email_summary = EmailSummary(**fallback_data)
                        email_summaries.append(email_summary)
                except Exception as e:
                    logger.error(f"Error processing email summary for {file_path}: {str(e)}")
                    continue
            
            logger.info(f"[search_emails] Returning {len(email_summaries)} email summaries")
            return email_summaries, total_count
        except Exception as e:
            logger.error(f"Error searching emails: {str(e)}", exc_info=True)
            return [], 0
    
    def _matches_search_criteria(self, file_path: str, search_request: EmailSearchRequest) -> bool:
        """Check if an email file matches the search criteria based on parsed email content"""
        try:
            # First check file-based criteria (faster)
            file_stats = os.stat(file_path)
            filename = os.path.basename(file_path)
            file_date = datetime.fromtimestamp(file_stats.st_mtime)
            
            # Quick date range check using file modification time
            if search_request.date_from and file_date < search_request.date_from:
                return False
            if search_request.date_to and file_date > search_request.date_to:
                return False
            
            # If only date filtering is needed and file passes, return True
            if not any([search_request.query, search_request.sender, search_request.subject]):
                return True
            
            # Parse email content only if content-based searching is needed
            email_data = self.msg_parser.get_msg_summary(file_path)
            
            if not email_data:
                # Fallback to filename-based searches if parsing fails
                filename_lower = filename.lower()
                if search_request.query and search_request.query.lower() not in filename_lower:
                    return False
                if search_request.subject and search_request.subject.lower() not in filename_lower:
                    return False
                if search_request.sender:
                    # Can't check sender from filename, so exclude
                    return False
                return True
            
            # Use parsed email data for more accurate searching
            email_date = email_data.get('date')
            subject = email_data.get('subject', '').lower()
            sender = email_data.get('sender', '').lower()
            recipients = email_data.get('recipients', [])
            recipients_text = ' '.join(recipients).lower() if recipients else ''
            
            # More precise date range check with actual email date
            if search_request.date_from and email_date and email_date < search_request.date_from:
                return False
            if search_request.date_to and email_date and email_date > search_request.date_to:
                return False
            
            # Check query in subject, sender, and recipients
            if search_request.query:
                query_lower = search_request.query.lower()
                if not any([
                    query_lower in subject,
                    query_lower in sender,
                    query_lower in recipients_text
                ]):
                    return False
            
            # Check specific subject search
            if search_request.subject and search_request.subject.lower() not in subject:
                return False
            
            # Check specific sender search
            if search_request.sender and search_request.sender.lower() not in sender:
                return False
            
            return True
        except Exception as e:
            logger.error(f"Error checking search criteria for {file_path}: {str(e)}")
            return False
    
    def _find_email_file(self, filename: str) -> Optional[str]:
        """Find the full path of an email file by filename"""
        try:
            email_folder = Path(self.email_folder)
            for file_path in email_folder.rglob("*.msg"):
                if file_path.name == filename:
                    return str(file_path)
            return None
        except Exception as e:
            logger.error(f"Error finding email file {filename}: {str(e)}")
            return None
    
    def get_emails_for_download(self, filenames: List[str], format_type: str, include_attachments: bool = False) -> List[Dict[str, Any]]:
        """
        Get email data for download in specified format
        
        Args:
            filenames: List of email filenames
            format_type: 'json' or 'text'
            include_attachments: Whether to include attachment data
            
        Returns:
            List of email data dictionaries
        """
        try:
            emails_data = []
            for filename in filenames:
                file_path = self._find_email_file(filename)
                if file_path:
                    email_data = self.msg_parser.parse_msg_file(file_path)
                    if email_data:
                        if not include_attachments:
                            # Remove attachment data but keep metadata
                            if 'attachments' in email_data:
                                for att in email_data['attachments']:
                                    att.pop('data', None)
                        emails_data.append(email_data)
            
            return emails_data
        except Exception as e:
            logger.error(f"Error preparing emails for download: {str(e)}")
            return []
