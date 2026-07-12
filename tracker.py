import streamlit as st
import time
from supabase import create_client, Client

# --- DATABASE CONNECTION ---
SUPABASE_URL = "https://xvlipedpfyngtwgnrpzt.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inh2bGlwZWRwZnluZ3R3Z25ycHp0Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4Mzg1MjcwNCwiZXhwIjoyMDk5NDI4NzA0fQ.sbc4c1g37cCSxw6ReLOGjotIfs13PFyqumwxrMRgyWk"

@st.cache_resource
def init_connection():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase: Client = init_connection()

# --- WEB PAGE LAYOUT ---
st.set_page_config(page_title="The Suilerua Bloodline tracker", page_icon="⚔️", layout="wide")

@st.fragment(run_every="3s")
def render_live_dashboard():
    # Use a generic try/except to catch any rendering errors
    try:
        response = supabase.table("clan_members").select("*").execute()
        st.subheader("Active training stats")
        
        if response.data:
            # We are using use_container_width=True to avoid the SyntaxErrors
            st.dataframe(response.data, use_container_width=True)
        else:
            st.info("No active clan members logged yet.")
    except Exception as e:
        st.error(f"Error loading dashboard: {e}")

# Render UI
st.title("The Suilerua Bloodline dashboard")
render_live_dashboard()
