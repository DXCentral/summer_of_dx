import streamlit as st
import pandas as pd
import math
from modules.data_forge import load_global_dashboard_data

# --- CYAN ESPIONAGE AESTHETIC ---
CYAN_SCALE = [
    [0.0, '#050505'], 
    [0.01, '#0a4040'], 
    [0.25, '#139a9b'], 
    [0.5, '#1bd2d4'], 
    [0.75, '#a3e8e9'], 
    [1.0, '#ffffff']
]

def render_dashboard():
    df = load_global_dashboard_data()
    
    if df.empty:
        st.error("🚨 SYSTEM ALERT: DATABANK OFFLINE OR EMPTY.")
        st.stop()
        
    st.markdown("""
    <style>
    /* Force Center DataFrame Headers and Cells */
    [data-testid="stDataFrame"] th {
        text-align: center !important;
    }
    [data-testid="stDataFrame"] td {
        text-align: center !important;
    }
    /* Eradicate Streamlit Toolbar */
    [data-testid="stElementToolbar"] {
        display: none !important;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("<h1 style='text-align: center; color: #1bd2d4; text-shadow: 0px 0px 10px rgba(27,210,212,0.8);'>GLOBAL INTELLIGENCE COMMAND</h1>", unsafe_allow_html=True)
    
    # --- SESSION STATE INITIALIZATION ---
    if 'dash_nav' not in st.session_state: st.session_state.dash_nav = "OVERVIEW"
    if 'filter_reset_key' not in st.session_state: st.session_state.filter_reset_key = 0

    def reset_flyouts():
        pass # Placeholder for future module flyout resets

    def reset_filters():
        st.session_state.filter_reset_key += 1

    # --- DASHBOARD NAVIGATION ---
    d_cols = st.columns(5)
    if d_cols[0].button("▶ MISSION OVERVIEW", use_container_width=True): 
        st.session_state.dash_nav = "OVERVIEW"
        reset_flyouts()
        st.rerun()
    if d_cols[1].button("▶ GEOGRAPHIC INTEL", use_container_width=True): 
        st.session_state.dash_nav = "GEOGRAPHY"
        reset_flyouts()
        st.rerun()
    if d_cols[2].button("▶ ACHIEVEMENT TRACKERS", use_container_width=True): 
        st.session_state.dash_nav = "ACHIEVEMENTS"
        reset_flyouts()
        st.rerun()
    if d_cols[3].button("▶ TIMELAPSE & RADAR", use_container_width=True): 
        st.session_state.dash_nav = "ES_TRACKER"
        reset_flyouts()
        st.rerun()
    if d_cols[4].button("▶ FREQUENCY TUNER", use_container_width=True): 
        st.session_state.dash_nav = "TUNER"
        reset_flyouts()
        st.rerun()
        
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

    # Propagation Filter Logic (Ignore for AM)
    if f_prop != "ALL":
        filt_df = filt_df[(filt_df['Band'] == 'AM') | (filt_df['Prop_Mode'] == f_prop)]
        
    if filt_df.empty:
        st.warning("NO TELEMETRY MATCHES CURRENT FILTER PARAMETERS.")
        st.stop()

    # --- SCORE CALCULATION HELPER ---
    def get_leader(band_target):
        b_df = filt_df[filt_df['Band'] == band_target]
        if b_df.empty: return "N/A (0 pts)"
        
        scores = b_df.groupby('DXer')['Base_Score'].sum().reset_index()
        
        if band_target in ['AM', 'FM']:
            bonuses = b_df.groupby(['DXer', 'Month']).size().reset_index(name='Logs')
            bonuses['Bonus'] = bonuses['Logs'].apply(lambda x: 100 if x >= 10 else 0)
            bonus_sum = bonuses.groupby('DXer')['Bonus'].sum().reset_index()
            scores = scores.merge(bonus_sum, on='DXer', how='left').fillna(0)
            scores['Total'] = scores['Base_Score'] + scores['Bonus']
        else:
            scores['Total'] = scores['Base_Score']
            
        leader = scores.sort_values('Total', ascending=False).iloc[0]
        return f"{leader['DXer']} ({int(leader['Total']):,} pts)"

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

        m9, m10, m11 = st.columns(3)
        m9.metric("MW Score Leader", get_leader('AM'))
        m10.metric("FM Score Leader", get_leader('FM'))
        m11.metric("NWR Score Leader", get_leader('NWR'))

        st.markdown("---")
        st.markdown("### 📡 SUBMITTED LOGGINGS")
        
        table_df = filt_df.copy()
        
        # Clean formatting for presentation
        table_df['Prop_Mode'] = table_df.apply(lambda x: " - " if x['Band'] == "AM" else x['Prop_Mode'], axis=1)
        table_df['Station_Grid'] = table_df.apply(lambda x: " - " if x['Country'] != "United States" else x['Station_Grid'], axis=1)
        table_df['County'] = table_df.apply(lambda x: " - " if x['Country'] != "United States" else x['County'], axis=1)
        
        display_cols = [
            'DXer', 'Date_Str', 'Time_Str', 'Band', 'Freq_Num', 'Callsign', 
            'City', 'State', 'Country', 'Station_Grid', 'County', 'Distance', 'Prop_Mode'
        ]
        
        rename_map = {
            'Date_Str': 'Date',
            'Time_Str': 'Time',
            'Freq_Num': 'Frequency',
            'Callsign': 'Station',
            'Station_Grid': 'Gridsquare',
            'Prop_Mode': 'Propagation'
        }
        
        view_df = table_df[display_cols].rename(columns=rename_map)
        
        st.dataframe(
            view_df, 
            hide_index=True, 
            use_container_width=True,
            column_config={
                "Distance": st.column_config.NumberColumn("Distance (mi)", format="%.1f")
            }
        )

    # =====================================================================
    # VIEW 2: GEOGRAPHIC INTELLIGENCE (STUB)
    # =====================================================================
    elif st.session_state.dash_nav == "GEOGRAPHY":
        st.info("GEOGRAPHIC INTELLIGENCE MODULE: AWAITING DEPLOYMENT")

    # =====================================================================
    # VIEW 3: ACHIEVEMENT TRACKERS (STUB)
    # =====================================================================
    elif st.session_state.dash_nav == "ACHIEVEMENTS":
        st.info("ACHIEVEMENT TRACKERS MODULE: AWAITING DEPLOYMENT")

    # =====================================================================
    # VIEW 4: TIMELAPSE & ES-CLOUD RADAR (STUB)
    # =====================================================================
    elif st.session_state.dash_nav == "ES_TRACKER":
        st.info("TIMELAPSE & ES-CLOUD RADAR MODULE: AWAITING DEPLOYMENT")

    # =====================================================================
    # VIEW 5: FREQUENCY TUNER (STUB)
    # =====================================================================
    elif st.session_state.dash_nav == "TUNER":
        st.info("FREQUENCY TUNER MODULE: AWAITING DEPLOYMENT")
