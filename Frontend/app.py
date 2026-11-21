from datetime import date, timedelta
import os

import streamlit as st

try:
    from .config import API_BASE_URL, MOCK_MODE, DEFAULT_PASSENGER_ID, REQUEST_TIMEOUT
    from .utils.session import init_session, clear_chat
    from .utils.formatters import rupee, status_label, mask_passenger_id
    from .services.api_client import ApiClient
    from .services.chat_service import normalize_chat_response
    from .services.booking_service import normalize_booking_list
    from .components.sidebar import render_sidebar
    from .components.chat import render_chat_history
    from .components.train_card import render_train_card
    from .components.booking_card import render_booking_card
    from .components.refund_card import render_refund_card
except ImportError:
    from config import API_BASE_URL, MOCK_MODE, DEFAULT_PASSENGER_ID, REQUEST_TIMEOUT
    from utils.session import init_session, clear_chat
    from utils.formatters import rupee, status_label, mask_passenger_id
    from services.api_client import ApiClient
    from services.chat_service import normalize_chat_response
    from services.booking_service import normalize_booking_list
    from components.sidebar import render_sidebar
    from components.chat import render_chat_history
    from components.train_card import render_train_card
    from components.booking_card import render_booking_card
    from components.refund_card import render_refund_card

st.set_page_config(page_title="Ujjwal Rail AI", page_icon="🚆", layout="wide", initial_sidebar_state="expanded")
css_path = os.path.join(os.path.dirname(__file__), "styles", "style.css")
if os.path.exists(css_path):
    with open(css_path, "r", encoding="utf-8") as css_file:
        st.markdown(f"<style>{css_file.read()}</style>", unsafe_allow_html=True)

passenger_id = st.sidebar.text_input("Passenger ID", value=DEFAULT_PASSENGER_ID, max_chars=64)
if not passenger_id.strip():
    st.warning("Passenger ID is required.")
    st.stop()

init_session(passenger_id.strip(), MOCK_MODE)
api = ApiClient(API_BASE_URL, REQUEST_TIMEOUT, MOCK_MODE)
health = api.health_check()
page = render_sidebar(mask_passenger_id(passenger_id), st.session_state.session_id, health, MOCK_MODE)

WELCOME = "Namaste! Welcome to Ujjwal Rail AI. I can help you search trains, check seat availability, understand refund policies, manage bookings and answer your railway-related questions."


def header(title, subtitle):
    st.markdown(f'<div class="page-header"><h1>{title}</h1><p>{subtitle}</p></div>', unsafe_allow_html=True)


def send_chat(prompt):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.spinner("Ujjwal Rail AI is thinking..."):
        response = normalize_chat_response(api.send_chat_message(passenger_id, st.session_state.session_id, prompt))
    st.session_state.messages.append({"role": "assistant", "content": response["answer"]})
    st.session_state.last_trace_id = response.get("trace_id")
    if response["answer_type"] == "confirm_needed" and response.get("preview"):
        st.session_state.pending_action = {"action_id": response.get("action_id"), "preview": response["preview"]}


if page == "AI Chat Assistant":
    header("AI Chat Assistant", "Plan, inquire and manage railway journeys")
    if not st.session_state.messages:
        st.session_state.messages.append({"role": "assistant", "content": WELCOME})
    render_chat_history()

    examples = ["Find trains from Prayagraj to Delhi", "What is the refund policy?", "Show my bookings", "I want to cancel my ticket"]
    cols = st.columns(4)
    for index, example in enumerate(examples):
        if cols[index].button(example, key=f"example_{index}", use_container_width=True):
            send_chat(example)
            st.rerun()

    prompt = st.chat_input("Ask in English, Hindi or Hinglish")
    if prompt:
        send_chat(prompt.strip())
        st.rerun()

    if st.session_state.pending_action:
        pending = st.session_state.pending_action
        preview = pending["preview"]
        st.markdown("### Pending confirmation")
        with st.container(border=True):
            st.write(f"**Action:** {pending['action_id']}")
            st.write(f"**Booking:** {preview.get('booking_id', '-')} · {preview.get('train_name', '-')}")
            st.write(f"**Estimated refund:** {rupee(preview.get('estimated_refund'))}")
            st.caption(preview.get("rules", "Backend-provided cancellation rules"))
        left, right = st.columns(2)
        if left.button("Confirm action", type="primary", use_container_width=True, key="chat_confirm"):
            with st.spinner("Verifying action..."):
                result = api.confirm_action(passenger_id, pending["action_id"])
            if result.get("success") is False:
                st.error(result.get("error", "Confirmation failed."))
            else:
                st.success(result.get("answer", "Action completed by the backend."))
                st.session_state.pending_action = None
        if right.button("Cancel request", use_container_width=True, key="chat_cancel"):
            with st.spinner("Cancelling pending action..."):
                result = api.cancel_action(passenger_id, pending["action_id"])
            if result.get("success") is False:
                st.error(result.get("error", "Could not cancel the pending action."))
            else:
                st.session_state.pending_action = None
                st.success(result.get("answer", "Pending action cancelled."))

    if st.button("Clear chat", use_container_width=True):
        clear_chat()
        st.rerun()

elif page == "Search Trains":
    header("Search Trains", "Find services for your journey")
    with st.container(border=True):
        cols = st.columns(4)
        origin = cols[0].text_input("From Station", placeholder="PRYJ")
        destination = cols[1].text_input("To Station", placeholder="NDLS")
        journey_date = cols[2].date_input("Journey Date", value=date.today() + timedelta(days=1), min_value=date.today())
        travel_class = cols[3].selectbox("Travel Class", ["All Classes", "Sleeper (SL)", "AC 3 Tier (3A)", "AC 2 Tier (2A)", "Chair Car (CC)"])
        if st.button("Search trains", type="primary"):
            if not origin.strip() or not destination.strip():
                st.error("Enter both origin and destination stations.")
            elif MOCK_MODE:
                st.session_state.search_results = [
                    {"train_number":"12304","train_name":"Prayagraj Express","departure_station":origin.upper(),"departure_time":"21:25","arrival_station":destination.upper(),"arrival_time":"06:10","duration":"8h 45m","classes":"SL, 3A, 2A","availability":"Mock: CNF 18","fare":"Mock ₹685"},
                    {"train_number":"22435","train_name":"Vande Bharat Express","departure_station":origin.upper(),"departure_time":"06:05","arrival_station":destination.upper(),"arrival_time":"13:20","duration":"7h 15m","classes":"CC, EC","availability":"Mock: Available 42","fare":"Mock ₹920"},
                ]
            else:
                st.session_state.search_results = None
                st.info("Train search requires a documented backend endpoint. It is not called because no search contract was provided.")
    if st.session_state.get("search_results"):
        st.markdown("### Available trains")
        st.caption("Mock data is for demonstration only. Live values must come from the backend.")
        for train in st.session_state.search_results:
            render_train_card(train)

elif page == "My Bookings":
    header("My Bookings", "Review journeys associated with your passenger ID")
    with st.spinner("Loading bookings..."):
        response = api.get_bookings(passenger_id)
    bookings = normalize_booking_list(response)
    if not bookings:
        st.info(response.get("answer", "No bookings found for this passenger."))
    else:
        for booking in bookings:
            render_booking_card(booking)

elif page == "Confirm Ticket":
    header("Confirm Ticket", "Verify and confirm only a pending backend action")
    action_id = st.text_input("Pending action ID", placeholder="ACT-...")
    if st.button("Load confirmation", type="primary"):
        if not action_id.strip():
            st.error("Enter a pending action ID.")
        elif not MOCK_MODE:
            st.info("Enter only an action ID returned by POST /chat. Confirmation will call POST /actions/{action_id}/confirm.")
            st.session_state.pending_confirmation = action_id.strip()
        else:
            st.session_state.pending_confirmation = action_id.strip()

    if st.session_state.get("pending_confirmation"):
        pending_id = st.session_state.pending_confirmation
        with st.container(border=True):
            st.write(f"**Pending action:** {pending_id}")
            st.warning("Confirm only after verifying the action details from the backend response.")
        left, right = st.columns(2)
        if left.button("Confirm Ticket", type="primary", use_container_width=True):
            with st.spinner("Waiting for backend verification..."):
                result = api.confirm_action(passenger_id, pending_id)
            if result.get("success") is False:
                st.error(result.get("error", "Ticket confirmation failed."))
            else:
                st.success(result.get("answer", "Backend confirmed the action."))
                st.session_state.pending_confirmation = None
        if right.button("Cancel Request", use_container_width=True):
            with st.spinner("Cancelling pending action..."):
                result = api.cancel_action(passenger_id, pending_id)
            if result.get("success") is False:
                st.error(result.get("error", "Could not cancel the request."))
            else:
                st.success(result.get("answer", "Request cancelled."))
                st.session_state.pending_confirmation = None

elif page == "Cancel Ticket":
    header("Cancel Ticket", "Review the refund preview before explicit confirmation")
    with st.spinner("Loading bookings..."):
        booking_response = api.get_bookings(passenger_id)
    bookings = normalize_booking_list(booking_response)
    eligible = [b for b in bookings if b.get("status") not in ("CANCELLED", "Cancelled")]
    if not eligible:
        st.info(booking_response.get("answer", "No active booking is available for cancellation preview."))
    else:
        options = {b["booking_id"]: b for b in eligible}
        selected_id = st.selectbox("Select booking", list(options), format_func=lambda value: f"{value} · {options[value].get('train_name','')}")
        selected = options[selected_id]
        refund_preview = selected.get("refund_preview", {})
        with st.container(border=True):
            left, right = st.columns(2)
            left.write(f"**Booking:** {selected['booking_id']}")
            left.write(f"**Train:** {selected['train_number']} · {selected['train_name']}")
            left.write(f"**Journey:** {selected['journey_date']}")
            left.write(f"**Status:** {status_label(selected['status'])}")
            right.write(f"**Amount paid:** {rupee(selected['amount_paid'])}")
            right.write(f"**Estimated refund:** {rupee(refund_preview.get('estimated_refund'))}")
            right.write(f"**Cancellation charges:** {rupee(refund_preview.get('cancellation_charges'))}")
            st.markdown(refund_preview.get("rules", "Backend-provided rules are required for an official refund preview."))
        st.warning("Cancellation is not submitted until you confirm below.")
        left, right = st.columns(2)
        action_id = f"ACT-CANCEL-{selected_id}"
        if "cancel_executed_ids" not in st.session_state:
            st.session_state.cancel_executed_ids = set()
        already_confirmed = action_id in st.session_state.cancel_executed_ids
        if left.button("Confirmed" if already_confirmed else "Confirm Cancellation", type="primary", use_container_width=True, disabled=already_confirmed):
            with st.spinner("Submitting cancellation to backend..."):
                result = api.confirm_action(passenger_id, action_id)
            if result.get("success") is False:
                st.error(result.get("error", "Cancellation failed."))
            else:
                st.session_state.cancel_executed_ids.add(action_id)
                st.success(result.get("answer", "Cancellation result received from backend."))
                if result.get("refund"):
                    render_refund_card(result["refund"], selected_id)
        if right.button("Go back / Cancel request", use_container_width=True):
            st.info("No cancellation was submitted.")

elif page == "Refund Information":
    header("Refund Information", "Official refund details must be returned by the backend")
    with st.spinner("Loading bookings..."):
        response = api.get_bookings(passenger_id)
    bookings = normalize_booking_list(response)
    if not bookings:
        st.info(response.get("answer", "No booking refund information is available."))
    else:
        options = {b["booking_id"]: b for b in bookings}
        selected_id = st.selectbox("Booking", list(options), format_func=lambda value: f"{value} · {options[value].get('train_name','')}")
        render_refund_card(options[selected_id].get("refund_preview", {}), selected_id)

elif page == "Help & Support":
    header("Help & Support", "Human handover and trace information")
    issue = st.text_area("Describe the issue", placeholder="Example: Main complaint escalate karna chahta hoon...")
    if st.button("Request human support", type="primary"):
        if not issue.strip():
            st.error("Please describe the issue.")
        else:
            with st.spinner("Submitting support request..."):
                response = normalize_chat_response(api.send_chat_message(passenger_id, st.session_state.session_id, "human agent: " + issue.strip()))
            if response["answer_type"] == "handed_to_human":
                st.warning(response["answer"])
                st.session_state.support_status = "Handover response received"
            else:
                st.info(response["answer"])
            st.session_state.last_trace_id = response.get("trace_id")
    if st.session_state.support_status:
        st.success(st.session_state.support_status)

    trace_id = st.text_input("Trace ID", value=st.session_state.last_trace_id or "")
    if st.button("Get trace"):
        if not trace_id.strip():
            st.error("Enter a trace ID.")
        else:
            st.json(api.get_trace(passenger_id, trace_id.strip()))
