import streamlit as st
import json
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

# Keep your SCOPES as they were
SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.settings.basic'
]

def get_gmail_service():
    creds = None
    
    # 1. Check if the "token" (your session) is in Streamlit Secrets
    if "gmail_token" in st.secrets:
        token_info = json.loads(st.secrets["gmail_token"])
        creds = Credentials.from_authorized_user_info(token_info, SCOPES)
    
    # 2. If token is expired, try to refresh it
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    
    # 3. If no valid creds exist, we can't run 'flow.run_local_server' on the web.
    # We must raise an error or handle it.
    if not creds or not creds.valid:
        st.error("Authentication credentials not found. Please set up gmail_token in Streamlit Secrets.")
        st.stop()
        
    return build('gmail', 'v1', credentials=creds)
