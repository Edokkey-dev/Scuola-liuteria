import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import hashlib
import requests
import time
import extra_streamlit_components as stx
from datetime import datetime, date, timedelta
from supabase import create_client, Client

# --- 1. CONFIGURAZIONE PAGINA & CSS "BOTTEGA PRO" ---
st.set_page_config(page_title="Liuteria San Barnaba", page_icon="🎻", layout="centered")

st.markdown("""
<style>
    /* === GENERALI === */
    .stApp { background-color: #F9F7F2; }
    h1, h2, h3, h4, p, span, label, div { color: #3E2723; font-family: 'Helvetica Neue', sans-serif; }

    /* === SIDEBAR SCURA === */
    [data-testid="stSidebar"] { background-color: #2D1B15 !important; border-right: 2px solid #8B5A2B; }
    [data-testid="stSidebar"] * { color: #F5F5DC !important; }

    /* === LOGIN E INPUT === */
    [data-testid="stForm"] { background-color: #FFFFFF; padding: 30px; border-radius: 15px; border: 1px solid #D7CCC8; box-shadow: 0 10px 20px rgba(0,0,0,0.05); }
    .stTextInput > div > div > input, .stDateInput > div > div > input, div[data-baseweb="select"] > div {
        background-color: #FFFFFF !important; color: #000000 !important; border: 2px solid #8B5A2B !important; border-radius: 8px !important;
    }
    
    /* === BOTTONI === */
    .stButton > button { background-color: #5D4037 !important; color: #FFFFFF !important; border-radius: 8px !important; width: 100%; transition: 0.3s; font-weight:bold !important; }
    .stButton > button:hover { background-color: #3E2723 !important; color: #FFD700 !important; }

    /* === CARD E BOX === */
    .booking-card { background-color: white; padding: 15px; border-radius: 8px; border-left: 5px solid #5D4037; margin-bottom: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
    .history-card { background-color: #EFEBE9; padding: 10px; border-radius: 8px; margin-bottom: 5px; font-size: 0.9em; border-left: 5px solid #9E9E9E; }
    
    /* === ACHIEVEMENTS (CLASSIFICA METALLI) === */
    .ach-box {
        background-color: #FFFFFF; 
        border-radius: 12px; 
        padding: 15px; 
        text-align: center; 
        margin-bottom: 15px;
        transition: transform 0.2s;
    }
    .ach-box:hover { transform: scale(1.02); }
    
    /* STILI PER LIVELLO */
    .rank-bronze { border: 3px solid #CD7F32; box-shadow: 0 4px 0 #A0522D; } /* Bronzo */
    .rank-gold { border: 3px solid #FFD700; box-shadow: 0 4px 0 #DAA520; } /* Oro */
    .rank-platinum { border: 3px solid #E5E4E2; box-shadow: 0 0 15px rgba(229, 228, 226, 0.8); background: linear-gradient(145deg, #fff, #f4f4f4); } /* Platino */
    
    /* STATO BLOCCATO/SBLOCCATO */
    .ach-locked { opacity: 0.4; filter: grayscale(100%); }
    .ach-unlocked { opacity: 1; }
    
    .ach-title { font-weight: bold; font-size: 0.9rem; margin-top: 5px; color: #3E2723; }
    .ach-icon { font-size: 2rem; }
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

# --- FUNZIONI CORE ---
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

# --- FUNZIONI PRENOTAZIONI & STORICO ---
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

# --- FUNZIONI STUDENTI & ACHIEVEMENTS ---
def get_all_students():
    return supabase.table("users").select("username").eq("role", "student").execute().data

def get_student_details(u):
    res = supabase.table("users").select("*").eq("username", u).execute()
    return res.data[0] if res.data else None

def toggle_achievement(u, col_name, current_val):
    supabase.table("users").update({col_name: not current_val}).eq("username", u).execute()


# --- INTERFACCIA ---
st.markdown("<h1 style='text-align: center;'>🎻 Liuteria San Barnaba</h1>", unsafe_allow_html=True)
st.markdown("---")

if 'logged_in' not in st.session_state: st.session_state.update({'logged_in': False, 'username': '', 'role': ''})

# --- LOGIN ---
if not st.session_state['logged_in']:
    c1, c2, c3 = st.columns([1, 6, 1])
    with c2:
        t1, t2 = st.tabs(["🔐 Accedi", "📝 Registrati"])
        with t1:
            with st.form("log"):
                u = st.text_input("Username").strip()
                p = st.text_input("Password", type='password').strip()
                if st.form_submit_button("Entra"):
                    ud = verify_user(u, p)
                    if ud:
                        st.session_state.update({'logged_in':True, 'username':u, 'role':ud['role']})
                        cookie_manager.set("scuola_user_session", u, expires_at=datetime.now()+timedelta(days=30))
                        st.rerun()
                    else: st.error("Dati errati")
        with t2:
            with st.form("reg"):
                nu = st.text_input("Nuovo User").strip()
                np = st.text_input("Password", type='password').strip()
                ia = st.checkbox("Titolare"); ac = st.text_input("Codice Admin", type='password')
                if st.form_submit_button("Crea"):
                    r = "admin" if ia and ac == ADMIN_KEY else "student"
                    if ia and ac != ADMIN_KEY: st.error("Codice errato")
                    elif nu and np:
                        if add_user(nu, np, r): st.success("Fatto! Accedi.")
                        else: st.error("Esiste già")

# --- APP ---
else:
    identify_user_onesignal(st.session_state['username'])
    with st.sidebar:
        st.markdown(f"### 👤 {st.session_state['username']}")
        if st.button("Logout"): st.session_state['logged_in']=False; cookie_manager.delete("scuola_user_session"); st.rerun()

    # --- VISTA ADMIN ---
    if st.session_state['role'] == 'admin':
        tab_reg, tab_std = st.tabs(["📅 Registro Generale", "👥 Gestione Studenti"])
        
        with tab_reg:
            st.subheader("Prossime Lezioni")
            data = get_all_future_bookings_admin()
            for x in data:
                st.markdown(f"<div class='booking-card'><b>👤 {x['username']}</b><br>📅 {x['booking_date']} | 🕒 {x['slot']}</div>", unsafe_allow_html=True)
                if st.button("Elimina", key=x['id']): delete_booking(x['id']); st.rerun()
        
        with tab_std:
            st.subheader("Scheda Studente")
            students = [s['username'] for s in get_all_students()]
            sel_std = st.selectbox("Seleziona uno studente:", [""] + students)
            
            if sel_std:
                std_data = get_student_details(sel_std)
                
                # SEZIONE OBIETTIVI (Organizzati per Livello)
                st.markdown("### 🥉 Livello Bronzo (Elementi)")
                c1, c2, c3 = st.columns(3)
                
                # Helper function per le checkbox admin
                def make_check(col, label, db_col):
                    val = std_data.get(db_col, False)
                    if col.checkbox(label, value=val):
                        if not val: toggle_achievement(sel_std, db_col, False); st.rerun()
                    else:
                        if val: toggle_achievement(sel_std, db_col, True); st.rerun()

                make_check(c1, "Rosetta", "ach_rosetta")
                make_check(c2, "Ponte", "ach_ponte")
                make_check(c3, "Assemblata", "ach_assemblata")

                st.markdown("### 🥇 Livello Oro (Struttura)")
                c4, c5 = st.columns(2)
                make_check(c4, "Manico", "ach_manico")
                make_check(c5, "Corpo", "ach_corpo")

                st.markdown("### 💎 Livello Platino (Maestro)")
                c6 = st.columns(1)[0]
                make_check(c6, "Chitarra Completata", "ach_finita")

                st.divider()
                
                # SEZIONE STORICO
                st.write("#### 📜 Storico Lezioni")
                past = get_past_bookings(sel_std)
                if past:
                    for p in past:
                        st.markdown(f"<div class='history-card'>📅 {p['booking_date']} | 🕒 {p['slot']} <br> Lezione #{p['lesson_number']}</div>", unsafe_allow_html=True)
                else:
                    st.info("Nessuna lezione passata.")

    # --- VISTA STUDENTE ---
    else:
        tab_agen, tab_carr = st.tabs(["📅 Agenda", "🏆 Carriera"])
        
        with tab_agen:
            nxt = calculate_next_lesson_number(st.session_state['username'])
            st.markdown(f"""<div class="booking-card" style="background:#3E2723; color:gold; text-align:center;"><h2>Lezione {nxt} di 8</h2></div>""", unsafe_allow_html=True)
            
            with st.form("new_bk"):
                c1, c2 = st.columns(2)
                d = c1.date_input("Data", min_value=date.today())
                s = c2.selectbox("Orario", ["10:00 - 13:00", "15:00 - 18:00"])
                if st.form_submit_button("Prenota"):
                    if d.weekday() in [0, 6]: st.error("Chiuso Lun/Dom")
                    else:
                        ok, m = add_booking(st.session_state['username'], d, s)
                        if ok: st.success("Fatto!"); time.sleep(1); st.rerun()
                        else: st.warning(m)
            
            st.write("### Future")
            fut = get_future_bookings(st.session_state['username'])
            if fut:
                for x in fut:
                    st.markdown(f"<div class='booking-card'>📅 {x['booking_date']} | 🕒 {x['slot']}</div>", unsafe_allow_html=True)
                    if st.button("Annulla", key=x['id']): delete_booking(x['id']); st.rerun()
            else: st.info("Nessuna prenotazione futura.")

        with tab_carr:
            me = get_student_details(st.session_state['username'])
            
            st.subheader("La tua Bacheca")
            
            # Helper per visualizzare badge con rank
            def show_badge(col, title, active, icon, rank_class):
                state = "ach-unlocked" if active else "ach-locked"
                icon_display = icon if active else "🔒"
                col.markdown(f"""
                <div class='ach-box {rank_class} {state}'>
                    <div class='ach-icon'>{icon_display}</div>
                    <div class='ach-title'>{title}</div>
                </div>
                """, unsafe_allow_html=True)

            # BRONZO
            st.write("🥉 **Base**")
            b1, b2, b3 = st.columns(3)
            show_badge(b1, "Rosetta", me.get('ach_rosetta'), "🏵️", "rank-bronze")
            show_badge(b2, "Ponte", me.get('ach_ponte'), "🌉", "rank-bronze")
            show_badge(b3, "Assemblaggio", me.get('ach_assemblata'), "🔧", "rank-bronze")

            # ORO
            st.write("🥇 **Avanzato**")
            g1, g2 = st.columns(2)
            show_badge(g1, "Manico", me.get('ach_manico'), "🪵", "rank-gold")
            show_badge(g2, "Corpo", me.get('ach_corpo'), "🎸", "rank-gold")

            # PLATINO
            st.write("💎 **Maestro Liutaio**")
            p1 = st.columns(1)[0]
            show_badge(p1, "Chitarra Finita", me.get('ach_finita'), "🏆", "rank-platinum")
            
            st.divider()
            
            st.subheader("Storico")
            past = get_past_bookings(st.session_state['username'])
            if past:
                for p in past:
                    st.markdown(f"<div class='history-card'>✅ <b>{p['booking_date']}</b> | {p['slot']} <br> Lezione #{p['lesson_number']}</div>", unsafe_allow_html=True)
            else:
                st.write("Ancora nessuna lezione conclusa.")
                
