import pypdf
import docx
import pandas as pd
import io
import os

def extract_text_from_pdf(file_bytes):
    try:
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        text_parts = []
        for page in reader.pages:
            t = page.extract_text()
            if t:
                text_parts.append(t)
        return "\n".join(text_parts)
    except Exception as e:
        print(f"Error parsing PDF: {e}")
        return ""

def extract_text_from_docx(file_bytes):
    try:
        doc = docx.Document(io.BytesIO(file_bytes))
        text_parts = []
        for p in doc.paragraphs:
            if p.text.strip():
                text_parts.append(p.text)
        # Parse tables if present
        for table in doc.tables:
            for row in table.rows:
                row_text = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if row_text:
                    text_parts.append(" | ".join(row_text))
        return "\n".join(text_parts)
    except Exception as e:
        print(f"Error parsing DOCX: {e}")
        return ""

def extract_text_from_xlsx(file_bytes):
    try:
        # Load sheets
        excel_file = pd.ExcelFile(io.BytesIO(file_bytes))
        text_parts = []
        for sheet_name in excel_file.sheet_names:
            df = excel_file.parse(sheet_name)
            # Represent rows as text lines
            text_parts.append(f"Sheet: {sheet_name}")
            for idx, row in df.iterrows():
                row_str = ", ".join([f"{col}: {val}" for col, val in row.items() if not pd.isna(val)])
                if row_str:
                    text_parts.append(row_str)
        return "\n".join(text_parts)
    except Exception as e:
        print(f"Error parsing XLSX: {e}")
        return ""

def extract_text_from_txt(file_bytes):
    try:
        return file_bytes.decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"Error parsing TXT: {e}")
        return ""

def parse_document(file_bytes, filename):
    """
    Directs the document to the corresponding parser based on extension.
    """
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".pdf":
        return extract_text_from_pdf(file_bytes)
    elif ext in [".docx", ".doc"]:
        return extract_text_from_docx(file_bytes)
    elif ext in [".xlsx", ".xls", ".csv"]:
        return extract_text_from_xlsx(file_bytes)
    elif ext == ".txt":
        return extract_text_from_txt(file_bytes)
    else:
        # Fallback to plain text decode
        return extract_text_from_txt(file_bytes)

def chunk_text(text, chunk_size=600, overlap=100):
    """
    Splits text into sliding-window character chunks, preserving space boundaries.
    """
    if not text:
        return []
        
    chunks = []
    text_len = len(text)
    start = 0
    
    while start < text_len:
        end = min(start + chunk_size, text_len)
        
        # Look for clean boundary space at the end of chunk
        if end < text_len:
            last_space = text.rfind(" ", end - 50, end)
            if last_space != -1:
                end = last_space
                
        chunk = text[start:end].strip()
        if len(chunk) > 20:
            chunks.append(chunk)
            
        start = end - overlap
        if start >= text_len - overlap:
            break
            
    return chunks
