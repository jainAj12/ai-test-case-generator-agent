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
import re

# --- 1. AI CONFIGURATION (SINGLE KEY MODE) ---
API_KEY = "AIzaSyC1FMkabE5zTdrOnS019CSdZVgYcPVKla4" 

def configure_genai():
    """Configures the Generative AI with a single fixed key."""
    if not API_KEY or "YOUR_KEY" in API_KEY:
        st.error("Please provide a valid API Key.")
        return None
    
    genai.configure(api_key=API_KEY)
    # Using gemini-1.5-flash (Highest free tier quota: 15 RPM / 1500 RPD)
    return genai.GenerativeModel('gemini-2.5-flash')

# --- 2. APP CONFIG ---
st.set_page_config(page_title="AI Test Case Agent", page_icon="🧪", layout="wide")
st.title("🧪 AI Test Case Generator")

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

# --- 4. ROBUST EXCEL CONVERSION ---
def convert_md_to_excel(md_table_text):
    try:
        lines = [line.strip() for line in md_table_text.split('\n') if '|' in line]
        table_data = []
        for line in lines:
            if re.match(r'^[\s|:-]+$', line): continue
            row = [cell.strip() for cell in line.split('|')]
            if row and not row[0]: row.pop(0)
            if row and not row[-1]: row.pop(-1)
            if row: table_data.append(row)
        
        if len(table_data) < 2: return None

        df = pd.DataFrame(table_data[1:], columns=table_data[0])
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='TestCases')
            workbook, worksheet = writer.book, writer.sheets['TestCases']
            header_fmt = workbook.add_format({'bold': True, 'bg_color': '#D7E4BC', 'border': 1})
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_fmt)
                width = max(df[value].astype(str).map(len).max(), len(value)) + 2
                worksheet.set_column(col_num, col_num, min(max(width, 10), 60))
        return output.getvalue()
    except Exception: return None

# --- 5. AI GENERATION LOGIC ---
def get_ai_test_cases(content, content_type):
    model = configure_genai()
    if not model: return "Configuration Error."

    base_prompt = """
    You are a Senior QA Automation Engineer.
    Return ONLY a Markdown Table. No conversational text.
    Columns: | Test ID | Title | Priority | Steps | Expected Result | Type |
    """
    
    try:
        if content_type == "image":
            response = model.generate_content([base_prompt, content])
        else:
            response = model.generate_content(f"{base_prompt}\n\nRequirements:\n{content}")
        return response.text
    except Exception as e:
        return f"AI Error: {str(e)}"

# --- 6. UI ---
with st.sidebar:
    st.header("Settings")
    source_type = st.radio("Source:", ["File Upload", "URL Link"])
    uploaded_file = st.file_uploader("Upload Image/Doc", type=["pdf", "docx", "xlsx", "xls", "png", "jpg"]) if source_type == "File Upload" else None
    url_input = st.text_input("Paste Requirement URL:") if source_type == "URL Link" else None

if st.button("Generate Test Suite 🚀"):
    if uploaded_file or url_input:
        with st.spinner("Processing..."):
            content, content_type = extract_content(uploaded_file, url_input)
            
        if content_type == "error":
            st.error(content)
        else:
            st.divider()
            if content_type == "image":
                st.image(content, use_container_width=True)
            else:
                with st.expander("Extracted Content"): st.text(content)

            st.divider()
            st.subheader("📊 Generated Test Cases")
            suite_md = get_ai_test_cases(content, content_type)
            st.markdown(suite_md)
            
            excel_bin = convert_md_to_excel(suite_md)
            if excel_bin:
                st.download_button("📥 Download Excel", excel_bin, "QA_Test_Cases.xlsx")
    else:
        st.warning("Please provide an input.")
