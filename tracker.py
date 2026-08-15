import asyncio
from datetime import datetime, timezone
import re
import threading
from urllib.parse import quote

import discord
import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from supabase import Client, create_client

st.set_page_config(
    page_title="The Suilerua Bloodline tracker",
    page_icon="⚔️",
    layout="wide",
)

# Auto refresh every 10 seconds
st_autorefresh(interval=10000, key="stats_refresh")

if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = datetime.now(timezone.utc)

# Fixed Channel ID for Training Logs
LOG_CHANNEL_ID = "1477345559097512028"


# --- KEEP DISCORD BOT ONLINE IN BACKGROUND ---
@st.cache_resource
def run_discord_bot():
    def bot_thread():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True  # Required to read role pings
        client = discord.Client(intents=intents)

        @client.event
        async def on_ready():
            print(f"✅ Bot is ONLINE in Discord as {client.user}")

        @client.event
        async def on_message(message):
            # Ignore messages from the bot itself
            if message.author == client.user:
                return

            # Check if it's the specific training channel
            if message.channel.id == 1477345427576717354:
                # Check strictly for the Trainings role ping (ID: 1480587720442122431)
                target_role_id = 1480587720442122431
                has_training_role = (
                    any(role.id == target_role_id for role in message.role_mentions)
                    or f"<@&{target_role_id}>" in message.content
                )

                if has_training_role:
                    try:
                        await message.add_reaction("✅")
                    except Exception as e:
                        print(f"Failed to add reaction: {e}")

        token = st.secrets.get("DISCORD_BOT_TOKEN")
        if token:
            try:
                loop.run_until_complete(client.start(token))
            except Exception as e:
                print(f"Bot failed to start: {e}")

    thread = threading.Thread(target=bot_thread, daemon=True)
    thread.start()
    return thread

run_discord_bot()


# --- DATABASE CONNECTION ---
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
TRAINER_PASSWORD = st.secrets["TRAINER_PASSWORD"]

try:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.exception(e)
    st.stop()


# --- HELPER: FETCH DISCORD MEMBER NAME-TO-ID MAP (SAFE & NON-BLOCKING) ---
def get_discord_user_map():
    BOT_TOKEN = st.secrets.get("DISCORD_BOT_TOKEN")
    GUILD_ID = st.secrets.get("DISCORD_GUILD_ID")
    if not (BOT_TOKEN and GUILD_ID):
        return {}

    headers = {"Authorization": f"Bot {BOT_TOKEN.strip()}"}
    url = f"https://discord.com/api/v10/guilds/{GUILD_ID.strip()}/members?limit=1000"

    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code != 200:
            return {}

        members = res.json()
        user_map = {}
        for m in members:
            u = m.get("user", {})
            user_id = u.get("id")
            if not user_id:
                continue

            names = [m.get("nick"), u.get("global_name"), u.get("username")]
            for n in names:
                if n:
                    n_str = n.strip().lower()
                    user_map[n_str] = user_id
                    clean_name = re.sub(r"[^\w\s]", "", n_str).strip()
                    if clean_name:
                        user_map[clean_name] = user_id

                    # Map parenthesized handles e.g. "bleh (roxsenpai)" -> "roxsenpai"
                    paren = re.search(r"\((.*?)\)", n_str)
                    if paren:
                        p_name = paren.group(1).strip()
                        if p_name:
                            user_map[p_name] = user_id
                            p_clean = re.sub(r"[^\w\s]", "", p_name).strip()
                            if p_clean:
                                user_map[p_clean] = user_id

        return user_map
    except Exception:
        return {}


# --- HELPER: CONVERT TEXT NAMES TO REAL DISCORD PINGS ---
def convert_to_discord_mentions(text_input: str, user_map: dict) -> str:
    if not text_input or not text_input.strip():
        return ""

    text = text_input.strip()

    # Already a Discord mention
    if re.match(r"^<@!?\d+>$", text):
        return text

    raw_clean = text.lstrip("@").strip()
    lookup_key = raw_clean.lower()
    clean_key = re.sub(r"[^\w\s]", "", raw_clean).strip().lower()

    # 1. Match the entire name string first
    user_id = user_map.get(lookup_key) or user_map.get(clean_key)

    # 2. Check for handle inside parentheses e.g. "bleh (roxsenpai)" -> "roxsenpai"
    if not user_id:
        paren_match = re.search(r"\((.*?)\)", raw_clean)
        if paren_match:
            inside_paren = paren_match.group(1).strip().lower()
            clean_inside = re.sub(r"[^\w\s]", "", inside_paren).strip().lower()
            user_id = user_map.get(inside_paren) or user_map.get(clean_inside)

        # Check part before parentheses e.g. "bleh"
        if not user_id:
            before_paren = raw_clean.split("(")[0].strip().lower()
            clean_before = re.sub(r"[^\w\s]", "", before_paren).strip().lower()
            user_id = user_map.get(before_paren) or user_map.get(clean_before)

    # Return single Discord ping if matched
    if user_id:
        return f"<@{user_id}>"

    # 3. Fallback for multi-username text inputs (e.g. "@user1 @user2")
    tokens = text.split()
    converted = []
    for token in tokens:
        if re.match(r"^<@!?\d+>$", token):
            converted.append(token)
            continue

        ct = token.lstrip("@").strip()
        lk = ct.lower()
        ck = re.sub(r"[^\w\s]", "", ct).strip().lower()

        uid = user_map.get(lk) or user_map.get(ck)
        if uid:
            converted.append(f"<@{uid}>")
        else:
            converted.append(f"@{ct}")

    return " ".join(converted)


# --- HELPER: POST TRAINING LOG TO DISCORD CHANNEL ---
def post_discord_message(channel_id: str, content: str):
    BOT_TOKEN = st.secrets.get("DISCORD_BOT_TOKEN")
    if not BOT_TOKEN:
        return False, "Missing 'DISCORD_BOT_TOKEN' in Streamlit Secrets!"

    headers = {
        "Authorization": f"Bot {BOT_TOKEN.strip()}",
        "Content-Type": "application/json",
    }
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    payload = {"content": content}

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=10)
        if res.status_code in [200, 201]:
            return True, "Successfully posted to Discord!"
        else:
            return False, f"HTTP {res.status_code}: {res.text}"
    except Exception as e:
        return False, f"Request Exception: {str(e)}"


# --- HELPER: FETCH CURRENT DISCORD EVENT ATTENDEES ---
def get_current_event_attendees():
    try:
        evt_res = supabase.table("event_settings").select("*").eq("id", 1).execute()
        if not (evt_res.data and evt_res.data[0].get("channel_id")):
            return []

        evt = evt_res.data[0]
        channel_id = evt["channel_id"]
        target_emoji = evt.get("emoji", "✅")

        BOT_TOKEN = st.secrets.get("DISCORD_BOT_TOKEN")
        GUILD_ID = st.secrets.get("DISCORD_GUILD_ID")

        if not (BOT_TOKEN and GUILD_ID):
            return []

        headers = {"Authorization": f"Bot {BOT_TOKEN.strip()}"}
        messages_url = (
            f"https://discord.com/api/v10/channels/{channel_id}/messages?limit=10"
        )
        msg_res = requests.get(messages_url, headers=headers)

        if msg_res.status_code != 200:
            return []

        active_message_id = None
        for msg in msg_res.json():
            reactions = msg.get("reactions", [])
            if any(
                r.get("emoji", {}).get("name") == target_emoji for r in reactions
            ) or reactions:
                active_message_id = msg["id"]
                break

        if not active_message_id:
            return []

        encoded_emoji = quote(target_emoji)
        reactions_url = f"https://discord.com/api/v10/channels/{channel_id}/messages/{active_message_id}/reactions/{encoded_emoji}?limit=100"
        react_res = requests.get(reactions_url, headers=headers)

        attendees = []
        if react_res.status_code == 200:
            users = react_res.json()
            for u in users:
                if u.get("bot"):
                    continue
                user_id = u["id"]
                member_res = requests.get(
                    f"https://discord.com/api/v10/guilds/{GUILD_ID}/members/{user_id}",
                    headers=headers,
                )
                if member_res.status_code == 200:
                    m = member_res.json()
                    name = (
                        m.get("nick")
                        or m.get("user", {}).get("global_name")
                        or u.get("global_name")
                        or u.get("username")
                    )
                else:
                    name = u.get("global_name") or u.get("username")

                if name:
                    attendees.append(name)

        return attendees
    except Exception:
        return []


# --- PAGE HEADER ---
st.title("The Suilerua Bloodline dashboard")
st.markdown(
    "Welcome to the official clan tracking database. "
    "Track your training warnings, combat kills, Glads, and TDMS matches."
)


# --- SIDEBAR: TRAINER PORTAL ---
st.sidebar.header("Trainer Portal")

password_input = st.sidebar.text_input(
    "Enter Trainer Password", type="password", key="trainer_password_input"
)

if password_input == TRAINER_PASSWORD:

    st.sidebar.success("Trainer Access Granted")

    try:
        response = supabase.table("clan_members").select("username").execute()
        existing_users = [row["username"] for row in response.data]
    except Exception:
        existing_users = []

    action = st.sidebar.radio(
        "Choose Action",
        [
            "Log & Post Training Session",
            "Add/Update Member",
            "Log Stats (Warnings & Kills)",
            "Delete Member",
            "Manage Glads Match",
            "Manage TDMS Match",
            "Set Active Channel Scan",
            "Sync Members by Role",
            "Reset All Member Stats",
        ],
        key="trainer_action_radio",
    )

    # ACTION: LOG & POST TRAINING SESSION TO DISCORD
    if action == "Log & Post Training Session":
        st.sidebar.subheader("📝 Log & Auto-Post Training")

        auto_select_attendees = st.sidebar.checkbox(
            "⚡ Filter by Event Attendees", value=True
        )

        default_selected = []
        if auto_select_attendees:
            current_attendees = get_current_event_attendees()
            default_selected = [u for u in current_attendees if u in existing_users]
            if default_selected:
                st.sidebar.caption(
                    f"Pre-loaded {len(default_selected)} event attendee(s)."
                )

        selected_users = st.sidebar.multiselect(
            "Select Training Participants",
            options=existing_users,
            default=default_selected,
            key="training_participants_select",
        )

        with st.sidebar.form("training_log_form"):
            training_num = st.text_input(
                "Training Title / Number", value="Training 101"
            )

            host = st.text_input("Host Username/Mention", placeholder="@username")
            cohost = st.text_input("Co-Host Username/Mention", placeholder="@username")

            st.markdown("---")
            st.markdown("### Participant Stats (XP & Warnings):")
            p_stats = {}

            for user in selected_users:
                st.markdown(f"**👤 {user}**")
                col1, col2 = st.columns(2)
                with col1:
                    xp_gained = st.number_input(
                        "XP (+)", min_value=0, step=1, value=22, key=f"xp_{user}"
                    )
                with col2:
                    w_gained = st.number_input(
                        "Warn (+)", min_value=0, step=1, value=0, key=f"tw_{user}"
                    )
                p_stats[user] = {"xp": xp_gained, "warnings": w_gained}

            st.markdown("---")
            st.markdown("### Match Winners & Highlights:")
            mvps = st.text_input("MVPs", placeholder="e.g. @username")
            koth = st.text_input("KOTH Winner", placeholder="e.g. @username")
            glads = st.text_input(
                "Glads Participants/Winners", placeholder="e.g. @username"
            )
            tdms = st.text_input("TDMS Winners", placeholder="e.g. @username")
            ffa = st.text_input("FFA Winner", placeholder="e.g. @username")
            twos = st.text_input("2s Winners", placeholder="e.g. @username")
            notes = st.text_area(
                "Notes / Comments",
                placeholder="e.g. DM me if I forgot you in the logs.",
            )

            submit_training = st.form_submit_button(
                "🚀 Save Stats & Post to Discord"
            )

            if submit_training:
                try:
                    # 1. Update Supabase Database Stats
                    for user, data in p_stats.items():
                        current = (
                            supabase.table("clan_members")
                            .select("*")
                            .eq("username", user)
                            .execute()
                            .data
                        )
                        if current:
                            curr_row = current[0]
                            new_xp = curr_row.get("xp", 0) + data["xp"]
                            new_w = curr_row.get("warnings", 0) + data["warnings"]
                            supabase.table("clan_members").update(
                                {"xp": new_xp, "warnings": new_w}
                            ).eq("username", user).execute()

                    # 2. Fetch Discord Member Map (Safe Fallback if API fails)
                    user_map = get_discord_user_map()

                    # 3. Format Discord Message
                    log_lines = [f"**{training_num}**\n"]

                    if host.strip():
                        log_lines.append(
                            f"**Host:** {convert_to_discord_mentions(host, user_map)}"
                        )
                    if cohost.strip():
                        log_lines.append(
                            f"**Co-host:** {convert_to_discord_mentions(cohost, user_map)}"
                        )

                    if p_stats:
                        log_lines.append("\n**Participants:**")
                        for user, data in p_stats.items():
                            mention = convert_to_discord_mentions(user, user_map)
                            w_str = f" w{data['warnings']}" if data["warnings"] > 0 else ""
                            log_lines.append(f"{mention} {data['xp']}xp{w_str}")

                    highlights = []
                    if mvps.strip():
                        highlights.append(
                            f"**Mvps:** {convert_to_discord_mentions(mvps, user_map)}"
                        )
                    if koth.strip():
                        highlights.append(
                            f"**koth:** {convert_to_discord_mentions(koth, user_map)}"
                        )
                    if glads.strip():
                        highlights.append(
                            f"**Glads:** {convert_to_discord_mentions(glads, user_map)}"
                        )
                    if tdms.strip():
                        highlights.append(
                            f"**Tdms:** {convert_to_discord_mentions(tdms, user_map)}"
                        )
                    if ffa.strip():
                        highlights.append(
                            f"**Ffa:** {convert_to_discord_mentions(ffa, user_map)}"
                        )
                    if twos.strip():
                        highlights.append(
                            f"**2s:** {convert_to_discord_mentions(twos, user_map)}"
                        )

                    if highlights:
                        log_lines.append("")
                        log_lines.extend(highlights)

                    if notes.strip():
                        log_lines.append(f"\n**Notes:** {notes.strip()}")

                    full_message = "\n".join(log_lines)

                    # 4. Post Message to Discord
                    success, msg = post_discord_message(LOG_CHANNEL_ID, full_message)
                    if success:
                        st.sidebar.success("✅ Training logged in DB and posted to Discord!")
                    else:
                        st.sidebar.error(
                            f"⚠️ Saved to DB, but Discord post failed:\n\n`{msg}`"
                        )

                except Exception as err:
                    st.sidebar.error(f"❌ Error during submission: {str(err)}")

    # ACTION: ADD / UPDATE MEMBER
    elif action == "Add/Update Member":
        with st.sidebar.form("add_member_form"):
            new_user = st.text_input("Roblox Username").strip()
            submit_member = st.form_submit_button("Register/Reset Member")
            if submit_member and new_user:
                supabase.table("clan_members").upsert(
                    {"username": new_user, "xp": 0, "kills": 0, "warnings": 0},
                    on_conflict="username",
                ).execute()
                st.sidebar.success(f"Registered {new_user}!")
                st.rerun()

    # ACTION: INDIVIDUAL STAT LOGGING FOR EVENT ATTENDEES
    elif action == "Log Stats (Warnings & Kills)" and existing_users:
        st.sidebar.subheader("Log Individual Stats")

        auto_select_attendees = st.sidebar.checkbox(
            "⚡ Filter by Event Attendees", value=True
        )

        default_selected = []
        if auto_select_attendees:
            current_attendees = get_current_event_attendees()
            default_selected = [u for u in current_attendees if u in existing_users]
            if not default_selected:
                st.sidebar.caption(
                    "No event attendees found in DB. Select members manually below."
                )
            else:
                st.sidebar.caption(
                    f"Pre-loaded {len(default_selected)} event attendee(s)."
                )

        selected_users = st.sidebar.multiselect(
            "Select Attendees to Edit",
            options=existing_users,
            default=default_selected,
            key="selected_users_stats",
        )

        if selected_users:
            with st.sidebar.form("log_stats_form"):
                st.markdown("### Enter Stats per Member:")
                stats_input = {}

                for user in selected_users:
                    st.markdown(f"**👤 {user}**")
                    col1, col2 = st.columns(2)
                    with col1:
                        w_add = st.number_input(
                            "Warn (+)", min_value=0, step=1, key=f"w_{user}"
                        )
                    with col2:
                        k_add = st.number_input(
                            "Kills (+)", min_value=0, step=1, key=f"k_{user}"
                        )
                    stats_input[user] = {"warnings": w_add, "kills": k_add}
                    st.markdown("---")

                submit_stats = st.form_submit_button("💾 Save All Member Stats")

                if submit_stats:
                    updated_count = 0
                    for user, data in stats_input.items():
                        if data["warnings"] > 0 or data["kills"] > 0:
                            current = (
                                supabase.table("clan_members")
                                .select("*")
                                .eq("username", user)
                                .execute()
                                .data[0]
                            )
                            supabase.table("clan_members").update({
                                "warnings": current["warnings"] + data["warnings"],
                                "kills": current.get("kills", 0) + data["kills"],
                            }).eq("username", user).execute()
                            updated_count += 1

                    st.sidebar.success(f"Updated stats for {updated_count} member(s)!")
                    st.rerun()

    # ACTION: DELETE MEMBER
    elif action == "Delete Member" and existing_users:
        with st.sidebar.form("delete_member_form"):
            user_to_delete = st.selectbox(
                "Select Member to Delete", existing_users, key="delete_user"
            )
            submit_delete = st.form_submit_button("🚨 Permanently Delete Member")
            if submit_delete:
                supabase.table("clan_members").delete().eq(
                    "username", user_to_delete
                ).execute()
                st.sidebar.success(f"Successfully deleted {user_to_delete}!")
                st.rerun()

    # ACTION: MANAGE GLADS MATCH
    elif action == "Manage Glads Match":
        st.sidebar.subheader("⚔️ Glads Live Match Settings")

        try:
            glads_res = supabase.table("glads_match").select("*").eq("id", 1).execute()
            glads_data = (
                glads_res.data[0]
                if glads_res.data
                else {
                    "team_1_name": "Team 1",
                    "team_1_score": 0,
                    "team_1_members": "",
                    "team_2_name": "Team 2",
                    "team_2_score": 0,
                    "team_2_members": "",
                }
            )
        except Exception:
            glads_data = {
                "team_1_name": "Team 1",
                "team_1_score": 0,
                "team_1_members": "",
                "team_2_name": "Team 2",
                "team_2_score": 0,
                "team_2_members": "",
            }

        with st.sidebar.form("glads_form"):
            t1_name = st.text_input(
                "Team 1 Name",
                value=glads_data.get("team_1_name", "Team Alpha"),
                key="g_t1_name",
            )
            t1_score = st.number_input(
                "Team 1 Wins/Score",
                min_value=0,
                step=1,
                value=int(glads_data.get("team_1_score", 0)),
                key="g_t1_score",
            )
            t1_members = st.text_area(
                "Team 1 Members (comma or line separated)",
                value=glads_data.get("team_1_members", ""),
                height=100,
                key="g_t1_members",
            )

            st.markdown("---")
            t2_name = st.text_input(
                "Team 2 Name",
                value=glads_data.get("team_2_name", "Team Bravo"),
                key="g_t2_name",
            )
            t2_score = st.number_input(
                "Team 2 Wins/Score",
                min_value=0,
                step=1,
                value=int(glads_data.get("team_2_score", 0)),
                key="g_t2_score",
            )
            t2_members = st.text_area(
                "Team 2 Members (comma or line separated)",
                value=glads_data.get("team_2_members", ""),
                height=100,
                key="g_t2_members",
            )

            submit_glads = st.form_submit_button("💾 Update Glads Match")

            if submit_glads:
                supabase.table("glads_match").upsert({
                    "id": 1,
                    "team_1_name": t1_name,
                    "team_1_score": t1_score,
                    "team_1_members": t1_members,
                    "team_2_name": t2_name,
                    "team_2_score": t2_score,
                    "team_2_members": t2_members,
                }).execute()

                st.sidebar.success("Glads match score & rosters updated!")
                st.rerun()

    # ACTION: MANAGE TDMS MATCH
    elif action == "Manage TDMS Match":
        st.sidebar.subheader("🎯 TDMS Live Match Settings")

        try:
            tdms_res = supabase.table("tdms_match").select("*").eq("id", 1).execute()
            tdms_data = (
                tdms_res.data[0]
                if tdms_res.data
                else {
                    "team_1_name": "Team 1",
                    "team_1_score": 0,
                    "team_1_members": "",
                    "team_2_name": "Team 2",
                    "team_2_score": 0,
                    "team_2_members": "",
                }
            )
        except Exception:
            tdms_data = {
                "team_1_name": "Team 1",
                "team_1_score": 0,
                "team_1_members": "",
                "team_2_name": "Team 2",
                "team_2_score": 0,
                "team_2_members": "",
            }

        with st.sidebar.form("tdms_form"):
            tdms_t1_name = st.text_input(
                "Team 1 Name",
                value=tdms_data.get("team_1_name", "Team Alpha"),
                key="t_t1_name",
            )
            tdms_t1_score = st.number_input(
                "Team 1 Wins/Score",
                min_value=0,
                step=1,
                value=int(tdms_data.get("team_1_score", 0)),
                key="t_t1_score",
            )
            tdms_t1_members = st.text_area(
                "Team 1 Members (comma or line separated)",
                value=tdms_data.get("team_1_members", ""),
                height=100,
                key="t_t1_members",
            )

            st.markdown("---")
            tdms_t2_name = st.text_input(
                "Team 2 Name",
                value=tdms_data.get("team_2_name", "Team Bravo"),
                key="t_t2_name",
            )
            tdms_t2_score = st.number_input(
                "Team 2 Wins/Score",
                min_value=0,
                step=1,
                value=int(tdms_data.get("team_2_score", 0)),
                key="t_t2_score",
            )
            tdms_t2_members = st.text_area(
                "Team 2 Members (comma or line separated)",
                value=tdms_data.get("team_2_members", ""),
                height=100,
                key="t_t2_members",
            )

            submit_tdms = st.form_submit_button("💾 Update TDMS Match")

            if submit_tdms:
                supabase.table("tdms_match").upsert({
                    "id": 1,
                    "team_1_name": tdms_t1_name,
                    "team_1_score": tdms_t1_score,
                    "team_1_members": tdms_t1_members,
                    "team_2_name": tdms_t2_name,
                    "team_2_score": tdms_t2_score,
                    "team_2_members": tdms_t2_members,
                }).execute()

                st.sidebar.success("TDMS match score & rosters updated!")
                st.rerun()

    # ACTION: SET ACTIVE CHANNEL SCAN
    elif action == "Set Active Channel Scan":
        st.sidebar.subheader("📌 Auto-Scan Channel Settings")
        st.sidebar.caption(
            "Set the channel ID and emoji. The bot will automatically inspect"
            " recent messages to find the latest event."
        )

        try:
            evt_res = (
                supabase.table("event_settings").select("*").eq("id", 1).execute()
            )
            evt_curr = evt_res.data[0] if evt_res.data else {}
        except Exception:
            evt_curr = {}

        with st.sidebar.form("event_settings_form"):
            evt_name = st.text_input(
                "Event Title", value=evt_curr.get("event_name", "Clan Practice")
            )
            c_id = st.text_input(
                "Discord Channel ID", value=evt_curr.get("channel_id", "")
            ).strip()
            emoji_val = st.text_input(
                "Target Emoji", value=evt_curr.get("emoji", "✅")
            ).strip()

            submit_evt = st.form_submit_button("💾 Save Settings")

            if submit_evt:
                supabase.table("event_settings").upsert({
                    "id": 1,
                    "event_name": evt_name,
                    "channel_id": c_id,
                    "message_id": "",
                    "emoji": emoji_val,
                }).execute()

                st.sidebar.success("Auto-scan settings saved!")
                st.rerun()

    # ACTION: SYNC MEMBERS BY DISCORD ROLE
    elif action == "Sync Members by Role":
        st.sidebar.subheader("🎭 Sync Members by Discord Role")
        st.sidebar.caption(
            "Fetches all server members holding a specific Role ID and adds them to"
            " clan_members."
        )

        with st.sidebar.form("role_sync_form"):
            role_id_input = st.text_input("Discord Role ID").strip()
            submit_role_sync = st.form_submit_button("Import Role Members")

            if submit_role_sync:
                BOT_TOKEN = st.secrets.get("DISCORD_BOT_TOKEN")
                GUILD_ID = st.secrets.get("DISCORD_GUILD_ID")

                if not BOT_TOKEN or not GUILD_ID:
                    st.sidebar.error(
                        "Missing DISCORD_BOT_TOKEN or DISCORD_GUILD_ID in secrets!"
                    )
                elif not role_id_input:
                    st.sidebar.error("Please enter a valid Role ID!")
                else:
                    headers = {"Authorization": f"Bot {BOT_TOKEN.strip()}"}
                    guild_members_url = f"https://discord.com/api/v10/guilds/{GUILD_ID.strip()}/members?limit=1000"

                    res = requests.get(guild_members_url, headers=headers, timeout=10)

                    if res.status_code == 200:
                        all_members = res.json()
                        added_count = 0
                        matched_count = 0

                        for m in all_members:
                            user_obj = m.get("user", {})
                            if user_obj.get("bot", False):
                                continue

                            member_roles = m.get("roles", [])

                            if role_id_input in member_roles:
                                matched_count += 1
                                username = (
                                    m.get("nick")
                                    or user_obj.get("global_name")
                                    or user_obj.get("username")
                                )

                                if username:
                                    existing = (
                                        supabase.table("clan_members")
                                        .select("*")
                                        .eq("username", username)
                                        .execute()
                                    )

                                    if not existing.data:
                                        supabase.table("clan_members").insert({
                                            "username": username,
                                            "xp": 0,
                                            "kills": 0,
                                            "warnings": 0,
                                        }).execute()
                                        added_count += 1

                        st.sidebar.success(
                            f"Synced! Found {matched_count} members with role, added"
                            f" {added_count} new members to DB."
                        )
                        st.rerun()
                    else:
                        st.sidebar.error(
                            f"Failed to fetch server members. Error {res.status_code}:"
                            f" {res.text}"
                        )

    # ACTION: RESET ALL MEMBER STATS
    elif action == "Reset All Member Stats":
        st.sidebar.subheader("🚨 Reset All Member Stats")
        st.sidebar.warning(
            "This will set Warnings and Kills back to 0 for EVERY member in the"
            " database."
        )

        with st.sidebar.form("reset_all_form"):
            confirm = st.checkbox("I confirm I want to reset all stats")
            submit_reset = st.form_submit_button("Wipe All Warnings & Kills")

            if submit_reset:
                if confirm:
                    supabase.table("clan_members").update(
                        {"warnings": 0, "kills": 0}
                    ).neq("username", "").execute()
                    st.sidebar.success("Successfully reset stats for all members!")
                    st.rerun()
                else:
                    st.sidebar.error("Please check the confirmation box first.")

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
# 1. LIVE EVENT ATTENDANCE BOARD
# ==========================================
try:
    attendees_names = get_current_event_attendees()
    evt_res = supabase.table("event_settings").select("*").eq("id", 1).execute()

    if evt_res.data and evt_res.data[0].get("channel_id"):
        evt = evt_res.data[0]
        st.subheader(f"📋 Live Event Sign-ups: {evt['event_name']}")

        if attendees_names:
            attendees_list = [
                {"#": idx, "Attending Member": name}
                for idx, name in enumerate(attendees_names, start=1)
            ]
            st.dataframe(attendees_list, width=500, height=300, hide_index=True)
        else:
            st.info("No reactions recorded yet for the latest message.")

        st.divider()
except Exception:
    pass


# ==========================================
# 2. XP LEADERBOARD
# ==========================================
st.subheader("⭐ Clan XP Leaderboard")

if members_data:
    sorted_by_xp = sorted(
        members_data, key=lambda x: x.get("xp", 0), reverse=True
    )
    xp_list = [
        {
            "Rank": rank,
            "Roblox Username": member["username"],
            "Total XP": member.get("xp", 0),
        }
        for rank, member in enumerate(sorted_by_xp, start=1)
    ]
    st.dataframe(xp_list, width=600, height=400, hide_index=True)
else:
    st.info("No members registered in the database yet.")

st.divider()


# ==========================================
# 3. WARNINGS LEADERBOARD
# ==========================================
st.subheader("Active training warnings")

if members_data:
    sorted_by_warnings = sorted(
        members_data, key=lambda x: x.get("warnings", 0), reverse=True
    )
    warnings_list = [
        {
            "Rank": rank,
            "Roblox Username": member["username"],
            "Active Warnings": member["warnings"],
        }
        for rank, member in enumerate(sorted_by_warnings, start=1)
    ]
    st.dataframe(warnings_list, width=600, height=400, hide_index=True)
else:
    st.info("No members registered in the database yet.")

st.divider()


# ==========================================
# 4. KING OF THE HILL LEADERBOARD
# ==========================================
st.subheader("👑 KOTH Live Scoreboard")

if members_data:
    sorted_by_kills = sorted(
        members_data, key=lambda x: x.get("kills", 0), reverse=True
    )
    koth_list = [
        {
            "Rank": rank,
            "Roblox Username": player["username"],
            "Total Kills": player.get("kills", 0),
        }
        for rank, player in enumerate(sorted_by_kills, start=1)
    ]
    st.dataframe(koth_list, width=600, height=400, hide_index=True)
else:
    st.info("No member kill stats recorded yet.")

st.divider()


# ==========================================
# 5. GLADS MATCH LIVE SCOREBOARD
# ==========================================
st.subheader("⚔️ Glads Live Scoreboard")

try:
    glads_response = (
        supabase.table("glads_match").select("*").eq("id", 1).execute()
    )
    if glads_response.data:
        g_data = glads_response.data[0]

        score_str = f"{g_data['team_1_score']}  —  {g_data['team_2_score']}"
        st.markdown(
            f"<h1 style='text-align: center; color: #FF4B4B;'>{score_str}</h1>",
            unsafe_allow_html=True,
        )

        col1, col2 = st.columns(2)

        with col1:
            st.markdown(f"### 🛡️ {g_data['team_1_name']}")
            st.caption("Team Roster:")
            members_1 = g_data["team_1_members"].strip()
            if members_1:
                formatted_t1 = "\n".join([
                    f"* {m.strip()}"
                    for m in members_1.replace(",", "\n").split("\n")
                    if m.strip()
                ])
                st.markdown(formatted_t1)
            else:
                st.info("No members assigned yet.")

        with col2:
            st.markdown(f"### ⚔️ {g_data['team_2_name']}")
            st.caption("Team Roster:")
            members_2 = g_data["team_2_members"].strip()
            if members_2:
                formatted_t2 = "\n".join([
                    f"* {m.strip()}"
                    for m in members_2.replace(",", "\n").split("\n")
                    if m.strip()
                ])
                st.markdown(formatted_t2)
            else:
                st.info("No members assigned yet.")

    else:
        st.info("No Glads match is currently active.")

except Exception:
    st.info("Glads match table not initialized yet.")

st.divider()


# ==========================================
# 6. TDMS MATCH LIVE SCOREBOARD
# ==========================================
st.subheader("🎯 TDM Live Scoreboard")

try:
    tdms_response = supabase.table("tdms_match").select("*").eq("id", 1).execute()
    if tdms_response.data:
        t_data = tdms_response.data[0]

        score_str = f"{t_data['team_1_score']}  —  {t_data['team_2_score']}"
        st.markdown(
            f"<h1 style='text-align: center; color: #4B9EFF;'>{score_str}</h1>",
            unsafe_allow_html=True,
        )

        col1, col2 = st.columns(2)

        with col1:
            st.markdown(f"### 🛡️ {t_data['team_1_name']}")
            st.caption("Team Roster:")
            members_1 = t_data["team_1_members"].strip()
            if members_1:
                formatted_t1 = "\n".join([
                    f"* {m.strip()}"
                    for m in members_1.replace(",", "\n").split("\n")
                    if m.strip()
                ])
                st.markdown(formatted_t1)
            else:
                st.info("No members assigned yet.")

        with col2:
            st.markdown(f"### ⚔️ {t_data['team_2_name']}")
            st.caption("Team Roster:")
            members_2 = t_data["team_2_members"].strip()
            if members_2:
                formatted_t2 = "\n".join([
                    f"* {m.strip()}"
                    for m in members_2.replace(",", "\n").split("\n")
                    if m.strip()
                ])
                st.markdown(formatted_t2)
            else:
                st.info("No members assigned yet.")

    else:
        st.info("No TDMS match is currently active.")

except Exception:
    st.info("TDMS match table not initialized yet.")


# --- REFRESH STATUS ---
st.session_state.last_refresh = datetime.now(timezone.utc)
st.caption("Auto-refresh: every 10 seconds")
