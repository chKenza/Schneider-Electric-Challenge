"""ETO Quote Risk & Pricing – entry point.

Run from the repo root:
    uv run streamlit run app/streamlit_app.py
"""

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

st.set_page_config(page_title="ETO Quote Risk & Pricing", layout="wide")

nav = st.navigation([
    st.Page(ROOT / "app" / "quote_page.py", title="Quote pricing", default=True),
    st.Page(ROOT / "app" / "airset_page.py", title="RM AirSeT strategy"),
])
nav.run()
