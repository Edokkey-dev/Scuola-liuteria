import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import hashlib
import requests
import time
import extra_streamlit_components as stx
from datetime import datetime, date, timedelta
from supabase import create_client, Client
import os

# --- 1. CONFIGURAZIONE PAGINA & CSS "ULTRA LEGGIBILITÀ" ---
st.set_page_config(page_title="Accademia Liuteria San Barnaba", page_icon="🎻", layout="centered")

st.markdown("""
<style>
    /* Sfondo Generale */
    .stApp { background-color: #FAF9F6; }
    
    /* Font Base */
    h1, h2, h3, h4, p, span, label, div { 
        font-family: 'Georgia', serif; 
    }

    /* --- FIX TOTALE BOTTONI --- */
    /* Colpiamo il bottone, il testo al suo interno (p) e l'icona (svg) */
    .stButton > button, 
    .stButton > button p, 
    .stButton > button div, 
    .stButton > button svg { 
        background-color: #1E1E1E !important; 
        color: #FFFFFF !important; 
        fill: #FFFFFF !important; /* Per le icone SVG */
    }

    .stButton > button {
        border: 1px solid #C0A062 !important;
        border-radius: 4px !important;
        height: 3.5em !important;
        width: 100% !important;
        font-weight: bold !important;
        text-transform: uppercase !important;
    }

    .stButton > button:hover {
        background-color: #C0A062 !important;
    }
    .stButton > button:hover p, .stButton > button:hover svg {
        color: #1E1E1E !important;
        fill: #1E1E1E !important;
    }

    /* --- FIX TOTALE TENDINA (EXPANDER) --- */
    /* Header della tendina */
    .streamlit-expanderHeader {
        background-color: #1E1E1E !important;
        border: 1px solid #C0A062 !important;
        border-radius: 4px !important;
    }
    
    /* Testo e icona della tendina (la freccetta) */
    .streamlit-expanderHeader p, 
    .streamlit-expanderHeader span, 
    .streamlit-expanderHeader svg {
        color: #FFFFFF !important;
        fill: #FFFFFF !important;
    }

    /* --- FIX BOX CONTATORE LEZIONI --- */
    .counter-box {
        background-color: #1E1E1E; 
        padding: 30px; 
        border-radius: 4px; 
        text-align: center; 
        margin-bottom: 25px; 
        border: 1px solid #C0A062;
    }
    .counter-box h2 {
        color: #FFFFFF !important; 
        margin: 0 !important;
        font-size: 2.5rem !important;
    }

    /* --- SIDEBAR --- */
    [data-testid="stSidebar"] { background-color: #1E1E1E !important; }
    [data-testid="stSidebar"] * { color: #FFFFFF !important; }

    /* --- INPUT E SELECTBOX --- */
    /* Testo dentro le selectbox (menu a tendina) */
    div[data-baseweb="select"] * {
        color: #FFFFFF !important;
    }
    /* Etichette degli input (Giorno, Orario, ecc.) */
    .stTextInput label, .stDateInput label, .stSelectbox label, .stNumberInput label {
        color: #2C2C2C !important;
        font-weight: bold !important;
    }

    /* Card Prenotazione */
    .booking-card { 
        background-color: white; 
        padding: 20px; 
        border-radius: 4px; 
        border-left: 5px solid #C0A062; 
        box-shadow: 0 2px 5px rgba(0,0,0,0.05); 
        color: #2C2C2C !important;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. BACKEND (Invariato) ---
try: ADMIN_KEY = st.secrets["admin_password"]
except: st.error("Errore Secrets."); st.stop()

@st.cache_resource
def init_connection():
    try: return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])
    except: return None

supabase = init_connection()
cookie_manager = stx.CookieManager()

ACHIEVEMENTS_MAP = {
    "Rosetta 🏵️": "ach_rosetta", "Ponte 🌉": "ach_ponte", "Assemblata 🔧": "ach_assemblata",
    "Manico 🪵": "ach_manico", "Corpo 🎸": "ach_corpo", "Chitarra Finita 🏆": "ach_finita"
}

def hash_password(p): return hashlib.sha256(str.encode(p)).hexdigest()
def verify_user(u, p):
    res = supabase.table("users").select("*").eq("username", u).eq("password", hash_password(p)).execute()
    return res.data[0] if res.data else None
def add_user(u, p, r):
    try: supabase.table("users").insert({"username": u, "password": hash_password(p), "role": r, "recovery_lessons": 0}).execute(); return True
    except: return False
def identify_user_onesignal(username):
    try:
        js = f"""<script src="https://cdn.onesignal.com/sdks/OneSignalSDK.js" async=""></script><script>window.OneSignal = window.OneSignal || [];OneSignal.push(function() {{OneSignal.init({{ appId: "{st.secrets["onesignal"]["app_id"]}", allowLocalhostAsSecureOrigin: true, autoRegister: true }});OneSignal.push(function() {{ OneSignal.setExternalUserId("{username}"); }});}});</script>"""
        components.html(js, height=0)
    except: pass
def calculate_next_lesson_number(u):
    res = supabase.table("bookings").select("*", count="exact").eq("username", u).execute()
    return (res.count % 8) + 1
def add_booking(u, d, s):
    sd = d.strftime("%Y-%m-%d")
    check = supabase.table("bookings").select("*").eq("username", u).eq("booking_date", sd).eq("slot", s).execute()
    if check.data: return False, "Già occupato"
    n = calculate_next_lesson_number(u)
    try: supabase.table("bookings").insert({"username":u, "booking_date":sd, "slot":s, "lesson_number":n}).execute(); return True, n
    except: return False, "Errore"
def get_future_bookings(u):
    today = date.today().isoformat()
    return supabase.table("bookings").select("*").eq("username", u).gte("booking_date", today).order("booking_date").execute().data
def get_past_bookings(u):
    today = date.today().isoformat()
    return supabase.table("bookings").select("*").eq("username", u).lt("booking_date", today).order("booking_date", desc=True).execute().data
def get_all_future_bookings_admin():
    today = date.today().isoformat()
    return supabase.table("bookings").select("*").gte("booking_date", today).order("booking_date").execute().data
def delete_booking(bid): supabase.table("bookings").delete().eq("id", bid).execute()
def update_lesson_number(booking_id, new_number):
    try: supabase.table("bookings").update({"lesson_number": new_number}).eq("id", booking_id).execute(); return True
    except: return False
def update_recovery_count(username, new_count):
    try: supabase.table("users").update({"recovery_lessons": new_count}).eq("username", username).execute(); return True
    except: return False
def get_all_students():
    return supabase.table("users").select("username").eq("role", "student").execute().data
def get_student_details(u):
    res = supabase.table("users").select("*").eq("username", u).execute()
    return res.data[0] if res.data else None
def assign_achievement_to_lesson(booking_id, student_username, achievement_name):
    try:
        supabase.table("bookings").update({"achievement": achievement_name}).eq("id", booking_id).execute()
        if achievement_name in ACHIEVEMENTS_MAP:
            col_db = ACHIEVEMENTS_MAP[achievement_name]
            supabase.table("users").update({col_db: True}).eq("username", student_username).execute()
            return True
    except: return False

# --- HEADER ---
col_logo_1, col_logo_2, col_logo_3 = st.columns([1, 2, 1])
with col_logo_2:
    if os.path.exists("logo.png"): st.image("logo.png", use_column_width=True)
    else: st.markdown("<h1 style='text-align: center; color:#2C2C2C;'>Liuteria San Barnaba</h1>", unsafe_allow_html=True)

if 'logged_in' not in st.session_state: st.session_state.update({'logged_in': False, 'username': '', 'role': ''})

# LOGIN
if not st.session_state['logged_in']:
    c1, c2, c3 = st.columns([1, 6, 1])
    with c2:
        t1, t2 = st.tabs(["ACCEDI", "REGISTRATI"])
        with t1:
            with st.form("log"):
                u = st.text_input("Username").strip()
                p = st.text_input("Password", type='password').strip()
                if st.form_submit_button("ENTRA"):
                    ud = verify_user(u, p)
                    if ud:
                        st.session_state.update({'logged_in':True, 'username':u, 'role':ud['role']})
                        cookie_manager.set("scuola_user_session", u, expires_at=datetime.now()+timedelta(days=30))
                        st.rerun()
                    else: st.error("Errore")

# APP
else:
    identify_user_onesignal(st.session_state['username'])
    with st.sidebar:
        if os.path.exists("sidebar.jpg"): st.image("sidebar.jpg", use_column_width=True)
        st.markdown(f"### 👤 {st.session_state['username'].upper()}")
        if st.button("LOGOUT"): st.session_state['logged_in']=False; cookie_manager.delete("scuola_user_session"); st.rerun()

    if st.session_state['role'] == 'admin':
        tab_reg, tab_std = st.tabs(["REGISTRO", "STUDENTI"])
        with tab_reg:
            st.subheader("Agenda Lezioni")
            data = get_all_future_bookings_admin()
            if data:
                for x in data:
                    st.markdown(f"<div class='booking-card'><b>👤 {x['username']}</b><br>📅 {x['booking_date']} | 🕒 {x['slot']} <br>Lezione: {x['lesson_number']}</div>", unsafe_allow_html=True)
                    with st.expander("✏️ Gestisci Prenotazione"):
                        new_n = st.number_input("Cambia Numero Lezione", min_value=1, value=x['lesson_number'], key=f"n_{x['id']}")
                        c_b1, c_b2 = st.columns(2)
                        with c_b1:
                            if st.button("💾 SALVA MODIFICHE", key=f"s_{x['id']}"): 
                                update_lesson_number(x['id'], new_n)
                                st.rerun()
                        with c_b2:
                            if st.button("🗑️ ELIMINA", key=f"d_{x['id']}"): 
                                delete_booking(x['id'])
                                st.rerun()
            else: st.info("Nessuna prenotazione.")

        with tab_std:
            st.subheader("Gestione Studente")
            students = [s['username'] for s in get_all_students()]
            sel_std = st.selectbox("Seleziona Studente:", [""] + students)
            if sel_std:
                me = get_student_details(sel_std)
                st.markdown("### 🟠 Recuperi")
                nr = st.number_input("Lezioni da recuperare", min_value=0, value=me.get('recovery_lessons', 0))
                if st.button("AGGIORNA RECUPERI"): update_recovery_count(sel_std, nr); st.rerun()
                
                st.divider()
                st.write("#### Storico & Premi")
                past = get_past_bookings(sel_std)
                if past:
                    for p in past:
                        curr_ach = p.get('achievement')
                        st.info(f"📅 {p['booking_date']} | Lez. {p['lesson_number']} {('🏆 ' + curr_ach) if curr_ach else ''}")
                        opts = ["Nessuno"] + list(ACHIEVEMENTS_MAP.keys())
                        idx = opts.index(curr_ach) if curr_ach in opts else 0
                        new_v = st.selectbox("Premio?", opts, index=idx, key=f"sel_{p['id']}")
                        if st.button("CONFERMA", key=f"btn_{p['id']}"): 
                            assign_achievement_to_lesson(p['id'], sel_std, (new_v if new_v != "Nessuno" else None))
                            st.rerun()

    else:
        # VISTA STUDENTE
        tab_agen, tab_carr = st.tabs(["AGENDA", "CARRIERA"])
        with tab_agen:
            me = get_student_details(st.session_state['username'])
            rec = me.get('recovery_lessons', 0)
            if rec > 0: st.warning(f"HAI {rec} LEZIONI DA RECUPERARE")
            nxt = calculate_next_lesson_number(st.session_state['username'])
            st.markdown(f"<div class='counter-box'><h2>LEZIONE {nxt} / 8</h2></div>", unsafe_allow_html=True)
            with st.form("new_bk"):
                d = st.date_input("Data", min_value=date.today())
                s = st.selectbox("Orario", ["10:00 - 13:00", "15:00 - 18:00"])
                if st.form_submit_button("PRENOTA"):
                    if d.weekday() in [0, 6]: st.error("Chiuso Lun/Dom")
                    else: add_booking(st.session_state['username'], d, s); st.rerun()
