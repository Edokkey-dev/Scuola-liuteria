import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import hashlib
import requests
import time
import extra_streamlit_components as stx
from datetime import datetime, date, timedelta
from supabase import create_client, Client

# --- 1. CONFIGURAZIONE PAGINA & NUOVO DESIGN "BOTTEGA" ---
st.set_page_config(page_title="Liuteria San Barnaba", page_icon="🎻", layout="centered")

st.markdown("""
<style>
    /* === 1. FONDI E TESTI GENERALI === */
    .stApp {
        background-color: #F9F7F2; /* Crema Carta Antica */
    }
    
    h1, h2, h3, h4, p, span, label, div {
        color: #3E2723; /* Marrone scurissimo per massima leggibilità */
        font-family: 'Helvetica Neue', sans-serif;
    }

    /* === 2. SIDEBAR (LA BARRA LATERALE) === */
    [data-testid="stSidebar"] {
        background-color: #2D1B15 !important; /* Legno scuro */
        border-right: 2px solid #8B5A2B;
    }
    
    /* FORZA IL TESTO BIANCO NELLA SIDEBAR */
    [data-testid="stSidebar"] * {
        color: #F5F5DC !important; /* Bianco crema */
    }
    
    /* === 3. RIMOZIONE RETTANGOLI GRIGI (IL FANTASMA) === */
    .block-container {
        padding-top: 2rem;
    }
    div[data-testid="stVerticalBlock"] > div {
        background-color: transparent; /* Rimuove sfondi indesiderati */
    }

    /* === 4. LOGIN & FORM (CONTRASTO ALTO) === */
    [data-testid="stForm"] {
        background-color: #FFFFFF;
        padding: 30px;
        border-radius: 15px;
        border: 1px solid #D7CCC8;
        box-shadow: 0 10px 20px rgba(0,0,0,0.05);
    }

    /* INPUT FIELDS (BIANCHI PULITI) */
    .stTextInput > div > div > input, .stDateInput > div > div > input {
        background-color: #FFFFFF !important;
        color: #000000 !important; /* Testo nero puro */
        border: 2px solid #8B5A2B !important;
        border-radius: 8px !important;
    }
    
    /* SELECTBOX */
    div[data-baseweb="select"] > div {
        background-color: #FFFFFF !important;
        color: #000000 !important;
        border: 2px solid #8B5A2B !important;
    }

    /* === 5. BOTTONI (LEGNO E ORO) === */
    .stButton > button {
        background-color: #5D4037 !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: bold !important;
        padding: 10px 20px !important;
        transition: 0.3s;
        width: 100%;
    }
    .stButton > button:hover {
        background-color: #3E2723 !important;
        color: #FFD700 !important; /* Oro al passaggio del mouse */
    }

    /* === 6. BOX NOTIFICHE E INFO === */
    .stAlert {
        background-color: #FFF8E1 !important;
        border: 1px solid #FFECB3 !important;
    }
    
    /* BOX CONTEGGIO LEZIONI */
    .lesson-counter-box {
        background-color: #3E2723;
        color: #FFD700 !important; /* Oro su Scuro */
        padding: 20px;
        border-radius: 10px;
        text-align: center;
        margin-bottom: 20px;
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }
    .lesson-counter-box h2 {
        color: #FFD700 !important;
        margin: 0;
    }
    
    /* CARD PRENOTAZIONI */
    .booking-card {
        background-color: white;
        padding: 15px;
        border-radius: 8px;
        border-left: 5px solid #5D4037;
        margin-bottom: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

# --- 2. LOGICA BACKEND (NON TOCCARE) ---
try:
    ADMIN_KEY = st.secrets["admin_password"]
except:
    st.error("Errore: Secrets non configurati.")
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
def identify_user_onesignal(username):
    try:
        app_id = st.secrets["onesignal"]["app_id"]
        js = f"""<script src="https://cdn.onesignal.com/sdks/OneSignalSDK.js" async=""></script>
        <script>
          window.OneSignal = window.OneSignal || [];
          OneSignal.push(function() {{
            OneSignal.init({{ appId: "{app_id}", allowLocalhostAsSecureOrigin: true, autoRegister: true }});
            OneSignal.push(function() {{ OneSignal.setExternalUserId("{username}"); }});
          }});
        </script>"""
        components.html(js, height=0)
    except: pass
def add_booking(u, d, s):
    sd = d.strftime("%Y-%m-%d")
    check = supabase.table("bookings").select("*").eq("username", u).eq("booking_date", sd).eq("slot", s).execute()
    if check.data: return False, "Occupato"
    n = calculate_next_lesson_number(u)
    try:
        supabase.table("bookings").insert({"username":u, "booking_date":sd, "slot":s, "lesson_number":n}).execute()
        return True, n
    except: return False, "Errore"
def get_my_bookings(u): return supabase.table("bookings").select("*").eq("username", u).order("booking_date").execute().data
def get_all_bookings_admin(): return supabase.table("bookings").select("*").order("booking_date", desc=True).execute().data
def delete_booking(bid): supabase.table("bookings").delete().eq("id", bid).execute()

# --- 3. INTERFACCIA UTENTE ---

st.markdown("<h1 style='text-align: center; font-size: 3rem;'>🎻 Liuteria San Barnaba</h1>", unsafe_allow_html=True)
st.markdown("---")

if 'logged_in' not in st.session_state:
    st.session_state.update({'logged_in': False, 'username': '', 'role': ''})

# --- LOGIN ---
if not st.session_state['logged_in']:
    col1, col2, col3 = st.columns([1, 6, 1])
    with col2:
        tab1, tab2 = st.tabs(["🔐 Accedi", "📝 Registrati"])
        
        with tab1:
            st.info("Inserisci le tue credenziali per entrare.")
            with st.form("login_form"):
                u = st.text_input("Username").strip()
                p = st.text_input("Password", type='password').strip()
                if st.form_submit_button("Entra"):
                    ud = verify_user(u, p)
                    if ud:
                        st.session_state.update({'logged_in':True, 'username':u, 'role':ud['role']})
                        cookie_manager.set("scuola_user_session", u, expires_at=datetime.now()+timedelta(days=30))
                        st.rerun()
                    else: st.error("Dati errati.")
        
        with tab2:
            st.warning("Crea un nuovo account se è la prima volta.")
            with st.form("reg_form"):
                nu = st.text_input("Nuovo Username").strip()
                np = st.text_input("Password", type='password').strip()
                st.markdown("---")
                ia = st.checkbox("Accesso Titolare")
                ac = st.text_input("Codice Admin", type='password')
                if st.form_submit_button("Registrati"):
                    role = "admin" if (ia and ac == ADMIN_KEY) else "student"
                    if ia and ac != ADMIN_KEY: st.error("Codice errato")
                    elif nu and np:
                        if add_user(nu, np, role): st.success("Fatto! Accedi.")
                        else: st.error("Username occupato.")
                    else: st.warning("Compila tutto.")

# --- AREA PRIVATA ---
else:
    identify_user_onesignal(st.session_state['username'])
    
    with st.sidebar:
        st.markdown("### 👤 Profilo")
        st.markdown(f"**Utente:** {st.session_state['username']}")
        st.markdown("---")
        if st.button("Logout"):
            st.session_state['logged_in'] = False
            cookie_manager.delete("scuola_user_session")
            st.rerun()
    
    tab_bk, tab_msg = st.tabs(["📅 Agenda", "🔔 Avvisi"])
    
    with tab_bk:
        if st.session_state['role'] == 'admin':
            st.subheader("Registro Generale")
            data = get_all_bookings_admin()
            for x in data:
                st.markdown(f"<div class='booking-card'><b>👤 {x['username']}</b><br>📅 {x['booking_date']} | 🕒 {x['slot']}<br>Lezione #{x['lesson_number']}</div>", unsafe_allow_html=True)
                if st.button("Elimina", key=x['id']): delete_booking(x['id']); st.rerun()
        else:
            # VISTA STUDENTE
            nxt = calculate_next_lesson_number(st.session_state['username'])
            
            # BOX CONTATORE LEZIONI (Ora Leggibile!)
            st.markdown(f"""
            <div class="lesson-counter-box">
                <h2>Lezione {nxt} di 8</h2>
                <p style="color:#FFD700 !important;">Pacchetto in corso</p>
            </div>
            """, unsafe_allow_html=True)
            
            with st.form("new_booking"):
                st.write("Prenota una nuova data:")
                c1, c2 = st.columns(2)
                d = c1.date_input("Data", min_value=date.today())
                s = c2.selectbox("Orario", ["10:00 - 13:00", "15:00 - 18:00"])
                if st.form_submit_button("Conferma Prenotazione"):
                    if d.weekday() in [0, 6]: st.error("Chiuso Lunedì e Domenica.")
                    else:
                        ok, m = add_booking(st.session_state['username'], d, s)
                        if ok: st.success("Prenotata!"); time.sleep(1); st.rerun()
                        else: st.warning(m)
            
            st.write("### 📜 Le tue prenotazioni")
            my = get_my_bookings(st.session_state['username'])
            if my:
                for x in my:
                    st.markdown(f"<div class='booking-card'><b>📅 {x['booking_date']}</b><br>🕒 {x['slot']} | Lezione #{x['lesson_number']}</div>", unsafe_allow_html=True)
                    if st.button("Annulla", key=x['id']): delete_booking(x['id']); st.rerun()
            else: st.info("Nessuna lezione futura.")

    with tab_msg:
        st.info("Nessun nuovo avviso.")
