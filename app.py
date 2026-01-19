import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import hashlib
import requests
import time
import extra_streamlit_components as stx
from datetime import datetime, date, timedelta
from supabase import create_client, Client

# --- 1. CONFIGURAZIONE PAGINA & CSS REVISIONATO ---
st.set_page_config(page_title="Liuteria San Barnaba", page_icon="🎻", layout="centered")

st.markdown("""
<style>
    /* SFONDO GENERALE */
    .stApp {
        background-color: #F9F7F2;
    }
    
    /* TITOLO PRINCIPALE */
    .main-title {
        color: #4A3B2A;
        font-family: 'Georgia', serif;
        text-align: center;
        font-size: 3rem;
        margin-bottom: 20px;
    }

    /* IL BOX SCURO DEL LOGIN */
    .login-box {
        background-color: #EFEBE9; /* Marrone grigio chiaro */
        padding: 40px;
        border-radius: 20px;
        border: 1px solid #D7CCC8;
        box-shadow: 0 15px 35px rgba(0,0,0,0.1);
    }
    
    /* FIX TESTI DENTRO IL BOX */
    label, p, .stMarkdown {
        color: #3E2723 !important;
        font-weight: 600 !important;
        font-size: 1.1rem !important;
    }

    /* INPUT FIELDS */
    .stTextInput > div > div > input {
        background-color: white !important;
        border: 2px solid #8B5A2B !important;
        border-radius: 10px !important;
        color: #3E2723 !important;
    }

    /* BOTTONE ENTRA/REGISTRATI */
    .stButton > button {
        background-color: #5D4037 !important;
        color: #F9F7F2 !important;
        border-radius: 10px !important;
        height: 3em !important;
        width: 100% !important;
        font-size: 1.2rem !important;
        border: none !important;
        margin-top: 10px;
    }
    .stButton > button:hover {
        background-color: #3E2723 !important;
        box-shadow: 0 5px 15px rgba(0,0,0,0.3) !important;
    }

    /* TABS */
    .stTabs [data-baseweb="tab-list"] {
        background-color: transparent !important;
        gap: 15px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        background-color: #D7CCC8 !important;
        border-radius: 10px 10px 0 0 !important;
        color: #3E2723 !important;
        font-weight: bold !important;
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background-color: #5D4037 !important;
        color: white !important;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. LOGICA DI BACKEND (Identica, non toccarla) ---
try:
    ADMIN_KEY = st.secrets["admin_password"]
except:
    st.error("Errore Secrets!")
    st.stop()

@st.cache_resource
def init_connection():
    try:
        return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])
    except: return None

supabase = init_connection()
cookie_manager = stx.CookieManager()

def hash_password(p): return hashlib.sha256(str.encode(p)).hexdigest()

def verify_user(u, p):
    res = supabase.table("users").select("*").eq("username", u).eq("password", hash_password(p)).execute()
    return res.data[0] if res.data else None

def add_user(u, p, r):
    try:
        supabase.table("users").insert({"username": u, "password": hash_password(p), "role": r}).execute()
        return True
    except: return False

def calculate_next_lesson_number(u):
    res = supabase.table("bookings").select("*", count="exact").eq("username", u).execute()
    return (res.count % 8) + 1

# --- 3. INTERFACCIA ---
st.markdown("<h1 class='main-title'>🎻 Liuteria San Barnaba</h1>", unsafe_allow_html=True)

if 'logged_in' not in st.session_state:
    st.session_state.update({'logged_in': False, 'username': '', 'role': ''})

# UI LOGIN
if not st.session_state['logged_in']:
    # Usiamo un contenitore di Streamlit per simulare il box scuro
    with st.container():
        # Questo crea il box visivo tramite CSS
        st.markdown('<div class="login-box">', unsafe_allow_html=True)
        
        tab1, tab2 = st.tabs(["🔐 Accedi", "📝 Registrati"])
        
        with tab1:
            with st.form("login_form", clear_on_submit=False):
                u = st.text_input("Username").strip()
                p = st.text_input("Password", type='password').strip()
                if st.form_submit_button("Entra"):
                    ud = verify_user(u, p)
                    if ud:
                        st.session_state.update({'logged_in':True, 'username':u, 'role':ud['role']})
                        cookie_manager.set("scuola_user_session", u, expires_at=datetime.now()+timedelta(days=30))
                        st.rerun()
                    else: st.error("Dati non corretti")
                    
        with tab2:
            with st.form("reg_form"):
                nu = st.text_input("Nome Utente").strip()
                np = st.text_input("Password scelta", type='password').strip()
                ia = st.checkbox("Accesso Titolare")
                ac = st.text_input("Codice Segreto", type='password')
                if st.form_submit_button("Crea Account"):
                    role = "admin" if (ia and ac == ADMIN_KEY) else "student"
                    if ia and ac != ADMIN_KEY: st.error("Codice errato")
                    elif nu and np:
                        if add_user(nu, np, role): st.success("Registrato! Ora accedi.")
                        else: st.error("Errore registrazione.")
        
        st.markdown('</div>', unsafe_allow_html=True)

# AREA PRIVATA
else:
    with st.sidebar:
        st.write(f"Connesso come: **{st.session_state['username']}**")
        if st.button("Logout"):
            st.session_state['logged_in'] = False
            cookie_manager.delete("scuola_user_session")
            st.rerun()
    
    st.success(f"Benvenuto nella tua area riservata, {st.session_state['username']}!")
    # Qui puoi rimettere il resto del codice delle prenotazioni...
