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
    except: pass

def save_notification_to_db(username, message):
    try: supabase.table("notifications").insert({"username": username, "message": message}).execute()
    except: pass

def send_notification(message, target_usernames=None, heading="Scuola Liuteria"):
    if target_usernames:
        for user in target_usernames:
            save_notification_to_db(user, message)
    try:
        app_id = st.secrets["onesignal"]["app_id"]
        api_key = st.secrets["onesignal"]["api_key"]
        header = {"Authorization": "Basic " + api_key}
        payload = {
            "app_id": app_id,
            "headings": {"en": heading},
            "contents": {"en": message},
            "channel_for_external_user_ids": "push"
        }
        if target_usernames: payload["include_external_user_ids"] = target_usernames
        else: payload["included_segments"] = ["Subscribed Users"]
        requests.post("https://onesignal.com/api/v1/notifications", headers=header, json=payload)
        return True
    except: return False

def get_my_notifications(username):
    clean_old_notifications()
    response = supabase.table("notifications").select("*").eq("username", username).order("created_at", desc=True).execute()
    return response.data

# --- LOGICA DB UTENTI ---
def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def verify_user(username, password):
    try:
        hashed = hash_password(password)
        response = supabase.table("users").select("*").eq("username", username).eq("password", hashed).execute()
        return response.data[0] if response.data else None
    except: return None

def get_user_role(username):
    try:
        response = supabase.table("users").select("role").eq("username", username).execute()
        return response.data[0]['role'] if response.data else None
    except: return None

def add_user(username, password, role):
    try:
        data = {"username": username, "password": hash_password(password), "role": role}
        supabase.table("users").insert(data).execute()
        return True
    except: return False

def update_password(username, new_password):
    try:
        hashed = hash_password(new_password)
        supabase.table("users").update({"password": hashed}).eq("username", username).execute()
        return True
    except: return False

def calculate_next_lesson_number(username):
    res = supabase.table("bookings").select("*", count="exact").eq("username", username).execute()
    return (res.count % 8) + 1

# --- LOGICA PRENOTAZIONI ---
def add_booking(username, booking_date, slot):
    str_date = booking_date.strftime("%Y-%m-%d")
    check = supabase.table("bookings").select("*").eq("username", username).eq("booking_date", str_date).eq("slot", slot).execute()
    if check.data: return False, "Già prenotato."
    
    lesson_num = calculate_next_lesson_number(username)
    new_bk = {"username": username, "booking_date": str_date, "slot": slot, "lesson_number": lesson_num}
    
    try:
        supabase.table("bookings").insert(new_bk).execute()
        try:
            admin = st.secrets["onesignal"]["admin_username"]
            send_notification(f"{username}: {str_date} {slot}", [admin], "Nuova Prenotazione")
        except: pass
        if lesson_num == 8:
            send_notification("8 Lezioni completate! Rinnova abbonamento.", [username], "Traguardo 🎻")
        return True, lesson_num
    except Exception as e: return False, str(e)

def get_my_bookings(username):
    return supabase.table("bookings").select("*").eq("username", username).order("booking_date", desc=False).execute().data

def get_all_bookings_admin():
    return supabase.table("bookings").select("*").order("booking_date", desc=True).execute().data

def delete_booking_admin(bid):
    try:
        res = supabase.table("bookings").select("*").eq("id", bid).execute()
        if res.data:
            bk = res.data[0]
            supabase.table("bookings").delete().eq("id", bid).execute()
            send_notification(f"Lezione del {bk['booking_date']} annullata.", [bk['username']], "Cancellazione ❌")
            return True
    except: return False

def delete_booking_student(bid):
    supabase.table("bookings").delete().eq("id", bid).execute()

# --- HEADER LOGO ---
st.markdown("<h1 style='text-align: center;'>🎻 Scuola di Liuteria</h1>", unsafe_allow_html=True)
st.markdown("---")

# --- INIT SESSION ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    st.session_state['username'] = ''
    st.session_state['role'] = ''

# --- AUTO LOGIN ---
if not st.session_state['logged_in']:
    try:
        c_user = cookie_manager.get("scuola_user_session")
        if c_user:
            role = get_user_role(c_user)
            if role:
                st.session_state['logged_in'] = True
                st.session_state['username'] = c_user
                st.session_state['role'] = role
                st.rerun()
    except: pass

# --- LOGIN UI ---
if not st.session_state['logged_in']:
    col1, col2, col3 = st.columns([1, 8, 1]) # Centra il contenuto
    with col2:
        tab1, tab2 = st.tabs(["🔐 Accedi", "📝 Registrati"])
        
        with tab1:
            st.write("Bentornato in bottega.")
            with st.form("login"):
                u = st.text_input("Username").strip()
                p = st.text_input("Password", type='password').strip()
                rem = st.checkbox("Resta collegato")
                if st.form_submit_button("Entra"):
                    ud = verify_user(u, p)
                    if ud:
                        st.session_state.update({'logged_in':True, 'username':u, 'role':ud['role']})
                        if rem:
                            cookie_manager.set("scuola_user_session", u, expires_at=datetime.now()+timedelta(days=30))
                            time.sleep(1)
                        st.rerun()
                    else: st.error("Credenziali non valide.")

        with tab2:
            st.write("Crea il tuo profilo studente.")
            with st.form("reg"):
                nu = st.text_input("Username").strip()
                np = st.text_input("Password", type='password').strip()
                ia = st.checkbox("Sono il Titolare")
                ac = st.text_input("Codice Admin", type='password')
                if st.form_submit_button("Registrati"):
                    role = "student"
                    if ia:
                        if ac == ADMIN_KEY: role="admin"
                        else: st.error("Codice errato!"); st.stop()
                    
                    if nu and np:
                        if add_user(nu, np, role): st.success("Registrato! Ora accedi.");
                        else: st.error("Username già in uso.")
                    else: st.warning("Compila i campi.")

# --- APP INTERNA ---
else:
    identify_user_onesignal(st.session_state['username'])
    
    # Sidebar
    with st.sidebar:
        st.title(f"👤 {st.session_state['username']}")
        st.write(f"Ruolo: **{st.session_state['role'].upper()}**")
        st.markdown("---")
        if st.button("🚪 Esci"):
            st.session_state['logged_in'] = False
            cookie_manager.delete("scuola_user_session")
            time.sleep(1)
            st.rerun()

    tab_bk, tab_nt = st.tabs(["📅 Agenda", "🔔 Avvisi"])

    # --- TAB PRENOTAZIONI ---
    with tab_bk:
        # VISTA ADMIN
        if st.session_state['role'] == 'admin':
            st.info("🔧 Pannello di Controllo")
            
            with st.expander("🔑 Reset Password Studente"):
                with st.form("reset_pwd"):
                    c1, c2 = st.columns(2)
                    tu = c1.text_input("Studente").strip()
                    tp = c2.text_input("Nuova Password").strip()
                    if st.form_submit_button("Aggiorna"):
                        if update_password(tu, tp): st.success("Password Aggiornata!")
                        else: st.error("Errore.")
            
            st.write("### 📜 Registro Lezioni")
            data = get_all_bookings_admin()
            if data:
                for x in data:
                    # Layout a scheda personalizzato
                    st.markdown(f"""
                    <div class="booking-card">
                        <b>👤 {x['username']}</b> <br>
                        📅 {x['booking_date']} <br>
                        🕒 {x['slot']} <br>
                        🎻 Lezione n. {x['lesson_number']}
                    </div>
                    """, unsafe_allow_html=True)
                    if st.button("Cancella Prenotazione", key=f"d_{x['id']}"):
                        delete_booking_admin(x['id'])
                        st.rerun()
            else: st.info("Nessuna prenotazione attiva.")

        # VISTA STUDENTE
        elif st.session_state['role'] == 'student':
            nxt = calculate_next_lesson_number(st.session_state['username'])
            
            # Box riassuntivo
            st.markdown(f"""
            <div style="background-color:#8B5A2B; padding:15px; border-radius:10px; color:white; text-align:center; margin-bottom:20px;">
                <h2 style="color:white !important; margin:0;">Lezione {nxt} di 8</h2>
                <p>Pacchetto attivo</p>
            </div>
            """, unsafe_allow_html=True)

            with st.expander("➕ Prenota Nuova Lezione", expanded=True):
                with st.form("new_bk"):
                    c1, c2 = st.columns(2)
                    d = c1.date_input("Giorno", min_value=date.today())
                    s = c2.selectbox("Orario", ["10:00 - 13:00", "15:00 - 18:00"])
                    if st.form_submit_button("Conferma Prenotazione"):
                        if d.weekday() in [0, 6]: st.error("Chiuso Lunedì e Domenica.")
                        else:
                            ok, msg = add_booking(st.session_state['username'], d, s)
                            if ok: st.success("Prenotato!"); time.sleep(1); st.rerun()
                            else: st.warning(msg)
            
            st.write("### 🎻 Le tue prenotazioni")
            my_b = get_my_bookings(st.session_state['username'])
            IT_DAYS = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]
            
            if my_b:
                for x in my_b:
                    try: 
                        dt = datetime.strptime(x['booking_date'], "%Y-%m-%d")
                        giorno = IT_DAYS[dt.weekday()]
                        fmt_date = dt.strftime("%d/%m")
                    except: giorno=""
                    
                    # Scheda visuale
                    st.markdown(f"""
                    <div class="booking-card">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <div>
                                <span style="font-size:1.2em; font-weight:bold; color:#8B5A2B;">{giorno} {fmt_date}</span><br>
                                🕒 {x['slot']}
                            </div>
                            <div style="font-size:1.5em; font-weight:bold; color:#D7CCC8;">#{x['lesson_number']}</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if st.button("Annulla", key=f"del_{x['id']}"):
                        delete_booking_student(x['id'])
                        st.rerun()
            else: st.info("Non hai lezioni programmate.")

    # --- TAB AVVISI ---
    with tab_nt:
        st.subheader("Bacheca Messaggi")
        msgs = get_my_notifications(st.session_state['username'])
        if msgs:
            for m in msgs:
                try: d = datetime.fromisoformat(m['created_at'].replace('Z','')).strftime("%d/%m %H:%M")
                except: d = ""
                st.info(f"📅 **{d}**\n\n{m['message']}")
        else:
            st.write("📭 Nessuna nuova notifica.")
