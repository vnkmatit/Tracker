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
    "Track your training warnings and combat kills."
)


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
        ).neq(
            "username",
            ""
        ).execute()

        st.sidebar.success("All member stats have been reset!")
        st.rerun()


    # Get members list for dropdown menus
    try:
        response = (
            supabase
            .table("clan_members")
            .select("username")
            .execute()
        )

        existing_users = [
            row["username"]
            for row in response.data
        ]

    except Exception:
        existing_users = []


    # Radio options including the new Delete Member action
    action = st.sidebar.radio(
        "Choose Action",
        [
            "Add/Update Member",
            "Log Stats (Warnings & Kills)",
            "Delete Member"
        ]
    )


    # ACTION 1: ADD / UPDATE MEMBER
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

                st.sidebar.success(
                    f"Registered {new_user}!"
                )

                st.rerun()


    # ACTION 2: LOG STATS
    elif action == "Log Stats (Warnings & Kills)" and existing_users:

        selected_user = st.sidebar.selectbox(
            "Select Member",
            existing_users,
            key="selected_user"
        )

        warnings_to_add = st.sidebar.number_input(
            "Warnings to Add",
            min_value=0,
            step=1
        )
        
        kills_to_add = st.sidebar.number_input(
            "Kills to Add",
            min_value=0,
            step=1
        )

        if st.sidebar.button("Submit Training Records"):

            current = (
                supabase
                .table("clan_members")
                .select("*")
                .eq(
                    "username",
                    selected_user
                )
                .execute()
                .data[0]
            )

            supabase.table("clan_members").update(
                {
                    "warnings": current["warnings"] + warnings_to_add,
                    "kills": current.get("kills", 0) + kills_to_add
                }
            ).eq(
                "username",
                selected_user
            ).execute()

            st.sidebar.success(
                f"Updated stats for {selected_user}!"
            )

            st.rerun()


    # ACTION 3: DELETE MEMBER
    elif action == "Delete Member" and existing_users:

        user_to_delete = st.sidebar.selectbox(
            "Select Member to Delete",
            existing_users,
            key="delete_user"
        )

        if st.sidebar.button("🚨 Permanently Delete Member"):

            supabase.table("clan_members").delete().eq(
                "username",
                user_to_delete
            ).execute()

            st.sidebar.success(
                f"Successfully deleted {user_to_delete}!"
            )

            st.rerun()

    elif action in ["Log Stats (Warnings & Kills)", "Delete Member"] and not existing_users:
        st.sidebar.info("No members registered in the database yet.")


else:

    if password_input:
        st.sidebar.error("Incorrect Password")

    st.sidebar.info(
        "Regular members can view the leaderboards. "
        "Trainers must log in to manage members."
    )



# --- PUBLIC LEADERBOARDS ---
st.subheader("Active training warnings")

try:

    data_response = (
        supabase
        .table("clan_members")
        .select("*")
        .order(
            "warnings",
            desc=True
        )
        .execute()
    )

    members_data = data_response.data

    if members_data:

        # 1. WARNINGS TABLE
        warnings_list = []
        for rank, member in enumerate(members_data, start=1):
            warnings_list.append(
                {
                    "Rank": rank,
                    "Roblox Username": member["username"],
                    "Active Warnings": member["warnings"]
                }
            )

        st.dataframe(
            warnings_list,
            width=600,
            hide_index=True
        )

        st.divider()

        # 2. KING OF THE HILL TABLE
        st.subheader("👑 King of the Hill")

        sorted_by_kills = sorted(members_data, key=lambda x: x.get('kills', 0), reverse=True)

        koth_list = []
        for rank, player in enumerate(sorted_by_kills, start=1):
            koth_list.append(
                {
                    "Rank": rank,
                    "Roblox Username": player["username"],
                    "Total Kills": player.get("kills", 0)
                }
            )

        st.dataframe(
            koth_list,
            width=600,
            hide_index=True
        )

        st.session_state.last_refresh = datetime.now(timezone.utc)

    else:

        st.info(
            "No members registered in the database yet."
        )


except Exception:

    st.code(traceback.format_exc())



# --- REFRESH STATUS ---
st.caption(
    "Auto-refresh: every 10 seconds"
)
