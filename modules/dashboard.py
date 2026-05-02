import streamlit as st
import pandas as pd
import pydeck as pdk
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import datetime
import time
import requests
import re
import math
from modules.data_forge import load_global_dashboard_data, get_lat_lon_from_city
from modules.awards import manual_award_claim_popup
from modules.importers import calculate_distance  # INJECTED FOR DYNAMIC DISTANCE RECALCULATION

# --- CYAN ESPIONAGE AESTHETIC ---
CYAN_SCALE = [
    '#0a4040', 
    '#139a9b', 
    '#1bd2d4', 
    '#a3e8e9', 
    '#ffffff'
]

# RGB Scale for PyDeck Heatmap
CYAN_RGB_SCALE = [
    [10, 64, 64], 
    [19, 154, 155], 
    [27, 210, 212], 
    [163, 232, 233], 
    [255, 255, 255]
]

# --- STATE FIPS DICTIONARY FOR COUNTY MAPPING (ABBREVIATIONS) ---
FIPS_TO_ABBR = {
    '01': 'AL', '02': 'AK', '04': 'AZ', '05': 'AR', '06': 'CA',
    '08': 'CO', '09': 'CT', '10': 'DE', '11': 'DC', '12': 'FL',
    '13': 'GA', '15': 'HI', '16': 'ID', '17': 'IL', '18': 'IN',
    '19': 'IA', '20': 'KS', '21': 'KY', '22': 'LA', '23': 'ME',
    '24': 'MD', '25': 'MA', '26': 'MI', '27': 'MN', '28': 'MS',
    '29': 'MO', '30': 'MT', '31': 'NE', '32': 'NV', '33': 'NH',
    '34': 'NJ', '35': 'NM', '36': 'NY', '37': 'NC', '38': 'ND',
    '39': 'OH', '40': 'OK', '41': 'OR', '42': 'PA', '44': 'RI',
    '45': 'SC', '46': 'SD', '47': 'TN', '48': 'TX', '49': 'UT',
    '50': 'VT', '51': 'VA', '53': 'WA', '54': 'WV', '55': 'WI',
    '56': 'WY'
}

# --- GLOBAL BAND CONFIGURATION ---
BAND_CONFIG = {
    "MW": {"min": 530, "max": 1700, "unit": "kHz"},
    "FM": {"min": 87.7, "max": 107.9, "unit": "MHz", "step": 0.2},
    "NWR": {"min": 162.400, "max": 162.550, "unit": "MHz", "step": 0.025}
}

@st.cache_data
def get_custom_county_geojson():
    url = "https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json"
    try:
        resp = requests.get(url, timeout=10)
        geojson = resp.json()
        for feature in geojson['features']:
            state_fips = str(feature['properties'].get('STATE', '')).zfill(2)
            state_abbr = FIPS_TO_ABBR.get(state_fips, "").upper()
            county_name = str(feature['properties'].get('NAME', '')).strip().upper()
            
            # Sanitizer: Strip all punctuation and spaces to guarantee match
            county_name_clean = re.sub(r'[^A-Z0-9]', '', county_name)
            
            map_id = f"{state_abbr}_{county_name_clean}"
            feature['id'] = map_id
        return geojson
    except Exception:
        return None

@st.cache_data
def generate_grid_geojson(_grids):
    features = []
    for g in _grids:
        g = str(g).strip()
        if len(g) >= 4:
            g4 = g[:4].upper()
            # Validator: Ensure it's a valid Maidenhead format (Letter, Letter, Number, Number)
            if not (g4[0].isalpha() and g4[1].isalpha() and g4[2].isdigit() and g4[3].isdigit()):
                continue
            try:
                lon = (ord(g4[0]) - ord('A')) * 20 - 180 + int(g4[2]) * 2
                lat = (ord(g4[1]) - ord('A')) * 10 - 90 + int(g4[3]) * 1
                features.append({
                    "type": "Feature",
                    "id": g4,
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[lon, lat], [lon + 2, lat], [lon + 2, lat + 1], [lon, lat + 1], [lon, lat]]]
                    },
                    "properties": {"Grid4": g4}
                })
            except Exception:
                pass
    return {"type": "FeatureCollection", "features": features}

def get_target_circle(lat, lon, radius_mi, pts=64):
    coords = []
    lat1, lon1 = math.radians(lat), math.radians(lon)
    d = radius_mi / 3959.0
    for i in range(pts + 1):
        brng = math.radians(i * (360.0 / pts))
        lat2 = math.asin(math.sin(lat1)*math.cos(d) + math.cos(lat1)*math.sin(d)*math.cos(brng))
        lon2 = lon1 + math.atan2(math.sin(brng)*math.sin(d)*math.cos(lat1), math.cos(d)-math.sin(lat1)*math.sin(lat2))
        coords.append([math.degrees(lon2), math.degrees(lat2)])
    return coords

def render_dashboard():
    df = load_global_dashboard_data()
    
    if df.empty:
        st.error("🚨 SYSTEM ALERT: DATABANK OFFLINE OR EMPTY.")
        st.stop()
        
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=VT323&display=swap');
    @font-face {
        font-family: 'Digital7';
        src: url('https://db.onlinewebfonts.com/t/8e23f95e5927c3ba779261a86851219b.woff2') format('woff2');
    }
    
    [data-testid="stDataFrame"] th { text-align: center !important; }
    [data-testid="stDataFrame"] td { text-align: center !important; }
    [data-testid="stElementToolbar"] { display: none !important; }
    
    .leader-box { border: 1px solid #139a9b; padding: 10px; background-color: #050505; text-align: center; box-shadow: inset 0px 0px 10px rgba(19, 154, 155, 0.1); }
    .leader-title { color: #139a9b; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 5px; }
    .leader-name { color: #ffffff; font-size: 1.4rem; line-height: 1.2; }
    .leader-score { color: #1bd2d4; font-size: 1.1rem; }
    
    .flyout-box { border: 1px solid #139a9b; padding: 15px; background-color: #050505; box-shadow: 0px 0px 10px rgba(19, 154, 155, 0.2); }
    .flyout-title { color: #1bd2d4; margin-top: 0; font-size: 1.8rem; text-transform: uppercase; border-bottom: 1px dashed #139a9b; padding-bottom: 5px; }
    .flyout-header { color: #1bd2d4; font-size: 0.85rem; margin-top: 15px; text-transform: uppercase; letter-spacing: 1px; }
    .flyout-val { font-size: 1.8rem; color: #ffffff; line-height: 1.1; }
    .flyout-sub { font-size: 0.95rem; color: #ffffff; margin-top: 2px; }
    .flyout-micro { font-size: 0.9rem; color: #ffffff; margin-top: 2px; }
    
    div[data-testid="stPills"] button { background-color: #050505 !important; border: 1px solid #139a9b !important; color: #1bd2d4 !important; font-family: 'VT323', monospace !important; }
    div[data-testid="stPills"] button[aria-checked="true"] { background-color: #139a9b !important; color: #050505 !important; box-shadow: 0px 0px 10px rgba(27,210,212,0.6); }

    .radio-chassis { background-color: #1a1a1a; border: 4px solid #333; border-radius: 10px; padding: 20px; box-shadow: 10px 10px 0px #000; margin-bottom: 20px; }
    .lcd-recess { background-color: #0a2020; border: 4px inset #000; padding: 15px; text-align: center; margin-bottom: 15px; }
    .lcd-text { font-family: 'Digital7', monospace; color: #1bd2d4; font-size: 4rem; text-shadow: 0px 0px 15px rgba(27,210,212,0.8); line-height: 1; }
    .lcd-marquee { font-family: 'VT323', monospace; color: #139a9b; font-size: 1.5rem; overflow: hidden; white-space: nowrap; }
    .marquee-content { display: inline-block; animation: marquee 10s linear infinite; }
    @keyframes marquee { 0% { transform: translateX(100%); } 100% { transform: translateX(-100%); } }
    
    div.stButton > button[key*="transmit"] { background-color: #8b0000 !important; color: white !important; border: 2px solid #ff0000 !important; font-weight: bold !important; box-shadow: 0px 0px 10px rgba(255,0,0,0.5) !important; }
    div.stButton > button[key*="transmit"]:hover { background-color: #ff0000 !important; box-shadow: 0px 0px 20px rgba(255,0,0,0.8) !important; }
    
    /* Notification Buttons */
    div.stButton > button[key*="award"] { border: 1px dashed #1bd2d4 !important; background-color: #0a1a1a !important; color: #1bd2d4 !important; }
    div.stButton > button[key*="award"]:hover { background-color: #1bd2d4 !important; color: #050505 !important; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("<h1 style='text-align: center; color: #1bd2d4; text-shadow: 0px 0px 10px rgba(27,210,212,0.8);'>GLOBAL INTELLIGENCE COMMAND</h1>", unsafe_allow_html=True)
    
    # --- HELPER: TACTICAL FORMATTER ---
    def get_top_with_count(series):
        s = series.replace(['', ' - ', 'Unknown'], pd.NA).dropna()
        if not s.empty:
            vc = s.value_counts()
            return f"{vc.index[0]} ({vc.iloc[0]})"
        return "N/A"

    # --- SESSION STATE INITIALIZATION ---
    if 'dash_nav' not in st.session_state: st.session_state.dash_nav = "OVERVIEW"
    if 'filter_reset_key' not in st.session_state: st.session_state.filter_reset_key = 0
    if 'matrix_loc' not in st.session_state: st.session_state.matrix_loc = None
    if 'matrix_map_key' not in st.session_state: st.session_state.matrix_map_key = 2000000
    
    if 'geo_us_state' not in st.session_state: st.session_state.geo_us_state = None
    if 'geo_intl_ctry' not in st.session_state: st.session_state.geo_intl_ctry = None
    if 'geo_can_prov' not in st.session_state: st.session_state.geo_can_prov = None
    if 'geo_county' not in st.session_state: st.session_state.geo_county = None
    if 'geo_grid' not in st.session_state: st.session_state.geo_grid = None
    if 'geo_st_loc' not in st.session_state: st.session_state.geo_st_loc = None
    if 'geo_map_key' not in st.session_state: st.session_state.geo_map_key = 3000000
    
    if 'tuner_freq' not in st.session_state: st.session_state.tuner_freq = None
    if 'tuner_band' not in st.session_state: st.session_state.tuner_band = "MW"
    if 'tuner_mw_step' not in st.session_state: st.session_state.tuner_mw_step = 10
    if 'transmit_active' not in st.session_state: st.session_state.transmit_active = False
    if 'direct_freq_input' not in st.session_state: st.session_state.direct_freq_input = ""
    
    if 'radar_playing' not in st.session_state: st.session_state.radar_playing = False
    if 'radar_p_idx' not in st.session_state: st.session_state.radar_p_idx = 0

    def reset_flyouts():
        st.session_state.matrix_loc = None
        st.session_state.geo_us_state = None
        st.session_state.geo_intl_ctry = None
        st.session_state.geo_can_prov = None
        st.session_state.geo_county = None
        st.session_state.geo_grid = None
        st.session_state.geo_st_loc = None
        st.session_state.transmit_active = False

    def reset_filters():
        st.session_state.filter_reset_key += 1

    # Frequency Tuner Input Callback
    def process_direct_freq_entry():
        val = re.sub(r'[^0-9]', '', st.session_state.direct_freq_input)
        if val:
            band_sel = st.session_state.tuner_band
            if band_sel == "FM" and len(val) >= 3:
                final_f = float(val[:-1] + "." + val[-1])
            elif band_sel == "NWR" and len(val) >= 6:
                final_f = float(val[:3] + "." + val[3:])
            else:
                final_f = float(val)
            
            if BAND_CONFIG[band_sel]["min"] <= final_f <= BAND_CONFIG[band_sel]["max"]:
                st.session_state.tuner_freq = final_f
            else:
                st.toast("🚨 FREQUENCY OUT OF BAND LIMITS", icon="⚠️")
        st.session_state.direct_freq_input = ""

    # =====================================================================
    # THE PRE-FLIGHT GLOBAL GEOCODER & RECALCULATION OVERRIDE
    # =====================================================================
    df['Date_TS'] = pd.to_datetime(df['Date_Str'], errors='coerce')
    df['Date_Obj'] = df['Date_TS'].dt.date
    
    if 'DX_Lat' not in df.columns: df['DX_Lat'] = 0.0
    if 'DX_Lon' not in df.columns: df['DX_Lon'] = 0.0
    if 'ST_Lat' not in df.columns: df['ST_Lat'] = 0.0
    if 'ST_Lon' not in df.columns: df['ST_Lon'] = 0.0
    
    # Universal Geocoder Override: Fix Missing DXer Coordinates
    mask_dx = df['DX_Lat'].isna() | (df['DX_Lat'] == 0.0)
    if mask_dx.any():
        missing_dx = df[mask_dx][['DXer_City', 'DXer_State', 'DXer_Country']].drop_duplicates()
        lats, lons = [], []
        for _, r in missing_dx.iterrows():
            city_q = f"{r['DXer_City']}, {r['DXer_State']}" if pd.notna(r.get('DXer_State')) and r.get('DXer_State') not in ['', 'XX', 'DX'] else r['DXer_City']
            lat, lon = get_lat_lon_from_city(city_q, r['DXer_Country'])
            lats.append(lat)
            lons.append(lon)
        missing_dx['New_DX_Lat'], missing_dx['New_DX_Lon'] = lats, lons
        df = df.merge(missing_dx, on=['DXer_City', 'DXer_State', 'DXer_Country'], how='left')
        df['DX_Lat'] = df['DX_Lat'].where(~mask_dx, df['New_DX_Lat'])
        df['DX_Lon'] = df['DX_Lon'].where(~mask_dx, df['New_DX_Lon'])
        df.drop(columns=['New_DX_Lat', 'New_DX_Lon'], inplace=True)

    # Universal Geocoder Override: Fix Missing Station Coordinates (Null Island Anomaly)
    mask_st = df['ST_Lat'].isna() | (df['ST_Lat'] == 0.0)
    if mask_st.any():
        missing_st = df[mask_st][['City', 'State', 'Country']].drop_duplicates()
        lats, lons = [], []
        for _, r in missing_st.iterrows():
            city_q = f"{r['City']}, {r['State']}" if pd.notna(r.get('State')) and r.get('State') not in ['', 'XX', 'DX', ' - '] else r['City']
            lat, lon = get_lat_lon_from_city(city_q, r['Country'])
            lats.append(lat)
            lons.append(lon)
        missing_st['New_ST_Lat'], missing_st['New_ST_Lon'] = lats, lons
        df = df.merge(missing_st, on=['City', 'State', 'Country'], how='left')
        df['ST_Lat'] = df['ST_Lat'].where(~mask_st, df['New_ST_Lat'])
        df['ST_Lon'] = df['ST_Lon'].where(~mask_st, df['New_ST_Lon'])
        df.drop(columns=['New_ST_Lat', 'New_ST_Lon'], inplace=True)

    # DYNAMIC DISTANCE RECALCULATOR (Catches Manual 0-mile logs)
    df['Distance'] = df.apply(lambda r: calculate_distance(r['DX_Lat'], r['DX_Lon'], r['ST_Lat'], r['ST_Lon']) if (pd.isna(r['Distance']) or r['Distance'] == 0.0) else r['Distance'], axis=1)
    
    # Recalculate Base Score with New Distance (UPDATED FOR 0-199 MILE THRESHOLD)
    df['Dist_Points'] = df['Distance'].apply(lambda x: max(1, math.floor(x / 100)) if x >= 0 else 0)
    df['Base_Score'] = df['Dist_Points'] + df['SDR_Bonus']
    
    df['Mid_Lat'] = (df['DX_Lat'] + df['ST_Lat']) / 2
    df['Mid_Lon'] = (df['DX_Lon'] + df['ST_Lon']) / 2

    # =====================================================================
    st.markdown("<hr style='margin-top: 5px; margin-bottom: 15px;'>", unsafe_allow_html=True)
    
    # --- GLOBAL FILTERS ---
    fk = st.session_state.filter_reset_key
    st.markdown("<div style='color:#139a9b; margin-bottom: 5px;'>[ GLOBAL INTERCEPT FILTERS ]</div>", unsafe_allow_html=True)
    
    c_f1, c_f2, c_f3, c_f4 = st.columns(4)
    f_dxer = c_f1.selectbox("DXer Name", ["ALL"] + sorted(df['DXer'].dropna().unique().tolist()), key=f"f_dxer_{fk}")
    f_dx_state = c_f2.selectbox("DXer State/Prov", ["ALL"] + sorted(df['DXer_State'].dropna().unique().tolist()), key=f"f_dx_st_{fk}")
    f_dx_ctry = c_f3.selectbox("DXer Country", ["ALL"] + sorted(df['DXer_Country'].dropna().unique().tolist()), key=f"f_dx_co_{fk}")
    f_band = c_f4.selectbox("Band", ["ALL", "AM", "FM", "NWR"], index=0, key=f"f_band_{fk}")

    c_f5, c_f6, c_f7, c_f8 = st.columns(4)
    f_prop = c_f5.selectbox("Propagation (FM/NWR)", ["ALL", "Local", "Tropo", "Sporadic E", "Meteor Scatter", "Aurora"], key=f"f_prop_{fk}")
    f_freq = c_f6.selectbox("Frequency", ["ALL"] + sorted(df['Freq_Num'].dropna().unique().tolist()), key=f"f_freq_{fk}")
    f_stat = c_f7.selectbox("Station", ["ALL"] + sorted(df['Callsign'].dropna().unique().tolist()), key=f"f_stat_{fk}")
    f_st_state = c_f8.selectbox("Station State/Prov", ["ALL"] + sorted(df['State'].dropna().unique().tolist()), key=f"f_st_st_{fk}")

    c_f9, c_f10, c_f11, c_f12 = st.columns(4)
    f_st_ctry = c_f9.selectbox("Station Country", ["ALL"] + sorted(df['Country'].dropna().unique().tolist()), key=f"f_st_co_{fk}")
    f_grid = c_f10.selectbox("Station Gridsquare", ["ALL"] + sorted(df['Station_Grid'].dropna().unique().tolist()), key=f"f_grid_{fk}")
    f_county = c_f11.selectbox("Station County/Parish", ["ALL"] + sorted(df['County'].dropna().unique().tolist()), key=f"f_county_{fk}")
    f_month = c_f12.selectbox("Month", ["ALL"] + sorted(df['Month'].dropna().unique().tolist()), key=f"f_month_{fk}")

    st.button("[ RESET ALL FILTERS ]", on_click=reset_filters, key=f"btn_reset_{fk}")

    # Apply Filters
    filt_df = df.copy()
    if f_dxer != "ALL": filt_df = filt_df[filt_df['DXer'] == f_dxer]
    if f_dx_state != "ALL": filt_df = filt_df[filt_df['DXer_State'] == f_dx_state]
    if f_dx_ctry != "ALL": filt_df = filt_df[filt_df['DXer_Country'] == f_dx_ctry]
    if f_band != "ALL": filt_df = filt_df[filt_df['Band'] == f_band]
    if f_freq != "ALL": filt_df = filt_df[filt_df['Freq_Num'] == f_freq]
    if f_stat != "ALL": filt_df = filt_df[filt_df['Callsign'] == f_stat]
    if f_st_state != "ALL": filt_df = filt_df[filt_df['State'] == f_st_state]
    if f_st_ctry != "ALL": filt_df = filt_df[filt_df['Country'] == f_st_ctry]
    if f_grid != "ALL": filt_df = filt_df[filt_df['Station_Grid'] == f_grid]
    if f_county != "ALL": filt_df = filt_df[filt_df['County'] == f_county]
    if f_month != "ALL": filt_df = filt_df[filt_df['Month'] == f_month]

    if f_prop != "ALL":
        filt_df = filt_df[(filt_df['Band'] == 'AM') | (filt_df['Prop_Mode'] == f_prop)]
        
    if filt_df.empty:
        st.warning("NO TELEMETRY MATCHES CURRENT FILTER PARAMETERS.")
        st.stop()

    # --- THE MULTIPLIER SCORING ENGINE (UPDATED TO UNIQUE LOGS ONLY) ---
    def calculate_scores(target_df):
        if target_df.empty: 
            return pd.DataFrame(columns=['DXer', 'Base_Score', 'Multiplier', 'Bonus', 'Total'])
        
        # 1. PURGE DUPLICATES: Only score a station once per band per DXer.
        unique_logs = target_df.drop_duplicates(subset=['DXer', 'Band', 'Callsign', 'Freq_Num']).copy()
        
        # 2. SEPARATE MULTIPLIERS (US/CAN/MEX vs. Rest of World)
        valid_state_countries = ['United States', 'Canada', 'Mexico']
        
        # Calculate Base Score & State Multipliers (Only for valid countries)
        base_scores = unique_logs.groupby(['DXer', 'Band']).agg(
            Band_Base=('Base_Score', 'sum')
        ).reset_index()
        
        state_mults = unique_logs[unique_logs['Country'].isin(valid_state_countries)].groupby(['DXer', 'Band']).agg(
            U_States=('State', 'nunique')
        ).reset_index()
        
        # Calculate Country Multipliers (Excluding US/CAN/MEX to avoid double-dipping)
        ctry_mults = unique_logs[~unique_logs['Country'].isin(valid_state_countries)].groupby(['DXer', 'Band']).agg(
            U_Ctry=('Country', 'nunique')
        ).reset_index()

        # Merge them back together
        pb = base_scores.merge(state_mults, on=['DXer', 'Band'], how='left')
        pb = pb.merge(ctry_mults, on=['DXer', 'Band'], how='left').fillna(0)
        
        # 3. CALCULATE MULTIPLIERS
        pb['Band_Mult'] = pb['U_States'] + pb['U_Ctry']
        pb['Band_Mult'] = pb['Band_Mult'].apply(lambda x: x if x > 0 else 1) 
        pb['Band_Total_Base'] = pb['Band_Base'] * pb['Band_Mult']
        
        s = pb.groupby('DXer').agg(
            Base_Score=('Band_Base', 'sum'),
            Multiplier=('Band_Mult', 'sum'), 
            Base_x_Mult=('Band_Total_Base', 'sum')
        ).reset_index()
        
        # 4. CALCULATE CONSISTENCY BONUS (10+ Logs per month on AM/FM)
        bonus_eligible = target_df[target_df['Band'].isin(['AM', 'FM'])]
        if not bonus_eligible.empty:
            b_counts = bonus_eligible.groupby(['DXer', 'Band', 'Month']).size().reset_index(name='Logs')
            b_counts['Bonus'] = b_counts['Logs'].apply(lambda x: 100 if x >= 10 else 0)
            b_sum = b_counts.groupby('DXer')['Bonus'].sum().reset_index()
            s = s.merge(b_sum, on='DXer', how='left').fillna(0)
            s['Total'] = s['Base_x_Mult'] + s['Bonus']
        else:
            s['Bonus'] = 0
            s['Total'] = s['Base_x_Mult']
            
        return s.sort_values('Total', ascending=False)

    def get_leader_data(band_target):
        b_df = filt_df[filt_df['Band'] == band_target]
        s = calculate_scores(b_df)
        if s.empty: return "N/A", "0 pts"
        leader = s.iloc[0]
        return leader['DXer'], f"{int(leader['Total']):,} pts"

    def render_geo_flyout(title_prefix, location_name, loc_df):
        st.markdown("<div class='flyout-box'>", unsafe_allow_html=True)
        st.markdown(f"<div class='flyout-title'>📍 {title_prefix}: {location_name}</div>", unsafe_allow_html=True)
        if st.button("❌ CLOSE INTEL", use_container_width=True, key=f"close_flyout_{title_prefix}"):
            reset_flyouts()
            st.session_state.geo_map_key += 1
            st.rerun()
            
        tot_v = len(loc_df)
        mw_v = len(loc_df[loc_df['Band'] == 'AM'])
        fm_v = len(loc_df[loc_df['Band'] == 'FM'])
        nwr_v = len(loc_df[loc_df['Band'] == 'NWR'])
        pct_vol = (tot_v / len(filt_df)) * 100 if len(filt_df) > 0 else 0
        
        st.markdown("<div class='flyout-header'>LOG VOLUME (RECEIVED FROM REGION)</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='flyout-val'>{tot_v:,} Logs</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='flyout-micro'>MW: {mw_v:,} | FM: {fm_v:,} | NWR: {nwr_v:,}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='flyout-sub'>{pct_vol:.2f}% of Total Global Volume</div>", unsafe_allow_html=True)
        
        tot_s = loc_df['Callsign'].nunique()
        mw_s = loc_df[loc_df['Band'] == 'AM']['Callsign'].nunique()
        fm_s = loc_df[loc_df['Band'] == 'FM']['Callsign'].nunique()
        nwr_s = loc_df[loc_df['Band'] == 'NWR']['Callsign'].nunique()
        st.markdown("<div class='flyout-header'>UNIQUE STATIONS IN REGION</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='flyout-val'>{tot_s:,}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='flyout-micro'>MW: {mw_s:,} | FM: {fm_s:,} | NWR: {nwr_s:,}</div>", unsafe_allow_html=True)
        
        if not loc_df.empty:
            st.markdown("<div class='flyout-header'>MOST HEARD STATION (OVERALL)</div>", unsafe_allow_html=True)
            most_heard = loc_df.groupby(['Freq_Num', 'Callsign', 'City', 'State']).size().reset_index(name='Logs').sort_values('Logs', ascending=False).iloc[0]
            st.markdown(f"<div class='flyout-val'>{most_heard['Callsign']}</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='flyout-micro'>{most_heard['Freq_Num']} MHz • {most_heard['City']}, {most_heard['State']} • {most_heard['Logs']} Logs</div>", unsafe_allow_html=True)
            
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("<div class='flyout-header'>GRIDSQUARES</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='flyout-sub'>{loc_df['Station_Grid'].nunique():,}</div>", unsafe_allow_html=True)
        with c2:
            st.markdown("<div class='flyout-header'>COUNTIES</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='flyout-sub'>{loc_df['County'].nunique():,}</div>", unsafe_allow_html=True)
            
        st.markdown("<div class='flyout-header'>TOP 5 HEARD STATIONS</div>", unsafe_allow_html=True)
        for b in ['AM', 'FM', 'NWR']:
            b_df = loc_df[loc_df['Band'] == b]
            if not b_df.empty:
                st.markdown(f"<div class='flyout-micro' style='color:#139a9b; margin-top:5px;'>{b} BAND</div>", unsafe_allow_html=True)
                top_s = b_df.groupby(['Freq_Num', 'Callsign', 'City']).size().reset_index(name='Logs').sort_values('Logs', ascending=False).head(5)
                st.dataframe(top_s, hide_index=True, use_container_width=True)
                
        st.markdown("<div class='flyout-header'>TOP INTERCEPTING AGENTS</div>", unsafe_allow_html=True)
        top_agents = loc_df.groupby('DXer').size().reset_index(name='Logs').sort_values('Logs', ascending=False).head(3)
        st.dataframe(top_agents, hide_index=True, use_container_width=True)
        
        st.markdown("<div class='flyout-header'>TOP 5 RECEIVING LOCATIONS</div>", unsafe_allow_html=True)
        for b in ['AM', 'FM', 'NWR']:
            b_df = loc_df[loc_df['Band'] == b]
            if not b_df.empty:
                st.markdown(f"<div class='flyout-micro' style='color:#139a9b; margin-top:5px;'>{b} BAND</div>", unsafe_allow_html=True)
                top_l = b_df.groupby('DXer_City').size().reset_index(name='Logs').sort_values('Logs', ascending=False).head(5)
                st.dataframe(top_l, hide_index=True, use_container_width=True)
                
        st.markdown("<div class='flyout-header'>TOP INTERCEPTING STATES</div>", unsafe_allow_html=True)
        loc_us_dx = loc_df[loc_df['DXer_Country'] == 'United States']
        t_st_mw = get_top_with_count(loc_us_dx[loc_us_dx['Band'] == 'AM']['DXer_State'])
        t_st_fm = get_top_with_count(loc_us_dx[loc_us_dx['Band'] == 'FM']['DXer_State'])
        t_st_nwr = get_top_with_count(loc_us_dx[loc_us_dx['Band'] == 'NWR']['DXer_State'])
        st.markdown(f"<div class='flyout-micro'><b>MW:</b> {t_st_mw} | <b>FM:</b> {t_st_fm} | <b>NWR:</b> {t_st_nwr}</div>", unsafe_allow_html=True)
        
        st.markdown("<div class='flyout-header'>TOP INTERCEPTING COUNTRIES</div>", unsafe_allow_html=True)
        loc_intl_dx = loc_df[loc_df['DXer_Country'] != 'United States']
        t_co_mw = get_top_with_count(loc_intl_dx[loc_intl_dx['Band'] == 'AM']['DXer_Country'])
        t_co_fm = get_top_with_count(loc_intl_dx[loc_intl_dx['Band'] == 'FM']['DXer_Country'])
        st.markdown(f"<div class='flyout-micro'><b>MW:</b> {t_co_mw} | <b>FM:</b> {t_co_fm}</div>", unsafe_allow_html=True)
        
        st.markdown("<div class='flyout-header'>FURTHEST RECEPTIONS</div>", unsafe_allow_html=True)
        for b in ['AM', 'FM', 'NWR']:
            b_df = loc_df[loc_df['Band'] == b]
            if not b_df.empty:
                f_r = b_df.sort_values('Distance', ascending=False).iloc[0]
                prop_str = f" • Prop: {f_r['Prop_Mode']}" if b in ['FM', 'NWR'] and f_r['Prop_Mode'] not in ['', ' - '] else ""
                st.markdown(f"<div class='flyout-val' style='font-size:1.2rem; color:#1bd2d4;'>{b}: {f_r['Distance']:,.0f} mi</div>", unsafe_allow_html=True)
                st.markdown(f"<div class='flyout-micro'>{f_r['Freq_Num']} MHz - {f_r['Callsign']} ({f_r['City']}, {f_r['State']}, {f_r['Country']}){prop_str}<br>Caught by {f_r['DXer']} on {f_r['Date_Str']} at {f_r['Time_Str']}</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # =====================================================================
    # VIEW 1: MISSION OVERVIEW
    # =====================================================================
    if st.session_state.dash_nav == "OVERVIEW":
        st.markdown("### 📊 OPERATIONAL OVERVIEW")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Logs", f"{len(filt_df):,}")
        m2.metric("Total Unique Stations", f"{filt_df['Callsign'].nunique():,}")
        m3.metric("Total Unique DXers", f"{filt_df['DXer'].nunique():,}")
        m4.metric("Furthest Reception", f"{filt_df['Distance'].max():,.0f} mi")
        m5, m6, m7, m8 = st.columns(4)
        us_only = filt_df[filt_df['Country'] == 'United States']
        m5.metric("US States Heard (Inc DC)", us_only['State'].nunique())
        m6.metric("Countries Heard", filt_df['Country'].nunique())
        m7.metric("Unique Gridsquares", filt_df['Station_Grid'].nunique())
        m8.metric("Unique Counties/Parishes", filt_df['County'].nunique())
        am_name, am_score = get_leader_data('AM')
        fm_name, fm_score = get_leader_data('FM')
        nwr_name, nwr_score = get_leader_data('NWR')
        m9, m10, m11 = st.columns(3)
        m9.markdown(f"<div class='leader-box'><div class='leader-title'>MW Score Leader</div><div class='leader-name'>{am_name}</div><div class='leader-score'>{am_score}</div></div>", unsafe_allow_html=True)
        m10.markdown(f"<div class='leader-box'><div class='leader-title'>FM Score Leader</div><div class='leader-name'>{fm_name}</div><div class='leader-score'>{fm_score}</div></div>", unsafe_allow_html=True)
        m11.markdown(f"<div class='leader-box'><div class='leader-title'>NWR Score Leader</div><div class='leader-name'>{nwr_name}</div><div class='leader-score'>{nwr_score}</div></div>", unsafe_allow_html=True)
        st.markdown("---")
        st.markdown("### 📡 SUBMITTED LOGGINGS")
        table_df = filt_df.copy()
        table_df['Prop_Mode'] = table_df.apply(lambda x: " - " if x['Band'] == "AM" else x['Prop_Mode'], axis=1)
        table_df['Station_Grid'] = table_df.apply(lambda x: " - " if x['Country'] != "United States" else x['Station_Grid'], axis=1)
        table_df['County'] = table_df.apply(lambda x: " - " if x['Country'] != "United States" else x['County'], axis=1)
        display_cols = ['DXer', 'Date_Str', 'Time_Str', 'Band', 'Freq_Num', 'Callsign', 'City', 'State', 'Country', 'Station_Grid', 'County', 'Distance', 'Prop_Mode']
        rename_map = {'Date_Str': 'Date', 'Time_Str': 'Time', 'Freq_Num': 'Frequency', 'Callsign': 'Station', 'Station_Grid': 'Gridsquare', 'Prop_Mode': 'Propagation'}
        view_df = table_df[display_cols].rename(columns=rename_map)
        st.dataframe(view_df, hide_index=True, use_container_width=True, column_config={"Distance": st.column_config.NumberColumn("Distance (mi)", format="%.1f")})

    # =====================================================================
    # VIEW 2: CLASSIFICATION MATRIX
    # =====================================================================
    elif st.session_state.dash_nav == "MATRIX":
        st.markdown("### 🗄️ CLASSIFICATION MATRIX")
        mx_tab = st.pills("MATRIX SECTOR", ["SCORE LEDGER", "GRID LEDGER", "COUNTY/PARISH LEDGER", "INTERCEPT LEDGER", "STATE LEDGER", "COUNTRY LEDGER", "AGENT LOCATION MAP"], default="SCORE LEDGER")
        def build_progress_board(target_df, group_col, metric_col, target_goal):
            if target_df.empty: return pd.DataFrame()
            brd = target_df.groupby(group_col)[metric_col].nunique().reset_index(name='Count').sort_values('Count', ascending=False).head(10)
            brd['Status'] = brd['Count'].apply(lambda x: "🥇 CENTURY CLUB ACHIEVED" if x >= target_goal and target_goal == 100 else ("🥇 MASTER ACHIEVED" if x >= target_goal else "⏳ IN PROGRESS"))
            brd['Progress'] = brd['Count'].apply(lambda x: target_goal if x >= target_goal else x)
            return brd

        if mx_tab == "SCORE LEDGER":
            c1, c2 = st.columns(2)
            c3, c4 = st.columns(2)
            
            def render_score_df(b_target):
                df_slice = filt_df if b_target == "ALL" else filt_df[filt_df['Band'] == b_target]
                s_df = calculate_scores(df_slice).head(10)
                if not s_df.empty:
                    disp = s_df[['DXer', 'Base_Score', 'Multiplier', 'Bonus', 'Total']].rename(columns={'Base_Score': 'Base', 'Multiplier': 'Mult (x)'})
                    return disp
                return pd.DataFrame()

            with c1:
                st.markdown("#### TOTAL SCORE")
                st.dataframe(render_score_df("ALL"), hide_index=True, use_container_width=True)
            with c2:
                st.markdown("#### MW SCORE")
                st.dataframe(render_score_df("AM"), hide_index=True, use_container_width=True)
            with c3:
                st.markdown("#### FM SCORE")
                st.dataframe(render_score_df("FM"), hide_index=True, use_container_width=True)
            with c4:
                st.markdown("#### NWR SCORE")
                st.dataframe(render_score_df("NWR"), hide_index=True, use_container_width=True)

        elif mx_tab == "GRID LEDGER":
            if st.button("🎖️ QUALIFY FOR CENTURY CLUB? CLICK HERE TO NOTIFY HIGH COMMAND TO PROCURE YOUR AWARD.", use_container_width=True, key="btn_grid_award"):
                manual_award_claim_popup("Grids")
            st.markdown("<hr style='border-color:#333; margin-top:5px; margin-bottom:15px;'>", unsafe_allow_html=True)
            
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("#### MW GRID MASTERS")
                st.dataframe(build_progress_board(filt_df[filt_df['Band'] == 'AM'], 'DXer', 'Station_Grid', 100), hide_index=True, use_container_width=True, column_config={"Count": "Grids", "Progress": st.column_config.ProgressColumn("To 100", min_value=0, max_value=100)})
            with c2:
                st.markdown("#### FM GRID MASTERS")
                st.dataframe(build_progress_board(filt_df[filt_df['Band'] == 'FM'], 'DXer', 'Station_Grid', 100), hide_index=True, use_container_width=True, column_config={"Count": "Grids", "Progress": st.column_config.ProgressColumn("To 100", min_value=0, max_value=100)})
            st.markdown("---")
            c3, c4 = st.columns(2)
            with c3:
                st.markdown("#### NWR GRID MASTERS")
                st.dataframe(build_progress_board(filt_df[filt_df['Band'] == 'NWR'], 'DXer', 'Station_Grid', 25), hide_index=True, use_container_width=True, column_config={"Count": "Grids", "Progress": st.column_config.ProgressColumn("To 25", min_value=0, max_value=25)})

        elif mx_tab == "COUNTY/PARISH LEDGER":
            if st.button("🎖️ QUALIFY FOR CENTURY CLUB? CLICK HERE TO NOTIFY HIGH COMMAND TO PROCURE YOUR AWARD.", use_container_width=True, key="btn_county_award"):
                manual_award_claim_popup("Counties")
            st.markdown("<hr style='border-color:#333; margin-top:5px; margin-bottom:15px;'>", unsafe_allow_html=True)
            
            us_df = filt_df[filt_df['Country'] == 'United States']
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("#### MW COUNTY MASTERS")
                st.dataframe(build_progress_board(us_df[us_df['Band'] == 'AM'], 'DXer', 'County', 100), hide_index=True, use_container_width=True, column_config={"Count": "Counties", "Progress": st.column_config.ProgressColumn("To 100", min_value=0, max_value=100)})
            with c2:
                st.markdown("#### FM COUNTY MASTERS")
                st.dataframe(build_progress_board(us_df[us_df['Band'] == 'FM'], 'DXer', 'County', 100), hide_index=True, use_container_width=True, column_config={"Count": "Counties", "Progress": st.column_config.ProgressColumn("To 100", min_value=0, max_value=100)})
            st.markdown("---")
            c3, c4 = st.columns(2)
            with c3:
                st.markdown("#### NWR COUNTY MASTERS")
                st.dataframe(build_progress_board(us_df[us_df['Band'] == 'NWR'], 'DXer', 'County', 25), hide_index=True, use_container_width=True, column_config={"Count": "Counties", "Progress": st.column_config.ProgressColumn("To 25", min_value=0, max_value=25)})

        elif mx_tab == "INTERCEPT LEDGER":
            def build_log_board(b_target=None):
                t_df = filt_df if not b_target else filt_df[filt_df['Band'] == b_target]
                return t_df.groupby('DXer')['Callsign'].nunique().reset_index(name='Unique Stations').sort_values('Unique Stations', ascending=False)
            
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("#### TOTAL STATIONS")
                st.dataframe(build_log_board(), hide_index=True, use_container_width=True)
            with c2:
                st.markdown("#### MW STATIONS")
                st.dataframe(build_log_board('AM'), hide_index=True, use_container_width=True)
                
            st.markdown("---")
            
            c3, c4 = st.columns(2)
            with c3:
                st.markdown("#### FM STATIONS")
                st.dataframe(build_log_board('FM'), hide_index=True, use_container_width=True)
            with c4:
                st.markdown("#### NWR STATIONS")
                st.dataframe(build_log_board('NWR'), hide_index=True, use_container_width=True)

        elif mx_tab == "STATE LEDGER":
            us_df = filt_df[filt_df['Country'] == 'United States']
            def build_state_board(b_target=None):
                t_df = us_df if not b_target else us_df[us_df['Band'] == b_target]
                return t_df.groupby('DXer')['State'].nunique().reset_index(name='States Heard').sort_values('States Heard', ascending=False)
            
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("#### STATES (ALL)")
                st.dataframe(build_state_board(), hide_index=True, use_container_width=True)
            with c2:
                st.markdown("#### STATES (MW)")
                st.dataframe(build_state_board('AM'), hide_index=True, use_container_width=True)
                
            st.markdown("---")
            
            c3, c4 = st.columns(2)
            with c3:
                st.markdown("#### STATES (FM)")
                st.dataframe(build_state_board('FM'), hide_index=True, use_container_width=True)
            with c4:
                st.markdown("#### STATES (NWR)")
                st.dataframe(build_state_board('NWR'), hide_index=True, use_container_width=True)

        elif mx_tab == "COUNTRY LEDGER":
            def build_ctry_board(b_target=None):
                t_df = filt_df if not b_target else filt_df[filt_df['Band'] == b_target]
                return t_df.groupby('DXer')['Country'].nunique().reset_index(name='Countries Heard').sort_values('Countries Heard', ascending=False)
            c1, c2, c3 = st.columns(3)
            c1.markdown("#### COUNTRIES (ALL)")
            c1.dataframe(build_ctry_board(), hide_index=True, use_container_width=True)
            c2.markdown("#### COUNTRIES (MW)")
            c2.dataframe(build_ctry_board('AM'), hide_index=True, use_container_width=True)
            c3.markdown("#### COUNTRIES (FM)")
            c3.dataframe(build_ctry_board('FM'), hide_index=True, use_container_width=True)

        elif mx_tab == "AGENT LOCATION MAP":
            c_map, c_fly = st.columns([3, 2]) if st.session_state.matrix_loc else st.columns([1, 0.001])
            with c_map:
                dx_map_data = filt_df.groupby(['DXer_City', 'DXer_State', 'DXer_Country']).size().reset_index(name='Logs')
                lats, lons = [], []
                for _, r in dx_map_data.iterrows():
                    city_query = f"{r['DXer_City']}, {r['DXer_State']}" if pd.notna(r['DXer_State']) and r['DXer_State'] != '' else r['DXer_City']
                    lat, lon = get_lat_lon_from_city(city_query, r['DXer_Country'])
                    lats.append(lat)
                    lons.append(lon)
                dx_map_data['DX_Lat'], dx_map_data['DX_Lon'] = lats, lons
                dx_map_data = dx_map_data[(dx_map_data['DX_Lat'] != 0.0) | (dx_map_data['DX_Lon'] != 0.0)]
                t_col1, t_col2 = st.columns([1.5, 3.5])
                t_col1.markdown("<div style='color: #1bd2d4; font-size: 1.2rem; font-weight: bold; margin-top: 8px;'>UPLINK STATUS:</div>", unsafe_allow_html=True)
                sat_view = t_col2.pills("SATELLITE UPLINK", ["North America Sector", "Global Sector"], default="North America Sector", label_visibility="collapsed")
                if not sat_view: sat_view = "North America Sector"
                geo_scope = 'north america' if sat_view == "North America Sector" else 'world'
                geo_res = 50 if sat_view == "North America Sector" else 110
                lat_rng = [15, 65] if sat_view == "North America Sector" else [-55, 75]
                lon_rng = [-130, -55] if sat_view == "North America Sector" else [-160, 160]

                fig_dx = px.scatter_geo(
                    dx_map_data, lat='DX_Lat', lon='DX_Lon', size='Logs',
                    hover_name='DXer_City', hover_data={'DX_Lat':False, 'DX_Lon':False, 'Logs':True, 'DXer_State':False, 'DXer_Country':False},
                    scope=geo_scope, size_max=16
                )
                fig_dx.update_traces(marker_symbol='diamond', marker_color='#1bd2d4', marker_line_color='#ffffff', marker_line_width=1, marker_sizemin=12, opacity=0.9)
                fig_dx.update_geos(resolution=geo_res, showcoastlines=True, coastlinecolor="#139a9b", showland=True, landcolor="#050505", showocean=True, oceancolor="#050505", showlakes=True, lakecolor="#050505", showcountries=True, countrycolor="#1bd2d4", showsubunits=True, subunitcolor="#139a9b", lataxis_range=lat_rng, lonaxis_range=lon_rng, bgcolor='#050505')
                fig_dx.update_layout(height=650, paper_bgcolor='rgba(0,0,0,0)', margin={"r":0,"t":0,"l":0,"b":0})
                ev_dx = st.plotly_chart(fig_dx, use_container_width=True, on_select="rerun", key=f"m_dx_{st.session_state.matrix_map_key}", config={'scrollZoom': True})
                if ev_dx and ev_dx.get("selection") and ev_dx["selection"].get("points"):
                    pt = ev_dx["selection"]["points"][0]
                    if "hovertext" in pt:
                        new_loc = pt["hovertext"]
                        if st.session_state.matrix_loc != new_loc:
                            st.session_state.matrix_loc = new_loc
                            st.rerun()
            if st.session_state.matrix_loc:
                with c_fly:
                    loc = st.session_state.matrix_loc
                    loc_df = filt_df[filt_df['DXer_City'] == loc]
                    st.markdown("<div class='flyout-box'>", unsafe_allow_html=True)
                    st.markdown(f"<div class='flyout-title'>📍 {loc}</div>", unsafe_allow_html=True)
                    if st.button("❌ CLOSE INTEL", use_container_width=True):
                        st.session_state.matrix_loc = None
                        st.rerun()
                    st.markdown(f"<div class='flyout-val'>{len(loc_df):,} Logs</div>", unsafe_allow_html=True)
                    
                    loc_us = loc_df[loc_df['Country'] == 'United States']
                    top_st_mw = get_top_with_count(loc_us[loc_us['Band'] == 'AM']['State'])
                    top_st_fm = get_top_with_count(loc_us[loc_us['Band'] == 'FM']['State'])
                    top_st_nwr = get_top_with_count(loc_us[loc_us['Band'] == 'NWR']['State'])
                    st.markdown("<div class='flyout-header'>TOP STATES HEARD</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='flyout-micro'><b>MW:</b> {top_st_mw} | <b>FM:</b> {top_st_fm} | <b>NWR:</b> {top_st_nwr}</div>", unsafe_allow_html=True)

                    loc_intl = loc_df[loc_df['Country'] != 'United States']
                    top_co_mw = get_top_with_count(loc_intl[loc_intl['Band'] == 'AM']['Country'])
                    top_co_fm = get_top_with_count(loc_intl[loc_intl['Band'] == 'FM']['Country'])
                    st.markdown("<div class='flyout-header'>TOP COUNTRIES HEARD</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='flyout-micro'><b>MW:</b> {top_co_mw} | <b>FM:</b> {top_co_fm}</div>", unsafe_allow_html=True)

                    st.markdown("<div class='flyout-header'>FURTHEST RECEPTIONS</div>", unsafe_allow_html=True)
                    for b in ['AM', 'FM', 'NWR']:
                        b_df = loc_df[loc_df['Band'] == b]
                        if not b_df.empty:
                            f_r = b_df.sort_values('Distance', ascending=False).iloc[0]
                            prop_str = f" • Prop: {f_r['Prop_Mode']}" if b in ['FM', 'NWR'] and f_r['Prop_Mode'] not in ['', ' - '] else ""
                            st.markdown(f"<div class='flyout-val' style='font-size:1.2rem; color:#1bd2d4;'>{b}: {f_r['Distance']:,.0f} mi</div>", unsafe_allow_html=True)
                            st.markdown(f"<div class='flyout-micro'>{f_r['Freq_Num']} MHz - {f_r['Callsign']} ({f_r['City']}, {f_r['State']}, {f_r['Country']}){prop_str}<br>Caught by {f_r['DXer']} on {f_r['Date_Str']} at {f_r['Time_Str']}</div>", unsafe_allow_html=True)
                    st.markdown("</div>", unsafe_allow_html=True)

    # =====================================================================
    # VIEW 3: GEOGRAPHIC INTELLIGENCE
    # =====================================================================
    elif st.session_state.dash_nav == "GEOGRAPHY":
        st.markdown("### 🗺️ GEOSPATIAL ANALYSIS")
        geo_tab = st.pills("GEOGRAPHIC SECTOR", ["US STATES", "INTERNATIONAL", "CANADA", "US COUNTIES", "GRIDSQUARES", "STATION LOCATIONS"], default="US STATES")
        
        if geo_tab == "US STATES":
            b_sel = st.pills("BAND OVERRIDE", ["ALL BANDS", "AM", "FM", "NWR"], default="ALL BANDS", key="b_us")
            map_df = filt_df if b_sel == "ALL BANDS" else filt_df[filt_df['Band'] == b_sel]
            us_df = map_df[map_df['Country'] == 'United States']
            cm1, cm2 = st.columns([3, 2]) if st.session_state.geo_us_state else st.columns([1, 0.001])
            with cm1:
                state_counts = us_df.groupby('State').size().reset_index(name='Logs')
                fig_us = px.choropleth(state_counts, locations='State', locationmode="USA-states", color='Logs', scope="usa", color_continuous_scale=CYAN_SCALE, template="plotly_dark")
                fig_us.update_traces(marker_line_width=0.5, marker_line_color='#050505')
                fig_us.update_geos(resolution=50, showcoastlines=True, coastlinecolor="#139a9b", showland=True, landcolor="#050505", showocean=True, oceancolor="#050505", showlakes=True, lakecolor="#050505", showsubunits=True, subunitcolor="#139a9b", bgcolor='#050505')
                fig_us.update_layout(paper_bgcolor='rgba(0,0,0,0)', margin={"r":0,"t":0,"l":0,"b":0}, height=500)
                ev_st = st.plotly_chart(fig_us, use_container_width=True, on_select="rerun", key=f"m_geo_us_{st.session_state.geo_map_key}", config={'scrollZoom': True})
                if ev_st and ev_st.get("selection") and ev_st["selection"].get("points"):
                    n_state = ev_st["selection"]["points"][0]["location"]
                    if st.session_state.geo_us_state != n_state:
                        st.session_state.geo_us_state = n_state
                        st.rerun()
            if st.session_state.geo_us_state:
                with cm2:
                    render_geo_flyout("STATE", st.session_state.geo_us_state, filt_df[(filt_df['Country'] == 'United States') & (filt_df['State'] == st.session_state.geo_us_state)])

        elif geo_tab == "INTERNATIONAL":
            b_sel = st.pills("BAND OVERRIDE", ["ALL BANDS", "AM", "FM"], default="ALL BANDS", key="b_intl")
            map_df = filt_df if b_sel == "ALL BANDS" else filt_df[filt_df['Band'] == b_sel]
            cm1, cm2 = st.columns([3, 2]) if st.session_state.geo_intl_ctry else st.columns([1, 0.001])
            with cm1:
                world_counts = map_df.groupby('Country').size().reset_index(name='Logs')
                fig_w = px.choropleth(world_counts, locations='Country', locationmode="country names", color='Logs', color_continuous_scale=CYAN_SCALE, template="plotly_dark")
                fig_w.update_traces(marker_line_width=0.5, marker_line_color='#050505')
                fig_w.update_geos(projection_type="equirectangular", lataxis_range=[-45, 75], lonaxis_range=[-130, 20], resolution=50, showcoastlines=True, coastlinecolor="#139a9b", showland=True, landcolor="#050505", showocean=True, oceancolor="#050505", showlakes=True, lakecolor="#050505", showcountries=True, countrycolor="#139a9b", bgcolor='#050505')
                fig_w.update_layout(paper_bgcolor='rgba(0,0,0,0)', margin={"r":0,"t":0,"l":0,"b":0}, height=500)
                ev_w = st.plotly_chart(fig_w, use_container_width=True, on_select="rerun", key=f"m_geo_intl_{st.session_state.geo_map_key}", config={'scrollZoom': True})
                if ev_w and ev_w.get("selection") and ev_w["selection"].get("points"):
                    n_ctry = ev_w["selection"]["points"][0]["location"]
                    if st.session_state.geo_intl_ctry != n_ctry:
                        st.session_state.geo_intl_ctry = n_ctry
                        st.rerun()
            if st.session_state.geo_intl_ctry:
                with cm2:
                    render_geo_flyout("COUNTRY", st.session_state.geo_intl_ctry, filt_df[filt_df['Country'] == st.session_state.geo_intl_ctry])

        elif geo_tab == "CANADA":
            b_sel = st.pills("BAND OVERRIDE", ["ALL BANDS", "AM", "FM"], default="ALL BANDS", key="b_can")
            map_df = filt_df if b_sel == "ALL BANDS" else filt_df[filt_df['Band'] == b_sel]
            can_df = map_df[map_df['Country'] == 'Canada'].copy()
            cm1, cm2 = st.columns([3, 2]) if st.session_state.geo_can_prov else st.columns([1, 0.001])
            with cm1:
                prov_counts = can_df.groupby('State').size().reset_index(name='Logs')
                cam = {'ON':'Ontario','QC':'Quebec','NS':'Nova Scotia','NB':'New Brunswick','MB':'Manitoba','BC':'British Columbia','PE':'Prince Edward Island','SK':'Saskatchewan','AB':'Alberta','NL':'Newfoundland and Labrador','NU':'Nunavut','NT':'Northwest Territories','YT':'Yukon'}
                prov_counts['MapLoc'] = prov_counts['State'].map(cam)
                gj_url = "https://raw.githubusercontent.com/codeforamerica/click_that_hood/master/public/data/canada.geojson"
                fig_can = px.choropleth(prov_counts, geojson=gj_url, locations='MapLoc', featureidkey='properties.name', color='Logs', scope='north america', color_continuous_scale=CYAN_SCALE, template="plotly_dark")
                fig_can.update_traces(marker_line_width=0.5, marker_line_color='#050505')
                fig_can.update_geos(resolution=50, showcoastlines=True, coastlinecolor="#139a9b", showland=True, landcolor="#050505", showocean=True, oceancolor="#050505", showlakes=True, lakecolor="#050505", showcountries=True, countrycolor="#1bd2d4", showsubunits=True, subunitcolor="#139a9b", lataxis_range=[45, 75], lonaxis_range=[-140, -55], bgcolor='#050505')
                fig_can.update_layout(height=500, paper_bgcolor='rgba(0,0,0,0)', margin={"r":0,"t":0,"l":0,"b":0})
                ev_can = st.plotly_chart(fig_can, use_container_width=True, on_select="rerun", key=f"m_geo_can_{st.session_state.geo_map_key}", config={'scrollZoom': True})
                if ev_can and ev_can.get("selection") and ev_can["selection"].get("points"):
                    full_name = ev_can["selection"]["points"][0]["location"]
                    inv_cam = {v: k for k, v in cam.items()}
                    n_prov = inv_cam.get(full_name, full_name)
                    if st.session_state.geo_can_prov != n_prov:
                        st.session_state.geo_can_prov = n_prov
                        st.rerun()
            if st.session_state.geo_can_prov:
                with cm2:
                    render_geo_flyout("PROVINCE", st.session_state.geo_can_prov, filt_df[(filt_df['Country'] == 'Canada') & (filt_df['State'] == st.session_state.geo_can_prov)])

        elif geo_tab == "US COUNTIES":
            b_sel = st.pills("BAND OVERRIDE", ["ALL BANDS", "AM", "FM", "NWR"], default="ALL BANDS", key="b_co")
            map_df = filt_df if b_sel == "ALL BANDS" else filt_df[filt_df['Band'] == b_sel]
            us_c_df = map_df[(map_df['Country'] == 'United States') & (map_df['County'] != 'Unknown') & (map_df['County'] != ' - ')].copy()
            cm1, cm2 = st.columns([3, 2]) if st.session_state.geo_county else st.columns([1, 0.001])
            with cm1:
                if not us_c_df.empty:
                    us_c_df['Clean_County'] = us_c_df['County'].str.replace(' County', '', case=False).str.replace(' Parish', '', case=False).str.upper()
                    us_c_df['Clean_County'] = us_c_df['Clean_County'].apply(lambda x: re.sub(r'[^A-Z0-9]', '', str(x)))
                    us_c_df['Map_ID'] = us_c_df['State'].str.strip().str.upper() + "_" + us_c_df['Clean_County']
                    
                    county_counts = us_c_df.groupby(['Map_ID', 'County', 'State']).size().reset_index(name='Logs')
                    county_counts['HoverName'] = county_counts['County'] + ", " + county_counts['State']
                    c_gj = get_custom_county_geojson()
                    if c_gj:
                        fig_co = px.choropleth(county_counts, geojson=c_gj, locations='Map_ID', featureidkey='id', color='Logs', hover_name='HoverName', scope="usa", color_continuous_scale=CYAN_SCALE, template="plotly_dark")
                        fig_co.update_traces(marker_line_width=0.5, marker_line_color='#050505')
                    else:
                        fig_co = px.scatter_geo(county_counts, scope='usa')
                    fig_co.update_geos(resolution=50, showcoastlines=True, coastlinecolor="#139a9b", showland=True, landcolor="#050505", showsubunits=True, subunitcolor="#139a9b", bgcolor='#050505')
                    fig_co.update_layout(height=500, paper_bgcolor='rgba(0,0,0,0)', margin={"r":0,"t":0,"l":0,"b":0})
                else: fig_co = go.Figure()
                ev_co = st.plotly_chart(fig_co, use_container_width=True, on_select="rerun", key=f"m_geo_co_{st.session_state.geo_map_key}", config={'scrollZoom': True})
                if ev_co and ev_co.get("selection") and ev_co["selection"].get("points"):
                    pt = ev_co["selection"]["points"][0]
                    if "hovertext" in pt:
                        n_co = pt["hovertext"]
                        if st.session_state.geo_county != n_co:
                            st.session_state.geo_county = n_co
                            st.rerun()
            if st.session_state.geo_county:
                with cm2:
                    co_df = filt_df[(filt_df['Country'] == 'United States') & ((filt_df['County'] + ", " + filt_df['State']) == st.session_state.geo_county)]
                    render_geo_flyout("COUNTY", st.session_state.geo_county, co_df)

        elif geo_tab == "GRIDSQUARES":
            b_sel = st.pills("BAND OVERRIDE", ["ALL BANDS", "AM", "FM", "NWR"], default="ALL BANDS", key="b_grid")
            map_df = filt_df if b_sel == "ALL BANDS" else filt_df[filt_df['Band'] == b_sel]
            grid_df = map_df[(map_df['Station_Grid'] != '') & (map_df['Station_Grid'] != ' - ')].copy()
            cm1, cm2 = st.columns([3, 2]) if st.session_state.geo_grid else st.columns([1, 0.001])
            with cm1:
                if not grid_df.empty:
                    grid_df['Grid4'] = grid_df['Station_Grid'].str[:4].str.upper()
                    grid_geojson = generate_grid_geojson(list(grid_df['Grid4'].unique()))
                    grid_counts = grid_df.groupby('Grid4').size().reset_index(name='Logs')
                    
                    fig_g = px.choropleth_mapbox(grid_counts, geojson=grid_geojson, locations='Grid4', featureidkey='id', color='Logs', color_continuous_scale=CYAN_SCALE, hover_name='Grid4', mapbox_style="carto-darkmatter", center=dict(lat=40, lon=-95), zoom=2.5)
                    fig_g.update_traces(marker_line_width=1.5, marker_line_color='#050505')
                    fig_g.update_layout(height=500, paper_bgcolor='rgba(0,0,0,0)', margin={"r":0,"t":0,"l":0,"b":0}, coloraxis_showscale=False, showlegend=False)
                else: fig_g = go.Figure()
                ev_g = st.plotly_chart(fig_g, use_container_width=True, on_select="rerun", key=f"m_geo_grid_{st.session_state.geo_map_key}", config={'scrollZoom': True})
                if ev_g and ev_g.get("selection") and ev_g["selection"].get("points"):
                    pt = ev_g["selection"]["points"][0]
                    if "hovertext" in pt:
                        n_grid = pt["hovertext"]
                        if st.session_state.geo_grid != n_grid:
                            st.session_state.geo_grid = n_grid
                            st.rerun()
            if st.session_state.geo_grid:
                with cm2:
                    g_df = filt_df[filt_df['Station_Grid'].str.upper().str.startswith(st.session_state.geo_grid)]
                    render_geo_flyout("GRIDSQUARE", st.session_state.geo_grid, g_df)
                    
        elif geo_tab == "STATION LOCATIONS":
            b_sel = st.pills("BAND OVERRIDE", ["ALL BANDS", "AM", "FM", "NWR"], default="ALL BANDS", key="b_st_loc")
            map_df = filt_df if b_sel == "ALL BANDS" else filt_df[filt_df['Band'] == b_sel]
            cm1, cm2 = st.columns([3, 2]) if st.session_state.geo_st_loc else st.columns([1, 0.001])
            with cm1:
                if not map_df.empty:
                    st_map_data = map_df.groupby(['City', 'State', 'Country', 'ST_Lat', 'ST_Lon', 'Band']).size().reset_index(name='Logs')
                    st_map_data['Loc_Name'] = st_map_data.apply(lambda x: f"{x['City']}, {x['State']}" if x['Country'] in ['United States', 'Canada'] else f"{x['City']}, {x['Country']}", axis=1)
                    band_colors = {'AM': '#1bd2d4', 'FM': '#39ff14', 'NWR': '#ffa500'}
                    fig_st = px.scatter_mapbox(st_map_data, lat='ST_Lat', lon='ST_Lon', color='Band', color_discrete_map=band_colors, hover_name='Loc_Name', mapbox_style="carto-darkmatter", zoom=3.5, center=dict(lat=38, lon=-95))
                    fig_st.update_traces(marker=dict(size=10), marker_sizemin=8)
                    fig_st.update_layout(margin={"r":0,"t":30,"l":0,"b":0}, legend=dict(title="Active Band", orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(color="white")), paper_bgcolor='rgba(0,0,0,0)')
                else: fig_st = go.Figure()
                ev_st = st.plotly_chart(fig_st, use_container_width=True, on_select="rerun", key=f"m_geo_st_{st.session_state.geo_map_key}", config={'scrollZoom': True})
                if ev_st and ev_st.get("selection") and ev_st["selection"].get("points"):
                    pt = ev_st["selection"]["points"][0]
                    if "hovertext" in pt:
                        n_loc = pt["hovertext"]
                        if st.session_state.geo_st_loc != n_loc:
                            st.session_state.geo_st_loc = n_loc
                            st.rerun()
            if st.session_state.geo_st_loc:
                with cm2:
                    f_loc_df = filt_df.copy()
                    f_loc_df['Loc_Name'] = f_loc_df.apply(lambda x: f"{x['City']}, {x['State']}" if x['Country'] in ['United States', 'Canada'] else f"{x['City']}, {x['Country']}", axis=1)
                    s_df = f_loc_df[f_loc_df['Loc_Name'] == st.session_state.geo_st_loc]
                    render_geo_flyout("STATION HUB", st.session_state.geo_st_loc, s_df)

    # =====================================================================
    # VIEW 4: RADAR & TELEMETRY
    # =====================================================================
    elif st.session_state.dash_nav == "RADAR":
        st.markdown("### 📡 RADAR & TELEMETRY COMMAND")
        
        radar_tab = st.pills("SECTOR", ["INTERCEPT VECTORS", "ES-CLOUD RADAR", "RANGE FORENSICS"], default="INTERCEPT VECTORS")
        
        # --- TACTICAL SECTORS ---
        if radar_tab == "INTERCEPT VECTORS":
            col_ctrl, col_map = st.columns([1, 3])
            
            with col_ctrl:
                b_sel = st.pills("BAND", ["ALL", "AM", "FM", "NWR"], default="ALL")
                p_sel = st.pills("PROPAGATION", ["ALL", "Local", "Tropo", "Sporadic E", "Meteor Scatter", "Aurora"], default="ALL")
                st.markdown("<hr style='margin:5px 0px;'>", unsafe_allow_html=True)
                range_on = st.checkbox("Enable Date Range Mode", value=True) 
                
                avail_days = sorted(filt_df['Date_Obj'].dropna().unique())
                v_df = pd.DataFrame()
                
                if len(avail_days) > 0:
                    if not range_on:
                        date_sel = st.date_input("Select Event Date", value=avail_days[-1], min_value=avail_days[0], max_value=avail_days[-1])
                        ts_sel = pd.to_datetime(date_sel)
                        v_df = filt_df[filt_df['Date_TS'] == ts_sel]
                    else:
                        date_range = st.date_input("Select Date Range", value=(avail_days[0], avail_days[-1]), min_value=avail_days[0], max_value=avail_days[-1])
                        if len(date_range) == 2: 
                            ts_start, ts_end = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
                            v_df = filt_df[(filt_df['Date_TS'] >= ts_start) & (filt_df['Date_TS'] <= ts_end)]
                        else: 
                            ts_sel = pd.to_datetime(date_range[0])
                            v_df = filt_df[filt_df['Date_TS'] == ts_sel]
                else:
                    st.warning("No dates available.")
                    
                if not v_df.empty:
                    if b_sel != "ALL": v_df = v_df[v_df['Band'] == b_sel]
                    if p_sel != "ALL": v_df = v_df[v_df['Prop_Mode'] == p_sel]
                
                st.markdown(f"**Active Vectors:** {len(v_df)}")
                
            with col_map:
                if not v_df.empty:
                    color_map = {'AM': [27, 210, 212, 200], 'FM': [57, 255, 20, 200], 'NWR': [255, 165, 0, 200]}
                    v_df['Vector_Color'] = v_df['Band'].map(color_map).fillna(pd.Series([[255, 255, 255, 100]] * len(v_df)))
                    
                    layers = [
                        pdk.Layer(
                            "LineLayer",
                            data=v_df[['DX_Lon', 'DX_Lat', 'ST_Lon', 'ST_Lat', 'Vector_Color']].dropna(),
                            get_source_position="[DX_Lon, DX_Lat]",
                            get_target_position="[ST_Lon, ST_Lat]",
                            get_color="Vector_Color",
                            get_width=2,
                            pickable=True,
                        )
                    ]
                    st.pydeck_chart(pdk.Deck(map_style='https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json', initial_view_state=pdk.ViewState(latitude=38, longitude=-95, zoom=3), layers=layers))
                else:
                    st.info("NO TELEMETRY VECTORS DETECTED FOR CURRENT PARAMETERS.")
                    
        elif radar_tab == "ES-CLOUD RADAR":
            es_df = filt_df[(filt_df['Band'].isin(['FM', 'NWR'])) & (filt_df['Prop_Mode'] == 'Sporadic E')].copy()
            
            if es_df.empty:
                st.warning("NO SPORADIC E TELEMETRY DETECTED IN DATABANK.")
            else:
                hc1, hc2 = st.columns([1, 2])
                with hc1:
                    range_on = st.checkbox("Enable Date Range Mode", value=True, key="es_range_on") 
                    avail_days = sorted(es_df['Date_Obj'].dropna().unique()) 
                    
                    if not range_on:
                        date_sel = st.date_input("Select Event Date", value=avail_days[-1], min_value=avail_days[0], max_value=avail_days[-1], key="es_d1")
                        ts_sel = pd.to_datetime(date_sel)
                        map_df = es_df[es_df['Date_TS'] == ts_sel]
                    else:
                        date_range = st.date_input("Select Date Range", value=(avail_days[0], avail_days[-1]), min_value=avail_days[0], max_value=avail_days[-1], key="es_d2")
                        if len(date_range) == 2: 
                            ts_start, ts_end = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
                            map_df = es_df[(es_df['Date_TS'] >= ts_start) & (es_df['Date_TS'] <= ts_end)]
                        else: 
                            ts_sel = pd.to_datetime(date_range[0])
                            map_df = es_df[es_df['Date_TS'] == ts_sel]
                            
                    speed_sets = {"1x": {"delay": 0.2, "step": 1}, "2x": {"delay": 0.1, "step": 2}, "3x": {"delay": 0.05, "step": 3}, "4x": {"delay": 0.01, "step": 4}}
                    play_speed = st.selectbox("Playback Speed", options=list(speed_sets.keys()), index=1)
                
                if not map_df.empty:
                    timeline = map_df.sort_values(['Date_Obj', 'Time_Str'])
                    time_steps = timeline[['Date_Str', 'Time_Str']].drop_duplicates().values.tolist()
                    
                    pb1, pb2, pb_txt = st.columns([1, 1, 3])
                    if pb1.button("▶ PLAY"): 
                        st.session_state.radar_playing = True
                        st.session_state.radar_p_idx = 0
                        st.rerun()
                    if pb2.button("⏹ STOP"): 
                        st.session_state.radar_playing = False
                        st.rerun()
                        
                    if st.session_state.radar_playing:
                        if st.session_state.radar_p_idx >= len(time_steps):
                            st.session_state.radar_playing = False
                            st.rerun()
                        cur_step = time_steps[st.session_state.radar_p_idx]
                        cur_date, cur_time = cur_step[0], cur_step[1]
                    else:
                        times_only = sorted(map_df['Time_Str'].unique())
                        cur_time = hc2.select_slider("Time Control", options=["SHOW ALL"] + times_only, value="SHOW ALL")
                        cur_date = "N/A"

                    if cur_time == "SHOW ALL":
                        pb_txt.write("## 🕒 VIEWING: ALL SELECTED DATA")
                        render_df = map_df
                    else:
                        display_date = f"{cur_date} | " if cur_date != "N/A" else ""
                        pb_txt.write(f"## 🕒 {display_date}{cur_time}")
                        try:
                            lookback_time_str = (datetime.datetime.strptime(cur_time, '%H:%M') - datetime.timedelta(minutes=30)).strftime('%H:%M')
                        except:
                            lookback_time_str = "00:00"
                            
                        if st.session_state.radar_playing:
                            render_df = map_df[(map_df['Date_Str'] == cur_date) & (map_df['Time_Str'] <= cur_time) & (map_df['Time_Str'] >= lookback_time_str)]
                        else:
                            render_df = map_df[(map_df['Time_Str'] <= cur_time) & (map_df['Time_Str'] >= lookback_time_str)]

                    layers = [pdk.Layer(
                        'HeatmapLayer', 
                        data=render_df[['Mid_Lat', 'Mid_Lon']].dropna(), 
                        get_position='[Mid_Lon, Mid_Lat]', 
                        radius_pixels=65, intensity=2.0, threshold=0.03, 
                        color_range=CYAN_RGB_SCALE
                    )]
                    st.pydeck_chart(pdk.Deck(map_style='https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json', initial_view_state=pdk.ViewState(latitude=38, longitude=-95, zoom=3.4), layers=layers))

                    if st.session_state.radar_playing:
                        conf = speed_sets[play_speed]
                        st.session_state.radar_p_idx += conf['step']
                        time.sleep(conf['delay'])
                        st.rerun()

        elif radar_tab == "RANGE FORENSICS":
            col_m, col_f = st.columns([3, 2])
            
            with col_f:
                st.markdown("#### RANGE FILTERS")
                b_sel = st.pills("TARGET BAND", ["ALL", "AM", "FM", "NWR"], default="ALL", key="rf_band")
                p_sel = st.pills("PROPAGATION (FM/NWR)", ["ALL", "Local", "Tropo", "Sporadic E", "Meteor Scatter", "Aurora"], default="ALL", key="rf_prop")
                
                rf_df = filt_df.copy()
                if b_sel != "ALL": rf_df = rf_df[rf_df['Band'] == b_sel]
                if p_sel != "ALL": rf_df = rf_df[rf_df['Prop_Mode'] == p_sel]
                
                st.markdown("#### MAX DISTANCE INTERCEPTS (TOP 10)")
                top_10 = rf_df.sort_values('Distance', ascending=False).head(10).reset_index(drop=True)
                
                if not top_10.empty:
                    t10_view = top_10[['DXer', 'Distance', 'Callsign', 'City', 'State']].copy()
                    ev_rf = st.dataframe(t10_view, on_select="rerun", selection_mode="single-row", hide_index=True, use_container_width=True, column_config={"Distance": st.column_config.NumberColumn("Miles", format="%d")})
                    
                    selected_log = None
                    if ev_rf and ev_rf["selection"]["rows"]:
                        sel_idx = ev_rf["selection"]["rows"][0]
                        selected_log = top_10.iloc[sel_idx]
                else:
                    st.warning("NO TARGETS IN RANGE.")
                    selected_log = None
                    
            with col_m:
                st.markdown("#### TACTICAL TARGETING SYSTEM")
                if selected_log is not None:
                    dx_lat, dx_lon = selected_log['DX_Lat'], selected_log['DX_Lon']
                    st_lat, st_lon = selected_log['ST_Lat'], selected_log['ST_Lon']
                    dist = selected_log['Distance']
                    
                    mid_lat = (dx_lat + st_lat) / 2
                    mid_lon = (dx_lon + st_lon) / 2
                    
                    target_fig = go.Figure()
                    
                    circle_pts = get_target_circle(dx_lat, dx_lon, dist)
                    target_fig.add_trace(go.Scattermapbox(
                        mode="lines",
                        lon=[p[0] for p in circle_pts],
                        lat=[p[1] for p in circle_pts],
                        line=dict(width=2, color='#1bd2d4'),
                        name="Intercept Range",
                        hoverinfo="skip"
                    ))
                    
                    target_fig.add_trace(go.Scattermapbox(
                        mode="lines",
                        lon=[dx_lon, st_lon],
                        lat=[dx_lat, st_lat],
                        line=dict(width=1, color='#1bd2d4'),
                        name="Signal Vector",
                        hoverinfo="skip"
                    ))
                    
                    target_fig.add_trace(go.Scattermapbox(
                        mode="markers",
                        lon=[dx_lon], lat=[dx_lat],
                        marker=dict(size=12, color='#1bd2d4'),
                        name="Receiver Node",
                        text=[selected_log['DXer_City']],
                        hoverinfo="text"
                    ))
                    
                    target_fig.add_trace(go.Scattermapbox(
                        mode="markers",
                        lon=[st_lon], lat=[st_lat],
                        marker=dict(size=14, color='#ff0000'),
                        name="Transmitter Target",
                        text=[selected_log['Callsign']],
                        hoverinfo="text"
                    ))
                    
                    zoom_lvl = 3.5
                    if dist < 100: zoom_lvl = 6.5
                    elif dist < 300: zoom_lvl = 5.5
                    elif dist < 600: zoom_lvl = 4.5
                    elif dist < 1000: zoom_lvl = 3.8
                    elif dist < 1500: zoom_lvl = 3.2
                    elif dist < 2500: zoom_lvl = 2.5
                    else: zoom_lvl = 2.0
                    
                    target_fig.update_layout(
                        mapbox_style="carto-darkmatter",
                        mapbox=dict(center=dict(lat=mid_lat, lon=mid_lon), zoom=zoom_lvl),
                        margin={"r":0,"t":0,"l":0,"b":0}, height=500,
                        paper_bgcolor='rgba(0,0,0,0)', showlegend=False
                    )
                    
                    st.plotly_chart(target_fig, use_container_width=True, config={'scrollZoom': True})
                    
                    prop_str = f" • Prop: {selected_log['Prop_Mode']}" if selected_log['Band'] in ['FM', 'NWR'] and selected_log['Prop_Mode'] not in ['', ' - '] else ""
                    st.markdown(f"""
                    <div style='border: 1px solid #139a9b; padding: 15px; background-color: #050505; border-left: 5px solid #1bd2d4;'>
                        <div style='color:#1bd2d4; font-size:1.4rem; font-weight:bold; margin-bottom:5px;'>TARGET DOSSIER: {selected_log['Callsign']} ({selected_log['Distance']:,.0f} mi)</div>
                        <div style='color:#ffffff;'>
                            <b>Freq:</b> {selected_log['Freq_Num']} MHz {prop_str}<br>
                            <b>Origin:</b> {selected_log['City']}, {selected_log['State']}, {selected_log['Country']}<br>
                            <b>Intercept:</b> Caught by {selected_log['DXer']} on {selected_log['Date_Str']} at {selected_log['Time_Str']}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                else:
                    fig_blank = go.Figure(go.Scattermapbox())
                    fig_blank.update_layout(mapbox_style="carto-darkmatter", mapbox=dict(center=dict(lat=38, lon=-95), zoom=3), margin={"r":0,"t":0,"l":0,"b":0}, height=500, paper_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig_blank, use_container_width=True)
                    st.info("SELECT A TARGET FROM THE LOG TABLE TO INITIATE FORENSIC SCAN.")

    # =====================================================================
    # VIEW 5: FREQUENCY TUNER
    # =====================================================================
    elif st.session_state.dash_nav == "TUNER":
        st.markdown("### 📟 FREQUENCY INTELLIGENCE TERMINAL")
        
        c_main, c_fly = st.columns([3, 2]) if st.session_state.transmit_active else st.columns([1, 0.001])
        
        with c_main:
            st.markdown("<div class='radio-chassis'>", unsafe_allow_html=True)
            
            lcd_val = f"{st.session_state.tuner_freq}" if st.session_state.tuner_freq else ""
            unit_label = BAND_CONFIG[st.session_state.tuner_band]["unit"] if st.session_state.tuner_freq else ""
            
            if not st.session_state.tuner_freq:
                st.markdown(f"""
                <div class='lcd-recess'>
                    <div class='lcd-marquee'><span class='marquee-content'>[ SYSTEM READY ] ... SELECT BAND OR ENTER FREQUENCY ... [ SCANNING SPECTRUM ] ...</span></div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class='lcd-recess'>
                    <div class='lcd-text'>{lcd_val} <span style='font-size:1.5rem;'>{unit_label}</span></div>
                </div>
                """, unsafe_allow_html=True)
                
            c_ctrl1, c_ctrl2, c_ctrl3 = st.columns([2, 1, 2])
            
            with c_ctrl1:
                band_sel = st.pills("BAND SELECT", ["MW", "FM", "NWR"], default=st.session_state.tuner_band)
                if band_sel != st.session_state.tuner_band:
                    st.session_state.tuner_band = band_sel
                    st.session_state.tuner_freq = BAND_CONFIG[band_sel]["min"]
                    st.session_state.transmit_active = False
                    st.rerun()
                    
                if band_sel == "MW":
                    step_sel = st.pills("TUNING STEP", [9, 10], default=st.session_state.tuner_mw_step)
                    st.session_state.tuner_mw_step = step_sel

            with c_ctrl2:
                st.markdown("<br>", unsafe_allow_html=True)
                t_up, t_dn = st.columns(2)
                curr = st.session_state.tuner_freq or BAND_CONFIG[band_sel]["min"]
                step = st.session_state.tuner_mw_step if band_sel == "MW" else BAND_CONFIG[band_sel]["step"]
                precision = 1 if band_sel == "FM" else (3 if band_sel == "NWR" else 0)
                
                if t_up.button("➕", use_container_width=True):
                    new_f = round(curr + step, precision)
                    if new_f > BAND_CONFIG[band_sel]["max"]: new_f = BAND_CONFIG[band_sel]["min"]
                    st.session_state.tuner_freq = new_f
                    st.rerun()
                if t_dn.button("➖", use_container_width=True):
                    new_f = round(curr - step, precision)
                    if new_f < BAND_CONFIG[band_sel]["min"]: new_f = BAND_CONFIG[band_sel]["max"]
                    st.session_state.tuner_freq = new_f
                    st.rerun()

            with c_ctrl3:
                st.text_input("DIRECT FREQ ENTRY", placeholder="e.g. 1003 or 162425", key="direct_freq_input", on_change=process_direct_freq_entry)

            st.markdown("<hr style='border-color:#333; margin-top:5px; margin-bottom:15px;'>", unsafe_allow_html=True)
            if st.button("🔴 Click Here to Transmit Data", use_container_width=True, key="transmit_btn"):
                if st.session_state.tuner_freq:
                    st.session_state.transmit_active = True
                    st.rerun()
                else:
                    st.warning("TUNER MUST BE LOCKED TO A FREQUENCY BEFORE TRANSMISSION.")
            st.markdown("</div>", unsafe_allow_html=True)

            st.markdown("### 📊 SPECTRUM DENSITY RANKINGS")
            r_cols = st.columns(3)
            for i, band in enumerate(["AM", "FM", "NWR"]):
                b_label = "MW" if band == "AM" else band
                with r_cols[i]:
                    st.markdown(f"#### TOP 5 {b_label} FREQS")
                    top_f = filt_df[filt_df['Band'] == band].groupby('Freq_Num').size().reset_index(name='Logs').sort_values('Logs', ascending=False).head(5)
                    if not top_f.empty:
                        max_y = top_f['Logs'].max() * 1.25 if top_f['Logs'].max() > 0 else 10
                        fig_top = px.bar(top_f, x='Freq_Num', y='Logs', template="plotly_dark", color_discrete_sequence=['#1bd2d4'], text='Logs')
                        fig_top.update_traces(textposition='outside', textfont_size=14)
                        fig_top.update_layout(height=300, margin=dict(l=0,r=0,t=25,b=0), xaxis_title="Freq", yaxis_title="Logs", yaxis=dict(showgrid=False, range=[0, max_y]))
                        fig_top.update_xaxes(type='category')
                        st.plotly_chart(fig_top, use_container_width=True)
                    else: 
                        st.caption("No data in band.")

        if st.session_state.transmit_active:
            f_target = st.session_state.tuner_freq
            f_band = "AM" if st.session_state.tuner_band == "MW" else st.session_state.tuner_band
            f_df = filt_df[(filt_df['Band'] == f_band) & (filt_df['Freq_Num'] == f_target)]
            
            with c_fly:
                st.markdown("<div class='flyout-box'>", unsafe_allow_html=True)
                st.markdown(f"<div class='flyout-title'>📡 INTEL: {f_target} {BAND_CONFIG[st.session_state.tuner_band]['unit']}</div>", unsafe_allow_html=True)
                if st.button("❌ CLOSE DOSSIER", use_container_width=True):
                    st.session_state.transmit_active = False
                    st.rerun()
                
                if f_df.empty:
                    st.warning("NO SIGNAL TELEMETRY LOGGED FOR THIS FREQUENCY.")
                else:
                    st.markdown("<div class='flyout-header'>TOTAL INTERCEPTS</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='flyout-val'>{len(f_df):,} Logs</div>", unsafe_allow_html=True)
                    
                    st.markdown("<div class='flyout-header'>GEOGRAPHIC DOMINANCE</div>", unsafe_allow_html=True)
                    g_cols = st.columns(2)
                    
                    us_f_df = f_df[f_df['Country'] == 'United States']
                    intl_f_df = f_df[f_df['Country'] != 'United States']
                    
                    top_st = get_top_with_count(us_f_df['State'])
                    top_co = get_top_with_count(intl_f_df['Country'])
                    
                    gr_series = us_f_df['Station_Grid'].replace(['', ' - ', 'Unknown'], pd.NA).dropna().str[:4].str.upper()
                    top_gr = f"{gr_series.value_counts().index[0]} ({gr_series.value_counts().iloc[0]})" if not gr_series.empty else "N/A"
                    
                    top_cy = get_top_with_count(us_f_df['County'])
                    
                    g_cols[0].markdown(f"<div class='flyout-micro'><b>STATE:</b> {top_st}<br><b>COUNTRY:</b> {top_co}</div>", unsafe_allow_html=True)
                    g_cols[1].markdown(f"<div class='flyout-micro'><b>GRID (US):</b> {top_gr}<br><b>COUNTY (US):</b> {top_cy}</div>", unsafe_allow_html=True)
                    
                    st.markdown("<div class='flyout-header'>TOP CAPTURED STATIONS</div>", unsafe_allow_html=True)
                    top_stats = f_df.groupby(['Callsign', 'City', 'State']).size().reset_index(name='Logs').sort_values('Logs', ascending=False).head(5)
                    st.dataframe(top_stats, hide_index=True, use_container_width=True)
                    
                    f_r = f_df.sort_values('Distance', ascending=False).iloc[0]
                    prop_str = f" • Prop: {f_r['Prop_Mode']}" if f_r['Band'] in ['FM', 'NWR'] and f_r['Prop_Mode'] not in ['', ' - '] else ""
                    st.markdown("<div class='flyout-header'>MAX DISTANCE INTERCEPT</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='flyout-val' style='font-size:1.2rem; color:#1bd2d4;'>{f_r['Distance']:,.0f} mi</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='flyout-micro'>{f_r['Callsign']} ({f_r['City']}, {f_r['State']}, {f_r['Country']}){prop_str}<br>Caught by {f_r['DXer']} on {f_r['Date_Str']} at {f_r['Time_Str']}</div>", unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)
