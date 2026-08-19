import os
import pickle
import streamlit as st
import google.generativeai as genai
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# --- Page Setup ---
st.set_page_config(
    page_title="YouTube AI Comment Bot",
    page_icon="🤖",
    layout="wide"
)

# --- Sidebar Configuration ---
st.sidebar.title("⚙️ Bot Configuration")
gemini_api_key = st.sidebar.text_input("Gemini API Key", type="password", help="Get free key from aistudio.google.com")
bot_tone = st.sidebar.selectbox("Reply Tone", ["Friendly & Engaging", "Professional", "Casual Hinglish", "Short & Direct"])
auto_pilot = st.sidebar.toggle("⚡ Full Auto-Pilot Mode", value=False)

SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']

# --- YouTube OAuth Setup ---
def get_youtube_service():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
            
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('client_secret.json'):
                st.error("⚠️ 'client_secret.json' file upload karein ya directory me rakhein.")
                return None
            flow = InstalledAppFlow.from_client_secrets_file('client_secret.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
            
    return build('youtube', 'v3', credentials=creds)

# --- AI Sentiment & Reply Processing ---
def analyze_comment(comment_text, tone, api_key):
    if not api_key:
        return "NEUTRAL", "Please enter Gemini API key."
        
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""
    You are an AI assistant for a YouTube creator.
    Analyze this comment: "{comment_text}"
    
    Tasks:
    1. Categorize as strictly one of: [POSITIVE, QUESTION, SPAM, ABUSIVE].
    2. If POSITIVE or QUESTION, generate a natural reply in {tone} tone. If the comment is in Hinglish/Hindi, reply in Hinglish/Hindi.
    3. If SPAM or ABUSIVE, set reply to 'DELETE'.
    
    Output Format strictly:
    CATEGORY: <CATEGORY>
    REPLY: <REPLY TEXT>
    """
    
    try:
        res = model.generate_content(prompt)
        category = "POSITIVE"
        reply = "Thank you for the support!"
        
        for line in res.text.strip().splitlines():
            if line.startswith("CATEGORY:"):
                category = line.replace("CATEGORY:", "").strip()
            elif line.startswith("REPLY:"):
                reply = line.replace("REPLY:", "").strip()
                
        return category, reply
    except Exception as e:
        return "ERROR", f"AI Error: {str(e)}"

# --- UI Dashboard ---
st.title("🎬 YouTube AI Comment Manager")
st.caption("AI-powered auto reply and moderation agent.")

col1, col2, col3 = st.columns(3)
col1.metric("Status", "🟢 Active" if gemini_api_key else "🔴 Missing API Key")
col2.metric("Operating Mode", "Auto-Pilot" if auto_pilot else "Review Mode")
col3.metric("AI Model", "Gemini 1.5 Flash")

st.divider()

if st.button("📥 Fetch Latest Comments", type="primary"):
    if not gemini_api_key:
        st.warning("Pehle sidebar me Gemini API Key dalein.")
    else:
        youtube = get_youtube_service()
        if youtube:
            with st.spinner("Fetching comments..."):
                try:
                    response = youtube.commentThreads().list(
                        part="snippet",
                        allThreadsRelatedToChannelId="mine",
                        maxResults=10,
                        order="time"
                    ).execute()
                    
                    items = response.get("items", [])
                    if not items:
                        st.info("Koi naya comment nahi mila.")
                    
                    for item in items:
                        c_id = item['id']
                        c_data = item['snippet']['topLevelComment']['snippet']
                        author = c_data['authorDisplayName']
                        text = c_data['textDisplay']
                        
                        cat, rep = analyze_comment(text, bot_tone, gemini_api_key)
                        
                        st.markdown(f"**👤 {author}**")
                        st.write(f"💬 *{text}*")
                        
                        if cat in ["SPAM", "ABUSIVE"]:
                            st.error(f"🚨 Category: {cat}")
                            if auto_pilot:
                                youtube.comments().setModerationStatus(id=c_id, moderationStatus="rejected").execute()
                                st.caption("🗑️ Auto-deleted.")
                            else:
                                if st.button("Delete Comment", key=f"d_{c_id}"):
                                    youtube.comments().setModerationStatus(id=c_id, moderationStatus="rejected").execute()
                                    st.success("Comment deleted.")
                        else:
                            st.success(f"🏷️ Category: {cat}")
                            st.info(f"🤖 **Reply:** {rep}")
                            if auto_pilot:
                                youtube.comments().insert(
                                    part="snippet",
                                    body={"snippet": {"parentId": c_id, "textOriginal": rep}}
                                ).execute()
                                st.caption("✅ Auto-replied.")
                            else:
                                if st.button("Send Reply", key=f"r_{c_id}"):
                                    youtube.comments().insert(
                                        part="snippet",
                                        body={"snippet": {"parentId": c_id, "textOriginal": rep}}
                                    ).execute()
                                    st.success("Reply sent.")
                        st.divider()
                except Exception as ex:
                    st.error(f"Error: {ex}")
