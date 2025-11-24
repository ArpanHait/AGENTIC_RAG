"""
Simple Conversational AI Agent with Streamlit
Chat with Google Gemini - Deploy anywhere!
"""

import streamlit as st
import google.generativeai as genai
from datetime import datetime
import os

# ============================================
# Configuration
# ============================================

class AgentConfig:
    """Configuration for the AI agent"""
    GEMINI_MODEL = "gemini-2.5-flash-preview-09-2025"
    MAX_HISTORY = 10 

# ============================================
# Page Configuration
# ============================================

st.set_page_config(
    page_title="AI Conversational Agent",
    page_icon="🤖",
    layout="centered",
    initial_sidebar_state="expanded"
)

# ============================================
# Initialize Session State
# ============================================

if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

if 'agent_initialized' not in st.session_state:
    st.session_state.agent_initialized = False

if 'model' not in st.session_state:
    st.session_state.model = None

# ============================================
# Sidebar - API Key Configuration
# ============================================

with st.sidebar:
    st.title("⚙️ Configuration:")
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
    if st.button("🗑️ Clear Conversation", use_container_width=True):
        st.session_state.chat_history = []
        st.rerun()
    
    st.markdown("---")
    
    # Instructions
    st.subheader("📖 Instructions")
    st.markdown("""
    1. Enter your Google API key above
    2. Start chatting with the AI agent
    3. The agent remembers context
    4. Click 'Clear' to reset conversation
    """)
    
    st.markdown("---")
    st.caption("💡 Get API key: [Google AI Studio](https://makersuite.google.com/app/apikey)")

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

def get_agent_response(user_message: str) -> str:
    """Get response from the agent"""
    try:
        # Build prompt with context
        context = get_context()
        
        if context:
            prompt = f"{context}\nUser: {user_message}\nAssistant:"
        else:
            prompt = user_message
        
        # Generate response
        response = st.session_state.model.generate_content(prompt)
        return response.text
        
    except Exception as e:
        return f"❌ Error: {str(e)}"

def add_to_history(role: str, content: str):
    """Add message to conversation history"""
    st.session_state.chat_history.append({
        "role": role,
        "content": content,
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
st.markdown("**Powered by using API**")
st.markdown("---")

# Check if API key is provided
if not api_key:
    st.warning("⚠️ Please enter your Google API key in the sidebar to start chatting.")
    st.info("💡 Get your free API key from [Google AI Studio](https://makersuite.google.com/app/apikey)")
    st.stop()

# Initialize agent if not already done
if not st.session_state.agent_initialized:
    with st.spinner("🚀 Initializing AI agent..."):
        if initialize_agent(api_key):
            st.success("✅ Agent ready! Start chatting ...")
        else:
            st.stop()

# Display chat history
chat_container = st.container()

with chat_container:
    for message in st.session_state.chat_history:
        if message["role"] == "User":
            with st.chat_message("user"):
                st.markdown(message["content"])
        else:
            with st.chat_message("assistant"):
                st.markdown(message["content"])

# Chat input
user_input = st.chat_input("🖥️:-Type your message here...")

if user_input:
    # Add user message to history
    add_to_history("User", user_input)
    
    # Display user message
    with st.chat_message("user"):
        st.markdown(user_input)
    
    # Get and display agent response
    with st.chat_message("assistant"):
        with st.spinner("🤔 Thinking..."):
            response = get_agent_response(user_input)
            st.markdown(response)
    
    # Add agent response to history
    add_to_history("Assistant", response)
    
    # Rerun to update chat display
    st.rerun()

# Footer
st.markdown("---")
st.caption("Built with Streamlit and API • Deploy on Streamlit Cloud")