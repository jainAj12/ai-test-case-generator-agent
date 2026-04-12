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
# Best practice: Use st.secrets["GEMINI_API_KEY"] for deployment
API_KEY = "AIzaSyA6_ZLXJN-DGv2W9ceT9yJ4jD5qE717gLY" 
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash-lite')

# --- 2. APP CONFIG ---
st.set_page_config(page_title="AI Test Case Agent", page_icon="🧪", layout="wide")
st.title("🧪 Multimodal AI Test Case Generator")
st.markdown("Upload PRDs, Screenshots, or Links to generate comprehensive test suites.")

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
        
        name = uploaded_file.name
        
        # IMAGE HANDLING
        if name.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
            img = Image.open(uploaded_file)
            return img, "image"
            
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
            full_text = []
            for p in doc.paragraphs:
                if p.text.strip():
                    full_text.append(p.text)
            for table in doc.tables:
                for row in table.rows:
                    row_data = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                    if row_data:
                        full_text.append(" | ".join(row_data))
            final_text = "\n".join(full_text)
            return (final_text if final_text.strip() else "Error: Empty content detected."), "text"
        
        # EXCEL HANDLING
        elif name.endswith(('.xlsx', '.xls')):
            uploaded_file.seek(0) # Ensure we start at the beginning of the file
            engine = 'xlrd' if name.endswith('.xls') else 'openpyxl'
            try:
                df = pd.read_excel(uploaded_file, engine=engine)
            except Exception:
                # Fallback: sometimes openpyxl handles weirdly formatted xlsx better
                df = pd.read_excel(uploaded_file) 
            return f"Excel Content:\n{df.to_csv(index=False)}", "text"
            
    except Exception as e:
        return f"Error: {str(e)}", "error"

# --- 4. AI GENERATION LOGIC ---
def get_ai_test_cases(content, content_type):
    base_prompt = """
    You are a Senior QA Automation Engineer. 
    Analyze the provided requirements (Text, Excel Data, or Image) and create a professional test suite.
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
            "Upload PRD (PDF/Docx), Test Data (Excel), or UI Mockup (PNG/JPG)", 
            type=["pdf", "docx", "xlsx", "xls", "png", "jpg", "jpeg"]
        )
    else:
        url_input = st.text_input("Paste Requirement URL (Confluence/Wiki):")

# --- 6. EXECUTION ---
if st.button("Generate Test Cases 🚀"):
    if uploaded_file or url_input:
        with st.spinner("Extracting requirements..."):
            content, content_type = extract_content(uploaded_file, url_input)
            
        if content_type == "error":
            st.error(f"Failed to process file: {content}")
            if "xlrd" in content:
                st.info("💡 Run 'pip install xlrd' to support old .xls files.")
        elif content_type == "text" and len(str(content)) < 15:
            st.warning("⚠️ The extracted content seems too short. Please check your file.")
        else:
            # Layout for Preview and Results
            col1, col2 = st.columns([1, 1])
            
            with col1:
                st.subheader("Input Preview")
                if content_type == "image":
                    st.image(content, use_container_width=True)
                else:
                    st.text_area("Extracted Requirements", content, height=400)
            
            with col2:
                st.subheader("AI Generated Test Suite")
                with st.spinner("Writing test cases..."):
                    test_suite = get_ai_test_cases(content, content_type)
                    st.markdown(test_suite)
                    st.download_button(
                        label="Download Test Suite",
                        data=test_suite,
                        file_name="ai_generated_test_suite.txt",
                        mime="text/plain"
                    )
    else:
        st.warning("Please provide a file or a valid URL first.")
