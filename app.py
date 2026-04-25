import streamlit as st
import pandas as pd
import datetime
import math
import json
import gspread
import maidenhead as mh
from geopy.geocoders import Nominatim
from google.oauth2.service_account import Credentials
from streamlit_javascript import st_javascript

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

header {visibility: hidden;}
footer {visibility: hidden;}

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

input, textarea, div[data-baseweb="select"] > div {
    background-color: #0a0a0a !important;
    border: 1px solid #39ff14 !important;
    color: #39ff14 !important;
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

# --- 3. GEOSPATIAL & MATH HELPERS ---
def calculate_distance(lat1, lon1, lat2, lon2):
    if any(v is None or pd.isna(v) for v in [lat1, lon1, lat2, lon2]): return 0.0
    try:
        lat1, lon1, lat2, lon2 = float(lat1), float(lon1), float(lat2), float(lon2)
        if lat1 == 0 and lon1 == 0: return 0.0
        R = 3958.8 
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi, dlambda = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
        return round(2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a)), 1)
    except:
        return 0.0

def reverse_geocode(lat, lon):
    try:
        geolocator = Nominatim(user_agent="dx_central_logger_v6")
        location = geolocator.reverse(f"{lat}, {lon}", language='en')
        if location:
            addr = location.raw.get('address', {})
            found_city = next((addr[tag] for tag in ['city', 'town', 'village', 'hamlet'] if tag in addr), "")
            st.session_state.op_city_val = found_city
            st.session_state.op_state_val = addr.get('state', addr.get('province', ''))
            st.session_state.op_country_val = addr.get('country', 'United States')
    except: pass

def update_from_grid():
    grid = st.session_state.grid_input.strip()
    if len(grid) >= 4:
        try:
            lat, lon = mh.to_location(grid)
            st.session_state.op_lat_val = float(lat)
            st.session_state.op_lon_val = float(lon)
            reverse_geocode(lat, lon)
        except: pass

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
        except: pass

# --- 4. DATABANK CONNECTIONS ---
@st.cache_data
def load_mw_intel():
    try:
        df = pd.read_csv("Mesa Mike Enriched.csv", dtype=str)
        df['Frequency'] = pd.to_numeric(df['FREQ'], errors='coerce')
        df['Callsign'] = df['CALL'].fillna("Unknown")
        df['State'] = df['STATE'].fillna("XX")
        df['City'] = df['CITY'].fillna("Unknown")
        df['County'] = df['County'].fillna("Unknown")
        df['LAT'] = pd.to_numeric(df['LAT'], errors='coerce')
        df['LON'] = pd.to_numeric(df['LON'], errors='coerce')
        return df
    except:
        return pd.DataFrame()

@st.cache_data
def load_fm_intel():
    try:
        df = pd.read_csv("WTFDA Enriched.csv", dtype=str)
        df['Frequency'] = pd.to_numeric(df['Frequency'], errors='coerce')
        if 'Call Letters' in df.columns and 'Callsign' not in df.columns:
            df['Callsign'] = df['Call Letters']
        df['Callsign'] = df['Callsign'].fillna("Unknown")
        df['State'] = df['S/P'].fillna("XX")
        df['County'] = df['County'].fillna("Unknown")
        df['LAT'] = pd.to_numeric(df['LAT'], errors='coerce')
        df['LON'] = pd.to_numeric(df['LON'], errors='coerce')
        return df
    except:
        return pd.DataFrame()

@st.cache_data
def load_countries():
    try:
        df = pd.read_csv("DX Central _ MW Frequency Challenge -All Seasons Master Logbook - Sheet64.csv")
        return df['Country Name'].dropna().sort_values().tolist()
    except:
        return ["Canada", "Mexico", "United States"]

def get_gsheet():
    scope = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    return client.open_by_key("11_4lKQRCrV2Q0YZM1syECgoSINmnGIG3k6UJH0m_u3Y").worksheet("Form Entries")

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

# --- 5. SESSION STATE ROUTING & PROFILE ---
if 'sys_state' not in st.session_state: st.session_state.sys_state = "OPERATOR_LOGIN"
if 'matrix_unlocked' not in st.session_state: st.session_state.matrix_unlocked = False
if 'operator_profile' not in st.session_state:
    st.session_state.operator_profile = {"name": "", "city": "", "state": "", "country": "United States", "lat": 0.0, "lon": 0.0}

def nav_to(page):
    st.session_state.sys_state = page

if st.session_state.sys_state != "OPERATOR_LOGIN":
    op_name_display = st.session_state.operator_profile.get('name', 'UNKNOWN').upper()
    st.markdown(f"<div style='text-align: right; font-size: 1.2rem;'>AGENT: {op_name_display} | STATUS: SECURE</div>", unsafe_allow_html=True)
    st.markdown("<hr style='margin-top: 5px; margin-bottom: 20px;'>", unsafe_allow_html=True)

# --- 6. OPERATOR LOGIN SCREEN ---
if st.session_state.sys_state == "OPERATOR_LOGIN":
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
        st.success(f"LOCAL PROFILE DETECTED: {st.session_state.op_name_val.upper()}")
        
    for key in ['op_name_val', 'op_city_val', 'op_state_val', 'op_lat_val', 'op_lon_val']:
        if key not in st.session_state: st.session_state[key] = "" if "val" not in key or "lat" not in key and "lon" not in key else 0.0

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
            if op_name and st.session_state.op_lat_val != 0.0:
                st.session_state.operator_profile = {
                    "name": op_name, "city": op_city, "state": op_state, 
                    "country": "United States", "lat": st.session_state.op_lat_val, "lon": st.session_state.op_lon_val
                }
                if remember_me:
                    prof = {"name": op_name, "city": op_city, "state": op_state, "lat": st.session_state.op_lat_val, "lon": st.session_state.op_lon_val}
                    st_javascript(f"localStorage.setItem('dx_central_operator', JSON.stringify({json.dumps(prof)}));")
                nav_to("TERMINAL_HOME")
                st.rerun()
            else:
                st.error("ACCESS DENIED. AGENT IDENTITY AND LOCATION REQUIRED.")

# --- 7. THE HOME TERMINAL ---
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
        
    if st.button("> LOGOUT / PURGE LOCAL CACHE"):
        st_javascript("localStorage.removeItem('dx_central_operator');")
        st.session_state.clear()
        st.rerun()

# --- 8. MW INTERCEPT ROOM ---
elif st.session_state.sys_state == "MW_LOG":
    st.markdown("### [ MW INTERCEPT CONSOLE ACTIVE ]")
    
    st.markdown("#### 1. OPERATING PARAMETERS")
    r_cat = st.radio("CATEGORY", ["HOME QTH", "ROVER"], horizontal=True, label_visibility="collapsed")
    rover_grid = ""
    active_lat, active_lon = st.session_state.operator_profile['lat'], st.session_state.operator_profile['lon']
    
    if r_cat == "ROVER":
        st.warning("ROVER MODE: ENTER CURRENT MAIDENHEAD GRID TO CALIBRATE DISTANCE.")
        rover_grid = st.text_input("ROVER GRID (e.g., EM40)")
        if len(rover_grid) >= 4:
            try:
                r_lat, r_lon = mh.to_location(rover_grid)
                active_lat, active_lon = float(r_lat), float(r_lon)
            except: pass
            
    st.markdown("#### 2. TARGET ACQUISITION")
    tab_search, tab_manual = st.tabs(["[ DATABASE SEARCH ]", "[ MANUAL ENTRY ]"])
    
    target_data = {}
    is_manual = False
    
    with tab_search:
        st.write("ACCESSING DOMESTIC AM DATABANKS...")
        c1, c2 = st.columns([1, 2])
        search_freq = c1.number_input("FREQ (kHz)", min_value=530, max_value=1710, value=540, step=10)
        search_call = c2.text_input("CALLSIGN (OPTIONAL)")
        
        if not mw_db.empty:
            results = mw_db[mw_db['Frequency'] == search_freq].copy()
            if search_call:
                results = results[results['Callsign'].str.contains(search_call.upper(), na=False)]
                
            st.write(f"> {len(results)} TARGETS FOUND:")
            if not results.empty:
                results['Dist'] = results.apply(lambda r: calculate_distance(active_lat, active_lon, r.get('LAT'), r.get('LON')), axis=1)
                results.insert(0, 'Log?', False)
                view_df = results[['Log?', 'Frequency', 'Callsign', 'City', 'State', 'County', 'Dist']]
                
                edited_df = st.data_editor(
                    view_df, hide_index=True, use_container_width=True,
                    column_config={"Log?": st.column_config.CheckboxColumn("Log?"), "Dist": st.column_config.NumberColumn("Dist (mi)", format="%.1f")},
                    disabled=['Frequency', 'Callsign', 'City', 'State', 'County', 'Dist'],
                    key="mw_db_editor"
                )
                
                selected_rows = edited_df[edited_df['Log?'] == True]
                if not selected_rows.empty:
                    target = selected_rows.iloc[0]
                    st.success(f"TARGET LOCKED: {target['Callsign']} ({target['City']}, {target['State']} - {target['Dist']} mi)")
                    target_data = {"freq": target['Frequency'], "call": target['Callsign'], "city": target['City'], "state": target['State'], "county": target['County'], "country": "United States", "dist": target['Dist']}

    with tab_manual:
        st.write("INITIATE UNLISTED / INTERNATIONAL PROTOCOL...")
        spacing = st.radio("CHANNEL SPACING", ["10 kHz (Region 2)", "9 kHz (Regions 1 & 3)"], horizontal=True)
        step_val = 10 if "10" in spacing else 9
        
        c_m1, c_m2, c_m3 = st.columns(3)
        man_freq = c_m1.number_input("MANUAL FREQ (kHz)", min_value=531, max_value=1710, value=540, step=step_val, key="man_mw")
        man_call = c_m2.text_input("STATION ID")
        
        full_countries = country_list + ["Other"] if "Other" not in country_list else country_list
        def_idx = full_countries.index("United States") if "United States" in full_countries else 0
        man_ctry = c_m3.selectbox("COUNTRY", full_countries, index=def_idx)
        
        man_other = st.text_input("SPECIFY COUNTRY:") if man_ctry == "Other" else ""
        
        c_m4, c_m5, c_m6 = st.columns(3)
        man_city = c_m4.text_input("STATION CITY")
        state_opts = get_state_list(man_ctry)
        man_sp = c_m5.selectbox("STATION STATE/PROV", state_opts)
        man_dist = c_m6.number_input("EST. DISTANCE (MILES)", min_value=0.0, step=1.0)
        
        if man_call:
            is_manual = True
            target_data = {"freq": man_freq, "call": man_call, "city": man_city, "state": man_sp, "county": "Unknown", "country": man_other if man_ctry == "Other" else man_ctry, "dist": man_dist}

    st.markdown("#### 3. SUBMIT INTERCEPT")
    with st.form("mw_submit_form", clear_on_submit=True):
        col_s1, col_s2, col_s3 = st.columns(3)
        now = datetime.datetime.now(datetime.timezone.utc)
        log_date = col_s1.date_input("DATE (UTC)", value=now.date())
        log_time = col_s2.text_input("TIME (UTC)", value=now.strftime("%H%M"))
        log_prop = col_s3.selectbox("PROPAGATION MODE", ["Groundwave - Daytime", "Grayline - Sunset", "Grayline - Sunrise", "Skywave - Nighttime", "Other"])
        
        log_notes = st.text_area("PROGRAMMING / INTERCEPT NOTES")
        
        submit_log = st.form_submit_button("> TRANSMIT REPORT TO SERVER")
        if submit_log:
            if not target_data:
                st.error("TARGET NOT ACQUIRED. SELECT OR ENTER A STATION.")
            else:
                try:
                    op = st.session_state.operator_profile
                    row_data = [
                        op['name'], op['city'], op['state'], op['country'], 
                        "AM", target_data.get("freq", ""), "", 
                        target_data.get("call", ""), "", target_data.get("city", ""), 
                        target_data.get("state", ""), target_data.get("country", ""), 
                        "", rover_grid, log_date.strftime("%m/%d/%Y"), log_time, 
                        target_data.get("dist", 0.0), log_notes, "", "", log_prop, target_data.get("county", ""), 
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

# --- 9. FM INTERCEPT ROOM ---
elif st.session_state.sys_state == "FM_LOG":
    st.markdown("### [ FM INTERCEPT CONSOLE ACTIVE ]")
    
    st.markdown("#### 1. OPERATING PARAMETERS")
    r_cat = st.radio("CATEGORY", ["HOME QTH", "ROVER"], horizontal=True, label_visibility="collapsed", key="fm_cat")
    rover_grid = ""
    active_lat, active_lon = st.session_state.operator_profile['lat'], st.session_state.operator_profile['lon']
    
    if r_cat == "ROVER":
        st.warning("ROVER MODE: ENTER CURRENT MAIDENHEAD GRID TO CALIBRATE DISTANCE.")
        rover_grid = st.text_input("ROVER GRID (e.g., EM40)", key="fm_rov")
        if len(rover_grid) >= 4:
            try:
                r_lat, r_lon = mh.to_location(rover_grid)
                active_lat, active_lon = float(r_lat), float(r_lon)
            except: pass
            
    st.markdown("#### 2. TARGET ACQUISITION")
    tab_search, tab_manual = st.tabs(["[ DATABASE SEARCH ]", "[ MANUAL ENTRY ]"])
    target_data = {}
    
    with tab_search:
        st.write("ACCESSING WTFDA DATABANKS...")
        c1, c2 = st.columns([1, 2])
        search_freq = c1.number_input("FREQ (MHz)", min_value=87.7, max_value=107.9, value=88.1, step=0.2, format="%.1f")
        search_call = c2.text_input("CALLSIGN (OPTIONAL)", key="fm_call_srch")
        
        if not fm_db.empty:
            results = fm_db[fm_db['Frequency'] == search_freq].copy()
            if search_call:
                results = results[results['Callsign'].str.contains(search_call.upper(), na=False)]
                
            st.write(f"> {len(results)} TARGETS FOUND:")
            if not results.empty:
                results['Dist'] = results.apply(lambda r: calculate_distance(active_lat, active_lon, r.get('LAT'), r.get('LON')), axis=1)
                results.insert(0, 'Log?', False)
                view_df = results[['Log?', 'Frequency', 'Callsign', 'City', 'State', 'County', 'PI Code', 'Dist']]
                
                edited_df = st.data_editor(
                    view_df, hide_index=True, use_container_width=True,
                    column_config={"Log?": st.column_config.CheckboxColumn("Log?"), "Dist": st.column_config.NumberColumn("Dist (mi)", format="%.1f")},
                    disabled=['Frequency', 'Callsign', 'City', 'State', 'County', 'PI Code', 'Dist'],
                    key="fm_db_editor"
                )
                
                selected_rows = edited_df[edited_df['Log?'] == True]
                if not selected_rows.empty:
                    target = selected_rows.iloc[0]
                    st.success(f"TARGET LOCKED: {target['Callsign']} ({target['City']}, {target['State']} - {target['Dist']} mi)")
                    target_data = {"freq": target['Frequency'], "call": target['Callsign'], "city": target['City'], "state": target['State'], "county": target['County'], "country": "United States", "pi": target['PI Code'], "dist": target['Dist']}

    with tab_manual:
        st.write("INITIATE UNLISTED PROTOCOL...")
        c_m1, c_m2, c_m3 = st.columns(3)
        man_freq = c_m1.number_input("MANUAL FREQ (MHz)", min_value=87.7, max_value=107.9, value=88.1, step=0.1, key="man_fm")
        man_call = c_m2.text_input("STATION ID", key="man_fm_call")
        
        full_countries = country_list + ["Other"] if "Other" not in country_list else country_list
        def_idx = full_countries.index("United States") if "United States" in full_countries else 0
        man_ctry = c_m3.selectbox("COUNTRY", full_countries, index=def_idx, key="fm_man_ctry")
        
        man_other = st.text_input("SPECIFY COUNTRY:") if man_ctry == "Other" else ""
        
        c_m4, c_m5, c_m6 = st.columns(3)
        man_city = c_m4.text_input("STATION CITY", key="fm_man_cty")
        state_opts = get_state_list(man_ctry)
        man_sp = c_m5.selectbox("STATION STATE/PROV", state_opts, key="fm_man_sp")
        man_dist = c_m6.number_input("EST. DISTANCE (MILES)", min_value=0.0, step=1.0, key="fm_man_dst")

        if man_call:
            target_data = {"freq": man_freq, "call": man_call, "city": man_city, "state": man_sp, "county": "Unknown", "country": man_other if man_ctry == "Other" else man_ctry, "pi": "", "dist": man_dist}

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
        
        log_notes = st.text_area("PROGRAMMING / INTERCEPT NOTES", key="fm_nts")
        
        submit_log = st.form_submit_button("> TRANSMIT REPORT TO SERVER")
        if submit_log:
            if not target_data:
                st.error("TARGET NOT ACQUIRED. SELECT OR ENTER A STATION.")
            else:
                try:
                    op = st.session_state.operator_profile
                    row_data = [
                        op['name'], op['city'], op['state'], op['country'], 
                        "FM", "", target_data.get("freq", ""), 
                        target_data.get("call", ""), "", target_data.get("city", ""), 
                        target_data.get("state", ""), target_data.get("country", ""), 
                        "", rover_grid, log_date.strftime("%m/%d/%Y"), log_time, 
                        target_data.get("dist", 0.0), log_notes, log_rds, log_pi, log_prop, target_data.get("county", ""), 
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

# --- 10. THE CLANDESTINE MATRIX (BOUNTY ROOM) ---
elif st.session_state.sys_state == "BOUNTY_HUNT":
    st.markdown("### --- SECURE UPLINK ESTABLISHED ---")
    st.markdown("AWAITING MATRIX ALIGNMENT PARAMETERS<span class='blink'>_</span>", unsafe_allow_html=True)
    
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
            st.button("> ACKNOWLEDGE & ACCEPT MISSION")

    st.write("---")
    if st.button("< ABORT PROTOCOL / RETURN"):
        st.session_state.matrix_unlocked = False
        nav_to("TERMINAL_HOME")
        st.rerun()

# --- 11. GLOBAL INTELLIGENCE (DASHBOARD STUB) ---
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
