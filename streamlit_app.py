import os

import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.title("Everyday Genius Coach")
st.caption("Ask memory & cognition questions grounded in your own ingested notes.")

tab_ask, tab_ingest = st.tabs(["Ask", "Ingest"])

with tab_ingest:
    document_id = st.text_input("Document ID", placeholder="memory-notes")
    text = st.text_area("Text to ingest", height=200)
    if st.button("Ingest") and document_id and text:
        with st.spinner("Ingesting..."):
            r = requests.post(f"{API_URL}/ingest", json={"document_id": document_id, "text": text}, timeout=120)
        r.raise_for_status()
        st.success(f"Ingested {r.json()['chunks_ingested']} chunks from '{document_id}'.")

with tab_ask:
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

        if data["citations"]:
            st.caption("Sources: " + ", ".join(data["citations"]))
        if data["sources_needed"]:
            st.warning("Not enough grounded information in the ingested documents to answer.")
