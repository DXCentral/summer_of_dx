import streamlit as st
import pandas as pd
import pydeck as pdk
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import datetime
from modules.data_forge import load_global_dashboard_data

# --- CYAN ESPIONAGE COLOR PALETTE ---
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
        
    st.markdown("<h1 style='text-align: center; color: #1bd2d4; text-shadow: 0px 0px 10px rgba(27,210,212,0.8);'>GLOBAL INTELLIGENCE COMMAND</h1>", unsafe_allow_html=True)
    
    # --- SESSION STATE FOR FLYOUTS & SELECTIONS ---
    if 'dash_nav' not in st.session_state: st.session_state.dash_nav = "OVERVIEW"
    if 'sel_dxer' not in st.session_state: st.session_state.sel_dxer = None
    if 'sel_state' not in st.session_state: st.session_state.sel_state = None
    if 'sel_country' not in st.session_state: st.session_state.sel_country = None
    if 'sel_mhz' not in st.session_state: st.session_state.sel_mhz = "TUNE..."
    if 'freq_direct_entry' not in st.session_state: st.session_state.freq_direct_entry = ""
    
    def reset_flyouts():
        st.session_state.sel_dxer = None
        st.session_state.sel_state = None
        st.session_state.sel_country = None

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
    if d_cols[3].button("▶ ES-CLOUD RADAR", use_container_width=True): 
        st.session_state.dash_nav = "ES_TRACKER"
        reset_flyouts()
        st.rerun()
    if d_cols[4].button("▶ FREQUENCY TUNER", use_container_width=True): 
        st.session_state.dash_nav = "TUNER"
        reset_flyouts()
        st.rerun()
        
    st.markdown("<hr style='margin-top: 5px; margin-bottom: 15px;'>", unsafe_allow_html=True)
    
    # --- GLOBAL FILTERS ---
    st.markdown("<div style='color:#139a9b; margin-bottom: 5px;'>[ GLOBAL INTERCEPT FILTERS ]</div>", unsafe_allow_html=True)
    c_f1, c_f2, c_f3, c_f4 = st.columns(4)
    
    band_filter = c_f1.selectbox("BANDWIDTH", ["ALL", "AM", "FM", "NWR"], index=0)
    prop_filter = c_f2.selectbox("PROPAGATION", ["ALL"] + sorted(df['Prop_Mode'].dropna().unique().tolist()))
    sdr_filter = c_f3.selectbox("HARDWARE", ["ALL", "Non-SDR Only", "SDR Only"])
    cat_filter = c_f4.selectbox("OPERATOR CATEGORY", ["ALL", "Home QTH", "Rover"])

    # Apply Filters
    filt_df = df.copy()
    if band_filter != "ALL": filt_df = filt_df[filt_df['Band'] == band_filter]
    if prop_filter != "ALL": filt_df = filt_df[filt_df['Prop_Mode'] == prop_filter]
    if sdr_filter == "Non-SDR Only": filt_df = filt_df[filt_df['SDR_Used'] == 'No']
    if sdr_filter == "SDR Only": filt_df = filt_df[filt_df['SDR_Used'] == 'Yes']
    if cat_filter == "Home QTH": filt_df = filt_df[filt_df['Category'] == 'HOME QTH']
    if cat_filter == "Rover": filt_df = filt_df[filt_df['Category'].str.contains('ROVER', case=False, na=False)]
    
    if filt_df.empty:
        st.warning("NO TELEMETRY MATCHES CURRENT FILTER PARAMETERS.")
        st.stop()

    # =====================================================================
    # VIEW 1: MISSION OVERVIEW
    # =====================================================================
    if st.session_state.dash_nav == "OVERVIEW":
        st.markdown("### 📊 SIGNAL TELEMETRY")
        m = st.columns(6)
        m[0].metric("Total Logs", f"{len(filt_df):,}")
        m[1].metric("Unique Stations", f"{filt_df['Callsign'].nunique():,}")
        m[2].metric("Unique DXers", f"{filt_df['DXer'].nunique():,}")
        m[3].metric("US States Heard", filt_df[filt_df['Country'] == 'United States']['State'].nunique())
        m[4].metric("Countries Heard", filt_df['Country'].nunique())
        m[5].metric("Max Distance", f"{filt_df['Distance'].max():,.0f} mi")
        
        st.markdown("---")
        
        # SCOREBOARD CALCULATION
        scores = filt_df.groupby('DXer').agg(
            Total_Logs=('Callsign', 'count'),
            Base_Points=('Base_Score', 'sum')
        ).reset_index()
        
        # Monthly Consistency Bonus Math (100 pts per 10+ logs in a month per band, excluding NWR)
        bonus_df = filt_df[filt_df['Band'].isin(['AM', 'FM'])].groupby(['DXer', 'Band', 'Month']).size().reset_index(name='Count')
        bonus_df['Bonus'] = bonus_df['Count'].apply(lambda x: 100 if x >= 10 else 0)
        bonuses = bonus_df.groupby('DXer')['Bonus'].sum().reset_index()
        
        scores = scores.merge(bonuses, on='DXer', how='left').fillna(0)
        scores['Total_Score'] = scores['Base_Points'] + scores['Bonus']
        scores = scores.sort_values('Total_Score', ascending=False)
        scores['Power Level'] = scores['Total_Score']

        t1, t2 = st.tabs(["[ GLOBAL SCOREBOARD ]", "[ OPERATOR LOG INTEL ]"])
        
        with t1:
            st.markdown("#### 🏆 COMMAND SCOREBOARD")
            st.caption("Base Score: 1pt per 100mi. +5pt Hardware Bonus (Non-SDR). +100pt Monthly Consistency Bonus.")
            st.dataframe(
                scores[['DXer', 'Total_Logs', 'Base_Points', 'Bonus', 'Total_Score', 'Power Level']],
                column_config={
                    "DXer": "Operator",
                    "Total_Score": st.column_config.NumberColumn("Total Score", format="%d"),
                    "Power Level": st.column_config.ProgressColumn("Power Level", format="%d", min_value=0, max_value=int(scores['Total_Score'].max() if not scores.empty else 100))
                },
                hide_index=True, use_container_width=True
            )
            
        with t2:
            st.markdown("#### 👤 DXER PERFORMANCE MATRIX")
            st.caption("👈 Select an Operator row to open their Tactical Flyout.")
            col_tbl, col_fly = st.columns([3, 2]) if st.session_state.sel_dxer else st.columns([1, 0.001])
            
            with col_tbl:
                # Basic Operator Table
                op_stats = filt_df.groupby('DXer').agg(
                    Total_Logs=('Callsign', 'count'),
                    Unique_Stations=('Callsign', 'nunique'),
                    Furthest_Rx=('Distance', 'max')
                ).reset_index().sort_values('Total_Logs', ascending=False)
                
                ev_op = st.dataframe(
                    op_stats, 
                    hide_index=True, use_container_width=True, 
                    on_select="rerun", selection_mode="single-row"
                )
                
                if ev_op and ev_op.get("selection") and ev_op["selection"].get("rows"):
                    idx = ev_op["selection"]["rows"][0]
                    selected_agent = op_stats.iloc[idx]['DXer']
                    if st.session_state.sel_dxer != selected_agent:
                        st.session_state.sel_dxer = selected_agent
                        st.rerun()

            if st.session_state.sel_dxer:
                with col_fly:
                    agent = st.session_state.sel_dxer
                    agent_df = filt_df[filt_df['DXer'] == agent]
                    st.markdown(f"<div style='border: 1px solid #139a9b; padding: 15px; background-color: #050505;'>", unsafe_allow_html=True)
                    st.markdown(f"<h3 style='color: #1bd2d4; margin-top:0;'>AGENT: {agent}</h3>", unsafe_allow_html=True)
                    
                    if st.button("❌ CLOSE DOSSIER", use_container_width=True):
                        st.session_state.sel_dxer = None
                        st.rerun()
                        
                    f_row = agent_df.sort_values('Distance', ascending=False).iloc[0] if not agent_df.empty else None
                    if f_row is not None:
                        st.markdown("<div style='color:#139a9b; font-size:0.8rem; margin-top:10px;'>FURTHEST INTERCEPT</div>", unsafe_allow_html=True)
                        st.markdown(f"<div style='font-size:1.5rem;'>{f_row['Distance']:,.0f} mi</div>", unsafe_allow_html=True)
                        st.markdown(f"<div style='font-size:0.9rem;'>{f_row['Frequency']} MHz - {f_row['Callsign']} ({f_row['City']}, {f_row['State']})<br>{f_row['Date_Str']} at {f_row['Time_Str']}</div>", unsafe_allow_html=True)
                    
                    st.markdown("<div style='color:#139a9b; font-size:0.8rem; margin-top:15px;'>TOP TARGET STATES</div>", unsafe_allow_html=True)
                    st.dataframe(agent_df.groupby('State').size().reset_index(name='Logs').sort_values('Logs', ascending=False).head(3), hide_index=True, use_container_width=True)
                    
                    st.markdown("<div style='color:#139a9b; font-size:0.8rem; margin-top:15px;'>MOST CAUGHT STATIONS</div>", unsafe_allow_html=True)
                    st.dataframe(agent_df.groupby('Callsign').size().reset_index(name='Logs').sort_values('Logs', ascending=False).head(3), hide_index=True, use_container_width=True)
                    
                    st.markdown("</div>", unsafe_allow_html=True)

    # =====================================================================
    # VIEW 2: GEOGRAPHIC INTELLIGENCE
    # =====================================================================
    elif st.session_state.dash_nav == "GEOGRAPHY":
        st.markdown("### 🗺️ GEOSPATIAL ANALYSIS")
        geo_tabs = st.tabs(["[ US STATE DENSITY ]", "[ GLOBAL COUNTRY DENSITY ]", "[ TRANSMITTER HEATMAP ]"])
        
        with geo_tabs[0]:
            st.caption("👈 Select a State on the map to open the Tactical Flyout.")
            us_df = filt_df[filt_df['Country'] == 'United States']
            cm1, cm2 = st.columns([3, 2]) if st.session_state.sel_state else st.columns([1, 0.001])
            
            with cm1:
                state_counts = us_df.groupby('State').size().reset_index(name='Logs')
                fig_us = px.choropleth(state_counts, locations='State', locationmode="USA-states", color='Logs', scope="usa", color_continuous_scale=CYAN_SCALE, template="plotly_dark")
                fig_us.update_layout(paper_bgcolor='rgba(0,0,0,0)', geo=dict(bgcolor='rgba(0,0,0,0)', lakecolor='#050505'), margin={"r":0,"t":0,"l":0,"b":0}, height=500)
                
                ev_st = st.plotly_chart(fig_us, use_container_width=True, on_select="rerun")
                if ev_st and ev_st.get("selection") and ev_st["selection"].get("points"):
                    n_state = ev_st["selection"]["points"][0]["location"]
                    if st.session_state.sel_state != n_state:
                        st.session_state.sel_state = n_state
                        st.rerun()
                        
            if st.session_state.sel_state:
                with cm2:
                    t_state = st.session_state.sel_state
                    t_state_df = us_df[us_df['State'] == t_state]
                    st.markdown(f"<div style='border: 1px solid #139a9b; padding: 15px; background-color: #050505;'>", unsafe_allow_html=True)
                    st.markdown(f"<h3 style='color: #1bd2d4; margin-top:0;'>TARGET REGION: {t_state}</h3>", unsafe_allow_html=True)
                    
                    if st.button("❌ CLOSE DOSSIER", key="close_state", use_container_width=True):
                        st.session_state.sel_state = None
                        st.rerun()
                        
                    st.markdown("<div style='color:#139a9b; font-size:0.8rem; margin-top:10px;'>TOTAL LOGS</div>", unsafe_allow_html=True)
                    st.markdown(f"<div style='font-size:1.5rem;'>{len(t_state_df):,}</div>", unsafe_allow_html=True)
                    
                    f_row = t_state_df.sort_values('Distance', ascending=False).iloc[0] if not t_state_df.empty else None
                    if f_row is not None:
                        st.markdown("<div style='color:#139a9b; font-size:0.8rem; margin-top:10px;'>FURTHEST INTERCEPT</div>", unsafe_allow_html=True)
                        st.markdown(f"<div style='font-size:1.1rem;'>{f_row['Distance']:,.0f} mi</div>", unsafe_allow_html=True)
                        st.markdown(f"<div style='font-size:0.9rem;'>{f_row['Callsign']} ({f_row['City']}) caught by {f_row['DXer']}</div>", unsafe_allow_html=True)
                    
                    st.markdown("<div style='color:#139a9b; font-size:0.8rem; margin-top:15px;'>TOP AGENTS TARGETING REGION</div>", unsafe_allow_html=True)
                    st.dataframe(t_state_df.groupby('DXer').size().reset_index(name='Logs').sort_values('Logs', ascending=False).head(3), hide_index=True, use_container_width=True)
                    st.markdown("</div>", unsafe_allow_html=True)

        with geo_tabs[1]:
            st.caption("Global Intelligence Network Yields.")
            world_counts = filt_df.groupby('Country').size().reset_index(name='Logs')
            fig_w = px.choropleth(world_counts, locations='Country', locationmode="country names", color='Logs', color_continuous_scale=CYAN_SCALE, template="plotly_dark")
            fig_w.update_geos(projection_type="equirectangular", visible=True, lataxis_range=[-45, 75], lonaxis_range=[-130, 20])
            fig_w.update_layout(paper_bgcolor='rgba(0,0,0,0)', geo=dict(bgcolor='rgba(0,0,0,0)', lakecolor='#050505'), margin={"r":0,"t":0,"l":0,"b":0}, height=500)
            st.plotly_chart(fig_w, use_container_width=True)
            
            w_c1, w_c2 = st.columns(2)
            with w_c1:
                st.markdown("#### HEARD COUNTRIES BY AGENT")
                st.dataframe(filt_df.groupby('DXer')['Country'].nunique().reset_index(name='Unique Countries').sort_values('Unique Countries', ascending=False), hide_index=True, use_container_width=True)
            with w_c2:
                st.markdown("#### LOGS BY COUNTRY")
                st.dataframe(world_counts.sort_values('Logs', ascending=False), hide_index=True, use_container_width=True)

        with geo_tabs[2]:
            st.caption("Heatmap of verified transmitter locations.")
            st_map_data = filt_df.dropna(subset=['ST_Lat', 'ST_Lon'])
            if not st_map_data.empty:
                layers = [pdk.Layer(
                    'HeatmapLayer', 
                    data=st_map_data[['ST_Lat', 'ST_Lon', 'Callsign']], 
                    get_position='[ST_Lon, ST_Lat]',
                    radius_pixels=40, intensity=1.5, threshold=0.03, 
                    color_range=[[5,5,5,50], [10,64,64,100], [19,154,155,150], [27,210,212,200], [255,255,255,255]]
                )]
                st.pydeck_chart(pdk.Deck(map_style='https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json', initial_view_state=pdk.ViewState(latitude=38, longitude=-95, zoom=3.4), layers=layers))
            else:
                st.warning("Insufficient coordinates for transmitter map.")

    # =====================================================================
    # VIEW 3: ACHIEVEMENT TRACKERS
    # =====================================================================
    elif st.session_state.dash_nav == "ACHIEVEMENTS":
        st.markdown("### 🎖️ SPECIAL DIRECTIVES & ENDORSEMENTS")
        
        t_cc, t_cm, t_gm, t_rc = st.tabs(["[ CENTURY CLUBS ]", "[ COUNTY MASTER ]", "[ GRAVEYARD MASTER ]", "[ ROVER COMMAND ]"])
        
        with t_cc:
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("#### 📻 JOHN CEREGHIN FM CENTURY CLUB (GRIDS)")
                fm_grids = filt_df[filt_df['Band'] == 'FM'].groupby('DXer')['Station_Grid'].nunique().reset_index(name='Grids').sort_values('Grids', ascending=False)
                fm_grids['Status'] = fm_grids['Grids'].apply(lambda x: "🟢 MASTER" if x >= 100 else "⏳ IN PROGRESS")
                fm_grids['Progress'] = fm_grids['Grids'].apply(lambda x: 100 if x >= 100 else x)
                st.dataframe(fm_grids[['DXer', 'Grids', 'Status', 'Progress']], column_config={"Progress": st.column_config.ProgressColumn("To 100", min_value=0, max_value=100)}, hide_index=True, use_container_width=True)
            
            with c2:
                st.markdown("#### 📻 MW CENTURY CLUB (GRIDS)")
                mw_grids = filt_df[filt_df['Band'] == 'AM'].groupby('DXer')['Station_Grid'].nunique().reset_index(name='Grids').sort_values('Grids', ascending=False)
                mw_grids['Status'] = mw_grids['Grids'].apply(lambda x: "🟢 MASTER" if x >= 100 else "⏳ IN PROGRESS")
                mw_grids['Progress'] = mw_grids['Grids'].apply(lambda x: 100 if x >= 100 else x)
                st.dataframe(mw_grids[['DXer', 'Grids', 'Status', 'Progress']], column_config={"Progress": st.column_config.ProgressColumn("To 100", min_value=0, max_value=100)}, hide_index=True, use_container_width=True)
                
        with t_cm:
            st.markdown("#### 🦅 COUNTY MASTER (MW & FM)")
            counties = filt_df[filt_df['Country'] == 'United States'].groupby(['DXer', 'Band'])['County'].nunique().reset_index(name='Counties').sort_values('Counties', ascending=False)
            counties['Status'] = counties['Counties'].apply(lambda x: "🟢 MASTER" if x >= 100 else "⏳ IN PROGRESS")
            counties['Progress'] = counties['Counties'].apply(lambda x: 100 if x >= 100 else x)
            st.dataframe(counties[['DXer', 'Band', 'Counties', 'Status', 'Progress']], column_config={"Progress": st.column_config.ProgressColumn("To 100", min_value=0, max_value=100)}, hide_index=True, use_container_width=True)

        with t_gm:
            st.markdown("#### 🧟 GRAVEYARD MASTER (MW)")
            st.caption("Requires 3+ logs at 500+ miles on all six graveyard frequencies (1230, 1240, 1340, 1400, 1450, 1460).")
            grave_df = filt_df[(filt_df['Band'] == 'AM') & (filt_df['Distance'] >= 500) & (filt_df['Freq_Num'].isin([1230, 1240, 1340, 1400, 1450, 1460]))]
            grave_counts = grave_df.groupby(['DXer', 'Freq_Num']).size().reset_index(name='Logs')
            grave_met = grave_counts[grave_counts['Logs'] >= 3].groupby('DXer').size().reset_index(name='Frequencies_Conquered')
            
            # Merge back all AM DXers so everyone shows up on the board
            all_am_dxers = pd.DataFrame(filt_df[filt_df['Band'] == 'AM']['DXer'].unique(), columns=['DXer'])
            grave_board = all_am_dxers.merge(grave_met, on='DXer', how='left').fillna(0)
            grave_board['Status'] = grave_board['Frequencies_Conquered'].apply(lambda x: "🟢 MASTER" if x >= 6 else f"⏳ {int(x)}/6 SECURED")
            grave_board['Progress'] = (grave_board['Frequencies_Conquered'] / 6) * 100
            st.dataframe(grave_board.sort_values('Frequencies_Conquered', ascending=False), column_config={"Progress": st.column_config.ProgressColumn("Mission %", min_value=0, max_value=100)}, hide_index=True, use_container_width=True)

        with t_rc:
            st.markdown("#### 🚙 ROVER COMMAND")
            st.caption("Ranking Operators by the number of unique transmission locations activated.")
            rover_df = filt_df[filt_df['Category'].str.contains('ROVER', case=False, na=False)]
            if not rover_df.empty:
                rovers = rover_df.groupby('DXer').agg(
                    Locations_Activated=('Category', 'nunique'),
                    Total_Rover_Logs=('Callsign', 'count')
                ).reset_index().sort_values('Locations_Activated', ascending=False)
                st.dataframe(rovers, hide_index=True, use_container_width=True)
            else:
                st.info("No Rover telemetry detected in current databank.")

    # =====================================================================
    # VIEW 4: ES-CLOUD RADAR
    # =====================================================================
    elif st.session_state.dash_nav == "ES_TRACKER":
        st.markdown("### ☁️ SPORADIC-E CLOUD RADAR")
        st.caption("Visualizing the calculated geographic mid-points of all logs tagged as 'Sporadic E'.")
        
        es_df = filt_df[filt_df['Prop_Mode'].str.upper() == 'SPORADIC E'].copy()
        if es_df.empty:
            st.warning("No Sporadic E telemetry found in current filter parameters.")
        else:
            # Calculate midpoints if not existing
            if 'Mid_Lat' not in es_df.columns:
                es_df['Mid_Lat'] = (es_df['DX_Lat'] + es_df['ST_Lat']) / 2
                es_df['Mid_Lon'] = (es_df['DX_Lon'] + es_df['ST_Lon']) / 2
                
            es_df = es_df.dropna(subset=['Mid_Lat', 'Mid_Lon'])
            
            if not es_df.empty:
                layers = [pdk.Layer(
                    'HeatmapLayer', 
                    data=es_df[['Mid_Lat', 'Mid_Lon', 'DXer']], 
                    get_position='[Mid_Lon, Mid_Lat]',
                    radius_pixels=65, intensity=2.0, threshold=0.03, 
                    color_range=[[5,5,5,50], [10,64,64,100], [19,154,155,150], [27,210,212,200], [255,255,255,255]]
                )]
                st.pydeck_chart(pdk.Deck(map_style='https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json', initial_view_state=pdk.ViewState(latitude=38, longitude=-95, zoom=3.4), layers=layers))
            else:
                st.warning("Coordinates missing for Es midpoint calculation.")

    # =====================================================================
    # VIEW 5: FREQUENCY TUNER
    # =====================================================================
    elif st.session_state.dash_nav == "TUNER":
        st.markdown("### 🎚️ SIGNAL FORENSICS TUNER")
        st.caption("Use the Coarse (1.0 MHz) or Fine (0.2 MHz) buttons to tune the dial, or enter a specific frequency directly.")
        
        current = st.session_state.sel_mhz
        base_freq = 87.7 if current in ["TUNE...", None] else current
        
        # Virtual LCD CSS for Tuner
        st.markdown("""
        <style>
        .lcd-screen {
            background-color: #0a4040;
            color: #1bd2d4;
            font-family: 'VT323', monospace;
            font-size: 4.5rem;
            font-weight: bold;
            text-align: center;
            padding: 10px;
            border-radius: 8px;
            border: 2px solid #139a9b;
            box-shadow: inset 0px 0px 15px rgba(27,210,212,0.4);
            line-height: 1.1;
            margin-bottom: 10px;
        }
        .lcd-unit { font-size: 1.8rem; color: #139a9b; }
        </style>
        """, unsafe_allow_html=True)
        
        t1, t2, t3, t4, t5 = st.columns([1, 1, 3, 1, 1])
        if t1.button("⏪ -1.0", use_container_width=True): 
            st.session_state.sel_mhz = round(base_freq - 1.0, 1)
            st.rerun()
        if t2.button("◀ -0.2", use_container_width=True): 
            st.session_state.sel_mhz = round(base_freq - 0.2, 1)
            st.rerun()
        
        with t3:
            if current in ["TUNE...", None]: 
                st.markdown('<div class="lcd-screen">TUNE...</div>', unsafe_allow_html=True)
            else: 
                st.markdown(f'<div class="lcd-screen">{current:.1f} <span class="lcd-unit">MHz/kHz</span></div>', unsafe_allow_html=True)
                
            def process_freq():
                raw = st.session_state.freq_direct_entry
                if raw:
                    try:
                        st.session_state.sel_mhz = float(raw)
                    except:
                        pass
                st.session_state.freq_direct_entry = ""
                
            st.text_input("DIRECT ENTRY (e.g. 92.1 or 1230)", key="freq_direct_entry", on_change=process_freq)
            
        if t4.button("+0.2 ▶", use_container_width=True): 
            st.session_state.sel_mhz = round(base_freq + 0.2, 1)
            st.rerun()
        if t5.button("+1.0 ⏩", use_container_width=True): 
            st.session_state.sel_mhz = round(base_freq + 1.0, 1)
            st.rerun()
        
        if current not in ["TUNE...", None]:
            st.markdown("---")
            f_df = filt_df[filt_df['Freq_Num'] == current]
            if f_df.empty:
                st.warning("No signal intelligence recorded on this frequency for current filters.")
            else:
                c1, c2, c3 = st.columns(3)
                c1.markdown(f"<div style='color:#139a9b;'>TOTAL LOGS</div><div style='font-size:2rem;'>{len(f_df):,}</div>", unsafe_allow_html=True)
                c2.markdown(f"<div style='color:#139a9b;'>UNIQUE DXERS</div><div style='font-size:2rem;'>{f_df['DXer'].nunique():,}</div>", unsafe_allow_html=True)
                c3.markdown(f"<div style='color:#139a9b;'>UNIQUE STATIONS</div><div style='font-size:2rem;'>{f_df['Callsign'].nunique():,}</div>", unsafe_allow_html=True)
                
                st.markdown("<br>#### FREQUENCY INTERCEPT LOG", unsafe_allow_html=True)
                st.dataframe(f_df[['DXer', 'Date_Str', 'Time_Str', 'Callsign', 'City', 'State', 'Distance', 'SDR_Used']], hide_index=True, use_container_width=True)
