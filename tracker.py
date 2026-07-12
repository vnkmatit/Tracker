import streamlit as st
from supabase import create_client, Client

# --- SETUP ---
SUPABASE_URL = "https://xvlipedpfyngtwgnrpzt.supabase.co"
# REPLACE THIS WITH YOUR ACTUAL SERVICE_ROLE KEY FROM SUPABASE SETTINGS
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inh2bGlwZWRwZnluZ3R3Z25ycHp0Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4Mzg1MjcwNCwiZXhwIjoyMDk5NDI4NzA0fQ.sbc4c1g37cCSxw6ReLOGjotIfs13PFyqumwxrMRgyWk" 

@st.cache_resource
def init_connection():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_connection()

st.set_page_config(page_title="The Suilerua Bloodline tracker", layout="wide")
st.title("The Suilerua Bloodline dashboard")

# Manual Refresh Button (Stable alternative to st.fragment)
if st.button("Refresh Data"):
    st.rerun()

# --- DISPLAY DATA ---
try:
    response = supabase.table("clan_members").select("*").execute()
    if response.data:
        st.subheader("Active training stats")
        st.dataframe(response.data, use_container_width=True)
    else:
        st.info("No active clan members.")
except Exception as e:
    st.error(f"Sync error: {e}")

# --- SIDEBAR (Ensure proper indentation here!) ---
st.sidebar.header("Trainer Portal")
password_input = st.sidebar.text_input("Enter Trainer Password", type="password")

if password_input == "ClanTrainer2026":
    st.sidebar.success("Trainer Access Granted")
    # Add your admin actions here
else:
    st.sidebar.info("Regular members can view the leaderboard on the right.")
