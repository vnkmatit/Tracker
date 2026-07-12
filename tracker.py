import streamlit as st
import time
from supabase import create_client, Client

# --- SETUP ---
SUPABASE_URL = "https://xvlipedpfyngtwgnrpzt.supabase.co"
SUPABASE_KEY = "..." # Use your key

@st.cache_resource
def init_connection():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_connection()

st.title("The Suilerua Bloodline dashboard")

# Placeholders for the dynamic content
status_placeholder = st.empty()

# Simple auto-refresh loop (use with caution in Cloud environments)
while True:
    with status_placeholder.container():
        try:
            response = supabase.table("clan_members").select("*").execute()
            if response.data:
                st.subheader("Active training stats")
                st.dataframe(response.data, use_container_width=True)
            else:
                st.info("No active clan members.")
        except Exception as e:
            st.error(f"Sync error: {e}")
    
    time.sleep(5) # Wait 5 seconds before next refresh
