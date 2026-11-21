import streamlit as st


def render_chat_history():
    for message in st.session_state.messages:
        role = message["role"]
        with st.chat_message(role, avatar="🧑🏻" if role == "user" else "🚆"):
            st.markdown(message["content"])


def render_answer(response: dict):
    answer_type = response.get("answer_type", "answer")
    answer = response.get("answer", "No response received.")

    if answer_type == "clarification":
        st.info(answer)
    elif answer_type == "confirm_needed":
        st.warning(answer)
    elif answer_type == "action_done":
        st.success(answer)
    elif answer_type == "handed_to_human":
        st.warning(answer)
    elif answer_type in ("not_found", "refusal"):
        st.error(answer)
    else:
        st.markdown(answer)

    if response.get("trace_id"):
        st.caption(f"Trace ID: {response['trace_id']}")
