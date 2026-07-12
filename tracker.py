import streamlit as st

st.title("Connection Test")
st.write("If this page loads, the environment is stable.")

# A very basic check to see if the app can even render without the fragment or Supabase
st.info("The application has successfully loaded the basic UI components.")
