import os, sys
import json
import base64
from dataclasses import dataclass

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

credentials_file = os.path.expanduser('~/llt/credentials.json')
token_file = os.path.expanduser('~/llt/token.json')

SCOPES = ['https://www.googleapis.com/auth/gmail.send']

def load_config(path: str):
    with open(path, 'r') as config_file:
        return json.load(config_file)
    
def get_credentials():
    creds = None
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, scopes=SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_file, SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open(token_file, "w") as token:
            token.write(creds.to_json())
    return creds

@dataclass
class Email:
    to: str
    subject: str
    message: str

def create_message(email: Email):
    message = MIMEMultipart()
    message['to'], message['subject'] = email.to, email.subject
    message.attach(MIMEText(email.message))
    raw = base64.urlsafe_b64encode(message.as_bytes())
    raw = raw.decode()
    return {'raw': raw}

def send_email(messages: list, args: dict):
    config = load_config(os.path.expanduser('~/llt/test_email.json'))
    email = Email(to=config['to'], subject=config['subject'].format(subject="message from llt"), message=messages[-1]['content'])
    print(f"Sending email to {email.to} with subject {email.subject}:\n{email.message}")
    try:
        email_body = create_message(email)
        client = build('gmail', 'v1', credentials=get_credentials())
        response = client.users().messages().send(userId="me", body=messages[-1]['content']).execute()
        print(f'Message sent successfully: {response["id"]}')
        print(f'Other details:\n{response}')
    except HttpError as error:
        print(f'An error occurred: {error}')
    return email_body

if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(f"Usage: {sys.argv[0]}")
        sys.exit(1)
    send_email([{'content': f"{sys.argv[1]}"}], {})