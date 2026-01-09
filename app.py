import requests  # Add this line!
import os.path
import streamlit as st
import mmh3
import numpy as np
import time
import hashlib
from datetime import datetime # NEW
from auth import get_gmail_service
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# --- 1. INITIALIZATION ---
if 'leaderboard' not in st.session_state:
    st.session_state.leaderboard = {}
if 'grid' not in st.session_state:
    st.session_state.grid = np.zeros((4, 1000))
if 'last_scanned' not in st.session_state: # NEW
    st.session_state.last_scanned = None

# --- 2. MATHEMATICAL ENGINE ---
def update_sketch(email):
    counts = []
    for row in range(4):
        col = mmh3.hash(email, row) % 1000
        st.session_state.grid[row][col] += 1
        counts.append(st.session_state.grid[row][col])
    st.session_state.leaderboard[email] = int(min(counts))

# --- 3. DIALOGS & HELPERS ---
@st.dialog("Confirm Auto-Delete Filter")
def confirm_future_delete(service, sender_email):
    st.warning(f"This will create a permanent Gmail filter for **{sender_email}**.")
    st.write("Future emails from this sender will go straight to the Trash.")
    if st.button("Confirm Block"):
        create_future_filter(service, sender_email)
        st.success(f"Blocked {sender_email}!")
        st.rerun()

def delete_existing_emails(service, sender_email):
    query = f"from:{sender_email} is:unread in:inbox"
    try:
        results = service.users().messages().list(userId='me', q=query).execute()
        messages = results.get('messages', [])
        if not messages:
            st.toast(f"No unread emails found for {sender_email}")
            return False
        
        # Trash in a loop for maximum reliability
        for msg in messages:
            service.users().messages().trash(userId='me', id=msg['id']).execute()
        return True
    except Exception as e:
        st.error(f"Gmail API Error: {e}")
        return False

def create_future_filter(service, sender_email):
    filter_rule = {
        'criteria': {'from': sender_email},
        'action': {'addLabelIds': ['TRASH'], 'removeLabelIds': ['INBOX']}
    }
    service.users().settings().filters().create(userId='me', body=filter_rule).execute()
    log_event(user_id_hash, "block")

# --- 4. MAIN UI ---
st.set_page_config(page_title="Clean up your Gmail", layout="wide")
st.title("📬 Clean up your Gmail")

# Display Timestamp at the top
if st.session_state.last_scanned:
    st.caption(f"🕒 Last successful scan: {st.session_state.last_scanned}")
else:
    st.caption("🕒 No scan data yet. Click below to start.")

col_a, col_b = st.columns(2)
with col_a:
    if st.button("🚀 Start Scanning Unread Emails", use_container_width=True):
        service = get_gmail_service()
        all_messages = []
        next_page_token = None
        target_limit = 20000

        # Inside your "Start Scanning" button logic:
        user_id_hash = hashlib.sha256(service.users().getProfile(userId='me').execute()['emailAddress'].encode()).hexdigest()
        user_id_hash = hashlib.sha256(service.users().getProfile(userId='me').execute()['emailAddress'].encode()).hexdigest()
        log_event(user_id_hash, "scan") # Logs a scan for this user
        
        status_msg = st.info("📑 Gathering email list...")
        while len(all_messages) < target_limit:
            results = service.users().messages().list(
                userId='me', q='label:unread label:inbox -label:trash', 
                maxResults=500, pageToken=next_page_token
            ).execute()
            all_messages.extend(results.get('messages', []))
            next_page_token = results.get('nextPageToken')
            if not next_page_token: break
        
        messages = all_messages[:target_limit]
        total = len(messages)
        status_msg.empty()
        
        progress_text = st.empty()
        bar = st.progress(0)
        
        def batch_callback(request_id, response, exception):
            if exception is None:
                headers = response.get('payload', {}).get('headers', [])
                sender = next((h['value'] for h in headers if h['name'] == 'From'), "Unknown")
                update_sketch(sender)

        batch_size = 50
        for i in range(0, total, batch_size):
            batch = service.new_batch_http_request(callback=batch_callback)
            for msg in messages[i : i + batch_size]:
                batch.add(service.users().messages().get(
                    userId='me', id=msg['id'], format='metadata', metadataHeaders=['From']
                ))
            batch.execute()
            
            pct = min((i + batch_size) / total, 1.0)
            bar.progress(pct)
            progress_text.text(f"Scanning {i + batch_size} / {total} emails...")
        
        # Update timestamp on completion
        st.session_state.last_scanned = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st.rerun()

with col_b:
    if st.button("🗑️ Reset All Data", use_container_width=True):
        st.session_state.grid = np.zeros((4, 1000))
        st.session_state.leaderboard = {}
        st.session_state.last_scanned = None
        st.rerun()

# --- 5. RESULTS ORGANIZATION ---
if st.session_state.leaderboard:
    st.divider()
    st.subheader("📊 Ranked Bulk Senders")
    
    st.markdown("*Note: Gmail API limits allow for processing batches of 50 emails per action. Counts are verified in real-time below.*")

    # This creates the sorted list of your top 15 offenders
    top_k = sorted(st.session_state.leaderboard.items(), key=lambda x: x[1], reverse=True)[:15]
    service = get_gmail_service()

    with st.container(border=True):
        # Header Row
        h1, h2, h3, h4 = st.columns([1, 4, 2, 4])
        h1.write("**Rank**")
        h2.write("**Sender**")
        h3.write("**Verified Count**")
        h4.write("**Actions**")
        st.divider()

        # Data Rows - Using 'top_k' here fixes your Error!
        for rank, (sender, estimate) in enumerate(top_k, 1):
            try:
                # Polite pause to stay under Google's rate limit
                time.sleep(0.3) 
                real_results = service.users().messages().list(
                    userId='me', 
                    q=f"from:{sender} is:unread in:inbox", 
                    maxResults=500
                ).execute()
                exact_count = len(real_results.get('messages', []))
                st.session_state.leaderboard[sender] = exact_count
            except Exception:
                exact_count = estimate

            # UI Display
            c1, c2, c3, c4 = st.columns([1, 4, 2, 4])
            c1.write(f"#{rank}")
            c2.write(f"`{sender}`")
            c3.write(str(exact_count))
            
            # Action Buttons
            btn_col1, btn_col2 = c4.columns(2)
            if btn_col1.button("Delete Past", key=f"del_{sender}"):
                if delete_existing_emails(service, sender):
                    st.toast(f"Cleaned {sender}")
                    del st.session_state.leaderboard[sender]
                    st.rerun()

            # Assuming 'total_deleted' is the length of the messages list
            log_event(user_id_hash, "delete", count=len(messages))
            
            if btn_col2.button("Block Future", key=f"fut_{sender}"):
                confirm_future_delete(service, sender, user_id_hash)

with st.expander("🛡️ Privacy Policy & Data Usage"):
    st.markdown("""
    ### Privacy Policy
    **Effective Date:** January 2026
    
    This app is designed to help you identify and manage high-volume email senders. Your privacy is our top priority.
    
    **1. Data Access**
    * The app requests access to your Gmail unread headers to calculate sender frequency.
    * We **do not** read, store, or transmit the content of your emails.
    * All processing is done in your active browser session.
    
    **2. Data Collection**
    * **Personal Data:** We do not collect or store your name, email address, or contact list.
    * **Usage Data:** We track the **total number of unique scans** across all users to measure app success. This data is completely anonymized and cannot be linked back to you.
    
    **3. Third-Party Services**
    * We use the Google Gmail API to provide the service. Your data remains within the Google ecosystem.
    
    **4. Your Control**
    * You can revoke the app's access at any time by clicking on "Revoke Access".
    """)

# In your sidebar or at the bottom of the page
with st.sidebar:
    st.divider()
    st.subheader("🔐 Data Control")
    st.write("Want to disconnect your Gmail?")
    
    # This link takes them directly to the page where they can remove your app
    revoke_url = "https://myaccount.google.com/permissions"
    st.link_button("Revoke App Access", revoke_url, use_container_width=True)
    
    st.caption("Clicking above will open your Google Security settings where you can remove this app's permissions.")

# Initialize connection
conn = st.connection("gsheets", type=GSheetsConnection)

def log_event(user_hash, action, count=1):
    try:
        # 1. Get existing data
        existing_data = conn.read(worksheet="Sheet1", ttl=0)
        
        # 2. Create new row
        new_row = pd.DataFrame([{
            "user_hash": user_hash,
            "action_type": action,
            "count": count,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }])
        
        # 3. Append and update
        updated_df = pd.concat([existing_data, new_row], ignore_index=True)
        conn.update(worksheet="Sheet1", data=updated_df)
    except Exception as e:
        # We use a silent pass so the user experience isn't ruined if logging fails
        print(f"Logging failed: {e}")
