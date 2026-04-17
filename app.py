# app.py
import streamlit as st
import uuid
from pathlib import Path
from langchain_core.messages import HumanMessage
from backend import app
from utils import parse_pdf_to_text, parse_docx_to_text

st.set_page_config(page_title="Groovia", layout="centered")

LOGO_PATH = r"assets/Immigroov_Transparent_Logo.png"

with st.sidebar:
    if Path(LOGO_PATH).exists():
        st.image(LOGO_PATH, use_container_width=True)
    st.markdown("---")
    if st.button("Clear Chat & Restart"):
        st.session_state.clear()
        st.rerun()

st.title("Groovia")
st.subheader("Immigroov's Virtual Assistant")

if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Welcome! Please attach your resume to begin."}]
if "resume_uploaded" not in st.session_state:
    st.session_state.resume_uploaded = False

config = {"configurable": {"thread_id": st.session_state.thread_id}}

def extract_content(msg) -> str:
    content = getattr(msg, "content", msg)
    if isinstance(content, list):
        return " ".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text").strip()
    return str(content).strip() if content else ""

col1, col2 = st.columns([1, 4])
with col1:
    with st.popover("📎 Attach"):
        uploaded_file = st.file_uploader("Upload Resume", type=["pdf", "docx"])

# IN-MEMORY PROCESSING BLOCK
if uploaded_file and not st.session_state.resume_uploaded:
    file_bytes = uploaded_file.getvalue()
    file_ext = Path(uploaded_file.name).suffix.lower()
    
    with st.spinner("Extracting content..."):
        resume_text = parse_pdf_to_text(file_bytes) if file_ext == ".pdf" else parse_docx_to_text(file_bytes)
    
    inputs = {"messages": [HumanMessage(content="Analyze my resume.")], "resume_text": resume_text, "revision_count": 0}
    
    with st.spinner("Analyzing..."):
        for event in app.stream(inputs, config): pass
        state = app.get_state(config)
        res = extract_content(state.values["messages"][-1])
        st.session_state.messages.append({"role": "assistant", "content": res})
        st.session_state.resume_uploaded = True
        st.rerun()

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Ask about your career..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("Consulting..."):
            for event in app.stream({"messages": [HumanMessage(content=prompt)]}, config): pass
            state = app.get_state(config)
            ans = extract_content(state.values["messages"][-1])
            st.markdown(ans)
            st.session_state.messages.append({"role": "assistant", "content": ans})