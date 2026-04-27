import streamlit as st
import pandas as pd
import gspread
import math
import os
import json
import re
import urllib.request
import maidenhead as mh
from geopy.geocoders import Nominatim
from google.oauth2.service_account import Credentials
from modules.importers import clean_callsign, standardize_cuban_station, simplify_string, super_clean, find_col

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
                mesa_df['County'] = mesa_df.get('County', pd.Series(["Unknown"] * len(mesa_df))).fillna("Unknown")
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
                co_col = find_col(df, ['COUNTY'])
                
                if f_col and c_col:
                    df['Frequency'] = pd.to_numeric(df[f_col], errors='coerce')
                    df['Callsign'] = df[c_col].fillna("Unknown").apply(clean_callsign)
                    df['City'] = df[cty_col].fillna("Unknown") if cty_col else "Unknown"
                    df['State'] = df[st_col].fillna("XX") if st_col else "XX"
                    df['Country'] = "United States"
                    if co_col:
                        df['County'] = df[co_col].fillna(" - ")
                    else:
                        df['County'] = " - "
                    df['LAT'] = pd.to_numeric(df[lat_col], errors='coerce') if lat_col else 0.0
                    df['LON'] = pd.to_numeric(df[lon_col], errors='coerce') if lon_col else 0.0
                    df['Grid'] = df.apply(lambda x: get_grid(x['LAT'], x['LON']), axis=1)
                    df['Slogan'] = "NOAA Weather Radio"
                    
                    df = df.dropna(subset=['Frequency'])
                    df = df[(df['Frequency'] >= 162.4) & (df['Frequency'] <= 162.55)]
                    
                    df = df[['Frequency', 'Callsign', 'City', 'State', 'County', 'Country', 'LAT', 'LON', 'Grid', 'Slogan']]
                    df = df.drop_duplicates(subset=['Callsign', 'Frequency']).reset_index(drop=True)
                    return df
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
                    
                    if l_call and c_val and l_call != "UNKNOWN" and c_val != "UNKNOWN" and (l_call in c_val or c_val in l_call):
                        return True
                        
                    elif l_city and city_val and l_city != "UNKNOWN" and city_val != "UNKNOWN" and (l_city in city_val or city_val in l_city) and l_ctry == ctry_val:
                        return True
                        
                    elif l_call and slogan_val and l_call != "UNKNOWN" and slogan_val != "UNKNOWN" and (l_call in slogan_val or slogan_val in l_call):
                        return True
                        
    except Exception: 
        pass
    return False

# --- THE DATA FORGE (DASHBOARD SCORING ENGINE) ---
@st.cache_data(ttl=600)
def load_global_dashboard_data():
    try:
        sheet = get_gsheet()
        if sheet is None: 
            return pd.DataFrame()
            
        vals = sheet.get_all_values()
        if len(vals) < 2: 
            return pd.DataFrame()
            
        cols = [f"Col_{i}" for i in range(len(vals[1]))]
        df = pd.DataFrame(vals[1:], columns=cols)
        
        c_dxer = cols[0]
        c_dxloc = cols[1]
        c_dxst = cols[2]
        c_dxco = cols[3]
        c_band = cols[4]
        c_freqm = cols[5]
        c_freqf = cols[6]
        c_call = cols[7]
        c_stcity = cols[9]
        c_stst = cols[10]
        c_stco = cols[11]
        c_stgrid = cols[13]
        c_date = cols[14]
        c_time = cols[15]
        c_dist = cols[16]
        c_notes = cols[17]
        c_rds = cols[18]
        c_pi = cols[19]
        c_prop = cols[20]
        c_county = cols[21]
        c_cat = cols[22]
        c_sdr = cols[25] if len(cols) > 25 else None
        
        clean_df = pd.DataFrame()
        clean_df['DXer'] = df[c_dxer].str.strip().str.upper()
        clean_df['DXer_City'] = df[c_dxloc]
        clean_df['DXer_State'] = df[c_dxst]
        clean_df['DXer_Country'] = df[c_dxco]
        clean_df['Band'] = df[c_band].str.strip().str.upper()
        
        clean_df['Frequency'] = df.apply(lambda x: x[c_freqm] if x[c_band].strip().upper() == "AM" else x[c_freqf], axis=1)
        clean_df['Freq_Num'] = pd.to_numeric(clean_df['Frequency'].str.replace(',', '.'), errors='coerce')
        
        clean_df['Callsign'] = df[c_call]
        clean_df['City'] = df[c_stcity]
        clean_df['State'] = df[c_stst]
        clean_df['Country'] = df[c_stco]
        clean_df['Station_Grid'] = df[c_stgrid]
        clean_df['Date_Str'] = df[c_date]
        clean_df['Time_Str'] = df[c_time]
        clean_df['Distance'] = pd.to_numeric(df[c_dist], errors='coerce').fillna(0.0)
        clean_df['Prop_Mode'] = df[c_prop]
        clean_df['County'] = df[c_county]
        clean_df['Category'] = df[c_cat]
        clean_df['SDR_Used'] = df[c_sdr].str.strip().str.title() if c_sdr else "Yes"
        
        clean_df['Date_Obj'] = pd.to_datetime(clean_df['Date_Str'], errors='coerce')
        clean_df['Month'] = clean_df['Date_Obj'].dt.month_name()
        
        clean_df['Dist_Points'] = clean_df['Distance'].apply(lambda x: math.floor(x / 100) + 1 if x >= 0 else 0)
        clean_df['SDR_Bonus'] = clean_df['SDR_Used'].apply(lambda x: 5 if str(x) == "No" else 0)
        clean_df['Base_Score'] = clean_df['Dist_Points'] + clean_df['SDR_Bonus']
        
        st_lat = []
        st_lon = []
        dx_lat = []
        dx_lon = []
        
        mw_db = load_mw_intel()
        fm_db = load_fm_intel()
        nwr_db = load_nwr_intel()
        
        mw_dict = mw_db.drop_duplicates(subset=['Callsign', 'Frequency']).set_index(['Callsign', 'Frequency'])[['LAT', 'LON']].to_dict('index') if not mw_db.empty else {}
        fm_dict = fm_db.drop_duplicates(subset=['Callsign', 'Frequency']).set_index(['Callsign', 'Frequency'])[['LAT', 'LON']].to_dict('index') if not fm_db.empty else {}
        nwr_dict = nwr_db.drop_duplicates(subset=['Callsign', 'Frequency']).set_index(['Callsign', 'Frequency'])[['LAT', 'LON']].to_dict('index') if not nwr_db.empty else {}
        
        for _, row in clean_df.iterrows():
            band = row['Band']
            call = row['Callsign']
            freq = row['Freq_Num']
            
            lat, lon = 0.0, 0.0
            if band == "AM" and (call, freq) in mw_dict:
                lat, lon = mw_dict[(call, freq)]['LAT'], mw_dict[(call, freq)]['LON']
            elif band == "FM" and (call, freq) in fm_dict:
                lat, lon = fm_dict[(call, freq)]['LAT'], fm_dict[(call, freq)]['LON']
            elif band == "NWR" and (call, freq) in nwr_dict:
                lat, lon = nwr_dict[(call, freq)]['LAT'], nwr_dict[(call, freq)]['LON']
                
            st_lat.append(lat)
            st_lon.append(lon)
            
            dx_l, dx_ln = 0.0, 0.0
            dx_lat.append(dx_l)
            dx_lon.append(dx_ln)
            
        clean_df['ST_Lat'] = st_lat
        clean_df['ST_Lon'] = st_lon
        clean_df['DX_Lat'] = dx_lat
        clean_df['DX_Lon'] = dx_lon
        
        return clean_df
    except Exception as e:
        st.error(f"Dashboard Data Forge Error: {e}")
        return pd.DataFrame()
