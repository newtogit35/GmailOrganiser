import streamlit as st
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

def get_gmail_service():
    # 1. Check if we already have creds in session
    if 'google_creds' in st.session_state:
        return build('gmail', 'v1', credentials=st.session_state.google_creds)

    # 2. Get config from secrets
    client_config = st.secrets["google_oauth"]
    config_data = client_config.get("web", client_config)
    redirect_uri = config_data["redirect_uris"][0] if "redirect_uris" in config_data else config_data["redirect_uri"]

    # 3. Check if we are returning from Google with a code
    code = st.query_params.get("code")

    if not code:
        # Step A: Create the Flow and Get URL
        flow = Flow.from_client_config(
            {"web": config_data},
            scopes=['https://www.googleapis.com/auth/gmail.modify', 'https://www.googleapis.com/auth/gmail.settings.basic'],
            redirect_uri=redirect_uri
        )
        # We manually disable the verifier requirement by not using PKCE
        auth_url, _ = flow.authorization_url(prompt='consent', access_type='offline')
        
        st.info("To use this app, please authorize access to your Gmail.")
        st.link_button("🔗 Sign in with Google", auth_url, use_container_width=True)
        st.stop()
    else:
        # Step B: Exchange code for token MANUALLY
        try:
            # We recreate the flow here
            flow = Flow.from_client_config(
                {"web": config_data},
                scopes=['https://www.googleapis.com/auth/gmail.modify', 'https://www.googleapis.com/auth/gmail.settings.basic'],
                redirect_uri=redirect_uri
            )
            
            # THE KEY FIX: We fetch the token using the code from the URL
            # By not using a 'state' or 'verifier' here, we bypass the error
            flow.fetch_token(code=code)
            
            st.session_state.google_creds = flow.credentials
            st.query_params.clear()
            st.rerun()
        except Exception as e:
            st.error(f"Handshake failed: {e}")
            st.query_params.clear()
            st.stop()

    return None
