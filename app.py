"""
AI Conversational RAG Agent with Streamlit
Chat with Google Gemini | Upload Files | Scrape Web Links
"""

import streamlit as st
import google.generativeai as genai
import os
import re
import io
import requests
from bs4 import BeautifulSoup
import pypdf
import docx
from PIL import Image

# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────
class AgentConfig:
    LOCKED_MODEL    = "gemini-3.1-flash-lite-preview" # Fixed as requested
    MAX_HISTORY     = 12                              # Max conversation turns kept in context
    MAX_WEB_CHARS   = 8000                            # Max chars scraped from a website
    MAX_FILE_CHARS  = 20000                           # Max chars extracted from a document

# ─────────────────────────────────────────────
# Page Setup
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="AI RAG Agent",
    page_icon="🤖",
    layout="centered",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .block-container { padding-top: 2rem; padding-bottom: 7rem; }
    [data-testid="stFileUploadDropzone"] { 
        padding: 5px; 
        min-height: 40px; 
        border: 1px dashed rgba(255,255,255,0.1);
        border-radius: 10px;
    }
    .stChatMessage { border-radius: 12px; margin-bottom: 0.5rem; }
    
    /* Sticky Bottom Container */
    .stChatInputContainer {
        padding-bottom: 20px;
        background: transparent !important;
    }
    
    .upload-chip {
        display: inline-flex;
        align-items: center;
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 16px;
        padding: 4px 12px;
        margin-right: 8px;
        margin-bottom: 8px;
        font-size: 0.8rem;
    }
    
    /* Hide default file uploader text for a cleaner look */
    .stFileUploader section div div { font-size: 0.7rem; }
    
    /* Mobile Responsiveness */
    @media (max-width: 768px) {
        .block-container { padding-top: 1rem; padding-bottom: 5.5rem; padding-left: 0.8rem; padding-right: 0.8rem; }
        .stChatMessage { font-size: 0.95rem; padding: 10px; }
        h1 { font-size: 1.8rem !important; }
        .upload-chip { font-size: 0.75rem; padding: 4px 8px; margin-bottom: 4px; }
        [data-testid="stFileUploadDropzone"] { min-height: 35px; }
    }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# Session State Defaults
# ─────────────────────────────────────────────
defaults = {
    "chat_history":   [],    # list of {"role": "user"|"assistant", "content": str}
    "model_instance": None,
    "last_api_key":   "",
    "last_model":     "",
    "temp_files":     [],
    "persistent_context": "",
    "persistent_images": [],
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─────────────────────────────────────────────
# Cached Utility Functions (run once per input)
# ─────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def extract_text_from_file(file_name: str, file_bytes: bytes) -> str:
    """Extract text from PDF, DOCX, or TXT — cached per unique file."""
    ext = file_name.rsplit(".", 1)[-1].lower()
    try:
        if ext == "pdf":
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            text = "\n".join(p.extract_text() or "" for p in reader.pages)
        elif ext == "docx":
            doc = docx.Document(io.BytesIO(file_bytes))
            text = "\n".join(p.text for p in doc.paragraphs)
        elif ext == "txt":
            text = file_bytes.decode("utf-8", errors="ignore")
        else:
            return f"⚠️ Unsupported format: {ext}"
    except Exception as e:
        return f"Error reading {file_name}: {e}"
    return text.strip()[:AgentConfig.MAX_FILE_CHARS]

@st.cache_data(show_spinner=False)
def scrape_website(url: str) -> str:
    """Scrape and clean a webpage — cached per URL."""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = re.sub(r"\s+", " ", soup.get_text(separator=" ")).strip()
        return text[:AgentConfig.MAX_WEB_CHARS]
    except Exception as e:
        return f"Error scraping {url}: {e}"

def find_urls(text: str) -> list[str]:
    """Find all http(s) URLs embedded anywhere in a string."""
    return re.findall(r"https?://[^\s\"'>]+", text)

# ─────────────────────────────────────────────
# Model Initialization (smart — only when key/model changes)
# ─────────────────────────────────────────────
def get_model(api_key: str, model_name: str):
    """Return cached model instance; reinitialize only if key or model changed."""
    if (
        st.session_state.model_instance is None
        or st.session_state.last_api_key   != api_key
        or st.session_state.last_model     != model_name
    ):
        genai.configure(api_key=api_key)
        st.session_state.model_instance = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=(
                "You are a smart, concise, and helpful AI assistant. "
                "Use markdown formatting, bullet points, and code blocks when appropriate. "
                "Be direct — avoid unnecessary filler phrases."
            ),
            generation_config={
                "temperature": 0.7,
                "top_p":       0.95,
                "max_output_tokens": 8192,
            },
        )
        st.session_state.last_api_key = api_key
        st.session_state.last_model   = model_name
    return st.session_state.model_instance

# ─────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Settings")
    st.divider()

    api_key = os.getenv("GOOGLE_API_KEY", "")
    if not api_key:
        api_key = st.text_input(
            "🔑 Google API Key",
            type="password",
            help="Get a free key at https://aistudio.google.com/app/apikey",
        )
    else:
        st.success("✅ Successfully running..")

    st.info(f"🤖 **Model:** {AgentConfig.LOCKED_MODEL}")

    st.divider()
    if st.button("🗑️ Clear Chat History", use_container_width=True):
        st.session_state.chat_history = []
        st.session_state.persistent_context = ""
        st.session_state.persistent_images = []
        st.rerun()

    st.divider()

    st.divider()
    st.subheader("📖 How to Use")
    st.markdown("""
- **Chat** — type naturally
- **Documents** — upload files above
- **Web links** — paste any URL in chat and the agent will scrape it
- **Clear** — reset conversation above
""")
    st.caption("Built with Streamlit & API")

# ─────────────────────────────────────────────
# Main Chat UI
# ─────────────────────────────────────────────


st.title("🤖 AI Conversational Agent")
st.caption("· Upload Files · Upload Images · Paste Links")

if not api_key:
    st.warning("⚠️ Enter your API Key in the sidebar to begin.")
    st.info("💡SET MODELS ACCORDING TO YOUR API KEY!!")
    st.stop()

# ── EMPTY STATE SUGGESTIONS ───────────────
suggestion_clicked = None
if len(st.session_state.chat_history) == 0:
    st.markdown("### ⛓️‍💥 Welcome to your Intelligent Space")
    st.markdown("Get started by typing a message below, or explore the capabilities directly:")
    
    st.write("")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("📄 Summarize a document", use_container_width=True, help="Upload a document below and click this."):
            suggestion_clicked = "Please summarize the document I attached."
        if st.button("🌐 Analyze a website", use_container_width=True):
            suggestion_clicked = "Can you help me extract insights from a website?"
    with c2:
        if st.button("💻 Debug my code", use_container_width=True):
            suggestion_clicked = "Can you help me analyze and fix some code?"
        if st.button("💡 Brainstorm ideas", use_container_width=True):
            suggestion_clicked = "Let's brainstorm some innovative ideas for my upcoming project."
    st.write("")
    st.write("")

# Render existing conversation
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ─────────────────────────────────────────────
# Bottom Floating Input Area
# ─────────────────────────────────────────────
# This container mimics a modern integrated input bar
input_container = st.container()

with input_container:
    # 1. File Uploading (Integrated above prompt)
    uploaded_files = st.file_uploader(
        "📎 Attach documents to conversation", 
        type=["pdf", "docx", "txt", "png", "jpg", "jpeg", "webp"], 
        accept_multiple_files=True,
        label_visibility="collapsed"
    )
    
    # Process files if any
    current_docs_context = ""
    current_images = []
    
    if uploaded_files:
        with st.spinner("Processing files..."):
            for f in uploaded_files:
                ext = f.name.rsplit(".", 1)[-1].lower()
                if ext in ["png", "jpg", "jpeg", "webp"]:
                    img = Image.open(f)
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    current_images.append(img)
                else:
                    content = extract_text_from_file(f.name, f.read())
                    current_docs_context += f"\n--- Source: {f.name} ---\n{content}\n"
                    
        st.session_state.persistent_context = current_docs_context
        st.session_state.persistent_images = current_images
        
        # Display small chips for feedback
        for f in uploaded_files:
            icon = "🖼️" if f.name.rsplit(".", 1)[-1].lower() in ["png", "jpg", "jpeg", "webp"] else "📄"
            st.markdown(f'<div class="upload-chip">{icon} {f.name}</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────
# Chat Input & Response
# ─────────────────────────────────────────────
user_input_from_chat = st.chat_input("Type your message, paste a URL, or ask about uploaded files…")
user_input = user_input_from_chat or suggestion_clicked

if user_input:
    # ── Collect any extra context ──────────────
    extra_context_parts = []

    # Documents from bottom bar
    if st.session_state.persistent_context:
        extra_context_parts.append(st.session_state.persistent_context)

    # URLs found in the user's message
    urls = find_urls(user_input)
    if urls:
        with st.status("🌐 Fetching web content…", expanded=False) as web_status:
            for url in urls:
                st.write(f"Scraping `{url}`…")
                content = scrape_website(url)
                extra_context_parts.append(f"\n--- Web: {url} ---\n{content}\n")
            web_status.update(label=f"✅ Scraped {len(urls)} URL(s)", state="complete")

    # ── Display user message immediately ───────
    with st.chat_message("user"):
        st.markdown(user_input)

    # ── Build the prompt ───────────────────────
    full_prompt = user_input
    if extra_context_parts:
        context_block = "\n".join(extra_context_parts)
        full_prompt = (
            f"--- Context / Reference ---\n{context_block}\n"
            f"--- User Question ---\n{user_input}"
        )

    # ── Format history for Gemini API ─────────
    # Gemini expects alternating user/model turns
    history_messages = []
    for h in st.session_state.chat_history[-(AgentConfig.MAX_HISTORY * 2):]:
        role = "user" if h["role"] == "user" else "model"
        history_messages.append({"role": role, "parts": [h["content"]]})

    current_prompt_parts = [full_prompt]
    if st.session_state.persistent_images:
        current_prompt_parts.extend(st.session_state.persistent_images)
        
    history_messages.append({"role": "user", "parts": current_prompt_parts})

    # ── Save user turn BEFORE generating ──────
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    # ── Stream the assistant response ─────────
    with st.chat_message("assistant"):
        try:
            model = get_model(api_key, AgentConfig.LOCKED_MODEL)

            with st.spinner("🤔 Thinking..."):
                def token_stream():
                    response = model.generate_content(history_messages, stream=True)
                    for chunk in response:
                        try:
                            if chunk.text:
                                yield chunk.text
                        except Exception:
                            pass

                full_response = st.write_stream(token_stream)

        except Exception as e:
            full_response = f"❌ **Error:** {e}"
            st.error(full_response)

    # ── Save assistant turn ────────────────────
    st.session_state.chat_history.append({"role": "assistant", "content": full_response})