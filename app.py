import streamlit as st
import pandas as pd
import datetime
import math
import json
import re
import maidenhead as mh
from geopy.geocoders import Nominatim
import streamlit.components.v1 as components
from streamlit_javascript import st_javascript
import pydeck as pdk  # INJECTED FOR TACTICAL RADAR

# Corrected modular imports
from modules.importers import (
    get_idx, find_col, handle_mw_file_upload, handle_fm_file_upload,
    clean_callsign, simplify_string, super_clean, standardize_cuban_station,
    format_date_import, format_time_import, map_mw_prop, map_fm_prop, calculate_distance
)
from modules.data_forge import (
    mw_db, fm_db, nwr_db, country_list, get_state_list, get_logged_dict, 
    check_is_logged_mw, check_is_logged_fm, get_lat_lon_from_city, 
    get_gsheet, get_full_logs_df, itu_map, load_mw_intel, load_fm_intel, load_nwr_intel
)
from modules.dashboard import render_dashboard
from challenge_rules import is_terminal_open, is_reception_valid, filter_bulk_dataframe

# --- BULLETPROOF IMPORT FAILSAFES ---
try:
    from modules.awards import manual_award_claim_popup
    AWARDS_ACTIVE = True
except ImportError:
    AWARDS_ACTIVE = False
    def manual_award_claim_popup(*args, **kwargs): pass

try:
    from modules.bounty import render_bounty_module
    BOUNTY_ACTIVE = True
except ImportError:
    BOUNTY_ACTIVE = False
    def render_bounty_module():
        st.warning("🚨 ENCRYPTED INTERCEPT MODULE OFFLINE. (Ensure modules/bounty.py is deployed).")


# --- 1. CORE CONFIGURATION ---
st.set_page_config(
    page_title="SUMMER OF DX: DEFCON 6", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# --- 2. WARGAMES CRT CSS (CYAN ESPIONAGE EDITION) ---
crt_css = """
<style>
@import url('https://fonts.googleapis.com/css2?family=VT323&display=swap');

html, body, [class*="st-"] {
    background-color: #050505 !important;
    font-family: 'VT323', monospace !important;
    color: #1bd2d4 !important; 
    text-shadow: 0px 0px 5px rgba(19, 154, 155, 0.8); 
    letter-spacing: 2px;
}

header {
    visibility: hidden;
}
footer {
    visibility: hidden;
}

[data-testid="stSidebar"] {
    background-color: #0a0a0a !important;
    border-right: 1px dashed #139a9b;
}

div.stButton > button {
    background-color: transparent !important;
    border: 1px solid #139a9b !important;
    color: #1bd2d4 !important;
    font-size: 1.5rem !important;
    font-family: 'VT323', monospace !important;
    justify-content: flex-start !important;
    padding-left: 20px !important;
    box-shadow: inset 0px 0px 10px rgba(19, 154, 155, 0.1);
    width: 100%;
    transition: all 0.2s ease-in-out;
}

div.stButton > button:hover {
    background-color: #139a9b !important;
    color: #050505 !important;
    text-shadow: none !important;
    box-shadow: 0px 0px 15px #1bd2d4;
}

input, textarea, div[data-baseweb="select"] > div {
    background-color: #0a0a0a !important;
    border: 1px solid #139a9b !important;
    color: #1bd2d4 !important;
    font-family: 'VT323', monospace !important;
    font-size: 1.2rem !important;
}

.stDataFrame {
    font-family: 'VT323', monospace !important;
}

/* Aggressive overrides for centering Dataframes */
[data-testid="stDataFrame"] th, 
[data-testid="stDataFrame"] td,
.stDataFrame div[role="gridcell"],
.stDataFrame div[data-testid="stTable"] {
    text-align: center !important;
    justify-content: center !important;
}

/* Eradicate Streamlit Dataframe Toolbars to prevent unauthorized downloads */
[data-testid="stElementToolbar"], 
[data-testid="stDataFrame"] [data-testid="stElementToolbar"] {
    display: none !important;
    visibility: hidden !important;
    opacity: 0 !important;
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
    border: 2px dashed #139a9b;
    padding: 20px;
    margin-top: 20px;
    background-color: rgba(19, 154, 155, 0.05);
}

hr {
    border-color: #139a9b !important;
    opacity: 0.3;
}

/* Sidebar Subheaders */
.sidebar-header {
    color: #ffffff;
    font-size: 1.4rem;
    text-transform: uppercase;
    letter-spacing: 2px;
    border-bottom: 1px dashed #139a9b;
    padding-bottom: 5px;
    margin-top: 20px;
    margin-bottom: 10px;
}
</style>
"""
st.markdown(crt_css, unsafe_allow_html=True)

# --- 3. BACKGROUND TASKS (LOCAL STORAGE INJECTION) ---
if "profile_to_save" in st.session_state:
    js_string = json.dumps(st.session_state.profile_to_save)
    components.html(
        f"<script>window.parent.localStorage.setItem('dx_central_operator', JSON.stringify({js_string}));</script>",
        height=0, 
        width=0
    )
    del st.session_state.profile_to_save

# --- 4. SESSION ROUTING & GEOLOCATION HELPERS ---
if 'sys_state' not in st.session_state: 
    st.session_state.sys_state = "OPERATOR_LOGIN"
if 'operator_profile' not in st.session_state:
    st.session_state.operator_profile = { "name": "", "city": "", "state": "", "country": "United States", "lat": 0.0, "lon": 0.0 }
if 'dash_nav' not in st.session_state: 
    st.session_state.dash_nav = "OVERVIEW"

# Sticky Memory Initialization for IQ Recordings
if 'iq_date' not in st.session_state: 
    st.session_state.iq_date = datetime.datetime.now(datetime.timezone.utc).date()
if 'iq_time' not in st.session_state: 
    st.session_state.iq_time = datetime.datetime.now(datetime.timezone.utc).strftime("%H%M")

def nav_to(page): 
    st.session_state.sys_state = page

def reverse_geocode(lat, lon):
    try:
        geolocator = Nominatim(user_agent="dx_central_logger_v6")
        location = geolocator.reverse(f"{lat}, {lon}", language='en')
        if location:
            addr = location.raw.get('address', {})
            found_city = ""
            for tag in ['city', 'town', 'village', 'hamlet']:
                if tag in addr: 
                    found_city = addr[tag]
                    break
            st.session_state.op_city_val = found_city
            st.session_state.op_state_val = addr.get('state', addr.get('province', ''))
            st.session_state.op_country_val = addr.get('country', 'United States')
    except Exception: 
        pass

def update_from_grid():
    grid = st.session_state.grid_input.strip()
    if len(grid) >= 4:
        try:
            lat, lon = mh.to_location(grid)
            st.session_state.op_lat_val = float(lat)
            st.session_state.op_lon_val = float(lon)
            reverse_geocode(lat, lon)
        except Exception: 
            pass

def update_from_search():
    query = st.session_state.search_query.strip()
    if query:
        try:
            geolocator = Nominatim(user_agent="dx_central_logger_v6")
            loc = geolocator.geocode(query)
            if loc:
                st.session_state.op_lat_val = float(loc.latitude)
                st.session_state.op_lon_val = float(loc.longitude)
                reverse_geocode(loc.latitude, loc.longitude)
        except Exception: 
            pass

if st.session_state.sys_state != "OPERATOR_LOGIN":
    prof = st.session_state.operator_profile
    if not prof.get('name') or float(prof.get('lat', 0.0)) == 0.0 or float(prof.get('lon', 0.0)) == 0.0:
        st.session_state.sys_state = "OPERATOR_LOGIN"
        st.rerun()

# --- 5. SIDEBAR NAVIGATION ---
with st.sidebar:
    try:
        st.image("Summer of DX Banner.png", use_container_width=True)
        st.markdown("<br>", unsafe_allow_html=True)
    except Exception: 
        pass
        
    if st.session_state.sys_state != "OPERATOR_LOGIN":
        op_name_display = st.session_state.operator_profile.get('name', 'UNKNOWN').upper()
        st.markdown(f"<div style='text-align: center; font-size: 1.3rem; color: #1bd2d4;'>AGENT: {op_name_display}<br>STATUS: SECURE</div>", unsafe_allow_html=True)
        st.markdown("<hr>", unsafe_allow_html=True)
        
        st.markdown("<div class='sidebar-header'>🗄️ INTELLIGENCE GATHERING</div>", unsafe_allow_html=True)
        if st.button("TERMINAL HOME", key="nav_home"): nav_to("TERMINAL_HOME"); st.rerun()
        if st.button("MW INTERCEPT REPORT", key="nav_mw"): nav_to("MW_LOG"); st.rerun()
        if st.button("FM INTERCEPT REPORT", key="nav_fm"): nav_to("FM_LOG"); st.rerun()
        if st.button("NWR INTERCEPT REPORT", key="nav_nwr"): nav_to("NWR_LOG"); st.rerun()
        if st.button("ENCRYPTED INTERCEPT REPORT", key="nav_bounty"): nav_to("BOUNTY_HUNT"); st.rerun()
                
        st.markdown("<div class='sidebar-header'>📡 INTERCEPT DEBRIEFING</div>", unsafe_allow_html=True)
        if st.button("MISSION OVERVIEW", key="nav_dash_over"): 
            nav_to("DASHBOARD"); st.session_state.dash_nav = "OVERVIEW"; st.rerun()
        if st.button("CLASSIFICATION MATRIX", key="nav_dash_mat"): 
            nav_to("DASHBOARD"); st.session_state.dash_nav = "MATRIX"; st.rerun()
        if st.button("GEOGRAPHIC INTEL", key="nav_dash_geo"): 
            nav_to("DASHBOARD"); st.session_state.dash_nav = "GEOGRAPHY"; st.rerun()
        if st.button("RADAR & TELEMETRY", key="nav_dash_rad"): 
            nav_to("DASHBOARD"); st.session_state.dash_nav = "RADAR"; st.rerun()
        if st.button("FREQUENCY TUNER", key="nav_dash_tun"): 
            nav_to("DASHBOARD"); st.session_state.dash_nav = "TUNER"; st.rerun()

        st.markdown("<div class='sidebar-header'>🔐 PROTOCOLS</div>", unsafe_allow_html=True)
        if st.button("DIRECTIVES (RULES)", key="nav_rules"): nav_to("RULES"); st.rerun()
        if st.button("DATA SECURITY", key="nav_privacy"): nav_to("PRIVACY"); st.rerun()

        st.write("---")
        if st.button("LOGOUT / PURGE CACHE", key="nav_logout"):
            components.html("<script>window.parent.localStorage.removeItem('dx_central_operator');</script>", height=0, width=0)
            st.cache_data.clear()
            st.session_state.clear()
            st.rerun()

# --- 8. CENTRAL COLUMN CONSTRAINT ---
spacer_left, main_content, spacer_right = st.columns([1, 8, 1])

with main_content:
    
    # --- 8A. OPERATOR LOGIN SCREEN ---
    if st.session_state.sys_state == "OPERATOR_LOGIN":
        try: 
            st.image("Summer of DX Banner.png", use_container_width=True)
        except Exception: 
            pass

        st.markdown('<div class="typewriter">DX CENTRAL MAINFRAME<br>AUTHENTICATION REQUIRED<span class="blink">_</span></div>', unsafe_allow_html=True)
        
        js_get = "JSON.parse(localStorage.getItem('dx_central_operator'));"
        saved_data = st_javascript(js_get)
        
        if saved_data and isinstance(saved_data, dict) and not st.session_state.get('ls_loaded'):
            st.session_state.op_name_val = saved_data.get("name", "")
            st.session_state.op_city_val = saved_data.get("city", "")
            st.session_state.op_state_val = saved_data.get("state", "")
            st.session_state.op_country_val = saved_data.get("country", "United States")
            st.session_state.op_lat_val = float(saved_data.get("lat", 0.0))
            st.session_state.op_lon_val = float(saved_data.get("lon", 0.0))
            st.session_state.ls_loaded = True
            if st.session_state.op_name_val:
                st.success(f"LOCAL PROFILE DETECTED: {st.session_state.op_name_val.upper()}")
            
        for key in ['op_name_val', 'op_city_val', 'op_state_val', 'op_country_val', 'op_lat_val', 'op_lon_val']:
            if key not in st.session_state: 
                if "lat" in key or "lon" in key:
                    st.session_state[key] = 0.0
                elif key == "op_country_val":
                    st.session_state[key] = "United States"
                else:
                    st.session_state[key] = ""

        if st.session_state.op_lat_val == 0.0 or st.session_state.op_lon_val == 0.0:
            st.error("🛑 ACTION REQUIRED: CALIBRATE TERMINAL LOCATION. A valid Latitude and Longitude are required to calculate intercept distances.")

        st.markdown("#### 1. CALIBRATE LOCATION")
        loc_method = st.radio("CALIBRATION METHOD", ["GRID SQUARE", "CITY SEARCH", "MANUAL COORDINATES"], horizontal=True)
        
        if loc_method == "GRID SQUARE":
            st.text_input("ENTER 4 OR 6 CHAR GRID", key="grid_input", on_change=update_from_grid)
        elif loc_method == "CITY SEARCH":
            col_s1, col_s2 = st.columns([3, 1])
            col_s1.text_input("ENTER CITY & STATE", key="search_query")
            col_s2.markdown("<br>", unsafe_allow_html=True)
            col_s2.button("EXECUTE SEARCH", on_click=update_from_search, use_container_width=True)

        c_lat, c_lon = st.columns(2)
        c_lat.number_input("LATITUDE", key="op_lat_val", format="%.4f")
        c_lon.number_input("LONGITUDE", key="op_lon_val", format="%.4f")

        st.markdown("#### 2. AGENT IDENTITY")
        with st.form("login_form"):
            op_name = st.text_input("AGENT IDENTITY (CALLSIGN/HANDLE)", value=st.session_state.get("op_name_val", ""))
            
            c1, c2, c3 = st.columns([2, 1, 2])
            op_city = c1.text_input("HOME QTH: CITY", value=st.session_state.get("op_city_val", ""))
            op_state = c2.text_input("STATE/PROV", value=st.session_state.get("op_state_val", ""))
            
            ctry_options = ["United States", "Canada", "Mexico", "United Kingdom", "Australia", "Other"]
            curr_ctry = st.session_state.get("op_country_val", "United States")
            ctry_idx = ctry_options.index(curr_ctry) if curr_ctry in ctry_options else 0
            op_country = c3.selectbox("COUNTRY", ctry_options, index=ctry_idx)
            
            remember_me = st.checkbox("[ SAVE CREDENTIALS TO LOCAL TERMINAL ]", value=True)
            
            if st.form_submit_button("> AUTHENTICATE"):
                if op_name and st.session_state.op_lat_val != 0.0 and st.session_state.op_lon_val != 0.0:
                    st.session_state.operator_profile = {
                        "name": op_name, 
                        "city": op_city, 
                        "state": op_state, 
                        "country": op_country, 
                        "lat": st.session_state.op_lat_val, 
                        "lon": st.session_state.op_lon_val
                    }
                    if remember_me:
                        st.session_state.profile_to_save = st.session_state.operator_profile
                    nav_to("TERMINAL_HOME")
                    st.rerun()
                else: 
                    st.error("ACCESS DENIED. AGENT IDENTITY AND NON-ZERO LOCATION REQUIRED.")

    # --- 8B. THE HOME TERMINAL ---
    elif st.session_state.sys_state == "TERMINAL_HOME":
        st.markdown('<div class="typewriter">GREETINGS, FELLOW SIGNAL TRAVELER.<br>WOULD YOU LIKE TO PLAY A GAME?<span class="blink">_</span></div>', unsafe_allow_html=True)
        if "gcp_service_account" not in st.secrets:
            st.error("🚨 [ SYSTEM ALERT ] DATALINK OFFLINE. Streamlit Secrets not configured. Logs cannot be submitted to the Google Sheet.")
        if not AWARDS_ACTIVE:
            st.warning("⚠️ AWARDS MODULE OFFLINE. Ensure 'modules/awards.py' is deployed to activate Century Club notifications.")
        if not BOUNTY_ACTIVE:
            st.warning("⚠️ BOUNTY MODULE OFFLINE. Ensure 'modules/bounty.py' is deployed.")
        st.write("Use the **[ SYSTEM COMMAND MENU ]** in the sidebar to navigate the mainframe.")

    # --- PROTOCOLS ---
    elif st.session_state.sys_state == "RULES":
        st.markdown("<h1 style='color:#1bd2d4;'>DIRECTIVES & PROTOCOLS (RULES OF ENGAGEMENT)</h1>", unsafe_allow_html=True)
        st.markdown("---")
        st.markdown("""
        <div style='font-size:1.2rem; color:#ffffff; line-height: 1.6;'>
        <b style='color:#1bd2d4; font-size:1.4rem;'>MISSION BRIEFING</b><br>
        Welcome to the 2026 Summer of DX. Your mission is to monitor, intercept, and catalog distant radio transmissions across the Medium Wave (MW), FM Broadcast Band II (FM), and US-based NOAA Weather Radio (NWR) spectrums. For this operation, we have completely overhauled the Global Intelligence Command. Registration is no longer required. The terminal is live, the databanks are primed, and the spectrum is yours.
        <br><br>
        <b style='color:#1bd2d4; font-size:1.4rem;'>OPERATIONAL WINDOW</b><br>
        <b>Intercept Window:</b> Saturday, May 2, 2026 @ 0100 UTC through Monday, August 31, 2026 @ 2359 UTC. All telemetry must be captured within this timeframe.<br>
        <b>Uplink Window:</b> The Terminal opens for data submission on Friday, May 1, 2026 @ 2300 UTC. The Terminal permanently severs external connections on Wednesday, September 30, 2026 @ 2359 UTC. This provides a 30-day grace period for post-operation audio review and data transmission.
        <br><br>
        <b style='color:#1bd2d4; font-size:1.4rem;'>THE SCORING MATRIX</b><br>
        Your intercepts are actively graded by the Central Forge using the following parameters per band (MW, FM, NWR are scored independently):<br>
        <b>1. Base Distance:</b> 1 point awarded per 100 miles of signal travel (e.g., 283 miles = 2 pts, 1398 miles = 13 pts).<br>
        <b>2. Hardware Bonus:</b> +5 points awarded to any intercept captured using legacy or traditional hardware (Non-SDR).<br>
        <b>3. Geographic Multipliers (NEW):</b> Your base score is exponentially amplified by your geographic footprint. Every unique US State, Canadian Province, and International Country you log acts as a 1x multiplier for your score on that band. (Example: 1,000 base points x [35 States + 3 Provinces + 10 Countries] = 48,000 Total Points).<br>
        <b>4. Consistency Bonus:</b> Agents who successfully transmit 10+ intercepts in a single calendar month on a specific band receive a flat +100 Point tactical bonus.
        <br><br>
        <b style='color:#1bd2d4; font-size:1.4rem;'>SPECIAL OPERATIONS & COMMENDATIONS</b><br>
        <b>The John Cereghin Century Club (UPDATED):</b> Track down 100 unique US Maidenhead Grids on MW or FM, 20 on NWR to achieve Century Club status and earn an exclusive commendation certificate. Endorsements are awarded for every 50 subsequent grids (10 for NWR).<br>
        <b>The County Hunter Protocol (NEW):</b> A new forensic tracker monitors your intercepts across all US Counties and Parishes. Maximize your coverage area to climb the newly established County Ledgers.<br>
        <b>The Rover Directive (NEW):</b> Agents are encouraged to go mobile to activate empty grids and counties. Select "ROVER" during your intercept log and provide your active operating Grid Square or County/Parish. The more dedicated Rovers will receive special recognition from High Command for their efforts.<br>
        <b>Bounty Hunts (NEW):</b> A highly classified "mission" will be issued every two weeks. To acquire your target dossier, you must intercept the cryptographic codeword broadcasted on DX Radio (thisisprobablydxradio.com). Timing details will be communicated from High Command through the Terminal.
        <br><br>
        <b style='color:#1bd2d4; font-size:1.4rem;'>RULES OF ENGAGEMENT</b><br>
        <b>Target Validation:</b> Only licensed stations broadcasting on their primary frequency count (no images, spurs, or harmonics). For MW, TIS/HAR and Pirate stations may be submitted, but they will not count toward Grid or County chases.<br>
        <b>Singular Intercepts:</b> A specific station may only be logged once per band for the duration of the DX event. A station can be submitted for multiple events on FM and NWR to demonstrate ionospheric performance and characteristics. Duplicate entries (a single station logged at the same date/time) will be purged. (Logging an FM HD sub-channel does not count as a new log; omit "-HD" or "-FM" from callsigns. -LP is acceptable, per High Command).<br>
        <b>Hardware Restrictions:</b> Equipment used must be your own (or equipment you maintain). The use of remote online receivers (other than your own) is strictly prohibited for logging, though they may be used for target identification assistance.<br>
        <b>Data Ingestion:</b> Manual entry is no longer required for listed targets. Agents can now use the Terminal's Database Search (for click-to-log targeting) or the Bulk Infiltration tool (supporting seamless CSV uploads from FMList, MWList, and WLogger). Manual Entry is still available for those situations where the other methods fail to allow capture for a station.
        </div>
        """, unsafe_allow_html=True)

    elif st.session_state.sys_state == "PRIVACY":
        st.markdown("<h1 style='color:#1bd2d4;'>DATA SECURITY CLEARANCE (PRIVACY)</h1>", unsafe_allow_html=True)
        st.markdown("---")
        st.markdown("""
        <div style='font-size:1.2rem; color:#ffffff; line-height: 1.6;'>
        <b style='color:#1bd2d4; font-size: 1.5rem;'>CLASSIFIED OPERATIONAL DATA PROTOCOL</b>
        <br><br>
        Your operational security is our highest priority. 
        <br><br>
        <b style='color:#1bd2d4;'>1. ZERO-RETENTION IDENTITY:</b><br>
        This terminal utilizes localized browser caching. We do not store, distribute, or retain passwords, IP addresses, or personal contact information on central servers.
        <br><br>
        <b style='color:#1bd2d4;'>2. GEOSPATIAL PROCESSING:</b><br>
        The exact Latitude and Longitude requested during your calibration sequence are utilized <b>strictly</b> as mathematical endpoints to calculate signal distance, Maidenhead Grids, and County vectors. We do not track your physical location beyond the calculations required for scoring.
        <br><br>
        <b style='color:#1bd2d4;'>3. PUBLIC LEDGER:</b><br>
        By transmitting intercept data, you authorize your Callsign/Operator Name, general City/State/Country location, and intercepted telemetry to be published on the Global Intelligence Command dashboard for leaderboard tracking and community analysis.
        </div>
        """, unsafe_allow_html=True)

    # --- 8C. MW INTERCEPT ROOM ---
    elif st.session_state.sys_state == "MW_LOG":
        if not is_terminal_open():
            st.error("🔒 **UPLINK SEVERED: THE TERMINAL IS CURRENTLY LOCKED.**")
            st.warning("Data submission is only authorized between 2300 UTC May 1, 2026 and 2359 UTC September 30, 2026. You may continue to view the Dashboard and Intelligence Ledgers.")
            st.stop()
            
        st.markdown("### [ MW INTERCEPT CONSOLE ACTIVE ]")
        
        active_lat = float(st.session_state.operator_profile.get('lat', 0.0))
        active_lon = float(st.session_state.operator_profile.get('lon', 0.0))
        entry_cat_val = "HOME QTH"
                
        st.markdown("#### 1. TARGET ACQUISITION")
        tab_search, tab_manual, tab_import = st.tabs(["[ DATABASE SEARCH ]", "[ MANUAL ENTRY ]", "[ BULK IMPORT ]"])
        target_data = {}
        
        with tab_search:
            st.write("ACCESSING DOMESTIC & INTERNATIONAL DATABANKS...")
            if mw_db.empty: 
                st.error("[ SYSTEM ALERT ] DATABANK OFFLINE.")
            else:
                if 'mw_filter_key' not in st.session_state: 
                    st.session_state.mw_filter_key = 0
                    
                def reset_mw_filters(): 
                    st.session_state.mw_filter_key += 1
                
                c_btn1, c_btn2 = st.columns([1.5, 3.5])
                c_btn1.button("[ RESET SEARCH FILTERS ]", on_click=reset_mw_filters)
                if c_btn2.button("[ REFRESH STATION DATA ]", key="sync_mw"):
                    get_logged_dict.clear()
                    load_mw_intel.clear()
                    st.rerun()
                
                fk = st.session_state.mw_filter_key
                c1, c2, c3, c4 = st.columns(4)
                
                all_freqs = sorted([str(x) for x in mw_db['Frequency'].dropna().unique()])
                mw_states = sorted([str(x) for x in mw_db['State'].dropna().unique()])
                mw_countries = sorted([str(x) for x in mw_db['Country'].dropna().unique()]) if 'Country' in mw_db.columns else ["United States"]
                
                f_freq = c1.selectbox("FREQ (kHz)", ["All"] + all_freqs, key=f"mw_f1_{fk}")
                f_call = c2.text_input("CALLSIGN", key=f"mw_f2_{fk}")
                f_city = c3.text_input("CITY", key=f"mw_f3_{fk}")
                f_state = c4.selectbox("STATE", ["All"] + mw_states, key=f"mw_f4_{fk}")
                
                c5, c6, c7, c8 = st.columns(4)
                f_ctry = c5.selectbox("COUNTRY", ["All"] + mw_countries, key=f"mw_f5_{fk}")
                f_county = c6.text_input("COUNTY/PARISH", key=f"mw_f6_{fk}")
                f_grid = c7.text_input("GRID", key=f"mw_f7_{fk}")
                f_status = c8.selectbox("STATUS", ["All", "Logged Only", "Not Logged Only"], key=f"mw_f8_{fk}")
                
                results = mw_db.copy()
                if f_freq != "All": 
                    results = results[results['Frequency'] == float(f_freq)]
                if f_call: 
                    c_simp = simplify_string(f_call)
                    results = results[results['Callsign'].apply(lambda x: c_simp in simplify_string(x))]
                if f_city: 
                    results = results[results['City'].str.contains(f_city, case=False, na=False)]
                if f_state != "All": 
                    results = results[results['State'] == f_state]
                if f_ctry != "All": 
                    results = results[results['Country'] == f_ctry]
                if f_county: 
                    results = results[results['County'].str.contains(f_county, case=False, na=False)]
                if f_grid: 
                    results = results[results['Grid'].str.contains(f_grid.upper(), na=False)]
                    
                if f_status != "All":
                    logged_dict = get_logged_dict(st.session_state.operator_profile.get('name', ''), "AM")
                    results['Is_Logged'] = results.apply(lambda r: check_is_logged_mw(r['Frequency'], r['Callsign'], r['City'], r['Country'], logged_dict), axis=1)
                    if f_status == "Logged Only": 
                        results = results[results['Is_Logged']]
                        st.markdown("<div style='font-size: 0.9rem; color: #1bd2d4; opacity: 0.7; margin-top: -15px; margin-bottom: 10px;'>*To export your logs to a CSV, choose 'Logged Only' from the status filter.*</div>", unsafe_allow_html=True)
                        full_logs_df = get_full_logs_df(st.session_state.operator_profile.get('name', ''), "AM")
                        if not full_logs_df.empty:
                            csv_data = full_logs_df.to_csv(index=False).encode('utf-8')
                            st.download_button(label="📥 DOWNLOAD MY LOGS (CSV)", data=csv_data, file_name=f"My_MW_Logs_{datetime.date.today().strftime('%Y%m%d')}.csv", mime="text/csv")
                    else: 
                        results = results[~results['Is_Logged']]
                        st.markdown("<div style='font-size: 0.9rem; color: #1bd2d4; opacity: 0.7; margin-top: -15px; margin-bottom: 10px;'>*To export your logs to a CSV, choose 'Logged Only' from the status filter.*</div>", unsafe_allow_html=True)
                else:
                    st.markdown("<div style='font-size: 0.9rem; color: #1bd2d4; opacity: 0.7; margin-top: -15px; margin-bottom: 10px;'>*To export your logs to a CSV, choose 'Logged Only' from the status filter.*</div>", unsafe_allow_html=True)
                        
                st.write(f"> {len(results)} TARGETS FOUND:")
                st.markdown("<div style='font-size: 0.9rem; color: #1bd2d4; opacity: 0.7; margin-top: -15px; margin-bottom: 10px;'>*Sources: Mesa Mike's AM DB (mesamike.org) & DX Central MW Frequency Challenge Data*</div>", unsafe_allow_html=True)
                
                if not results.empty:
                    if len(results) <= 100:
                        for idx, r in results.iterrows():
                            if float(r.get('LAT', 0.0)) == 0.0 and float(r.get('LON', 0.0)) == 0.0:
                                lat, lon = get_lat_lon_from_city(r['City'], r.get('Country', 'United States'))
                                results.at[idx, 'LAT'] = lat
                                results.at[idx, 'LON'] = lon
                                
                    results['Dist'] = results.apply(lambda r: calculate_distance(active_lat, active_lon, r.get('LAT'), r.get('LON')), axis=1)
                    
                    if active_lat != 0.0 and active_lon != 0.0:
                        results = results[results['Dist'] > 0.0]
                        
                    results = results.sort_values(by='Dist', ascending=True)
                    
                    logged_dict = get_logged_dict(st.session_state.operator_profile.get('name', ''), "AM")
                    results['Is_Logged'] = results.apply(lambda r: check_is_logged_mw(r['Frequency'], r['Callsign'], r['City'], r['Country'], logged_dict), axis=1)
                    results['Display Call'] = results.apply(lambda r: f"🟢 {r['Callsign']}" if r['Is_Logged'] else r['Callsign'], axis=1)
                    results.insert(0, 'Log?', False)
                    
                    view_df = results[['Log?', 'Frequency', 'Display Call', 'City', 'State', 'Country', 'Dist', 'Grid', 'County', 'Callsign']]
                    edited_df = st.data_editor(
                        view_df, 
                        hide_index=True, 
                        use_container_width=True,
                        column_config={
                            "Log?": st.column_config.CheckboxColumn("Log?"), 
                            "Dist": st.column_config.NumberColumn("Dist (mi)", format="%.1f"), 
                            "County": "County/Parish",
                            "Callsign": None 
                        },
                        disabled=['Frequency', 'Display Call', 'City', 'State', 'Country', 'Dist', 'Grid', 'County', 'Callsign'], 
                        key=f"mw_db_editor_{fk}"
                    )
                    
                    selected_rows = edited_df[edited_df['Log?'] == True]
                    if not selected_rows.empty:
                        target = selected_rows.iloc[0]
                        grid_str = f" | Grid: {target['Grid']}" if target['Grid'] else ""
                        dist_str = f" | {target['Dist']} mi" if target['Dist'] > 0 else ""
                        st.success(f"TARGET LOCKED: {target['Callsign']} ({target['City']}, {target['State']} - {target.get('Country', 'United States')}{grid_str}{dist_str})")
                        target_data = {
                            "freq": target['Frequency'], 
                            "call": target['Callsign'], 
                            "city": target['City'], 
                            "state": target['State'], 
                            "county": target.get('County', 'Unknown'), 
                            "country": target.get('Country', 'United States'), 
                            "grid": target['Grid'], 
                            "dist": target['Dist']
                        }
                        
                        st.markdown("#### RECEPTION VIA SDR?")
                        sdr_choice_db = st.radio("SDR Used?", ["Yes", "No"], horizontal=True, key=f"mw_sdr_db_{fk}")
                        target_data["sdr"] = sdr_choice_db

        with tab_manual:
            st.write("INITIATE UNLISTED / INTERNATIONAL PROTOCOL...")
            spacing = st.radio("CHANNEL SPACING", ["10 kHz (Region 2)", "9 kHz (Regions 1 & 3)"], horizontal=True)
            step_val = 10 if "10" in spacing else 9
                
            c_m1, c_m2, c_m3 = st.columns(3)
            man_freq = c_m1.number_input("MANUAL FREQ (kHz)", min_value=531, max_value=1710, value=540, step=step_val, key="man_mw")
            man_call = c_m2.text_input("STATION ID")
            
            all_db_countries = sorted([str(x) for x in mw_db['Country'].dropna().unique()]) if not mw_db.empty else ["United States"]
            if "Other" not in all_db_countries: 
                all_db_countries.append("Other")
            def_idx = all_db_countries.index("United States") if "United States" in all_db_countries else 0
            man_ctry = c_m3.selectbox("COUNTRY", all_db_countries, index=def_idx, key="man_mw_ctry")
            man_other = st.text_input("SPECIFY COUNTRY:") if man_ctry == "Other" else ""
            
            c_m4, c_m5, c_m6 = st.columns(3)
            man_city = c_m4.text_input("STATION CITY")
            man_sp = c_m5.selectbox("STATION STATE/PROV", get_state_list(man_ctry))
            man_dist = c_m6.number_input("EST. DISTANCE (MILES)", min_value=0.0, step=1.0)
            
            if man_call:
                selected_country = man_other if man_ctry == "Other" else man_ctry
                target_data = {
                    "freq": man_freq, 
                    "call": standardize_cuban_station(man_call, man_freq, selected_country), 
                    "city": man_city, 
                    "state": man_sp, 
                    "county": " - " if selected_country not in ["United States"] else "", 
                    "country": selected_country, 
                    "grid": "", 
                    "dist": man_dist
                }

        with tab_import:
            st.write("INITIATE BULK INGESTION PROTOCOL (MWLIST ONLY)...")
            uploaded_file = st.file_uploader("UPLOAD CSV/TSV PAYLOAD", type=["csv", "txt", "tsv"], key="mw_bulk")
            if uploaded_file is not None:
                try:
                    df_import = handle_mw_file_upload(uploaded_file)
                    st.write(f"DETECTED {len(df_import)} RECORDS. PREVIEW:")
                    st.dataframe(df_import.head(5), use_container_width=True)
                    st.markdown("#### MAP DATABANK COLUMNS")
                    cols = ["<Skip>"] + df_import.columns.tolist()
                    
                    c_i1, c_i2, c_i3, c_i4 = st.columns(4)
                    map_freq = c_i1.selectbox("FREQUENCY", cols, index=get_idx(["khz", "freq"], cols), key="mw_map_1")
                    map_call = c_i2.selectbox("CALLSIGN", cols, index=get_idx(["program", "call", "station"], cols), key="mw_map_2")
                    map_date = c_i3.selectbox("DATE (UTC)", cols, index=get_idx(["date"], cols), key="mw_map_3")
                    map_time = c_i4.selectbox("TIME (UTC)", cols, index=get_idx(["utc", "time"], cols), key="mw_map_4")
                    
                    c_i5, c_i6, c_i7, c_i8 = st.columns(4)
                    map_city = c_i5.selectbox("STATION CITY", cols, index=get_idx(["location", "city", "loc"], cols), key="mw_map_5")
                    map_state = c_i6.selectbox("STATION STATE", cols, index=get_idx(["reg", "state", "prov"], cols), key="mw_map_6")
                    map_ctry = c_i7.selectbox("COUNTRY / ITU", cols, index=get_idx(["itu", "countr"], cols), key="mw_map_7")
                    map_dist = c_i8.selectbox("DISTANCE", cols, index=get_idx(["qrb", "dist", "mi", "km"], cols), key="mw_map_10")
                    
                    c_i9, c_i10, c_i11 = st.columns(3)
                    map_prop = c_i9.selectbox("PROPAGATION", cols, index=get_idx(["propa", "mode"], cols), key="mw_map_9")
                    map_notes = c_i10.selectbox("NOTES / DETAILS", cols, index=get_idx(["remarks", "detail", "info", "comment"], cols), key="mw_map_11")
                    map_sdr = c_i11.selectbox("SDR USED?", cols, index=0, key="mw_map_12")
                    
                    st.markdown("#### DEFAULT SDR STATUS")
                    st.caption("If a log has no mapped SDR status, apply this global default.")
                    def_sdr = st.radio("SDR Used Default", ["Yes", "No"], horizontal=True, key="mw_def_sdr")
                    
                    if st.button("> PROCESS & TRANSMIT BULK PAYLOAD", key="mw_bulk_btn"):
                        sheet = get_gsheet()
                        if sheet is None: 
                            st.error("🚨 DATALINK OFFLINE. Streamlit Secrets not configured.")
                        else:
                            bulk_rows = []
                            op = st.session_state.operator_profile
                            
                            vals = sheet.get_all_values()
                            existing_signatures = set()
                            op_name_upper = op.get('name', '').strip().upper()
                            if len(vals) > 1:
                                for r in vals[1:]:
                                    if len(r) >= 16:
                                        r_name = str(r[0]).strip().upper()
                                        if r_name != op_name_upper: 
                                            continue
                                        r_band = str(r[4]).strip().upper()
                                        r_freq_raw = str(r[5]).strip() if r_band == "AM" else str(r[6]).strip()
                                        try:
                                            r_freq = str(float(r_freq_raw.replace(',', '.')))
                                        except Exception:
                                            r_freq = r_freq_raw
                                        r_call = str(r[7]).strip().upper()
                                        r_date = str(r[14]).strip()
                                        r_time = str(r[15]).strip()
                                        existing_signatures.add(f"{r_band}_{r_freq}_{r_call}_{r_date}_{r_time}")
                            
                            # --- TEMPORAL SCRUBBER ---
                            with st.spinner("Scanning payload against temporal mission parameters..."):
                                valid_df, skipped_out_of_range = filter_bulk_dataframe(df_import, date_col=map_date, time_col=map_time)
                            
                            if valid_df.empty:
                                if skipped_out_of_range > 0:
                                    st.error(f"❌ **INFILTRATION FAILED:** All {skipped_out_of_range} intercepts were rejected for falling outside the authorized DEFCON 6 operational window (May 2 - Aug 31).")
                                else:
                                    st.error("❌ **INFILTRATION FAILED:** No valid intercepts found.")
                            else:
                                skipped_dupes = 0
                                
                                for _, row in valid_df.iterrows():
                                    raw_freq = row[map_freq] if map_freq != "<Skip>" else ""
                                    
                                    if raw_freq:
                                        try:
                                            f_val = float(str(raw_freq).replace(',', '.').strip())
                                            if f_val < 530.0 or f_val > 1710.0: 
                                                continue 
                                        except Exception: 
                                            pass
                                            
                                    raw_country = row[map_ctry] if map_ctry != "<Skip>" else "USA"
                                    clean_country = itu_map.get(str(raw_country).upper(), str(raw_country).title())
                                    if clean_country.upper() == "USA": 
                                        clean_country = "United States"
                                    
                                    raw_call = row[map_call] if map_call != "<Skip>" else ""
                                    clean_call = clean_callsign(raw_call)
                                    clean_call = standardize_cuban_station(clean_call, raw_freq, clean_country)
                                    
                                    dist_val = 0.0
                                    if map_dist != "<Skip>":
                                        raw_dist = str(row[map_dist]).lower()
                                        try:
                                            clean_dist = float(raw_dist.replace('km', '').replace('mi', '').replace(',', '').strip())
                                            if "km" in raw_dist or "qrb" in str(map_dist).lower(): 
                                                dist_val = clean_dist * 0.621371
                                            else: 
                                                dist_val = clean_dist
                                        except Exception: 
                                            dist_val = 0.0
                                            
                                    clean_state = row[map_state] if map_state != "<Skip>" else ""
                                    if clean_country not in ["United States", "Canada", "Mexico"]: 
                                        clean_state = "DX"
                                    
                                    clean_city = str(row[map_city]).strip() if map_city != "<Skip>" and not pd.isna(row[map_city]) else ""
                                    station_grid = ""
                                    station_county = " - " if clean_country not in ["United States"] else ""
                                    
                                    # EXPLICIT MW DUAL-TRACK MATCHING ENGINE & OVERWRITE
                                    if not mw_db.empty and raw_freq:
                                        try:
                                            f_val = float(str(raw_freq).replace(',', '.'))
                                            match_df = mw_db[mw_db['Frequency'] == f_val]
                                            for _, m_row in match_df.iterrows():
                                                db_call = simplify_string(m_row['Callsign'])
                                                db_city = simplify_string(m_row.get('City', ''))
                                                db_state = simplify_string(m_row.get('State', ''))
                                                db_country = simplify_string(m_row.get('Country', 'United States'))
                                                
                                                is_match = False
                                                imp_call = simplify_string(clean_call)
                                                imp_country = simplify_string(clean_country)
                                                imp_city = simplify_string(clean_city)
                                                imp_state = simplify_string(clean_state)
                                                
                                                if clean_country.upper() in ["UNITED STATES", "CANADA", "MEXICO", "CUBA"]:
                                                    if imp_call and db_call and (imp_call in db_call or db_call in imp_call): 
                                                        is_match = True
                                                    else:
                                                        if imp_city and imp_country == db_country and (imp_city in db_city or db_city in imp_city): 
                                                            is_match = True
                                                            
                                                if is_match:
                                                    station_grid = m_row['Grid']
                                                    station_county = m_row['County']
                                                    clean_call = m_row['Callsign']
                                                    clean_city = m_row['City']
                                                    clean_state = m_row['State']
                                                    break
                                        except Exception: 
                                            pass

                                    try:
                                        sig_freq = str(float(str(raw_freq).replace(',', '.')))
                                    except Exception:
                                        sig_freq = str(raw_freq).strip()
                                        
                                    call_sig = str(clean_call).strip().upper()
                                    date_sig = str(format_date_import(row[map_date])).strip()
                                    time_sig = str(format_time_import(row[map_time])).strip()
                                    
                                    row_sig = f"AM_{sig_freq}_{call_sig}_{date_sig}_{time_sig}"
                                    if row_sig in existing_signatures:
                                        skipped_dupes += 1
                                        continue
                                    existing_signatures.add(row_sig)
                                    
                                    sdr_val = str(row[map_sdr]).strip().title() if map_sdr != "<Skip>" and not pd.isna(row[map_sdr]) else def_sdr
                                    if sdr_val not in ["Yes", "No"]: 
                                        sdr_val = def_sdr

                                    r_data = [
                                        op.get('name', ''), 
                                        op.get('city', ''), 
                                        op.get('state', ''), 
                                        op.get('country', ''),
                                        "AM", 
                                        raw_freq, 
                                        "", 
                                        clean_call, 
                                        "", 
                                        clean_city, 
                                        clean_state, 
                                        clean_country, 
                                        "", 
                                        station_grid,
                                        format_date_import(row[map_date]) if map_date != "<Skip>" else "", 
                                        row[map_time] if map_time != "<Skip>" else "", 
                                        round(dist_val, 1), 
                                        row[map_notes] if map_notes != "<Skip>" else "", 
                                        "", 
                                        "", 
                                        map_mw_prop(row[map_prop]) if map_prop != "<Skip>" else "Other", 
                                        station_county, 
                                        entry_cat_val, 
                                        "", 
                                        "",
                                        sdr_val
                                    ]
                                    bulk_rows.append(["" if pd.isna(item) else (item.item() if hasattr(item, 'item') else item) for item in r_data])
                                    
                                try:
                                    sheet.append_rows(bulk_rows)
                                    # Force cache clear to ensure immediate award recognition
                                    try:
                                        get_full_logs_df.clear()
                                        get_logged_dict.clear()
                                    except Exception: pass
                                    
                                    st.success(f"### [ {len(bulk_rows)} RECORDS TRANSMITTED ]")
                                    if skipped_dupes > 0:
                                        st.info(f"### [ {skipped_dupes} DUPLICATES IGNORED ]")
                                    if skipped_out_of_range > 0:
                                        st.warning(f"### [ {skipped_out_of_range} LOGS OUTSIDE WINDOW (May 1 - Aug 31) PURGED ]")
                                    st.balloons()
                                    
                                except Exception as e: 
                                    st.error(f"BULK FAILED: {e}")
                except Exception as e: 
                    st.error(f"FILE PARSING ERROR: {e}")

        st.markdown("#### 3. TIME SYNCHRONIZATION")
        log_mode = st.radio("LOGGING MODE", ["LIVE DX (AUTO-CLOCK)", "IQ RECORDING (STICKY MEMORY)"], horizontal=True, key="mw_log_mode", label_visibility="collapsed")

        st.markdown("#### 4. SUBMIT INTERCEPT")
        with st.form("mw_submit_form", clear_on_submit=True):
            col_s1, col_s2, col_s3 = st.columns([1, 1, 1])
            now = datetime.datetime.now(datetime.timezone.utc)
            
            # Use real-time for LIVE DX, use session state for IQ RECORDING
            def_date = now.date() if "LIVE" in log_mode else st.session_state.iq_date
            def_time = now.strftime("%H%M") if "LIVE" in log_mode else st.session_state.iq_time
            
            log_date = col_s1.date_input("DATE (UTC)", value=def_date)
            log_time = col_s2.text_input("TIME (UTC)", value=def_time)
            
            if "sdr" in target_data: 
                log_sdr = target_data["sdr"]
            else: 
                log_sdr = col_s3.selectbox("RECEPTION VIA SDR?", ["Yes", "No"], index=0, key="mw_man_sdr")
                
            log_notes = st.text_area("PROGRAMMING / INTERCEPT NOTES")
            
            submit_log = st.form_submit_button("> TRANSMIT REPORT TO SERVER")
            if submit_log:
                # Instantly save the submitted date/time to memory so it sticks for the next record
                st.session_state.iq_date = log_date
                st.session_state.iq_time = log_time
                
                if not target_data: 
                    st.error("TARGET NOT ACQUIRED. SELECT OR ENTER A STATION.")
                elif not is_reception_valid(log_date.strftime("%Y-%m-%d"), log_time):
                    st.error("🚨 TRANSMISSION REJECTED: Intercept date falls outside the authorized DEFCON 6 window (May 2 - Aug 31 UTC). Please verify your log and try again.")
                else:
                    sheet = get_gsheet()
                    if sheet is None: 
                        st.error("🚨 DATALINK OFFLINE. Streamlit Secrets are not configured.")
                    else:
                        try:
                            op = st.session_state.operator_profile
                            row_data = [
                                op.get('name', ''), 
                                op.get('city', ''), 
                                op.get('state', ''), 
                                op.get('country', ''),
                                "AM", 
                                target_data.get("freq", ""), 
                                "", 
                                target_data.get("call", ""), 
                                "", 
                                target_data.get("city", ""),
                                target_data.get("state", ""), 
                                target_data.get("country", ""), 
                                "", 
                                target_data.get("grid", ""),
                                log_date.strftime("%m/%d/%Y"), 
                                log_time, 
                                target_data.get("dist", 0.0), 
                                log_notes, 
                                "", 
                                "",
                                "", 
                                target_data.get("county", ""), 
                                entry_cat_val, 
                                "", 
                                "",
                                log_sdr
                            ]
                            sheet.append_row(["" if pd.isna(item) else (item.item() if hasattr(item, 'item') else item) for item in row_data])
                            
                            # Force cache clear
                            try:
                                get_full_logs_df.clear()
                                get_logged_dict.clear()
                            except Exception: pass
                            
                            st.markdown("### [ TRANSMISSION SUCCESSFUL ]")
                            st.balloons()
                            
                        except Exception as e: 
                            st.error(f"TRANSMISSION FAILED: {e}")

    # --- 8D. FM INTERCEPT ROOM ---
    elif st.session_state.sys_state == "FM_LOG":
        if not is_terminal_open():
            st.error("🔒 **UPLINK SEVERED: THE TERMINAL IS CURRENTLY LOCKED.**")
            st.warning("Data submission is only authorized between 2300 UTC May 1, 2026 and 2359 UTC September 30, 2026. You may continue to view the Dashboard and Intelligence Ledgers.")
            st.stop()
            
        st.markdown("### [ FM INTERCEPT CONSOLE ACTIVE ]")
        st.markdown("#### 1. OPERATING PARAMETERS")
        r_cat = st.radio("CATEGORY", ["HOME QTH", "ROVER"], horizontal=True, label_visibility="collapsed", key="fm_cat")
        rover_grid = ""
        
        active_lat = float(st.session_state.operator_profile.get('lat', 0.0))
        active_lon = float(st.session_state.operator_profile.get('lon', 0.0))
        
        if r_cat == "ROVER":
            st.warning("ROVER MODE: ENTER CURRENT MAIDENHEAD GRID TO CALIBRATE DISTANCE.")
            rover_grid = st.text_input("ROVER GRID (e.g., EM40)", key="fm_rov")
            if len(rover_grid) >= 4:
                try:
                    r_lat, r_lon = mh.to_location(rover_grid)
                    active_lat = float(r_lat)
                    active_lon = float(r_lon)
                except Exception: 
                    pass
                    
        st.markdown("#### 2. TARGET ACQUISITION")
        tab_search, tab_manual, tab_import = st.tabs(["[ DATABASE SEARCH ]", "[ MANUAL ENTRY ]", "[ BULK IMPORT ]"])
        target_data = {}
        
        with tab_search:
            st.write("ACCESSING WTFDA DATABANKS...")
            if fm_db.empty: 
                st.error("[ SYSTEM ALERT ] DATABANK OFFLINE: WTFDA database not found in repository.")
            else:
                if 'fm_filter_key' not in st.session_state: 
                    st.session_state.fm_filter_key = 0
                    
                def reset_fm_filters(): 
                    st.session_state.fm_filter_key += 1
                
                c_btn1, c_btn2 = st.columns([1.5, 3.5])
                c_btn1.button("[ RESET SEARCH FILTERS ]", on_click=reset_fm_filters, key="fm_reset")
                if c_btn2.button("[ REFRESH STATION DATA ]", key="sync_fm"):
                    get_logged_dict.clear()
                    load_fm_intel.clear()
                    st.rerun()
                
                fk = st.session_state.fm_filter_key
                c1, c2, c3, c4 = st.columns(4)
                
                all_freqs = sorted([str(x) for x in fm_db['Frequency'].dropna().unique()])
                fm_states = sorted([str(x) for x in fm_db['State'].dropna().unique()])
                fm_countries = sorted([str(x) for x in fm_db['Country'].dropna().unique()]) if 'Country' in fm_db.columns else ["United States"]
                
                f_freq = c1.selectbox("FREQ (MHz)", ["All"] + all_freqs, key=f"fm_f1_{fk}")
                f_call = c2.text_input("CALLSIGN", key=f"fm_f2_{fk}")
                f_city = c3.text_input("CITY", key=f"fm_f3_{fk}")
                f_state = c4.selectbox("STATE", ["All"] + fm_states, key=f"fm_f4_{fk}")
                
                c5, c6, c7, c8 = st.columns(4)
                f_ctry = c5.selectbox("COUNTRY", ["All"] + fm_countries, key=f"fm_f5_{fk}")
                f_county = c6.text_input("COUNTY/PARISH", key=f"fm_f6_{fk}")
                f_grid = c7.text_input("GRID", key=f"fm_f7_{fk}")
                f_status = c8.selectbox("STATUS", ["All", "Logged Only", "Not Logged Only"], key=f"fm_f8_{fk}")
                
                results = fm_db.copy()
                if f_freq != "All": 
                    results = results[results['Frequency'] == float(f_freq)]
                if f_call: 
                    c_simp = simplify_string(f_call)
                    results = results[results['Callsign'].apply(lambda x: c_simp in simplify_string(x))]
                if f_city: 
                    results = results[results['City'].str.contains(f_city, case=False, na=False)]
                if f_state != "All": 
                    results = results[results['State'] == f_state]
                if f_ctry != "All": 
                    results = results[results['Country'] == f_ctry]
                if f_county: 
                    results = results[results['County'].str.contains(f_county, case=False, na=False)]
                if f_grid: 
                    results = results[results['Grid'].str.contains(f_grid.upper(), na=False)]
                    
                if f_status != "All":
                    logged_dict = get_logged_dict(st.session_state.operator_profile.get('name', ''), "FM")
                    results['Is_Logged'] = results.apply(lambda r: check_is_logged_fm(r['Frequency'], r['Callsign'], r.get('Slogan', ''), r['City'], r['State'], r['Country'], logged_dict), axis=1)
                    if f_status == "Logged Only": 
                        results = results[results['Is_Logged']]
                        st.markdown("<div style='font-size: 0.9rem; color: #1bd2d4; opacity: 0.7; margin-top: -15px; margin-bottom: 10px;'>*To export your logs to a CSV, choose 'Logged Only' from the status filter.*</div>", unsafe_allow_html=True)
                        full_logs_df = get_full_logs_df(st.session_state.operator_profile.get('name', ''), "FM")
                        if not full_logs_df.empty:
                            csv_data = full_logs_df.to_csv(index=False).encode('utf-8')
                            st.download_button(label="📥 DOWNLOAD MY LOGS (CSV)", data=csv_data, file_name=f"My_FM_Logs_{datetime.date.today().strftime('%Y%m%d')}.csv", mime="text/csv")
                    else: 
                        results = results[~results['Is_Logged']]
                        st.markdown("<div style='font-size: 0.9rem; color: #1bd2d4; opacity: 0.7; margin-top: -15px; margin-bottom: 10px;'>*To export your logs to a CSV, choose 'Logged Only' from the status filter.*</div>", unsafe_allow_html=True)
                else:
                    st.markdown("<div style='font-size: 0.9rem; color: #1bd2d4; opacity: 0.7; margin-top: -15px; margin-bottom: 10px;'>*To export your logs to a CSV, choose 'Logged Only' from the status filter.*</div>", unsafe_allow_html=True)
                        
                st.write(f"> {len(results)} TARGETS FOUND:")
                st.markdown("<div style='font-size: 0.9rem; color: #1bd2d4; opacity: 0.7; margin-top: -15px; margin-bottom: 10px;'>*Source: WTFDA FM Database*</div>", unsafe_allow_html=True)
                
                if not results.empty:
                    if len(results) <= 100:
                        for idx, r in results.iterrows():
                            if float(r.get('LAT', 0.0)) == 0.0 and float(r.get('LON', 0.0)) == 0.0:
                                lat, lon = get_lat_lon_from_city(r['City'], r.get('Country', 'United States'))
                                results.at[idx, 'LAT'] = lat
                                results.at[idx, 'LON'] = lon
                                
                    results['Dist'] = results.apply(lambda r: calculate_distance(active_lat, active_lon, r.get('LAT'), r.get('LON')), axis=1)
                    
                    if active_lat != 0.0 and active_lon != 0.0:
                        results = results[results['Dist'] > 0.0]
                        
                    results = results.sort_values(by='Dist', ascending=True)
                    
                    logged_dict = get_logged_dict(st.session_state.operator_profile.get('name', ''), "FM")
                    results['Is_Logged'] = results.apply(lambda r: check_is_logged_fm(r['Frequency'], r['Callsign'], r.get('Slogan', ''), r['City'], r['State'], r['Country'], logged_dict), axis=1)
                    results['Display Call'] = results.apply(lambda r: f"🟢 {r['Callsign']}" if r['Is_Logged'] else r['Callsign'], axis=1)
                    results.insert(0, 'Log?', False)
                    
                    view_df = results[['Log?', 'Frequency', 'Display Call', 'Slogan', 'City', 'State', 'Country', 'Dist', 'Grid', 'County', 'Callsign']]
                    edited_df = st.data_editor(
                        view_df, 
                        hide_index=True, 
                        use_container_width=True,
                        column_config={
                            "Log?": st.column_config.CheckboxColumn("Log?"), 
                            "Dist": st.column_config.NumberColumn("Dist (mi)", format="%.1f"),
                            "County": "County/Parish",
                            "Callsign": None
                        },
                        disabled=['Frequency', 'Display Call', 'Slogan', 'City', 'State', 'Country', 'Dist', 'Grid', 'County', 'Callsign'], 
                        key=f"fm_db_editor_{fk}"
                    )
                    
                    selected_rows = edited_df[edited_df['Log?'] == True]
                    if not selected_rows.empty:
                        target = selected_rows.iloc[0]
                        grid_str = f" | Grid: {target['Grid']}" if target['Grid'] else ""
                        dist_str = f" | {target['Dist']} mi" if target['Dist'] > 0 else ""
                        
                        c_str = target.get('County', '')
                        county_str = f" - {c_str} County" if c_str and c_str not in ["Unknown", " - "] else ""
                        
                        st.success(f"TARGET LOCKED: {target['Callsign']} ({target['City']}, {target['State']}{county_str} - {target.get('Country', 'United States')}{grid_str}{dist_str})")
                        target_data = {
                            "freq": target['Frequency'], 
                            "call": target['Callsign'], 
                            "city": target['City'], 
                            "state": target['State'], 
                            "county": target.get('County', 'Unknown'), 
                            "country": target.get('Country', 'United States'), 
                            "grid": target['Grid'], 
                            "pi": "", 
                            "dist": target['Dist']
                        }
                        
                        st.markdown("#### RECEPTION VIA SDR?")
                        sdr_choice_db = st.radio("SDR Used?", ["Yes", "No"], horizontal=True, key=f"fm_sdr_db_{fk}")
                        target_data["sdr"] = sdr_choice_db

        with tab_manual:
            st.write("INITIATE UNLISTED PROTOCOL...")
            c_m1, c_m2, c_m3 = st.columns(3)
            man_freq = c_m1.number_input("MANUAL FREQ (MHz)", min_value=87.7, max_value=107.9, value=88.1, step=0.1, key="man_fm")
            man_call = c_m2.text_input("STATION ID", key="man_fm_call")
            
            all_db_countries_fm = sorted([str(x) for x in fm_db['Country'].dropna().unique()]) if not fm_db.empty else ["United States"]
            if "Other" not in all_db_countries_fm: 
                all_db_countries_fm.append("Other")
            def_idx = all_db_countries_fm.index("United States") if "United States" in all_db_countries_fm else 0
            man_ctry = c_m3.selectbox("COUNTRY", all_db_countries_fm, index=def_idx, key="man_fm_ctry")
            man_other = st.text_input("SPECIFY COUNTRY:") if man_ctry == "Other" else ""
            
            c_m4, c_m5, c_m6 = st.columns(3)
            man_city = c_m4.text_input("CITY", key="fm_man_cty")
            man_sp = c_m5.selectbox("STATE/PROV", get_state_list(man_ctry), key="fm_sp")
            man_dist = c_m6.number_input("DIST (MILES)", min_value=0.0, step=1.0, key="fm_dist")
            
            if man_call: 
                selected_country = man_other if man_ctry == "Other" else man_ctry
                target_data = {
                    "freq": man_freq, 
                    "call": standardize_cuban_station(man_call, man_freq, selected_country), 
                    "city": man_city, 
                    "state": man_sp, 
                    "county": " - " if selected_country not in ["United States"] else "", 
                    "country": selected_country, 
                    "grid": "", 
                    "pi": "", 
                    "dist": man_dist
                }

        with tab_import:
            st.write("INITIATE BULK INGESTION PROTOCOL...")
            uploaded_file = st.file_uploader("UPLOAD CSV/TSV PAYLOAD", type=["csv", "txt", "tsv"], key="fm_bulk")
            
            if uploaded_file is not None:
                try:
                    df_import = handle_fm_file_upload(uploaded_file)
                    st.write(f"DETECTED {len(df_import)} RECORDS. PREVIEW:")
                    st.dataframe(df_import.head(5), use_container_width=True)
                    st.markdown("#### MAP DATABANK COLUMNS")
                    cols = ["<Skip>"] + df_import.columns.tolist()
                    cols_lower = [str(c).lower() for c in cols]
                    
                    is_wlogger = False
                    if any("timestamp" in c for c in cols_lower) and any("mode" in c for c in cols_lower):
                        is_wlogger = True
                    
                    if is_wlogger:
                        st.success("✅ WLogger Export Format Detected & Mapped")
                        idx_freq = get_idx(["frequency"], cols)
                        idx_call = get_idx(["callsign", "call"], cols)
                        idx_date = get_idx(["timestamp"], cols)
                        idx_time = get_idx(["timestamp"], cols)
                        idx_city = get_idx(["city"], cols)
                        idx_state = get_idx(["state"], cols)
                        idx_ctry = 0
                        idx_dist = get_idx(["distance"], cols)
                        idx_pi = 0
                        idx_prop = get_idx(["mode"], cols)
                        idx_notes = get_idx(["comments"], cols)
                    else:
                        st.info("✅ FMList Export Format Detected & Mapped")
                        idx_freq = get_idx(["freq", "mhz"], cols)
                        idx_call = get_idx(["call", "station", "program"], cols)
                        idx_date = get_idx(["date"], cols)
                        idx_time = get_idx(["time", "utc"], cols)
                        idx_city = get_idx(["city", "loc"], cols)
                        idx_state = get_idx(["state", "reg"], cols)
                        idx_ctry = get_idx(["itu", "countr"], cols)
                        idx_dist = get_idx(["qrb", "dist", "mi", "km"], cols)
                        idx_pi = get_idx(["pi"], cols)
                        idx_prop = get_idx(["propa", "mode"], cols)
                        idx_notes = get_idx(["remarks", "detail", "info", "comment"], cols)
                    
                    c_i1, c_i2, c_i3, c_i4 = st.columns(4)
                    map_freq = c_i1.selectbox("FREQUENCY", cols, index=idx_freq, key="fm_map_1")
                    map_call = c_i2.selectbox("CALLSIGN", cols, index=idx_call, key="fm_map_2")
                    map_date = c_i3.selectbox("DATE (UTC)", cols, index=idx_date, key="fm_map_3")
                    map_time = c_i4.selectbox("TIME (UTC)", cols, index=idx_time, key="fm_map_4")
                    
                    c_i5, c_i6, c_i7, c_i8 = st.columns(4)
                    map_city = c_i5.selectbox("CITY", cols, index=idx_city, key="fm_map_5")
                    map_state = c_i6.selectbox("STATE", cols, index=idx_state, key="fm_map_6")
                    map_ctry = c_i7.selectbox("COUNTRY / ITU", cols, index=idx_ctry, key="fm_map_7")
                    map_dist = c_i8.selectbox("DISTANCE", cols, index=idx_dist, key="fm_map_10")
                    
                    c_i9, c_i10, c_i11 = st.columns(3)
                    map_pi = c_i9.selectbox("PI CODE", cols, index=idx_pi, key="fm_map_8")
                    map_prop = c_i10.selectbox("PROPAGATION", cols, index=idx_prop, key="fm_map_9")
                    map_notes = c_i11.selectbox("NOTES / DETAILS", cols, index=idx_notes, key="fm_map_11")
                    
                    map_sdr = c_i11.selectbox("SDR USED?", cols, index=0, key="fm_map_12")
                    
                    st.markdown("#### DEFAULT SDR STATUS")
                    st.caption("If a log has no mapped SDR status, apply this global default.")
                    def_sdr = st.radio("SDR Used Default", ["Yes", "No"], horizontal=True, key="fm_def_sdr")
                    
                    if st.button("> PROCESS & TRANSMIT BULK PAYLOAD", key="fm_bulk_btn"):
                        sheet = get_gsheet()
                        if sheet is None: 
                            st.error("🚨 DATALINK OFFLINE. Streamlit Secrets not configured.")
                        else:
                            bulk_rows = []
                            op = st.session_state.operator_profile
                            entry_cat_val = f"ROVER ({rover_grid})" if r_cat == "ROVER" and rover_grid else r_cat
                            
                            vals = sheet.get_all_values()
                            existing_signatures = set()
                            op_name_upper = op.get('name', '').strip().upper()
                            if len(vals) > 1:
                                for r in vals[1:]:
                                    if len(r) >= 16:
                                        r_name = str(r[0]).strip().upper()
                                        if r_name != op_name_upper: 
                                            continue
                                        r_band = str(r[4]).strip().upper()
                                        r_freq_raw = str(r[5]).strip() if r_band == "AM" else str(r[6]).strip()
                                        try:
                                            r_freq = str(float(r_freq_raw.replace(',', '.')))
                                        except Exception:
                                            r_freq = r_freq_raw
                                        r_call = str(r[7]).strip().upper()
                                        r_date = str(r[14]).strip()
                                        r_time = str(r[15]).strip()
                                        existing_signatures.add(f"{r_band}_{r_freq}_{r_call}_{r_date}_{r_time}")
                            
                            # --- TEMPORAL SCRUBBER ---
                            with st.spinner("Scanning payload against temporal mission parameters..."):
                                valid_df, skipped_out_of_range = filter_bulk_dataframe(df_import, date_col=map_date, time_col=map_time)
                            
                            if valid_df.empty:
                                if skipped_out_of_range > 0:
                                    st.error(f"❌ **INFILTRATION FAILED:** All {skipped_out_of_range} intercepts were rejected for falling outside the authorized DEFCON 6 operational window (May 2 - Aug 31).")
                                else:
                                    st.error("❌ **INFILTRATION FAILED:** No valid intercepts found.")
                            else:
                                skipped_dupes = 0
                                
                                for _, row in valid_df.iterrows():
                                    raw_freq = row[map_freq] if map_freq != "<Skip>" else ""
                                    
                                    if raw_freq:
                                        try:
                                            f_val = float(str(raw_freq).replace(',', '.').strip())
                                            if f_val < 87.0 or f_val > 108.0: 
                                                continue 
                                        except Exception: 
                                            pass
                                            
                                    raw_country = str(row[map_ctry]).strip() if map_ctry != "<Skip>" and not pd.isna(row[map_ctry]) else "USA"
                                    clean_country = itu_map.get(raw_country.upper(), raw_country.title())
                                    if clean_country.upper() in ["USA", "UNITED STATES"]: 
                                        clean_country = "United States"
                                    
                                    raw_call = row[map_call] if map_call != "<Skip>" else ""
                                    clean_call = clean_callsign(raw_call)
                                    clean_call = standardize_cuban_station(clean_call, raw_freq, clean_country)
                                    
                                    dist_val = 0.0
                                    if map_dist != "<Skip>":
                                        raw_dist = str(row[map_dist]).lower()
                                        try:
                                            clean_dist = float(raw_dist.replace('km', '').replace('mi', '').replace(',', '').strip())
                                            if "km" in raw_dist or "qrb" in str(map_dist).lower(): 
                                                dist_val = clean_dist * 0.621371
                                            else: 
                                                dist_val = clean_dist
                                        except Exception: 
                                            dist_val = 0.0
                                            
                                    clean_state = row[map_state] if map_state != "<Skip>" else ""
                                    if clean_country not in ["United States", "Canada", "Mexico"]: 
                                        clean_state = "DX"
                                    
                                    clean_city = str(row[map_city]).strip() if map_city != "<Skip>" and not pd.isna(row[map_city]) else ""
                                    station_grid = ""
                                    station_county = " - " if clean_country not in ["United States"] else ""
                                    
                                    # EXPLICIT FM TRIPLE-TRACK MATCHING ENGINE
                                    if not fm_db.empty and raw_freq:
                                        try:
                                            f_val = float(str(raw_freq).replace(',', '.'))
                                            
                                            match_df = fm_db[(pd.to_numeric(fm_db['Frequency'], errors='coerce') >= f_val - 0.05) & 
                                                             (pd.to_numeric(fm_db['Frequency'], errors='coerce') <= f_val + 0.05)]
                                                             
                                            for _, m_row in match_df.iterrows():
                                                db_call = super_clean(m_row['Callsign'])
                                                db_slogan = super_clean(m_row.get('Slogan', ''))
                                                db_city = simplify_string(m_row.get('City', ''))
                                                db_country = simplify_string(m_row.get('Country', 'United States'))
                                                
                                                is_match = False
                                                
                                                imp_call = super_clean(clean_callsign(raw_call))
                                                imp_country = simplify_string(clean_country)
                                                imp_city = simplify_string(clean_city)
                                                
                                                # Track 1: Standard Callsign Match
                                                if imp_call and db_call and imp_call != "UNKNOWN" and db_call != "UNKNOWN" and (imp_call in db_call or db_call in imp_call): 
                                                    is_match = True
                                                    
                                                # Track 2: City + Country Match
                                                elif imp_city and db_city and imp_city != "UNKNOWN" and db_city != "UNKNOWN" and (imp_city in db_city or db_city in imp_city) and imp_country == db_country:
                                                    is_match = True
                                                    
                                                # Track 3: Slogan Match
                                                elif imp_call and db_slogan and imp_call != "UNKNOWN" and db_slogan != "UNKNOWN" and (imp_call in db_slogan or db_slogan in imp_call):
                                                    is_match = True
                                                        
                                                if is_match:
                                                    station_county = m_row['County']
                                                    station_grid = m_row['Grid']
                                                    clean_call = m_row['Callsign']   
                                                    clean_city = m_row['City']       
                                                    clean_state = m_row['State']  
                                                    clean_country = m_row.get('Country', clean_country)   
                                                    break
                                        except Exception: 
                                            pass

                                    try:
                                        sig_freq = str(float(str(raw_freq).replace(',', '.')))
                                    except Exception:
                                        sig_freq = str(raw_freq).strip()
                                        
                                    call_sig = str(clean_call).strip().upper()
                                    date_sig = str(format_date_import(row[map_date])).strip()
                                    time_sig = str(format_time_import(row[map_time])).strip()
                                    
                                    row_sig = f"FM_{sig_freq}_{call_sig}_{date_sig}_{time_sig}"
                                    if row_sig in existing_signatures:
                                        skipped_dupes += 1
                                        continue
                                    existing_signatures.add(row_sig)
                                    
                                    rds_val = "No"
                                    pi_val = str(row[map_pi]).strip().upper() if map_pi != "<Skip>" and not pd.isna(row[map_pi]) else ""
                                    
                                    if pi_val != "" and pi_val not in ["NONE", "0", "0000"]:
                                        rds_val = "Yes"
                                        
                                    map_notes_val = str(row[map_notes]).strip() if map_notes != "<Skip>" and not pd.isna(row[map_notes]) else ""
                                    if "pi logged" in map_notes_val.lower():
                                        rds_val = "Yes"
                                        if not pi_val:
                                            pi_match = re.search(r'pi logged:\s*([A-F0-9]{4})', map_notes_val, re.IGNORECASE)
                                            if pi_match:
                                                pi_val = pi_match.group(1).upper()
                                    
                                    sdr_val = str(row[map_sdr]).strip().title() if map_sdr != "<Skip>" and not pd.isna(row[map_sdr]) else def_sdr
                                    if sdr_val not in ["Yes", "No"]: 
                                        sdr_val = def_sdr 

                                    r_data = [
                                        op.get('name', ''), 
                                        op.get('city', ''), 
                                        op.get('state', ''), 
                                        op.get('country', ''),
                                        "FM", 
                                        "", 
                                        raw_freq, 
                                        clean_call, 
                                        "", 
                                        clean_city, 
                                        clean_state, 
                                        clean_country, 
                                        "", 
                                        station_grid,
                                        date_sig, 
                                        time_sig, 
                                        round(dist_val, 1), 
                                        map_notes_val, 
                                        rds_val, 
                                        pi_val, 
                                        map_fm_prop(row[map_prop]) if map_prop != "<Skip>" else "Other", 
                                        station_county, 
                                        entry_cat_val, 
                                        "", 
                                        "",
                                        sdr_val
                                    ]
                                    bulk_rows.append(["" if pd.isna(item) else (item.item() if hasattr(item, 'item') else item) for item in r_data])
                                    
                                try:
                                    sheet.append_rows(bulk_rows)
                                    # Force cache clear 
                                    try:
                                        get_full_logs_df.clear()
                                        get_logged_dict.clear()
                                    except Exception: pass
                                    
                                    st.success(f"### [ {len(bulk_rows)} RECORDS TRANSMITTED ]")
                                    if skipped_dupes > 0:
                                        st.info(f"### [ {skipped_dupes} DUPLICATES IGNORED ]")
                                    if skipped_out_of_range > 0:
                                        st.warning(f"### [ {skipped_out_of_range} LOGS OUTSIDE WINDOW (May 1 - Aug 31) PURGED ]")
                                    st.balloons()
                                    
                                except Exception as e: 
                                    st.error(f"BULK FAILED: {e}")
                except Exception as e: 
                    st.error(f"FILE PARSING ERROR: {e}")

        st.markdown("#### 3. TIME SYNCHRONIZATION")
        log_mode = st.radio("LOGGING MODE", ["LIVE DX (AUTO-CLOCK)", "IQ RECORDING (STICKY MEMORY)"], horizontal=True, key="fm_log_mode", label_visibility="collapsed")

        st.markdown("#### 4. SUBMIT INTERCEPT")
        with st.form("fm_submit_form", clear_on_submit=True):
            col_s1, col_s2, col_s3 = st.columns(3)
            now = datetime.datetime.now(datetime.timezone.utc)
            
            def_date = now.date() if "LIVE" in log_mode else st.session_state.iq_date
            def_time = now.strftime("%H%M") if "LIVE" in log_mode else st.session_state.iq_time
            
            log_date = col_s1.date_input("DATE (UTC)", value=def_date, key="fm_dt")
            log_time = col_s2.text_input("TIME (UTC)", value=def_time, key="fm_tm")
            log_prop = col_s3.selectbox("PROPAGATION MODE", ["Tropo", "Sporadic E", "Meteor Scatter", "Aurora", "Local"])
            
            c_p1, c_p2, c_p3 = st.columns(3)
            log_rds = c_p1.selectbox("RDS DECODE?", ["No", "Yes"])
            default_pi = target_data["pi"] if "pi" in target_data else ""
            log_pi = c_p2.text_input("PI CODE", value=default_pi)
            
            if "sdr" in target_data:
                log_sdr = target_data["sdr"]
            else:
                log_sdr = c_p3.selectbox("RECEPTION VIA SDR?", ["Yes", "No"], index=0, key="fm_man_sdr")
                
            log_notes = st.text_area("PROGRAMMING / INTERCEPT NOTES", key="fm_nts")
            
            submit_log = st.form_submit_button("> TRANSMIT REPORT TO SERVER")
            if submit_log:
                # Instantly save the submitted date/time to memory so it sticks for the next record
                st.session_state.iq_date = log_date
                st.session_state.iq_time = log_time
                
                if not target_data: 
                    st.error("TARGET NOT ACQUIRED. SELECT OR ENTER A STATION.")
                elif not is_reception_valid(log_date.strftime("%Y-%m-%d"), log_time):
                    st.error("🚨 TRANSMISSION REJECTED: Intercept date falls outside the authorized DEFCON 6 window (May 2 - Aug 31 UTC). Please verify your log and try again.")
                else:
                    sheet = get_gsheet()
                    if sheet is None: 
                        st.error("🚨 TRANSMISSION FAILED: Streamlit Secrets are not configured.")
                    else:
                        try:
                            op = st.session_state.operator_profile
                            entry_cat_val = f"ROVER ({rover_grid})" if r_cat == "ROVER" and rover_grid else r_cat
                            
                            row_data = [
                                op.get('name', ''), 
                                op.get('city', ''), 
                                op.get('state', ''), 
                                op.get('country', ''),
                                "FM", 
                                "", 
                                target_data.get("freq", ""), 
                                target_data.get("call", ""), 
                                "", 
                                target_data.get("city", ""),
                                target_data.get("state", ""), 
                                target_data.get("country", ""), 
                                "", 
                                target_data.get("grid", ""),
                                log_date.strftime("%m/%d/%Y"), 
                                log_time, 
                                target_data.get("dist", 0.0), 
                                log_notes, 
                                log_rds, 
                                log_pi, 
                                log_prop, 
                                target_data.get("county", ""), 
                                entry_cat_val, 
                                "", 
                                "",
                                log_sdr
                            ]
                            sheet.append_row(["" if pd.isna(item) else (item.item() if hasattr(item, 'item') else item) for item in row_data])
                            
                            # Force cache clear
                            try:
                                get_full_logs_df.clear()
                                get_logged_dict.clear()
                            except Exception: pass
                            
                            st.markdown("### [ TRANSMISSION SUCCESSFUL ]")
                            st.balloons()
                            
                        except Exception as e: 
                            st.error(f"FAILED: {e}")

    # --- 8D. NWR INTERCEPT ROOM ---
    elif st.session_state.sys_state == "NWR_LOG":
        if not is_terminal_open():
            st.error("🔒 **UPLINK SEVERED: THE TERMINAL IS CURRENTLY LOCKED.**")
            st.warning("Data submission is only authorized between 2300 UTC May 1, 2026 and 2359 UTC September 30, 2026. You may continue to view the Dashboard and Intelligence Ledgers.")
            st.stop()
            
        st.markdown("### [ NOAA WEATHER RADIO (NWR) CONSOLE ACTIVE ]")
        st.markdown("#### 1. OPERATING PARAMETERS")
        r_cat = st.radio("CATEGORY", ["HOME QTH", "ROVER"], horizontal=True, label_visibility="collapsed", key="nwr_cat")
        rover_grid = ""
        
        active_lat = float(st.session_state.operator_profile.get('lat', 0.0))
        active_lon = float(st.session_state.operator_profile.get('lon', 0.0))
        
        if r_cat == "ROVER":
            st.warning("ROVER MODE: ENTER CURRENT MAIDENHEAD GRID TO CALIBRATE DISTANCE.")
            rover_grid = st.text_input("ROVER GRID (e.g., EM40)", key="nwr_rov")
            if len(rover_grid) >= 4:
                try:
                    r_lat, r_lon = mh.to_location(rover_grid)
                    active_lat = float(r_lat)
                    active_lon = float(r_lon)
                except Exception: 
                    pass
                    
        st.markdown("#### 2. TARGET ACQUISITION")
        tab_search, tab_manual, tab_import = st.tabs(["[ DATABASE SEARCH ]", "[ MANUAL ENTRY ]", "[ BULK IMPORT ]"])
        target_data = {}
        
        with tab_search:
            st.write("ACCESSING NWS DATABANKS...")
            if nwr_db.empty: 
                st.error("[ SYSTEM ALERT ] DATABANK OFFLINE: NWR database not found.")
            else:
                # --- NEW TACTICAL RADAR VIEW TOGGLE ---
                view_mode = st.radio("DISPLAY INTERFACE", ["[ DATABANK VIEW ]", "[ TACTICAL MAP VIEW ]"], horizontal=True, label_visibility="collapsed")
                st.markdown("<hr style='border: 1px dashed #139a9b; opacity: 0.3; margin-top: 5px; margin-bottom: 20px;'>", unsafe_allow_html=True)
                
                if 'nwr_filter_key' not in st.session_state: 
                    st.session_state.nwr_filter_key = 0
                    
                def reset_nwr_filters(): 
                    st.session_state.nwr_filter_key += 1
                
                c_btn1, c_btn2 = st.columns([1.5, 3.5])
                c_btn1.button("[ RESET FILTERS ]", on_click=reset_nwr_filters, key="nwr_reset")
                if c_btn2.button("[ REFRESH STATION DATA ]", key="sync_nwr"):
                    get_logged_dict.clear()
                    load_nwr_intel.clear()
                    st.rerun()
                
                fk = st.session_state.nwr_filter_key
                
                # --- UNIVERSAL FILTERS (APPLIES TO BOTH VIEWS) ---
                c1, c2, c3, c4 = st.columns(4)
                
                all_freqs = sorted([str(x) for x in nwr_db['Frequency'].dropna().unique()])
                nwr_states = sorted([str(x) for x in nwr_db['State'].dropna().unique()])
                nwr_wfos = sorted([str(x) for x in nwr_db['WFO'].dropna().unique()]) if 'WFO' in nwr_db.columns else []
                
                f_freq = c1.selectbox("FREQ (MHz)", ["All"] + all_freqs, key=f"nwr_f1_{fk}")
                f_state = c2.selectbox("STATE", ["All"] + nwr_states, key=f"nwr_f4_{fk}")
                
                if nwr_wfos:
                    f_wfo = c3.selectbox("WFO", ["All"] + nwr_wfos, key=f"nwr_wfo_{fk}")
                else:
                    f_ctry = c3.selectbox("COUNTRY", ["All", "United States", "Canada", "Other"], key=f"nwr_ctry_{fk}")
                    f_wfo = "All"
                    
                f_status = c4.selectbox("STATUS", ["All", "Logged Only", "Not Logged Only"], key=f"nwr_f8_{fk}")
                
                # Execute primary filtering
                results = nwr_db.copy()
                
                # Clean LAT/LON data for map engine stability
                if 'LAT' in results.columns and 'LON' in results.columns:
                    results['LAT'] = pd.to_numeric(results['LAT'], errors='coerce')
                    results['LON'] = pd.to_numeric(results['LON'], errors='coerce')
                
                if f_freq != "All": 
                    results = results[results['Frequency'] == float(f_freq)]
                if f_state != "All": 
                    results = results[results['State'] == f_state]
                if f_wfo != "All" and 'WFO' in results.columns: 
                    results = results[results['WFO'] == f_wfo]
                
                # Calculate Logged Status dynamically against user's history
                logged_dict = get_logged_dict(st.session_state.operator_profile.get('name', ''), "NWR")
                results['Is_Logged'] = results.apply(lambda r: check_is_logged_fm(r['Frequency'], r['Callsign'], r.get('Slogan', ''), r['City'], r['State'], r['Country'] if 'Country' in r else 'United States', logged_dict), axis=1)
                
                if f_status == "Logged Only": 
                    results = results[results['Is_Logged']]
                    st.markdown("<div style='font-size: 0.9rem; color: #1bd2d4; opacity: 0.7; margin-top: -15px; margin-bottom: 10px;'>*To export your logs to a CSV, choose 'Logged Only' from the status filter.*</div>", unsafe_allow_html=True)
                    full_logs_df = get_full_logs_df(st.session_state.operator_profile.get('name', ''), "NWR")
                    if not full_logs_df.empty:
                        csv_data = full_logs_df.to_csv(index=False).encode('utf-8')
                        st.download_button(label="📥 DOWNLOAD MY LOGS (CSV)", data=csv_data, file_name=f"My_NWR_Logs_{datetime.date.today().strftime('%Y%m%d')}.csv", mime="text/csv")
                elif f_status == "Not Logged Only": 
                    results = results[~results['Is_Logged']]
                    st.markdown("<div style='font-size: 0.9rem; color: #1bd2d4; opacity: 0.7; margin-top: -15px; margin-bottom: 10px;'>*To export your logs to a CSV, choose 'Logged Only' from the status filter.*</div>", unsafe_allow_html=True)
                else:
                    st.markdown("<div style='font-size: 0.9rem; color: #1bd2d4; opacity: 0.7; margin-top: -15px; margin-bottom: 10px;'>*To export your logs to a CSV, choose 'Logged Only' from the status filter.*</div>", unsafe_allow_html=True)

                # ==========================================
                # ROUTE 1: TACTICAL MAP VIEW
                # ==========================================
                if view_mode == "[ TACTICAL MAP VIEW ]":
                    st.markdown("<div style='font-size: 0.9rem; color: #1bd2d4; opacity: 0.7; margin-bottom: 10px;'>*Geospatial Array Active. Hover over a target to view telemetry.*</div>", unsafe_allow_html=True)
                    
                    # Strip null coordinate rows to prevent map crashing
                    map_results = results.dropna(subset=['LAT', 'LON'])
                    map_results = map_results[(map_results['LAT'] != 0.0) & (map_results['LON'] != 0.0)]
                    
                    if not map_results.empty:
                        # US States Borders Layer (Transparent fill, Cyan borders)
                        state_borders = pdk.Layer(
                            "GeoJsonLayer",
                            "https://raw.githubusercontent.com/PublicaMundi/MappingAPI/master/data/geojson/us-states.json",
                            opacity=0.4,
                            stroked=True,
                            filled=False,
                            get_line_color=[19, 154, 155, 200],  # DX Central Cyan
                            get_line_width=3000,  # Line width in meters
                            pickable=False
                        )
                        
                        # Station Data Layer
                        station_layer = pdk.Layer(
                            "ScatterplotLayer",
                            data=map_results,
                            get_position=["LON", "LAT"],
                            get_color="[27, 210, 212, 180]", # DX Radio Cyan
                            get_radius=15000, # 15km radius
                            pickable=True,
                            auto_highlight=True
                        )
                        
                        cam_lat = active_lat if active_lat != 0.0 else 39.8283
                        cam_lon = active_lon if active_lon != 0.0 else -98.5795
                        view_state = pdk.ViewState(latitude=cam_lat, longitude=cam_lon, zoom=4, pitch=0)
                        
                        tooltip_html = "<b>{Callsign}</b> - {Frequency} MHz<br/>{City}, {State}"
                        if 'WFO' in map_results.columns:
                            tooltip_html += "<br/><b>WFO:</b> {WFO}"
                            
                        st.pydeck_chart(pdk.Deck(
                            map_style="mapbox://styles/mapbox/dark-v10",
                            layers=[state_borders, station_layer],
                            initial_view_state=view_state,
                            tooltip={
                                "html": tooltip_html,
                                "style": {
                                    "backgroundColor": "#050505",
                                    "color": "#1bd2d4",
                                    "border": "1px solid #139a9b",
                                    "fontFamily": "monospace"
                                }
                            }
                        ))
                    else:
                        st.warning("NO TARGETS FOUND TO PLOT ON RADAR.")

                # ==========================================
                # ROUTE 2: STANDARD DATABANK VIEW
                # ==========================================
                else:
                    # Specific text filters only needed for the table view
                    c5, c6, c7 = st.columns(3)
                    f_call = c5.text_input("CALLSIGN FILTER", key=f"nwr_f2_{fk}")
                    f_city = c6.text_input("CITY FILTER", key=f"nwr_f3_{fk}")
                    f_grid = c7.text_input("GRID FILTER", key=f"nwr_f7_{fk}")
                    
                    if f_call: 
                        c_simp = simplify_string(f_call)
                        results = results[results['Callsign'].apply(lambda x: c_simp in simplify_string(x))]
                    if f_city: 
                        results = results[results['City'].str.contains(f_city, case=False, na=False)]
                    if f_grid: 
                        results = results[results['Grid'].str.contains(f_grid.upper(), na=False)]
                        
                    st.write(f"> {len(results)} TARGETS FOUND:")
                    st.markdown("<div style='font-size: 0.9rem; color: #1bd2d4; opacity: 0.7; margin-top: -15px; margin-bottom: 10px;'>*Source: Weather.gov (NWR)*</div>", unsafe_allow_html=True)
                    
                    if not results.empty:
                        # Geocode missing values for top 100
                        if len(results) <= 100:
                            for idx, r in results.iterrows():
                                if float(r.get('LAT', 0.0)) == 0.0 and float(r.get('LON', 0.0)) == 0.0:
                                    lat, lon = get_lat_lon_from_city(r['City'], r.get('Country', 'United States'))
                                    results.at[idx, 'LAT'] = lat
                                    results.at[idx, 'LON'] = lon
                                    
                        results['Dist'] = results.apply(lambda r: calculate_distance(active_lat, active_lon, r.get('LAT'), r.get('LON')), axis=1)
                        
                        if active_lat != 0.0 and active_lon != 0.0:
                            results = results[results['Dist'] > 0.0]
                            
                        results = results.sort_values(by='Dist', ascending=True)
                        results['Display Call'] = results.apply(lambda r: f"🟢 {r['Callsign']}" if r['Is_Logged'] else r['Callsign'], axis=1)
                        results.insert(0, 'Log?', False)
                        
                        view_df = results[['Log?', 'Frequency', 'Display Call', 'City', 'State', 'Country', 'Dist', 'Grid', 'County', 'Callsign']]
                        edited_df = st.data_editor(
                            view_df, 
                            hide_index=True, 
                            use_container_width=True,
                            column_config={
                                "Log?": st.column_config.CheckboxColumn("Log?"), 
                                "Dist": st.column_config.NumberColumn("Dist (mi)", format="%.1f"),
                                "County": "County/Parish",
                                "Callsign": None
                            },
                            disabled=['Frequency', 'Display Call', 'City', 'State', 'Country', 'Dist', 'Grid', 'County', 'Callsign'], 
                            key=f"nwr_db_editor_{fk}"
                        )
                        
                        selected_rows = edited_df[edited_df['Log?'] == True]
                        if not selected_rows.empty:
                            target = selected_rows.iloc[0]
                            grid_str = f" | Grid: {target['Grid']}" if target['Grid'] else ""
                            dist_str = f" | {target['Dist']} mi" if target['Dist'] > 0 else ""
                            
                            c_str = target.get('County', '')
                            county_str = f" - {c_str} County" if c_str and c_str not in ["Unknown", " - "] else ""
                            
                            st.success(f"TARGET LOCKED: {target['Callsign']} ({target['City']}, {target['State']}{county_str} - {target.get('Country', 'United States')}{grid_str}{dist_str})")
                            target_data = {
                                "freq": target['Frequency'], 
                                "call": target['Callsign'], 
                                "city": target['City'], 
                                "state": target['State'], 
                                "county": target.get('County', 'Unknown'), 
                                "country": target.get('Country', 'United States'), 
                                "grid": target['Grid'], 
                                "pi": "", 
                                "dist": target['Dist']
                            }
                            
                            st.markdown("#### RECEPTION VIA SDR?")
                            sdr_choice_db = st.radio("SDR Used?", ["Yes", "No"], horizontal=True, key=f"nwr_sdr_db_{fk}")
                            target_data["sdr"] = sdr_choice_db

        with tab_manual:
            st.write("INITIATE UNLISTED PROTOCOL...")
            c_m1, c_m2, c_m3 = st.columns(3)
            man_freq = c_m1.number_input("MANUAL FREQ (MHz)", min_value=162.400, max_value=162.550, value=162.400, step=0.025, key="man_nwr")
            man_call = c_m2.text_input("STATION ID", key="man_nwr_call")
            
            all_db_countries_nwr = sorted([str(x) for x in nwr_db['Country'].dropna().unique()]) if not nwr_db.empty else ["United States"]
            if "Other" not in all_db_countries_nwr: 
                all_db_countries_nwr.append("Other")
            def_idx = all_db_countries_nwr.index("United States") if "United States" in all_db_countries_nwr else 0
            man_ctry = c_m3.selectbox("COUNTRY", all_db_countries_nwr, index=def_idx, key="man_nwr_ctry")
            man_other = st.text_input("SPECIFY COUNTRY:") if man_ctry == "Other" else ""
            
            c_m4, c_m5, c_m6 = st.columns(3)
            man_city = c_m4.text_input("CITY", key="nwr_man_cty")
            man_sp = c_m5.selectbox("STATE/PROV", get_state_list(man_ctry), key="nwr_sp")
            man_dist = c_m6.number_input("DIST (MILES)", min_value=0.0, step=1.0, key="nwr_dist")
            
            if man_call: 
                selected_country = man_other if man_ctry == "Other" else man_ctry
                target_data = {
                    "freq": man_freq, 
                    "call": standardize_cuban_station(man_call, man_freq, selected_country), 
                    "city": man_city, 
                    "state": man_sp, 
                    "county": " - " if selected_country not in ["United States"] else "", 
                    "country": selected_country, 
                    "grid": "", 
                    "pi": "", 
                    "dist": man_dist
                }

        with tab_import:
            st.write("INITIATE BULK INGESTION PROTOCOL...")
            uploaded_file = st.file_uploader("UPLOAD CSV/TSV PAYLOAD", type=["csv", "txt", "tsv"], key="nwr_bulk")
            
            if uploaded_file is not None:
                try:
                    df_import = handle_fm_file_upload(uploaded_file)
                    st.write(f"DETECTED {len(df_import)} RECORDS. PREVIEW:")
                    st.dataframe(df_import.head(5), use_container_width=True)
                    st.markdown("#### MAP DATABANK COLUMNS")
                    cols = ["<Skip>"] + df_import.columns.tolist()
                    cols_lower = [str(c).lower() for c in cols]
                    
                    is_wlogger = False
                    if any("timestamp" in c for c in cols_lower) and any("mode" in c for c in cols_lower):
                        is_wlogger = True
                    
                    if is_wlogger:
                        st.success("✅ WLogger Export Format Detected & Mapped")
                        idx_freq = get_idx(["frequency"], cols)
                        idx_call = get_idx(["callsign", "call"], cols)
                        idx_date = get_idx(["timestamp"], cols)
                        idx_time = get_idx(["timestamp"], cols)
                        idx_city = get_idx(["city"], cols)
                        idx_state = get_idx(["state"], cols)
                        idx_ctry = 0
                        idx_dist = get_idx(["distance"], cols)
                        idx_pi = 0
                        idx_prop = get_idx(["mode"], cols)
                        idx_notes = get_idx(["comments"], cols)
                    else:
                        st.info("✅ FMList Export Format Detected & Mapped")
                        idx_freq = get_idx(["freq", "mhz"], cols)
                        idx_call = get_idx(["call", "station", "program"], cols)
                        idx_date = get_idx(["date"], cols)
                        idx_time = get_idx(["time", "utc"], cols)
                        idx_city = get_idx(["city", "loc"], cols)
                        idx_state = get_idx(["state", "reg"], cols)
                        idx_ctry = get_idx(["itu", "countr"], cols)
                        idx_dist = get_idx(["qrb", "dist", "mi", "km"], cols)
                        idx_pi = get_idx(["pi"], cols)
                        idx_prop = get_idx(["propa", "mode"], cols)
                        idx_notes = get_idx(["remarks", "detail", "info", "comment"], cols)
                    
                    c_i1, c_i2, c_i3, c_i4 = st.columns(4)
                    map_freq = c_i1.selectbox("FREQUENCY", cols, index=idx_freq, key="nwr_map_1")
                    map_call = c_i2.selectbox("CALLSIGN", cols, index=idx_call, key="nwr_map_2")
                    map_date = c_i3.selectbox("DATE (UTC)", cols, index=idx_date, key="nwr_map_3")
                    map_time = c_i4.selectbox("TIME (UTC)", cols, index=idx_time, key="nwr_map_4")
                    
                    c_i5, c_i6, c_i7, c_i8 = st.columns(4)
                    map_city = c_i5.selectbox("CITY", cols, index=idx_city, key="nwr_map_5")
                    map_state = c_i6.selectbox("STATE", cols, index=idx_state, key="nwr_map_6")
                    map_ctry = c_i7.selectbox("COUNTRY / ITU", cols, index=idx_ctry, key="nwr_map_7")
                    map_dist = c_i8.selectbox("DISTANCE", cols, index=idx_dist, key="nwr_map_10")
                    
                    c_i9, c_i10, c_i11 = st.columns(3)
                    map_pi = c_i9.selectbox("PI CODE", cols, index=idx_pi, key="nwr_map_8")
                    map_prop = c_i10.selectbox("PROPAGATION", cols, index=idx_prop, key="nwr_map_9")
                    map_notes = c_i11.selectbox("NOTES / DETAILS", cols, index=idx_notes, key="nwr_map_11")
                    
                    map_sdr = c_i11.selectbox("SDR USED?", cols, index=0, key="nwr_map_12")
                    
                    st.markdown("#### DEFAULT SDR STATUS")
                    st.caption("If a log has no mapped SDR status, apply this global default.")
                    def_sdr = st.radio("SDR Used Default", ["Yes", "No"], horizontal=True, key="nwr_def_sdr")
                    
                    if st.button("> PROCESS & TRANSMIT BULK PAYLOAD", key="nwr_bulk_btn"):
                        sheet = get_gsheet()
                        if sheet is None: 
                            st.error("🚨 DATALINK OFFLINE. Streamlit Secrets not configured.")
                        else:
                            bulk_rows = []
                            op = st.session_state.operator_profile
                            entry_cat_val = f"ROVER ({rover_grid})" if r_cat == "ROVER" and rover_grid else r_cat
                            
                            vals = sheet.get_all_values()
                            existing_signatures = set()
                            op_name_upper = op.get('name', '').strip().upper()
                            if len(vals) > 1:
                                for r in vals[1:]:
                                    if len(r) >= 16:
                                        r_name = str(r[0]).strip().upper()
                                        if r_name != op_name_upper: 
                                            continue
                                        r_band = str(r[4]).strip().upper()
                                        r_freq_raw = str(r[5]).strip() if r_band == "AM" else str(r[6]).strip()
                                        try:
                                            r_freq = str(float(r_freq_raw.replace(',', '.')))
                                        except Exception:
                                            r_freq = r_freq_raw
                                        r_call = str(r[7]).strip().upper()
                                        r_date = str(r[14]).strip()
                                        r_time = str(r[15]).strip()
                                        existing_signatures.add(f"{r_band}_{r_freq}_{r_call}_{r_date}_{r_time}")
                            
                            # --- TEMPORAL SCRUBBER ---
                            with st.spinner("Scanning payload against temporal mission parameters..."):
                                valid_df, skipped_out_of_range = filter_bulk_dataframe(df_import, date_col=map_date, time_col=map_time)
                            
                            if valid_df.empty:
                                if skipped_out_of_range > 0:
                                    st.error(f"❌ **INFILTRATION FAILED:** All {skipped_out_of_range} intercepts were rejected for falling outside the authorized DEFCON 6 operational window (May 2 - Aug 31).")
                                else:
                                    st.error("❌ **INFILTRATION FAILED:** No valid intercepts found.")
                            else:
                                skipped_dupes = 0
                                
                                for _, row in valid_df.iterrows():
                                    raw_freq = row[map_freq] if map_freq != "<Skip>" else ""
                                    
                                    # Aggressive NWR Frequency Filter
                                    try:
                                        f_val = float(str(raw_freq).replace(',', '.'))
                                        if f_val < 162.0 or f_val > 163.0: 
                                            continue 
                                    except Exception: 
                                        continue
                                        
                                    raw_country = str(row[map_ctry]).strip() if map_ctry != "<Skip>" and not pd.isna(row[map_ctry]) else "USA"
                                    clean_country = itu_map.get(raw_country.upper(), raw_country.title())
                                    if clean_country.upper() in ["USA", "UNITED STATES"]: 
                                        clean_country = "United States"
                                    
                                    raw_call = row[map_call] if map_call != "<Skip>" else ""
                                    clean_call = clean_callsign(raw_call)
                                    clean_call = standardize_cuban_station(clean_call, raw_freq, clean_country)
                                    
                                    clean_state = row[map_state] if map_state != "<Skip>" else ""
                                    if clean_country not in ["United States", "Canada", "Mexico"]: 
                                        clean_state = "DX"
                                    
                                    clean_city = str(row[map_city]).strip() if map_city != "<Skip>" and not pd.isna(row[map_city]) else ""
                                    
                                    dist_val = 0.0
                                    if map_dist != "<Skip>":
                                        raw_dist = str(row[map_dist]).lower()
                                        try:
                                            clean_dist = float(raw_dist.replace('km', '').replace('mi', '').replace(',', '').strip())
                                            if "km" in raw_dist or "qrb" in str(map_dist).lower(): 
                                                dist_val = clean_dist * 0.621371
                                            else: 
                                                dist_val = clean_dist
                                        except Exception: 
                                            dist_val = 0.0
                                            
                                    rds_val = "No"
                                    pi_val = str(row[map_pi]).strip().upper() if map_pi != "<Skip>" and not pd.isna(row[map_pi]) else ""
                                    
                                    if pi_val != "" and pi_val not in ["NONE", "0", "0000"]:
                                        rds_val = "Yes"
                                        
                                    map_notes_val = str(row[map_notes]).strip() if map_notes != "<Skip>" and not pd.isna(row[map_notes]) else ""
                                    if "pi logged" in map_notes_val.lower():
                                        rds_val = "Yes"
                                        if not pi_val:
                                            pi_match = re.search(r'pi logged:\s*([A-F0-9]{4})', map_notes_val, re.IGNORECASE)
                                            if pi_match:
                                                pi_val = pi_match.group(1).upper()
                                    
                                    station_grid = ""
                                    station_county = " - " if clean_country not in ["United States"] else ""
                                    
                                    # EXPLICIT NWR TRIPLE-TRACK MATCHING ENGINE
                                    if not nwr_db.empty and raw_freq:
                                        try:
                                            f_val = float(str(raw_freq).replace(',', '.'))
                                            
                                            match_df = nwr_db[(pd.to_numeric(nwr_db['Frequency'], errors='coerce') >= f_val - 0.05) & 
                                                              (pd.to_numeric(nwr_db['Frequency'], errors='coerce') <= f_val + 0.05)]
                                                              
                                            for _, m_row in match_df.iterrows():
                                                db_call = super_clean(m_row['Callsign'])
                                                db_slogan = super_clean(m_row.get('Slogan', ''))
                                                db_city = simplify_string(m_row.get('City', ''))
                                                db_country = simplify_string(m_row.get('Country', 'United States'))
                                                
                                                is_match = False
                                                
                                                imp_call = super_clean(clean_callsign(raw_call))
                                                imp_country = simplify_string(clean_country)
                                                imp_city = simplify_string(clean_city)
                                                
                                                # Track 1: Standard Callsign Match
                                                if imp_call and db_call and imp_call != "UNKNOWN" and db_call != "UNKNOWN" and (imp_call in db_call or db_call in imp_call): 
                                                    is_match = True
                                                    
                                                # Track 2: City + Country Match
                                                elif imp_city and db_city and imp_city != "UNKNOWN" and db_city != "UNKNOWN" and (imp_city in db_city or db_city in imp_city) and imp_country == db_country:
                                                    is_match = True
                                                    
                                                # Track 3: Slogan Match
                                                elif imp_call and db_slogan and imp_call != "UNKNOWN" and db_slogan != "UNKNOWN" and (imp_call in db_slogan or db_slogan in imp_call):
                                                    is_match = True
                                                        
                                                if is_match:
                                                    station_county = m_row['County']
                                                    station_grid = m_row['Grid']
                                                    clean_call = m_row['Callsign']   
                                                    clean_city = m_row['City']       
                                                    clean_state = m_row['State']  
                                                    clean_country = m_row.get('Country', clean_country)   
                                                    break
                                        except Exception: 
                                            pass

                                    try:
                                        sig_freq = str(float(str(raw_freq).replace(',', '.')))
                                    except Exception:
                                        sig_freq = str(raw_freq).strip()
                                        
                                    call_sig = str(clean_call).strip().upper()
                                    date_sig = str(format_date_import(row[map_date])).strip()
                                    time_sig = str(format_time_import(row[map_time])).strip()
                                    
                                    row_sig = f"NWR_{sig_freq}_{call_sig}_{date_sig}_{time_sig}"
                                    if row_sig in existing_signatures:
                                        skipped_dupes += 1
                                        continue
                                    existing_signatures.add(row_sig)
                                    
                                    sdr_val = str(row[map_sdr]).strip().title() if map_sdr != "<Skip>" and not pd.isna(row[map_sdr]) else def_sdr
                                    if sdr_val not in ["Yes", "No"]: 
                                        sdr_val = def_sdr

                                    r_data = [
                                        op.get('name', ''), 
                                        op.get('city', ''), 
                                        op.get('state', ''), 
                                        op.get('country', ''),
                                        "NWR", 
                                        "", 
                                        raw_freq, 
                                        clean_call, 
                                        "", 
                                        clean_city, 
                                        clean_state, 
                                        clean_country, 
                                        "", 
                                        station_grid,
                                        format_date_import(row[map_date]) if map_date != "<Skip>" else "", 
                                        format_time_import(row[map_time]) if map_time != "<Skip>" else "", 
                                        round(dist_val, 1), 
                                        str(row[map_notes]).strip() if map_notes != "<Skip>" and not pd.isna(row[map_notes]) else "", 
                                        "", 
                                        "", 
                                        map_fm_prop(row[map_prop]) if map_prop != "<Skip>" else "Other", 
                                        station_county, 
                                        entry_cat_val, 
                                        "", 
                                        "",
                                        sdr_val
                                    ]
                                    bulk_rows.append(["" if pd.isna(item) else (item.item() if hasattr(item, 'item') else item) for item in r_data])
                                    
                                try:
                                    sheet.append_rows(bulk_rows)
                                    # Force cache clear 
                                    try:
                                        get_full_logs_df.clear()
                                        get_logged_dict.clear()
                                    except Exception: pass
                                    
                                    st.success(f"### [ {len(bulk_rows)} RECORDS TRANSMITTED ]")
                                    if skipped_dupes > 0:
                                        st.info(f"### [ {skipped_dupes} DUPLICATES IGNORED ]")
                                    if skipped_out_of_range > 0:
                                        st.warning(f"### [ {skipped_out_of_range} LOGS OUTSIDE WINDOW (May 1 - Aug 31) PURGED ]")
                                    st.balloons()
                                    
                                except Exception as e: 
                                    st.error(f"BULK FAILED: {e}")
                except Exception as e: 
                    st.error(f"FILE ERROR: {e}")

        st.markdown("#### 3. TIME SYNCHRONIZATION")
        log_mode = st.radio("LOGGING MODE", ["LIVE DX (AUTO-CLOCK)", "IQ RECORDING (STICKY MEMORY)"], horizontal=True, key="nwr_log_mode", label_visibility="collapsed")

        st.markdown("#### 4. SUBMIT INTERCEPT")
        with st.form("nwr_submit_form", clear_on_submit=True):
            col_s1, col_s2, col_s3 = st.columns(3)
            now = datetime.datetime.now(datetime.timezone.utc)
            
            def_date = now.date() if "LIVE" in log_mode else st.session_state.iq_date
            def_time = now.strftime("%H%M") if "LIVE" in log_mode else st.session_state.iq_time
            
            log_date = col_s1.date_input("DATE (UTC)", value=def_date, key="nwr_dt")
            log_time = col_s2.text_input("TIME (UTC)", value=def_time, key="nwr_tm")
            log_prop = col_s3.selectbox("PROPAGATION MODE", ["Tropo", "Sporadic E", "Meteor Scatter", "Aurora", "Local"], key="nwr_prop")
            
            if "sdr" in target_data:
                log_sdr = target_data["sdr"]
            else:
                log_sdr = st.selectbox("RECEPTION VIA SDR?", ["Yes", "No"], index=0, key="nwr_man_sdr")
                
            log_notes = st.text_area("PROGRAMMING / INTERCEPT NOTES", key="nwr_nts")
            
            submit_log = st.form_submit_button("> TRANSMIT REPORT TO SERVER")
            if submit_log:
                # Instantly save the submitted date/time to memory so it sticks for the next record
                st.session_state.iq_date = log_date
                st.session_state.iq_time = log_time
                
                if not target_data: 
                    st.error("TARGET NOT ACQUIRED. SELECT OR ENTER A STATION.")
                elif not is_reception_valid(log_date.strftime("%Y-%m-%d"), log_time):
                    st.error("🚨 TRANSMISSION REJECTED: Intercept date falls outside the authorized DEFCON 6 window (May 2 - Aug 31 UTC). Please verify your log and try again.")
                else:
                    sheet = get_gsheet()
                    if sheet is None: 
                        st.error("🚨 TRANSMISSION FAILED: Streamlit Secrets are not configured.")
                    else:
                        try:
                            op = st.session_state.operator_profile
                            entry_cat_val = f"ROVER ({rover_grid})" if r_cat == "ROVER" and rover_grid else r_cat
                            
                            row_data = [
                                op.get('name', ''), 
                                op.get('city', ''), 
                                op.get('state', ''), 
                                op.get('country', ''),
                                "NWR", 
                                "", 
                                target_data.get("freq", ""), 
                                target_data.get("call", ""), 
                                "", 
                                target_data.get("city", ""),
                                target_data.get("state", ""), 
                                target_data.get("country", ""), 
                                "", 
                                target_data.get("grid", ""),
                                log_date.strftime("%m/%d/%Y"), 
                                log_time, 
                                target_data.get("dist", 0.0), 
                                log_notes, 
                                "", 
                                "",
                                log_prop, 
                                target_data.get("county", ""), 
                                entry_cat_val, 
                                "", 
                                "",
                                log_sdr
                            ]
                            sheet.append_row(["" if pd.isna(item) else (item.item() if hasattr(item, 'item') else item) for item in row_data])
                            
                            # Force cache clear 
                            try:
                                get_full_logs_df.clear()
                                get_logged_dict.clear()
                            except Exception: pass
                            
                            st.markdown("### [ TRANSMISSION SUCCESSFUL ]")
                            st.balloons()
                            
                        except Exception as e: 
                            st.error(f"FAILED: {e}")

    # --- 8F. ENCRYPTED INTERCEPT REPORT (BOUNTY STUB) ---
    elif st.session_state.sys_state == "BOUNTY_HUNT":
        if BOUNTY_ACTIVE:
            render_bounty_module()
        else:
            st.warning("🚨 ENCRYPTED INTERCEPT MODULE OFFLINE. (Ensure modules/bounty.py is deployed).")

    # --- 8G. GLOBAL INTELLIGENCE (DASHBOARD STUB) ---
    elif st.session_state.sys_state == "DASHBOARD":
        render_dashboard()
