import streamlit as st
import pandas as pd
import datetime
import math
import json
import gspread
import maidenhead as mh
import io
import re
import os
import csv
import urllib.request
import unicodedata
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

# --- 4. HELPERS & TRANSLATORS ---
itu_map = {
    "USA": "United States", "CAN": "Canada", "MEX": "Mexico", "CUB": "Cuba", 
    "CLM": "Colombia", "DOM": "Dominican Republic", "PRU": "Peru", "BHS": "Bahamas", "BAH": "Bahamas",
    "GTM": "Guatemala", "HND": "Honduras", "NIC": "Nicaragua", "NCG": "Nicaragua", "CRI": "Costa Rica", "CTR": "Costa Rica",
    "PAN": "Panama", "PNR": "Panama", "VEN": "Venezuela", "ECU": "Ecuador", "EQA": "Ecuador", "BRA": "Brazil",
    "BOL": "Bolivia", "CHL": "Chile", "ARG": "Argentina", "URY": "Uruguay", "URG": "Uruguay",
    "PRY": "Paraguay", "PRG": "Paraguay", "JAM": "Jamaica", "JMC": "Jamaica", "HTI": "Haiti", "BEL": "Belize", "BLZ": "Belize",
    "SLV": "El Salvador", "PUR": "Puerto Rico", "PTR": "Puerto Rico", "BER": "Bermuda",
    "BVI": "British Virgin Islands", "VGB": "British Virgin Islands", "VRG": "British Virgin Islands", "BRITISH VIRGIN ISLANDS": "British Virgin Islands",
    "VIR": "US Virgin Islands", "ALG": "Algeria", "ATG": "Antigua", "KNA": "St. Kitts & Nevis",
    "LCA": "St. Lucia", "VCT": "St. Vincent", "GRD": "Grenada", "TCA": "Turks & Caicos",
    "AIA": "Anguilla", "CYM": "Cayman Islands", "MSR": "Montserrat", "GLP": "Guadeloupe",
    "MTQ": "Martinique", "SPM": "St. Pierre & Miquelon",
    "BON": "Bonaire", "BES": "Bonaire", "ATN": "Bonaire", "ANT": "Bonaire", "BONAIRE": "Bonaire",
    "ABW": "Aruba"
}

def clean_callsign(call):
    if not call or pd.isna(call): 
        return ""
    call = str(call).strip().upper()
    call = re.sub(r'\s+R:.*$', '', call) # Remove FMList meta tags
    call = call.replace('-FM', '')       # Safely remove -FM while preserving -LP or -2
    call = re.sub(r'\s+FM\b', '', call)  # Remove trailing standalone FM
    return call.strip('- ')

def simplify_string(s):
    if not s or pd.isna(s): 
        return ""
    s = str(s).upper()
    s = unicodedata.normalize('NFD', s).encode('ascii', 'ignore').decode('utf-8')
    s = s.replace(' DX', '')
    return re.sub(r'[^A-Z0-9]', '', s)

def super_clean(s):
    if not s or pd.isna(s): 
        return ""
    s = str(s).upper()
    s = unicodedata.normalize('NFD', s).encode('ascii', 'ignore').decode('utf-8')
    s = re.sub(r'[^A-Z0-9]', '', s)
    if s.endswith('FM'):
        s = s[:-2]
    return s

def standardize_cuban_station(call, freq, country):
    if str(country).strip() != "Cuba" or not call or pd.isna(call):
        return call
        
    call_lower = str(call).lower()
    
    try: 
        freq_str = str(int(float(str(freq).replace(',', '.'))))
    except Exception: 
        freq_str = str(freq).strip()
        
    cuban_networks = {
        r'reloj': 'Radio Reloj',
        r'rebelde': 'Radio Rebelde',
        r'progres[s]*o': 'Radio Progreso',
        r'enc[iy]clopedia': 'Radio Enciclopedia',
        r'music[al]*\s*nacional|cmbf': 'Radio Musical Nacional',
        r'ciudad\s*de\s*h[ab|av]ana': 'Radio Ciudad de Habana',
        r'guam[aá]': 'Radio Guamá',
        r'mart[ií]': 'Radio Martí',
        r'victori[a]': 'Radio Victoria',
        r'cadena\s*agramonte': 'Radio Cadena Agramonte'
    }
    
    std_name = None
    for pattern, true_name in cuban_networks.items():
        if re.search(pattern, call_lower):
            std_name = true_name
            break
            
    if not std_name:
        std_name = re.sub(r'^r\.\s*', 'Radio ', str(call), flags=re.IGNORECASE)
        if re.match(r'^CM[A-Z]{2}$', std_name.upper()):
            std_name = std_name.upper()
        else:
            std_name = std_name.title()
            
    if freq_str and f"({freq_str})" not in std_name:
        return f"{std_name} ({freq_str})"
        
    return std_name

def format_date_import(date_str):
    try:
        date_str = str(date_str).strip()
        if not date_str or date_str == "<Skip>": 
            return ""
        
        # If it's WLogger format (YYYY-MM-DD), don't use dayfirst
        if "-" in date_str and len(date_str.split("-")[0]) == 4:
            d = pd.to_datetime(date_str)
        else:
            d = pd.to_datetime(date_str, dayfirst=True)
            
        return d.strftime("%m/%d/%Y")
    except Exception:
        return date_str

def format_time_import(time_str):
    try:
        time_str = str(time_str).strip()
        if not time_str or time_str == "<Skip>": 
            return ""
            
        if re.match(r'^\d{3,4}$', time_str):
            return time_str.zfill(4)
            
        d = pd.to_datetime(time_str)
        return d.strftime("%H%M")
    except Exception:
        return time_str

def map_mw_prop(prop_raw):
    if not prop_raw or pd.isna(prop_raw): 
        return "Other"
    p = str(prop_raw).lower()
    if "day" in p or "ground" in p: 
        return "Groundwave - Daytime"
    if "night" in p or "sky" in p or "dx" in p: 
        return "Skywave - Nighttime"
    if "sunset" in p or "dusk" in p: 
        return "Grayline - Sunset"
    if "sunrise" in p or "dawn" in p: 
        return "Grayline - Sunrise"
    return "Other"

def map_fm_prop(prop_raw):
    if not prop_raw or pd.isna(prop_raw): 
        return "Other"
    p = str(prop_raw).upper()
    if "ES" in p or "SPORADIC" in p: 
        return "Sporadic E"
    if "TR" in p or "TROPO" in p: 
        return "Tropo"
    if "MS" in p or "METEOR" in p: 
        return "Meteor Scatter"
    if "AU" in p or "AURORA" in p: 
        return "Aurora"
    if "LOS" in p or "LOCAL" in p: 
        return "Local"
    return "Other"

def calculate_distance(lat1, lon1, lat2, lon2):
    if pd.isna(lat1) or pd.isna(lon1) or pd.isna(lat2) or pd.isna(lon2):
        return 0.0
    try:
        lat1 = float(lat1)
        lon1 = float(lon1)
        lat2 = float(lat2)
        lon2 = float(lon2)
        if (lat1 == 0.0 and lon1 == 0.0) or (lat2 == 0.0 and lon2 == 0.0):
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

@st.cache_data(ttl=86400)
def get_lat_lon_from_city(city, country):
    try:
        geolocator = Nominatim(user_agent="dx_central_logger_v7", timeout=5)
        query = f"{city}, {country}" if city and city != "Unknown" and not pd.isna(city) else country
        loc = geolocator.geocode(query)
        if not loc and city and city != "Unknown":
            loc = geolocator.geocode(country)
        if loc:
            return float(loc.latitude), float(loc.longitude)
    except Exception:
        pass
    return 0.0, 0.0

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

def get_idx(guess_list, cols):
    for g in guess_list:
        for idx, c in enumerate(cols):
            if str(g).lower() in str(c).lower(): 
                return idx
    return 0

def find_col(df, possible_names):
    # Strict Exact Match Check First
    for n in possible_names:
        for col in df.columns:
            if str(n).lower() == str(col).lower().strip(): 
                return col
    # Fallback Fuzzy Check
    for n in possible_names:
        for col in df.columns:
            if str(n).lower() in str(col).lower(): 
                return col
    return None

# --- THE BULLETPROOF MW CSV PARSER (ISOLATED) ---
def handle_mw_file_upload(uploaded_file):
    content = ""
    for enc in ['utf-8', 'latin-1', 'cp1252']:
        try:
            uploaded_file.seek(0)
            content = uploaded_file.read().decode(enc)
            break
        except Exception: 
            continue
            
    if not content: 
        raise ValueError("Unable to decode file. Encoding failure.")
        
    lines = content.splitlines()
    
    best_row = 0
    best_sep = ","
    
    keywords = ['khz', 'freq', 'mhz', 'program', 'station', 'itu', 'propa', 'date', 'utc', 'call', 'qrb', 'sinpo', 'remarks', 'details']
    
    for i, line in enumerate(lines[:50]):
        line_lower = line.lower()
        if sum(1 for kw in keywords if kw in line_lower) >= 3 and len(line) < 300:
            best_row = i
            c_comma = line.count(",")
            c_semi = line.count(";")
            c_tab = line.count("\t")
            max_d = max(c_comma, c_semi, c_tab)
            if max_d == c_semi: 
                best_sep = ";"
            elif max_d == c_tab: 
                best_sep = "\t"
            else: 
                best_sep = ","
            break
            
    if best_row == 0:
        max_delims = 0
        for i, line in enumerate(lines[:50]):
            c_comma = line.count(",")
            c_semi = line.count(";")
            c_tab = line.count("\t")
            current_max = max(c_comma, c_semi, c_tab)
            if current_max > max_delims and len(line) < 300:
                max_delims = current_max
                best_row = i
                if c_semi == current_max: 
                    best_sep = ";"
                elif c_tab == current_max: 
                    best_sep = "\t"
                else: 
                    best_sep = ","

    header_line_raw = next(csv.reader([lines[best_row]], delimiter=best_sep))
    header_line = [h.strip(' \'"') for h in header_line_raw]
    num_cols = len(header_line)
    parsed_data = []
    
    for line in lines[best_row+1:]:
        if not line.strip(): 
            continue
        
        cols = next(csv.reader([line], delimiter=best_sep))
        
        if len(cols) > num_cols:
            merged_last = best_sep.join(cols[num_cols-1:])
            cols = cols[:num_cols-1] + [merged_last]
        elif len(cols) < num_cols:
            cols.extend([""] * (num_cols - len(cols)))
            
        cols = [c.strip(' \'"') for c in cols]
        parsed_data.append(cols)
        
    unique_headers = []
    for j, h in enumerate(header_line):
        h_str = str(h) if h else f"Unnamed_{j}"
        if h_str in unique_headers: 
            h_str = f"{h_str}_{j}"
        unique_headers.append(h_str)
        
    return pd.DataFrame(parsed_data, columns=unique_headers)


# --- THE HEAVYWEIGHT FM PANDAS PARSER (ISOLATED) ---
def handle_fm_file_upload(uploaded_file):
    content = ""
    for enc in ['utf-8', 'latin-1', 'cp1252']:
        try:
            uploaded_file.seek(0)
            content = uploaded_file.read().decode(enc)
            break
        except Exception: 
            continue
            
    if not content: 
        raise ValueError("Unable to decode file. Encoding failure.")
        
    lines = content.splitlines()
    
    best_row = 0
    best_sep = ","
    
    keywords = [
        'khz', 'freq', 'mhz', 'program', 'station', 'itu', 'propa', 'date', 'utc', 'call', 
        'qrb', 'sinpo', 'remarks', 'details', 'timestamp', 'city', 'state', 'distance', 
        'mode', 'comments'
    ]
    
    for i, line in enumerate(lines[:50]):
        line_lower = line.lower()
        if sum(1 for kw in keywords if kw in line_lower) >= 3 and len(line) < 300:
            best_row = i
            c_comma = line.count(",")
            c_semi = line.count(";")
            c_tab = line.count("\t")
            max_d = max(c_comma, c_semi, c_tab)
            if max_d == c_semi: 
                best_sep = ";"
            elif max_d == c_tab: 
                best_sep = "\t"
            else: 
                best_sep = ","
            break
            
    try:
        df = pd.read_csv(io.StringIO(content), sep=best_sep, skiprows=best_row, engine='python', on_bad_lines='skip')
    except Exception:
        df = pd.read_csv(io.StringIO(content), sep=best_sep, skiprows=best_row, on_bad_lines='skip')
        
    df.columns = [str(c).strip(' \'"') for c in df.columns]
    
    # Strip WLogger Location/Signature immediately to prevent alignment drift
    if 'Location' in df.columns:
        df = df.drop(columns=['Location'])
    if 'Signature' in df.columns:
        df = df.drop(columns=['Signature'])
        
    return df

# --- 5. DATABANK CONNECTIONS ---
def get_gsheet():
    try:
        if "gcp_service_account" not in st.secrets: 
            return None
        scope = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        client = gspread.authorize(creds)
        return client.open_by_key("11_4lKQRCrV2Q0YZM1syECgoSINmnGIG3k6UJH0m_u3Y").worksheet("Form Entries")
    except Exception: 
        return None

@st.cache_data(ttl=60)
def get_full_logs_df(dxer_name, band):
    try:
        sheet = get_gsheet()
        if sheet is None: 
            return pd.DataFrame()
        vals = sheet.get_all_values()
        if len(vals) < 2: 
            return pd.DataFrame()
        
        df = pd.DataFrame(vals[1:], columns=vals[0])
        
        if len(df.columns) > 4:
            name_col = df.columns[0]
            band_col = df.columns[4]
            
            df = df[(df[name_col].str.strip().str.upper() == dxer_name.strip().upper()) & 
                    (df[band_col].str.strip().str.upper() == band.upper())]
        return df
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=60)
def get_logged_dict(dxer_name, band):
    try:
        if not dxer_name: 
            return {}
        sheet = get_gsheet()
        if sheet is None: 
            return {}
        vals = sheet.get_all_values()
        if len(vals) < 2: 
            return {}
        
        logged = {}
        for row in vals[1:]:
            try:
                row_name = str(row[0]).strip().upper()
                row_band = str(row[4]).strip().upper()
                if row_name == dxer_name.strip().upper() and row_band == band.upper():
                    call = str(row[7]).strip().upper()
                    city = str(row[9]).strip().upper()
                    state = str(row[10]).strip().upper()
                    country = str(row[11]).strip().upper()
                    
                    if band == "AM": 
                        freq_val = float(str(row[5]).replace(',', '.'))
                    else: 
                        freq_val = float(str(row[6]).replace(',', '.'))
                        
                    if freq_val not in logged: 
                        logged[freq_val] = []
                    logged[freq_val].append({
                        "call": call, 
                        "city": city, 
                        "state": state, 
                        "country": country
                    })
            except Exception: 
                continue
        return logged
    except Exception: 
        return {}

def check_is_logged_mw(freq, call, city, country, logged_dict):
    try:
        f_val = float(freq)
        c_val = simplify_string(call)
        city_val = simplify_string(city)
        ctry_val = simplify_string(country)
        
        if f_val in logged_dict:
            for l_dict in logged_dict[f_val]:
                l_call = simplify_string(l_dict['call'])
                l_city = simplify_string(l_dict['city'])
                l_ctry = simplify_string(l_dict['country'])
                
                if ctry_val in ["UNITEDSTATES", "CANADA", "MEXICO", "CUBA"]:
                    if l_call and c_val and (l_call in c_val or c_val in l_call):
                        return True
                else:
                    if l_city and city_val and ctry_val == l_ctry and (l_city in city_val or city_val in l_city):
                        return True
    except Exception: 
        pass
    return False

def check_is_logged_fm(freq, call, slogan, city, state, country, logged_dict):
    try:
        f_val = float(freq)
        c_val = super_clean(call)
        slogan_val = super_clean(slogan)
        city_val = simplify_string(city)
        ctry_val = simplify_string(country)
        
        for l_freq, logs in logged_dict.items():
            if abs(l_freq - f_val) < 0.05:
                for l_dict in logs:
                    l_call = super_clean(l_dict['call'])
                    l_city = simplify_string(l_dict['city'])
                    l_ctry = simplify_string(l_dict['country'])
                    
                    # Track 1: Standard Callsign Match
                    if l_call and c_val and l_call != "UNKNOWN" and c_val != "UNKNOWN" and (l_call in c_val or c_val in l_call):
                        return True
                        
                    # Track 2: City + Country Match
                    elif l_city and city_val and l_city != "UNKNOWN" and city_val != "UNKNOWN" and (l_city in city_val or city_val in l_city) and l_ctry == ctry_val:
                        return True
                        
                    # Track 3: Slogan Match against Slogan OR Callsign column
                    elif l_call and slogan_val and l_call != "UNKNOWN" and slogan_val != "UNKNOWN" and (l_call in slogan_val or slogan_val in l_call):
                        return True
                        
    except Exception: 
        pass
    return False

@st.cache_data
def load_mw_intel():
    mesa_df = pd.DataFrame()
    files_to_try = [
        "Mesa_Mike_Enriched.csv", 
        "Mesa_Mike_Enriched (1).csv",
        "Mesa Mike Enriched.csv", 
        "Mesa Mike US Station Data - Sheet1.csv"
    ]
    
    actual_file = None
    try:
        files_in_dir = os.listdir('.')
        lower_files = {f.lower(): f for f in files_in_dir}
        for name in files_to_try:
            if name.lower() in lower_files:
                actual_file = lower_files[name.lower()]
                break
    except Exception: 
        pass
        
    actual_files = [actual_file] if actual_file else files_to_try

    for file in actual_files:
        try:
            mesa_df = pd.read_csv(file, dtype=str)
            if not mesa_df.empty:
                mesa_df['Frequency'] = pd.to_numeric(mesa_df['FREQ'], errors='coerce')
                mesa_df['Callsign'] = mesa_df['CALL'].fillna("Unknown").apply(clean_callsign)
                mesa_df['State'] = mesa_df['STATE'].fillna("XX")
                mesa_df['City'] = mesa_df['CITY'].fillna("Unknown")
                if 'County' in mesa_df.columns:
                    mesa_df['County'] = mesa_df['County'].fillna("Unknown")
                else:
                    mesa_df['County'] = "Unknown"
                mesa_df['LAT'] = pd.to_numeric(mesa_df['LAT'], errors='coerce')
                mesa_df['LON'] = pd.to_numeric(mesa_df['LON'], errors='coerce')
                mesa_df['Grid'] = mesa_df.apply(lambda x: get_grid(x['LAT'], x['LON']), axis=1)
                mesa_df['Country'] = "United States"
                mesa_df['Slogan'] = ""
                break
        except Exception: 
            continue
            
    try:
        intl_files = [
            "Summer of DX - International Database - MW - International Station List.csv",
            "Summer of DX - International Database - MW - International Station List (2).csv",
            "International_Master_Cleaned.csv"
        ]
        
        actual_intl_file = None
        try:
            files_in_dir = os.listdir('.')
            lower_files = {f.lower(): f for f in files_in_dir}
            for name in intl_files:
                if name.lower() in lower_files:
                    actual_intl_file = lower_files[name.lower()]
                    break
        except Exception: 
            pass
            
        actual_intl_files = [actual_intl_file] if actual_intl_file else intl_files

        intl_df = pd.DataFrame()
        for f in actual_intl_files:
            try:
                temp_df = pd.read_csv(f, dtype=str)
                if not temp_df.empty:
                    intl_df = temp_df
                    break
            except Exception: 
                continue
                
        if not intl_df.empty:
            f_col = find_col(intl_df, ['Frequency', 'Freq', 'FREQ'])
            c_col = find_col(intl_df, ['Station Call Letters', 'Station', 'Call', 'Callsign', 'CALL'])
            cty_col = find_col(intl_df, ['Station City', 'City', 'CITY'])
            st_col = find_col(intl_df, ['Station State/Province', 'State', 'Prov', 'STATE'])
            ctr_col = find_col(intl_df, ['Station Country', 'Country', 'COUNTRY'])
            lat_col = find_col(intl_df, ['Station Lat', 'Lat', 'LAT'])
            lon_col = find_col(intl_df, ['Station Long', 'Long', 'Lon', 'LON'])

            if f_col and c_col:
                intl_df['Frequency'] = pd.to_numeric(intl_df[f_col], errors='coerce')
                intl_df['Callsign'] = intl_df[c_col].fillna("Unknown").apply(clean_callsign)
                intl_df['City'] = intl_df[cty_col].fillna("Unknown") if cty_col else "Unknown"
                intl_df['State'] = intl_df[st_col].fillna("DX") if st_col else "DX"
                intl_df['Country'] = intl_df[ctr_col].fillna("Unknown") if ctr_col else "Unknown"
                intl_df['County'] = " - "
                intl_df['Slogan'] = ""
                
                intl_df['LAT'] = pd.to_numeric(intl_df[lat_col], errors='coerce') if lat_col else 0.0
                intl_df['LON'] = pd.to_numeric(intl_df[lon_col], errors='coerce') if lon_col else 0.0
                intl_df['Grid'] = intl_df.apply(lambda x: get_grid(x['LAT'], x['LON']), axis=1)
                
                intl_df['Callsign'] = intl_df.apply(lambda x: standardize_cuban_station(x['Callsign'], x['Frequency'], x['Country']), axis=1)
                
                keep_cols = ['Frequency', 'Callsign', 'City', 'State', 'County', 'Country', 'LAT', 'LON', 'Grid', 'Slogan']
                if not mesa_df.empty:
                    mesa_df = pd.concat([mesa_df[keep_cols], intl_df[keep_cols]], ignore_index=True)
                else:
                    mesa_df = intl_df[keep_cols]
    except Exception: 
        pass
        
    return mesa_df

@st.cache_data
def load_fm_intel():
    files_to_try = [
        "WTFDA Enriched.csv",
        "WTFDA_Enriched.csv", 
        "WTFDA Enriched (1).csv", 
        "WTFDA Enriched.CSV",
        "FM Challenge - Station List and Data - WTFDA Data.csv",
        "sporadic-es-data-analysis.FMList_Data.wtfda_fips.csv"
    ]
    
    actual_file = None
    try:
        files_in_dir = os.listdir('.')
        lower_files = {f.lower(): f for f in files_in_dir}
        for name in files_to_try:
            if name.lower() in lower_files:
                actual_file = lower_files[name.lower()]
                break
    except Exception: 
        pass
        
    actual_files = [actual_file] if actual_file else files_to_try

    for file in actual_files:
        try:
            df = pd.read_csv(file, dtype=str)
            if not df.empty:
                f_col = find_col(df, ['Frequency', 'Freq', 'FREQ', 'MHz'])
                c_col = find_col(df, ['Callsign', 'Call Letters', 'Call', 'CALL'])
                cty_col = find_col(df, ['City', 'CITY'])
                st_col = find_col(df, ['S_P', 'S/P', 'State', 'Prov', 'STATE'])
                pi_col = find_col(df, ['PI Code', 'PI', 'PI_Code'])
                co_col = find_col(df, ['County', 'COUNTY'])
                lat_col = find_col(df, ['Decimal_Lat', 'Lat', 'LAT', 'Lat_N', 'Lat-N'])
                lon_col = find_col(df, ['Decimal_Lon', 'Long', 'Lon', 'LON', 'Long_W', 'Long-W'])
                ctr_col = find_col(df, ['Country', 'COUNTRY'])
                slg_col = find_col(df, ['Slogan', 'SLOGAN'])

                df['Frequency'] = pd.to_numeric(df[f_col], errors='coerce') if f_col else 0.0
                df['Callsign'] = df[c_col].fillna("Unknown").apply(clean_callsign) if c_col else "Unknown"
                df['City'] = df[cty_col].fillna("Unknown") if cty_col else "Unknown"
                df['State'] = df[st_col].fillna("XX") if st_col else "XX"
                df['Slogan'] = df[slg_col].fillna("").apply(lambda x: str(x).strip()) if slg_col else ""
                
                df['PI Code'] = df[pi_col].fillna("").apply(lambda x: str(x).strip().upper()) if pi_col else ""
                df['PI Code'] = df['PI Code'].apply(lambda x: "" if x in ["NONE", "0", "0000", ""] else x)
                
                df['County'] = df[co_col].fillna("Unknown") if co_col else "Unknown"
                df['LAT'] = pd.to_numeric(df[lat_col], errors='coerce') if lat_col else 0.0
                df['LON'] = pd.to_numeric(df[lon_col], errors='coerce') if lon_col else 0.0
                df['Grid'] = df.apply(lambda x: get_grid(x['LAT'], x['LON']), axis=1)
                
                if ctr_col:
                    df['Country'] = df[ctr_col].fillna("United States").apply(
                        lambda x: itu_map.get(str(x).strip().upper(), str(x).strip().title())
                    )
                    df['Country'] = df['Country'].apply(
                        lambda x: "United States" if str(x).upper() in ["USA", "UNITED STATES"] else x
                    )
                else:
                    df['Country'] = "United States"
                    
                df['County'] = df.apply(lambda x: x['County'] if x['Country'] == "United States" else " - ", axis=1)
                
                return df
        except Exception: 
            continue
            
    return pd.DataFrame()

@st.cache_data(ttl=86400)
def load_nwr_intel():
    text = ""
    try:
        files_in_dir = os.listdir('.')
        lower_files = {f.lower(): f for f in files_in_dir}
        if "ccl.js" in lower_files:
            with open(lower_files["ccl.js"], 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
    except Exception:
        pass
        
    if not text:
        try:
            url = "https://www.weather.gov/source/nwr/JS/CCL.js"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                text = response.read().decode('utf-8')
        except Exception:
            pass

    if text:
        try:
            lines = text.splitlines()
            data = {}
            for line in lines:
                line = line.strip()
                if not line or line.startswith('var '): continue
                
                match = re.match(r'([A-Z]+)\[(\d+)\]\s*=\s*"(.*?)";', line)
                if match:
                    var_name = match.group(1)
                    idx = int(match.group(2))
                    val = match.group(3)
                    
                    if idx not in data:
                        data[idx] = {}
                    data[idx][var_name] = val

            df = pd.DataFrame.from_dict(data, orient='index')
            
            if not df.empty:
                f_col = find_col(df, ['FREQ'])
                c_col = find_col(df, ['CALLSIGN'])
                cty_col = find_col(df, ['SITENAME'])
                st_col = find_col(df, ['ST'])
                lat_col = find_col(df, ['LAT'])
                lon_col = find_col(df, ['LON'])
                
                if f_col and c_col:
                    df['Frequency'] = pd.to_numeric(df[f_col], errors='coerce')
                    df['Callsign'] = df[c_col].fillna("Unknown").apply(clean_callsign)
                    df['City'] = df[cty_col].fillna("Unknown") if cty_col else "Unknown"
                    df['State'] = df[st_col].fillna("XX") if st_col else "XX"
                    df['Country'] = "United States"
                    df['County'] = " - "
                    df['LAT'] = pd.to_numeric(df[lat_col], errors='coerce') if lat_col else 0.0
                    df['LON'] = pd.to_numeric(df[lon_col], errors='coerce') if lon_col else 0.0
                    df['Grid'] = df.apply(lambda x: get_grid(x['LAT'], x['LON']), axis=1)
                    df['Slogan'] = "NOAA Weather Radio"
                    
                    df = df.dropna(subset=['Frequency'])
                    df = df[(df['Frequency'] >= 162.4) & (df['Frequency'] <= 162.55)]
                    
                    return df[['Frequency', 'Callsign', 'City', 'State', 'County', 'Country', 'LAT', 'LON', 'Grid', 'Slogan']]
        except Exception:
            pass
            
    return pd.DataFrame()

@st.cache_data
def load_countries():
    files_to_try = [
        "Summer of DX - International Database - MW - International Station List.csv",
        "Summer of DX - International Database - MW - International Station List (2).csv",
        "International_Master_Cleaned.csv",
        "DX Central _ MW Frequency Challenge -All Seasons Master Logbook - Sheet64.csv"
    ]
    
    actual_file = None
    try:
        files_in_dir = os.listdir('.')
        lower_files = {f.lower(): f for f in files_in_dir}
        for name in files_to_try:
            if name.lower() in lower_files:
                actual_file = lower_files[name.lower()]
                break
    except Exception: 
        pass
        
    actual_files = [actual_file] if actual_file else files_to_try

    for file in actual_files:
        try:
            df = pd.read_csv(file)
            c_col = find_col(df, ['Station Country', 'Country', 'Country Name'])
            if c_col: 
                return df[c_col].dropna().sort_values().unique().tolist()
        except Exception: 
            continue
            
    return ["Canada", "Mexico", "United States"]

mw_db = load_mw_intel()
fm_db = load_fm_intel()
nwr_db = load_nwr_intel()
country_list = load_countries()

us_states = ["AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"]
can_prov = ["AB", "BC", "MB", "NB", "NL", "NS", "NT", "NU", "ON", "PE", "QC", "SK", "YT"]
mex_states = ["AGU", "BCN", "BCS", "CAM", "CHP", "CHH", "CMX", "COA", "COL", "DUR", "GUA", "GRO", "HID", "JAL", "MEX", "MIC", "MOR", "NAY", "NLE", "OAX", "PUE", "QUE", "ROO", "SLP", "SIN", "SON", "TAB", "TAM", "TLA", "VER", "YUC", "ZAC"]

def get_state_list(country):
    if country == "United States": 
        return us_states
    if country == "Canada": 
        return can_prov
    if country == "Mexico": 
        return mex_states
    return ["DX"]

# --- 6. SESSION STATE ROUTING & PROFILE ---
if 'sys_state' not in st.session_state: 
    st.session_state.sys_state = "OPERATOR_LOGIN"
    
if 'matrix_unlocked' not in st.session_state: 
    st.session_state.matrix_unlocked = False
    
if 'operator_profile' not in st.session_state:
    st.session_state.operator_profile = { 
        "name": "", 
        "city": "", 
        "state": "", 
        "country": "United States", 
        "lat": 0.0, 
        "lon": 0.0 
    }

def nav_to(page): 
    st.session_state.sys_state = page

if st.session_state.sys_state != "OPERATOR_LOGIN":
    prof = st.session_state.operator_profile
    if not prof.get('name') or float(prof.get('lat', 0.0)) == 0.0 or float(prof.get('lon', 0.0)) == 0.0:
        st.session_state.sys_state = "OPERATOR_LOGIN"
        st.rerun()

# --- 7. SIDEBAR NAVIGATION ---
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
            if st.button("NWR INTERCEPT REPORT", key="nav_nwr"): 
                nav_to("NWR_LOG")
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
            st.session_state.op_lat_val = float(saved_data.get("lat", 0.0))
            st.session_state.op_lon_val = float(saved_data.get("lon", 0.0))
            st.session_state.ls_loaded = True
            if st.session_state.op_name_val:
                st.success(f"LOCAL PROFILE DETECTED: {st.session_state.op_name_val.upper()}")
            
        for key in ['op_name_val', 'op_city_val', 'op_state_val', 'op_lat_val', 'op_lon_val']:
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
                all_freqs = sorted(mw_db['Frequency'].dropna().unique().tolist())
                f_freq = c1.selectbox("FREQ (kHz)", ["All"] + all_freqs, key=f"mw_f1_{fk}")
                f_call = c2.text_input("CALLSIGN", key=f"mw_f2_{fk}")
                f_city = c3.text_input("CITY", key=f"mw_f3_{fk}")
                f_state = c4.selectbox("STATE", ["All"] + sorted(mw_db['State'].dropna().unique().tolist()), key=f"mw_f4_{fk}")
                
                c5, c6, c7, c8 = st.columns(4)
                all_countries = sorted(mw_db['Country'].dropna().unique().tolist()) if 'Country' in mw_db.columns else ["United States"]
                f_ctry = c5.selectbox("COUNTRY", ["All"] + all_countries, key=f"mw_f5_{fk}")
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

        with tab_manual:
            st.write("INITIATE UNLISTED / INTERNATIONAL PROTOCOL...")
            spacing = st.radio("CHANNEL SPACING", ["10 kHz (Region 2)", "9 kHz (Regions 1 & 3)"], horizontal=True)
            step_val = 10 if "10" in spacing else 9
                
            c_m1, c_m2, c_m3 = st.columns(3)
            man_freq = c_m1.number_input("MANUAL FREQ (kHz)", min_value=531, max_value=1710, value=540, step=step_val, key="man_mw")
            man_call = c_m2.text_input("STATION ID")
            
            all_db_countries = sorted(mw_db['Country'].dropna().unique().tolist()) if not mw_db.empty else ["United States"]
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
                    
                    c_i9, c_i10 = st.columns(2)
                    map_prop = c_i9.selectbox("PROPAGATION", cols, index=get_idx(["propa", "mode"], cols), key="mw_map_9")
                    map_notes = c_i10.selectbox("NOTES / DETAILS", cols, index=get_idx(["remarks", "detail", "info", "comment"], cols), key="mw_map_11")
                    
                    if st.button("> PROCESS & TRANSMIT BULK PAYLOAD", key="mw_bulk_btn"):
                        sheet = get_gsheet()
                        if sheet is None: 
                            st.error("🚨 DATALINK OFFLINE. Streamlit Secrets not configured.")
                        else:
                            bulk_rows = []
                            op = st.session_state.operator_profile
                            
                            for _, row in df_import.iterrows():
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
                                    ""
                                ]
                                bulk_rows.append(["" if pd.isna(item) else (item.item() if hasattr(item, 'item') else item) for item in r_data])
                                
                            try:
                                sheet.append_rows(bulk_rows)
                                st.success(f"### [ {len(bulk_rows)} RECORDS TRANSMITTED ]")
                                st.balloons()
                            except Exception as e: 
                                st.error(f"BULK FAILED: {e}")
                except Exception as e: 
                    st.error(f"FILE PARSING ERROR: {e}")

        st.markdown("#### 3. SUBMIT INTERCEPT")
        with st.form("mw_submit_form", clear_on_submit=True):
            col_s1, col_s2 = st.columns(2)
            now = datetime.datetime.now(datetime.timezone.utc)
            
            log_date = col_s1.date_input("DATE (UTC)", value=now.date())
            log_time = col_s2.text_input("TIME (UTC)", value=now.strftime("%H%M"))
            log_notes = st.text_area("PROGRAMMING / INTERCEPT NOTES")
            
            submit_log = st.form_submit_button("> TRANSMIT REPORT TO SERVER")
            if submit_log:
                if not target_data: 
                    st.error("TARGET NOT ACQUIRED. SELECT OR ENTER A STATION.")
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
                                ""
                            ]
                            sheet.append_row(["" if pd.isna(item) else (item.item() if hasattr(item, 'item') else item) for item in row_data])
                            st.markdown("### [ TRANSMISSION SUCCESSFUL ]")
                        except Exception as e: 
                            st.error(f"TRANSMISSION FAILED: {e}")

    # --- 8D. FM INTERCEPT ROOM ---
    elif st.session_state.sys_state == "FM_LOG":
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
                all_freqs = sorted(fm_db['Frequency'].dropna().unique().tolist())
                f_freq = c1.selectbox("FREQ (MHz)", ["All"] + all_freqs, key=f"fm_f1_{fk}")
                f_call = c2.text_input("CALLSIGN", key=f"fm_f2_{fk}")
                f_city = c3.text_input("CITY", key=f"fm_f3_{fk}")
                f_state = c4.selectbox("STATE", ["All"] + sorted(fm_db['State'].dropna().unique().tolist()), key=f"fm_f4_{fk}")
                
                c5, c6, c7, c8 = st.columns(4)
                all_countries = sorted(fm_db['Country'].dropna().unique().tolist()) if 'Country' in fm_db.columns else ["United States"]
                f_ctry = c5.selectbox("COUNTRY", ["All"] + all_countries, key=f"fm_f5_{fk}")
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

        with tab_manual:
            st.write("INITIATE UNLISTED PROTOCOL...")
            c_m1, c_m2, c_m3 = st.columns(3)
            man_freq = c_m1.number_input("MANUAL FREQ (MHz)", min_value=87.7, max_value=107.9, value=88.1, step=0.1, key="man_fm")
            man_call = c_m2.text_input("STATION ID", key="man_fm_call")
            
            all_db_countries_fm = sorted(fm_db['Country'].dropna().unique().tolist()) if not fm_db.empty else ["United States"]
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
                    
                    if st.button("> PROCESS & TRANSMIT BULK PAYLOAD", key="fm_bulk_btn"):
                        sheet = get_gsheet()
                        if sheet is None: 
                            st.error("🚨 DATALINK OFFLINE. Streamlit Secrets not configured.")
                        else:
                            bulk_rows = []
                            op = st.session_state.operator_profile
                            entry_cat_val = f"ROVER ({rover_grid})" if r_cat == "ROVER" and rover_grid else r_cat
                            
                            for _, row in df_import.iterrows():
                                raw_freq = row[map_freq] if map_freq != "<Skip>" else ""
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
                                    format_date_import(row[map_date]) if map_date != "<Skip>" else "", 
                                    format_time_import(row[map_time]) if map_time != "<Skip>" else "", 
                                    round(dist_val, 1), 
                                    map_notes_val, 
                                    rds_val, 
                                    pi_val, 
                                    map_fm_prop(row[map_prop]) if map_prop != "<Skip>" else "Other", 
                                    station_county, 
                                    entry_cat_val, 
                                    "", 
                                    ""
                                ]
                                bulk_rows.append(["" if pd.isna(item) else (item.item() if hasattr(item, 'item') else item) for item in r_data])
                                
                            try:
                                sheet.append_rows(bulk_rows)
                                st.success(f"### [ {len(bulk_rows)} RECORDS TRANSMITTED ]")
                                st.balloons()
                            except Exception as e: 
                                st.error(f"BULK FAILED: {e}")
                except Exception as e: 
                    st.error(f"FILE ERROR: {e}")

        st.markdown("#### 3. SUBMIT INTERCEPT")
        with st.form("fm_submit_form", clear_on_submit=True):
            col_s1, col_s2, col_s3 = st.columns(3)
            now = datetime.datetime.now(datetime.timezone.utc)
            
            log_date = col_s1.date_input("DATE (UTC)", value=now.date(), key="fm_dt")
            log_time = col_s2.text_input("TIME (UTC)", value=now.strftime("%H%M"), key="fm_tm")
            log_prop = col_s3.selectbox("PROPAGATION MODE", ["Tropo", "Sporadic E", "Meteor Scatter", "Aurora", "Local"])
            
            c_p1, c_p2 = st.columns(2)
            log_rds = c_p1.selectbox("RDS DECODE?", ["No", "Yes"])
            default_pi = target_data["pi"] if "pi" in target_data else ""
            log_pi = c_p2.text_input("PI CODE", value=default_pi)
            log_notes = st.text_area("PROGRAMMING / INTERCEPT NOTES", key="fm_nts")
            
            submit_log = st.form_submit_button("> TRANSMIT REPORT TO SERVER")
            if submit_log:
                if not target_data: 
                    st.error("TARGET NOT ACQUIRED. SELECT OR ENTER A STATION.")
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
                                ""
                            ]
                            sheet.append_row(["" if pd.isna(item) else (item.item() if hasattr(item, 'item') else item) for item in row_data])
                            st.markdown("### [ TRANSMISSION SUCCESSFUL ]")
                        except Exception as e: 
                            st.error(f"FAILED: {e}")
                            
    # --- 8D. NWR INTERCEPT ROOM ---
    elif st.session_state.sys_state == "NWR_LOG":
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
            st.write("ACCESSING WTFDA DATABANKS...")
            if nwr_db.empty: 
                st.error("[ SYSTEM ALERT ] DATABANK OFFLINE: NWR database not found.")
            else:
                if 'nwr_filter_key' not in st.session_state: 
                    st.session_state.nwr_filter_key = 0
                    
                def reset_nwr_filters(): 
                    st.session_state.nwr_filter_key += 1
                
                c_btn1, c_btn2 = st.columns([1.5, 3.5])
                c_btn1.button("[ RESET SEARCH FILTERS ]", on_click=reset_nwr_filters, key="nwr_reset")
                if c_btn2.button("[ REFRESH STATION DATA ]", key="sync_nwr"):
                    get_logged_dict.clear()
                    load_nwr_intel.clear()
                    st.rerun()
                
                fk = st.session_state.nwr_filter_key
                c1, c2, c3, c4 = st.columns(4)
                all_freqs = sorted(nwr_db['Frequency'].dropna().unique().tolist())
                f_freq = c1.selectbox("FREQ (MHz)", ["All"] + all_freqs, key=f"nwr_f1_{fk}")
                f_call = c2.text_input("CALLSIGN", key=f"nwr_f2_{fk}")
                f_city = c3.text_input("CITY", key=f"nwr_f3_{fk}")
                f_state = c4.selectbox("STATE", ["All"] + sorted(nwr_db['State'].dropna().unique().tolist()), key=f"nwr_f4_{fk}")
                
                c5, c6, c7, c8 = st.columns(4)
                all_countries = sorted(nwr_db['Country'].dropna().unique().tolist()) if 'Country' in nwr_db.columns else ["United States"]
                f_ctry = c5.selectbox("COUNTRY", ["All"] + all_countries, key=f"nwr_f5_{fk}")
                f_county = c6.text_input("COUNTY/PARISH", key=f"nwr_f6_{fk}")
                f_grid = c7.text_input("GRID", key=f"nwr_f7_{fk}")
                f_status = c8.selectbox("STATUS", ["All", "Logged Only", "Not Logged Only"], key=f"nwr_f8_{fk}")
                
                results = nwr_db.copy()
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
                    logged_dict = get_logged_dict(st.session_state.operator_profile.get('name', ''), "NWR")
                    results['Is_Logged'] = results.apply(lambda r: check_is_logged_fm(r['Frequency'], r['Callsign'], r.get('Slogan', ''), r['City'], r['State'], r['Country'], logged_dict), axis=1)
                    if f_status == "Logged Only": 
                        results = results[results['Is_Logged']]
                        st.markdown("<div style='font-size: 0.9rem; color: #1bd2d4; opacity: 0.7; margin-top: -15px; margin-bottom: 10px;'>*To export your logs to a CSV, choose 'Logged Only' from the status filter.*</div>", unsafe_allow_html=True)
                        full_logs_df = get_full_logs_df(st.session_state.operator_profile.get('name', ''), "NWR")
                        if not full_logs_df.empty:
                            csv_data = full_logs_df.to_csv(index=False).encode('utf-8')
                            st.download_button(label="📥 DOWNLOAD MY LOGS (CSV)", data=csv_data, file_name=f"My_NWR_Logs_{datetime.date.today().strftime('%Y%m%d')}.csv", mime="text/csv")
                    else: 
                        results = results[~results['Is_Logged']]
                        st.markdown("<div style='font-size: 0.9rem; color: #1bd2d4; opacity: 0.7; margin-top: -15px; margin-bottom: 10px;'>*To export your logs to a CSV, choose 'Logged Only' from the status filter.*</div>", unsafe_allow_html=True)
                else:
                    st.markdown("<div style='font-size: 0.9rem; color: #1bd2d4; opacity: 0.7; margin-top: -15px; margin-bottom: 10px;'>*To export your logs to a CSV, choose 'Logged Only' from the status filter.*</div>", unsafe_allow_html=True)
                        
                st.write(f"> {len(results)} TARGETS FOUND:")
                st.markdown("<div style='font-size: 0.9rem; color: #1bd2d4; opacity: 0.7; margin-top: -15px; margin-bottom: 10px;'>*Source: Weather.gov (NWR)*</div>", unsafe_allow_html=True)
                
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
                    
                    logged_dict = get_logged_dict(st.session_state.operator_profile.get('name', ''), "NWR")
                    results['Is_Logged'] = results.apply(lambda r: check_is_logged_fm(r['Frequency'], r['Callsign'], r.get('Slogan', ''), r['City'], r['State'], r['Country'], logged_dict), axis=1)
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

        with tab_manual:
            st.write("INITIATE UNLISTED PROTOCOL...")
            c_m1, c_m2, c_m3 = st.columns(3)
            man_freq = c_m1.number_input("MANUAL FREQ (MHz)", min_value=162.400, max_value=162.550, value=162.400, step=0.025, key="man_nwr")
            man_call = c_m2.text_input("STATION ID", key="man_nwr_call")
            
            all_db_countries_nwr = sorted(nwr_db['Country'].dropna().unique().tolist()) if not nwr_db.empty else ["United States"]
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
                    
                    if st.button("> PROCESS & TRANSMIT BULK PAYLOAD", key="nwr_bulk_btn"):
                        sheet = get_gsheet()
                        if sheet is None: 
                            st.error("🚨 DATALINK OFFLINE. Streamlit Secrets not configured.")
                        else:
                            bulk_rows = []
                            op = st.session_state.operator_profile
                            entry_cat_val = f"ROVER ({rover_grid})" if r_cat == "ROVER" and rover_grid else r_cat
                            
                            for _, row in df_import.iterrows():
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
                                    map_notes_val, 
                                    rds_val, 
                                    pi_val, 
                                    map_fm_prop(row[map_prop]) if map_prop != "<Skip>" else "Other", 
                                    station_county, 
                                    entry_cat_val, 
                                    "", 
                                    ""
                                ]
                                bulk_rows.append(["" if pd.isna(item) else (item.item() if hasattr(item, 'item') else item) for item in r_data])
                                
                            try:
                                sheet.append_rows(bulk_rows)
                                st.success(f"### [ {len(bulk_rows)} RECORDS TRANSMITTED ]")
                                st.balloons()
                            except Exception as e: 
                                st.error(f"BULK FAILED: {e}")
                except Exception as e: 
                    st.error(f"FILE ERROR: {e}")

        st.markdown("#### 3. SUBMIT INTERCEPT")
        with st.form("nwr_submit_form", clear_on_submit=True):
            col_s1, col_s2, col_s3 = st.columns(3)
            now = datetime.datetime.now(datetime.timezone.utc)
            
            log_date = col_s1.date_input("DATE (UTC)", value=now.date(), key="nwr_dt")
            log_time = col_s2.text_input("TIME (UTC)", value=now.strftime("%H%M"), key="nwr_tm")
            log_prop = col_s3.selectbox("PROPAGATION MODE", ["Tropo", "Sporadic E", "Meteor Scatter", "Aurora", "Local"], key="nwr_prop")
            
            log_notes = st.text_area("PROGRAMMING / INTERCEPT NOTES", key="nwr_nts")
            
            submit_log = st.form_submit_button("> TRANSMIT REPORT TO SERVER")
            if submit_log:
                if not target_data: 
                    st.error("TARGET NOT ACQUIRED. SELECT OR ENTER A STATION.")
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
                                ""
                            ]
                            sheet.append_row(["" if pd.isna(item) else (item.item() if hasattr(item, 'item') else item) for item in row_data])
                            st.markdown("### [ TRANSMISSION SUCCESSFUL ]")
                        except Exception as e: 
                            st.error(f"FAILED: {e}")

    # --- 8E. THE CLANDESTINE MATRIX (BOUNTY ROOM) ---
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

    # --- 8F. GLOBAL INTELLIGENCE (DASHBOARD STUB) ---
    elif st.session_state.sys_state == "DASHBOARD":
        st.markdown("### [ GLOBAL INTELLIGENCE DATABANKS ]")
        st.write("ESTABLISHING CONNECTION TO PLOTLY SERVERS...")
        st.markdown("""
        <div class="classified-box">
        <strong>SYSTEM STATUS:</strong> DATA VISUALIZATION MODULES COMPILING.<br>
        STANDBY FOR CHOROPLETH MAPS, VOLUME TIMELINES, AND OPERATOR LEADERBOARDS.
        </div>
        """, unsafe_allow_html=True)
