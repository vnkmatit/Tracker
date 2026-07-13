import streamlit as st
from supabase import create_client

st.set_page_config(page_title="Test")

st.write("Step 1")

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

st.write("Step 2")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

st.write("Step 3")
response = supabase.table("clan_members").select("*").execute()

st.write("Step 4")
st.write(response.data)
st.dataframe(response.data)
