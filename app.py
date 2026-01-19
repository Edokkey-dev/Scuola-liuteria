import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import hashlib
import requests
import time
import extra_streamlit_components as stx
from datetime import datetime, date, timedelta
from supabase import create_client, Client

# --- 1. CONFIGURAZIONE PAGINA & CSS AVANZATO ---
st.set_page_config(page_title="Liuteria San Barnaba", page_icon="🎻", layout="centered")

st.markdown("""
<style>
    /* SFONDO GENERALE */
    .stApp {
        background-color: #F9F7F2;
    }
    
    /* FIX TESTI - Colore marrone scuro per massima leggibilità */
    label, .stMarkdown, p, span, stText {
        color: #4A3B2A !important;
        font-weight: 500 !important;
    }
    
    /* TITOLO PRINCIPALE */
    h1 {
        color: #4A3B2A !important;
        font-family: 'Georgia', serif;
        padding-bottom: 10px;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.1);
    }

    /* RIQUADRO LOGIN (BOX SCURO) */
    .login-container {
        background-color: #EFEBE9; /* Colore più scuro dello sfondo crema */
        padding: 30px;
        border-radius: 15px;
        border: 1px solid #D7CCC8;
        box-shadow: 0 10px 25px rgba(0,0,0,0.05);
        margin-top: 20px;
    }

    /* BOTTONI - Stile Legno pregiato */
    .stButton > button {
        background-color: #5D4037;
        color: white !important;
        border-radius: 8px;
        border: none;
        padding: 12px 24px;
        font-weight: bold;
        transition: all 0.3s ease;
    }
    .stButton > button:hover {
        background-color: #3E2723;
        transform: translateY(-1px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }

    /* CAMPI DI INPUT */
    .stTextInput > div > div > input {
        border: 1px solid #8B5A2B !important;
        border-radius: 8px !important;
        background-color: white !important;
    }

    /* CARD PRENOTAZIONI */
    .booking-card {
        background-color: #FFFFFF;
        padding: 18px;
        border-radius: 12px;
        border-left: 6px solid #8B5A2B;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin-bottom: 12px;
        color: #4A3B2A;
    }

    /* TAB STYLE */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #D7CCC8;
        border-radius: 8px 8px 0 0;
        padding: 10px 20px;
        color: #4A3B2A !important;
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background-color: #5D4037;
        color: white !important;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. CONFIGURAZIONE SECRETS ---
try:
    ADMIN_KEY = st.secrets["admin_password"]
except:
    st.error("ERRORE: Manca 'admin_password' nei Secrets!")
    st.stop()

# --- 3. CONNESSIONE SUPABASE ---
@st.cache_resource
def init_connection():
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except: return None

supabase: Client = init_connection()

# --- 4. GESTORE COOKIE ---
def get_manager():
    return stx.CookieManager()

cookie_manager = get_manager()

# --- 5. FUNZIONI LOGICHE ---
def identify_user_onesignal(username):
    try:
        onesignal_app_id = st.secrets["onesignal"]["app_id"]
        js_code = f"""
        <script src="https://cdn.onesignal.com/sdks/OneSignalSDK.js" async=""></script>
        <script>
          window.OneSignal = window.OneSignal || [];
          OneSignal.push(function() {{
            OneSignal.init({{ appId: "{onesignal_app_id}", allowLocalhostAsSecureOrigin: true, autoRegister: true }});
            OneSignal.push(function() {{ OneSignal.setExternalUserId("{username}"); }});
          }});
        </script>
        """
        components.html(js_code, height=0)
    except: pass

def hash_password(p): return hashlib.sha256(str.encode(p)).hexdigest()

def verify_user(u, p):
    try:
        res = supabase.table("users").select("*").eq("username", u).eq("password", hash_password(p)).execute()
        return res.data[0] if res.data else None
    except: return None

def get_user_role(u):
    try:
        res = supabase.table("users").select("role").eq("username", u).execute()
        return res.data[0]['role'] if res.data else None
    except: return None

def add_user(u, p, r):
    try:
        supabase.table("users").insert({"username": u, "password": hash_password(p), "role": r}).execute()
        return True
    except: return False

def update_password(u, p):
    try:
        supabase.table("users").update({"password": hash_password(p)}).eq("username", u).execute()
        return True
    except: return False

def calculate_next_lesson_number(u):
    res = supabase.table("bookings").select("*", count="exact").eq("username", u).execute()
    return (res.count % 8) + 1

def add_booking(u, d, s):
    str_d = d.strftime("%Y-%m-%d")
    check = supabase.table("bookings").select("*").eq("username", u).eq("booking_date", str_d).eq("slot", s).execute()
    if check.data: return False, "Già prenotato."
    num = calculate_next_lesson_number(u)
    try:
        supabase.table("bookings").insert({"username": u, "booking_date": str_d, "slot": s, "lesson_number": num}).execute()
        return True, num
    except: return False, "Errore DB"

def get_my_bookings(u): return supabase.table("bookings").select("*").eq("username", u).order("booking_date").execute().data
def get_all_bookings_admin(): return supabase.table("bookings").select("*").order("booking_date", desc=True).execute().data
def delete_booking(bid): supabase.table("bookings").delete().eq("id", bid).execute()

# --- 6. INTERFACCIA ---
st.markdown("<h1 style='text-align: center;'>🎻 Liuteria San Barnaba</h1>", unsafe_allow_html=True)

if 'logged_in' not in st.session_state:
    st.session_state.update({'logged_in': False, 'username': '', 'role': ''})

# AUTO LOGIN
if not st.session_state['logged_in']:
    try:
        c_user = cookie_manager.get("scuola_user_session")
        if c_user:
            role = get_user_role(c_user)
            if role:
                st.session_state.update({'logged_in':True, 'username':c_user, 'role':role})
                st.rerun()
    except: pass

# UI ACCESSO (CON RIQUADRO SCURO)
if not st.session_state['logged_in']:
    col1, col2, col3 = st.columns([1, 10, 1])
    with col2:
        st.markdown('<div class="login-container">', unsafe_allow_html=True)
        tab1, tab2 = st.tabs(["🔐 Accedi", "📝 Registrati"])
        with tab1:
            with st.form("login"):
                u = st.text_input("Username").strip()
                p = st.text_input("Password", type='password').strip()
                if st.form_submit_button("Entra"):
                    ud = verify_user(u, p)
                    if ud:
                        st.session_state.update({'logged_in':True, 'username':u, 'role':ud['role']})
                        cookie_manager.set("scuola_user_session", u, expires_at=datetime.now()+timedelta(days=30))
                        st.rerun()
                    else: st.error("Credenziali errate.")
        with tab2:
            with st.form("reg"):
                nu = st.text_input("Scegli Username").strip()
                np = st.text_input("Scegli Password", type='password').strip()
                ia = st.checkbox("Sono il Titolare")
                ac = st.text_input("Codice Segreto Admin", type='password')
                if st.form_submit_button("Crea Account"):
                    role = "admin" if (ia and ac == ADMIN_KEY) else "student"
                    if ia and ac != ADMIN_KEY: st.error("Codice Admin errato")
                    elif nu and np:
                        if add_user(nu, np, role):
