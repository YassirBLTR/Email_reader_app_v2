import extract_msg
import os
import email
import email.utils
import email.header
import quopri
import html
import base64
import mimetypes
import re
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class MSGParser:
    """Utility class for parsing .msg email files"""
    
    @staticmethod
    def parse_msg_file(file_path: str) -> Optional[Dict[str, Any]]:
        """
        Parse a .msg file and extract email information
        Supports both Outlook .msg files and RFC 2822 email files
        
        Args:
            file_path: Path to the .msg file
            
        Returns:
            Dictionary containing parsed email data or None if parsing fails
        """
        # First try to parse as Outlook .msg file
        try:
            with extract_msg.Message(file_path) as msg:
                return MSGParser._extract_outlook_data(msg, file_path)
        except Exception as e:
            logger.debug(f"Failed to parse as Outlook MSG file {file_path}: {str(e)}")
            # Try to parse as RFC 2822 email file
            return MSGParser._parse_rfc2822_file(file_path)
    
    @staticmethod
    def get_msg_summary(file_path: str) -> Optional[Dict[str, Any]]:
        """
        Get a summary of the .msg file without parsing the full content
        Supports both Outlook .msg files and RFC 2822 email files
        
        Args:
            file_path: Path to the .msg file
            
        Returns:
            Dictionary containing email summary or None if parsing fails
        """
        # First try to parse as Outlook .msg file
        try:
            with extract_msg.Message(file_path) as msg:
                return MSGParser._extract_outlook_summary(msg, file_path)
        except Exception as e:
            logger.debug(f"Failed to parse as Outlook MSG file {file_path}: {str(e)}")
            # Try to parse as RFC 2822 email file for summary
            return MSGParser._get_rfc2822_summary(file_path)
    
    @staticmethod
    def _extract_outlook_data(msg, file_path: str) -> Dict[str, Any]:
        """Extract full data from Outlook .msg file"""
        # Extract recipients
        recipients = MSGParser._parse_recipients(msg.to, ';') if msg.to else []
        cc = MSGParser._parse_recipients(msg.cc, ';') if msg.cc else []
        bcc = MSGParser._parse_recipients(msg.bcc, ';') if msg.bcc else []
        
        # Extract attachments information and prepare CID map for inline images
        attachments = []
        cid_map = {}
        if msg.attachments:
            for attachment in msg.attachments:
                att_filename = attachment.longFilename or attachment.shortFilename
                att_bytes = attachment.data if hasattr(attachment, 'data') else None
                att_type = getattr(attachment, 'mimetype', None)
                if not att_type and att_filename:
                    guessed, _ = mimetypes.guess_type(att_filename)
                    att_type = guessed or 'application/octet-stream'
                # Build attachment info for API consumers
                att_info = {
                    'filename': att_filename,
                    'size': len(att_bytes) if att_bytes else 0,
                    'content_type': att_type or 'application/octet-stream'
                }
                attachments.append(att_info)
                # Collect CID mapping if possible
                cid = getattr(attachment, 'contentId', None) or getattr(attachment, 'cid', None)
                if cid and att_bytes:
                    cid_clean = cid.strip('<>')
                    try:
                        b64 = base64.b64encode(att_bytes).decode('ascii')
                        cid_map[cid_clean] = f"data:{att_type or 'application/octet-stream'};base64,{b64}"
                    except Exception:
                        pass

        # Robust sender extraction: sender, senderEmail, or From header
        headers_dict = msg.header if hasattr(msg, 'header') else {}
        sender_candidates = [
            getattr(msg, 'sender', None),
            getattr(msg, 'senderEmail', None),
            (headers_dict.get('From') if isinstance(headers_dict, dict) else None),
        ]
        sender_raw = next((s for s in sender_candidates if s), 'Unknown Sender')
        sender_decoded = MSGParser._decode_mime_header(sender_raw)

        # Normalize date to datetime when possible
        date_value = getattr(msg, 'date', None)
        if isinstance(date_value, str):
            date_value = MSGParser._parse_email_date(date_value)

        # Determine and clean HTML body
        html_body_candidates = [
            getattr(msg, 'htmlBody', None),
            getattr(msg, 'bodyHTML', None),
            getattr(msg, 'bodyHtml', None),
        ]
        html_body = next((h for h in html_body_candidates if isinstance(h, str) and h.strip()), '')
        html_body = MSGParser._clean_html_content(html_body)

        # If HTML body missing but plain body contains HTML-like content, promote it
        if not html_body and isinstance(msg.body, str):
            body_str = (msg.body or '').strip()
            if body_str.startswith('<') or '<html' in body_str.lower():
                html_body = MSGParser._clean_html_content(body_str)

        # Inline cid: images for Outlook messages
        if html_body and cid_map:
            html_body = MSGParser._inline_cid_sources(html_body, cid_map)

        return {
            'filename': os.path.basename(file_path),
            'subject': MSGParser._decode_mime_header(msg.subject or 'No Subject'),
            'sender': sender_decoded,
            'date': date_value,
            'body': msg.body,
            'html_body': html_body,
            'message_id': msg.messageId,
            'size': os.path.getsize(file_path),
            'recipients': recipients,
            'cc': cc,
            'bcc': bcc,
            'attachments': attachments,
            'headers': msg.header if hasattr(msg, 'header') else {}
        }
    
    @staticmethod
    def _extract_outlook_summary(msg, file_path: str) -> Dict[str, Any]:
        """Extract summary data from Outlook .msg file"""
        recipients = MSGParser._parse_recipients(msg.to, ';') if msg.to else []

        # Robust sender extraction for summary
        headers_dict = msg.header if hasattr(msg, 'header') else {}
        sender_candidates = [
            getattr(msg, 'sender', None),
            getattr(msg, 'senderEmail', None),
            (headers_dict.get('From') if isinstance(headers_dict, dict) else None),
        ]
        sender_raw = next((s for s in sender_candidates if s), 'Unknown Sender')
        sender_decoded = MSGParser._decode_mime_header(sender_raw)

        # Normalize date to datetime when possible
        date_value = getattr(msg, 'date', None)
        if isinstance(date_value, str):
            date_value = MSGParser._parse_email_date(date_value)

        return {
            'filename': os.path.basename(file_path),
            'subject': MSGParser._decode_mime_header(msg.subject or 'No Subject'),
            'sender': sender_decoded,
            'date': date_value,
            'size': os.path.getsize(file_path),
            'has_attachments': bool(msg.attachments),
            'attachment_count': len(msg.attachments) if msg.attachments else 0,
            'recipients': recipients
        }
    
    @staticmethod
    def _parse_rfc2822_file(file_path: str) -> Optional[Dict[str, Any]]:
        """
        Parse an RFC 2822 email file (raw email format)
        
        Args:
            file_path: Path to the email file
            
        Returns:
            Dictionary containing parsed email data or None if parsing fails
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                msg = email.message_from_file(f)
            
            # Parse date
            parsed_date = MSGParser._parse_email_date(msg.get('Date'))
            
            # Extract body with proper decoding
            body, html_body = MSGParser._extract_email_bodies(msg)
            
            # Inline CID images if present
            try:
                cid_map = MSGParser._build_cid_map_rfc(msg)
                if html_body and cid_map:
                    html_body = MSGParser._inline_cid_sources(html_body, cid_map)
            except Exception:
                pass
            
            # Parse recipients
            recipients = MSGParser._parse_recipients(msg.get('To', ''), ',')
            cc = MSGParser._parse_recipients(msg.get('Cc', ''), ',')
            bcc = MSGParser._parse_recipients(msg.get('Bcc', ''), ',')
            
            # Extract attachments
            attachments = MSGParser._extract_rfc2822_attachments(msg)
            
            return {
                'filename': os.path.basename(file_path),
                'subject': MSGParser._decode_mime_header(msg.get('Subject', 'No Subject')),
                'sender': MSGParser._decode_mime_header(msg.get('From', 'Unknown Sender')),
                'date': parsed_date,
                'body': body,
                'html_body': html_body,
                'message_id': msg.get('Message-ID'),
                'size': os.path.getsize(file_path),
                'recipients': recipients,
                'cc': cc,
                'bcc': bcc,
                'attachments': attachments,
                'headers': dict(msg.items())
            }
            
        except Exception as e:
            logger.error(f"Error parsing RFC 2822 email file {file_path}: {str(e)}")
            return None
    
    @staticmethod
    def _get_rfc2822_summary(file_path: str) -> Optional[Dict[str, Any]]:
        """
        Get a summary of an RFC 2822 email file
        
        Args:
            file_path: Path to the email file
            
        Returns:
            Dictionary containing email summary or None if parsing fails
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                msg = email.message_from_file(f)
            
            # Parse date
            parsed_date = MSGParser._parse_email_date(msg.get('Date'))
            
            # Parse recipients
            recipients = MSGParser._parse_recipients(msg.get('To', ''), ',')
            
            # Check for attachments
            has_attachments, attachment_count = MSGParser._count_rfc2822_attachments(msg)
            
            return {
                'filename': os.path.basename(file_path),
                'subject': MSGParser._decode_mime_header(msg.get('Subject', 'No Subject')),
                'sender': MSGParser._decode_mime_header(msg.get('From', 'Unknown Sender')),
                'date': parsed_date,
                'size': os.path.getsize(file_path),
                'has_attachments': has_attachments,
                'attachment_count': attachment_count,
                'recipients': recipients
            }
            
        except Exception as e:
            logger.error(f"Error getting RFC 2822 email summary for {file_path}: {str(e)}")
            return None
    
    @staticmethod
    def _parse_recipients(recipients_str: str, delimiter: str) -> List[str]:
        """Parse recipients string into list"""
        if not recipients_str:
            return []
        return [recipient.strip() for recipient in recipients_str.split(delimiter) if recipient.strip()]
    
    @staticmethod
    def _parse_email_date(date_str: str) -> Optional[datetime]:
        """Parse email date string"""
        if not date_str:
            return None
        try:
            return email.utils.parsedate_to_datetime(date_str)
        except Exception:
            return None
    
    @staticmethod
    def _extract_email_bodies(msg) -> tuple[str, str]:
        """Extract plain text and HTML bodies from email message"""
        body = ""
        html_body = ""
        
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        body = MSGParser._decode_content(payload, part.get('Content-Transfer-Encoding', ''))
                elif part.get_content_type() == "text/html":
                    payload = part.get_payload(decode=True)
                    if payload:
                        html_body = MSGParser._decode_content(payload, part.get('Content-Transfer-Encoding', ''))
                        html_body = MSGParser._clean_html_content(html_body)
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                content = MSGParser._decode_content(payload, msg.get('Content-Transfer-Encoding', ''))
                if msg.get_content_type() == "text/plain":
                    body = content
                elif msg.get_content_type() == "text/html":
                    html_body = MSGParser._clean_html_content(content)
                else:
                    # If no specific content type, try to detect HTML
                    if content.strip().startswith('<'):
                        html_body = MSGParser._clean_html_content(content)
                    else:
                        body = content

        # Final fallback: if HTML missing but body looks like HTML, promote it
        if not html_body and body and (body.strip().startswith('<') or '<html' in body.lower()):
            html_body = MSGParser._clean_html_content(body)

        return body, html_body

    @staticmethod
    def _build_cid_map_rfc(msg) -> Dict[str, str]:
        """Build CID -> data: URI map from RFC 2822 message parts"""
        cid_map: Dict[str, str] = {}
        try:
            if msg.is_multipart():
                for part in msg.walk():
                    cid = part.get('Content-ID')
                    if not cid:
                        continue
                    cid_clean = cid.strip().strip('<>')
                    payload = part.get_payload(decode=True)
                    if not payload:
                        continue
                    ctype = part.get_content_type() or 'application/octet-stream'
                    try:
                        b64 = base64.b64encode(payload).decode('ascii')
                        cid_map[cid_clean] = f"data:{ctype};base64,{b64}"
                    except Exception:
                        continue
        except Exception:
            pass
        return cid_map

    @staticmethod
    def _inline_cid_sources(html_content: str, cid_map: Dict[str, str]) -> str:
        """Replace cid: URLs in src/href/url() with data URIs from cid_map"""
        if not html_content or not cid_map:
            return html_content

        def replace_attr(match: re.Match) -> str:
            attr = match.group(1)
            cid = match.group(2)
            cid_clean = cid.strip().strip('<>')
            data_uri = cid_map.get(cid_clean)
            if data_uri:
                return f'{attr}="{data_uri}"'
            return match.group(0)

        def replace_css(match: re.Match) -> str:
            cid = match.group(1)
            cid_clean = cid.strip().strip('<>')
            data_uri = cid_map.get(cid_clean)
            if data_uri:
                return f"url('{data_uri}')"
            return match.group(0)

        # Replace src/href="cid:..."
        html_content = re.sub(r'(?i)\b(src|href)\s*=\s*["\']cid:([^"\']+)["\']', replace_attr, html_content)
        # Replace url('cid:...') in inline styles
        html_content = re.sub(r"(?i)url\(['\"]cid:([^'\"]+)['\"]\)", replace_css, html_content)
        return html_content
    
    @staticmethod
    def _extract_rfc2822_attachments(msg) -> List[Dict[str, Any]]:
        """Extract attachments from RFC 2822 message"""
        attachments = []
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_disposition() == 'attachment':
                    filename = part.get_filename()
                    if filename:
                        attachments.append({
                            'filename': filename,
                            'size': len(part.get_payload(decode=True) or b''),
                            'content_type': part.get_content_type()
                        })
        return attachments
    
    @staticmethod
    def _count_rfc2822_attachments(msg) -> tuple[bool, int]:
        """Count attachments in RFC 2822 message"""
        attachment_count = 0
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_disposition() == 'attachment':
                    attachment_count += 1
        return attachment_count > 0, attachment_count
    
    @staticmethod
    def _decode_content(payload: bytes, encoding: str) -> str:
        """
        Decode email content based on transfer encoding
        
        Args:
            payload: Raw content bytes
            encoding: Content transfer encoding
            
        Returns:
            Decoded string content
        """
        try:
            # Handle quoted-printable encoding
            if encoding and encoding.lower() == 'quoted-printable':
                decoded_bytes = quopri.decodestring(payload)
                content = decoded_bytes.decode('utf-8', errors='ignore')
            else:
                # Try to decode as UTF-8 first, then fallback
                try:
                    content = payload.decode('utf-8')
                except UnicodeDecodeError:
                    try:
                        content = payload.decode('iso-8859-1')
                    except UnicodeDecodeError:
                        content = payload.decode('utf-8', errors='ignore')
            
            # Clean up common encoding issues
            content = MSGParser._clean_encoded_content(content)
            
            return content
            
        except Exception as e:
            logger.error(f"Error decoding content: {str(e)}")
            return payload.decode('utf-8', errors='ignore')
    
    @staticmethod
    def _clean_encoded_content(content: str) -> str:
        """Clean up common encoding issues in content"""
        content = content.replace('=\n', '')  # Remove soft line breaks
        content = content.replace('=3D', '=')  # Fix quoted-printable equals
        content = content.replace('=20', ' ')  # Fix quoted-printable spaces
        content = content.replace('=0D=0A', '\n')  # Fix line breaks
        return content
    
    @staticmethod
    def _decode_mime_header(header_value: str) -> str:
        """Decode MIME-encoded header values (RFC 2047)"""
        if not header_value:
            return ""
        
        try:
            # Decode MIME header encoding
            decoded_parts = email.header.decode_header(header_value)
            decoded_string = ""
            
            for part, encoding in decoded_parts:
                if isinstance(part, bytes):
                    if encoding:
                        decoded_string += part.decode(encoding, errors='ignore')
                    else:
                        # Try common encodings if none specified
                        for enc in ['utf-8', 'iso-8859-1', 'windows-1252']:
                            try:
                                decoded_string += part.decode(enc)
                                break
                            except UnicodeDecodeError:
                                continue
                        else:
                            decoded_string += part.decode('utf-8', errors='ignore')
                else:
                    decoded_string += str(part)
            
            return decoded_string.strip()
        except Exception as e:
            logger.warning(f"Error decoding MIME header '{header_value}': {e}")
            return header_value

    @staticmethod
    def _clean_html_content(html_content: str) -> str:
        """Clean and decode HTML content"""
        if not html_content:
            return ""
        
        try:
            # Decode quoted-printable if present
            if '=' in html_content and any(c in html_content for c in ['=20', '=3D', '=0D', '=0A']):
                html_content = quopri.decodestring(html_content).decode('utf-8', errors='ignore')
            
            # Clean up common HTML encoding issues
            html_content = html_content.replace('&shy;', '')  # Remove soft hyphens
            html_content = MSGParser._clean_encoded_content(html_content)
            
            return html_content
        except Exception as e:
            logger.warning(f"Error cleaning HTML content: {e}")
            return html_content
    
    @staticmethod
    def extract_attachment(file_path: str, attachment_name: str) -> Optional[bytes]:
        """
        Extract a specific attachment from a .msg file
        
        Args:
            file_path: Path to the .msg file
            attachment_name: Name of the attachment to extract
            
        Returns:
            Attachment data as bytes or None if not found
        """
        try:
            with extract_msg.Message(file_path) as msg:
                if msg.attachments:
                    for attachment in msg.attachments:
                        att_filename = attachment.longFilename or attachment.shortFilename
                        if att_filename == attachment_name:
                            return attachment.data
                return None
                
        except Exception as e:
            logger.error(f"Error extracting attachment {attachment_name} from {file_path}: {str(e)}")
            return None
