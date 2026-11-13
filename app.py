"""CacheMind entry point. Run with: streamlit run app.py"""
import streamlit as st

import theme
import views_analysis
import views_core
import views_learn
from ui_common import CSS, bound, config_summary, init_state

st.set_page_config(page_title="CacheMind", page_icon=":material/memory:", layout="wide")
st.markdown(CSS, unsafe_allow_html=True)
init_state()

PAGES = {
    "Overview": lambda: views_core.dashboard(list(PAGES)),
    "Cache Simulator": views_core.simulator,
    "Mapping Laboratory": views_core.mapping_lab,
    "Address Calculator": views_core.address_calculator,
    "Performance Analyzer": views_analysis.performance,
    "Cache Optimiser": views_analysis.optimiser,
    "Learning Centre": views_learn.learning,
    "Challenge Mode": views_learn.challenge,
    "Settings": views_learn.settings,
}

st.session_state.setdefault("nav", "Overview")
if st.session_state.nav not in PAGES:  # older sessions used "Dashboard"
    st.session_state.nav = "Overview"
with st.sidebar:
    st.markdown(f'<div class="cm-brand">{theme.BRAND_MARK}<b>CacheMind</b></div>'
                f'<div class="cm-scope">{theme.esc(config_summary(st.session_state.cfg))}</div>',
                unsafe_allow_html=True)
    st.radio("Navigate", list(PAGES), label_visibility="collapsed", **bound("nav"))

PAGES[st.session_state.nav]()
