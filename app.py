import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import hashlib
import requests
import time
import extra_streamlit_components as stx
from datetime import datetime, date, timedelta
from supabase import create_client, Client

# --- 1. CONFIGURAZIONE PAGINA & CSS (IL TOCCO ESTETICO) ---
st.set_page_config(page_title="Scuola Liuteria", page_icon="🎻", layout="centered")

# --- INIEZIONE STILE "BOTTEGA DEL LIUTAIO" ---
st.markdown("""
<style>
    /* SFONDO GENERALE - Crema Carta Antica */
    .stApp {
        background-color: #F9F7F2;
    }
    
    /* TITOLI - Marrone Scuro */
    h1, h2, h3 {
        color: #4A3B2A !important;
        font-family: 'Helvetica Neue', sans-serif;
    }
    
    /* BOTTONI - Stile Legno */
    .stButton > button {
        background-color: #8B5A2B;
        color: white;
        border-radius: 8px;
        border: 1px solid #6D4C41;
        font-weight: bold;
        transition: 0.3s;
        width: 100%;
    }
    .stButton > button:hover {
        background-color: #6D4C41;
        color: #FFD700;
        border-color: #FFD700;
    }

    /* INPUT TEXT - Puliti */
    .stTextInput > div > div > input {
        border-radius: 8px;
        border: 1px solid #D7CCC8;
        background-color: #FFFFFF;
    }

    /* CARD PRENOTAZIONI - Effetto Cartoncino */
    .booking-card {
        background-color: #FFFFFF;
        padding: 15px;
        border-radius: 10px;
        border-left: 5px solid #8B5A2B;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
        margin-bottom: 10px;
    }

    /* MENU TABS - Più evidenti */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
        background-color: transparent;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #EFEbe9;
        border-radius: 5px;
        color: #5D4037;
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background-color: #8B5A2B;
        color: white;
    }
    
    /* BOX NOTIFICHE */
    .stAlert {
        background-color: #FFF8E1;
        color: #5D4037;
        border: 1px solid #FFECB3;
    }
</style>
""", unsafe_allow_html=True)

# --- CONFIGURAZIONE SECRETS ---
try:
    ADMIN_KEY = st.secrets["admin_password"]
except:
    st.error("ERRORE: Manca 'admin_password' nei Secrets!")
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
    st.error("Errore critico: Database non connesso.")
    st.stop()

# --- GESTORE COOKIE ---
def get_manager():
    return stx.CookieManager()

cookie_manager = get_manager()

# --- ONE SIGNAL & JS ---
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
              autoRegister: true
            }});
            OneSignal.push(function() {{
                OneSignal.setExternalUserId("{username}");
            }});
          }});
        </script>
        """
        components.html(js_code, height=0)
    except: pass

# --- LOGICA NOTIFICHE ---
def clean_old_notifications():
    try:
        cutoff = (datetime.now() - timedelta(days=30)).isoformat()
        supabase.table("notifications").delete().lt("created_at", cutoff).execute()
    except:
