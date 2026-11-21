import streamlit as st
from utils.formatters import rupee


def render_action_preview(preview: dict, action_id: str, api_client, passenger_id: str, mode: str = "cancel"):
    st.markdown("### Review action")
    with st.container(border=True):
        cols = st.columns(2)
        cols[0].write(f"**Booking:** {preview.get('booking_id', '-')}")
        cols[0].write(f"**Train:** {preview.get('train_number', '-')} · {preview.get('train_name', '-')}")
        cols[0].write(f"**Journey:** {preview.get('journey_date', '-')}")
        cols[1].write(f"**Status:** {preview.get('status', '-')}")
        cols[1].write(f"**Amount paid:** {rupee(preview.get('amount_paid'))}")
        cols[1].write(f"**Estimated refund:** {rupee(preview.get('estimated_refund'))}")
        st.caption(preview.get("rules", "Cancellation rules were not provided by the backend."))

    st.warning("This action will be submitted only after explicit confirmation.")
    a, b = st.columns(2)
    if a.button("Confirm cancellation" if mode == "cancel" else "Confirm ticket", type="primary", use_container_width=True, key=f"confirm_{action_id}"):
        with st.spinner("Waiting for backend verification..."):
            result = api_client.confirm_action(passenger_id, action_id)
        if result.get("success") is False:
            st.error(result.get("error", "Confirmation failed."))
        else:
            st.success(result.get("answer", "Action completed by the backend."))
            st.session_state.pending_action = None
            st.session_state.last_trace_id = result.get("trace_id")

    if b.button("Go back", use_container_width=True, key=f"back_{action_id}"):
        st.session_state.pending_action = None
        st.rerun()
