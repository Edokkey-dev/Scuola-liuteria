import streamlit as st
import streamlit.components.v1 as components # NECESSARIO PER IL PONTE JAVASCRIPT
import pandas as pd
import hashlib
import smtplib
import requests
import random
import string
from email.mime.text import MIMEText
from datetime import datetime, date
from supabase import create_client, Client

# --- CONFIGURAZIONE ---
ADMIN_KEY = "Francescorussoascoltaultimo"

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

# --- FUNZIONE PONTE: COLLEGA UTENTE A ONESIGNAL ---
def identify_user_onesignal(username):
    """
    Inserisce uno script invisibile che dice a OneSignal:
    'L'utente attuale è [username]'
    """
    onesignal_app_id = st.secrets["onesignal"]["app_id"]
    
    # Questo script Javascript viene eseguito nel browser/app dell'utente
    js_code = f"""
    <script src="https://cdn.onesignal.com/sdks/OneSignalSDK.js" async=""></script>
    <script>
      window.OneSignal = window.OneSignal || [];
      OneSignal.push(function() {{
        OneSignal.init({{
          appId: "{onesignal_app_id}",
          allowLocalhostAsSecureOrigin: true,
        }});
        // Qui avviene la magia: colleghiamo il nome utente al dispositivo
        OneSignal.setExternalUserId("{username}");
      }});
    </script>
    """
    # Inseriamo lo script nella pagina (altezza 0 = invisibile)
    components.html(js_code, height=0)

# --- FUNZIONE INVIO NOTIFICHE (LATO SERVER) ---
def send_notification(message, target_usernames=None, heading="Avviso Scuola"):
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
        
        # Se target_usernames è None, invia a TUTTI (Broadcast)
        if target_usernames:
            payload["include_external_user_ids"] = target_usernames
        else:
            payload["included_segments"] = ["Subscribed Users"]

        req = requests.post("https://onesignal.com/api/v1/notifications", headers=header, json=payload)
        return req.status_code == 200
    except Exception as e:
        print(f"Errore OneSignal: {e}")
        return False

# --- FUNZIONI EMAIL ---
def send_email(to_email, subject, body):
    try:
        smtp_server = st.secrets["email"]["smtp_server"]
        smtp_port = st.secrets["email"]["smtp_port"]
        sender_email = st.secrets["email"]["sender_email"]
        sender_password = st.secrets["email"]["sender_password"]

        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = sender_email
        msg['To'] = to_email

        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, to_email, msg.as_string())
        return True
    except:
        return False

# --- FUNZIONI DB ---
def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def verify_user(username, password):
    try:
        hashed = hash_password(password)
        response = supabase.table("users").select("*").eq("username", username).eq("password", hashed).execute()
        if response.data: return response.data[0]
        return None
    except: return None

def add_user(username, password, email, role):
    try:
        data = {"username": username, "password": hash_password(password), "email": email, "role": role}
        supabase.table("users").insert(data).execute()
        return True
    except: return False

def update_password(username, new_password):
    try:
        hashed = hash_password(new_password)
        supabase.table("users").update({"password": hashed}).eq("username", username).execute()
        return True
    except: return False

def get_user_email(username):
    try:
        response = supabase.table("users").select("email").eq("username", username).execute()
        if response.data: return response.data[0]['email']
        return None
    except: return None

def calculate_next_lesson_number(username):
    response = supabase.table("bookings").select("*", count="exact").eq("username", username).execute()
    return (response.count % 8) + 1

# --- LOGICA CORE ---
def add_booking(username, booking_date, slot):
    str_date = booking_date.strftime("%Y-%m-%d")
    
    check = supabase.table("bookings").select("*").eq("username", username).eq("booking_date", str_date).eq("slot", slot).execute()
    if check.data: return False, "Prenotazione già esistente."
    
    lesson_num = calculate_next_lesson_number(username)
    new_booking = {"username": username, "booking_date": str_date, "slot": slot, "lesson_number": lesson_num}
    
    try:
        supabase.table("bookings").insert(new_booking).execute()
        
        # NOTIFICA ADMIN
        admin_user = st.secrets["onesignal"]["admin_username"]
        msg_admin = f"{username} ha prenotato: {str_date} ore {slot}."
        send_notification(msg_admin, target_usernames=[admin_user], heading="Nuova Lezione 📅")
        
        # NOTIFICA 8° LEZIONE
        if lesson_num == 8:
            msg_user = "Hai raggiunto l'ottava lezione! Ricorda il rinnovo."
            send_notification(msg_user, target_usernames=[username], heading="Traguardo Raggiunto 🎉")
            
        return True, lesson_num
    except Exception as e:
        return False, str(e)

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
            
            # NOTIFICA CANCELLAZIONE STUDENTE
            msg = f"Lezione del {b_date} cancellata dalla segreteria."
            send_notification(msg, target_usernames=[student_name], heading="Cancellazione ❌")
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
    if 'reset_stage' not in st.session_state: st.session_state['reset_stage'] = 0

if not st.session_state['logged_in']:
    tab1, tab2, tab3 = st.tabs(["🔐 Accedi", "📝 Registrati", "❓ Password Persa"])

    with tab1:
        st.subheader("Accedi")
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type='password')
            if st.form_submit_button("Entra"):
                user_data = verify_user(username, password)
                if user_data:
                    st.session_state['logged_in'] = True
                    st.session_state['username'] = username
                    st.session_state['role'] = user_data['role']
                    st.rerun()
                else:
                    st.error("Dati errati.")

    with tab2:
        st.subheader("Nuovo Profilo")
        with st.form("register_form"):
            new_user = st.text_input("Username")
            new_email = st.text_input("Email")
            new_pass = st.text_input("Password", type='password')
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
                    if add_user(new_user, new_pass, new_email, role): st.success("Fatto! Accedi."); 
                    else: st.error("Username esistente.")
                    
    with tab3:
        st.subheader("Recupero Password")
        if st.session_state['reset_stage'] == 0:
            rec_user = st.text_input("Tuo Username")
            if st.button("Invia Codice"):
                email = get_user_email(rec_user)
                if email:
                    code = ''.join(random.choices(string.digits, k=4))
                    st.session_state['reset_code'] = code; st.session_state['reset_username'] = rec_user
                    if send_email(email, "Codice Recupero", f"Il tuo codice è: {code}"):
                        st.session_state['reset_stage'] = 1; st.success("Email inviata!"); st.rerun()
                else: st.error("Utente non trovato.")
        elif st.session_state['reset_stage'] == 1:
            code_in = st.text_input("Codice 4 cifre")
            new_p = st.text_input("Nuova Password", type='password')
            if st.button("Cambia"):
                if code_in == st.session_state['reset_code']:
                    update_password(st.session_state['reset_username'], new_p)
                    st.success("Password cambiata!"); st.session_state['reset_stage'] = 0
                else: st.error("Codice errato.")

else:
    # --- UTENTE LOGGATO ---
    
    # !!! QUI È IL PUNTO CRUCIALE !!!
    # Ogni volta che l'utente è loggato, eseguiamo lo script per registrarlo su OneSignal
    identify_user_onesignal(st.session_state['username'])
    
    st.sidebar.title(f"Ciao, {st.session_state['username']}")
    if st.sidebar.button("Logout"):
        st.session_state['logged_in'] = False
        st.rerun()

    # DASHBOARD ADMIN
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
        else:
            st.info("Nessuna prenotazione.")

    # DASHBOARD STUDENTE
    elif st.session_state['role'] == 'student':
        next_l = calculate_next_lesson_number(st.session_state['username'])
        st.metric("Prossima Lezione", f"N° {next_l} di 8")

        with st.expander("➕ Nuova Prenotazione", expanded=True):
            with st.form("bk_form"):
                col1, col2 = st.columns(2)
                with col1: d = st.date_input("Data", min_value=date.today())
                with col2: s = st.selectbox("Orario", ["10:00 - 13:00", "15:00 - 18:00"])
                if st.form
