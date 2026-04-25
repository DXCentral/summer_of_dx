import streamlit as st
import pandas as pd
import datetime
import math
import gspread
from google.oauth2.service_account import Credentials

# --- 1. CORE CONFIGURATION ---
st.set_page_config(page_title="SUMMER OF DX: DEFCON 6", layout="centered", initial_sidebar_state="collapsed")

# --- 2. WARGAMES CRT CSS ---
crt_css = """
<style>
@import url('https://fonts.googleapis.com/css2?family=VT323&display=swap');

html, body, [class*="st-"] {
    background-color: #050505 !important;
    font-family: 'VT323', monospace !important;
    color: #39ff14 !important;
    text-shadow: 0px 0px 4px rgba(57, 255, 20, 0.7);
    letter-spacing: 2px;
}

/* Hide standard Streamlit header/footer for full immersion */
header {visibility: hidden;}
footer {visibility: hidden;}

/* Stylize Streamlit Buttons as Terminal Prompts */
div.stButton > button {
    background-color: transparent !important;
    border: 1px solid #39ff14 !important;
    color: #39ff14 !important;
    font-size: 1.5rem !important;
    font-family: 'VT323', monospace !important;
    justify-content: flex-start !important;
    padding-left: 20px !important;
    box-shadow: inset 0px 0px 10px rgba(57, 255, 20, 0.1);
    width: 100%;
    transition: all 0.2s ease-in-out;
}
div.stButton > button:hover {
    background-color: #39ff14 !important;
    color: #050505 !important;
    text-shadow: none !important;
    box-shadow: 0px 0px 15px #39ff14;
}

/* Stylize Inputs */
input, textarea, div[data-baseweb="select"] > div {
    background-color: #0a0a0a !important;
    border: 1px solid #39ff14 !important;
    color: #39ff14 !important;
    font-family: 'VT323', monospace !important;
    font-size: 1.2rem !important;
}

.typewriter {
    font-size: 2.2rem;
    text-align: center;
    margin-bottom: 40px;
    line-height: 1.2;
}
.blink {
    animation: blinker 1s linear infinite;
}
@keyframes blinker {
    50% { opacity: 0; }
}
.classified-box {
    border: 2px dashed #39ff14;
    padding: 20px;
    margin-top: 20px;
    background-color: rgba(57, 255, 20, 0.05);
}
hr {
    border-color: #39ff14 !important;
    opacity: 0.3;
}
</style>
"""
st.markdown(crt_css, unsafe_allow_html=True)

# --- 3. DATABANK CONNECTIONS & HELPERS ---
@st.cache_data
def load_mw_intel():
    try:
        df = pd.read_csv("Mesa Mike Enriched.csv", dtype=str)
        df['Frequency'] = pd.to_numeric(df['FREQ'], errors='coerce')
        df['Callsign'] = df['CALL'].fillna("Unknown")
        df['State'] = df['STATE'].fillna("XX")
        df['City'] = df['CITY'].fillna("Unknown")
        df['County'] = df['County'].fillna("Unknown")
        return df
    except:
        return pd.DataFrame()

@st.cache_data
def load_fm_intel():
    try:
        df = pd.read_csv("WTFDA Enriched.csv", dtype=str)
        df['Frequency'] = pd.to_numeric(df['Frequency'], errors='coerce')
        df['State'] = df['S/P'].fillna("XX")
        df['County'] = df['County'].fillna("Unknown")
        return df
    except:
        return pd.DataFrame()

@st.cache_data
def load_countries():
    try:
        df = pd.read_csv("DX Central _ MW Frequency Challenge -All Seasons Master Logbook - Sheet64.csv")
        return df['Country Name'].dropna().sort_values().tolist() + ["Other"]
    except:
        return ["United States", "Canada", "Mexico", "Other"]

def get_gsheet():
    scope = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    # Uses the specific Document ID provided for the Summer of DX outputs
    return client.open_by_key("11_4lKQRCrV2Q0YZM1syECgoSINmnGIG3k6UJH0m_u3Y").worksheet("Form Entries")

mw_db = load_mw_intel()
fm_db = load_fm_intel()
country_list = load_countries()

# --- 4. SESSION STATE ROUTING & PROFILE ---
if 'sys_state' not in st.session_state:
    st.session_state.sys_state = "OPERATOR_LOGIN"
if 'matrix_unlocked' not in st.session_state:
    st.session_state.matrix_unlocked = False
if 'operator_profile' not in st.session_state:
    st.session_state.operator_profile = {"name": "", "city": "", "state": "", "country": "United States"}

def nav_to(page):
    st.session_state.sys_state = page

# Persistent Header for Operator Status
if st.session_state.sys_state != "OPERATOR_LOGIN":
    st.markdown(f"<div style='text-align: right; font-size: 1rem;'>OPERATOR: {st.session_state.operator_profile['name'].upper()} | STATUS: SECURE</div>", unsafe_allow_html=True)
    st.markdown("<hr style='margin-top: 5px; margin-bottom: 20px;'>", unsafe_allow_html=True)

# --- 5. OPERATOR LOGIN SCREEN ---
if st.session_state.sys_state == "OPERATOR_LOGIN":
    st.markdown('<div class="typewriter">DX CENTRAL MAINFRAME<br>AUTHENTICATION REQUIRED<span class="blink">_</span></div>', unsafe_allow_html=True)
    
    with st.form("login_form"):
        st.write("ENTER OPERATOR DESIGNATION:")
        op_name = st.text_input("CALLSIGN / HANDLE")
        c1, c2 = st.columns(2)
        op_city = c1.text_input("HOME QTH: CITY")
        op_state = c2.text_input("HOME QTH: STATE/PROV")
        
        if st.form_submit_button("> AUTHENTICATE"):
            if op_name:
                st.session_state.operator_profile = {"name": op_name, "city": op_city, "state": op_state, "country": "United States"}
                nav_to("TERMINAL_HOME")
                st.rerun()
            else:
                st.error("ACCESS DENIED. OPERATOR DESIGNATION REQUIRED.")

# --- 6. THE HOME TERMINAL ---
elif st.session_state.sys_state == "TERMINAL_HOME":
    st.markdown('<div class="typewriter">GREETINGS, FELLOW SIGNAL TRAVELER.<br>WOULD YOU LIKE TO PLAY A GAME?<span class="blink">_</span></div>', unsafe_allow_html=True)
    
    if st.button("> INITIATE MW INTERCEPT REPORT"):
        nav_to("MW_LOG")
        st.rerun()
        
    if st.button("> INITIATE FM INTERCEPT REPORT"):
        nav_to("FM_LOG")
        st.rerun()
        
    if st.button("> INITIATE ENCRYPTION PROTOCOL"):
        nav_to("BOUNTY_HUNT")
        st.rerun()
        
    if st.button("> ACCESS GLOBAL INTELLIGENCE DASHBOARD"):
        nav_to("DASHBOARD")
        st.rerun()

# --- 7. MW INTERCEPT ROOM ---
elif st.session_state.sys_state == "MW_LOG":
    st.markdown("### [ MW INTERCEPT CONSOLE ACTIVE ]")
    
    st.markdown("#### 1. OPERATING PARAMETERS")
    r_cat = st.radio("CATEGORY", ["HOME QTH", "ROVER"], horizontal=True, label_visibility="collapsed")
    rover_grid = ""
    if r_cat == "ROVER":
        st.warning("ROVER MODE: ENTER CURRENT MAIDENHEAD GRID TO CALIBRATE DISTANCE.")
        rover_grid = st.text_input("ROVER GRID (e.g., EM40)")
    
    st.markdown("#### 2. TARGET ACQUISITION")
    tab_search, tab_manual = st.tabs(["[ DATABASE SEARCH ]", "[ MANUAL ENTRY ]"])
    
    target_data = {}
    
    with tab_search:
        st.write("ACCESSING DOMESTIC AM DATABANKS...")
        c1, c2 = st.columns([1, 2])
        search_freq = c1.number_input("FREQ (kHz)", min_value=530, max_value=1710, value=540, step=10)
        search_call = c2.text_input("CALLSIGN (OPTIONAL)")
        
        if not mw_db.empty:
            results = mw_db[mw_db['Frequency'] == search_freq]
            if search_call:
                results = results[results['Callsign'].str.contains(search_call.upper(), na=False)]
                
            st.write(f"> {len(results)} TARGETS FOUND:")
            
            if not results.empty:
                results.insert(0, 'Select', False)
                view_df = results[['Select', 'Callsign', 'City', 'State', 'County', 'Frequency']]
                edited_df = st.data_editor(view_df, hide_index=True, use_container_width=True, disabled=['Callsign', 'City', 'State', 'County', 'Frequency'])
                
                selected_rows = edited_df[edited_df['Select'] == True]
                if not selected_rows.empty:
                    target = selected_rows.iloc[0]
                    st.success(f"TARGET LOCKED: {target['Callsign']} ({target['City']}, {target['State']} - {target['County']} County)")
                    target_data = {"freq": target['Frequency'], "call": target['Callsign'], "city": target['City'], "state": target['State'], "county": target['County'], "country": "USA"}

    with tab_manual:
        st.write("INITIATE UNLISTED / INTERNATIONAL PROTOCOL...")
        c_m1, c_m2, c_m3 = st.columns(3)
        man_freq = c_m1.number_input("MANUAL FREQ (kHz)", min_value=531, max_value=1710, value=540, step=9, key="man_mw")
        man_call = c_m2.text_input("STATION ID")
        def_idx = country_list.index("United States") if "United States" in country_list else 0
        man_ctry = c_m3.selectbox("COUNTRY", country_list, index=def_idx)
        man_other = st.text_input("SPECIFY COUNTRY:") if man_ctry == "Other" else ""
        man_city = st.text_input("STATION CITY")
        man_sp = st.text_input("STATION STATE/PROV")
        
        if man_call:
            target_data = {"freq": man_freq, "call": man_call, "city": man_city, "state": man_sp, "county": "Unknown", "country": man_ctry}

    st.markdown("#### 3. SUBMIT INTERCEPT")
    with st.form("mw_submit_form", clear_on_submit=True):
        col_s1, col_s2, col_s3 = st.columns(3)
        now = datetime.datetime.now(datetime.timezone.utc)
        log_date = col_s1.date_input("DATE (UTC)", value=now.date())
        log_time = col_s2.text_input("TIME (UTC)", value=now.strftime("%H%M"))
        log_dist = col_s3.number_input("DISTANCE (MILES)", min_value=0.0, step=1.0)
        
        log_notes = st.text_area("PROGRAMMING / INTERCEPT NOTES")
        log_prop = st.selectbox("PROPAGATION MODE", ["Groundwave", "Skywave", "Other"])
        
        submit_log = st.form_submit_button("> TRANSMIT REPORT TO SERVER")
        if submit_log:
            try:
                op = st.session_state.operator_profile
                # Maps to your 25-column format:
                # Name, City, State, DXer Country, AM/FM, AM Freq, FM Freq, Call, Slogan, St City, St State, St Country, Other Ctry, Grid, Date, Time, Dist, Notes, RDS, PI, Prop, County, Entry Cat, Points, Total
                row_data = [
                    op['name'], op['city'], op['state'], op['country'], 
                    "AM", target_data.get("freq", ""), "", 
                    target_data.get("call", ""), "", target_data.get("city", ""), 
                    target_data.get("state", ""), target_data.get("country", ""), 
                    man_other if target_data.get("country") == "Other" else "", 
                    rover_grid, log_date.strftime("%m/%d/%Y"), log_time, 
                    log_dist, log_notes, "", "", log_prop, target_data.get("county", ""), 
                    r_cat, "", ""
                ]
                get_gsheet().append_row(row_data)
                st.markdown("### [ TRANSMISSION SUCCESSFUL ]")
            except Exception as e:
                st.error(f"TRANSMISSION FAILED: {e}")
            
    st.write("---")
    if st.button("< RETURN TO MAIN TERMINAL"):
        nav_to("TERMINAL_HOME")
        st.rerun()

# --- 8. FM INTERCEPT ROOM ---
elif st.session_state.sys_state == "FM_LOG":
    st.markdown("### [ FM INTERCEPT CONSOLE ACTIVE ]")
    
    st.markdown("#### 1. OPERATING PARAMETERS")
    r_cat = st.radio("CATEGORY", ["HOME QTH", "ROVER"], horizontal=True, label_visibility="collapsed", key="fm_cat")
    rover_grid = ""
    if r_cat == "ROVER":
        st.warning("ROVER MODE: ENTER CURRENT MAIDENHEAD GRID TO CALIBRATE DISTANCE.")
        rover_grid = st.text_input("ROVER GRID (e.g., EM40)", key="fm_rov")
        
    st.markdown("#### 2. TARGET ACQUISITION")
    tab_search, tab_manual = st.tabs(["[ DATABASE SEARCH ]", "[ MANUAL ENTRY ]"])
    target_data = {}
    
    with tab_search:
        st.write("ACCESSING WTFDA DATABANKS...")
        c1, c2 = st.columns([1, 2])
        search_freq = c1.number_input("FREQ (MHz)", min_value=87.7, max_value=107.9, value=88.1, step=0.2, format="%.1f")
        search_call = c2.text_input("CALLSIGN (OPTIONAL)", key="fm_call_srch")
        
        if not fm_db.empty:
            results = fm_db[fm_db['Frequency'] == search_freq]
            if search_call:
                results = results[results['Callsign'].str.contains(search_call.upper(), na=False)]
                
            st.write(f"> {len(results)} TARGETS FOUND:")
            
            if not results.empty:
                results.insert(0, 'Select', False)
                view_df = results[['Select', 'Callsign', 'City', 'State', 'County', 'Frequency', 'PI Code']]
                edited_df = st.data_editor(view_df, hide_index=True, use_container_width=True, disabled=['Callsign', 'City', 'State', 'County', 'Frequency', 'PI Code'])
                
                selected_rows = edited_df[edited_df['Select'] == True]
                if not selected_rows.empty:
                    target = selected_rows.iloc[0]
                    st.success(f"TARGET LOCKED: {target['Callsign']} ({target['City']}, {target['State']} - {target['County']} County)")
                    target_data = {"freq": target['Frequency'], "call": target['Callsign'], "city": target['City'], "state": target['State'], "county": target['County'], "country": "USA", "pi": target['PI Code']}

    with tab_manual:
        st.write("INITIATE UNLISTED PROTOCOL...")
        c_m1, c_m2 = st.columns(2)
        man_freq = c_m1.number_input("MANUAL FREQ (MHz)", min_value=87.7, max_value=107.9, value=88.1, step=0.1, key="man_fm")
        man_call = c_m2.text_input("STATION ID", key="man_fm_call")
        if man_call:
            target_data = {"freq": man_freq, "call": man_call, "city": "Unknown", "state": "XX", "county": "Unknown", "country": "Unknown", "pi": ""}

    st.markdown("#### 3. SUBMIT INTERCEPT")
    with st.form("fm_submit_form", clear_on_submit=True):
        col_s1, col_s2, col_s3 = st.columns(3)
        now = datetime.datetime.now(datetime.timezone.utc)
        log_date = col_s1.date_input("DATE (UTC)", value=now.date(), key="fm_dt")
        log_time = col_s2.text_input("TIME (UTC)", value=now.strftime("%H%M"), key="fm_tm")
        log_dist = col_s3.number_input("DISTANCE (MILES)", min_value=0.0, step=1.0, key="fm_dst")
        
        c_p1, c_p2, c_p3 = st.columns(3)
        log_prop = c_p1.selectbox("PROPAGATION MODE", ["Tropo", "Sporadic E", "Meteor Scatter", "Aurora", "Local"])
        log_rds = c_p2.selectbox("RDS DECODE?", ["No", "Yes"])
        log_pi = c_p3.text_input("PI CODE", value=target_data.get("pi", ""))
        
        log_notes = st.text_area("PROGRAMMING / INTERCEPT NOTES", key="fm_nts")
        
        submit_log = st.form_submit_button("> TRANSMIT REPORT TO SERVER")
        if submit_log:
            try:
                op = st.session_state.operator_profile
                row_data = [
                    op['name'], op['city'], op['state'], op['country'], 
                    "FM", "", target_data.get("freq", ""), 
                    target_data.get("call", ""), "", target_data.get("city", ""), 
                    target_data.get("state", ""), target_data.get("country", ""), 
                    "", rover_grid, log_date.strftime("%m/%d/%Y"), log_time, 
                    log_dist, log_notes, log_rds, log_pi, log_prop, target_data.get("county", ""), 
                    r_cat, "", ""
                ]
                get_gsheet().append_row(row_data)
                st.markdown("### [ TRANSMISSION SUCCESSFUL ]")
            except Exception as e:
                st.error(f"TRANSMISSION FAILED: {e}")

    st.write("---")
    if st.button("< RETURN TO MAIN TERMINAL"):
        nav_to("TERMINAL_HOME")
        st.rerun()

# --- 9. THE CLANDESTINE MATRIX (BOUNTY ROOM) ---
elif st.session_state.sys_state == "BOUNTY_HUNT":
    st.markdown("### --- SECURE UPLINK ESTABLISHED ---")
    st.markdown("AWAITING MATRIX ALIGNMENT PARAMETERS<span class='blink'>_</span>", unsafe_allow_html=True)
    
    # Active Bounty Configuration (Update these variables bi-weekly)
    ACTIVE_ALPHA = "D"
    ACTIVE_NUMERIC = "4"
    SECRET_PAYLOAD = "SPORADIC"
    
    col1, col2 = st.columns(2)
    alpha_key = col1.selectbox("ALPHA KEY", ["A", "B", "C", "D", "E"])
    numeric_key = col2.selectbox("NUMERIC KEY", ["1", "2", "3", "4", "5"])
    
    if alpha_key == ACTIVE_ALPHA and numeric_key == ACTIVE_NUMERIC:
        st.success("MATRIX ALIGNMENT LOCKED.")
        st.session_state.matrix_unlocked = True
    else:
        st.warning("MATRIX MISALIGNED. DECRYPTION UNAVAILABLE.")
        st.session_state.matrix_unlocked = False

    if st.session_state.matrix_unlocked:
        st.markdown("""
        <div class="classified-box">
        <strong>DECRYPTION CIPHER ACTIVE:</strong><br>
        19 = S | 16 = P | 15 = O | 18 = R | 01 = A | 04 = D | 09 = I | 03 = C
        </div>
        """, unsafe_allow_html=True)
        
        st.write("ENTER DECRYPTED PAYLOAD TO ACCESS DOSSIER:")
        payload = st.text_input(">", key="payload_input")
        
        if payload.upper() == SECRET_PAYLOAD:
            st.markdown("### [ ACCESS GRANTED ]")
            st.error("### TOP SECRET DOSSIER: ACTIVE")
            st.markdown("""
            **TARGET SPECIFICATIONS:**
            * Log any Class C AM Graveyard station.
            * Distance must exceed 400 miles.
            * Acquisition window closes in 14 days.
            """)
            # Future integration: Route them to a specialized Bounty form
            st.button("> ACKNOWLEDGE & ACCEPT MISSION")

    st.write("---")
    if st.button("< ABORT PROTOCOL / RETURN"):
        st.session_state.matrix_unlocked = False
        nav_to("TERMINAL_HOME")
        st.rerun()

# --- 10. GLOBAL INTELLIGENCE (DASHBOARD STUB) ---
elif st.session_state.sys_state == "DASHBOARD":
    st.markdown("### [ GLOBAL INTELLIGENCE DATABANKS ]")
    st.write("ESTABLISHING CONNECTION TO PLOTLY SERVERS...")
    st.markdown("""
    <div class="classified-box">
    <strong>SYSTEM STATUS:</strong> DATA VISUALIZATION MODULES COMPILING.<br>
    STANDBY FOR CHOROPLETH MAPS, VOLUME TIMELINES, AND OPERATOR LEADERBOARDS.
    </div>
    """, unsafe_allow_html=True)
    
    st.write("---")
    if st.button("< RETURN TO MAIN TERMINAL"):
        nav_to("TERMINAL_HOME")
        st.rerun()
