# utils/file_parser.py
import PyPDF2
import json
import os
from email import message_from_string
from email.parser import BytesParser
from email.policy import default as default_policy

def get_file_format(filepath: str, content_bytes: bytes = None) -> str:
    _, ext = os.path.splitext(filepath)
    ext = ext.lower()
    if ext == ".pdf":
        return "PDF"
    elif ext == ".json":
        return "JSON"
    elif ext in [".txt", ".eml", ".msg"] or content_bytes: # if content_bytes, could be raw email
        # Further check for .eml if needed
        if ext == ".eml" or (content_bytes and b"Content-Type:" in content_bytes and b"Subject:" in content_bytes):
            return "EMAIL" # More specific
        return "TEXT" # Generic text, could be email body
    return "UNKNOWN"

def extract_text_from_pdf(filepath: str) -> str:
    text = ""
    try:
        with open(filepath, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page_num in range(len(reader.pages)):
                page = reader.pages[page_num]
                text += page.extract_text() or "" # Add or "" to handle None
    except Exception as e:
        print(f"Error reading PDF {filepath}: {e}")
    return text

def parse_json_file(filepath: str) -> dict:
    try:
        with open(filepath, "r", encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error reading JSON {filepath}: {e}")
        return None

def extract_text_from_email_file(filepath: str) -> tuple[str, str, str, str]:
    """Parses an .eml file and extracts sender, subject, and body."""
    try:
        with open(filepath, 'rb') as fp:
            msg = BytesParser(policy=default_policy).parse(fp)
        
        sender = msg.get('From', 'Unknown Sender')
        subject = msg.get('Subject', 'No Subject')
        recipients = msg.get('To', '') # Could be multiple
        
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                cdispo = str(part.get('Content-Disposition'))
                if ctype == 'text/plain' and 'attachment' not in cdispo:
                    body = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', errors='replace')
                    break
        else:
            body = msg.get_payload(decode=True).decode(msg.get_content_charset() or 'utf-8', errors='replace')
        
        return sender, subject, recipients, body.strip()
    except Exception as e:
        print(f"Error parsing email file {filepath}: {e}")
        return "Error", "Error", "Error", f"Could not parse email content: {e}"


def extract_text_from_raw_email_content(email_content: str) -> tuple[str, str, str, str]:
    """Parses raw email text content."""
    try:
        msg = message_from_string(email_content)
        sender = msg.get('From', 'Unknown Sender (from text)')
        subject = msg.get('Subject', 'No Subject (from text)')
        recipients = msg.get('To', '')

        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == 'text/plain':
                    payload = part.get_payload(decode=True)
                    if payload:
                        try:
                            body = payload.decode(part.get_content_charset() or 'utf-8', errors='replace')
                            break
                        except Exception:
                            pass # Try next part
            if not body and msg.get_payload(): # Fallback for non-multipart or simple text
                 if isinstance(msg.get_payload(), str):
                    body = msg.get_payload()
                 else: # if it's a list of parts
                    for p in msg.get_payload():
                        if isinstance(p, str): # Should not happen with proper parsing
                            body += p
                        elif p.get_content_type() == 'text/plain':
                             payload = p.get_payload(decode=True)
                             if payload:
                                 body = payload.decode(p.get_content_charset() or 'utf-8', errors='replace')
                                 break


        else: # Not multipart
            payload = msg.get_payload(decode=True)
            if payload:
                body = payload.decode(msg.get_content_charset() or 'utf-8', errors='replace')
            elif isinstance(msg.get_payload(), str): # if it's just plain text without headers
                body = msg.get_payload()

        # If body is still empty, it might be that the whole input was the body
        if not body.strip() and not sender and not subject:
            body = email_content # Assume the whole string is the body if parsing fails to find parts

        return sender, subject, recipients, body.strip()
    except Exception as e:
        print(f"Error parsing raw email content: {e}")
        return "Error", "Error", "Error", f"Could not parse raw email content: {e}"
    