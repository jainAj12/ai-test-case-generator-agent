import streamlit as st
import pandas as pd
from docx import Document
import pymupdf4llm
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import os
from PIL import Image
import io

# --- 1. AI CONFIGURATION ---
API_KEY = "AIzaSyA6_ZLXJN-DGv2W9ceT9yJ4jD5qE717gLY" 
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash-lite')

# --- 2. APP CONFIG ---
st.set_page_config(page_title="AI Test Case Agent", page_icon="🧪", layout="wide")
st.title("🧪 Multimodal AI Test Case Generator")

# --- 3. EXTRACTION LOGIC ---
def extract_content(uploaded_file, camera_photo, url_input):
    try:
        # 1. URL Logic
        if url_input:
            res = requests.get(url_input, timeout=10)
            res.raise_for_status()
            soup = BeautifulSoup(res.text, 'html.parser')
            for element in soup(['script', 'style', 'nav', 'footer']):
                element.decompose()
            return soup.get_text(separator='\n', strip=True), "text"
        
        # 2. Camera Logic (Mobile Scanner)
        if camera_photo:
            img = Image.open(camera_photo)
            return img, "image"

        # 3. File Upload Logic
        if uploaded_file:
            name = uploaded_file.name
            
            if name.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                return Image.open(uploaded_file), "image"
                
            elif name.endswith('.pdf'):
                with open("temp.pdf", "wb") as f:
                    f.write(uploaded_file.getbuffer())
                text = pymupdf4llm.to_markdown("temp.pdf")
                os.remove("temp.pdf")
                return text, "text"
            
            elif name.endswith('.docx'):
                doc = Document(uploaded_file)
                full_text = [p.text for p in doc.paragraphs if p.text.strip()]
                for table in doc.tables:
                    for row in table.rows:
                        full_text.append(" | ".join([cell.text.strip() for cell in row.cells]))
                return "\n".join(full_text), "text"
            
            elif name.endswith(('.xlsx', '.xls')):
                engine = 'xlrd' if name.endswith('.xls') else 'openpyxl'
                df = pd.read_excel(uploaded_file, engine=engine)
                return f"Excel Data:\n{df.to_csv(index=False)}", "text"
                
    except Exception as e:
        return f"Error: {str(e)}", "error"

# --- 4. AI GENERATION LOGIC ---
def get_ai_test_cases(content, content_type):
    base_prompt = """
    You are a Senior QA Automation Engineer. Analyze the requirements and create a professional test suite.
    Include: Functional, Negative, Security, and Edge cases.
    Format: ID, Title, Priority, Steps, Expected Result.
    """
    try:
        if content_type == "image":
            response = model.generate_content([base_prompt, content])
        else:
            response = model.generate_content(f"{base_prompt}\n\nRequirements:\n{content}")
        return response.text
    except Exception as e:
        return f"AI Error: {str(e)}"

# --- 5. UI LAYOUT ---
with st.sidebar:
    st.header("Input Method")
    source_type = st.radio("Choose Source:", ["Camera Scanner 📸", "File Upload 📁", "URL Link 🔗"])
    
    uploaded_file = None
    camera_photo = None
    url_input = None

    if source_type == "Camera Scanner 📸":
        st.info("Perfect for scanning whiteboards or printed PRDs.")
        camera_photo = st.camera_input("Take a photo of the requirement")
    elif source_type == "File Upload 📁":
        uploaded_file = st.file_uploader("Upload PDF, Docx, or Image", type=["pdf", "docx", "xlsx", "xls", "png", "jpg"])
    else:
        url_input = st.text_input("Paste Confluence/Jira URL:")

# --- 6. EXECUTION ---
if st.button("Generate Test Cases 🚀"):
    if uploaded_file or camera_photo or url_input:
        with st.spinner("Processing input..."):
            content, content_type = extract_content(uploaded_file, camera_photo, url_input)
            
        if content_type == "error":
            st.error(content)
        else:
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("Captured Content")
                if content_type == "image":
                    st.image(content, use_container_width=True)
                else:
                    st.text_area("Extracted Text", content, height=300)
            
            with col2:
                st.subheader("AI Generated Suite")
                test_suite = get_ai_test_cases(content, content_type)
                st.markdown(test_suite)
                st.download_button("Download TXT", test_suite, "test_cases.txt")
    else:
        st.warning("Please provide an input first!")
