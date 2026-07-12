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
            # Using the stable parameter to avoid SyntaxError/Segmentation fault
            st.dataframe(response.data, use_container_width=True)
        else:
            st.info("No active clan members logged yet.")
            
    except Exception:
        st.error("Live sync momentarily interrupted.")

# Render UI
st.title("The Suilerua Bloodline dashboard")
st.markdown("Welcome to the official clan tracking database. Track your training XP, combat kills, and active warnings.")

# Call the function exactly once here
render_live_dashboard()

# --- SIDEBAR: TRAINER PORTAL ---
# (Keep your existing sidebar logic here, ensuring it is at the bottom)
    if password_input:
        st.sidebar.error("Incorrect Password")
    st.sidebar.info("Regular members can view the leaderboard on the right.")
