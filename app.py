"""
Simple Conversational AI Agent with Streamlit
Chat with Google Gemini - Deploy anywhere!
"""

import streamlit as st
import google.generativeai as genai
from datetime import datetime
import os
import requests
from bs4 import BeautifulSoup
import pypdf
import docx
import io

# ============================================
# Configuration
# ============================================

class AgentConfig:
    """Configuration for the AI agent"""
    GEMINI_MODEL = "gemini-2.5-flash"
    MAX_HISTORY = 10 

# ============================================
# Page Configuration
# ============================================

st.set_page_config(
    page_title="AI Conversational Agent RAG",
    page_icon="🤖",
    layout="centered",
    initial_sidebar_state="expanded"
)

# Custom CSS for better file upload UI
st.markdown("""
<style>
    .upload-container {
        display: flex;
        gap: 10px;
        align-items: center;
        margin-bottom: 10px;
    }
    .stFileUploader {
        max-width: 150px;
    }
    [data-testid="stFileUploadDropzone"] {
        padding: 10px;
        min-height: 50px;
    }
</style>
""", unsafe_allow_html=True)

# ============================================
# Initialize Session State
# ============================================

if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

if 'agent_initialized' not in st.session_state:
    st.session_state.agent_initialized = False

if 'model' not in st.session_state:
    st.session_state.model = None

if 'uploaded_files' not in st.session_state:
    st.session_state.uploaded_files = []

if 'current_context' not in st.session_state:
    st.session_state.current_context = ""

if 'temp_files' not in st.session_state:
    st.session_state.temp_files = []

# ============================================
# File Processing Functions
# ============================================

def extract_text_from_pdf(file) -> str:
    """Extract text from PDF file"""
    try:
        pdf_reader = pypdf.PdfReader(file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        return f"Error reading PDF: {str(e)}"

def extract_text_from_docx(file) -> str:
    """Extract text from DOCX file"""
    try:
        doc = docx.Document(file)
        return "\n".join([paragraph.text for paragraph in doc.paragraphs])
    except Exception as e:
        return f"Error reading DOCX: {str(e)}"

def extract_text_from_txt(file) -> str:
    """Extract text from TXT file"""
    try:
        return file.read().decode('utf-8')
    except Exception as e:
        return f"Error reading TXT: {str(e)}"

def process_uploaded_file(uploaded_file):
    """Process uploaded file and extract text"""
    file_type = uploaded_file.name.split('.')[-1].lower()
    
    if file_type == 'pdf':
        return extract_text_from_pdf(uploaded_file)
    elif file_type == 'docx':
        return extract_text_from_docx(uploaded_file)
    elif file_type == 'txt':
        return extract_text_from_txt(uploaded_file)
    else:
        return "Unsupported file format. Please upload PDF, DOCX, or TXT files."

def scrape_website(url: str) -> str:
    """Scrape text content from a website"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Get text
        text = soup.get_text()
        
        # Clean up text
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        # Limit to first 5000 characters
        return text[:5000] if len(text) > 5000 else text
        
    except Exception as e:
        return f"Error scraping website: {str(e)}"

def is_url(text: str) -> bool:
    """Check if text is a URL"""
    return text.startswith(('http://', 'https://', 'www.'))

# ============================================
# Sidebar - API Key Configuration
# ============================================

with st.sidebar:
    st.title("⚙️ Other Features:")
    st.markdown("---")
    
    # Get API key from environment variable or user input
    api_key = os.getenv('GOOGLE_API_KEY')
    
    if not api_key:
        api_key = st.text_input(
            "🔑 Enter Google API Key",
            type="password",
            help="Get your API key from https://makersuite.google.com/app/apikey"
        )
    else:
        st.success("✅ API Key loaded from environment")
    
    st.markdown("---")
    
    # Model information
    st.subheader("🤖 Model Info")
    st.info(f"**Model:** {AgentConfig.GEMINI_MODEL}")
    
    st.markdown("---")
    
    # Clear conversation button
    if st.button("🗑️ Clear Conversation ⌀", use_container_width=True):
        st.session_state.chat_history = []
        st.session_state.current_context = ""
        st.session_state.uploaded_files = []
        st.session_state.temp_files = []
        st.rerun()
    
    st.markdown("---")
    
    # Instructions
    st.subheader("📖 Instructions")
    st.markdown("""
    **💬 Chat:**
    - Type your message normally
    
    **📁 Upload Files:**
    - Click 📎 button next to message box
    - Upload PDF, DOCX, or TXT files
    
    **🔗 Paste Links:**
    - Paste any website URL in chat
    - Ask questions about the page
    
    **🗑️ Clear:**
    - Click 'Clear Conversation' to reset
    """)
    
    st.markdown("---")
    st.caption("💡Visit My Profile: [Portfolio](https://your-portfolio.com)")

# ============================================
# Initialize Agent
# ============================================

def initialize_agent(api_key):
    """Initialize the Gemini model"""
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            AgentConfig.GEMINI_MODEL,
            generation_config={
                "temperature": 0.7,
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 5000,
            }
        )
        st.session_state.model = model
        st.session_state.agent_initialized = True
        return True
    except Exception as e:
        st.error(f"❌ Error initializing agent: {str(e)}")
        return False

# ============================================
# Chat Functions
# ============================================

def get_context() -> str:
    """Build conversation context from history"""
    if not st.session_state.chat_history:
        return ""
    
    context = "Previous conversation:\n"
    for msg in st.session_state.chat_history[-10:]:  # Last 5 exchanges
        context += f"{msg['role']}: {msg['content']}\n"
    return context

def get_agent_response(user_message: str, additional_context: str = "") -> str:
    """Get response from the agent"""
    try:
        # Build prompt with context
        context = get_context()
        
        # Add additional context from files or websites
        if additional_context:
            context += f"\n\nAdditional Context:\n{additional_context}\n"
        
        if context:
            prompt = f"{context}\nUser: {user_message}\nAssistant:"
        else:
            prompt = user_message
        
        # Generate response
        response = st.session_state.model.generate_content(prompt)
        return response.text
        
    except Exception as e:
        return f"❌ Error: {str(e)}"

def add_to_history(role: str, content: str, context: str = ""):
    """Add message to conversation history"""
    st.session_state.chat_history.append({
        "role": role,
        "content": content,
        "context": context,
        "timestamp": datetime.now().strftime("%H:%M:%S")
    })
    
    # Keep only recent history
    if len(st.session_state.chat_history) > AgentConfig.MAX_HISTORY * 2:
        st.session_state.chat_history = st.session_state.chat_history[-AgentConfig.MAX_HISTORY * 2:]

# ============================================
# Main App
# ============================================

# Header
st.title("🤖 AI Conversational Agent")
st.markdown("**Powered by using API** | 📁 Upload Files | 🔗 Paste Links")
st.markdown("---")

# Check if API key is provided
if not api_key:
    st.warning("⚠️ Please enter your API key in the sidebar to start chatting.")
    st.info("💡 Get your free API key from [Google AI Studio](https://makersuite.google.com/app/apikey)")
    st.stop()

# Initialize agent if not already done
if not st.session_state.agent_initialized:
    with st.spinner("🚀 Initializing AI agent..."):
        if initialize_agent(api_key):
            st.success("✅ I Am ready! let's Start chatting ...")
        else:
            st.stop()

# Display chat history
chat_container = st.container()

with chat_container:
    for message in st.session_state.chat_history:
        if message["role"] == "User":
            with st.chat_message("user"):
                st.markdown(message["content"])
                if message.get("context"):
                    with st.expander("📎 Attached Context"):
                        st.text(message["context"][:500] + "..." if len(message["context"]) > 500 else message["context"])
        else:
            with st.chat_message("assistant"):
                st.markdown(message["content"])

# File upload section ABOVE the chat input
col1, col2 = st.columns([0.4, 0.7])

with col1:
    uploaded_files_input = st.file_uploader(
        "📎",
        type=['pdf', 'docx', 'txt'],
        accept_multiple_files=True,
        label_visibility="collapsed",
        key="file_uploader"
    )
    
    if uploaded_files_input:
        st.session_state.temp_files = uploaded_files_input

with col2:
    # Show uploaded files
    if st.session_state.temp_files:
        file_names = [f.name for f in st.session_state.temp_files]
        st.info(f"📁 Files ready: {', '.join(file_names)}")

# Chat input
user_input = st.chat_input("🖥️:-Type your message here, paste a link, or upload files using 📎 button...")

if user_input:
    additional_context = ""
    
    # Check if input contains a URL
    if is_url(user_input.strip()):
        with st.spinner("🔍 Fetching website content..."):
            website_content = scrape_website(user_input.strip())
            additional_context += f"\n\nWebsite Content from {user_input}:\n{website_content}"
            st.info(f"📄 Fetched content from: {user_input}")
    
    # Process uploaded files from the upload button
    if st.session_state.temp_files:
        with st.spinner("📄 Processing uploaded files..."):
            for uploaded_file in st.session_state.temp_files:
                file_content = process_uploaded_file(uploaded_file)
                additional_context += f"\n\nFile: {uploaded_file.name}\n{file_content}\n"
            st.info(f"📁 Processed {len(st.session_state.temp_files)} file(s)")
    
    # Add user message to history
    add_to_history("User", user_input, additional_context)
    
    # Display user message
    with st.chat_message("user"):
        st.markdown(user_input)
        if additional_context:
            with st.expander("📎 Attached Context"):
                st.text(additional_context[:500] + "..." if len(additional_context) > 500 else additional_context)
    
    # Get and display agent response
    with st.chat_message("assistant"):
        with st.spinner("🤔 Thinking..."):
            response = get_agent_response(user_input, additional_context)
            st.markdown(response)
    
    # Add agent response to history
    add_to_history("Assistant", response)
    
    # Clear temp files after processing
    st.session_state.temp_files = []
    
    # Rerun to update chat display
    st.rerun()

# Footer
st.markdown("---")
st.caption("Built with Streamlit and API • Upload files using 📎 button or paste links to analyze content")