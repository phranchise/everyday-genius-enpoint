import os

import requests
import streamlit as st

# Voice input is optional: if the component or the browser can't do it, typing still works.
try:
    from streamlit_mic_recorder import speech_to_text
    MIC = True
except Exception:
    MIC = False

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(page_title="Everyday Genius — Memory Coach", page_icon="🧠", layout="centered")

st.markdown(
    """
    <style>
      /* clean, app-like: hide Streamlit chrome */
      [data-testid="stToolbar"], #MainMenu, footer, header { visibility: hidden; height: 0; }
      .block-container { padding-top: 2.2rem; max-width: 720px; }
      /* responsive hero */
      .hero { text-align: center; margin-bottom: 0.4rem; }
      .hero-title { font-weight: 800; font-size: clamp(2rem, 7vw, 2.7rem); line-height: 1.1; }
      .hero-sub { opacity: 0.82; font-size: clamp(0.95rem, 3.4vw, 1.12rem); margin-top: 0.3rem; }
      /* bigger, comfier tabs for thumbs */
      .stTabs [data-baseweb="tab"] { font-size: 1.02rem; padding: 0.4rem 0.6rem; }
      div.stButton > button { border-radius: 10px; font-weight: 600; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="hero">
      <div class="hero-title">🧠 Everyday Genius</div>
      <div class="hero-sub">Lock anything into memory. Ask for a quick trick, or study smarter from your own notes.</div>
    </div>
    """,
    unsafe_allow_html=True,
)


def mic_into(state_key: str):
    """Render a mic button; if speech comes back, drop it into state_key. No-op if unavailable."""
    if not MIC:
        return
    said = speech_to_text(start_prompt="🎤", stop_prompt="⏹", just_once=True, language="en", key=state_key + "_mic")
    if said:
        st.session_state[state_key] = said


def ask_row(state_key: str, label: str, placeholder: str):
    """A text input with a mic button beside it, both bound to st.session_state[state_key]."""
    st.session_state.setdefault(state_key, "")
    text_col, mic_col = st.columns([6, 1], vertical_alignment="bottom")
    with mic_col:
        mic_into(state_key)  # must run before the text_input so state is set first
    with text_col:
        st.text_input(label, key=state_key, placeholder=placeholder)


def show_meta(data: dict):
    with st.expander("nerd stats"):
        st.caption(
            f"confidence {data.get('confidence', 0):.2f} · "
            f"{data.get('tokens_used', 0)} tokens · ${data.get('cost_usd', 0):.6f}"
        )


tab_remember, tab_study = st.tabs(["✨ Remember anything", "📚 Study from my notes"])

# --- Mode 1: general technique coach (/ask) ---
with tab_remember:
    st.caption("Type a name, a list, a formula, a date, anything. I'll give you the best trick to remember it.")

    st.write("**Try an example:**")
    ex = st.columns(3)
    examples = {
        "🧪 Periodic table": "the first 8 elements of the periodic table",
        "🧠 Cranial nerves": "the 12 cranial nerves in order",
        "🔢 A phone number": "the phone number 612-555-0182",
    }
    for col, (chip, value) in zip(ex, examples.items()):
        if col.button(chip, use_container_width=True):
            st.session_state["remember_q"] = value

    ask_row("remember_q", "What do you want to remember?", "e.g. the first 20 digits of pi")

    if st.button("Get my technique ✨", type="primary", use_container_width=True) and st.session_state.get("remember_q"):
        with st.spinner("Finding your best trick..."):
            r = requests.post(f"{API_URL}/ask", json={"question": st.session_state["remember_q"]}, timeout=60)
        r.raise_for_status()
        data = r.json()
        with st.container(border=True):
            st.markdown(data["answer"])
        show_meta(data)

# --- Mode 2: RAG grounded in the student's own notes (/ingest + /study) ---
with tab_study:
    st.caption("Add your class notes once, then ask how to remember any topic from them.")

    st.markdown("#### 🧠 Ask about your notes")
    ask_row("study_q", "Which topic do you want to remember?", "e.g. the steps of the Krebs cycle")

    if st.button("Coach me 📚", type="primary", use_container_width=True) and st.session_state.get("study_q"):
        with st.spinner("Reading your notes..."):
            r = requests.post(f"{API_URL}/study", json={"question": st.session_state["study_q"]}, timeout=60)
        r.raise_for_status()
        data = r.json()
        if data["sources_needed"]:
            st.warning(data["answer"] + "  \n\n_Add notes on it below, then ask again._")
        else:
            with st.container(border=True):
                st.markdown(data["answer"])
                if data["citations"]:
                    st.caption("📌 From your notes: " + ", ".join(data["citations"]))
        show_meta(data)

    st.markdown("")
    with st.expander("📥 Add or update your notes", expanded=True):
        course = st.text_input("Give these notes a name", placeholder="bio-chapter-3", key="course_name")
        notes = st.text_area("Paste your notes", height=140, placeholder="The Krebs cycle is...", key="notes_text")
        if st.button("Add to my notes 📥", use_container_width=True) and course and notes:
            with st.spinner("Filing your notes..."):
                r = requests.post(f"{API_URL}/ingest", json={"document_id": course, "text": notes}, timeout=120)
            r.raise_for_status()
            st.success(f"Added {r.json()['chunks_ingested']} chunk(s) from '{course}'. Now ask about it above ⬆️")
