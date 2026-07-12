import streamlit as st
from supabase import create_client, Client

# --- DATABASE CONNECTION ---
SUPABASE_URL = "https://xvlipedpfyngtwgnrpzt.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inh2bGlwZWRwZnluZ3R3Z25ycHp0Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4Mzg1MjcwNCwiZXhwIjoyMDk5NDI4NzA0fQ.sbc4c1g37cCSxw6ReLOGjotIfs13PFyqumwxrMRgyWk"

@st.cache_resource
def init_connection():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase: Client = init_connection()

st.title("Step 1: Database Connection")
try:
    # Test a simple query
    response = supabase.table("clan_members").select("username").limit(1).execute()
    st.success("Successfully connected to Supabase!")
    st.write("Data check:", response.data)
except Exception as e:
    st.error(f"Connection failed: {e}")
