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
# Using the provided key
API_KEY = "AIzaSyCmQF3w7UXpufXXDzZjxxWhopnkxiH3KZ0" 
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash-lite')

# --- 2. APP CONFIG ---
st.set_page_config(page_title="AI Test Case Agent", page_icon="🧪", layout="wide")
st.title("🧪 Multimodal AI Test Case Generator")

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

# --- 4. ROBUST EXCEL CONVERSION HELPER ---
def convert_md_to_excel(md_table_text):
    try:
        # Clean lines and keep only those containing the table pipe '|'
        lines = [line.strip() for line in md_table_text.split('\n') if '|' in line]
        
        table_data = []
        for line in lines:
            # Skip Markdown separator lines like |---|---|
            if re.match(r'^[\s|:-]+$', line):
                continue
            
            # Split by | and clean whitespace
            row = [cell.strip() for cell in line.split('|')]
            
            # Handle leading/trailing empty strings from the pipes
            if row and not row[0]: row.pop(0)
            if row and not row[-1]: row.pop(-1)
            
            if row:
                table_data.append(row)
        
        if not table_data or len(table_data) < 2:
            return None

        # Headers are the first row
        headers = table_data[0]
        rows = table_data[1:]
        
        # Standardize row lengths to match headers
        standardized_rows = []
        for r in rows:
            if len(r) > len(headers):
                standardized_rows.append(r[:len(headers)])
            elif len(r) < len(headers):
                standardized_rows.append(r + [""] * (len(headers) - len(r)))
            else:
                standardized_rows.append(r)

        df = pd.DataFrame(standardized_rows, columns=headers)
        
        # Convert to Excel Buffer with XlsxWriter for professional formatting
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='TestCases')
            
            workbook = writer.book
            worksheet = writer.sheets['TestCases']
            
            # Add some styling
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#D7E4BC',
                'border': 1
            })
            
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
                # Auto-adjust column width (min 10, max 60)
                column_len = max(df[value].astype(str).map(len).max(), len(value)) + 2
                worksheet.set_column(col_num, col_num, min(max(column_len, 10), 60))
        
        return output.getvalue()
    except Exception as e:
        st.error(f"Excel Conversion Logic Error: {e}")
        return None

# --- 5. AI GENERATION LOGIC ---
def get_ai_test_cases(content, content_type):
    base_prompt = """
    You are a Senior QA Automation Engineer. 
    Analyze the requirements and create a professional, comprehensive test suite.
    
    CRITICAL OUTPUT RULE: 
    Return ONLY a Markdown Table. Do not include any intro, outro, or conversation.
    Columns: | Test ID | Title | Priority | Steps | Expected Result | Type |
    """
    try:
        if content_type == "image":
            response = model.generate_content([base_prompt, content])
        else:
            response = model.generate_content(f"{base_prompt}\n\nRequirements Content:\n{content}")
        return response.text
    except Exception as e:
        return f"AI Error: {str(e)}"

# --- 6. UI SIDEBAR ---
with st.sidebar:
    st.header("Settings")
    source_type = st.radio("Source Selection:", ["File Upload", "URL Link"])
    uploaded_file = None
    url_input = None

    if source_type == "File Upload":
        uploaded_file = st.file_uploader("Upload Image or Document", type=["pdf", "docx", "xlsx", "xls", "png", "jpg"])
    else:
        url_input = st.text_input("Paste Requirement URL:")

# --- 7. EXECUTION FLOW ---
if st.button("Generate Test Suite 🚀"):
    if uploaded_file or url_input:
        with st.spinner("Processing..."):
            content, content_type = extract_content(uploaded_file, url_input)
            
        if content_type == "error":
            st.error(content)
        else:
            # 1. Image/Content Preview
            st.divider()
            st.subheader("🖼️ Input Preview")
            if content_type == "image":
                st.image(content, caption="Requirement Screenshot", use_container_width=True)
            else:
                with st.expander("View Extracted Text"):
                    st.text(content)

            # 2. AI Generation & Table Display
            st.divider()
            st.subheader("📊 AI Generated Test Case Table")
            with st.spinner("Writing test cases..."):
                test_suite_md = get_ai_test_cases(content, content_type)
                st.markdown(test_suite_md)
            
            # 3. Conversion to Excel and Download
            st.divider()
            excel_data = convert_md_to_excel(test_suite_md)
            
            if excel_data:
                st.download_button(
                    label="📥 Download Test Suite (Excel)",
                    data=excel_data,
                    file_name="QA_Test_Cases.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.error("Failed to parse the AI table into Excel. Please try clicking Generate again.")
    else:
        st.warning("Please provide an input first.")
