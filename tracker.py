import requests
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
    "Track your training warnings, combat kills, Glads, and TDMS matches."
)


# --- SIDEBAR: TRAINER PORTAL ---
st.sidebar.header("Trainer Portal")

password_input = st.sidebar.text_input(
    "Enter Trainer Password",
    type="password"
)

if password_input == TRAINER_PASSWORD:

    st.sidebar.success("Trainer Access Granted")

    # Fetch members list for dropdown menus
    try:
        response = supabase.table("clan_members").select("username").execute()
        existing_users = [row["username"] for row in response.data]
    except Exception:
        existing_users = []

    # Trainer Options
    action = st.sidebar.radio(
        "Choose Action",
        [
            "Add/Update Member",
            "Log Stats (Warnings & Kills)",
            "Delete Member",
            "Manage Glads Match",
            "Manage TDMS Match",
            "Sync Discord Members"
        ]
    )

    # ACTION 1: ADD / UPDATE MEMBER
    if action == "Add/Update Member":
        with st.sidebar.form("add_member_form"):
            new_user = st.text_input("Roblox Username").strip()
            submit_member = st.form_submit_button("Register/Reset Member")
            if submit_member and new_user:
                supabase.table("clan_members").upsert(
                    {"username": new_user, "xp": 0, "kills": 0, "warnings": 0},
                    on_conflict="username"
                ).execute()
                st.sidebar.success(f"Registered {new_user}!")
                st.rerun()

    # ACTION 2: LOG STATS
    elif action == "Log Stats (Warnings & Kills)" and existing_users:
        with st.sidebar.form("log_stats_form"):
            selected_user = st.selectbox("Select Member", existing_users, key="selected_user")
            warnings_to_add = st.number_input("Warnings to Add", min_value=0, step=1)
            kills_to_add = st.number_input("Kills to Add", min_value=0, step=1)
            submit_stats = st.form_submit_button("Submit Training Records")

            if submit_stats:
                current = supabase.table("clan_members").select("*").eq("username", selected_user).execute().data[0]
                supabase.table("clan_members").update(
                    {
                        "warnings": current["warnings"] + warnings_to_add,
                        "kills": current.get("kills", 0) + kills_to_add
                    }
                ).eq("username", selected_user).execute()

                st.sidebar.success(f"Updated stats for {selected_user}!")
                st.rerun()

    # ACTION 3: DELETE MEMBER
    elif action == "Delete Member" and existing_users:
        with st.sidebar.form("delete_member_form"):
            user_to_delete = st.selectbox("Select Member to Delete", existing_users, key="delete_user")
            submit_delete = st.form_submit_button("🚨 Permanently Delete Member")
            if submit_delete:
                supabase.table("clan_members").delete().eq("username", user_to_delete).execute()
                st.sidebar.success(f"Successfully deleted {user_to_delete}!")
                st.rerun()

    # ACTION 4: MANAGE GLADS MATCH
    elif action == "Manage Glads Match":
        st.sidebar.subheader("⚔️ Glads Live Match Settings")

        try:
            glads_res = supabase.table("glads_match").select("*").eq("id", 1).execute()
            glads_data = glads_res.data[0] if glads_res.data else {
                "team_1_name": "Team 1", "team_1_score": 0, "team_1_members": "",
                "team_2_name": "Team 2", "team_2_score": 0, "team_2_members": ""
            }
        except Exception:
            glads_data = {
                "team_1_name": "Team 1", "team_1_score": 0, "team_1_members": "",
                "team_2_name": "Team 2", "team_2_score": 0, "team_2_members": ""
            }

        with st.sidebar.form("glads_form"):
            t1_name = st.text_input("Team 1 Name", value=glads_data.get("team_1_name", "Team Alpha"), key="g_t1_name")
            t1_score = st.number_input("Team 1 Wins/Score", min_value=0, step=1, value=int(glads_data.get("team_1_score", 0)), key="g_t1_score")
            t1_members = st.text_area("Team 1 Members (comma or line separated)", value=glads_data.get("team_1_members", ""), height=100, key="g_t1_members")

            st.markdown("---")
            t2_name = st.text_input("Team 2 Name", value=glads_data.get("team_2_name", "Team Bravo"), key="g_t2_name")
            t2_score = st.number_input("Team 2 Wins/Score", min_value=0, step=1, value=int(glads_data.get("team_2_score", 0)), key="g_t2_score")
            t2_members = st.text_area("Team 2 Members (comma or line separated)", value=glads_data.get("team_2_members", ""), height=100, key="g_t2_members")

            submit_glads = st.form_submit_button("💾 Update Glads Match")

            if submit_glads:
                supabase.table("glads_match").upsert({
                    "id": 1,
                    "team_1_name": t1_name,
                    "team_1_score": t1_score,
                    "team_1_members": t1_members,
                    "team_2_name": t2_name,
                    "team_2_score": t2_score,
                    "team_2_members": t2_members
                }).execute()

                st.sidebar.success("Glads match score & rosters updated!")
                st.rerun()

    # ACTION 5: MANAGE TDMS MATCH
    elif action == "Manage TDMS Match":
        st.sidebar.subheader("🎯 TDMS Live Match Settings")

        try:
            tdms_res = supabase.table("tdms_match").select("*").eq("id", 1).execute()
            tdms_data = tdms_res.data[0] if tdms_res.data else {
                "team_1_name": "Team 1", "team_1_score": 0, "team_1_members": "",
                "team_2_name": "Team 2", "team_2_score": 0, "team_2_members": ""
            }
        except Exception:
            tdms_data = {
                "team_1_name": "Team 1", "team_1_score": 0, "team_1_members": "",
                "team_2_name": "Team 2", "team_2_score": 0, "team_2_members": ""
            }

        with st.sidebar.form("tdms_form"):
            tdms_t1_name = st.text_input("Team 1 Name", value=tdms_data.get("team_1_name", "Team Alpha"), key="t_t1_name")
            tdms_t1_score = st.number_input("Team 1 Wins/Score", min_value=0, step=1, value=int(tdms_data.get("team_1_score", 0)), key="t_t1_score")
            tdms_t1_members = st.text_area("Team 1 Members (comma or line separated)", value=tdms_data.get("team_1_members", ""), height=100, key="t_t1_members")

            st.markdown("---")
            tdms_t2_name = st.text_input("Team 2 Name", value=tdms_data.get("team_2_name", "Team Bravo"), key="t_t2_name")
            tdms_t2_score = st.number_input("Team 2 Wins/Score", min_value=0, step=1, value=int(tdms_data.get("team_2_score", 0)), key="t_t2_score")
            tdms_t2_members = st.text_area("Team 2 Members (comma or line separated)", value=tdms_data.get("team_2_members", ""), height=100, key="t_t2_members")

            submit_tdms = st.form_submit_button("💾 Update TDMS Match")

            if submit_tdms:
                supabase.table("tdms_match").upsert({
                    "id": 1,
                    "team_1_name": tdms_t1_name,
                    "team_1_score": tdms_t1_score,
                    "team_1_members": tdms_t1_members,
                    "team_2_name": tdms_t2_name,
                    "team_2_score": tdms_t2_score,
                    "team_2_members": tdms_t2_members
                }).execute()

                st.sidebar.success("TDMS match score & rosters updated!")
                st.rerun()

    # ACTION 6: SYNC DISCORD MEMBERS
    elif action == "Sync Discord Members":
        st.sidebar.subheader("🔄 Sync Server Members")
        st.sidebar.caption("Pulls real members from Discord into the database without touching existing stats.")

        with st.sidebar.form("discord_sync_form"):
            submit_sync = st.form_submit_button("Pull Members from Discord")

            if submit_sync:
                BOT_TOKEN = st.secrets.get("DISCORD_BOT_TOKEN")
                GUILD_ID = st.secrets.get("DISCORD_GUILD_ID")

                if not BOT_TOKEN or not GUILD_ID:
                    st.sidebar.error("Missing DISCORD_BOT_TOKEN or DISCORD_GUILD_ID in secrets!")
                else:
                    headers = {"Authorization": f"Bot {BOT_TOKEN}"}
                    url = f"https://discord.com/api/v10/guilds/{GUILD_ID}/members?limit=1000"

                    res = requests.get(url, headers=headers)

                    if res.status_code == 200:
                        discord_members = res.json()
                        added_count = 0

                        for m in discord_members:
                            if m.get("user", {}).get("bot", False):
                                continue

                            username = m.get("nick") or m.get("user", {}).get("global_name") or m.get("user", {}).get("username")

                            if username:
                                existing = supabase.table("clan_members").select("*").eq("username", username).execute()

                                if not existing.data:
                                    supabase.table("clan_members").insert({
                                        "username": username,
                                        "xp": 0,
                                        "kills": 0,
                                        "warnings": 0
                                    }).execute()
                                    added_count += 1

                        st.sidebar.success(f"Synced! Added {added_count} new members.")
                        st.rerun()
                    else:
                        st.sidebar.error(f"Failed to fetch members. Error {res.status_code}: {res.text}")

    elif action in ["Log Stats (Warnings & Kills)", "Delete Member"] and not existing_users:
        st.sidebar.info("No members registered in the database yet.")

else:
    if password_input:
        st.sidebar.error("Incorrect Password")

    st.sidebar.info(
        "Regular members can view the leaderboards. "
        "Trainers must log in to manage members and live scores."
    )


# ==========================================
# FETCH ALL MEMBER DATA ONCE
# ==========================================
members_data = []
try:
    data_response = supabase.table("clan_members").select("*").execute()
    members_data = data_response.data if data_response.data else []
except Exception as e:
    st.error(f"Error connecting to database: {e}")


# ==========================================
# 1. WARNINGS LEADERBOARD
# ==========================================
st.subheader("Active training warnings")

if members_data:
    sorted_by_warnings = sorted(members_data, key=lambda x: x.get('warnings', 0), reverse=True)
    warnings_list = [
        {
            "Rank": rank,
            "Roblox Username": member["username"],
            "Active Warnings": member["warnings"]
        }
        for rank, member in enumerate(sorted_by_warnings, start=1)
    ]
    st.dataframe(warnings_list, width=600, hide_index=True)
else:
    st.info("No members registered in the database yet.")

st.divider()


# ==========================================
# 2. KING OF THE HILL LEADERBOARD
# ==========================================
st.subheader("👑 KOTH Live Scoreboard")

if members_data:
    sorted_by_kills = sorted(members_data, key=lambda x: x.get('kills', 0), reverse=True)
    koth_list = [
        {
            "Rank": rank,
            "Roblox Username": player["username"],
            "Total Kills": player.get("kills", 0)
        }
        for rank, player in enumerate(sorted_by_kills, start=1)
    ]
    st.dataframe(koth_list, width=600, hide_index=True)
else:
    st.info("No member kill stats recorded yet.")

st.divider()


# ==========================================
# 3. GLADS MATCH LIVE SCOREBOARD
# ==========================================
st.subheader("⚔️ Glads Live Scoreboard")

try:
    glads_response = supabase.table("glads_match").select("*").eq("id", 1).execute()
    if glads_response.data:
        g_data = glads_response.data[0]
        
        score_str = f"{g_data['team_1_score']}  —  {g_data['team_2_score']}"
        st.markdown(f"<h1 style='text-align: center; color: #FF4B4B;'>{score_str}</h1>", unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown(f"### 🛡️ {g_data['team_1_name']}")
            st.caption("Team Roster:")
            members_1 = g_data['team_1_members'].strip()
            if members_1:
                formatted_t1 = "\n".join([f"* {m.strip()}" for m in members_1.replace(",", "\n").split("\n") if m.strip()])
                st.markdown(formatted_t1)
            else:
                st.info("No members assigned yet.")

        with col2:
            st.markdown(f"### ⚔️ {g_data['team_2_name']}")
            st.caption("Team Roster:")
            members_2 = g_data['team_2_members'].strip()
            if members_2:
                formatted_t2 = "\n".join([f"* {m.strip()}" for m in members_2.replace(",", "\n").split("\n") if m.strip()])
                st.markdown(formatted_t2)
            else:
                st.info("No members assigned yet.")

    else:
        st.info("No Glads match is currently active.")

except Exception:
    st.info("Glads match table not initialized yet. Please run the SQL setup command in Supabase.")

st.divider()


# ==========================================
# 4. TDMS MATCH LIVE SCOREBOARD
# ==========================================
st.subheader("🎯 TDM Live Scoreboard")

try:
    tdms_response = supabase.table("tdms_match").select("*").eq("id", 1).execute()
    if tdms_response.data:
        t_data = tdms_response.data[0]
        
        score_str = f"{t_data['team_1_score']}  —  {t_data['team_2_score']}"
        st.markdown(f"<h1 style='text-align: center; color: #4B9EFF;'>{score_str}</h1>", unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown(f"### 🛡️ {t_data['team_1_name']}")
            st.caption("Team Roster:")
            members_1 = t_data['team_1_members'].strip()
            if members_1:
                formatted_t1 = "\n".join([f"* {m.strip()}" for m in members_1.replace(",", "\n").split("\n") if m.strip()])
                st.markdown(formatted_t1)
            else:
                st.info("No members assigned yet.")

        with col2:
            st.markdown(f"### ⚔️ {t_data['team_2_name']}")
            st.caption("Team Roster:")
            members_2 = t_data['team_2_members'].strip()
            if members_2:
                formatted_t2 = "\n".join([f"* {m.strip()}" for m in members_2.replace(",", "\n").split("\n") if m.strip()])
                st.markdown(formatted_t2)
            else:
                st.info("No members assigned yet.")

    else:
        st.info("No TDMS match is currently active.")

except Exception:
    st.info("TDMS match table not initialized yet. Please run the SQL setup command in Supabase.")


# --- REFRESH STATUS ---
st.session_state.last_refresh = datetime.now(timezone.utc)
st.caption("Auto-refresh: every 10 seconds")
