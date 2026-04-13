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

# --- 1. AI CONFIGURATION ---
API_KEY = "AIzaSyCmQF3w7UXpufXXDzZjxxWhopnkxiH3KZ0" 
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash-lite')

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
        # 1. Clean up lines and find any line containing a pipe '|'
        lines = [line.strip() for line in md_table_text.split('\n') if '|' in line]
        
        table_data = []
        for line in lines:
            # Skip lines that are just Markdown separators (e.g., |---|---|)
            if re.match(r'^[\s|:-]+$', line):
                continue
            
            # Split and clean cells
            row = [cell.strip() for cell in line.split('|')]
            
            # Remove empty strings at start/end (caused by leading/trailing pipes)
            if row and not row[0]: row.pop(0)
            if row and not row[-1]: row.pop(-1)
            
            if row:
                table_data.append(row)
        
        if not table_data or len(table_data) < 2:
            return None

        # 2. Extract Headers and ensure all rows match header length
        headers = table_data[0]
        rows = table_data[1:]
        
        # Clean rows: pad if too short, truncate if too long
        cleaned_rows = []
        for r in rows:
            if len(r) > len(headers):
                cleaned_rows.append(r[:len(headers)])
            else:
                cleaned_rows.append(r + [""] * (len(headers) - len(r)))

        df = pd.DataFrame(cleaned_rows, columns=headers)
        
        # 3. Write to Excel
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='TestCases')
            
            workbook = writer.book
            worksheet = writer.sheets['TestCases']
            
            # Header styling
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#D7E4BC',
                'border': 1
            })
            
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
                # Auto-adjust column width
                column_len = max(df[value].astype(str).map(len).max(), len(value)) + 2
                worksheet.set_column(col_num, col_num, min(max(column_len, 10), 60))
        
        return output.getvalue()
    except Exception:
        return None

# --- 5. AI GENERATION LOGIC ---
def get_ai_test_cases(content, content_type):
    base_prompt = """
    You are a Senior QA Automation Engineer.
    Analyze the provided requirements and create a comprehensive test suite.
    
    OUTPUT FORMAT: You MUST return a Markdown Table ONLY. 
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

# --- 6. UI SIDEBAR ---
with st.sidebar:
    st.header("Settings")
    source_type = st.radio("Source Selection:", ["File Upload", "URL Link"])
    uploaded_file = st.file_uploader("Upload Image/Doc", type=["pdf", "docx", "xlsx", "xls", "png", "jpg"]) if source_type == "File Upload" else None
    url_input = st.text_input("Paste Requirement URL:") if source_type == "URL Link" else None

# --- 7. EXECUTION ---
if st.button("Generate Test Suite 🚀"):
    if uploaded_file or url_input:
        with st.spinner("Processing..."):
            content, content_type = extract_content(uploaded_file, url_input)
            
        if content_type == "error":
            st.error(content)
        else:
            # 1. Preview
            st.divider()
            st.subheader("🖼️ Input Preview")
            if content_type == "image":
                st.image(content, use_container_width=True)
            else:
                with st.expander("View Extracted Text"):
                    st.text(content)

            # 2. Table
            st.divider()
            st.subheader("📊 AI Generated Test Case Table")
            with st.spinner("Writing test cases..."):
                suite_md = get_ai_test_cases(content, content_type)
                st.markdown(suite_md)
            
            # 3. Excel Download
            st.divider()
            excel_file = convert_md_to_excel(suite_md)
            
            if excel_file:
                st.download_button(
                    label="📥 Download Test Suite (Excel)",
                    data=excel_file,
                    file_name="QA_Test_Cases.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.warning("Excel conversion failed. Try clicking 'Generate' again.")
    else:
        st.warning("Please provide an input first.")
