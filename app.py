import streamlit as st
import pandas as pd
import hashlib
import psycopg2
from datetime import datetime, date

# --- CONFIGURAZIONE ---
ADMIN_KEY = "Francescorussoascoltaultimo"

# --- GESTIONE CONNESSIONE DATABASE (SUPABASE/POSTGRES) ---
def get_connection():
    """
    Si connette al database usando i dati salvati nei 'Secrets' di Streamlit.
    """
    # Recupera la URL dai Secrets di Streamlit
    db_url = st.secrets["postgres"]["url"]
    return psycopg2.connect(db_url)

def init_db():
    """
    Crea le tabelle se non esistono (Sintassi PostgreSQL).
    """
    conn = get_connection()
    c = conn.cursor()
    
    # Tabella Utenti
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                 username TEXT PRIMARY KEY, 
                 password TEXT, 
                 role TEXT
                 )''')
    
    # Tabella Prenotazioni (SERIAL è l'autoincrement di Postgres)
    c.execute('''CREATE TABLE IF NOT EXISTS bookings (
                 id SERIAL PRIMARY KEY, 
                 username TEXT, 
                 booking_date DATE, 
                 slot TEXT,
                 lesson_number INTEGER
                 )''')
    
    conn.commit()
    conn.close()

# Inizializziamo il DB appena parte l'app
# (In produzione si farebbe una volta sola, ma qui è per sicurezza)
try:
    init_db()
except Exception as e:
    st.error(f"Errore connessione database: {e}")

# --- FUNZIONI UTILI ---

def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def verify_user(username, password):
    conn = get_connection()
    c = conn.cursor()
    # In Postgres si usa %s come placeholder
    c.execute('SELECT role FROM users WHERE username = %s AND password = %s', 
              (username, hash_password(password)))
    data = c.fetchone()
    conn.close()
    return data

def add_user(username, password, role):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('INSERT INTO users (username, password, role) VALUES (%s, %s, %s)', 
                  (username, hash_password(password), role))
        conn.commit()
        conn.close()
        return True
    except psycopg2.IntegrityError:
        conn.close()
        return False # Utente duplicato
    except Exception as e:
        conn.close()
        st.error(e)
        return False

def calculate_next_lesson_number(username):
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM bookings WHERE username = %s', (username,))
    count = c.fetchone()[0]
    conn.close()
    return (count % 8) + 1

def add_booking(username, booking_date, slot):
    conn = get_connection()
    c = conn.cursor()
    
    # Controllo duplicati
    c.execute('SELECT * FROM bookings WHERE username=%s AND booking_date=%s AND slot=%s', 
              (username, booking_date, slot))
    if c.fetchone():
        conn.close()
        return False, "Esiste già una prenotazione per questo orario."
    
    lesson_num = calculate_next_lesson_number(username)
    
    c.execute('INSERT INTO bookings (username, booking_date, slot, lesson_number) VALUES (%s, %s, %s, %s)', 
              (username, booking_date, slot, lesson_num))
    conn.commit()
    conn.close()
    return True, lesson_num

def get_my_bookings(username):
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT id, booking_date, slot, lesson_number FROM bookings WHERE username = %s ORDER BY booking_date', (username,))
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
    c.execute('DELETE FROM bookings WHERE id = %s', (booking_id,))
    conn.commit()
    conn.close()

# --- INTERFACCIA STREAMLIT (Identica a prima) ---

st.set_page_config(page_title="Gestione Scuola", layout="centered")
st.title("📚 Portale Prenotazioni Scuola")

# Gestione Sessione
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
            submit_login = st.form_submit_button("Entra")
            
            if submit_login:
                # Blocchiamo errori se il DB non è configurato
                try:
                    result = verify_user(username, password)
                    if result:
                        st.session_state['logged_in'] = True
                        st.session_state['username'] = username
                        st.session_state['role'] = result[0]
                        st.rerun()
                    else:
                        st.error("Dati errati.")
                except Exception as e:
                    st.error(f"Errore connessione: {e}")

    with tab2:
        st.subheader("Nuovo Profilo")
        with st.form("register_form"):
            new_user = st.text_input("Username")
            new_pass = st.text_input("Password", type='password')
            st.markdown("---")
            is_admin = st.checkbox("Sono il Titolare")
            admin_code = st.text_input("Codice Segreto", type='password')
            submit_register = st.form_submit_button("Crea Account")

            if submit_register:
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
                        st.error("Username occupato.")
                elif valid:
                    st.warning("Compila tutto.")

else:
    st.sidebar.title(f"Ciao, {st.session_state['username']}")
    if st.sidebar.button("Logout"):
        st.session_state['logged_in'] = False
        st.rerun()

    if st.session_state['role'] == 'admin':
        st.subheader("👑 Registro Globale")
        data = get_all_bookings_admin()
        if data:
            df = pd.DataFrame(data, columns=['Studente', 'Data', 'Orario', 'Lezione N°'])
            st.dataframe(df.style.format({"Lezione N°": "{:.0f}"}), use_container_width=True)
        else:
            st.info("Nessuna prenotazione.")

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
                    if day_idx not in [1, 2, 3, 4, 5]:
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
        my_data = get_my_bookings(st.session_state['username'])
        if my_data:
            for item in my_data:
                bid, bdate, bslot, bnum = item
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
