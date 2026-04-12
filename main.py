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
import qrcode
import socket

# --- 1. AI CONFIGURATION ---
API_KEY = "AIzaSyCmQF3w7UXpufXXDzZjxxWhopnkxiH3KZ0" 
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash-lite')

# --- 2. NETWORK HELPER (For QR Code) ---
def get_local_ip():
    """Detects the local IP to allow mobile devices on the same Wi-Fi to connect."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

# --- 3. APP CONFIG ---
st.set_page_config(page_title="AI Test Case Agent", page_icon="🧪", layout="wide")
st.title("🧪 Multimodal AI Test Case Generator")

# --- 4. EXTRACTION LOGIC ---
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

# --- 5. ROBUST EXCEL CONVERSION ---
def convert_md_to_excel(md_table_text):
    try:
        # Filter lines to find the table rows
        lines = [line.strip() for line in md_table_text.split('\n') if '|' in line]
        table_data = []
        for line in lines:
            # Skip separator lines |---|
            if re.match(r'^[\s|:-]+$', line):
                continue
            row = [cell.strip() for cell in line.split('|')]
            if row and not row[0]: row.pop(0)
            if row and not row[-1]: row.pop(-1)
            if row:
                table_data.append(row)
        
        if not table_data or len(table_data) < 2:
            return None

        headers = table_data[0]
        rows = table_data[1:]
        
        # Standardize row lengths
        std_rows = [r[:len(headers)] if len(r) > len(headers) else r + [""]*(len(headers)-len(r)) for r in rows]
        df = pd.DataFrame(std_rows, columns=headers)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='TestCases')
            workbook, worksheet = writer.book, writer.sheets['TestCases']
            header_fmt = workbook.add_format({'bold': True, 'bg_color': '#D7E4BC', 'border': 1})
            for i, col in enumerate(df.columns):
                worksheet.write(0, i, col, header_fmt)
                width = max(df[col].astype(str).map(len).max(), len(col)) + 2
                worksheet.set_column(i, i, min(max(width, 10), 60))
        return output.getvalue()
    except Exception:
        return None

# --- 6. AI GENERATION ---
def get_ai_test_cases(content, content_type):
    base_prompt = """
    You are a Senior QA Automation Engineer. Create a comprehensive test suite.
    OUTPUT RULE: Return ONLY a Markdown Table. No intro/outro conversation.
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

# --- 7. SIDEBAR (Settings + QR) ---
with st.sidebar:
    st.header("⚙️ Settings")
    source_type = st.radio("Source Selection:", ["File Upload", "URL Link"])
    uploaded_file = st.file_uploader("Upload Document/Image", type=["pdf", "docx", "xlsx", "xls", "png", "jpg"]) if source_type == "File Upload" else None
    url_input = st.text_input("Paste Requirement URL:") if source_type == "URL Link" else None

    st.divider()
    st.header("📱 Mobile Access")
    ip = get_local_ip()
    url = f"http://{ip}:8501"
    qr_img = qrcode.make(url)
    buf = io.BytesIO()
    qr_img.save(buf, format="PNG")
    st.image(buf, caption="Scan to use on Phone", use_container_width=True)
    st.caption(f"Network URL: {url}")

# --- 8. MAIN EXECUTION ---
if st.button("Generate Test Suite 🚀"):
    if uploaded_file or url_input:
        with st.spinner("Processing requirements..."):
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
                with st.expander("View Text Content"):
                    st.text(content)

            # 2. Table
            st.divider()
            st.subheader("📊 AI Generated Test Case Table")
            with st.spinner("AI is thinking..."):
                suite_md = get_ai_test_cases(content, content_type)
                st.markdown(suite_md)
            
            # 3. Excel Download
            st.divider()
            excel_bin = convert_md_to_excel(suite_md)
            if excel_bin:
                st.download_button(
                    label="📥 Download Test Suite (Excel)",
                    data=excel_bin,
                    file_name="QA_Test_Cases.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.error("Table parsing failed. Try generating again.")
    else:
        st.warning("Input required.")
