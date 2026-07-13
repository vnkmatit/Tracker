import streamlit as st
from supabase import create_client, Client
from datetime import datetime, timezone
from streamlit_autorefresh import st_autorefresh
import traceback

st.set_page_config(
    page_title="The Suilerua Bloodline tracker",
    page_icon="⚔️",
    layout="wide"
)

# Auto refresh every 10 seconds
st_autorefresh(interval=10000, key="stats_refresh")

if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = datetime.now(timezone.utc)

# --- DATABASE CONNECTION ---
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
TRAINER_PASSWORD = st.secrets["TRAINER_PASSWORD"]

try:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.exception(e)
    st.stop()

# --- PAGE HEADER ---
st.title("The Suilerua Bloodline dashboard")
st.markdown(
    "Welcome to the official clan tracking database. "
    "Track your training XP, combat kills, and active warnings."
)

# --- SIDEBAR: TRAINER PORTAL ---
# --- SIDEBAR: TRAINER PORTAL ---
st.sidebar.header("Trainer Portal")

password_input = st.sidebar.text_input(
    "Enter Trainer Password",
    type="password"
)

if password_input == TRAINER_PASSWORD:
    st.sidebar.success("Trainer Access Granted")
    st.sidebar.subheader("Update Member Stats")

    # Reset all stats button
    if st.sidebar.button("Reset All Training Stats"):
        supabase.table("clan_members").update(
            {
                "xp": 0,
                "kills": 0,
                "warnings": 0
            }
        ).neq("username", "").execute()

        st.sidebar.success("All member stats have been reset!")
        st.rerun()

    # Get members
    try:
        response = supabase.table("clan_members").select("username").execute()
        existing_users = [row["username"] for row in response.data]
    except Exception:
        existing_users = []

    action = st.sidebar.radio(
        "Choose Action",
        ["Add/Update Member", "Log Training Stats"]
    )

    if action == "Add/Update Member":

        new_user = st.sidebar.text_input(
            "Roblox Username"
        ).strip()

        if st.sidebar.button("Register/Reset Member"):
            if new_user:
                supabase.table("clan_members").upsert(
                    {
                        "username": new_user,
                        "xp": 0,
                        "kills": 0,
                        "warnings": 0
                    },
                    on_conflict="username"
                ).execute()

                st.sidebar.success(f"Registered {new_user}!")
                st.rerun()

    elif action == "Log Training Stats" and existing_users:

        selected_user = st.sidebar.selectbox(
            "Select Member",
            existing_users,
            key="selected_user"
        )

        xp_to_add = st.sidebar.number_input(
            "XP to Add",
            min_value=0,
            step=1
        )

        kills_to_add = st.sidebar.number_input(
            "Kills to Add",
            min_value=0,
            step=1
        )

        warnings_to_add = st.sidebar.number_input(
            "Warnings to Add",
            min_value=0,
            step=1
        )

        if st.sidebar.button("Submit Training Records"):

            current = (
                supabase
                .table("clan_members")
                .select("*")
                .eq("username", selected_user)
                .execute()
                .data[0]
            )

            supabase.table("clan_members").update(
                {
                    "xp": current["xp"] + xp_to_add,
                    "kills": current["kills"] + kills_to_add,
                    "warnings": current["warnings"] + warnings_to_add
                }
            ).eq(
                "username",
                selected_user
            ).execute()

            st.sidebar.success(
                f"Updated stats for {selected_user}!"
            )

            st.rerun()

else:
    if password_input:
        st.sidebar.error("Incorrect Password")

    st.sidebar.info(
        "Regular members can view the leaderboard. "
        "Trainers must log in to record stats."
    )
# --- MAIN WINDOW: PUBLIC LEADERBOARD ---
st.subheader("Active training stats")

try:
    data_response = (
        supabase
        .table("clan_members")
        .select("*")
        .order("xp", desc=True)
        .execute()
    )

    members_data = data_response.data

    if members_data:

        formatted_list = []

        for rank, member in enumerate(members_data, start=1):
            formatted_list.append(
    {
        "Rank": rank,
        "Roblox Username": member["username"],
        "Active Warnings": member["warnings"]
    }
)

        st.dataframe(
            formatted_list,
            use_container_width=True
        )

        # Save when leaderboard was updated
        st.session_state.last_refresh = datetime.now(timezone.utc)

    else:
        st.info(
            "No members registered in the database yet."
        )

except Exception:
    st.code(traceback.format_exc())


# --- REFRESH STATUS ---
seconds_ago = int(
    (
        datetime.now(timezone.utc)
        - st.session_state.last_refresh
    ).total_seconds()
)


st.caption("Auto-refresh: every 10 seconds")
