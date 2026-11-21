import streamlit as st
from utils.formatters import rupee, status_label


def render_booking_card(booking: dict):
    status = str(booking.get("status", "UNKNOWN")).upper()
    status_class = "confirmed" if status == "CNF" else "waiting"

    with st.container(border=True):
        cols = st.columns([2.4, 1])
        with cols[0]:
            st.markdown(f"**{booking.get('train_number','-')} · {booking.get('train_name','Unnamed train')}**")
            st.caption(f"Booking {booking.get('booking_id','-')}  •  {booking.get('journey_date','-')}")
        with cols[1]:
            st.markdown(f'<span class="status-chip {status_class}">{status_label(status)}</span>', unsafe_allow_html=True)

        route = st.columns(3)
        route[0].markdown(f"**From**\n{booking.get('from_station','-')}")
        route[1].markdown(f"**To**\n{booking.get('to_station','-')}")
        route[2].markdown(f"**Paid**\n{rupee(booking.get('amount_paid'))}")

        st.caption(f"Class: {booking.get('travel_class','-')}  •  PNR: {booking.get('pnr','-')}")
        if st.button("View details", key=f"details_{booking.get('booking_id')}", use_container_width=True):
            st.session_state.selected_booking_id = booking.get("booking_id")
            st.rerun()
