import json
import tempfile
import zipfile
from typing import List, Dict, Any
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class FileService:
    """Service class for handling file operations and downloads"""
    
    @staticmethod
    def create_json_download(emails_data: List[Dict[str, Any]], filename: str = "emails.json") -> str:
        """
        Create a JSON file for download
        
        Args:
            emails_data: List of email data dictionaries
            filename: Name for the output file
            
        Returns:
            Path to the created temporary file
        """
        try:
            # Create temporary file
            temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
            
            # Convert datetime objects to strings for JSON serialization
            serializable_data = FileService._make_json_serializable(emails_data)
            
            # Write JSON data
            json.dump({
                'emails': serializable_data,
                'total_count': len(serializable_data),
                'export_timestamp': FileService._get_current_timestamp()
            }, temp_file, indent=2, ensure_ascii=False)
            
            temp_file.close()
            return temp_file.name
        except Exception as e:
            logger.error(f"Error creating JSON download: {str(e)}")
            raise
    
    @staticmethod
    def create_text_download(emails_data: List[Dict[str, Any]], filename: str = "emails.txt") -> str:
        """
        Create a text file for download
        
        Args:
            emails_data: List of email data dictionaries
            filename: Name for the output file
            
        Returns:
            Path to the created temporary file
        """
        try:
            # Create temporary file
            temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8')
            
            # Write header
            temp_file.write("EMAIL EXPORT\n")
            temp_file.write("=" * 50 + "\n")
            temp_file.write(f"Export Date: {FileService._get_current_timestamp()}\n")
            temp_file.write(f"Total Emails: {len(emails_data)}\n")
            temp_file.write("=" * 50 + "\n\n")
            
            # Write each email
            for i, email in enumerate(emails_data, 1):
                temp_file.write(f"EMAIL #{i}\n")
                temp_file.write("-" * 30 + "\n")
                temp_file.write(f"Filename: {email.get('filename', 'N/A')}\n")
                temp_file.write(f"Subject: {email.get('subject', 'N/A')}\n")
                temp_file.write(f"From: {email.get('sender', 'N/A')}\n")
                temp_file.write(f"To: {', '.join(email.get('recipients', []))}\n")
                temp_file.write(f"Date: {email.get('date', 'N/A')}\n")
                
                if email.get('cc'):
                    temp_file.write(f"CC: {', '.join(email.get('cc', []))}\n")
                
                if email.get('bcc'):
                    temp_file.write(f"BCC: {', '.join(email.get('bcc', []))}\n")
                
                temp_file.write(f"Size: {email.get('size', 0)} bytes\n")
                
                if email.get('attachments'):
                    temp_file.write(f"Attachments: {len(email.get('attachments', []))}\n")
                    for att in email.get('attachments', []):
                        temp_file.write(f"  - {att.get('filename', 'Unknown')} ({att.get('size', 0)} bytes)\n")
                
                temp_file.write("\nBody:\n")
                body = email.get('body', '')
                if body:
                    temp_file.write(body)
                else:
                    temp_file.write("No text body available")
                
                temp_file.write("\n\n" + "=" * 50 + "\n\n")
            
            temp_file.close()
            return temp_file.name
        except Exception as e:
            logger.error(f"Error creating text download: {str(e)}")
            raise
    
    @staticmethod
    def create_zip_download(emails_data: List[Dict[str, Any]], format_type: str = "json") -> str:
        """
        Create a ZIP file containing multiple email files
        
        Args:
            emails_data: List of email data dictionaries
            format_type: 'json' or 'text'
            
        Returns:
            Path to the created temporary ZIP file
        """
        try:
            # Create temporary ZIP file
            temp_zip = tempfile.NamedTemporaryFile(suffix='.zip', delete=False)
            temp_zip.close()
            
            with zipfile.ZipFile(temp_zip.name, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for email in emails_data:
                    filename = email.get('filename', 'unknown.msg')
                    base_name = Path(filename).stem
                    
                    if format_type == "json":
                        # Create individual JSON file for each email
                        email_json = json.dumps(
                            FileService._make_json_serializable([email]),
                            indent=2,
                            ensure_ascii=False
                        )
                        zipf.writestr(f"{base_name}.json", email_json)
                    else:
                        # Create individual text file for each email
                        email_text = FileService._format_email_as_text(email)
                        zipf.writestr(f"{base_name}.txt", email_text)
            
            return temp_zip.name
        except Exception as e:
            logger.error(f"Error creating ZIP download: {str(e)}")
            raise

    @staticmethod
    def create_original_zip(file_paths: List[str]) -> str:
        """Create a ZIP file containing the original .msg files without parsing.

        Args:
            file_paths: Full paths to the original .msg files to include

        Returns:
            Path to the created temporary ZIP file
        """
        try:
            # Create temporary ZIP file
            temp_zip = tempfile.NamedTemporaryFile(suffix='.zip', delete=False)
            temp_zip.close()

            with zipfile.ZipFile(temp_zip.name, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for path in file_paths:
                    p = Path(path)
                    if p.exists() and p.is_file():
                        # Store each file by its original filename
                        zipf.write(str(p), arcname=p.name)
            return temp_zip.name
        except Exception as e:
            logger.error(f"Error creating original files ZIP: {str(e)}")
            raise
    
    @staticmethod
    def _make_json_serializable(data: Any) -> Any:
        """Convert data to JSON serializable format"""
        if isinstance(data, dict):
            return {key: FileService._make_json_serializable(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [FileService._make_json_serializable(item) for item in data]
        elif hasattr(data, 'isoformat'):  # datetime objects
            return data.isoformat()
        else:
            return data
    
    @staticmethod
    def _format_email_as_text(email: Dict[str, Any]) -> str:
        """Format a single email as text"""
        text_parts = []
        text_parts.append(f"Filename: {email.get('filename', 'N/A')}")
        text_parts.append(f"Subject: {email.get('subject', 'N/A')}")
        text_parts.append(f"From: {email.get('sender', 'N/A')}")
        text_parts.append(f"To: {', '.join(email.get('recipients', []))}")
        text_parts.append(f"Date: {email.get('date', 'N/A')}")
        
        if email.get('cc'):
            text_parts.append(f"CC: {', '.join(email.get('cc', []))}")
        
        if email.get('bcc'):
            text_parts.append(f"BCC: {', '.join(email.get('bcc', []))}")
        
        text_parts.append(f"Size: {email.get('size', 0)} bytes")
        
        if email.get('attachments'):
            text_parts.append(f"Attachments: {len(email.get('attachments', []))}")
            for att in email.get('attachments', []):
                text_parts.append(f"  - {att.get('filename', 'Unknown')} ({att.get('size', 0)} bytes)")
        
        text_parts.append("\nBody:")
        body = email.get('body', '')
        if body:
            text_parts.append(body)
        else:
            text_parts.append("No text body available")
        
        return "\n".join(text_parts)
    
    @staticmethod
    def _get_current_timestamp() -> str:
        """Get current timestamp as string"""
        from datetime import datetime
        return datetime.now().isoformat()
