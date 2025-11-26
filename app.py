import streamlit as st
import sqlite3
import pandas as pd
import hashlib
from datetime import datetime, date

# --- CONFIGURAZIONE ---
ADMIN_KEY = "Francescorussoascoltaultimo"
DB_FILE = "scuola.db"

# --- DATABASE ---
# Usiamo una funzione per connetterci ogni volta ed evitare errori di thread
def get_connection():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    # Tabella Utenti
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (username TEXT PRIMARY KEY, password TEXT, role TEXT)''')
    
    # Tabella Prenotazioni
    c.execute('''CREATE TABLE IF NOT EXISTS bookings
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  username TEXT, 
                  booking_date DATE, 
                  slot TEXT,
                  lesson_number INTEGER)''')
    conn.commit()
    conn.close()

# Inizializza il DB all'avvio
init_db()

# --- FUNZIONI DI UTILITÀ ---
def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def verify_user(username, password):
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT role FROM users WHERE username = ? AND password = ?', 
              (username, hash_password(password)))
    data = c.fetchone()
    conn.close()
    return data

def add_user(username, password, role):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)', 
                  (username, hash_password(password), role))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False

def calculate_next_lesson_number(username):
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM bookings WHERE username = ?', (username,))
    count = c.fetchone()[0]
    conn.close()
    # Ciclo 1-8
    return (count % 8) + 1

def add_booking(username, booking_date, slot):
    conn = get_connection()
    c = conn.cursor()
    # Controllo duplicati
    c.execute('SELECT * FROM bookings WHERE username=? AND booking_date=? AND slot=?', (username, booking_date, slot))
    if c.fetchone():
        conn.close()
        return False, "Esiste già una prenotazione per questo orario."
    
    lesson_num = calculate_next_lesson_number(username)
    
    c.execute('INSERT INTO bookings (username, booking_date, slot, lesson_number) VALUES (?, ?, ?, ?)', 
              (username, booking_date, slot, lesson_num))
    conn.commit()
    conn.close()
    return True, lesson_num

def get_my_bookings(username):
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT id, booking_date, slot, lesson_number FROM bookings WHERE username = ? ORDER BY booking_date', (username,))
    data = c.fetchall()
    conn.close()
    return data

def get_all_bookings_admin():
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT username, booking_date, slot, lesson_number FROM bookings ORDER BY booking_date DESC')
    data = c.fetchall()
    conn.close()
    return data

def delete_booking(booking_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute('DELETE FROM bookings WHERE id = ?', (booking_id,))
    conn.commit()
    conn.close()

# --- INTERFACCIA UTENTE ---
st.set_page_config(page_title="Gestione Scuola", layout="centered")

# Titolo principale
st.title("📚 Portale Prenotazioni Scuola")

# Gestione Sessione
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    st.session_state['username'] = ''
    st.session_state['role'] = ''

# --- LOGICA DI NAVIGAZIONE ---

if not st.session_state['logged_in']:
    # Menu a schede per Login/Registrazione (più pulito)
    tab1, tab2 = st.tabs(["🔐 Accedi", "📝 Registrati"])

    with tab1:
        st.subheader("Accedi al tuo account")
        # Usiamo st.form per abilitare il salvataggio password del browser
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type='password')
            submit_login = st.form_submit_button("Entra")
            
            if submit_login:
                result = verify_user(username, password)
                if result:
                    st.session_state['logged_in'] = True
                    st.session_state['username'] = username
                    st.session_state['role'] = result[0]
                    st.rerun()
                else:
                    st.error("Username o Password errati.")

    with tab2:
        st.subheader("Crea un nuovo profilo")
        with st.form("register_form"):
            new_user = st.text_input("Scegli un Username")
            new_pass = st.text_input("Scegli una Password", type='password')
            
            # Sezione Admin
            st.markdown("---")
            is_admin = st.checkbox("Sono il Titolare")
            admin_code = st.text_input("Codice Segreto (solo per Titolare)", type='password')
            
            submit_register = st.form_submit_button("Crea Account")

            if submit_register:
                role = "student"
                valid = True
                
                if is_admin:
                    if admin_code == ADMIN_KEY:
                        role = "admin"
                    else:
                        valid = False
                        st.error("Chiave segreta errata!")
                
                if valid and new_user and new_pass:
                    if add_user(new_user, new_pass, role):
                        st.success("Account creato! Ora vai su 'Accedi' per entrare.")
                    else:
                        st.error("Questo Username è già utilizzato.")
                elif valid:
                    st.warning("Compila tutti i campi.")

else:
    # --- UTENTE LOGGATO ---
    
    # Barra laterale con info utente
    st.sidebar.title(f"Ciao, {st.session_state['username']}")
    st.sidebar.info(f"Ruolo: {st.session_state['role'].upper()}")
    
    if st.sidebar.button("Esci (Logout)"):
        st.session_state['logged_in'] = False
        st.rerun()

    # --- PANNELLO ADMIN ---
    if st.session_state['role'] == 'admin':
        st.subheader("👑 Registro Prenotazioni")
        
        data = get_all_bookings_admin()
        if data:
            df = pd.DataFrame(data, columns=['Studente', 'Data', 'Orario', 'Lezione N°'])
            # Convertiamo la data in formato leggibile se necessario
            st.dataframe(
                df.style.format({"Lezione N°": "{:.0f}"}), 
                use_container_width=True,
                height=400
            )
        else:
            st.info("Nessuna prenotazione presente nel sistema.")

    # --- PANNELLO STUDENTE ---
    elif st.session_state['role'] == 'student':
        # Calcolo prossima lezione
        next_lesson = calculate_next_lesson_number(st.session_state['username'])
        st.metric(label="Prossima Lezione", value=f"N° {next_lesson} di 8")

        # Form Prenotazione
        with st.expander("➕ Nuova Prenotazione", expanded=True):
            with st.form("booking_form"):
                col1, col2 = st.columns(2)
                with col1:
                    d = st.date_input("Data Lezione", min_value=date.today())
                with col2:
                    slot = st.selectbox("Fascia Oraria", ["10:00 - 13:00", "15:00 - 18:00"])
                
                confirm_btn = st.form_submit_button("Conferma Prenotazione")

                if confirm_btn:
                    day_idx = d.weekday()
                    valid_days = [1, 2, 3, 4, 5] # Mar-Sab
                    
                    if day_idx not in valid_days:
                        st.error("❌ La scuola è chiusa Lunedì e Domenica.")
                    else:
                        ok, msg_or_num = add_booking(st.session_state['username'], d, slot)
                        if ok:
                            st.success(f"✅ Prenotata lezione {msg_or_num} per il {d}!")
                            # Ritardo il rerun per far leggere il messaggio
                            import time
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.warning(f"⚠️ {msg_or_num}")

        st.markdown("---")
        st.subheader("Le tue Lezioni")
        
        my_data = get_my_bookings(st.session_state['username'])
        if my_data:
            for item in my_data:
                bid, bdate, bslot, bnum = item
                
                # Layout card per ogni lezione
                with st.container():
                    c1, c2, c3 = st.columns([1, 3, 1])
                    c1.markdown(f"## {bnum}")
                    c2.markdown(f"**{bdate}**\n\n{bslot}")
                    if c3.button("Cancella", key=f"del_{bid}"):
                        delete_booking(bid)
                        st.rerun()
                    st.divider()
        else:
            st.info("Non hai ancora prenotato lezioni.")
