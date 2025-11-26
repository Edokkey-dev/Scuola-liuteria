import streamlit as st
import pandas as pd
import hashlib
from datetime import datetime, date
from supabase import create_client, Client

# --- CONFIGURAZIONE ---
ADMIN_KEY = "Francescorussoascoltaultimo"

# --- CONNESSIONE SUPABASE (API) ---
# Questa funzione usa l'API HTTP, quindi bypassa i problemi di IPv6/Porte
@st.cache_resource
def init_connection():
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

supabase: Client = init_connection()

# --- FUNZIONI UTILI ---

def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def verify_user(username, password):
    # API: SELECT * FROM users WHERE ...
    try:
        hashed = hash_password(password)
        response = supabase.table("users").select("role").eq("username", username).eq("password", hashed).execute()
        # Se la lista dei dati non è vuota, l'utente esiste
        if response.data:
            return response.data[0] # Ritorna il dizionario {'role': ...}
        return None
    except Exception as e:
        st.error(f"Errore connessione: {e}")
        return None

def add_user(username, password, role):
    try:
        data = {
            "username": username, 
            "password": hash_password(password), 
            "role": role
        }
        supabase.table("users").insert(data).execute()
        return True
    except Exception as e:
        # Solitamente errore di chiave duplicata
        return False

def calculate_next_lesson_number(username):
    # API: Conta le righe filtrate per username
    response = supabase.table("bookings").select("*", count="exact").eq("username", username).execute()
    count = response.count
    return (count % 8) + 1

def add_booking(username, booking_date, slot):
    # 1. Controllo duplicati
    # Convertiamo la data in stringa ISO per l'API (YYYY-MM-DD)
    str_date = booking_date.strftime("%Y-%m-%d")
    
    check = supabase.table("bookings").select("*")\
            .eq("username", username)\
            .eq("booking_date", str_date)\
            .eq("slot", slot).execute()
            
    if check.data:
        return False, "Esiste già una prenotazione per questo orario."
    
    # 2. Calcolo numero lezione
    lesson_num = calculate_next_lesson_number(username)
    
    # 3. Inserimento
    new_booking = {
        "username": username,
        "booking_date": str_date,
        "slot": slot,
        "lesson_number": lesson_num
    }
    
    try:
        supabase.table("bookings").insert(new_booking).execute()
        return True, lesson_num
    except Exception as e:
        return False, str(e)

def get_my_bookings(username):
    # Ordiniamo per data
    response = supabase.table("bookings").select("*")\
               .eq("username", username)\
               .order("booking_date", desc=False).execute()
    return response.data

def get_all_bookings_admin():
    response = supabase.table("bookings").select("*")\
               .order("booking_date", desc=True).execute()
    return response.data

def delete_booking(booking_id):
    supabase.table("bookings").delete().eq("id", booking_id).execute()

# --- INTERFACCIA UTENTE (Identica a prima) ---

st.set_page_config(page_title="Gestione Scuola", layout="centered")
st.title("📚 Portale Prenotazioni Scuola")

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    st.session_state['username'] = ''
    st.session_state['role'] = ''

if not st.session_state['logged_in']:
    tab1, tab2 = st.tabs(["🔐 Accedi", "📝 Registrati"])

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
                    st.error("Dati errati o errore di connessione.")

    with tab2:
        st.subheader("Nuovo Profilo")
        with st.form("register_form"):
            new_user = st.text_input("Username")
            new_pass = st.text_input("Password", type='password')
            st.markdown("---")
            is_admin = st.checkbox("Sono il Titolare")
            admin_code = st.text_input("Codice Segreto", type='password')
            
            if st.form_submit_button("Crea Account"):
                role = "student"
                valid = True
                if is_admin:
                    if admin_code == ADMIN_KEY:
                        role = "admin"
                    else:
                        valid = False
                        st.error("Chiave errata!")
                
                if valid and new_user and new_pass:
                    if add_user(new_user, new_pass, role):
                        st.success("Creato! Vai su Accedi.")
                    else:
                        st.error("Errore: username occupato o problema server.")

else:
    st.sidebar.title(f"Ciao, {st.session_state['username']}")
    if st.sidebar.button("Logout"):
        st.session_state['logged_in'] = False
        st.rerun()

    # DASHBOARD ADMIN
    if st.session_state['role'] == 'admin':
        st.subheader("👑 Registro Globale")
        data = get_all_bookings_admin()
        if data:
            df = pd.DataFrame(data)
            # Rinominiamo le colonne per l'estetica se necessario, o lasciamo quelle del DB
            st.dataframe(df, use_container_width=True)
        else:
            st.info("Nessuna prenotazione.")

    # DASHBOARD STUDENTE
    elif st.session_state['role'] == 'student':
        next_lesson = calculate_next_lesson_number(st.session_state['username'])
        st.metric(label="Prossima Lezione", value=f"N° {next_lesson} di 8")

        with st.expander("➕ Nuova Prenotazione", expanded=True):
            with st.form("booking_form"):
                col1, col2 = st.columns(2)
                with col1:
                    d = st.date_input("Data", min_value=date.today())
                with col2:
                    slot = st.selectbox("Orario", ["10:00 - 13:00", "15:00 - 18:00"])
                
                if st.form_submit_button("Conferma"):
                    day_idx = d.weekday()
                    if day_idx not in [1, 2, 3, 4, 5]: # Mar-Sab
                        st.error("Chiuso Lunedì e Domenica.")
                    else:
                        ok, msg = add_booking(st.session_state['username'], d, slot)
                        if ok:
                            st.success(f"Fatto! Lezione {msg} il {d}")
                            import time
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.warning(msg)

        st.subheader("Le tue Lezioni")
        my_bookings = get_my_bookings(st.session_state['username'])
        if my_bookings:
            for item in my_bookings:
                # item è un dizionario ora: {'id': 1, 'booking_date': '...', ...}
                bid = item['id']
                bdate = item['booking_date']
                bslot = item['slot']
                bnum = item['lesson_number']
                
                with st.container():
                    c1, c2, c3 = st.columns([1, 3, 1])
                    c1.markdown(f"## {bnum}")
                    c2.markdown(f"**{bdate}**\n\n{bslot}")
                    if c3.button("Cancella", key=f"del_{bid}"):
                        delete_booking(bid)
                        st.rerun()
                    st.divider()
        else:
            st.info("Nessuna lezione.")
