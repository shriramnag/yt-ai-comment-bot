import os
import streamlit as st
import google.generativeai as genai
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials

# --- Page Setup ---
st.set_page_config(page_title="YouTube AI Manager", page_icon="🎬", layout="wide")

# --- Sidebar Configuration ---
st.sidebar.title("⚙️ Settings")
gemini_api_key = st.sidebar.text_input("Gemini API Key", type="password")
bot_tone = st.sidebar.selectbox("Reply Tone", ["Friendly & Engaging", "Casual Hinglish", "Professional", "Short & Direct"])
auto_pilot = st.sidebar.toggle("⚡ Full Auto-Pilot Mode", value=False)
fetch_limit = st.sidebar.slider("Number of Comments to Fetch", min_value=5, max_value=50, value=10)

SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']

# --- OAuth 2.0 Web Flow ---
def get_auth_flow():
    # Google Cloud Console se Client ID & Secret
    client_config = {
        "web": {
            "client_id": st.secrets.get("GOOGLE_CLIENT_ID", ""),
            "client_secret": st.secrets.get("GOOGLE_CLIENT_SECRET", ""),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "https://oauth.pstmn.io/v1/browser-callback"]
        }
    }
    
    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri="urn:ietf:wg:oauth:2.0:oob"
    )
    return flow

# --- Session State for Auth ---
if "youtube_creds" not in st.session_state:
    st.session_state.youtube_creds = None

# --- AI Analyzer ---
def analyze_comment(comment_text, tone, api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""
    You are an AI assistant for a YouTube creator.
    Analyze this comment: "{comment_text}"
    
    1. Categorize as strictly one of: [POSITIVE, QUESTION, SPAM, ABUSIVE].
    2. If POSITIVE or QUESTION, generate a natural reply in {tone} tone. Match language (Hinglish/Hindi/English).
    3. If SPAM or ABUSIVE, reply must be strictly 'DELETE'.
    
    Output strictly:
    CATEGORY: <CATEGORY>
    REPLY: <REPLY TEXT>
    """
    try:
        res = model.generate_content(prompt)
        cat = "POSITIVE"
        rep = "Thank you for the support!"
        for line in res.text.strip().splitlines():
            if line.startswith("CATEGORY:"):
                cat = line.replace("CATEGORY:", "").strip()
            elif line.startswith("REPLY:"):
                rep = line.replace("REPLY:", "").strip()
        return cat, rep
    except Exception as e:
        return "ERROR", str(e)

# --- UI Header ---
st.title("🎬 YouTube AI Comment & Moderation Manager")

# Channel Connection Section
st.subheader("1️⃣ Connect Channel")
if not st.session_state.youtube_creds:
    st.info("YouTube Channel link karne ke liye niche diye gaye steps follow karein:")
    
    col_a, col_b = st.columns(2)
    client_id = col_a.text_input("Google OAuth Client ID", type="password")
    client_secret = col_b.text_input("Google OAuth Client Secret", type="password")
    
    if client_id and client_secret:
        client_config = {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob"]
            }
        }
        flow = Flow.from_client_config(client_config, scopes=SCOPES, redirect_uri="urn:ietf:wg:oauth:2.0:oob")
        auth_url, _ = flow.authorization_url(prompt='consent')
        
        st.markdown(f"👉 **[Click Here to Sign In with Google & Authorize Channel]({auth_url})**")
        auth_code = st.text_input("Enter Authorization Code (Google se copy karke yahan paste karein):")
        
        if st.button("Link Channel"):
            try:
                flow.fetch_token(code=auth_code)
                st.session_state.youtube_creds = flow.credentials
                st.success("✅ Channel Successfully Connected!")
                st.rerun()
            except Exception as e:
                st.error(f"Auth Error: {e}")
else:
    st.success("✅ Channel Connected & Ready!")
    if st.button("Disconnect Channel"):
        st.session_state.youtube_creds = None
        st.rerun()

st.divider()

# --- Comments Processing Section ---
st.subheader("2️⃣ Comments Feed & Auto-Actions")

if st.button("📥 Fetch & Analyze Comments", type="primary"):
    if not gemini_api_key:
        st.warning("⚠️ Pehle sidebar me Gemini API Key dalein.")
    elif not st.session_state.youtube_creds:
        st.warning("⚠️ Pehle apna YouTube channel link karein.")
    else:
        youtube = build('youtube', 'v3', credentials=st.session_state.youtube_creds)
        with st.spinner("Channel se comments load ho rahe hain..."):
            try:
                response = youtube.commentThreads().list(
                    part="snippet,replies",
                    allThreadsRelatedToChannelId="mine",
                    maxResults=fetch_limit,
                    order="time"
                ).execute()
                
                items = response.get("items", [])
                if not items:
                    st.info("Koi comment nahi mila.")
                
                for item in items:
                    c_id = item['id']
                    c_data = item['snippet']['topLevelComment']['snippet']
                    author = c_data['authorDisplayName']
                    text = c_data['textDisplay']
                    
                    cat, rep = analyze_comment(text, bot_tone, gemini_api_key)
                    
                    st.markdown(f"**👤 {author}**")
                    st.write(f"💬 *{text}*")
                    
                    # Replies count check
                    total_replies = item['snippet']['totalReplyCount']
                    if total_replies > 0:
                        st.caption(f"↳ {total_replies} reply/replies under this comment")
                    
                    if cat in ["SPAM", "ABUSIVE"]:
                        st.error(f"🚨 Flagged: {cat}")
                        if auto_pilot:
                            youtube.comments().setModerationStatus(id=c_id, moderationStatus="rejected").execute()
                            st.caption("🗑️ Auto-deleted.")
                        else:
                            if st.button(f"🗑️ Delete Comment", key=f"del_{c_id}"):
                                youtube.comments().setModerationStatus(id=c_id, moderationStatus="rejected").execute()
                                st.success("Comment deleted.")
                    else:
                        st.success(f"🏷️ Category: {cat}")
                        st.info(f"🤖 **Suggested Reply:** {rep}")
                        
                        if auto_pilot:
                            youtube.comments().insert(
                                part="snippet",
                                body={"snippet": {"parentId": c_id, "textOriginal": rep}}
                            ).execute()
                            st.caption("✅ Auto-replied.")
                        else:
                            if st.button(f"🚀 Send Reply", key=f"rep_{c_id}"):
                                youtube.comments().insert(
                                    part="snippet",
                                    body={"snippet": {"parentId": c_id, "textOriginal": rep}}
                                ).execute()
                                st.success("Reply posted!")
                    st.divider()
            except Exception as err:
                st.error(f"Error: {err}")
