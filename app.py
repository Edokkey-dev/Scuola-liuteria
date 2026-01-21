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

# --- 1. CONFIGURAZIONE PAGINA & CSS "SAN BARNABA" ---
st.set_page_config(page_title="Accademia Liuteria San Barnaba", page_icon="🎻", layout="centered")

# --- CSS DEFINITIVO (Fix per scritte invisibili) ---
st.markdown("""
<style>
    /* Sfondo Generale */
    .stApp { background-color: #FAF9F6; }
    
    /* Font e Testi */
    h1, h2, h3, h4, p, span, label, div { 
        color: #2C2C2C; 
        font-family: 'Georgia', serif; 
    }

    /* Sidebar */
    [data-testid="stSidebar"] { 
        background-color: #1E1E1E !important; 
        border-right: 1px solid #C0A062; 
    }
    [data-testid="stSidebar"] * { color: #E0E0E0 !important; }

    /* Login Box */
    [data-testid="stForm"] { 
        background-color: #FFFFFF; 
        padding: 40px; 
        border-radius: 4px; 
        border-top: 5px solid #C0A062; 
        box-shadow: 0 10px 30px rgba(0,0,0,0.08); 
    }
    
    /* Input Fields */
    .stTextInput > div > div > input, .stDateInput > div > div > input, .stNumberInput > div > div > input, div[data-baseweb="select"] > div {
        background-color: #FFFFFF !important; 
        color: #333 !important; 
        border: 1px solid #ccc !important; 
        border-radius: 2px !important;
    }
    
    /* BOTTONE PRENOTA E ALTRI (Fix Testo Invisibile) */
    .stButton > button { 
        background-color: #1E1E1E !important; /* Nero/Marrone scuro come il box */
        color: #C0A062 !important; /* Testo ORO brillante */
        border-radius: 4px !important; 
        width: 100%; 
        font-weight: bold !important; 
        letter-spacing: 1px;
        text-transform: uppercase;
        border: 1px solid #C0A062 !important;
        height: 3em;
    }
    .stButton > button:hover { 
        background-color: #C0A062 !important; 
        color: #1E1E1E !important;
    }

    /* BOX CONTATORE LEZIONI (Fix Testo Invisibile) */
    .counter-box {
        background-color: #1E1E1E; 
        padding: 30px; 
        border-radius: 4px; 
        text-align: center; 
        margin-bottom: 25px; 
        border: 1px solid #C0A062;
    }
    .counter-box h2 {
        color: #C0A062 !important; /* ORO brillante su fondo nero */
        margin: 0;
        font-family: 'Helvetica Neue', sans-serif;
        font-size: 2.5rem;
    }
    
    /* Alert Recuperi */
    .recovery-alert {
        background-color: #FFF3E0;
        border: 1px solid #FFB74D;
        color: #E65100;
        padding: 10px;
        border-radius: 4px;
        text-align: center;
        font-weight: bold;
        margin-bottom: 15px;
    }

    /* Card Storico */
    .booking-card { 
        background-color: white; 
        padding: 15px; 
        border-radius: 2px; 
        border-left: 4px solid #C0A062; 
        margin-bottom: 15px; 
        box-shadow: 0 2px 5px rgba(0,0,0,0.05); 
    }
    .history-card { 
        background-color: #F4F4F4; 
        padding: 15px; 
        border-radius: 2px; 
        margin-bottom: 10px; 
        border-left: 4px solid #999; 
    }
</style>
""", unsafe_allow_html=True)

# --- 2. BACKEND ---
try: ADMIN_KEY = st.secrets["admin_password"]
except: st.error("Errore Secrets."); st.stop()

@st.cache_resource
def init_connection():
    try: return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])
    except: return None

supabase = init_connection()
cookie_manager = stx.CookieManager()

# --- DIZIONARIO OBIETTIVI ---
ACHIEVEMENTS_MAP = {
    "Rosetta 🏵️": "ach_rosetta",
    "Ponte 🌉": "ach_ponte",
    "Assemblata 🔧": "ach_assemblata",
    "Manico 🪵": "ach_manico",
    "Corpo 🎸": "ach_corpo",
    "Chitarra Finita 🏆": "ach_finita"
}

# --- FUNZIONI UTILI ---
def hash_password(p): return hashlib.sha256(str.encode(p)).hexdigest()
def verify_user(u, p):
    res = supabase.table("users").select("*").eq("username", u).eq("password", hash_password(p)).execute()
    return res.data[0] if res.data else None
def add_user(u, p, r):
    try: supabase.table("users").insert({"username": u, "password": hash_password(p), "role": r}).execute(); return True
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
    try:
        supabase.table("bookings").update({"lesson_number": new_number}).eq("id", booking_id).execute()
        return True
    except: return False

def update_recovery_count(username, new_count):
    try:
        supabase.table("users").update({"recovery_lessons": new_count}).eq("username", username).execute()
        return True
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
    if os.path.exists("logo.png"):
        st.image("logo.png", use_column_width=True)
    else:
        st.markdown("<h1 style='text-align: center; color:#2C2C2C;'>Liuteria San Barnaba</h1>", unsafe_allow_html=True)

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
        with t2:
            with st.form("reg"):
                nu = st.text_input("Nuovo User").strip()
                np = st.text_input("Password", type='password').strip()
                ia = st.checkbox("Sono Titolare"); ac = st.text_input("Codice Admin", type='password')
                if st.form_submit_button("CREA ACCOUNT"):
                    r = "admin" if ia and ac == ADMIN_KEY else "student"
                    if ia and ac != ADMIN_KEY: st.error("Codice errato")
                    elif nu and np:
                        if add_user(nu, np, r): st.success("Fatto! Accedi.")
                        else: st.error("Esiste già")

# APP INTERNA
else:
    identify_user_onesignal(st.session_state['username'])
    with st.sidebar:
        if os.path.exists("sidebar.jpg"):
            st.image("sidebar.jpg", use_column_width=True)
        st.markdown(f"### 👤 {st.session_state['username'].upper()}")
        if st.session_state['role'] == 'student':
            me_sidebar = get_student_details(st.session_state['username'])
            if me_sidebar and me_sidebar.get('recovery_lessons', 0) > 0:
                st.markdown(f"<div style='background-color:#E65100; color:white; padding:10px; border-radius:4px; margin-top:10px; text-align:center;'>⚠️ <b>RECUPERI: {me_sidebar.get('recovery_lessons')}</b></div>", unsafe_allow_html=True)
        st.markdown("---")
        if st.button("LOGOUT"): st.session_state['logged_in']=False; cookie_manager.delete("scuola_user_session"); st.rerun()

    if st.session_state['role'] == 'admin':
        tab_reg, tab_std = st.tabs(["REGISTRO", "STUDENTI"])
        with tab_reg:
            st.subheader("Agenda Lezioni")
            data = get_all_future_bookings_admin()
            if data:
                for x in data:
                    with st.container():
                        st.markdown(f"<div class='booking-card' style='margin-bottom:0px;'><b>👤 {x['username']}</b><br>📅 {x['booking_date']} | 🕒 {x['slot']}</div>", unsafe_allow_html=True)
                        c1, c2, c3 = st.columns([2, 1, 1])
                        with c1: new_num = st.number_input("N° Lez.", min_value=1, value=x['lesson_number'], key=f"n_{x['id']}")
                        with c2: 
                            if st.button("💾", key=f"s_{x['id']}"): 
                                update_lesson_number(x['id'], new_num)
                                st.rerun()
                        with c3:
                            if st.button("🗑️", key=f"d_{x['id']}"): 
                                delete_booking(x['id'])
                                st.rerun()
                        st.markdown("---")
        with tab_std:
            st.subheader("Gestione Carriera")
            students = [s['username'] for s in get_all_students()]
            sel_std = st.selectbox("Seleziona Studente:", [""] + students)
            if sel_std:
                me = get_student_details(sel_std)
                st.markdown("### 🟠 Gestione Recuperi")
                cr = me.get('recovery_lessons', 0)
                nr = st.number_input("Lezioni da recuperare", min_value=0, value=cr)
                if st.button("AGGIORNA RECUPERI"):
                    update_recovery_count(sel_std, nr)
                    st.rerun()
                st.divider()
                st.write("#### Storico & Assegnazione Obiettivi")
                past = get_past_bookings(sel_std)
                if past:
                    for p in past:
                        with st.container():
                            curr_ach = p.get('achievement')
                            st.markdown(f"<div class='history-card { 'special' if curr_ach else '' }'><b>{p['booking_date']}</b> (Lez. {p['lesson_number']})<br>{p['slot']} <b>{('🏆 ' + curr_ach) if curr_ach else ''}</b></div>", unsafe_allow_html=True)
                            opts = ["Nessuno"] + list(ACHIEVEMENTS_MAP.keys())
                            idx = opts.index(curr_ach) if curr_ach in opts else 0
                            new_val = st.selectbox("Obiettivo raggiunto?", opts, index=idx, key=f"sel_{p['id']}")
                            if st.button("SALVA PREMIO", key=f"btn_{p['id']}"):
                                assign_achievement_to_lesson(p['id'], sel_std, (new_val if new_val != "Nessuno" else None))
                                st.rerun()

    else:
        tab_agen, tab_carr = st.tabs(["AGENDA", "CARRIERA"])
        with tab_agen:
            me = get_student_details(st.session_state['username'])
            rec = me.get('recovery_lessons', 0)
            if rec > 0: st.markdown(f"<div class='recovery-alert'>⚠️ HAI {rec} LEZIONI DA RECUPERARE</div>", unsafe_allow_html=True)
            nxt = calculate_next_lesson_number(st.session_state['username'])
            st.markdown(f"<div class='counter-box'><h2>LEZIONE {nxt} / 8</h2></div>", unsafe_allow_html=True)
            with st.form("new_bk"):
                c1, c2 = st.columns(2)
                d = c1.date_input("Data", min_value=date.today())
                s = c2.selectbox("Orario", ["10:00 - 13:00", "15:00 - 18:00"])
                if st.form_submit_button("PRENOTA"):
                    if d.weekday() in [0, 6]: st.error("Chiuso Lun/Dom")
                    else:
                        ok, m = add_booking(st.session_state['username'], d, s)
                        if ok: st.rerun()
                        else: st.warning(m)
            st.write("### Future")
            fut = get_future_bookings(st.session_state['username'])
            for x in fut:
                st.markdown(f"<div class='booking-card'>📅 {x['booking_date']} | 🕒 {x['slot']}</div>", unsafe_allow_html=True)
                if st.button("ANNULLA", key=x['id']): delete_booking(x['id']); st.rerun()

        with tab_carr:
            me = get_student_details(st.session_state['username'])
            def show_badge(col, title, active, icon, rank_class):
                stt = "ach-unlocked" if active else "ach-locked"
                ico = icon if active else "🔒"
                col.markdown(f"<div class='ach-box {rank_class} {stt}'><span class='ach-icon'>{ico}</span><span class='ach-title'>{title}</span></div>", unsafe_allow_html=True)
            st.write("🥉 **ELEMENTI BASE**")
            b1, b2, b3 = st.columns(3)
            show_badge(b1, "Rosetta", me.get('ach_rosetta'), "🏵️", "rank-bronze")
            show_badge(b2, "Ponte", me.get('ach_ponte'), "🌉", "rank-bronze")
            show_badge(b3, "Assemblaggio", me.get('ach_assemblata'), "🔧", "rank-bronze")
            st.write("🥇 **STRUTTURA**")
            g1, g2 = st.columns(2)
            show_badge(g1, "Manico", me.get('ach_manico'), "🪵", "rank-gold")
            show_badge(g2, "Corpo", me.get('ach_corpo'), "🎸", "rank-gold")
            st.write("💎 **MAESTRO**")
            p1 = st.columns(1)[0]; show_badge(p1, "Chitarra Finita", me.get('ach_finita'), "🏆", "rank-platinum")
            st.divider()
            st.subheader("Il tuo Percorso")
            past = get_past_bookings(st.session_state['username'])
            for p in past:
                ach = p.get('achievement')
                st.markdown(f"<div class='history-card { 'special' if ach else '' }'>✅ <b>{p['booking_date']}</b> (Lez. {p['lesson_number']})<br>{p['slot']} {('<span class=\"achievement-tag\">🏆 '+ach+'</span>') if ach else ''}</div>", unsafe_allow_html=True)
