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

# --- CSS PERSONALIZZATO ---
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
    
    /* Bottoni */
    .stButton > button { 
        background-color: #C0A062 !important; 
        color: #FFFFFF !important; 
        border-radius: 2px !important; 
        width: 100%; 
        font-weight: 500 !important; 
        letter-spacing: 1px;
        text-transform: uppercase;
        border: none !important;
    }
    .stButton > button:hover { 
        background-color: #A08040 !important; 
        box-shadow: 0 4px 10px rgba(192, 160, 98, 0.4);
    }

    /* Box Contatore Lezioni */
    .counter-box {
        background-color: #2C2C2C; 
        padding: 25px; 
        border-radius: 4px; 
        text-align: center; 
        margin-bottom: 25px; 
        border: 1px solid #C0A062;
    }
    .counter-box h2 {
        color: #C0A062 !important; 
        margin: 0;
        font-family: 'Helvetica Neue', sans-serif;
    }
    
    /* Box Recuperi (Student View) */
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

    /* Card Storico e Admin */
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
    .history-card.special {
        background-color: #FFFAF0; 
        border-left: 4px solid #C0A062; 
    }
    .achievement-tag {
        display: inline-block; 
        background-color: #C0A062; 
        color: white; 
        padding: 3px 10px; 
        border-radius: 20px; 
        font-size: 0.75em; 
        margin-left: 10px; 
        text-transform: uppercase;
    }

    /* Badges */
    .ach-box { background-color: #FFFFFF; border-radius: 4px; padding: 15px; text-align: center; margin-bottom: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.03); border: 1px solid #eee; }
    .rank-bronze { border-bottom: 4px solid #CD7F32; }
    .rank-gold { border-bottom: 4px solid #FFD700; }
    .rank-platinum { border-bottom: 4px solid #E5E4E2; background: linear-gradient(to bottom right, #fff, #f8f9fa); }
    .ach-locked { opacity: 0.2; filter: grayscale(100%); }
    .ach-unlocked { opacity: 1; }
    .ach-icon { font-size: 2.5rem; margin-bottom: 10px; display:block; }
    .ach-title { font-weight: bold; text-transform: uppercase; font-size: 0.8rem; letter-spacing: 0.5px; }

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

# --- HEADER CON LOGO LOCALE ---
col_logo_1, col_logo_2, col_logo_3 = st.columns([1, 2, 1])
with col_logo_2:
    if os.path.exists("logo.png"):
        st.image("logo.png", use_column_width=True)
    else:
        st.markdown("<h1 style='text-align: center; color:#2C2C2C;'>Accademia Liuteria</h1>", unsafe_allow_html=True)

st.markdown("<div style='text-align:center; color:#666; font-style:italic; margin-bottom: 20px;'>San Barnaba</div>", unsafe_allow_html=True)

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
        
        # VISUALIZZAZIONE RECUPERI NELLA SIDEBAR PER STUDENTE
        if st.session_state['role'] == 'student':
            me_sidebar = get_student_details(st.session_state['username'])
            if me_sidebar and me_sidebar.get('recovery_lessons', 0) > 0:
                st.markdown(f"""
                <div style="background-color:#E65100; color:white; padding:10px; border-radius:4px; margin-top:10px; text-align:center;">
                    ⚠️ <b>RECUPERI: {me_sidebar.get('recovery_lessons')}</b>
                </div>
                """, unsafe_allow_html=True)

        st.markdown("---")
        if st.button("LOGOUT"): st.session_state['logged_in']=False; cookie_manager.delete("scuola_user_session"); st.rerun()

    # --- VISTA ADMIN ---
    if st.session_state['role'] == 'admin':
        tab_reg, tab_std = st.tabs(["REGISTRO", "STUDENTI"])
        
        with tab_reg:
            st.subheader("Registro Lezioni")
            data = get_all_future_bookings_admin()
            
            if data:
                for x in data:
                    with st.container():
                        st.markdown(f"""
                        <div class='booking-card' style='margin-bottom:0px;'>
                            <b>👤 {x['username']}</b><br>
                            📅 {x['booking_date']} | 🕒 {x['slot']}
                        </div>
                        """, unsafe_allow_html=True)
                        
                        c1, c2, c3 = st.columns([2, 1, 1])
                        with c1:
                            new_num = st.number_input("N° Lez.", min_value=1, max_value=100, value=x['lesson_number'], key=f"num_{x['id']}")
                        with c2:
                            st.write("") 
                            st.write("") 
                            if st.button("💾", key=f"save_{x['id']}"):
                                update_lesson_number(x['id'], new_num)
                                st.toast("Aggiornato!")
                                time.sleep(1)
                                st.rerun()
                        with c3:
                            st.write("")
                            st.write("")
                            if st.button("🗑️", key=f"del_{x['id']}"):
                                delete_booking(x['id'])
                                st.rerun()
                        st.markdown("---")
            else:
                st.info("Nessuna prenotazione.")
        
        with tab_std:
            st.subheader("Gestione Carriera")
            students = [s['username'] for s in get_all_students()]
            sel_std = st.selectbox("Seleziona Studente:", [""] + students)
            
            if sel_std:
                me = get_student_details(sel_std)
                
                # --- NUOVA SEZIONE RECUPERI ---
                st.markdown("### 🟠 Gestione Recuperi")
                col_rec_1, col_rec_2 = st.columns([1, 2])
                current_rec = me.get('recovery_lessons', 0)
                
                with col_rec_1:
                    # Input numerico per gestire i recuperi
                    new_rec_val = st.number_input("Lezioni da recuperare", min_value=0, value=current_rec, step=1)
                
                with col_rec_2:
                    st.write("")
                    st.write("")
                    if st.button("AGGIORNA RECUPERI"):
                        update_recovery_count(sel_std, new_rec_val)
                        st.toast("Recuperi aggiornati!")
                        time.sleep(1)
                        st.rerun()
                
                st.divider()

                st.write("**Stato Achievements:**")
                k1, k2, k3, k4 = st.columns(4)
                k1.caption(f"Rosetta: {'✅' if me.get('ach_rosetta') else '❌'}")
                k2.caption(f"Corpo: {'✅' if me.get('ach_corpo') else '❌'}")
                k3.caption(f"Manico: {'✅' if me.get('ach_manico') else '❌'}")
                k4.caption(f"Finita: {'✅' if me.get('ach_finita') else '❌'}")
                
                st.divider()
                st.write("#### Assegnazione su Storico")
                past = get_past_bookings(sel_std)
                
                if past:
                    for p in past:
                        with st.container():
                            col_info, col_action = st.columns([3, 2])
                            current_ach = p.get('achievement')
                            ach_display = f"🏆 {current_ach}" if current_ach else ""
                            col_info.markdown(f"""
                            <div class='history-card { "special" if current_ach else "" }'>
                                <b>{p['booking_date']}</b> (Lez. {p['lesson_number']})<br>
                                {p['slot']} <br>
                                <span style='color:#C0A062; font-weight:bold;'>{ach_display}</span>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            options = ["Nessuno"] + list(ACHIEVEMENTS_MAP.keys())
                            idx = 0
                            if current_ach in options: idx = options.index(current_ach)
                            
                            with col_action:
                                new_val = st.selectbox("Premio:", options, index=idx, key=f"sel_{p['id']}", label_visibility="collapsed")
                                if st.button("SALVA", key=f"btn_{p['id']}"):
                                    val_to_save = new_val if new_val != "Nessuno" else None
                                    assign_achievement_to_lesson(p['id'], sel_std, val_to_save)
                                    st.success("Fatto")
                                    time.sleep(1)
                                    st.rerun()
                else:
                    st.info("Nessuna lezione.")

    # --- VISTA STUDENTE ---
    else:
        tab_agen, tab_carr = st.tabs(["AGENDA", "CARRIERA"])
        
        with tab_agen:
            # Recupero dati aggiornati per mostrare eventuali recuperi
            me = get_student_details(st.session_state['username'])
            recuperi = me.get('recovery_lessons', 0)
            
            if recuperi > 0:
                st.markdown(f"<div class='recovery-alert'>⚠️ HAI {recuperi} LEZIONI DA RECUPERARE</div>", unsafe_allow_html=True)

            nxt = calculate_next_lesson_number(st.session_state['username'])
            st.markdown(f"""
            <div class="counter-box">
                <h2>LEZIONE {nxt} / 8</h2>
            </div>
            """, unsafe_allow_html=True)
            
            with st.form("new_bk"):
                c1, c2 = st.columns(2)
                d = c1.date_input("Data", min_value=date.today())
                s = c2.selectbox("Orario", ["10:00 - 13:00", "15:00 - 18:00"])
                if st.form_submit_button("PRENOTA"):
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
                    if st.button("ANNULLA", key=x['id']): delete_booking(x['id']); st.rerun()
            else: st.info("Nessuna prenotazione futura.")

        with tab_carr:
            me = get_student_details(st.session_state['username'])
            
            def show_badge(col, title, active, icon, rank_class):
                state = "ach-unlocked" if active else "ach-locked"
                icon_display = icon if active else "🔒"
                col.markdown(f"""<div class='ach-box {rank_class} {state}'><span class='ach-icon'>{icon_display}</span><span class='ach-title'>{title}</span></div>""", unsafe_allow_html=True)

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
            p1 = st.columns(1)[0]
            show_badge(p1, "Chitarra Finita", me.get('ach_finita'), "🏆", "rank-platinum")
            
            st.divider()
            
            st.subheader("Il tuo Percorso")
            past = get_past_bookings(st.session_state['username'])
            if past:
                for p in past:
                    is_special = p.get('achievement') is not None
                    ach_html = f"<span class='achievement-tag'>🏆 {p['achievement']}</span>" if is_special else ""
                    cls_special = "special" if is_special else ""
                    
                    st.markdown(f"""
                    <div class='history-card {cls_special}'>
                        ✅ <b>{p['booking_date']}</b> (Lez. {p['lesson_number']})<br>
                        {p['slot']} {ach_html}
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.write("Nessuna lezione passata.")
