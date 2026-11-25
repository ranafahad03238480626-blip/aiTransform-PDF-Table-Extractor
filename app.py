import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="AITransform Table Extractor",
    page_icon="📊",
    layout="wide",
)

st.title("📊 AITransform PDF Table Extractor")

try:
    import pdfplumber
except ImportError:
    st.error("pdfplumber install nahi hai. Terminal mein chalayein: pip install pdfplumber")
    st.stop()


def make_unique(cols):
    seen, out = {}, []
    for i, c in enumerate(cols):
        name = str(c).strip() if c not in (None, "") else f"col_{i + 1}"
        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 0
        out.append(name)
    return out


def table_to_df(table):
    if not table or len(table) < 2:
        return pd.DataFrame(table or [])
    header = make_unique(table[0])
    return pd.DataFrame(table[1:], columns=header)


uploaded = st.file_uploader("PDF file upload karein", type=["pdf"])

if uploaded is None:
    st.info("Shuru karne ke liye koi PDF upload karein.")
else:
    try:
        total = 0
        with pdfplumber.open(uploaded) as pdf:
            st.write(f"Total pages: **{len(pdf.pages)}**")
            for page_no, page in enumerate(pdf.pages, start=1):
                tables = page.extract_tables()
                for t_no, table in enumerate(tables, start=1):