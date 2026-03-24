import streamlit as st
import requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# Same scopes as your Google Console screenshot
SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.settings.basic'
]

def get_gmail_service():
    # 1. If already logged in, just return the service
    if 'google_creds' in st.session_state:
        return build('gmail', 'v1', credentials=st.session_state.google_creds)

    # 2. Extract configuration from secrets
    client_config = st.secrets["google_oauth"]["web"]
    client_id = client_config["client_id"]
    client_secret = client_config["client_secret"]
    redirect_uri = client_config["redirect_uris"][0]

    # 3. Check if Google sent an authorization code in the URL
    code = st.query_params.get("code")

    if not code:
        # STEP A: Create the Login URL manually
        auth_url = (
            f"https://accounts.google.com/o/oauth2/v2/auth?"
            f"client_id={client_id}&"
            f"redirect_uri={redirect_uri}&"
            f"response_type=code&"
            f"scope={' '.join(SCOPES)}&"
            f"access_type=offline&prompt=consent"
        )
        st.info("To use this app, please authorize access to your Gmail.")
        st.link_button("🔗 Sign in with Google", auth_url, use_container_width=True)
        st.stop()
    else:
        # STEP B: Manually exchange the code for a token via a POST request
        # This bypasses the "code verifier" error entirely
        try:
            token_url = "https://oauth2.googleapis.com/token"
            data = {
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            }
            response = requests.post(token_url, data=data).json()
            
            if "error" in response:
                st.error(f"Auth Error: {response.get('error_description', 'Unknown error')}")
                st.query_params.clear()
                st.stop()

            # Create credentials and save to session
            creds = Credentials(
                token=response["access_token"],
                refresh_token=response.get("refresh_token"),
                token_uri=token_url,
                client_id=client_id,
                client_secret=client_secret,
                scopes=SCOPES
            )
            
            st.session_state.google_creds = creds
            st.query_params.clear()
            st.rerun()
            
        except Exception as e:
            st.error(f"Manual Handshake failed: {e}")
            st.stop()
