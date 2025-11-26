import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import hashlib
import requests
import extra_streamlit_components as stx
from datetime import datetime, date, timedelta
from supabase import create_client, Client

# --- CONFIGURAZIONE ---
ADMIN_KEY = st.secrets["admin_password"]

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
    st.error("Errore critico: Impossibile connettersi al Database. Controlla i secrets.")
    st.stop()

# --- GESTORE COOKIE ---
def get_manager():
    return stx.CookieManager()

cookie_manager = get_manager()

# --- ONE SIGNAL ---
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
            }});
            OneSignal.setExternalUserId("{username}");
          }});
        </script>
        """
        components.html(js_code, height=0)
    except:
        pass

# --- GESTIONE NOTIFICHE ---
def clean_old_notifications():
    try:
        cutoff_date = (datetime.now() - timedelta(days=30)).isoformat()
        supabase.table("notifications").delete().lt("created_at", cutoff_date).execute()
    except Exception as e:
        print(f"Errore pulizia: {e}")

def save_notification_to_db(username, message):
    try:
        supabase.table("notifications").insert({"username": username, "message": message}).execute()
    except: pass

def send_notification(message, target_usernames=None, heading="Avviso Scuola"):
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

# --- FUNZIONI UTENTI ---
def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def verify_user(username, password):
    try:
        hashed = hash_password(password)
        response = supabase.table("users").select("*").eq("username", username).eq("password", hashed).execute()
        if response.data: return response.data[0]
        return None
    except: return None

def get_user_role(username):
    try:
        response = supabase.table("users").select("role").eq("username", username).execute()
        if response.data: return response.data[0]['role']
        return None
    except: return None

def add_user(username, password, role):
    try:
        data = {"username": username, "password": hash_password(password), "role": role}
        supabase.table("users").insert(data).execute()
        return True
    except: return False

def calculate_next_lesson_number(username):
    response = supabase.table("bookings").select("*", count="exact").eq("username", username).execute()
    return (response.count % 8) + 1

# --- LOGICA PRENOTAZIONI ---
def add_booking(username, booking_date, slot):
    str_date = booking_date.strftime("%Y-%m-%d")
    check = supabase.table("bookings").select("*").eq("username", username).eq("booking_date", str_date).eq("slot", slot).execute()
    if check.data: return False, "Prenotazione esistente."
    
    lesson_num = calculate_next_lesson_number(username)
    new_booking = {"username": username, "booking_date": str_date, "slot": slot, "lesson_number": lesson_num}
    
    try:
        supabase.table("bookings").insert(new_booking).execute()
        try:
            admin_user = st.secrets["onesignal"]["admin_username"]
            send_notification(f"{username} ha prenotato: {str_date} {slot}", [admin_user], "Nuova Lezione")
        except: pass
        if lesson_num == 8:
            send_notification("Hai raggiunto l'ottava lezione!", [username], "Traguardo 🎉")
        return True, lesson_num
    except Exception as e: return False, str(e)

def get_my_bookings(username):
    response = supabase.table("bookings").select("*").eq("username", username).order("booking_date", desc=False).execute()
    return response.data

def get_all_bookings_admin():
    response = supabase.table("bookings").select("*").order("booking_date", desc=True).execute()
    return response.data

def delete_booking_admin(booking_id):
    try:
        res = supabase.table("bookings").select("*").eq("id", booking_id).execute()
        if res.data:
            booking = res.data[0]
            student_name = booking['username']
            b_date = booking['booking_date']
            supabase.table("bookings").delete().eq("id", booking_id).execute()
            send_notification(f"Lezione del {b_date} cancellata.", [student_name], "Cancellazione ❌")
            return True
    except: return False

def delete_booking_student(booking_id):
    supabase.table("bookings").delete().eq("id", booking_id).execute()

# --- INTERFACCIA ---
st.set_page_config(page_title="Gestione Scuola", layout="centered")
st.title("📚 Portale Prenotazioni Scuola")

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    st.session_state['username'] = ''
    st.session_state['role'] = ''

# Cookie Login Check
if not st.session_state['logged_in']:
    cookie_user = cookie_manager.get("scuola_user_session")
    if cookie_user:
        role = get_user_role(cookie_user)
        if role:
            st.session_state['logged_in'] = True
            st.session_state['username'] = cookie_user
            st.session_state['role'] = role
            st.rerun()

if not st.session_state['logged_in']:
    tab1, tab2 = st.tabs(["🔐 Accedi", "📝 Registrati"])

    with tab1:
        st.subheader("Accedi")
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type='password')
            remember_me = st.checkbox("Ricordami")
            if st.form_submit_button("Entra"):
                user_data = verify_user(username, password)
                if user_data:
                    st.session_state['logged_in'] = True
                    st.session_state['username'] = username
                    st.session_state['role'] = user_data['role']
                    if remember_me:
                        cookie_manager.set("scuola_user_session", username, expires_at=datetime.now() + timedelta(days=30))
                    st.rerun()
                else: st.error("Dati errati.")

    with tab2:
        st.subheader("Nuovo Profilo")
        with st.form("register_form"):
            new_user = st.text_input("Scegli Username")
            new_pass = st.text_input("Scegli Password", type='password')
            st.markdown("---")
            is_admin = st.checkbox("Sono il Titolare")
            admin_code = st.text_input("Codice Segreto", type='password')
            if st.form_submit_button("Crea Account"):
                role = "student"
                valid = True
                if is_admin:
                    if admin_code == ADMIN_KEY: role = "admin"
                    else: valid = False; st.error("Chiave errata!")
                
                if valid and new_user and new_pass:
                    if add_user(new_user, new_pass, role): st.success("Creato! Accedi."); 
                    else: st.error("Username esistente.")
                elif valid: st.warning("Compila tutto.")

else:
    identify_user_onesignal(st.session_state['username'])
    st.sidebar.title(f"Ciao, {st.session_state['username']}")
    if st.sidebar.button("Logout"):
        st.session_state['logged_in'] = False
        cookie_manager.delete("scuola_user_session")
        st.rerun()

    tab_booking, tab_notif = st.tabs(["📅 Prenotazioni", "🔔 Notifiche"])

    with tab_booking:
        if st.session_state['role'] == 'admin':
            st.subheader("👑 Registro Globale")
            data = get_all_bookings_admin()
            if data:
                for item in data:
                    with st.container():
                        c1, c2 = st.columns([4, 1])
                        c1.markdown(f"**{item['username']}** | {item['booking_date']} | {item['slot']} | Lez: {item['lesson_number']}")
                        if c2.button("❌", key=f"d_{item['id']}"):
                            delete_booking_admin(item['id'])
                            st.rerun()
                        st.divider()
            else: st.info("Nessuna prenotazione.")

        elif st.session_state['role'] == 'student':
            next_l = calculate_next_lesson_number(st.session_state['username'])
            st.metric("Prossima Lezione", f"N° {next_l} di 8")

            with st.expander("➕ Nuova Prenotazione", expanded=True):
                with st.form("bk_form"):
                    col1, col2 = st.columns(2)
                    with col1: d = st.date_input("Data", min_value=date.today())
                    with col2: s = st.selectbox("Orario", ["10:00 - 13:00", "15:00 - 18:00"])
                    if st.form_submit_button("Conferma"):
                        if d.weekday() not in [1,2,3,4,5]: st.error("Chiuso Lun/Dom.")
                        else:
                            ok, msg = add_booking(st.session_state['username'], d, s)
                            if ok: st.success(f"Fatto! Lezione {msg}"); import time; time.sleep(1); st.rerun()
                            else: st.warning(msg)

            st.subheader("Le tue Lezioni")
            my_b = get_my_bookings(st.session_state['username'])
            
            # --- MODIFICA QUI SOTTO PER IL GIORNO DELLA SETTIMANA ---
            GIORNI_IT = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]
            
            if my_b:
                for item in my_b:
                    # Calcolo del giorno
                    data_str = item['booking_date']
                    try:
                        data_obj = datetime.strptime(data_str, "%Y-%m-%d")
                        nome_giorno = GIORNI_IT[data_obj.weekday()]
                    except:
                        nome_giorno = "" # Fallback se la data è strana

                    with st.container():
                        c1, c2, c3 = st.columns([1,3,1])
                        c1.markdown(f"## {item['lesson_number']}")
                        # Visualizzazione: Esempio "Martedì 2023-11-28"
                        c2.markdown(f"**{nome_giorno} {data_str}**\n\n{item['slot']}")
                        if c3.button("Cancella", key=f"ud_{item['id']}"):
                            delete_booking_student(item['id'])
                            st.rerun()
                        st.divider()
            else: st.info("Nessuna lezione.")

    with tab_notif:
        st.subheader("I tuoi messaggi")
        notifiche = get_my_notifications(st.session_state['username'])
        if notifiche:
            for notif in notifiche:
                data_grezza = notif['created_at']
                try:
                    data_obj = datetime.fromisoformat(data_grezza.replace('Z', '+00:00'))
                    data_fmt = data_obj.strftime("%d/%m/%Y %H:%M")
                except: data_fmt = data_grezza
                st.info(f"📅 **{data_fmt}**\n\n{notif['message']}")
        else: st.write("📭 Nessun messaggio.")
