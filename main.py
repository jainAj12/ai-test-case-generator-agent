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

# --- 4. EXCEL CONVERSION HELPER ---
def convert_md_to_excel(md_table_text):
    try:
        # Split the text into lines and find the table part
        lines = [line.strip() for line in md_table_text.split('\n') if '|' in line]
        
        # Remove the separator line (the one with ---|---|---)
        valid_lines = [line for line in lines if not all(c in '|- ' for c in line)]
        
        # Parse into a list of lists
        data = []
        for line in valid_lines:
            # Split by | and remove the empty strings from the start/end
            row = [cell.strip() for cell in line.split('|') if cell.strip() != '']
            if row:
                data.append(row)
        
        if not data:
            return None

        # Create DataFrame
        df = pd.DataFrame(data[1:], columns=data[0])
        
        # Convert to Excel Buffer
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='TestCases')
            # Auto-adjust column width
            worksheet = writer.sheets['TestCases']
            for i, col in enumerate(df.columns):
                column_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
                worksheet.set_column(i, i, min(column_len, 50)) # Cap at 50
        
        return output.getvalue()
    except Exception:
        return None

# --- 5. AI GENERATION LOGIC ---
def get_ai_test_cases(content, content_type):
    base_prompt = """
    You are a Senior QA Automation Engineer. 
    Analyze the requirements and create a comprehensive test suite.
    
    OUTPUT FORMAT: You MUST return a Markdown Table ONLY. 
    Do not add conversational text before or after the table.
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
                    file_name="ai_test_cases.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.error("Failed to convert table to Excel. Please try again.")
    else:
        st.warning("Please provide an input first.")
