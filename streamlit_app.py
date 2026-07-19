import os

import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.title("Everyday Genius Coach")
st.caption("Memory & cognition techniques from Nelson Dellis's *Everyday Genius*.")

question = st.text_input("Ask a question", placeholder="How do I remember people's names?")

if st.button("Ask") and question:
    with st.spinner("Thinking..."):
        r = requests.post(f"{API_URL}/ask", json={"question": question}, timeout=60)
    r.raise_for_status()
    data = r.json()

    st.write(data["answer"])
    cols = st.columns(3)
    cols[0].metric("Confidence", f"{data['confidence']:.2f}")
    cols[1].metric("Tokens", data["tokens_used"])
    cols[2].metric("Cost (USD)", f"${data['cost_usd']:.6f}")

    if data["sources_needed"]:
        st.warning("The coach flagged that this needs source material — grounding arrives in Week 2.")
