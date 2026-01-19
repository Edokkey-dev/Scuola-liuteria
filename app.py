import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import hashlib
import requests
import time
import extra_streamlit_components as stx
from datetime import datetime, date, timedelta
from supabase import create_client, Client

# --- 1. CONFIGURAZIONE PAGINA & DESIGN ---
st.set_page_config(page_title="Liuteria San Barnaba", page_icon="🎻", layout="centered")

st.markdown("""
<style>
    /* SFONDO GENERALE - Crema Carta Antica */
    .stApp {
        background-color: #F9F7F2;
    }
    
    /* TITOLO PRINCIPALE */
    .main-title {
        color: #3E2723;
        font-family: 'Georgia', serif;
        text-align: center;
        font-size: 3rem;
        margin-bottom: 30px;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.1);
    }

    /* RIMUOVIAMO SPAZI INUTILI IN ALTO */
    .block-container {
        padding-top: 2rem;
    }

    /* STILE "CARD" PER I FORM (IL RIQUADRO SCURO) */
    [data-testid="stForm"] {
        background-color: #EFEBE9; /* Marrone grigio caldo */
        padding: 30px;
        border-radius: 0px 15px 15px 15px; /* Angolo in alto a sx dritto per effetto "cartella" */
        border: 1px solid #D7CCC8;
        box-shadow: 0 8px 16px rgba(0,0,0,0.1);
    }

    /* TESTI LEGGIBILI (Marrone Scuro) */
    label, p, .stMarkdown, h1, h2, h3 {
        color: #3E2723 !important;
        font-family: 'Helvetica Neue', sans-serif;
    }
    
    /* CAMPI DI INPUT (Bianchi per contrasto) */
    .stTextInput > div > div > input {
        background-color: #FFFFFF !important;
        color: #3E2723 !important;
        border: 1px solid #A1887F !important;
        border-radius: 8px !important;
    }

    /* BOTTONI (Marrone Scuro) */
    .stButton > button {
        background-color: #4E342E !important;
        color: #F9F7F2 !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: bold !important;
        width: 100%;
        padding: 10px;
        margin-top: 10px;
        transition: 0.3s;
    }
    .stButton > button:hover {
        background-color: #3E2723 !important;
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }

    /* TAB (LINGUETTE) */
    .stTabs [data-baseweb="tab-list"] {
        gap: 5px;
        background-color: transparent;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #D7CCC8;
        border-radius: 10px 10px 0 0;
        padding: 10px 25px;
        color: #5D4037;
        font-weight: 600;
        border: none;
    }
    .stTabs [data-baseweb="tab"]:hover {
        background-color: #BCAAA4;
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background-color: #EFEBE9; /* Stesso colore del form per continuità */
        color: #3E2723;
        border-bottom: 1px solid #EFEBE9; /* Nasconde la linea di stacco */
    }
    
    /* SCHEDE PRENOTAZIONI INTERNE */
    .booking-card {
        background-color: #FFFFFF;
        padding: 15px;
        border-radius: 10px;
        border-left: 5px solid #4E342E;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        margin-bottom: 15px;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. BACKEND E CONNESSIONI ---
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

# --- FUNZIONI DI SUPPORTO ---
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

# Titolo fuori dai container per centrarlo bene
st.markdown("<h1 class='main-title'>🎻 Liuteria San Barnaba</h1>", unsafe_allow_html=True)

if 'logged_in' not in st.session_state:
    st.session_state.update({'logged_in': False, 'username': '', 'role': ''})

# --- SCHERMATA LOGIN ---
if not st.session_state['logged_in']:
    
    # Colonne per centrare il modulo (Responsive)
    col1, col2, col3 = st.columns([1, 6, 1])
    
    with col2:
        # I Tabs
        tab1, tab2 = st.tabs(["🔐 Accedi", "📝 Registrati"])
        
        with tab1:
            # Il Form creerà automaticamente il box scuro grazie al CSS [data-testid="stForm"]
            with st.form("login_form"):
                st.write("Inserisci le tue credenziali:")
                u = st.text_input("Username").strip()
                p = st.text_input("Password", type='password').strip()
                
                # Bottone Entra
                if st.form_submit_button("Entra"):
                    ud = verify_user(u, p)
                    if ud:
                        st.session_state.update({'logged_in':True, 'username':u, 'role':ud['role']})
                        cookie_manager.set("scuola_user_session", u, expires_at=datetime.now()+timedelta(days=30))
                        st.rerun()
                    else: st.error("Username o Password errati.")
        
        with tab2:
            with st.form("register_form"):
                st.write("Crea un nuovo profilo:")
                nu = st.text_input("Scegli Username").strip()
                np = st.text_input("Scegli Password", type='password').strip()
                st.markdown("---")
                ia = st.checkbox("Sono il Titolare")
                ac = st.text_input("Codice Segreto (solo titolare)", type='password')
                
                if st.form_submit_button("Crea Account"):
                    role = "admin" if (ia and ac == ADMIN_KEY) else "student"
                    if ia and ac != ADMIN_KEY: st.error("Codice errato")
                    elif nu and np:
                        if add_user(nu, np, role): st.success("Fatto! Ora vai su Accedi.");
                        else: st.error("Username già esistente.")
                    else: st.warning("Compila tutti i campi.")

# --- AREA RISERVATA (LOGGATO) ---
else:
    identify_user_onesignal(st.session_state['username'])
    
    with st.sidebar:
        st.header(f"Ciao, {st.session_state['username']}")
        if st.button("Logout"):
            st.session_state['logged_in'] = False
            cookie_manager.delete("scuola_user_session")
            st.rerun()
    
    tab_bk, tab_msg = st.tabs(["📅 Agenda", "🔔 Avvisi"])
    
    with tab_bk:
        if st.session_state['role'] == 'admin':
            st.subheader("Registro Lezioni")
            data = get_all_bookings_admin()
            for x in data:
                st.markdown(f"<div class='booking-card'><b>👤 {x['username']}</b><br>📅 {x['booking_date']} | 🕒 {x['slot']}<br>Lezione #{x['lesson_number']}</div>", unsafe_allow_html=True)
                if st.button("Elimina", key=x['id']): delete_booking(x['id']); st.rerun()
        else:
            # Vista Studente
            nxt = calculate_next_lesson_number(st.session_state['username'])
            
            # Box Informativo
            st.markdown(f"""
            <div style="background-color:#4E342E; color:#F9F7F2; padding:15px; border-radius:10px; text-align:center; margin-bottom:20px;">
                <h2 style="color:white !important; margin:0;">Lezione {nxt} di 8</h2>
            </div>
            """, unsafe_allow_html=True)
            
            with st.form("new_booking"):
                c1, c2 = st.columns(2)
                d = c1.date_input("Giorno", min_value=date.today())
                s = c2.selectbox("Orario", ["10:00 - 13:00", "15:00 - 18:00"])
                if st.form_submit_button("Prenota Lezione"):
                    if d.weekday() in [0, 6]: st.error("La scuola è chiusa Lunedì e Domenica.")
                    else:
                        ok, m = add_booking(st.session_state['username'], d, s)
                        if ok: st.success("Prenotazione salvata!"); time.sleep(1); st.rerun()
                        else: st.warning(m)
            
            st.write("### Le tue prossime lezioni")
            my = get_my_bookings(st.session_state['username'])
            if my:
                for x in my:
                    st.markdown(f"<div class='booking-card'><b>📅 {x['booking_date']}</b><br>🕒 {x['slot']} | Lezione #{x['lesson_number']}</div>", unsafe_allow_html=True)
                    if st.button("Annulla", key=x['id']): delete_booking(x['id']); st.rerun()
            else: st.info("Nessuna lezione in programma.")

    with tab_msg:
        st.info("Nessun nuovo messaggio.")
