import streamlit as st
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

def get_gmail_service():
    # 1. If we already have valid credentials, use them
    if 'google_creds' in st.session_state:
        return build('gmail', 'v1', credentials=st.session_state.google_creds)

    # 2. Setup the Flow (Use session_state to prevent "Missing code verifier")
    client_config = st.secrets["google_oauth"]
    config_data = client_config.get("web", client_config)
    
    # Check if we already have a flow in progress
    if 'auth_flow' not in st.session_state:
        st.session_state.auth_flow = Flow.from_client_config(
            {"web": config_data},
            scopes=['https://www.googleapis.com/auth/gmail.modify'],
            redirect_uri=config_data["redirect_uris"][0] if "redirect_uris" in config_data else config_data["redirect_uri"]
        )

    # 3. Handle the return from Google
    code = st.query_params.get("code")
    if code:
        try:
            # Use the EXACT SAME flow object we created before the redirect
            st.session_state.auth_flow.fetch_token(code=code)
            st.session_state.google_creds = st.session_state.auth_flow.credentials
            st.query_params.clear()
            st.rerun()
        except Exception as e:
            st.error(f"Handshake failed: {e}")
            # Reset flow so user can try again
            del st.session_state.auth_flow 
            st.stop()

    # 4. If no code and no creds, show the login button
    auth_url, _ = st.session_state.auth_flow.authorization_url(prompt='consent', access_type='offline')
    st.info("To use this app, please authorize access to your Gmail.")
    st.link_button("🔗 Sign in with Google", auth_url, use_container_width=True)
    st.stop()
