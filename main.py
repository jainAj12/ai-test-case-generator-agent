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
API_KEY = "AIzaSyBB3QEy8csYS7RTIj0Qk6Gs_BrVjYWDFkg"
genai.configure(api_key=API_KEY)
# Using the stable 2026 workhorse model
model = genai.GenerativeModel('gemini-2.5-flash-lite')

# --- 2. APP CONFIG ---
st.set_page_config(page_title="AI Test Case Agent", page_icon="🧪", layout="wide")
st.title("🧪 Multimodal AI Test Case Generator")
st.markdown("Upload PRDs, Screenshots, or Links to generate comprehensive test suites.")

# --- 3. UPDATED EXTRACTION LOGIC ---
def extract_content(uploaded_file, url_input=None):
    try:
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
            
        # PDF HANDLING (Aggressive Markdown)
        elif name.endswith('.pdf'):
            with open("temp.pdf", "wb") as f:
                f.write(uploaded_file.getbuffer())
            # Use PyMuPDF4LLM for better structural extraction
            text = pymupdf4llm.to_markdown("temp.pdf")
            os.remove("temp.pdf")
            return text, "text"
        
        # WORD HANDLING (Deep Table Search)
        elif name.endswith('.docx'):
            doc = Document(uploaded_file)
            full_text = []
            
            # 1. Check standard paragraphs
            for p in doc.paragraphs:
                if p.text.strip():
                    full_text.append(p.text)
            
            # 2. Check Tables (Crucial for PRDs!)
            for table in doc.tables:
                for row in table.rows:
                    row_data = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                    if row_data:
                        full_text.append(" | ".join(row_data))
            
            final_text = "\n".join(full_text)
            return (final_text if final_text.strip() else "Error: Empty content detected."), "text"
        
        # EXCEL HANDLING
        elif name.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(uploaded_file)
            return "Excel Data:\n" + df.to_csv(index=False), "text"
            
    except Exception as e:
        return f"Error: {str(e)}", "error"

# --- 4. AI GENERATION LOGIC ---
def get_ai_test_cases(content, content_type):
    base_prompt = """
    You are a Senior QA Automation Engineer. 
    Analyze the provided requirements (Text or Image) and create a test suite.
    Include: Functional, Negative, and Edge cases.
    
    Format:
    - **Test ID:** [ID]
    - **Title:** [Description]
    - **Priority:** [P0/P1/P2]
    - **Steps:** 1, 2, 3...
    - **Expected Result:** [Outcome]
    """
    try:
        if content_type == "image":
            # Multi-modal call
            response = model.generate_content([base_prompt, content])
        else:
            response = model.generate_content(f"{base_prompt}\n\nRequirements:\n{content}")
        return response.text
    except Exception as e:
        return f"AI Error: {str(e)}"

# --- 5. UI LAYOUT ---
with st.sidebar:
    st.header("Settings")
    source_type = st.radio("Source:", ["File Upload", "URL Link"])
    uploaded_file = None
    url_input = None

    if source_type == "File Upload":
        uploaded_file = st.file_uploader(
            "Upload Doc (PDF/Docx) or UI Image (PNG/JPG)", 
            type=["pdf", "docx", "xlsx", "png", "jpg", "jpeg"]
        )
    else:
        url_input = st.text_input("Paste URL:")

# --- 6. EXECUTION ---
if st.button("Generate Test Cases 🚀"):
    if uploaded_file or url_input:
        with st.spinner("Processing..."):
            content, content_type = extract_content(uploaded_file, url_input)
            
        if content_type == "error":
            st.error(content)
        elif content_type == "text" and len(str(content)) < 10:
            st.warning("⚠️ No readable text found. If this is a scanned PDF or a UI mockup, please save it as an IMAGE (PNG/JPG) and upload again!")
        else:
            # Preview
            if content_type == "image":
                st.image(content, caption="Requirement Image", width=600)
            else:
                with st.expander("Show Extracted Text"):
                    st.text(content)
            
            # AI Call
            with st.spinner("Writing Test Cases..."):
                test_suite = get_ai_test_cases(content, content_type)
                st.divider()
                st.markdown(test_suite)
                st.download_button("Download TXT", test_suite, file_name="test_cases.txt")
    else:
        st.warning("Provide a file or link.")
