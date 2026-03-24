import requests 
import os.path
import streamlit as st
import mmh3
import numpy as np
import time
import hashlib
import pandas as pd
from datetime import datetime
from auth import get_gmail_service

# <!-- Google Tag Manager -->
gtm_id = "GTM-54JS276X"

gtm_script = f"""
<script>(function(w,d,s,l,i){{w[l]=w[l]||[];w[l].push({{'gtm.start':
new Date().getTime(),event:'gtm.js'}});var f=d.getElementsByTagName(s)[0],
j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
}})(window,document,'script','dataLayer','{gtm_id}');</script>
"""
# <!-- End Google Tag Manager -->

# This injects the tag into the app invisibly
components.html(gtm_script, height=0, width=0)

# --- 1. INITIALIZATION & CONNECTION ---
if 'leaderboard' not in st.session_state:
    st.session_state.leaderboard = {}
if 'total_size' not in st.session_state: # NEW: Tracks total inbox size in bytes
    st.session_state.total_size = 0
if 'sender_sizes' not in st.session_state: # NEW: Tracks size per sender for accurate deletion
    st.session_state.sender_sizes = {}
if 'grid' not in st.session_state:
    st.session_state.grid = np.zeros((4, 1000))
if 'last_scanned' not in st.session_state:
    st.session_state.last_scanned = None
if 'user_id_hash' not in st.session_state:
    st.session_state.user_id_hash = None


# --- 2. LOGGING ENGINE ---
# def log_event(user_hash, action, count=1):
#     """Logs app activity to Google Sheets for analytics."""
#     try:
#         # Read current data from Sheet1
#         existing_data = conn.read(worksheet="Sheet1", ttl=0)
        
#         # Prepare new entry
#         new_row = pd.DataFrame([{
#             "user_hash": user_hash,
#             "action_type": action,
#             "count": count,
#             "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#         }])
        
#         # Append and push update
#         updated_df = pd.concat([existing_data, new_row], ignore_index=True)
#         conn.update(worksheet="Sheet1", data=updated_df)
#     except Exception as e:
#         # Fails silently in UI but shows in logs to keep app running
#         print(f"Logging failed: {e}")

# --- 3. GMAIL & MATH ENGINE ---
def update_sketch(email):
    """Uses Count-Min Sketch to estimate sender frequency."""
    counts = []
    for row in range(4):
        col = mmh3.hash(email, row) % 1000
        st.session_state.grid[row][col] += 1
        counts.append(st.session_state.grid[row][col])
    st.session_state.leaderboard[email] = int(min(counts))

def delete_existing_emails(service, sender_email):
    """Trashes unread emails from a specific sender."""
    query = f"from:{sender_email} in:inbox"
    try:
        results = service.users().messages().list(userId='me', q=query).execute()
        messages = results.get('messages', [])
        if not messages:
            st.toast(f"No emails found for {sender_email}")
            return 0
        
        for msg in messages:
            service.users().messages().trash(userId='me', id=msg['id']).execute()
        return len(messages)
    except Exception as e:
        st.error(f"Gmail API Error: {e}")
        return 0

def create_future_filter(service, sender_email, user_id_hash):
    """Creates a Gmail filter to auto-trash future emails."""
    filter_rule = {
        'criteria': {'from': sender_email},
        'action': {'addLabelIds': ['TRASH'], 'removeLabelIds': ['INBOX']}
    }
    try:
        service.users().settings().filters().create(userId='me', body=filter_rule).execute()
#        log_event(user_id_hash, "block")
    except Exception as e:
        st.error(f"Filter Error: {e}")

@st.dialog("Confirm Auto-Delete Filter")
def confirm_future_delete(service, sender_email, user_id_hash):
    st.warning(f"This will create a permanent Gmail filter for **{sender_email}**.")
    st.write("Future emails from this sender will go straight to the Trash.")
    if st.button("Confirm Block"):
        create_future_filter(service, sender_email, user_id_hash)
        st.success(f"Blocked {sender_email}!")
        st.rerun()

# --- 4. MAIN UI ---
st.set_page_config(page_title="Clean up your Gmail", layout="wide")
st.title("📬 Clean up your Gmail")

# Helper to format size nicely
def format_size(size_bytes):
    mb = size_bytes / (1024 * 1024)
    if mb < 1024:
        return f"{mb:.1f} MB"
    return f"{mb/1024:.2f} GB"

# Initialize variables if they don't exist
if 'total_size' not in st.session_state:
    st.session_state.total_size = 0

# Display Timestamp and size 

# Create two columns for the Metadata (Time and Size)
meta_col1, meta_col2 = st.columns([2, 1])

with meta_col1:
 if st.session_state.last_scanned:
     st.caption(f"🕒 Last successful scan: {st.session_state.last_scanned}")
 else:
     st.caption("🕒 No scan data yet. Click below to start.")

with meta_col2:
    # This displays the size right next to the timestamp
    current_size = format_size(st.session_state.get('total_size', 0))
    st.metric(
        label="📦 Total Inbox Volume:",
        value=current_size,
        help="This size is an estimate, in order to free up the space you will have to go to your trash in gmail and click on 'empty trash'."
    )

col_a, col_b = st.columns(2)

with col_a:
    if st.button("🚀 Start Scanning All Inbox Emails", use_container_width=True):
        service = get_gmail_service()
        all_messages = []
        next_page_token = None
        target_limit = 40000

        # Create user hash for privacy-safe logging
        user_profile = service.users().getProfile(userId='me').execute()
        user_email = user_profile['emailAddress']
        st.session_state.user_id_hash = hashlib.sha256(user_email.encode()).hexdigest()
        
        # Log the scan event
#        log_event(st.session_state.user_id_hash, "scan")
        
        status_msg = st.info("📑 Gathering email list...")
        while len(all_messages) < target_limit:
            results = service.users().messages().list(
                userId='me', q='label:inbox -label:trash', 
                maxResults=1000, pageToken=next_page_token
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
                size = response.get('sizeEstimate', 0)
                st.session_state.total_size += size
                st.session_state.sender_sizes[sender] = st.session_state.sender_sizes.get(sender, 0) + size
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
        
        st.session_state.last_scanned = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # st.rerun()

with st.sidebar:
    st.header("⚙️ App Controls")
    
    if st.button("🗑️ Reset All Data", use_container_width=True):
        st.session_state.grid = np.zeros((4, 1000))
        st.session_state.leaderboard = {}
        st.session_state.last_scanned = None

# ADD THESE TWO LINES TO CLEAR THE SIZE METRICS
        st.session_state.total_size = 0
        st.session_state.sender_sizes = {}
        st.rerun()
    
    st.info("Tip: Close this sidebar using the arrow (>) at the top left for a full-screen table view.")

# --- 5. RESULTS ORGANIZATION ---
if st.session_state.leaderboard:
    st.divider()
    st.subheader("📊 Ranked Heavy Hitters")
    
    # 1. Get the top candidates based on estimates
    candidates = sorted(st.session_state.leaderboard.items(), key=lambda x: x[1], reverse=True)[:15]
    service = get_gmail_service()
    
    # 2. PRE-VERIFY: Get actual counts for just these 15
    verified_data = []
    status_text = st.empty()
    status_text.caption("Refining rankings with live data...")
    
    for sender, estimate in candidates:
        try:
            time.sleep(0.1) # Faster pause for pre-verification
            res = service.users().messages().list(userId='me', q=f"from:{sender} in:inbox", maxResults=500).execute()
            count = len(res.get('messages', []))
            verified_data.append((sender, count))
        except:
            verified_data.append((sender, estimate))
    
    status_text.empty()

    # 3. RE-SORT: Sort the list again using the TRUTH
    top_k = sorted(verified_data, key=lambda x: x[1], reverse=True)

    # 4. DISPLAY: Now Rank #1 will always have the highest Verified Count
    with st.container(border=True):
        h1, h2, h3, h4 = st.columns([1, 4, 2, 4])
        # ... (Headers stay the same) ...

        for rank, (sender, exact_count) in enumerate(top_k, 1):
            c1, c2, c3, c4 = st.columns([1, 4, 2, 4])
            c1.write(f"#{rank}")
            c2.write(f"`{sender}`") # Plain text fix included
            c3.write(f"**{exact_count}**")
            # ... (Buttons stay the same) ...
            
            btn_col1, btn_col2 = c4.columns(2)
            if btn_col1.button("Delete Past", key=f"del_{sender}"):
                deleted_count = delete_existing_emails(service, sender)
                if deleted_count > 0:
                    # NEW: Subtract this sender's footprint from the total
                    deleted_weight = st.session_state.sender_sizes.get(sender, 0)
                    st.session_state.total_size -= deleted_weight

#                    log_event(st.session_state.user_id_hash, "delete", count=deleted_count)
                    st.toast(f"Cleaned {sender}")
                    del st.session_state.leaderboard[sender]
                    st.rerun()
            
            if btn_col2.button("Block Future", key=f"fut_{sender}"):
                confirm_future_delete(service, sender, st.session_state.user_id_hash)

# --- 6. FOOTER & PRIVACY ---
st.divider()
with st.expander("🛡️ Privacy Policy & Data Usage"):
    st.markdown("""
    ### Privacy Policy
    **Effective Date:** January 2026
    
    This app helps you manage high-volume email senders while keeping your data private.
    
    **1. Data Access**
    * We access Gmail headers to calculate sender frequency.
    * We **do not** read or store email content.
    
    **2. Data Collection**
    * **Personal Data:** We do not store names or email addresses.
    * **Usage Data:** We track anonymous activity (scans, deletes, blocks) in a private Google Sheet to improve the app. This is linked to a private 'hash' ID, not your identity.
    
    **3. Your Control**
    * You can revoke access anytime via your Google Account settings.
    """)

with st.sidebar:
    st.subheader("🔐 Data Control")
    st.write("Want to disconnect your Gmail?")
    revoke_url = "https://myaccount.google.com/permissions"
    st.link_button("Revoke App Access", revoke_url, use_container_width=True)
    st.caption("This will open your Google Security settings.")
