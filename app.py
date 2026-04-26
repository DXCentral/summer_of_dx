import streamlit as st
import pandas as pd
import datetime
import math
import json
import gspread
import maidenhead as mh
import io
import streamlit.components.v1 as components
from geopy.geocoders import Nominatim
from google.oauth2.service_account import Credentials
from streamlit_javascript import st_javascript

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
    background-color: #050505 !important;
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

# --- 4. GEOSPATIAL & MATH HELPERS ---
def calculate_distance(lat1, lon1, lat2, lon2):
    if pd.isna(lat1) or pd.isna(lon1) or pd.isna(lat2) or pd.isna(lon2):
        return 0.0
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return 0.0
        
    try:
        lat1 = float(lat1)
        lon1 = float(lon1)
        lat2 = float(lat2)
        lon2 = float(lon2)
        
        if lat1 == 0.0 and lon1 == 0.0:
            return 0.0
            
        R = 3958.8 
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
        dist = 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return round(dist, 1)
    except Exception:
        return 0.0

def get_grid(lat, lon):
    try:
        if pd.isna(lat) or pd.isna(lon):
            return ""
        lat = float(lat)
        lon = float(lon)
        if lat == 0.0 and lon == 0.0:
            return ""
        return mh.to_maiden(lat, lon)
    except Exception:
        return ""

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

# --- 5. DATABANK CONNECTIONS & GOOGLE SHEETS ---
def get_gsheet():
    try:
        if "gcp_service_account" not in st.secrets:
            return None
        scope = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key("11_4lKQRCrV2Q0YZM1syECgoSINmnGIG3k6UJH0m_u3Y").worksheet("Form Entries")
        return sheet
    except Exception:
        return None

@st.cache_data(ttl=60)
def get_logged_set(dxer_name, band):
    try:
        if not dxer_name:
            return set()
        sheet = get_gsheet()
        if sheet is None:
            return set()
            
        vals = sheet.get_all_values()
        if len(vals) < 2:
            return set()
            
        logged = set()
        for row in vals[1:]:
            try:
                row_name = str(row[0]).strip().upper()
                row_band = str(row[4]).strip().upper()
                if row_name == dxer_name.strip().upper() and row_band == band.upper():
                    call = str(row[7]).strip().upper()
                    freq = str(row[5]).strip() if band == "AM" else str(row[6]).strip()
                    logged.add(f"{call}-{freq}")
            except Exception:
                continue
        return logged
    except Exception:
        return set()

@st.cache_data
def load_mw_intel():
    files_to_try = [
        "Mesa_Mike_Enriched.csv",
        "Mesa_Mike_Enriched (1).csv",
        "Mesa Mike Enriched.csv", 
        "Mesa Mike US Station Data - Sheet1.csv"
    ]
    
    for file in files_to_try:
        try:
            df = pd.read_csv(file, dtype=str)
            if not df.empty:
                df['Frequency'] = pd.to_numeric(df['FREQ'], errors='coerce')
                df['Callsign'] = df['CALL'].fillna("Unknown")
                df['State'] = df['STATE'].fillna("XX")
                df['City'] = df['CITY'].fillna("Unknown")
                
                if 'County' in df.columns:
                    df['County'] = df['County'].fillna("Unknown")
                else:
                    df['County'] = "Unknown"
                    
                df['LAT'] = pd.to_numeric(df['LAT'], errors='coerce')
                df['LON'] = pd.to_numeric(df['LON'], errors='coerce')
                df['Grid'] = df.apply(lambda x: get_grid(x['LAT'], x['LON']), axis=1)
                return df
        except Exception:
            continue
    return pd.DataFrame()

@st.cache_data
def load_fm_intel():
    files_to_try = [
        "WTFDA_Enriched.csv",
        "WTFDA Enriched.csv", 
        "FM Challenge - Station List and Data - WTFDA Data.csv",
        "sporadic-es-data-analysis.FMList_Data.wtfda_fips.csv"
    ]
    
    for file in files_to_try:
        try:
            df = pd.read_csv(file, dtype=str)
            if not df.empty:
                df['Frequency'] = pd.to_numeric(df['Frequency'], errors='coerce')
                
                if 'Call Letters' in df.columns and 'Callsign' not in df.columns:
                    df['Callsign'] = df['Call Letters']
                    
                df['Callsign'] = df.get('Callsign', pd.Series(["Unknown"] * len(df))).fillna("Unknown")
                df['State'] = df.get('S/P', pd.Series(["XX"] * len(df))).fillna("XX")
                
                if 'County' in df.columns:
                    df['County'] = df['County'].fillna("Unknown")
                else:
                    df['County'] = "Unknown"
                    
                lat_col = 'LAT' if 'LAT' in df.columns else 'Lat_N'
                lon_col = 'LON' if 'LON' in df.columns else 'Long_W'
                
                df['LAT'] = pd.to_numeric(df.get(lat_col, pd.Series([0.0]*len(df))), errors='coerce')
                df['LON'] = pd.to_numeric(df.get(lon_col, pd.Series([0.0]*len(df))), errors='coerce')
                df['Grid'] = df.apply(lambda x: get_grid(x['LAT'], x['LON']), axis=1)
                return df
        except Exception:
            continue
    return pd.DataFrame()

@st.cache_data
def load_countries():
    files_to_try = [
        "DX Central _ MW Frequency Challenge -All Seasons Master Logbook - Sheet64.csv",
        "DX_Central___MW_Frequency_Challenge_-All_Seasons_Master_Logbook_-_Sheet64.csv"
    ]
    for file in files_to_try:
        try:
            df = pd.read_csv(file)
            country_col = df['Country Name'].dropna().sort_values().tolist()
            return country_col
        except Exception:
            continue
    return ["Canada", "Mexico", "United States"]

mw_db = load_mw_intel()
fm_db = load_fm_intel()
country_list = load_countries()

us_states = ["AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"]
can_prov = ["AB", "BC", "MB", "NB", "NL", "NS", "NT", "NU", "ON", "PE", "QC", "SK", "YT"]
mex_states = ["AGU", "BCN", "BCS", "CAM", "CHP", "CHH", "CMX", "COA", "COL", "DUR", "GUA", "GRO", "HID", "JAL", "MEX", "MIC", "MOR", "NAY", "NLE", "OAX", "PUE", "QUE", "ROO", "SLP", "SIN", "SON", "TAB", "TAM", "TLA", "VER", "YUC", "ZAC"]

def get_state_list(country):
    if country == "United States": return us_states
    if country == "Canada": return can_prov
    if country == "Mexico": return mex_states
    return ["DX"]

def get_idx(guess_list, cols):
    for g in guess_list:
        for idx, c in enumerate(cols):
            if g.lower() in c.lower(): 
                return idx
    return 0

def handle_file_upload(uploaded_file):
    # Try multiple decodings to avoid byte errors with accents
    content = ""
    for enc in ['utf-8', 'latin-1', 'cp1252']:
        try:
            uploaded_file.seek(0)
            content = uploaded_file.read().decode(enc)
            break
        except:
            continue
            
    if not content:
        raise ValueError("Unable to decode file. Please ensure it is a standard CSV or Text format.")
        
    lines = content.splitlines()
    header_idx = 0
    
    # Auto-detect real header by looking for common DX keywords
    keywords = ['khz', 'freq', 'mhz', 'program', 'station', 'itu', 'propa', 'date']
    for i, line in enumerate(lines[:25]):
        line_lower = line.lower()
        if any(kw in line_lower for kw in keywords):
            header_idx = i
            break
            
    # Auto-detect separator
    sample = lines[header_idx]
    sep = ","
    if ";" in sample: sep = ";"
    elif "\t" in sample: sep = "\t"
    
    # Read as dataframe starting from the header row
    df = pd.read_csv(io.StringIO("\n".join(lines[header_idx:])), sep=sep, dtype=str)
    return df

# --- 6. SESSION STATE ROUTING & PROFILE ---
if 'sys_state' not in st.session_state: 
    st.session_state.sys_state = "OPERATOR_LOGIN"

if 'matrix_unlocked' not in st.session_state: 
    st.session_state.matrix_unlocked = False

if 'operator_profile' not in st.session_state:
    st.session_state.operator_profile = {
        "name": "", "city": "", "state": "", "country": "United States", "lat": 0.0, "lon": 0.0
    }

def nav_to(page):
    st.session_state.sys_state = page

# --- 6b. GLOBAL IRONCLAD FAILSAFE ---
if st.session_state.sys_state != "OPERATOR_LOGIN":
    prof = st.session_state.operator_profile
    op_name = prof.get('name')
    op_lat = float(prof.get('lat', 0.0))
    op_lon = float(prof.get('lon', 0.0))
    
    if not op_name or op_lat == 0.0 or op_lon == 0.0:
        st.session_state.sys_state = "OPERATOR_LOGIN"
        st.rerun()

# --- 7. SIDEBAR NAVIGATION (OMNIPRESENT) ---
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

        st.markdown("### [ SYSTEM COMMAND MENU ]")
        
        with st.expander("> INTELLIGENCE GATHERING", expanded=True):
            if st.button("MW INTERCEPT REPORT", key="nav_mw"): 
                nav_to("MW_LOG")
                st.rerun()
            if st.button("FM INTERCEPT REPORT", key="nav_fm"): 
                nav_to("FM_LOG")
                st.rerun()
            if st.button("ENCRYPTION PROTOCOL", key="nav_bounty"): 
                nav_to("BOUNTY_HUNT")
                st.rerun()
                
        with st.expander("> INTERCEPT DEBRIEFING", expanded=True):
            if st.button("GLOBAL DASHBOARD", key="nav_dash"): 
                nav_to("DASHBOARD")
                st.rerun()
                
        st.write("---")
        if st.button("LOGOUT / PURGE CACHE", key="nav_logout"):
            components.html("<script>window.parent.localStorage.removeItem('dx_central_operator');</script>", height=0, width=0)
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
            st.session_state.op_lat_val = float(saved_data.get("lat", 0.0))
            st.session_state.op_lon_val = float(saved_data.get("lon", 0.0))
            st.session_state.ls_loaded = True
            
            if st.session_state.op_name_val:
                st.success(f"LOCAL PROFILE DETECTED: {st.session_state.op_name_val.upper()}")
            
        state_keys = ['op_name_val', 'op_city_val', 'op_state_val', 'op_lat_val', 'op_lon_val']
        for key in state_keys:
            if key not in st.session_state: 
                if "lat" in key or "lon" in key:
                    st.session_state[key] = 0.0
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
            
            c1, c2 = st.columns(2)
            op_city = c1.text_input("HOME QTH: CITY", value=st.session_state.get("op_city_val", ""))
            op_state = c2.text_input("HOME QTH: STATE/PROV", value=st.session_state.get("op_state_val", ""))
            
            remember_me = st.checkbox("[ SAVE CREDENTIALS TO LOCAL TERMINAL ]", value=True)
            
            if st.form_submit_button("> AUTHENTICATE"):
                if op_name and st.session_state.op_lat_val != 0.0 and st.session_state.op_lon_val != 0.0:
                    
                    st.session_state.operator_profile = {
                        "name": op_name, 
                        "city": op_city, 
                        "state": op_state, 
                        "country": "United States", 
                        "lat": st.session_state.op_lat_val, 
                        "lon": st.session_state.op_lon_val
                    }
                    
                    if remember_me:
                        st.session_state.profile_to_save = {
                            "name": op_name, 
                            "city": op_city, 
                            "state": op_state, 
                            "lat": st.session_state.op_lat_val, 
                            "lon": st.session_state.op_lon_val
                        }
                        
                    nav_to("TERMINAL_HOME")
                    st.rerun()
                else:
                    st.error("ACCESS DENIED. AGENT IDENTITY AND NON-ZERO LOCATION REQUIRED.")

    # --- 8B. THE HOME TERMINAL ---
    elif st.session_state.sys_state == "TERMINAL_HOME":
        st.markdown('<div class="typewriter">GREETINGS, FELLOW SIGNAL TRAVELER.<br>WOULD YOU LIKE TO PLAY A GAME?<span class="blink">_</span></div>', unsafe_allow_html=True)
        
        if "gcp_service_account" not in st.secrets:
            st.error("🚨 [ SYSTEM ALERT ] DATALINK OFFLINE. Streamlit Secrets not configured. Logs cannot be submitted to the Google Sheet.")
        
        st.write("Use the **[ SYSTEM COMMAND MENU ]** in the sidebar to navigate the mainframe.")

    # --- 8C. MW INTERCEPT ROOM ---
    elif st.session_state.sys_state == "MW_LOG":
        st.markdown("### [ MW INTERCEPT CONSOLE ACTIVE ]")
        
        st.markdown("#### 1. OPERATING PARAMETERS")
        r_cat = st.radio("CATEGORY", ["HOME QTH", "ROVER"], horizontal=True, label_visibility="collapsed")
        rover_grid = ""
        
        active_lat = float(st.session_state.operator_profile.get('lat', 0.0))
        active_lon = float(st.session_state.operator_profile.get('lon', 0.0))
        active_grid_calc = get_grid(active_lat, active_lon)
        
        if r_cat == "ROVER":
            st.warning("ROVER MODE: ENTER CURRENT MAIDENHEAD GRID TO CALIBRATE DISTANCE.")
            rover_grid = st.text_input("ROVER GRID (e.g., EM40)")
            if len(rover_grid) >= 4:
                try:
                    r_lat, r_lon = mh.to_location(rover_grid)
                    active_lat = float(r_lat)
                    active_lon = float(r_lon)
                    active_grid_calc = rover_grid.upper()
                except Exception:
                    pass
                
        st.markdown("#### 2. TARGET ACQUISITION")
        tab_search, tab_manual, tab_import = st.tabs(["[ DATABASE SEARCH ]", "[ MANUAL ENTRY ]", "[ BULK IMPORT ]"])
        
        target_data = {}
        
        with tab_search:
            st.write("ACCESSING DOMESTIC AM DATABANKS...")
            
            if mw_db.empty:
                st.error("[ SYSTEM ALERT ] DATABANK OFFLINE: Mesa Mike database not found in repository.")
            else:
                if 'mw_filter_key' not in st.session_state:
                    st.session_state.mw_filter_key = 0
                def reset_mw_filters():
                    st.session_state.mw_filter_key += 1
                st.button("[ RESET SEARCH FILTERS ]", on_click=reset_mw_filters)
                
                fk = st.session_state.mw_filter_key
                c1, c2, c3, c4 = st.columns(4)
                
                all_freqs = sorted(mw_db['Frequency'].dropna().unique().tolist())
                f_freq = c1.selectbox("FREQ (kHz)", ["All"] + all_freqs, key=f"mw_f1_{fk}")
                f_call = c2.text_input("CALLSIGN", key=f"mw_f2_{fk}")
                f_city = c3.text_input("CITY", key=f"mw_f3_{fk}")
                
                all_states = sorted(mw_db['State'].dropna().unique().tolist())
                f_state = c4.selectbox("STATE", ["All"] + all_states, key=f"mw_f4_{fk}")
                
                c5, c6, c7 = st.columns(3)
                f_county = c5.text_input("COUNTY", key=f"mw_f5_{fk}")
                f_grid = c6.text_input("GRID", key=f"mw_f6_{fk}")
                f_status = c7.selectbox("STATUS", ["All", "Logged Only", "Not Logged Only"], key=f"mw_f7_{fk}")
                
                results = mw_db.copy()
                if f_freq != "All": results = results[results['Frequency'] == float(f_freq)]
                if f_call: results = results[results['Callsign'].str.contains(f_call.upper(), na=False)]
                if f_city: results = results[results['City'].str.contains(f_city, case=False, na=False)]
                if f_state != "All": results = results[results['State'] == f_state]
                if f_county: results = results[results['County'].str.contains(f_county, case=False, na=False)]
                if f_grid: results = results[results['Grid'].str.contains(f_grid.upper(), na=False)]
                
                if f_status != "All":
                    logged_set = get_logged_set(st.session_state.operator_profile.get('name', ''), "AM")
                    results['Check'] = results['Callsign'].str.upper() + "-" + results['Frequency'].astype(str)
                    if f_status == "Logged Only": results = results[results['Check'].isin(logged_set)]
                    else: results = results[~results['Check'].isin(logged_set)]
                        
                st.write(f"> {len(results)} TARGETS FOUND:")
                if not results.empty:
                    results['Dist'] = results.apply(lambda r: calculate_distance(active_lat, active_lon, r.get('LAT'), r.get('LON')), axis=1)
                    logged_set = get_logged_set(st.session_state.operator_profile.get('name', ''), "AM")
                    results['Check'] = results['Callsign'].str.upper() + "-" + results['Frequency'].astype(str)
                    results['Display Call'] = results.apply(lambda r: f"🟢 {r['Callsign']}" if r['Check'] in logged_set else r['Callsign'], axis=1)
                    results.insert(0, 'Log?', False)
                    view_df = results[['Log?', 'Frequency', 'Display Call', 'City', 'State', 'County', 'Grid', 'Dist', 'Callsign']]
                    edited_df = st.data_editor(view_df, hide_index=True, use_container_width=True,
                        column_config={"Log?": st.column_config.CheckboxColumn("Log?"), "Dist": st.column_config.NumberColumn("Dist (mi)", format="%.1f"), "Callsign": None},
                        disabled=['Frequency', 'Display Call', 'City', 'State', 'County', 'Grid', 'Dist', 'Callsign'], key=f"mw_db_editor_{fk}")
                    selected_rows = edited_df[edited_df['Log?'] == True]
                    if not selected_rows.empty:
                        target = selected_rows.iloc[0]
                        st.success(f"TARGET LOCKED: {target['Callsign']} ({target['City']}, {target['State']} - {target['County']} County | Grid: {target['Grid']} | {target['Dist']} mi)")
                        target_data = {"freq": target['Frequency'], "call": target['Callsign'], "city": target['City'], "state": target['State'], "county": target['County'], "country": "United States", "grid": target['Grid'], "dist": target['Dist']}

        with tab_manual:
            st.write("INITIATE UNLISTED / INTERNATIONAL PROTOCOL...")
            spacing = st.radio("CHANNEL SPACING", ["10 kHz (Region 2)", "9 kHz (Regions 1 & 3)"], horizontal=True)
            step_val = 10 if "10" in spacing else 9
            c_m1, c_m2, c_m3 = st.columns(3)
            man_freq = c_m1.number_input("MANUAL FREQ (kHz)", min_value=531, max_value=1710, value=540, step=step_val, key="man_mw")
            man_call = c_m2.text_input("STATION ID")
            full_countries = country_list.copy()
            if "Other" not in full_countries: full_countries.append("Other")
            def_idx = full_countries.index("United States") if "United States" in full_countries else 0
            man_ctry = c_m3.selectbox("COUNTRY", full_countries, index=def_idx)
            man_other = st.text_input("SPECIFY COUNTRY:") if man_ctry == "Other" else ""
            c_m4, c_m5, c_m6 = st.columns(3)
            man_city = c_m4.text_input("STATION CITY")
            man_sp = c_m5.selectbox("STATION STATE/PROV", get_state_list(man_ctry))
            man_dist = c_m6.number_input("EST. DISTANCE (MILES)", min_value=0.0, step=1.0)
            if man_call:
                target_data = {"freq": man_freq, "call": man_call, "city": man_city, "state": man_sp, "county": "Unknown", "country": man_other if man_ctry == "Other" else man_ctry, "grid": "", "dist": man_dist}

        with tab_import:
            st.write("INITIATE BULK INGESTION PROTOCOL (MWLIST / WLOGGER)...")
            uploaded_file = st.file_uploader("UPLOAD CSV/TSV PAYLOAD", type=["csv", "txt", "tsv"], key="mw_bulk")
            if uploaded_file is not None:
                try:
                    df_import = handle_file_upload(uploaded_file)
                    st.write(f"DETECTED {len(df_import)} RECORDS. PREVIEW:")
                    st.dataframe(df_import.head(5), use_container_width=True)
                    st.markdown("#### MAP DATABANK COLUMNS")
                    cols = ["<Skip>"] + df_import.columns.tolist()
                    c_i1, c_i2, c_i3 = st.columns(3)
                    map_freq = c_i1.selectbox("FREQUENCY", cols, index=get_idx(["freq", "khz"], cols))
                    map_call = c_i2.selectbox("CALLSIGN", cols, index=get_idx(["call", "station", "program"], cols))
                    map_date = c_i3.selectbox("DATE (UTC)", cols, index=get_idx(["date", "utc date"], cols))
                    c_i4, c_i5, c_i6 = st.columns(3)
                    map_time = c_i4.selectbox("TIME (UTC)", cols, index=get_idx(["time", "utc time", "utc"], cols))
                    map_city = c_i5.selectbox("STATION CITY", cols, index=get_idx(["city", "loc", "town", "location"], cols))
                    map_state = c_i6.selectbox("STATION STATE", cols, index=get_idx(["state", "prov", "sp", "reg"], cols))
                    c_i7, c_i8, c_i9 = st.columns(3)
                    map_ctry = c_i7.selectbox("COUNTRY", cols, index=get_idx(["countr", "itu"], cols))
                    map_dist = c_i8.selectbox("DISTANCE", cols, index=get_idx(["dist", "mi", "km", "qrb"], cols))
                    map_notes = c_i9.selectbox("NOTES / DETAILS", cols, index=get_idx(["note", "detail", "info", "comment", "remarks"], cols))
                    if st.button("> PROCESS & TRANSMIT BULK PAYLOAD"):
                        sheet = get_gsheet()
                        if sheet is None: st.error("🚨 DATALINK OFFLINE.")
                        else:
                            bulk_rows = []
                            op = st.session_state.operator_profile
                            cat = f"ROVER ({rover_grid})" if r_cat == "ROVER" and rover_grid else r_cat
                            for _, row in df_import.iterrows():
                                try:
                                    d_v = row[map_dist] if map_dist != "<Skip>" else 0.0
                                    d_v = float(str(d_v).replace('km', '').replace('mi', '').strip())
                                except: d_v = 0.0
                                r = [op.get('name', ''), op.get('city', ''), op.get('state', ''), op.get('country', ''),
                                    "AM", row[map_freq] if map_freq != "<Skip>" else "", "", row[map_call] if map_call != "<Skip>" else "", "",
                                    row[map_city] if map_city != "<Skip>" else "", row[map_state] if map_state != "<Skip>" else "",
                                    row[map_ctry] if map_ctry != "<Skip>" else "USA", "", active_grid_calc,
                                    row[map_date] if map_date != "<Skip>" else "", row[map_time] if map_time != "<Skip>" else "",
                                    d_v, row[map_notes] if map_notes != "<Skip>" else "", "", "", "Other", "", cat, "", ""]
                                bulk_rows.append(["" if pd.isna(x) else (x.item() if hasattr(x, 'item') else x) for x in r])
                            try:
                                sheet.append_rows(bulk_rows)
                                st.success(f"### [ {len(bulk_rows)} RECORDS TRANSMITTED ]")
                                st.balloons()
                            except Exception as e: st.error(f"BULK FAILED: {e}")
                except Exception as e: st.error(f"FILE PARSING ERROR: {e}")

        st.markdown("#### 3. SUBMIT INTERCEPT")
        with st.form("mw_submit_form", clear_on_submit=True):
            col_s1, col_s2, col_s3 = st.columns(3)
            now = datetime.datetime.now(datetime.timezone.utc)
            log_date = col_s1.date_input("DATE (UTC)", value=now.date())
            log_time = col_s2.text_input("TIME (UTC)", value=now.strftime("%H%M"))
            log_prop = col_s3.selectbox("PROPAGATION MODE", ["Groundwave - Daytime", "Grayline - Sunset", "Grayline - Sunrise", "Skywave - Nighttime", "Other"])
            log_notes = st.text_area("PROGRAMMING / INTERCEPT NOTES")
            if st.form_submit_button("> TRANSMIT REPORT TO SERVER"):
                if not target_data: st.error("TARGET NOT ACQUIRED.")
                else:
                    sheet = get_gsheet()
                    if sheet is None: st.error("🚨 DATALINK OFFLINE.")
                    else:
                        try:
                            op = st.session_state.operator_profile
                            cat = f"ROVER ({rover_grid})" if r_cat == "ROVER" and rover_grid else r_cat
                            r = [op.get('name', ''), op.get('city', ''), op.get('state', ''), op.get('country', ''),
                                "AM", target_data.get("freq", ""), "", target_data.get("call", ""), "", target_data.get("city", ""),
                                target_data.get("state", ""), target_data.get("country", ""), "", target_data.get("grid", ""),
                                log_date.strftime("%m/%d/%Y"), log_time, target_data.get("dist", 0.0), log_notes, "", "",
                                log_prop, target_data.get("county", ""), cat, "", ""]
                            sheet.append_row(["" if pd.isna(x) else (x.item() if hasattr(x, 'item') else x) for x in r])
                            st.markdown("### [ TRANSMISSION SUCCESSFUL ]")
                        except Exception as e: st.error(f"TRANSMISSION FAILED: {e}")

    # --- 8D. FM INTERCEPT ROOM ---
    elif st.session_state.sys_state == "FM_LOG":
        st.markdown("### [ FM INTERCEPT CONSOLE ACTIVE ]")
        r_cat = st.radio("CATEGORY", ["HOME QTH", "ROVER"], horizontal=True, label_visibility="collapsed", key="fm_cat")
        rover_grid = ""
        active_lat = float(st.session_state.operator_profile.get('lat', 0.0))
        active_lon = float(st.session_state.operator_profile.get('lon', 0.0))
        active_grid_calc = get_grid(active_lat, active_lon)
        if r_cat == "ROVER":
            st.warning("ROVER MODE ACTIVE.")
            rover_grid = st.text_input("ROVER GRID (e.g., EM40)", key="fm_rov")
            if len(rover_grid) >= 4:
                try:
                    r_lat, r_lon = mh.to_location(rover_grid)
                    active_lat, active_lon = float(r_lat), float(r_lon)
                    active_grid_calc = rover_grid.upper()
                except: pass
        tab_search, tab_manual, tab_import = st.tabs(["[ DATABASE SEARCH ]", "[ MANUAL ENTRY ]", "[ BULK IMPORT ]"])
        target_data = {}
        with tab_search:
            st.write("ACCESSING WTFDA DATABANKS...")
            if fm_db.empty: st.error("DATABANK OFFLINE.")
            else:
                if 'fm_filter_key' not in st.session_state: st.session_state.fm_filter_key = 0
                def reset_fm_filters(): st.session_state.fm_filter_key += 1
                st.button("[ RESET SEARCH FILTERS ]", on_click=reset_fm_filters, key="fm_reset")
                fk = st.session_state.fm_filter_key
                c1, c2, c3, c4 = st.columns(4)
                all_freqs = sorted(fm_db['Frequency'].dropna().unique().tolist())
                f_freq = c1.selectbox("FREQ (MHz)", ["All"] + all_freqs, key=f"fm_f1_{fk}")
                f_call = c2.text_input("CALLSIGN", key=f"fm_f2_{fk}")
                f_city = c3.text_input("CITY", key=f"fm_f3_{fk}")
                f_state = c4.selectbox("STATE", ["All"] + sorted(fm_db['State'].dropna().unique().tolist()), key=f"fm_f4_{fk}")
                c5, c6, c7 = st.columns(3)
                f_county = c5.text_input("COUNTY", key=f"fm_f5_{fk}")
                f_grid = c6.text_input("GRID", key=f"fm_f6_{fk}")
                f_status = c7.selectbox("STATUS", ["All", "Logged Only", "Not Logged Only"], key=f"fm_f7_{fk}")
                results = fm_db.copy()
                if f_freq != "All": results = results[results['Frequency'] == float(f_freq)]
                if f_call: results = results[results['Callsign'].str.contains(f_call.upper(), na=False)]
                if f_city: results = results[results['City'].str.contains(f_city, case=False, na=False)]
                if f_state != "All": results = results[results['State'] == f_state]
                if f_county: results = results[results['County'].str.contains(f_county, case=False, na=False)]
                if f_grid: results = results[results['Grid'].str.contains(f_grid.upper(), na=False)]
                if f_status != "All":
                    logged_set = get_logged_set(st.session_state.operator_profile.get('name', ''), "FM")
                    results['Check'] = results['Callsign'].str.upper() + "-" + results['Frequency'].astype(str)
                    if f_status == "Logged Only": results = results[results['Check'].isin(logged_set)]
                    else: results = results[~results['Check'].isin(logged_set)]
                st.write(f"> {len(results)} TARGETS FOUND:")
                if not results.empty:
                    results['Dist'] = results.apply(lambda r: calculate_distance(active_lat, active_lon, r.get('LAT'), r.get('LON')), axis=1)
                    logged_set = get_logged_set(st.session_state.operator_profile.get('name', ''), "FM")
                    results['Check'] = results['Callsign'].str.upper() + "-" + results['Frequency'].astype(str)
                    results['Display Call'] = results.apply(lambda r: f"🟢 {r['Callsign']}" if r['Check'] in logged_set else r['Callsign'], axis=1)
                    results.insert(0, 'Log?', False)
                    view_df = results[['Log?', 'Frequency', 'Display Call', 'City', 'State', 'County', 'Grid', 'PI Code', 'Dist', 'Callsign']]
                    edited_df = st.data_editor(view_df, hide_index=True, use_container_width=True,
                        column_config={"Log?": st.column_config.CheckboxColumn("Log?"), "Dist": st.column_config.NumberColumn("Dist (mi)", format="%.1f"), "Callsign": None},
                        disabled=['Frequency', 'Display Call', 'City', 'State', 'County', 'Grid', 'PI Code', 'Dist', 'Callsign'], key=f"fm_db_editor_{fk}")
                    selected_rows = edited_df[edited_df['Log?'] == True]
                    if not selected_rows.empty:
                        target = selected_rows.iloc[0]
                        st.success(f"TARGET LOCKED: {target['Callsign']} ({target['Dist']} mi)")
                        target_data = {"freq": target['Frequency'], "call": target['Callsign'], "city": target['City'], "state": target['State'], "county": target['County'], "country": "United States", "grid": target['Grid'], "pi": target.get('PI Code', ''), "dist": target['Dist']}

        with tab_manual:
            st.write("INITIATE UNLISTED PROTOCOL...")
            c_m1, c_m2, c_m3 = st.columns(3)
            man_freq = c_m1.number_input("MANUAL FREQ (MHz)", min_value=87.7, max_value=107.9, value=88.1, step=0.1, key="man_fm")
            man_call = c_m2.text_input("STATION ID", key="man_fm_call")
            man_ctry = c_m3.selectbox("COUNTRY", country_list + ["Other"], key="fm_ctry")
            man_other = st.text_input("SPECIFY COUNTRY:") if man_ctry == "Other" else ""
            c_m4, c_m5, c_m6 = st.columns(3)
            man_city = c_m4.text_input("CITY", key="fm_city")
            man_sp = c_m5.selectbox("STATE/PROV", get_state_list(man_ctry), key="fm_sp")
            man_dist = c_m6.number_input("DIST (MILES)", min_value=0.0, step=1.0, key="fm_dist")
            if man_call: target_data = {"freq": man_freq, "call": man_call, "city": man_city, "state": man_sp, "county": "Unknown", "country": man_other if man_ctry == "Other" else man_ctry, "grid": "", "pi": "", "dist": man_dist}

        with tab_import:
            st.write("INITIATE BULK INGESTION PROTOCOL (FMLIST / WLOGGER)...")
            uploaded_file = st.file_uploader("UPLOAD CSV/TSV PAYLOAD", type=["csv", "txt", "tsv"], key="fm_bulk")
            if uploaded_file is not None:
                try:
                    df_import = handle_file_upload(uploaded_file)
                    st.write(f"DETECTED {len(df_import)} RECORDS.")
                    st.dataframe(df_import.head(5), use_container_width=True)
                    cols = ["<Skip>"] + df_import.columns.tolist()
                    c_i1, c_i2, c_i3 = st.columns(3)
                    map_freq = c_i1.selectbox("FREQUENCY", cols, index=get_idx(["freq", "mhz"], cols), key="fm_map_1")
                    map_call = c_i2.selectbox("CALLSIGN", cols, index=get_idx(["call", "station", "program"], cols), key="fm_map_2")
                    map_date = c_i3.selectbox("DATE", cols, index=get_idx(["date"], cols), key="fm_map_3")
                    c_i4, c_i5, c_i6 = st.columns(3)
                    map_time = c_i4.selectbox("TIME", cols, index=get_idx(["time", "utc"], cols), key="fm_map_4")
                    map_city = c_i5.selectbox("CITY", cols, index=get_idx(["city", "loc"], cols), key="fm_map_5")
                    map_state = c_i6.selectbox("STATE", cols, index=get_idx(["state", "reg"], cols), key="fm_map_6")
                    if st.button("> PROCESS & TRANSMIT BULK", key="fm_bulk_btn"):
                        sheet = get_gsheet()
                        if sheet:
                            bulk = []
                            op = st.session_state.operator_profile
                            cat = f"ROVER ({rover_grid})" if r_cat == "ROVER" and rover_grid else r_cat
                            for _, row in df_import.iterrows():
                                r = [op.get('name', ''), op.get('city', ''), op.get('state', ''), op.get('country', ''),
                                    "FM", "", row[map_freq] if map_freq != "<Skip>" else "", row[map_call] if map_call != "<Skip>" else "", "",
                                    row[map_city] if map_city != "<Skip>" else "", row[map_state] if map_state != "<Skip>" else "", "USA", "", active_grid_calc,
                                    row[map_date] if map_date != "<Skip>" else "", row[map_time] if map_time != "<Skip>" else "", 0.0, "", "", "", "Other", "", cat, "", ""]
                                bulk.append(["" if pd.isna(x) else (x.item() if hasattr(x, 'item') else x) for x in r])
                            sheet.append_rows(bulk)
                            st.success(f"### [ {len(bulk)} RECORDS TRANSMITTED ]")
                            st.balloons()
                except Exception as e: st.error(f"FILE ERROR: {e}")

        st.markdown("#### 3. SUBMIT INTERCEPT")
        with st.form("fm_submit_form", clear_on_submit=True):
            col_s1, col_s2, col_s3 = st.columns(3)
            now = datetime.datetime.now(datetime.timezone.utc)
            log_date = col_s1.date_input("DATE (UTC)", value=now.date(), key="fm_dt")
            log_time = col_s2.text_input("TIME (UTC)", value=now.strftime("%H%M"), key="fm_tm")
            log_prop = col_s3.selectbox("PROPAGATION MODE", ["Tropo", "Sporadic E", "Meteor Scatter", "Aurora", "Local"])
            c_p1, c_p2 = st.columns(2)
            log_rds = c_p1.selectbox("RDS DECODE?", ["No", "Yes"])
            log_pi = c_p2.text_input("PI CODE", value=target_data.get("pi", ""))
            log_notes = st.text_area("NOTES", key="fm_nts")
            if st.form_submit_button("> TRANSMIT REPORT"):
                if not target_data: st.error("TARGET NOT ACQUIRED.")
                else:
                    sheet = get_gsheet()
                    if sheet:
                        try:
                            op = st.session_state.operator_profile
                            cat = f"ROVER ({rover_grid})" if r_cat == "ROVER" and rover_grid else r_cat
                            r = [op.get('name', ''), op.get('city', ''), op.get('state', ''), op.get('country', ''),
                                "FM", "", target_data.get("freq", ""), target_data.get("call", ""), "", target_data.get("city", ""),
                                target_data.get("state", ""), target_data.get("country", ""), "", target_data.get("grid", ""),
                                log_date.strftime("%m/%d/%Y"), log_time, target_data.get("dist", 0.0), log_notes, log_rds, log_pi,
                                log_prop, target_data.get("county", ""), cat, "", ""]
                            sheet.append_row(["" if pd.isna(x) else (x.item() if hasattr(x, 'item') else x) for x in r])
                            st.markdown("### [ TRANSMISSION SUCCESSFUL ]")
                        except Exception as e: st.error(f"FAILED: {e}")

    # --- 8E. THE CLANDESTINE MATRIX (BOUNTY ROOM) ---
    elif st.session_state.sys_state == "BOUNTY_HUNT":
        st.markdown("### --- SECURE UPLINK ESTABLISHED ---")
        st.markdown("AWAITING MATRIX ALIGNMENT PARAMETERS<span class='blink'>_</span>", unsafe_allow_html=True)
        ACTIVE_ALPHA, ACTIVE_NUMERIC, SECRET_PAYLOAD = "D", "4", "SPORADIC"
        col1, col2 = st.columns(2)
        alpha_key = col1.selectbox("ALPHA KEY", ["A", "B", "C", "D", "E"])
        numeric_key = col2.selectbox("NUMERIC KEY", ["1", "2", "3", "4", "5"])
        if alpha_key == ACTIVE_ALPHA and numeric_key == ACTIVE_NUMERIC:
            st.success("MATRIX ALIGNMENT LOCKED.")
            st.markdown('<div class="classified-box"><strong>DECRYPTION CIPHER ACTIVE:</strong><br>19=S | 16=P | 15=O | 18=R | 01=A | 04=D | 09=I | 03=C</div>', unsafe_allow_html=True)
            payload = st.text_input("ENTER DECRYPTED PAYLOAD:")
            if payload.upper() == SECRET_PAYLOAD:
                st.markdown("### [ ACCESS GRANTED ]")
                st.error("### TOP SECRET DOSSIER: ACTIVE")
                st.markdown("* Log any Class C AM Graveyard station.\n* Distance > 400 miles.\n* Window: 14 days.")
                st.button("> ACKNOWLEDGE MISSION")
        else: st.warning("MATRIX MISALIGNED.")

    # --- 8F. GLOBAL INTELLIGENCE (DASHBOARD STUB) ---
    elif st.session_state.sys_state == "DASHBOARD":
        st.markdown("### [ GLOBAL INTELLIGENCE DATABANKS ]")
        st.write("ESTABLISHING CONNECTION TO PLOTLY SERVERS...")
        st.markdown('<div class="classified-box"><strong>SYSTEM STATUS:</strong> DATA VISUALIZATION MODULES COMPILING.<br>STANDBY FOR CHOROPLETH MAPS, VOLUME TIMELINES, AND OPERATOR LEADERBOARDS.</div>', unsafe_allow_html=True)
