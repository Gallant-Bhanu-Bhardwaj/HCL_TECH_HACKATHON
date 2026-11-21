"""
ui/app.py - Streamlit chat page for the Ujjwal Rail assistant.
Start the API first (./run.sh mock), then:  streamlit run ui/app.py
"""
import json
import os
import uuid

import requests
import streamlit as st

API = os.getenv("API_URL", "http://localhost:8000")
st.set_page_config(page_title="Ujjwal Rail Assistant")


def call(method, path, passenger=None, body=None):
    """Call the API. Returns (status_code, json). Status 0 means the API is not reachable."""
    headers = {"X-Passenger-Id": passenger} if passenger else {}
    try:
        r = requests.request(method, API + path, headers=headers, json=body, timeout=180)
        return r.status_code, r.json()
    except (requests.RequestException, ValueError) as e:
        return 0, {"detail": f"API not reachable: {e}"}


def reset_chat():
    st.session_state.messages = []
    st.session_state.pending = None
    st.session_state.session_id = uuid.uuid4().hex[:8]


if "messages" not in st.session_state:
    reset_chat()

# ---------- sidebar: who is asking, what time it is, and helper tools ----------
with st.sidebar:
    st.header("Settings")
    passenger = st.text_input("Passenger ID (sent as X-Passenger-Id)", "P007")
    if st.session_state.get("passenger") != passenger:     # another person: start a fresh chat
        st.session_state.passenger = passenger
        reset_chat()
    use_now = st.checkbox("Use the real current time", value=False)
    as_of = None if use_now else st.text_input("as_of (test time)", "2026-12-03T10:00:00+05:30")
    if st.button("New conversation"):
        reset_chat()

    code, health = call("GET", "/health")
    st.caption("API: connected" if code == 200 else f"API: not reachable at {API}")

    st.subheader("Look up a booking")
    booking_id = st.text_input("Booking ID", "UR-30418")
    if st.button("Get booking"):
        code, data = call("GET", f"/bookings/{booking_id}", passenger)
        st.json(data) if code == 200 else st.error(data.get("detail", data))

    st.subheader("Add a rule or circular")
    doc_text = st.text_area("Document as JSON", '{"doc_id": "CIR-2026-09", "type": "circular", "text": "..."}')
    if st.button("Send to /ingest"):
        try:
            code, data = call("POST", "/ingest", body=json.loads(doc_text))
            st.success(data) if code == 200 else st.error(data.get("detail", data))
        except json.JSONDecodeError:
            st.error("That is not valid JSON.")


# ---------- show one assistant reply with its details ----------
def show_reply(reply):
    st.markdown(reply.get("answer") or "(no answer)")
    st.caption(f"answer_type: {reply.get('answer_type')}   |   trace_id: {reply.get('trace_id')}")
    if reply.get("sources"):
        st.caption("Sources: " + ", ".join(f"{s['doc_id']} ({s['section']})" for s in reply["sources"]))
    if reply.get("handed_to_human"):
        h = reply["handed_to_human"]
        st.warning(f"Passed to the {h.get('desk')} desk, reference {h.get('ref')}.")
    if reply.get("tools"):
        with st.expander("Tools used"):
            st.json(reply["tools"])


# ---------- chat history ----------
st.title("Ujjwal Rail Assistant")
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "user":
            st.markdown(msg["text"])
        else:
            show_reply(msg["reply"])

# ---------- a proposed change waiting for Confirm or Cancel ----------
pending = st.session_state.pending
if pending:
    st.info("Proposed change. Nothing happens until you press Confirm.")
    st.json(pending)
    col1, col2 = st.columns(2)
    for col, label, action in [(col1, "Confirm", "confirm"), (col2, "Cancel", "cancel")]:
        if col.button(label, use_container_width=True):
            code, reply = call("POST", f"/actions/{pending['action_id']}/{action}", passenger, {"as_of": as_of})
            st.session_state.messages.append({"role": "assistant", "reply": reply})
            st.session_state.pending = None
            st.rerun()

# ---------- new message ----------
if text := st.chat_input("Ask about trains, fares, bookings, refunds or rules"):
    st.session_state.messages.append({"role": "user", "text": text})
    with st.spinner("Thinking..."):
        body = {"session_id": st.session_state.session_id, "message": text, "as_of": as_of}
        code, reply = call("POST", "/chat", passenger, body)
    if code != 200:
        reply = {"answer": f"Error: {reply.get('detail', reply)}", "answer_type": "error"}
    st.session_state.messages.append({"role": "assistant", "reply": reply})
    st.session_state.pending = reply.get("pending_action")
    st.rerun()
