from dotenv import load_dotenv
load_dotenv()

import streamlit as st
import os
import io
import base64
from PIL import Image 
import pdf2image
import google.generativeai as genai

# --- Configuration ---
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# Add Poppler path for environments that require it (like Windows)
POPPLER_PATH = r"C:\Release-25.07.0-0\poppler-25.07.0\Library\bin" 

# --- Helper Functions ---

# Caching the LLM response to speed up repeated analysis with the same input
@st.cache_data(show_spinner="⏳ Analyzing with AI...")
def get_gemini_response(input_prompt, pdf_content, context_text):
    model = genai.GenerativeModel('gemini-2.5-flash') 
    response = model.generate_content([input_prompt, pdf_content[0], context_text])
    return response.text

# Uncached function for dynamic chat conversations
def get_chat_response(user_query, pdf_content, context_text=None):
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    content_parts = []
    
    if pdf_content and len(pdf_content) > 0:
        hr_system_prompt = "You are a helpful HR expert and career assistant. Analyze the provided resume (PDF image) and the job description (if present) to answer the user's query about the candidate's skills, experience, or role suitability. You can also answer general career questions."
        content_parts.append(hr_system_prompt)
        content_parts.append(pdf_content[0])
        
        if context_text and context_text.strip():
            content_parts.append(f"The associated Job Description for context is: {context_text}")
    else:
        general_system_prompt = "You are a general career and resume advice assistant. Please answer the user's query with helpful advice on topics like trending job roles or general career improvements. Since no document is uploaded, answer based on general knowledge."
        content_parts.append(general_system_prompt)
        
    content_parts.append(user_query)
    
    response = model.generate_content(content_parts)
    return response.text


# Caching the PDF processing (crucial for quick UI response)
@st.cache_data(show_spinner="⚙️ Preparing resume file...")
def input_pdf_setup(uploaded_file, poppler_path):
    if uploaded_file is not None:
        uploaded_file.seek(0)
        
        if poppler_path:
            images = pdf2image.convert_from_bytes(uploaded_file.read(), poppler_path=poppler_path)
        else:
            images = pdf2image.convert_from_bytes(uploaded_file.read())

        first_page = images[0]

        img_byte_arr = io.BytesIO()
        if first_page.mode != 'RGB':
            first_page = first_page.convert('RGB')
        first_page.save(img_byte_arr, format='JPEG')
        img_byte_arr = img_byte_arr.getvalue()

        pdf_parts = [
            {
                "mime_type": "image/jpeg",
                "data": base64.b64encode(img_byte_arr).decode() 
            }
        ]
        return pdf_parts
    else:
        return None

# --- Streamlit App ---

st.set_page_config(
    page_title="ATS Resume Expert",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- Session State Initialization for Chat ---
if 'chat_messages' not in st.session_state:
    st.session_state['chat_messages'] = []
if 'chat_open' not in st.session_state:
    st.session_state['chat_open'] = False
if 'pdf_content_for_chat' not in st.session_state:
    st.session_state['pdf_content_for_chat'] = None
# --- End Session State Initialization ---


# 1. Title and Description
st.title("🤖 Intelligent ATS Resume Scanner")
st.caption("Maximize your job application success with AI-powered resume analysis.")
st.markdown("---")
st.subheader("Match Your Resume to the Job Description")

# 2. Input Section
col_file, col_jd = st.columns([1, 2]) 

with col_file:
    st.markdown("#### 📄 Upload Resume (PDF)")
    uploaded_file = st.file_uploader(
        "Choose a PDF file...", 
        type=["pdf"], 
        key="pdf_uploader",
        label_visibility="collapsed" 
    )
    
    if uploaded_file is not None:
        st.success(f"✅ **{uploaded_file.name}** Uploaded Successfully!")
    else:
        st.info("⬆️ **Upload your resume** to start the analysis.")

with col_jd:
    st.markdown("#### 💼 Job Description")
    input_text = st.text_area(
        "Paste the Job Description here:", 
        key="input_jd",
        height=300, 
        placeholder="Paste the full job description text here..."
    )

st.divider()

# 3. Action Buttons Section
st.markdown("#### 🚀 Select Analysis Type")
btn_col1, btn_col2, btn_col3, btn_col4, btn_col_spacer = st.columns([1, 1, 1, 1, 1])

submit1 = btn_col1.button("🧑‍💼 HR Review", use_container_width=True)
submit3 = btn_col2.button("🔥 Percentage Match", type="primary", use_container_width=True)
submit_improve = btn_col3.button("📈 Improvements", use_container_width=True)

# NEW Chat Button Logic
def toggle_chat():
    if not st.session_state['chat_open'] and uploaded_file is None:
        st.error("🚨 Please upload a resume PDF first to start the chat assistant.")
        return 

    st.session_state['chat_open'] = not st.session_state['chat_open']
    if st.session_state['chat_open'] and st.session_state['chat_messages'] == []:
        initial_message = "Hello! 👋 I'm your **AI Career Assistant**. Ask me questions about your uploaded documents or get general career advice.\n\n**Example questions:**\n- What are the candidate's core skills?\n- How can I improve this resume?\n- What are the trending job roles in 2025?"
        st.session_state['chat_messages'].append({"role": "assistant", "content": initial_message})

submit_chat = btn_col4.button("💬 Chat with AI", on_click=toggle_chat, use_container_width=True)


# 4. Output Placeholder
result_placeholder = st.empty()

# --- Prompts ---
input_prompt1 = """
You are an experienced Technical Human Resource Manager,your task is to review the provided resume against the job description. 
Please share your professional evaluation on whether the candidate's profile aligns with the role. 
Highlight the strengths and weaknesses of the applicant in relation to the specified job requirements.
"""

input_prompt3 = """
You are an skilled ATS (Applicant Tracking System) scanner with a deep understanding of data science and ATS functionality, 
your task is to evaluate the resume against the provided job description. give me the percentage of match if the resume matches
the job description. First the output should come as percentage and then keywords missing and last final thoughts.
"""

input_prompt_improve = """
You are an expert career consultant and ATS specialist. Your task is to analyze the user's resume and the provided job description. 
Based on the gap between the candidate's profile and the job requirements, provide detailed, actionable recommendations for improvement.

Your response must be structured clearly, covering these three areas:
1. **Resume Content & Formatting Improvements:** Suggest specific changes to the resume (e.g., adding project details, quantifying achievements, changing section names) to align better with ATS and HR expectations for this role.
2. **Skill & Experience Gap Closure:** Identify 2-3 specific skills (technical or soft) mentioned in the job description that are missing or weak in the resume. Suggest concrete ways the candidate can acquire or demonstrate these skills (e.g., courses, projects, certifications).
3. **ATS Keyword Optimization:** List the top 5 essential keywords from the Job Description that the resume should integrate more prominently to increase the ATS match score.
"""


# --- Logic for Button Clicks (Main Analysis) ---

if submit1 or submit3 or submit_improve:
    # Close chat interface when a main analysis button is pressed
    st.session_state['chat_open'] = False
    st.session_state['chat_messages'] = []

    if uploaded_file is None or not input_text.strip():
        result_placeholder.error("🚨 **Error:** Please upload a **resume PDF** and paste a **Job Description** before running the analysis.")
        
    else:
        # Determine the correct prompt and title based on the clicked button
        if submit1:
            current_prompt = input_prompt1
            analysis_title = "🧑‍💼 Professional HR Review"
        elif submit3:
            current_prompt = input_prompt3
            analysis_title = "🔥 ATS Match Results"
        elif submit_improve:
            current_prompt = input_prompt_improve
            analysis_title = "📈 Resume Improvement Plan"
        
        # Use a Streamlit spinner for the entire process
        with st.spinner(f"**Analyzing resume for {analysis_title}...**") :
            try:
                # Setup PDF content (will use cache if same file)
                pdf_content = input_pdf_setup(uploaded_file, POPPLER_PATH)
                
                # Store PDF content for the chat feature
                st.session_state['pdf_content_for_chat'] = pdf_content

                # Get Gemini response (will use cache if same inputs)
                response = get_gemini_response(current_prompt, pdf_content, input_text)
                
                # Display results using an expander for clean presentation
                with result_placeholder.expander(f"**{analysis_title}**", expanded=True):
                    st.markdown(response)
                    st.success(f"✅ **{analysis_title}** completed successfully!")

            except Exception as e:
                # Catch specific Poppler error if path is wrong, or API error
                st.error(f"❌ **An Error Occurred During Analysis!** Details: {e}")

# --- Chat Functionality Logic ---
if st.session_state['chat_open']:
    
    with result_placeholder.container():
        st.markdown("### 💬 Interactive AI Assistant")
        st.caption("Ask questions about the resume, job description, or general career advice.")
        st.markdown("---")
        
        # 1. Display chat messages from history
        for message in st.session_state['chat_messages']:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        # 2. Handle user input
        user_query = st.chat_input("💭 Ask me anything about the documents or career advice...")

        if user_query:
            st.session_state['chat_messages'].append({"role": "user", "content": user_query})
            with st.chat_message("user"):
                st.markdown(user_query)
            
            with st.chat_message("assistant"):
                with st.spinner("🤔 **Thinking...**"):
                    try:
                        pdf_content = st.session_state['pdf_content_for_chat']
                        current_jd = st.session_state.get('input_jd', '')
                        
                        assistant_response = get_chat_response(
                            user_query, 
                            pdf_content, 
                            current_jd
                        )
                        
                        st.markdown(assistant_response)
                        st.session_state['chat_messages'].append({"role": "assistant", "content": assistant_response})
                        
                    except Exception as e:
                        error_msg = f"❌ **Sorry, an error occurred:** {e}"
                        st.error(error_msg)
                        st.session_state['chat_messages'].append({"role": "assistant", "content": error_msg})
