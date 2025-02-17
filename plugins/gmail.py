import os, sys
import json
import base64
from dataclasses import dataclass
from typing import List, Dict
from typing import Optional
import traceback
from utils import Colors, content_input, get_valid_index
from logger import llt_logger

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from plugins import llt

# Gmail API configuration
SCOPES = ['https://www.googleapis.com/auth/gmail.send']
DEFAULT_CONFIG_PATH = os.path.expanduser('~/.llt/gmail_config.json')
DEFAULT_CREDS_PATH = os.path.expanduser('~/.llt/gmail_credentials.json')
DEFAULT_TOKEN_PATH = os.path.expanduser('~/.llt/gmail_token.json')

@dataclass
class Email:
    to: str
    subject: str
    message: str
    from_email: Optional[str] = None
    cc: Optional[str] = None
    bcc: Optional[str] = None

def load_config(config_path: str = DEFAULT_CONFIG_PATH) -> Dict:
    """Load Gmail configuration from file."""
    try:
        with open(config_path, 'r') as config_file:
            config = json.load(config_file)
            llt_logger.log_info("Gmail config loaded", {"path": config_path})
            return config
    except (FileNotFoundError, json.JSONDecodeError) as e:
        llt_logger.log_error(f"Error loading Gmail config: {str(e)}")
        return {}

def get_credentials(
    credentials_path: str = DEFAULT_CREDS_PATH,
    token_path: str = DEFAULT_TOKEN_PATH
) -> Optional[Credentials]:
    """Get or refresh Gmail API credentials."""
    try:
        creds = None
        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
            
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(credentials_path):
                    llt_logger.log_error("Gmail credentials file not found", {"path": credentials_path})
                    return None
                    
                flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)
                
            # Save the credentials for future use
            os.makedirs(os.path.dirname(token_path), exist_ok=True)
            with open(token_path, "w") as token:
                token.write(creds.to_json())
                
        return creds
        
    except Exception as e:
        llt_logger.log_error("Error getting Gmail credentials", {
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        return None

def create_message(email: Email) -> Dict:
    """Create Gmail API compatible message."""
    message = MIMEMultipart()
    message['to'] = email.to
    message['subject'] = email.subject
    
    if email.from_email:
        message['from'] = email.from_email
    if email.cc:
        message['cc'] = email.cc
    if email.bcc:
        message['bcc'] = email.bcc
        
    message.attach(MIMEText(email.message, 'plain'))
    
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    return {'raw': raw}

@llt
def send_email(messages: List[Dict], args: Dict, index: int = -1) -> List[Dict]:
    """
    Description: Send email using Gmail API
    Type: string
    Default: None
    flag: email
    short: mail
    """
    if not args.get('non_interactive'):
        index = get_valid_index(messages, "send email content from", index)
    
    # Load config and get credentials
    config = load_config()
    creds = get_credentials()
    
    if not creds:
        error_msg = "Failed to get Gmail credentials. Please check your configuration."
        Colors.print_colored(error_msg, Colors.RED)
        messages.append({"role": "system", "content": error_msg})
        return messages
    
    try:
        # Get email details
        if args.get('non_interactive'):
            to_email = args.get('to') or config.get('default_to')
            subject = args.get('subject') or config.get('default_subject', 'Message from LLT')
        else:
            to_email = content_input("To email address", default=config.get('default_to', ''))
            subject = content_input("Subject", default=config.get('default_subject', 'Message from LLT'))
        
        if not to_email:
            error_msg = "No recipient email address provided"
            Colors.print_colored(error_msg, Colors.RED)
            messages.append({"role": "system", "content": error_msg})
            return messages
            
        # Create email object
        email = Email(
            to=to_email,
            subject=subject,
            message=messages[index]['content'],
            from_email=config.get('from_email'),
            cc=args.get('cc') or config.get('default_cc'),
            bcc=args.get('bcc') or config.get('default_bcc')
        )
        
        # Send email
        email_body = create_message(email)
        service = build('gmail', 'v1', credentials=creds)
        response = service.users().messages().send(userId="me", body=email_body).execute()
        
        success_msg = (
            f"Email sent successfully!\n"
            f"To: {email.to}\n"
            f"Subject: {email.subject}\n"
            f"Message ID: {response['id']}"
        )
        Colors.print_colored(success_msg, Colors.GREEN)
        
        # Log success
        llt_logger.log_info("Email sent successfully", {
            "to": email.to,
            "subject": email.subject,
            "message_id": response["id"]
        })
        
        messages.append({
            "role": "system",
            "content": success_msg
        })
        
    except HttpError as e:
        error_msg = f"Gmail API error: {str(e)}"
        Colors.print_colored(error_msg, Colors.RED)
        llt_logger.log_error("Gmail API error", {
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        messages.append({"role": "system", "content": error_msg})
        
    except Exception as e:
        error_msg = f"Unexpected error sending email: {str(e)}"
        Colors.print_colored(error_msg, Colors.RED)
        llt_logger.log_error("Unexpected email error", {
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        messages.append({"role": "system", "content": error_msg})
    
    return messages

if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(f"Usage: {sys.argv[0]}")
        sys.exit(1)
    send_email([{'content': f"{sys.argv[1]}"}], {})