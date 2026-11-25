import io
import zipfile

import pandas as pd
import streamlit as st

from table_extractor import extract_from_image, extract_from_pdf

st.set_page_config(
    page_title="AITransform Table Extractor",
    page_icon="📊",
    layout="wide",
)

st.title("📊 AITransform PDF Table Extractor")
st.write("Upload a PDF or an image, preview the extracted tables, then download them as Excel or CSV.")


@st.cache_data(show_spinner=False)
def run_extraction(file_bytes, file_name):
    buffer = io.BytesIO(file_bytes)
    if file_name.lower().endswith(".pdf"):
        return extract_from_pdf(buffer)
    return extract_from_image(buffer)


def to_excel(tables):
    out = io.BytesIO()
    used = set()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        for t in tables:
            sheet = t["name"][:31]
            n = 1
            while sheet in used:
                n += 1
                sheet = f"{t['name'][:28]}_{n}"
            used.add(sheet)
            t["data"].to_excel(writer, sheet_name=sheet, index=False)
    return out.getvalue()


def to_csv_zip(tables):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for t in tables:
            z.writestr(f"{t['name']}.csv", t["data"].to_csv(index=False))
    return out.getvalue()


uploaded = st.file_uploader(
    "Upload a file", type=["pdf", "png", "jpg", "jpeg"]
)

if uploaded is None:
    st.info("Upload a PDF or an image containing tables to get started.")
    st.stop()

with st.spinner("Extracting tables..."):
    try:
        tables = run_extraction(uploaded.getvalue(), uploaded.name)
    except Exception as e:
        st.error(f"Extraction failed: {e}")
        st.stop()

if not tables:
    st.warning("No tables were found in this file.")
    st.stop()

st.success(f"Found {len(tables)} table(s).")

st.subheader("Preview")
for t in tables:
    st.markdown(f"**{t['name']}** ({t['data'].shape[0]} rows x {t['data'].shape[1]} columns)")
    st.dataframe(t["data"], use_container_width=True)

st.subheader("Download")
col1, col2 = st.columns(2)

with col1:
    st.download_button(
        "Download Excel (one sheet per table)",
        data=to_excel(tables),
        file_name="tables.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

with col2:
    if len(tables) == 1:
        st.download_button(
            "Download CSV",
            data=tables[0]["data"].to_csv(index=False),
            file_name=f"{tables[0]['name']}.csv",
            mime="text/csv",
        )
    else:
        st.download_button(
            "Download CSV (zip, one CSV per table)",