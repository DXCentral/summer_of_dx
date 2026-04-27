import streamlit as st
import pandas as pd
import pydeck as pdk
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import datetime
import time
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

    # --- SESSION STATE INITIALIZATION (SEDAP MECHANICS) ---
    if 'dash_nav' not in st.session_state: st.session_state.dash_nav = "OVERVIEW"
    if 'sel_dxer' not in st.session_state: st.session_state.sel_dxer = None
    if 'sel_state' not in st.session_state: st.session_state.sel_state = None
    if 'sel_country' not in st.session_state: st.session_state.sel_country = None
    if 'sel_mhz' not in st.session_state: st.session_state.sel_mhz = "TUNE..."
    if 'freq_direct_entry' not in st.session_state: st.session_state.freq_direct_entry = ""
    
    # Timelapse & Map States
    if 'full_screen' not in st.session_state: st.session_state.full_screen = False
    if 'playing' not in st.session_state: st.session_state.playing = False
    if 'p_idx' not in st.session_state: st.session_state.p_idx = 0
    if 'map_key' not in st.session_state: st.session_state.map_key = 500000
    if 'dx_map_key' not in st.session_state: st.session_state.dx_map_key = 1000000
    if 'selected_dx_loc' not in st.session_state: st.session_state.selected_dx_loc = None

    def reset_flyouts():
        st.session_state.sel_dxer = None
        st.session_state.sel_state = None
        st.session_state.sel_country = None
        st.session_state.selected_dx_loc = None

    if st.session_state.full_screen:
        st.markdown("""<style>[data-testid="stSidebar"], [data-testid="stHeader"] { display: none !important; } .stMain { padding: 0 !important; }</style>""", unsafe_allow_html=True)

    st.markdown("<h1 style='text-align: center; color: #1bd2d4; text-shadow: 0px 0px 10px rgba(27,210,212,0.8);'>GLOBAL INTELLIGENCE COMMAND</h1>", unsafe_allow_html=True)
    
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

    # --- REUSABLE FLYOUT STYLES ---
    st.markdown("""
    <style>
    .flyout-box { border: 1px solid #139a9b; padding: 15px; background-color: #050505; box-shadow: 0px 0px 10px rgba(19, 154, 155, 0.2); }
    .flyout-title { color: #1bd2d4; margin-top: 0; font-size: 1.8rem; text-transform: uppercase; border-bottom: 1px dashed #139a9b; padding-bottom: 5px; }
    .flyout-header { color: #139a9b; font-size: 0.85rem; margin-top: 15px; text-transform: uppercase; letter-spacing: 1px; }
    .flyout-val { font-size: 1.8rem; color: #ffffff; line-height: 1.1; }
    .flyout-sub { font-size: 0.9rem; color: #a3e8e9; }
    </style>
    """, unsafe_allow_html=True)

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
                    
                    st.markdown("<div class='flyout-box'>", unsafe_allow_html=True)
                    st.markdown(f"<div class='flyout-title'>AGENT: {agent}</div>", unsafe_allow_html=True)
                    
                    if st.button("❌ CLOSE DOSSIER", use_container_width=True):
                        st.session_state.sel_dxer = None
                        st.rerun()
                        
                    f_row = agent_df.sort_values('Distance', ascending=False).iloc[0] if not agent_df.empty else None
                    if f_row is not None:
                        st.markdown("<div class='flyout-header'>FURTHEST INTERCEPT</div>", unsafe_allow_html=True)
                        st.markdown(f"<div class='flyout-val'>{f_row['Distance']:,.0f} mi</div>", unsafe_allow_html=True)
                        st.markdown(f"<div class='flyout-sub'>{f_row['Frequency']} MHz - {f_row['Callsign']} ({f_row['City']}, {f_row['State']})<br>{f_row['Date_Str']} at {f_row['Time_Str']}</div>", unsafe_allow_html=True)
                    
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown("<div class='flyout-header'>TOP TARGET STATES</div>", unsafe_allow_html=True)
                        st.dataframe(agent_df.groupby('State').size().reset_index(name='Logs').sort_values('Logs', ascending=False).head(5), hide_index=True, use_container_width=True)
                    with c2:
                        st.markdown("<div class='flyout-header'>MOST CAUGHT STATIONS</div>", unsafe_allow_html=True)
                        st.dataframe(agent_df.groupby('Callsign').size().reset_index(name='Logs').sort_values('Logs', ascending=False).head(5), hide_index=True, use_container_width=True)
                    
                    st.markdown("</div>", unsafe_allow_html=True)

    # =====================================================================
    # VIEW 2: GEOGRAPHIC INTELLIGENCE
    # =====================================================================
    elif st.session_state.dash_nav == "GEOGRAPHY":
        st.markdown("### 🗺️ GEOSPATIAL ANALYSIS")
        geo_tabs = st.tabs(["[ US STATE DENSITY ]", "[ GLOBAL DENSITY ]", "[ RECEIVER NETWORK MAP ]"])
        
        with geo_tabs[0]:
            st.caption("👈 Select a State on the map to open the Tactical Flyout.")
            us_df = filt_df[filt_df['Country'] == 'United States']
            cm1, cm2 = st.columns([3, 2]) if st.session_state.sel_state else st.columns([1, 0.001])
            
            with cm1:
                state_counts = us_df.groupby('State').size().reset_index(name='Logs')
                fig_us = px.choropleth(state_counts, locations='State', locationmode="USA-states", color='Logs', scope="usa", color_continuous_scale=CYAN_SCALE, template="plotly_dark")
                fig_us.update_layout(paper_bgcolor='rgba(0,0,0,0)', geo=dict(bgcolor='rgba(0,0,0,0)', lakecolor='#050505'), margin={"r":0,"t":0,"l":0,"b":0}, height=500)
                
                ev_st = st.plotly_chart(fig_us, use_container_width=True, on_select="rerun", key=f"m_state_{st.session_state.map_key}")
                if ev_st and ev_st.get("selection") and ev_st["selection"].get("points"):
                    n_state = ev_st["selection"]["points"][0]["location"]
                    if st.session_state.sel_state != n_state:
                        st.session_state.sel_state = n_state
                        st.rerun()
                        
            if st.session_state.sel_state:
                with cm2:
                    t_state = st.session_state.sel_state
                    t_state_df = us_df[us_df['State'] == t_state]
                    
                    st.markdown("<div class='flyout-box'>", unsafe_allow_html=True)
                    st.markdown(f"<div class='flyout-title'>REGION: {t_state}</div>", unsafe_allow_html=True)
                    
                    if st.button("❌ CLOSE DOSSIER", key="close_state", use_container_width=True):
                        st.session_state.sel_state = None
                        st.session_state.map_key += 1
                        st.rerun()
                        
                    st.markdown("<div class='flyout-header'>TOTAL LOGS</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='flyout-val'>{len(t_state_df):,}</div>", unsafe_allow_html=True)
                    
                    f_row = t_state_df.sort_values('Distance', ascending=False).iloc[0] if not t_state_df.empty else None
                    if f_row is not None:
                        st.markdown("<div class='flyout-header'>FURTHEST INTERCEPT</div>", unsafe_allow_html=True)
                        st.markdown(f"<div style='font-size:1.3rem; color:#fff;'>{f_row['Distance']:,.0f} mi</div>", unsafe_allow_html=True)
                        st.markdown(f"<div class='flyout-sub'>{f_row['Callsign']} ({f_row['City']}) caught by {f_row['DXer']}</div>", unsafe_allow_html=True)
                    
                    st.markdown("<div class='flyout-header'>TOP AGENTS TARGETING REGION</div>", unsafe_allow_html=True)
                    st.dataframe(t_state_df.groupby('DXer').size().reset_index(name='Logs').sort_values('Logs', ascending=False).head(5), hide_index=True, use_container_width=True)
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
            st.caption("👈 Click any location cluster to interrogate specific DXer intelligence.")
            
            col_rx_map, col_rx_fly = st.columns([3, 1]) if st.session_state.selected_dx_loc else st.columns([1, 0.001])
            
            with col_rx_map:
                dx_map_data = filt_df.groupby(['DXer_City', 'DX_Lat', 'DX_Lon']).agg(
                    Logs=('Callsign', 'count'),
                    DXer_Count=('DXer', 'nunique'),
                    DXers=('DXer', lambda x: '<br>'.join(x.unique()))
                ).reset_index()
                
                fig_dx = px.scatter_mapbox(
                    dx_map_data, lat='DX_Lat', lon='DX_Lon', size='Logs', color='Logs',
                    hover_name='DXer_City', 
                    hover_data={'DX_Lat':False, 'DX_Lon':False, 'DXers':True, 'DXer_Count':True},
                    color_continuous_scale=CYAN_SCALE, zoom=4.2, center=dict(lat=38, lon=-95), size_max=45
                )
                fig_dx.update_layout(mapbox_style="carto-darkmatter", height=600, paper_bgcolor='rgba(0,0,0,0)', margin={"r":0,"t":0,"l":0,"b":0})
                
                ev_dx = st.plotly_chart(fig_dx, use_container_width=True, on_select="rerun", key=f"dx_map_{st.session_state.dx_map_key}")
                
                if ev_dx and ev_dx.get("selection") and ev_dx["selection"].get("points"):
                    pt = ev_dx["selection"]["points"][0]
                    if "hovertext" in pt:
                        new_loc = pt["hovertext"]
                        if st.session_state.selected_dx_loc != new_loc:
                            st.session_state.selected_dx_loc = new_loc
                            st.rerun()

            if st.session_state.selected_dx_loc:
                with col_rx_fly:
                    loc = st.session_state.selected_dx_loc
                    loc_df = filt_df[filt_df['DXer_City'] == loc]
                    
                    st.markdown("<div class='flyout-box'>", unsafe_allow_html=True)
                    st.markdown(f"<div class='flyout-title'>📍 {loc}</div>", unsafe_allow_html=True)
                    
                    if st.button("❌ CLEAR LOCATION", key="cl_dx_map", use_container_width=True): 
                        st.session_state.selected_dx_loc = None
                        st.session_state.dx_map_key += 1
                        st.rerun()
                        
                    st.markdown("<div class='flyout-header'>TOTAL LOGS</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='flyout-val'>{len(loc_df):,}</div>", unsafe_allow_html=True)
                    
                    f_r = loc_df.sort_values('Distance', ascending=False).iloc[0] if not loc_df.empty else None
                    if f_r is not None:
                        st.markdown("<div class='flyout-header'>FURTHEST RECEPTION</div>", unsafe_allow_html=True)
                        st.markdown(f"<div style='font-size:1.3rem; color:#fff;'>{f_r['Distance']:,.0f} MILES</div>", unsafe_allow_html=True)
                        st.markdown(f"<div class='flyout-sub'>{f_r['Frequency']} - {f_r['Callsign']}, {f_r['State']} on {f_r['Date_Str']} by {f_r['DXer']}</div>", unsafe_allow_html=True)

                    st.markdown("<div class='flyout-header'>LOCAL AGENTS</div>", unsafe_allow_html=True)
                    st.dataframe(loc_df.groupby('DXer').size().reset_index(name='Logs').sort_values('Logs', ascending=False), hide_index=True, use_container_width=True)
                    st.markdown("</div>", unsafe_allow_html=True)

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
    # VIEW 4: TIMELAPSE & ES-CLOUD RADAR (SEDAP LOGIC PORTED)
    # =====================================================================
    elif st.session_state.dash_nav == "ES_TRACKER":
        st.markdown("### ☁️ IONOSPHERIC PROPAGATION ANALYSIS")
        
        vm = st.pills("MAP LAYER SELECTION", ["Heatmap (Midpoints)", "Path Line Analysis"], default="Heatmap (Midpoints)")
        
        hc1, hc2 = st.columns([1, 2])
        with hc1:
            range_on = st.checkbox("Enable Date Range Mode", value=True) 
            avail_days = sorted(filt_df['Date_Obj'].dropna().unique()) 
            if not avail_days:
                st.warning("No dates available for timeline.")
                st.stop()
                
            if not range_on:
                date_sel = st.date_input("Select Event Date", value=avail_days[-1])
                map_df = filt_df[filt_df['Date_Obj'] == date_sel].copy()
            else:
                date_range = st.date_input("Select Date Range", value=(avail_days[0], avail_days[-1]))
                if len(date_range) == 2: 
                    map_df = filt_df[(filt_df['Date_Obj'] >= date_range[0]) & (filt_df['Date_Obj'] <= date_range[1])].copy()
                else: 
                    map_df = filt_df[filt_df['Date_Obj'] == date_range[0]].copy()
            
            speed_sets = {"1x": {"delay": 0.2, "step": 1}, "2x": {"delay": 0.1, "step": 2}, "3x": {"delay": 0.05, "step": 3}, "4x": {"delay": 0.01, "step": 4}}
            play_speed = st.selectbox("Playback Speed", options=list(speed_sets.keys()), index=1)
            
            if st.button("📺 VIEW FULL SCREEN" if not st.session_state.full_screen else "❌ EXIT"): 
                st.session_state.full_screen = not st.session_state.full_screen
                st.rerun()

        if not map_df.empty:
            # Force Es Midpoint calculations for Heatmap
            if 'Mid_Lat' not in map_df.columns:
                map_df['Mid_Lat'] = (map_df['DX_Lat'] + map_df['ST_Lat']) / 2
                map_df['Mid_Lon'] = (map_df['DX_Lon'] + map_df['ST_Lon']) / 2

            map_df['DateTime_Key'] = pd.to_datetime(map_df['Date_Str'] + ' ' + map_df['Time_Str'], errors='coerce')
            timeline = map_df.dropna(subset=['DateTime_Key']).sort_values('DateTime_Key')
            time_steps = timeline[['Date_Str', 'Time_Str']].drop_duplicates().values.tolist()
            
            pb1, pb2, pb_txt = st.columns([1, 1, 3])
            if pb1.button("▶ PLAY"): 
                st.session_state.playing = True
                st.session_state.p_idx = 0
                st.rerun()
            if pb2.button("⏹ STOP"): 
                st.session_state.playing = False
                st.rerun()
            
            if st.session_state.playing and len(time_steps) > 0:
                cur_step = time_steps[st.session_state.p_idx]
                cur_date, cur_time = cur_step[0], cur_step[1]
            else:
                times_only = sorted(map_df['Time_Str'].dropna().unique())
                cur_time = hc2.select_slider("Time Control", options=["SHOW ALL"] + times_only, value="SHOW ALL")
                cur_date = "N/A"

            if cur_time == "SHOW ALL":
                pb_txt.write("## 🕒 VIEWING: ALL SELECTED DATA")
                render_df = map_df
            else:
                display_date = f"{cur_date} | " if cur_date != "N/A" else ""
                pb_txt.write(f"## 🕒 {display_date}{cur_time}")
                
                # STROBE EFFECT FIX: 30-Minute Persistence Window
                try:
                    lookback_time_str = (datetime.datetime.strptime(cur_time, '%H:%M') - datetime.timedelta(minutes=30)).strftime('%H:%M')
                except:
                    lookback_time_str = "00:00"
                    
                if st.session_state.playing:
                    render_df = map_df[(map_df['Date_Str'] == cur_date) & (map_df['Time_Str'] <= cur_time) & (map_df['Time_Str'] >= lookback_time_str)]
                else:
                    render_df = map_df[(map_df['Time_Str'] <= cur_time) & (map_df['Time_Str'] >= lookback_time_str)]
            
            # --- RENDER MAP LAYERS ---
            if vm == "Heatmap (Midpoints)":
                es_df = render_df[render_df['Prop_Mode'].str.upper() == 'SPORADIC E']
                layers = [pdk.Layer(
                    'HeatmapLayer', 
                    data=es_df[['Mid_Lat', 'Mid_Lon', 'DXer']].dropna(), 
                    get_position='[Mid_Lon, Mid_Lat]',
                    radius_pixels=65, intensity=2.0, threshold=0.03, 
                    color_range=[[5,5,5,50], [10,64,64,100], [19,154,155,150], [27,210,212,200], [255,255,255,255]]
                )]
            else:
                layers = [pdk.Layer(
                    'LineLayer',
                    data=render_df[['DX_Lat', 'DX_Lon', 'ST_Lat', 'ST_Lon']].dropna(),
                    get_source_position='[DX_Lon, DX_Lat]',
                    get_target_position='[ST_Lon, ST_Lat]',
                    get_width=2,
                    get_color=[27, 210, 212, 100],  # Cyan lines
                )]
                                            
            st.pydeck_chart(pdk.Deck(map_style='https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json', initial_view_state=pdk.ViewState(latitude=38, longitude=-95, zoom=3.4), layers=layers))
            
            # Autoplay loop execution
            if st.session_state.playing:
                conf = speed_sets[play_speed]
                if st.session_state.p_idx + conf['step'] < len(time_steps):
                    st.session_state.p_idx += conf['step']
                    time.sleep(conf['delay'])
                    st.rerun()
                else:
                    st.session_state.playing = False
                    st.rerun()
        else:
            st.warning("No data points available for the selected dates.")

    # =====================================================================
    # VIEW 5: FREQUENCY TUNER
    # =====================================================================
    elif st.session_state.dash_nav == "TUNER":
        st.markdown("### 🎚️ SIGNAL FORENSICS TUNER")
        st.caption("Use the Coarse (1.0) or Fine (0.2 / 0.01) buttons to tune the dial, or enter a specific frequency directly.")
        
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
        
        step_val = 0.2 if band_filter == "FM" else (10 if band_filter == "AM" else 0.025)
        coarse_val = 1.0 if band_filter == "FM" else 100
        
        if t1.button(f"⏪ -{coarse_val}", use_container_width=True): 
            st.session_state.sel_mhz = round(base_freq - coarse_val, 3)
            st.rerun()
        if t2.button(f"◀ -{step_val}", use_container_width=True): 
            st.session_state.sel_mhz = round(base_freq - step_val, 3)
            st.rerun()
        
        with t3:
            if current in ["TUNE...", None]: 
                st.markdown('<div class="lcd-screen">TUNE...</div>', unsafe_allow_html=True)
            else: 
                disp = f"{current:.1f}" if current > 50 else f"{current:.0f}"
                st.markdown(f'<div class="lcd-screen">{disp} <span class="lcd-unit">MHz/kHz</span></div>', unsafe_allow_html=True)
                
            def process_freq():
                raw = st.session_state.freq_direct_entry
                if raw:
                    try:
                        st.session_state.sel_mhz = float(raw)
                    except:
                        pass
                st.session_state.freq_direct_entry = ""
                
            st.text_input("DIRECT ENTRY (e.g. 92.1 or 1230)", key="freq_direct_entry", on_change=process_freq)
            
        if t4.button(f"+{step_val} ▶", use_container_width=True): 
            st.session_state.sel_mhz = round(base_freq + step_val, 3)
            st.rerun()
        if t5.button(f"+{coarse_val} ⏩", use_container_width=True): 
            st.session_state.sel_mhz = round(base_freq + coarse_val, 3)
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
