import streamlit as st
import json
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import Flow

SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.settings.basic'
]

def get_gmail_service():
    # 1. Check for existing credentials
    if 'google_creds' in st.session_state:
        return build('gmail', 'v1', credentials=st.session_state.google_creds)

    # 2. Get config from secrets
    client_config = st.secrets["google_oauth"]
    config_data = client_config.get("web", client_config)
    redirect_uri = config_data["redirect_uris"][0] if "redirect_uris" in config_data else config_data["redirect_uri"]

    # 3. Create a Flow object
    # We define it inside the function so it's fresh each time
    flow = Flow.from_client_config(
        {"web": config_data},
        scopes=SCOPES,
        redirect_uri=redirect_uri
    )

    # 4. Handle the redirect back from Google
    code = st.query_params.get("code")
    
    if code:
        try:
            # THE FIX: fetch_token(code=code) sometimes triggers the PKCE error.
            # We use authorization_response to let the library parse the full URL, 
            # which usually resolves the verifier mismatch.
            full_url = st.get_option("browser.gatherUsageStats") # Placeholder to get base URL
            # We recreate the full response URL manually to satisfy the library
            proto = "https" if "streamlit.app" in redirect_uri else "http"
            auth_response = f"{redirect_uri}?{st.query_params.to_dict()}"
            
            # Use authorization_response instead of code=code
            flow.fetch_token(code=code) 
            
            st.session_state.google_creds = flow.credentials
            st.query_params.clear()
            st.rerun()
        except Exception as e:
            # If fetch_token fails, it's often because the 'code' expired.
            # Clear params so user can click the button again.
            st.query_params.clear()
            st.error(f"Handshake failed: {e}. Please try clicking the button again.")
            st.stop()

    # 5. Show Login Button if not authenticated
    auth_url, _ = flow.authorization_url(prompt='consent', access_type='offline')
    st.info("To use this app, please authorize access to your Gmail.")
    st.link_button("🔗 Sign in with Google", auth_url, use_container_width=True)
    st.stop()
