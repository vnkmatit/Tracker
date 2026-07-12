import streamlit as st
from supabase import create_client, Client

# --- DATABASE CONNECTION ---
# Replace these with your actual Supabase credentials
SUPABASE_URL = "https://xvlipedpfyngtwgnrpzt.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inh2bGlwZWRwZnluZ3R3Z25ycHp0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODM4NTI3MDQsImV4cCI6MjA5OTQyODcwNH0.4bgMQTbhA5zCT9OAVdQBNCueXcrcAuoWELDnWF7Eci0"

# Secret password for trainers to unlock editing tools
TRAINER_PASSWORD = "ClanTrainer2026" 

# Initialize connection
@st.cache_resource
def init_connection():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase: Client = init_connection()

# --- WEB PAGE LAYOUT ---
st.set_page_config(page_title="Zo Samurai Clan Tracker", page_icon="⚔️", layout="wide")

st.title("⚔️ Zo Samurai Training Dashboard")
st.markdown("Welcome to the official clan database. Track your training XP, combat kills, and active warnings.")

# --- SIDEBAR: TRAINER PORTAL ---
st.sidebar.header("Trainer Portal")
password_input = st.sidebar.text_input("Enter Trainer Password", type="password")

# Check if the trainer typed the correct password
if password_input == TRAINER_PASSWORD:
    st.sidebar.success("Trainer Access Granted")
    st.sidebar.subheader("Update Member Stats")
    
    # Fetch active member names for the dropdown list
    try:
        response = supabase.table("clan_members").select("username").execute()
        existing_users = [row['username'] for row in response.data]
    except Exception:
        existing_users = []
        
    action = st.sidebar.radio("Choose Action", ["Add/Update Member", "Log Training Stats"])
    
    if action == "Add/Update Member":
        new_user = st.sidebar.text_input("Roblox Username").strip()
        if st.sidebar.button("Register/Reset Member"):
            if new_user:
                # Insert or update user details in the cloud
                supabase.table("clan_members").upsert({"username": new_user, "xp": 0, "kills": 0, "warnings": 0}, on_conflict="username").execute()
                st.sidebar.success(f"Registered {new_user}!")
                st.rerun()
                
    elif action == "Log Training Stats" and existing_users:
        selected_user = st.sidebar.selectbox("Select Member", existing_users)
        xp_to_add = st.sidebar.number_input("XP to Add", min_value=0, step=1)
        kills_to_add = st.sidebar.number_input("Kills to Add", min_value=0, step=1)
        warnings_to_add = st.sidebar.number_input("Warnings to Add", min_value=0, step=1)
        
        if st.sidebar.button("Submit Training Records"):
            # Get current records first
            current = supabase.table("clan_members").select("*").eq("username", selected_user).execute().data[0]
            
            # Calculate new tallies
            new_xp = current['xp'] + xp_to_add
            new_kills = current['kills'] + kills_to_add
            new_warnings = current['warnings'] + warnings_to_add
            
            # Push changes back to Supabase cloud
            supabase.table("clan_members").update({"xp": new_xp, "kills": new_kills, "warnings": new_warnings}).eq("username", selected_user).execute()
            st.sidebar.success(f"Updated stats for {selected_user}!")
            st.rerun()
else:
    if password_input:
        st.sidebar.error("Incorrect Password")
    st.sidebar.info("Regular members can view the leaderboard on the right. Trainers must log in to record stats.")

# --- MAIN WINDOW: PUBLIC LEADERBOARD ---
st.subheader("🏆 Clan Leaderboard")

try:
    # Pull data from the cloud, sorted by highest XP first
    data_response = supabase.table("clan_members").select("*").order("xp", desc=True).execute()
    members_data = data_response.data
    
    if members_data:
        # Format the visual table neatly
        formatted_list = []
        for rank, member in enumerate(members_data, start=1):
            formatted_list.append({
                "Rank": rank,
                "Roblox Username": member['username'],
                "Training XP": member['xp'],
                "Logged Kills": member['kills'],
                "Active Warnings": member['warnings']
            })
        st.dataframe(formatted_list, use_container_width=True)
    else:
        st.info("No members registered in the database yet. Trainer must log in to register the first recruit.")
except Exception as e:
    st.error(f"Failed to connect to cloud database: {e}")