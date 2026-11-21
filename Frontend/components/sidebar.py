import streamlit as st

NAV_ITEMS = [
    "AI Chat Assistant",
    "Search Trains",
    "My Bookings",
    "Confirm Ticket",
    "Cancel Ticket",
    "Refund Information",
    "Help & Support",
]


def render_sidebar(passenger_id: str, session_id: str, health: dict, mock_mode: bool):
    with st.sidebar:
        st.markdown('<div class="brand-mark"><span>U</span></div>', unsafe_allow_html=True)
        st.markdown("### Ujjwal Rail AI")
        st.caption("Rail travel assistant")
        st.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)

        choice = st.radio("Navigation", NAV_ITEMS, label_visibility="collapsed")

        st.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)
        st.markdown("**Session**")
        st.caption(f"Passenger: `{passenger_id}`")
        st.caption(f"Session: `{session_id[:12]}…`")

        if mock_mode:
            st.info("Mock mode active")
        else:
            status = health.get("status", "offline")
            if status in ("ok", "healthy"):
                st.success("Backend connected")
            else:
                st.error("Backend offline")

        st.caption("Identity is sent via X-Passenger-Id")
        return choice
