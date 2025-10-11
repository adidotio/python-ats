from dotenv import load_dotenv
load_dotenv()

import streamlit as st
import os
from PIL import Image
import pdf2image
import google.generativeai as genai
import io
import base64

# ---------------------- API KEY ----------------------
if os.getenv("GOOGLE_API_KEY"):
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
elif os.getenv("GENERAL_API_KEY"):
    genai.configure(api_key=os.getenv("GENERAL_API_KEY"))
else:
    st.error("🚨 Neither GOOGLE_API_KEY nor GENERAL_API_KEY found! API functions will not work.")

POPPLER_PATH = r"C:\Release-25.07.0-0\poppler-25.07.0\Library\bin"

# ---------------------- CACHED FUNCS ----------------------
@st.cache_data(show_spinner="Running AI Analysis...")
def get_gemini_response(input_prompt, pdf_content, context_text):
    model = genai.GenerativeModel('gemini-2.5-flash')
    resp = model.generate_content([input_prompt, pdf_content[0], context_text])
    return resp.text

@st.cache_data(show_spinner="Processing resume PDF...")
def input_pdf_setup(uploaded_file, poppler_path):
    if not uploaded_file:
        return None
    uploaded_file.seek(0)
    images = pdf2image.convert_from_bytes(uploaded_file.read(), poppler_path=poppler_path)
    first_page = images[0]
    if first_page.mode != 'RGB':
        first_page = first_page.convert('RGB')
    buf = io.BytesIO()
    first_page.save(buf, format="JPEG")
    img_b64 = base64.b64encode(buf.getvalue()).decode()
    return [{"mime_type": "image/jpeg", "data": img_b64}]

def get_chat_response(user_query, pdf_content, context_text=None):
    model = genai.GenerativeModel('gemini-2.5-flash')
    parts = []
    if pdf_content:
        parts.append("You are a helpful HR expert assistant. Analyze the provided resume (PDF image) and the job description (if present).")
        parts.append(pdf_content[0])
        if context_text and context_text.strip():
            parts.append(f"The associated Job Description is: {context_text}")
    else:
        parts.append("You are a general career and resume advice assistant. No document is uploaded.")
    parts.append(user_query)
    return model.generate_content(parts).text

# ---------------------- APP ----------------------
st.set_page_config(page_title="ATS Resume Parser", layout="wide", initial_sidebar_state="collapsed")

st.title("🤖 Intelligent ATS Resume Parser")
st.divider()

if 'chat_messages' not in st.session_state: st.session_state['chat_messages'] = []
if 'chat_open' not in st.session_state: st.session_state['chat_open'] = False
if 'pdf_content_for_chat' not in st.session_state: st.session_state['pdf_content_for_chat'] = None

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("📄 Upload Resume")
    uploaded_file = st.file_uploader("Choose a PDF file...", type=["pdf"], key="pdf_uploader")
    if uploaded_file:
        st.success("✅ PDF uploaded successfully! Ready to analyze.")
        st.markdown(f"**File:** `{uploaded_file.name}`")
        st.markdown(f"**Size:** `{uploaded_file.size / 1024:.2f} KB`")
    else:
        st.info("📤 Please upload your resume to begin.")

with col2:
    st.subheader("💼 Job Description")
    input_text = st.text_area(
        "Paste the Job Description (JD) here:",
        height=280,
        key="input_jd",
        placeholder="Paste the full job description text here...\n\nExample:\n- Position: Senior Software Engineer\n- Requirements: 5+ years Python, React...\n- Responsibilities: Lead development team..."
    )
    if input_text.strip():
        st.caption(f"📝 Word count: {len(input_text.split())}")

st.divider()

st.subheader("🎯 Select Analysis Type")
st.caption("Choose an analysis method to evaluate the resume against the job description")

btn_col1, btn_col2, _, btn_col4 = st.columns([1, 1, 1, 1])
submit3 = btn_col1.button("🔥 Match Score", type="primary", use_container_width=True)
submit1 = btn_col2.button("🧑‍💼 HR Review", use_container_width=True)

def toggle_chat():
    st.session_state['chat_open'] = not st.session_state['chat_open']
    if st.session_state['chat_open'] and not st.session_state['chat_messages']:
        st.session_state['chat_messages'].append({
            "role": "assistant",
            "content": ("Hello! 👋 I'm your AI Career Assistant. Ask me questions about your uploaded resume, "
                        "the job description, or general career advice!\n\n**Example questions:**\n"
                        "- What are the candidate's core skills?\n- How can I improve this resume?\n"
                        "- Does the experience match the job requirements?")
        })

btn_col4.button("💬 Chat Assistant", on_click=toggle_chat, key="chat_button", use_container_width=True)

st.markdown("---")
result_placeholder = st.empty()

input_prompt_hr = (
    "You are an experienced HR with tech experience. Review the resume against the job description. "
    "Provide strengths, weaknesses, and recommendations."
)
input_prompt_ats = (
    "You are a skilled ATS scanner. Evaluate the resume against the job description. "
    "Provide a percentage match score and matched/missing keywords."
)

if submit1 or submit3:
    st.session_state['chat_open'] = False
    st.session_state['chat_messages'] = []
    if not uploaded_file or not input_text.strip():
        st.error("🚨 Please upload a resume PDF and paste a Job Description before running the analysis.")
    else:
        prompt = input_prompt_hr if submit1 else input_prompt_ats
        title = "📊 Professional HR Review" if submit1 else "🎯 ATS Match Results"
        with st.spinner('🔍 Analyzing resume...'):
            try:
                pdf_content = input_pdf_setup(uploaded_file, POPPLER_PATH)
                st.session_state['pdf_content_for_chat'] = pdf_content
                resp = get_gemini_response(prompt, pdf_content, input_text)
                with result_placeholder.expander(f"**{title}**", expanded=True):
                    st.markdown(resp)
                    st.success("✅ Analysis completed successfully!")
            except Exception as e:
                st.error(f"❌ An error occurred during processing: {e}")

if st.session_state['chat_open']:
    with result_placeholder.container():
        st.subheader("💬 Interactive AI Assistant")
        st.caption("Ask questions about the resume, job description, or get career advice")
        for m in st.session_state['chat_messages']:
            with st.chat_message(m["role"]):
                st.markdown(m["content"])
        user_q = st.chat_input("💭 Ask me anything about the resume or career advice...")
        if user_q:
            st.session_state['chat_messages'].append({"role": "user", "content": user_q})
            with st.chat_message("user"): st.markdown(user_q)
            with st.chat_message("assistant"):
                with st.spinner("🤔 Thinking..."):
                    try:
                        pdf_content = st.session_state['pdf_content_for_chat']
                        jd = st.session_state.get('input_jd', '')
                        ans = get_chat_response(user_q, pdf_content, jd)
                        st.markdown(ans)
                        st.session_state['chat_messages'].append({"role": "assistant", "content": ans})
                    except Exception as e:
                        msg = f"❌ Sorry, an error occurred: {e}"
                        st.error(msg)
                        st.session_state['chat_messages'].append({"role": "assistant", "content": msg})

