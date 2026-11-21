import streamlit as st
import uuid


def init_session(passenger_id: str, mock_mode: bool):
    defaults = {
        "passenger_id": passenger_id,
        "session_id": f"session_{uuid.uuid4().hex[:8]}",
        "mock_mode": mock_mode,
        "messages": [],
        "selected_booking_id": None,
        "pending_action": None,
        "last_trace_id": None,
        "support_status": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def clear_chat():
    st.session_state.messages = []
