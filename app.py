"""Forensic Science Laboratory — Streamlit app.  Run: streamlit run app.py"""
import streamlit as st

st.set_page_config(page_title="Forensic Science Laboratory", page_icon="⚖️", layout="wide")

import cases_db  # noqa: E402
import page_cases  # noqa: E402
import page_digital  # noqa: E402
import page_dna  # noqa: E402
import page_fingerprint  # noqa: E402
import page_learn  # noqa: E402
import page_portal  # noqa: E402
import page_tox  # noqa: E402
import ui  # noqa: E402

PAGES = {"🏛️ Laboratory portal": page_portal.render, "🗂️ Cases & custody": page_cases.render, "🧬 DNA laboratory": page_dna.render,
         "💻 Digital forensics": page_digital.render, "🧪 Toxicology & pathology": page_tox.render,
         "🖐️ Fingerprints": page_fingerprint.render, "📚 Learning hub": page_learn.render}


def main():
    cases_db.init()
    ui.style()
    st.sidebar.title("⚖️ Forensic Lab")
    page = st.sidebar.radio("Navigate", list(PAGES), label_visibility="collapsed")
    st.sidebar.caption("Demo data is fictional. Educational software — not for operational casework.")
    PAGES[page]()


main()
