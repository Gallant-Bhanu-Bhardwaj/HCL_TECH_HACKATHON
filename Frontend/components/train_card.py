import streamlit as st


def render_train_card(train: dict):
    with st.container(border=True):
        top = st.columns([3, 1.2])
        with top[0]:
            st.markdown(f"### {train.get('train_number', '-')} · {train.get('train_name', 'Unnamed train')}")
        with top[1]:
            st.metric("Fare", train.get("fare", "Mock"))

        route = st.columns(3)
        route[0].markdown(f"**Departure**\n{train.get('departure_station','-')}  \n**{train.get('departure_time','-')}**")
        route[1].markdown(f"**Duration**\n{train.get('duration','-')}")
        route[2].markdown(f"**Arrival**\n{train.get('arrival_station','-')}  \n**{train.get('arrival_time','-')}**")

        details = st.columns(3)
        details[0].caption(f"Classes: {train.get('classes','-')}")
        details[1].caption(f"Availability: {train.get('availability','-')}")
        details[2].button("Book / Continue", key=f"train_{train.get('train_number','x')}", use_container_width=True)
