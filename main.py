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
st.markdown("Upload requirements or paste a URL to generate test suites in a tabular format.")

# --- 3. EXTRACTION LOGIC ---
def extract_content(uploaded_file, url_input=None):
    try:
        if url_input:
            res = requests.get(url_input, timeout=10)
            res.raise_for_status()
            soup = BeautifulSoup(res.text, 'html.parser')
            for element in soup(['script', 'style', 'nav', 'footer']):
                element.decompose()
            return soup.get_text(separator='\n', strip=True), "text"
        
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
                return "\n".join(full_text), "text"
            elif name.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(uploaded_file)
                return f"Excel Data:\n{df.to_csv(index=False)}", "text"
    except Exception as e:
        return f"Error: {str(e)}", "error"

# --- 4. AI GENERATION LOGIC (Updated for Tables) ---
def get_ai_test_cases(content, content_type):
    # Strict prompt to force Markdown Table output
    base_prompt = """
    You are a Senior QA Automation Engineer. 
    Analyze the provided requirements and create a comprehensive test suite.
    
    IMPORTANT: You must output the results ONLY as a Markdown Table with the following columns:
    | Test ID | Title | Priority | Pre-conditions | Steps | Expected Result | Type (Functional/Negative/Edge) |
    
    Ensure all scenarios including security and boundary value analysis are covered.
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
    st.header("Settings")
    source_type = st.radio("Source Selection:", ["File Upload", "URL Link"])
    uploaded_file = None
    url_input = None

    if source_type == "File Upload":
        uploaded_file = st.file_uploader("Upload PRD or UI Mockup", type=["pdf", "docx", "xlsx", "xls", "png", "jpg"])
    else:
        url_input = st.text_input("Paste Requirement URL:")

# --- 6. EXECUTION ---
if st.button("Generate Test Table 🚀"):
    if uploaded_file or url_input:
        with st.spinner("Analyzing requirements..."):
            content, content_type = extract_content(uploaded_file, url_input)
            
        if content_type == "error":
            st.error(content)
        else:
            test_suite = get_ai_test_cases(content, content_type)
            
            st.subheader("📝 Generated Test Suite Table")
            st.markdown(test_suite)
            
            # Allow downloading as a CSV-compatible format
            st.download_button(
                label="Download Test Suite",
                data=test_suite,
                file_name="test_cases_table.md",
                mime="text/markdown"
            )
    else:
        st.warning("Please provide a file or URL first.")
