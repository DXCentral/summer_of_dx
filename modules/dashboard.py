import streamlit as st
import pandas as pd
import pydeck as pdk
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import datetime
import time
from modules.data_forge import load_global_dashboard_data, get_lat_lon_from_city

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
    /* Score Leader Custom UI */
    .leader-box {
        border: 1px solid #139a9b;
        padding: 10px;
        background-color: #050505;
        text-align: center;
        box-shadow: inset 0px 0px 10px rgba(19, 154, 155, 0.1);
    }
    .leader-title {
        color: #139a9b;
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 5px;
    }
    .leader-name {
        color: #ffffff;
        font-size: 1.4rem;
        line-height: 1.2;
    }
    .leader-score {
        color: #1bd2d4;
        font-size: 1.1rem;
    }
    /* Flyout Custom UI */
    .flyout-box { border: 1px solid #139a9b; padding: 15px; background-color: #050505; box-shadow: 0px 0px 10px rgba(19, 154, 155, 0.2); }
    .flyout-title { color: #1bd2d4; margin-top: 0; font-size: 1.8rem; text-transform: uppercase; border-bottom: 1px dashed #139a9b; padding-bottom: 5px; }
    .flyout-header { color: #1bd2d4; font-size: 0.85rem; margin-top: 15px; text-transform: uppercase; letter-spacing: 1px; }
    .flyout-val { font-size: 1.8rem; color: #ffffff; line-height: 1.1; }
    .flyout-sub { font-size: 0.95rem; color: #ffffff; margin-top: 2px; }
    .flyout-micro { font-size: 0.9rem; color: #ffffff; margin-top: 2px; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("<h1 style='text-align: center; color: #1bd2d4; text-shadow: 0px 0px 10px rgba(27,210,212,0.8);'>GLOBAL INTELLIGENCE COMMAND</h1>", unsafe_allow_html=True)
    
    # --- SESSION STATE INITIALIZATION ---
    if 'dash_nav' not in st.session_state: st.session_state.dash_nav = "OVERVIEW"
    if 'filter_reset_key' not in st.session_state: st.session_state.filter_reset_key = 0
    if 'matrix_loc' not in st.session_state: st.session_state.matrix_loc = None
    if 'matrix_map_key' not in st.session_state: st.session_state.matrix_map_key = 2000000

    def reset_flyouts():
        st.session_state.matrix_loc = None

    def reset_filters():
        st.session_state.filter_reset_key += 1

    # --- DASHBOARD NAVIGATION ---
    d_cols = st.columns(5)
    if d_cols[0].button("▶ MISSION OVERVIEW", use_container_width=True): 
        st.session_state.dash_nav = "OVERVIEW"
        reset_flyouts()
        st.rerun()
    if d_cols[1].button("▶ CLASSIFICATION MATRIX", use_container_width=True): 
        st.session_state.dash_nav = "MATRIX"
        reset_flyouts()
        st.rerun()
    if d_cols[2].button("▶ GEOGRAPHIC INTEL", use_container_width=True): 
        st.session_state.dash_nav = "GEOGRAPHY"
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

    if f_prop != "ALL":
        filt_df = filt_df[(filt_df['Band'] == 'AM') | (filt_df['Prop_Mode'] == f_prop)]
        
    if filt_df.empty:
        st.warning("NO TELEMETRY MATCHES CURRENT FILTER PARAMETERS.")
        st.stop()

    # --- SCORE CALCULATION HELPER ---
    def calculate_scores(target_df):
        if target_df.empty: return pd.DataFrame(columns=['DXer', 'Total'])
        s = target_df.groupby('DXer')['Base_Score'].sum().reset_index()
        
        # Calculate consistency bonus for AM/FM
        bonus_eligible = target_df[target_df['Band'].isin(['AM', 'FM'])]
        if not bonus_eligible.empty:
            b_counts = bonus_eligible.groupby(['DXer', 'Band', 'Month']).size().reset_index(name='Logs')
            b_counts['Bonus'] = b_counts['Logs'].apply(lambda x: 100 if x >= 10 else 0)
            b_sum = b_counts.groupby('DXer')['Bonus'].sum().reset_index()
            s = s.merge(b_sum, on='DXer', how='left').fillna(0)
            s['Total'] = s['Base_Score'] + s['Bonus']
        else:
            s['Total'] = s['Base_Score']
        return s.sort_values('Total', ascending=False)

    def get_leader_data(band_target):
        b_df = filt_df[filt_df['Band'] == band_target]
        s = calculate_scores(b_df)
        if s.empty: return "N/A", "0 pts"
        leader = s.iloc[0]
        return leader['DXer'], f"{int(leader['Total']):,} pts"

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
        
        display_cols = [
            'DXer', 'Date_Str', 'Time_Str', 'Band', 'Freq_Num', 'Callsign', 
            'City', 'State', 'Country', 'Station_Grid', 'County', 'Distance', 'Prop_Mode'
        ]
        
        rename_map = {
            'Date_Str': 'Date', 'Time_Str': 'Time', 'Freq_Num': 'Frequency',
            'Callsign': 'Station', 'Station_Grid': 'Gridsquare', 'Prop_Mode': 'Propagation'
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
    # VIEW 2: CLASSIFICATION MATRIX
    # =====================================================================
    elif st.session_state.dash_nav == "MATRIX":
        st.markdown("### 🗄️ CLASSIFICATION MATRIX")
        st.caption("Detailed breakdown of operator intelligence and geographic distribution.")
        
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
            
            with c1:
                st.markdown("#### TOTAL SCORE (ALL BANDS)")
                s_all = calculate_scores(filt_df).head(10)
                st.dataframe(s_all[['DXer', 'Total']], hide_index=True, use_container_width=True, column_config={"Total": st.column_config.NumberColumn("Points", format="%d")})
            with c2:
                st.markdown("#### MW SCORE")
                s_am = calculate_scores(filt_df[filt_df['Band'] == 'AM']).head(10)
                st.dataframe(s_am[['DXer', 'Total']], hide_index=True, use_container_width=True, column_config={"Total": st.column_config.NumberColumn("Points", format="%d")})
            with c3:
                st.markdown("#### FM SCORE")
                s_fm = calculate_scores(filt_df[filt_df['Band'] == 'FM']).head(10)
                st.dataframe(s_fm[['DXer', 'Total']], hide_index=True, use_container_width=True, column_config={"Total": st.column_config.NumberColumn("Points", format="%d")})
            with c4:
                st.markdown("#### NWR SCORE")
                s_nwr = calculate_scores(filt_df[filt_df['Band'] == 'NWR']).head(10)
                st.dataframe(s_nwr[['DXer', 'Total']], hide_index=True, use_container_width=True, column_config={"Total": st.column_config.NumberColumn("Points", format="%d")})

        elif mx_tab == "GRID LEDGER":
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("#### MW GRID MASTERS")
                df_g_am = build_progress_board(filt_df[filt_df['Band'] == 'AM'], 'DXer', 'Station_Grid', 100)
                st.dataframe(df_g_am, hide_index=True, use_container_width=True, column_config={"Count": "Grids", "Progress": st.column_config.ProgressColumn("To 100", min_value=0, max_value=100)})
            with c2:
                st.markdown("#### FM GRID MASTERS")
                df_g_fm = build_progress_board(filt_df[filt_df['Band'] == 'FM'], 'DXer', 'Station_Grid', 100)
                st.dataframe(df_g_fm, hide_index=True, use_container_width=True, column_config={"Count": "Grids", "Progress": st.column_config.ProgressColumn("To 100", min_value=0, max_value=100)})
            
            st.markdown("---")
            c3, c4 = st.columns(2)
            with c3:
                st.markdown("#### NWR GRID MASTERS")
                df_g_nwr = build_progress_board(filt_df[filt_df['Band'] == 'NWR'], 'DXer', 'Station_Grid', 25)
                st.dataframe(df_g_nwr, hide_index=True, use_container_width=True, column_config={"Count": "Grids", "Progress": st.column_config.ProgressColumn("To 25", min_value=0, max_value=25)})

        elif mx_tab == "COUNTY/PARISH LEDGER":
            us_df = filt_df[filt_df['Country'] == 'United States']
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("#### MW COUNTY MASTERS")
                df_c_am = build_progress_board(us_df[us_df['Band'] == 'AM'], 'DXer', 'County', 100)
                st.dataframe(df_c_am, hide_index=True, use_container_width=True, column_config={"Count": "Counties", "Progress": st.column_config.ProgressColumn("To 100", min_value=0, max_value=100)})
            with c2:
                st.markdown("#### FM COUNTY MASTERS")
                df_c_fm = build_progress_board(us_df[us_df['Band'] == 'FM'], 'DXer', 'County', 100)
                st.dataframe(df_c_fm, hide_index=True, use_container_width=True, column_config={"Count": "Counties", "Progress": st.column_config.ProgressColumn("To 100", min_value=0, max_value=100)})
            
            st.markdown("---")
            c3, c4 = st.columns(2)
            with c3:
                st.markdown("#### NWR COUNTY MASTERS")
                df_c_nwr = build_progress_board(us_df[us_df['Band'] == 'NWR'], 'DXer', 'County', 25)
                st.dataframe(df_c_nwr, hide_index=True, use_container_width=True, column_config={"Count": "Counties", "Progress": st.column_config.ProgressColumn("To 25", min_value=0, max_value=25)})

        elif mx_tab == "INTERCEPT LEDGER":
            def build_log_board(b_target=None):
                t_df = filt_df if not b_target else filt_df[filt_df['Band'] == b_target]
                return t_df.groupby('DXer').size().reset_index(name='Total Logs').sort_values('Total Logs', ascending=False)
            
            c1, c2, c3, c4 = st.columns(4)
            c1.markdown("#### TOTAL LOGS (ALL)")
            c1.dataframe(build_log_board(), hide_index=True, use_container_width=True)
            c2.markdown("#### TOTAL LOGS (MW)")
            c2.dataframe(build_log_board('AM'), hide_index=True, use_container_width=True)
            c3.markdown("#### TOTAL LOGS (FM)")
            c3.dataframe(build_log_board('FM'), hide_index=True, use_container_width=True)
            c4.markdown("#### TOTAL LOGS (NWR)")
            c4.dataframe(build_log_board('NWR'), hide_index=True, use_container_width=True)

        elif mx_tab == "STATE LEDGER":
            st.caption("Tracking unique US States logged (Includes DC).")
            us_df = filt_df[filt_df['Country'] == 'United States']
            def build_state_board(b_target=None):
                t_df = us_df if not b_target else us_df[us_df['Band'] == b_target]
                return t_df.groupby('DXer')['State'].nunique().reset_index(name='States Heard').sort_values('States Heard', ascending=False)
            
            c1, c2, c3, c4 = st.columns(4)
            c1.markdown("#### STATES (ALL BANDS)")
            c1.dataframe(build_state_board(), hide_index=True, use_container_width=True)
            c2.markdown("#### STATES (MW)")
            c2.dataframe(build_state_board('AM'), hide_index=True, use_container_width=True)
            c3.markdown("#### STATES (FM)")
            c3.dataframe(build_state_board('FM'), hide_index=True, use_container_width=True)
            c4.markdown("#### STATES (NWR)")
            c4.dataframe(build_state_board('NWR'), hide_index=True, use_container_width=True)

        elif mx_tab == "COUNTRY LEDGER":
            def build_ctry_board(b_target=None):
                t_df = filt_df if not b_target else filt_df[filt_df['Band'] == b_target]
                return t_df.groupby('DXer')['Country'].nunique().reset_index(name='Countries Heard').sort_values('Countries Heard', ascending=False)
            
            c1, c2, c3 = st.columns(3)
            c1.markdown("#### COUNTRIES (ALL BANDS)")
            c1.dataframe(build_ctry_board(), hide_index=True, use_container_width=True)
            c2.markdown("#### COUNTRIES (MW)")
            c2.dataframe(build_ctry_board('AM'), hide_index=True, use_container_width=True)
            c3.markdown("#### COUNTRIES (FM)")
            c3.dataframe(build_ctry_board('FM'), hide_index=True, use_container_width=True)

        elif mx_tab == "AGENT LOCATION MAP":
            c_map, c_fly = st.columns([3, 2]) if st.session_state.matrix_loc else st.columns([1, 0.001])
            
            with c_map:
                dx_map_data = filt_df.groupby(['DXer_City', 'DXer_State', 'DXer_Country']).size().reset_index(name='Logs')
                
                # Dynamic Geocoding fallback for missing app.py payload coordinates
                lats, lons = [], []
                for _, r in dx_map_data.iterrows():
                    city_query = f"{r['DXer_City']}, {r['DXer_State']}" if pd.notna(r['DXer_State']) and r['DXer_State'] != '' else r['DXer_City']
                    lat, lon = get_lat_lon_from_city(city_query, r['DXer_Country'])
                    lats.append(lat)
                    lons.append(lon)
                    
                dx_map_data['DX_Lat'] = lats
                dx_map_data['DX_Lon'] = lons
                dx_map_data = dx_map_data[(dx_map_data['DX_Lat'] != 0.0) | (dx_map_data['DX_Lon'] != 0.0)]
                
                # CRT Wireframe Vector Map (Plotly Scatter Geo)
                fig_dx = px.scatter_geo(
                    dx_map_data, lat='DX_Lat', lon='DX_Lon', size='Logs',
                    hover_name='DXer_City', hover_data={'DX_Lat':False, 'DX_Lon':False, 'Logs':True, 'DXer_State':False, 'DXer_Country':False},
                    size_max=25
                )
                fig_dx.update_traces(marker=dict(symbol='diamond', color='#1bd2d4', line=dict(color='#ffffff', width=1), opacity=0.9))
                fig_dx.update_geos(
                    projection_type="equirectangular",
                    showcoastlines=True, coastlinecolor="#139a9b",
                    showland=True, landcolor="#050505",
                    showocean=True, oceancolor="#050505",
                    showlakes=True, lakecolor="#050505",
                    showcountries=True, countrycolor="#139a9b",
                    showsubunits=True, subunitcolor="#0a4040",
                    fitbounds="locations",
                    bgcolor='#050505'
                )
                fig_dx.update_layout(height=650, paper_bgcolor='rgba(0,0,0,0)', margin={"r":0,"t":0,"l":0,"b":0})
                
                ev_dx = st.plotly_chart(fig_dx, use_container_width=True, on_select="rerun", key=f"m_dx_{st.session_state.matrix_map_key}")
                
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
                        st.session_state.matrix_map_key += 1
                        st.rerun()

                    # Volume Metrics
                    tot_v = len(loc_df)
                    mw_v = len(loc_df[loc_df['Band'] == 'AM'])
                    fm_v = len(loc_df[loc_df['Band'] == 'FM'])
                    nwr_v = len(loc_df[loc_df['Band'] == 'NWR'])
                    pct_vol = (tot_v / len(filt_df)) * 100 if len(filt_df) > 0 else 0
                    
                    st.markdown("<div class='flyout-header'>LOG VOLUME</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='flyout-val'>{tot_v:,} Logs</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='flyout-micro'>MW: {mw_v:,} | FM: {fm_v:,} | NWR: {nwr_v:,}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='flyout-sub'>{pct_vol:.2f}% of Total Global Volume</div>", unsafe_allow_html=True)

                    # Unique Stations
                    tot_s = loc_df['Callsign'].nunique()
                    mw_s = loc_df[loc_df['Band'] == 'AM']['Callsign'].nunique()
                    fm_s = loc_df[loc_df['Band'] == 'FM']['Callsign'].nunique()
                    nwr_s = loc_df[loc_df['Band'] == 'NWR']['Callsign'].nunique()
                    
                    st.markdown("<div class='flyout-header'>UNIQUE STATIONS</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='flyout-val'>{tot_s:,}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='flyout-micro'>MW: {mw_s:,} | FM: {fm_s:,} | NWR: {nwr_s:,}</div>", unsafe_allow_html=True)

                    # Gridsquares
                    tot_g = loc_df['Station_Grid'].nunique()
                    mw_g = loc_df[loc_df['Band'] == 'AM']['Station_Grid'].nunique()
                    fm_g = loc_df[loc_df['Band'] == 'FM']['Station_Grid'].nunique()
                    nwr_g = loc_df[loc_df['Band'] == 'NWR']['Station_Grid'].nunique()
                    
                    st.markdown("<div class='flyout-header'>UNIQUE GRIDSQUARES</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='flyout-val'>{tot_g:,}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='flyout-micro'>MW: {mw_g:,} | FM: {fm_g:,} | NWR: {nwr_g:,}</div>", unsafe_allow_html=True)

                    # Counties
                    loc_us = loc_df[loc_df['Country'] == 'United States']
                    tot_c = loc_us['County'].nunique()
                    mw_c = loc_us[loc_us['Band'] == 'AM']['County'].nunique()
                    fm_c = loc_us[loc_us['Band'] == 'FM']['County'].nunique()
                    nwr_c = loc_us[loc_us['Band'] == 'NWR']['County'].nunique()
                    
                    st.markdown("<div class='flyout-header'>US COUNTIES/PARISHES</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='flyout-val'>{tot_c:,}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='flyout-micro'>MW: {mw_c:,} | FM: {fm_c:,} | NWR: {nwr_c:,}</div>", unsafe_allow_html=True)

                    # Local Agents
                    st.markdown("<div class='flyout-header'>TOP LOCAL AGENTS</div>", unsafe_allow_html=True)
                    top_agents = loc_df.groupby('DXer').size().reset_index(name='Logs').sort_values('Logs', ascending=False).head(3)
                    for _, row in top_agents.iterrows():
                        st.markdown(f"<div class='flyout-sub'>• {row['DXer']} ({row['Logs']} logs)</div>", unsafe_allow_html=True)

                    # Top Heard States
                    st.markdown("<div class='flyout-header'>TOP STATES HEARD</div>", unsafe_allow_html=True)
                    top_st_mw = loc_us[loc_us['Band'] == 'AM']['State'].mode().iloc[0] if not loc_us[loc_us['Band'] == 'AM'].empty else "N/A"
                    top_st_fm = loc_us[loc_us['Band'] == 'FM']['State'].mode().iloc[0] if not loc_us[loc_us['Band'] == 'FM'].empty else "N/A"
                    top_st_nwr = loc_us[loc_us['Band'] == 'NWR']['State'].mode().iloc[0] if not loc_us[loc_us['Band'] == 'NWR'].empty else "N/A"
                    st.markdown(f"<div class='flyout-micro'><b>MW:</b> {top_st_mw} | <b>FM:</b> {top_st_fm} | <b>NWR:</b> {top_st_nwr}</div>", unsafe_allow_html=True)

                    # Top Heard Countries
                    loc_intl = loc_df[loc_df['Country'] != 'United States']
                    st.markdown("<div class='flyout-header'>TOP COUNTRIES HEARD</div>", unsafe_allow_html=True)
                    top_co_mw = loc_intl[loc_intl['Band'] == 'AM']['Country'].mode().iloc[0] if not loc_intl[loc_intl['Band'] == 'AM'].empty else "N/A"
                    top_co_fm = loc_intl[loc_intl['Band'] == 'FM']['Country'].mode().iloc[0] if not loc_intl[loc_intl['Band'] == 'FM'].empty else "N/A"
                    st.markdown(f"<div class='flyout-micro'><b>MW:</b> {top_co_mw} | <b>FM:</b> {top_co_fm}</div>", unsafe_allow_html=True)

                    # Furthest Receptions Breakdown
                    st.markdown("<div class='flyout-header'>FURTHEST RECEPTIONS</div>", unsafe_allow_html=True)
                    for b in ['AM', 'FM', 'NWR']:
                        b_df = loc_df[loc_df['Band'] == b]
                        if not b_df.empty:
                            f_r = b_df.sort_values('Distance', ascending=False).iloc[0]
                            st.markdown(f"<div class='flyout-val' style='font-size:1.2rem; color:#1bd2d4;'>{b}: {f_r['Distance']:,.0f} mi</div>", unsafe_allow_html=True)
                            st.markdown(f"<div class='flyout-micro'>{f_r['Freq_Num']} - {f_r['Callsign']} ({f_r['City']}, {f_r['State']}, {f_r['Country']})<br>By {f_r['DXer']} on {f_r['Date_Str']} at {f_r['Time_Str']}</div>", unsafe_allow_html=True)

                    st.markdown("</div>", unsafe_allow_html=True)

    # =====================================================================
    # STUBS
    # =====================================================================
    elif st.session_state.dash_nav == "GEOGRAPHY":
        st.info("GEOGRAPHIC INTELLIGENCE MODULE: AWAITING DEPLOYMENT")
    elif st.session_state.dash_nav == "ES_TRACKER":
        st.info("TIMELAPSE & ES-CLOUD RADAR MODULE: AWAITING DEPLOYMENT")
    elif st.session_state.dash_nav == "TUNER":
        st.info("FREQUENCY TUNER MODULE: AWAITING DEPLOYMENT")
