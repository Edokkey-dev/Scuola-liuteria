import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import hashlib
import requests
import time
import extra_streamlit_components as stx
from datetime import datetime, date, timedelta
from supabase import create_client, Client

# --- CONFIGURAZIONE ---
try:
    ADMIN_KEY = st.secrets["admin_password"]
except:
    st.error("ERRORE: Manca 'admin_password' nei Secrets di Streamlit!")
    st.stop()

# --- CONNESSIONE SUPABASE ---
@st.cache_resource
def init_connection():
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except:
        return None

supabase: Client = init_connection()

if not supabase:
    st.error("Errore critico: Impossibile connettersi al Database. Controlla i secrets.")
    st.stop()

# --- GESTORE COOKIE (CORRETTO) ---
# Rimossa la cache per evitare l'errore "CachedWidgetWarning"
def get_manager():
    return stx.CookieManager()

cookie_manager = get_manager()

# --- ONE SIGNAL & JAVASCRIPT ---
def identify_user_onesignal(username):
    try:
        onesignal_app_id = st.secrets["onesignal"]["app_id"]
        # Script ottimizzato per Webview Android (AppsGeyser)
        js_code
