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
# Using your provided key directly
API_KEY = "AIzaSyALBNm1sHxTg5u2bkaHJhw6yveI5DVGoGQ" 
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash-lite')

# --- 2. APP CONFIG ---
st.set_page_config(page_title="AI Test Case Agent", page_icon="🧪", layout="wide")
st.title("🧪 Multimodal AI Test Case Generator")
st.markdown("Upload requirements (PDF, Word, Excel, or Images) or paste a URL to generate test suites.")

# --- 3. EXTRACTION LOGIC ---
def extract_content(uploaded_file, url_input=None):
    try:
        # URL Logic
        if url_input:
            res = requests.get(url_input, timeout=10)
            res.raise_for_status()
            soup = BeautifulSoup(res.text, 'html.parser')
            for element in soup(['script', 'style', 'nav', 'footer']):
                element.decompose()
            return soup.get_text(separator='\n', strip=True), "text"
        
        if uploaded_file:
            name = uploaded_file.name
            
            # IMAGE HANDLING
            if name.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                return Image.open(uploaded_file), "image"
                
            # PDF HANDLING
            elif name.endswith('.pdf'):
                with open("temp.pdf", "wb") as f:
                    f.write(uploaded_file.getbuffer())
                text = pymupdf4llm.to_markdown("temp.pdf")
                os.remove("temp.pdf")
                return text, "text"
            
            # WORD HANDLING
            elif name.endswith('.docx'):
                doc = Document(uploaded_file)
                full_text = [p.text for p in doc.paragraphs if p.text.strip()]
                for table in doc.tables:
                    for row in table.rows:
                        row_data = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                        if row_data:
                            full_text.append(" | ".join(row_data))
                return "\n".join(full_text), "text"
            
            # EXCEL HANDLING
            elif name.endswith(('.xlsx', '.xls')):
                engine = 'xlrd' if name.endswith('.xls') else 'openpyxl'
                df = pd.read_excel(uploaded_file, engine=engine)
                return f"Excel Content:\n{df.to_csv(index=False)}", "text"
                
    except Exception as e:
        return f"Error: {str(e)}", "error"

# --- 4. AI GENERATION LOGIC ---
def get_ai_test_cases(content, content_type):
    base_prompt = """
    You are a Senior QA Automation Engineer. 
    Analyze the provided requirements and create a professional test suite.
    Include: Functional, Negative, Security, and Edge cases.
    
    Format:
    - **Test ID:** [ID]
    - **Title:** [Description]
    - **Priority:** [P0/P1/P2]
    - **Steps:** 1, 2, 3...
    - **Expected Result:** [Outcome]
    """
    try:
        if content_type == "image":
            response = model.generate_content([base_prompt, content])
        else:
            response = model.generate_content(f"{base_prompt}\n\nRequirements Content:\n{content}")
        return response.text
    except Exception as e:
        return f"AI Error: {str(e)}"

# --- 5. UI LAYOUT ---
with st.sidebar:
    st.header("Settings")
    source_type = st.radio("Source Selection:", ["File Upload", "URL Link"])
    
    uploaded_file = None
    url_input = None

    if source_type == "File Upload":
        uploaded_file = st.file_uploader(
            "Upload PRD (PDF/Docx), Test Data (Excel), or UI Mockup", 
            type=["pdf", "docx", "xlsx", "xls", "png", "jpg", "jpeg"]
        )
    else:
        url_input = st.text_input("Paste Requirement URL (e.g., Confluence):")

# --- 6. EXECUTION ---
if st.button("Generate Test Cases 🚀"):
    if uploaded_file or url_input:
        with st.spinner("Processing requirements..."):
            content, content_type = extract_content(uploaded_file, url_input)
            
        if content_type == "error":
            st.error(f"Failed to process: {content}")
        else:
            col1, col2 = st.columns([1, 1])
            
            with col1:
                st.subheader("Input Preview")
                if content_type == "image":
                    st.image(content, use_container_width=True)
                else:
                    st.text_area("Extracted Requirements", content, height=400)
            
            with col2:
                st.subheader("AI Generated Test Suite")
                test_suite = get_ai_test_cases(content, content_type)
                st.markdown(test_suite)
                st.download_button(
                    label="Download Test Suite",
                    data=test_suite,
                    file_name="test_suite.txt",
                    mime="text/plain"
                )
    else:
        st.warning("Please provide a file or URL first.")
