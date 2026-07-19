import os

import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(page_title="Everyday Genius — Memory Coach", page_icon="🧠", layout="centered")

st.markdown(
    """
    <div style="text-align:center; padding: 0.5rem 0 1rem 0;">
      <div style="font-size:2.4rem; font-weight:800;">🧠 Everyday Genius</div>
      <div style="font-size:1.05rem; opacity:0.8;">Your memory coach for remembering anything and studying smarter.</div>
    </div>
    """,
    unsafe_allow_html=True,
)


def show_meta(data):
    """Small, out-of-the-way tokens/cost line (kept for the assignment)."""
    with st.expander("nerd stats"):
        st.caption(
            f"confidence {data.get('confidence', 0):.2f} · "
            f"{data.get('tokens_used', 0)} tokens · ${data.get('cost_usd', 0):.6f}"
        )


tab_remember, tab_study = st.tabs(["✨ Remember anything", "📚 Study from my notes"])

# --- Mode 1: general technique coach (/ask) ---
with tab_remember:
    st.subheader("Give me something to remember")
    st.caption("A name, a list, a formula, a date — anything. I'll give you the best trick to lock it in.")
    thing = st.text_input(
        "What do you want to remember?",
        placeholder="The first 8 elements of the periodic table",
        label_visibility="collapsed",
    )
    if st.button("Get my technique ✨", type="primary") and thing:
        with st.spinner("Finding your best trick..."):
            r = requests.post(f"{API_URL}/ask", json={"question": thing}, timeout=60)
        r.raise_for_status()
        data = r.json()
        st.success(data["answer"])
        show_meta(data)

# --- Mode 2: RAG grounded in the student's own notes (/ingest + /study) ---
with tab_study:
    st.subheader("1. Add your class notes")
    st.caption("Paste notes from a lecture or reading. Give them a name so you can add more later.")
    course = st.text_input("Notes name", placeholder="bio-chapter-3")
    notes = st.text_area("Paste your notes", height=160, placeholder="The Krebs cycle is...")
    if st.button("Add to my notes 📥") and course and notes:
        with st.spinner("Filing your notes..."):
            r = requests.post(f"{API_URL}/ingest", json={"document_id": course, "text": notes}, timeout=120)
        r.raise_for_status()
        st.success(f"Added {r.json()['chunks_ingested']} chunk(s) from '{course}'. Ask about it below.")

    st.divider()
    st.subheader("2. Ask how to remember a topic")
    st.caption("I'll pull it from your notes and give you a technique made for that exact material.")
    topic = st.text_input(
        "Which topic?",
        placeholder="How do I remember the steps of the Krebs cycle?",
        label_visibility="collapsed",
    )
    if st.button("Coach me 📚", type="primary") and topic:
        with st.spinner("Reading your notes..."):
            r = requests.post(f"{API_URL}/study", json={"question": topic}, timeout=60)
        r.raise_for_status()
        data = r.json()
        if data["sources_needed"]:
            st.warning(data["answer"])
        else:
            st.success(data["answer"])
            if data["citations"]:
                st.caption("📌 From your notes: " + ", ".join(data["citations"]))
        show_meta(data)
