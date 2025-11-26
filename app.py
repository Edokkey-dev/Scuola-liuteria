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
# Nessun decoratore cache qui per evitare errori di widget
def get_manager():
    return stx.CookieManager()

cookie_manager = get_manager()

# --- ONE SIGNAL & JAVASCRIPT ---
def identify_user_onesignal(username):
    try:
        onesignal_app_id = st.secrets["onesignal"]["app_id"]
        js_code = f"""
        <script src="https://cdn.onesignal.com/sdks/OneSignalSDK.js" async=""></script>
        <script>
          window.OneSignal = window.OneSignal || [];
          OneSignal.push(function() {{
            OneSignal.init({{
              appId: "{onesignal_app_id}",
              allowLocalhostAsSecureOrigin: true,
            }});
            OneSignal.setExternalUserId("{username}");
          }});
        </script>
        """
        components.html(js_code, height=0)
    except:
        pass

# --- GESTIONE NOTIFICHE ---
def clean_old_notifications():
    try:
        cutoff_date = (datetime.now() - timedelta(days=30)).isoformat()
        supabase.table("notifications").delete().lt("created_at", cutoff_date).execute()
    except Exception as e:
        print(f"Errore pulizia: {e}")

def save_notification_to_db(username, message):
    try:
        supabase.table("notifications").insert({"username": username, "message": message}).execute()
    except: pass

def send_notification(message, target_usernames=None, heading="Avviso Scuola"):
    if target_usernames:
        for user in target_usernames:
            save_notification_to_db(user, message)
    try:
        app_id = st.secrets["onesignal"]["app_id"]
        api_key = st.secrets["onesignal"]["api_key"]
        header = {"Authorization": "Basic " + api
