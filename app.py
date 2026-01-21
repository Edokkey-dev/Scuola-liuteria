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
    .rank-bronze { border-
