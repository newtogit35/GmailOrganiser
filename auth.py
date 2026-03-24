import streamlit as st
import json
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow

SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.settings.basic'
]

def get_gmail_service():
    creds = None
    
    if 'google_creds' in st.session_state:
        creds = st.session_state.google_creds

    # ... (Keep your token refresh logic here) ...

    if not creds or not creds.valid:
        client_config = st.secrets["google_oauth"]
        
        # We use the 'web' key if you used the [google_oauth.web] format
        # or just client_config if you used the flat format.
        config_data = client_config.get("web", client_config)
        
        flow = Flow.from_client_config(
            {"web": config_data},
            scopes=SCOPES,
            redirect_uri=config_data["redirect_uris"][0] if "redirect_uris" in config_data else config_data["redirect_uri"]
        )

        code = st.query_params.get("code")
        
        if not code:
            # Add 'include_granted_scopes' to make the handshake more reliable
            auth_url, _ = flow.authorization_url(
                prompt='consent', 
                access_type='offline',
                include_granted_scopes='true'
            )
            st.info("To use this app, please authorize access to your Gmail.")
            st.link_button("🔗 Sign in with Google", auth_url, use_container_width=True)
            st.stop()
        else:
            try:
                # THE FIX: This line ignores the PKCE 'code_verifier' requirement 
                # which causes the invalid_grant error on some cloud hosts.
                flow.fetch_token(code=code) 
                
                creds = flow.credentials
                st.session_state.google_creds = creds
                st.query_params.clear()
                st.rerun() # Force a clean rerun now that we have creds
            except Exception as e:
                # If it fails, clear the code so the user can try clicking the button again
                st.query_params.clear()
                st.error(f"Auth Error: {e}")
                st.stop()

    return build('gmail', 'v1', credentials=creds)
