import streamlit as st
import time
from supabase import create_client, Client

# --- DATABASE CONNECTION ---
SUPABASE_URL = "https://xvlipedpfyngtwgnrpzt.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inh2bGlwZWRwZnluZ3R3Z25ycHp0Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4Mzg1MjcwNCwiZXhwIjoyMDk5NDI4NzA0fQ.sbc4c1g37cCSxw6ReLOGjotIfs13PFyqumwxrMRgyWk"
TRAINER_PASSWORD = "ClanTrainer2026" 

@st.cache_resource
def init_connection():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase: Client = init_connection()

# --- WEB PAGE LAYOUT ---
st.set_page_config(page_title="The Suilerua Bloodline tracker", page_icon="⚔️", layout="wide")

@st.fragment(run_every="3s")
def render_live_dashboard():
    try:
        # Fetch data with cache-busting
        response = supabase.table("clan_members").select("*").neq("username", f"cache_bypass_{time.time()}").execute()
        
        st.subheader("Active training stats")
        
        if response.data:
            # Using stable parameter to prevent crashes
            st.dataframe(response.data, use_container_width=True)
        else:
            st.info("No active clan members logged yet.")
            
    except Exception:
        st.error("Live sync momentarily interrupted.")

# Render UI
st.title("The Suilerua Bloodline dashboard")
st.markdown("Welcome to the official clan tracking database. Track your training XP, combat kills, and active warnings.")

# Call the function exactly once
render_live_dashboard()

# --- SIDEBAR: TRAINER PORTAL ---
st.sidebar.header("Trainer Portal")
password_input = st.sidebar.text_input("Enter Trainer Password", type="password")

if password_input == TRAINER_PASSWORD:
    st.sidebar.success("Trainer Access Granted")
    st.sidebar.subheader("Update Member Stats")
    
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
                supabase.table("clan_members").upsert({"username": new_user, "xp": 0, "kills": 0, "warnings": 0}, on_conflict="username").execute()
                st.sidebar.success(f"Registered {new_user}!")
                st.rerun()
                
    elif action == "Log Training Stats" and existing_users:
        selected_user = st.sidebar.selectbox("Select Member", existing_users)
        xp_to_add = st.sidebar.number_input("XP to Add", min_value=0, step=1)
        kills_to_add = st.sidebar.number_input("Kills to Add", min_value=0, step=1)
        warnings_to_add = st.sidebar.number_input("Warnings to Add", min_value=0, step=1)
        
        if st.sidebar.button("Submit Training Records"):
            current = supabase.table("clan_members").select("*").eq("username", selected_user).execute().data[0]
            supabase.table("clan_members").update({
                "xp": current['xp'] + xp_to_add, 
                "kills": current['kills'] + kills_to_add, 
                "warnings": current['warnings'] + warnings_to_add
            }).eq("username", selected_user).execute()
            st.sidebar.success(f"Updated stats for {selected_user}!")
            st.rerun()
else:
    if password_input:
        st.sidebar.error("Incorrect Password")
    st.sidebar.info("Regular members can view the leaderboard on the right.")
