import streamlit as st
import time
from supabase import create_client, Client


# --- DATABASE CONNECTION ---
# Replace these with your actual Supabase credentials
SUPABASE_URL = "https://xvlipedpfyngtwgnrpzt.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inh2bGlwZWRwZnluZ3R3Z25ycHp0Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4Mzg1MjcwNCwiZXhwIjoyMDk5NDI4NzA0fQ.sbc4c1g37cCSxw6ReLOGjotIfs13PFyqumwxrMRgyWk"

# Secret password for trainers to unlock editing tools
TRAINER_PASSWORD = "ClanTrainer2026" 

# Initialize connection
@st.cache_resource
def init_connection():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase: Client = init_connection()

# --- WEB PAGE LAYOUT ---
st.set_page_config(page_title="The Suilerua Bloodline tracker", page_icon="⚔️", layout="wide")
# 1. Define a fragment function that automatically updates every 3 seconds

@st.fragment(run_every="3s")
def render_live_dashboard():
    # 2. Everything inside the function MUST have 4 spaces of indentation
    try:
        response = supabase.table("clan_members").select("*").neq("username", f"cache_bypass_{time.time()}").execute()
        existing_users = [row['username'] for row in response.data]
    except Exception:
        existing_users = []

    # Put whatever scoreboard or data rendering code you have right here (indented 4 spaces)
    st.write(existing_users)

# 1. Print the title and welcome text first so they sit at the top of the webpage
st.title("The Suilerua Bloodline dashboard")
st.markdown("Welcome to the official clan tracking database. Track your training XP, combat kills, and active warnings.")

# 2. Call the live fragment loop right below the titles
render_live_dashboard()

# --- SIDEBAR: TRAINER PORTAL ---
st.sidebar.header("Trainer Portal")
password_input = st.sidebar.text_input("Enter Trainer Password", type="password")

# Check if the trainer typed the correct password
if password_input == TRAINER_PASSWORD:
    st.sidebar.success("Trainer Access Granted")
    st.sidebar.subheader("Update Member Stats")
    
    # Fetch active member names for the dropdown list
    try:
        response = supabase.table("clan_members").select("*").neq("username", f"cache_bypass_{time.time()}").execute()
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
st.subheader("Active training stats")

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
        st.dataframe(formatted_list, width="stretch")
    else:
        st.info("No members registered in the database yet. Trainer must log in to register the first recruit.")
except Exception as e:
    st.error(f"Failed to connect to cloud database: {e}")
