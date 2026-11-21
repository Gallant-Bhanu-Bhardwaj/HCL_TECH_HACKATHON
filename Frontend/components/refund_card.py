import streamlit as st
from utils.formatters import rupee


def render_refund_card(refund: dict, booking_id: str = None):
    with st.container(border=True):
        if booking_id:
            st.caption(f"Booking ID: {booking_id}")
        cols = st.columns(3)
        cols[0].metric("Estimated refund", rupee(refund.get("estimated_refund") or refund.get("estimated_refund_amount")))
        cols[1].metric("Cancellation charges", rupee(refund.get("cancellation_charges") or refund.get("charges")))
        cols[2].metric("Eligibility", "Eligible" if refund.get("eligible", True) else "Not eligible")
        st.markdown("**Refund processing**")
        st.write(refund.get("processing", refund.get("processing_info", "Backend-provided details are shown here.")))
        st.markdown("**Applicable policy**")
        st.write(refund.get("rules", refund.get("policy_reference", "Policy reference not provided by backend.")))
