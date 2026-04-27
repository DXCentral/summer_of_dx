import streamlit as st
import pandas as pd
import pydeck as pdk
import plotly.express as px
import plotly.graph_objects as go
from modules.data_forge import load_global_dashboard_data

def render_dashboard():
    df = load_global_dashboard_data()
    
    if df.empty:
        st.error("🚨 SYSTEM ALERT: DATABANK OFFLINE OR EMPTY.")
        st.stop()
        
    st.markdown("<h1 style='text-align: center; color: #1bd2d4; text-shadow: 0px 0px 10px rgba(27,210,212,0.8);'>GLOBAL INTELLIGENCE COMMAND</h1>", unsafe_allow_html=True)
    
    # DASHBOARD NAVIGATION
    d_cols = st.columns(4)
    if d_cols[0].button("▶ MISSION OVERVIEW", use_container_width=True): 
        st.session_state.dash_nav = "OVERVIEW"
        st.rerun()
    if d_cols[1].button("▶ ACHIEVEMENT TRACKERS", use_container_width=True): 
        st.session_state.dash_nav = "ACHIEVEMENTS"
        st.rerun()
    if d_cols[2].button("▶ ES-CLOUD TRACKER", use_container_width=True): 
        st.session_state.dash_nav = "ES_TRACKER"
        st.rerun()
    if d_cols[3].button("▶ FREQUENCY TUNER", use_container_width=True): 
        st.session_state.dash_nav = "TUNER"
        st.rerun()
        
    st.markdown("<hr style='margin-top: 5px; margin-bottom: 15px;'>", unsafe_allow_html=True)
    
    # GLOBAL FILTER
    c_f1, c_f2 = st.columns([1, 4])
    band_filter = c_f1.selectbox("BANDWIDTH ISOLATION", ["ALL", "AM", "FM", "NWR"], index=0)
    
    if band_filter != "ALL": 
        df = df[df['Band'] == band_filter]
    
    # --- VIEW 1: MISSION OVERVIEW ---
    if st.session_state.dash_nav == "OVERVIEW":
        st.markdown("### 📊 SIGNAL TELEMETRY")
        m = st.columns(6)
        m[0].metric("Total Logs", f"{len(df):,}")
        m[1].metric("Unique Stations", f"{df['Callsign'].nunique():,}")
        m[2].metric("Unique Operators", f"{df['DXer'].nunique():,}")
        m[3].metric("US States Heard", df[df['Country'] == 'United States']['State'].nunique())
        m[4].metric("Countries Heard", df['Country'].nunique())
        m[5].metric("Max Distance", f"{df['Distance'].max():,.0f} mi")
        
        st.markdown("---")
        l_col, r_col = st.columns([2, 1])
        with l_col:
            st.markdown("### 🏆 GLOBAL SCOREBOARD")
            st.caption("Base Score: 1pt per 100mi. +5pt Bonus for Non-SDR.")
            
            scores = df.groupby('DXer').agg(
                Total_Logs=('Callsign', 'count'),
                Base_Points=('Base_Score', 'sum')
            ).reset_index()
            
            bonus_df = df[df['Band'].isin(['AM', 'FM'])].groupby(['DXer', 'Band', 'Month']).size().reset_index(name='Count')
            bonus_df['Bonus'] = bonus_df['Count'].apply(lambda x: 100 if x >= 10 else 0)
            bonuses = bonus_df.groupby('DXer')['Bonus'].sum().reset_index()
            
            scores = scores.merge(bonuses, on='DXer', how='left').fillna(0)
            scores['Total_Score'] = scores['Base_Points'] + scores['Bonus']
            scores = scores.sort_values('Total_Score', ascending=False)
            scores['Power Level'] = scores['Total_Score']
            
            st.dataframe(
                scores[['DXer', 'Total_Logs', 'Base_Points', 'Bonus', 'Total_Score', 'Power Level']],
                column_config={
                    "DXer": "Operator",
                    "Total_Score": st.column_config.NumberColumn("Total Score", format="%d"),
                    "Power Level": st.column_config.ProgressColumn("Power Level", format="%d", min_value=0, max_value=int(scores['Total_Score'].max() if not scores.empty else 100))
                },
                hide_index=True, 
                use_container_width=True
            )
            
        with r_col:
            st.markdown("### 📡 TOP LOGS BY DISTANCE")
            st.caption("Click any column to sort.")
            furthest = df.sort_values('Distance', ascending=False).head(15)
            st.dataframe(
                furthest[['Distance', 'DXer', 'Callsign', 'Band']],
                column_config={
                    "Distance": st.column_config.NumberColumn("Miles", format="%.1f")
                },
                hide_index=True,
                use_container_width=True
            )

    # --- VIEW 2: ACHIEVEMENT TRACKERS ---
    elif st.session_state.dash_nav == "ACHIEVEMENTS":
        st.markdown("### 🎖️ SPECIAL DIRECTIVES & ENDORSEMENTS")
        st.caption("Tracking Operator progress toward elite classification.")
        
        t1, t2 = st.tabs(["[ CENTURY CLUBS (GRIDS & COUNTIES) ]", "[ GRAVEYARD & ROVER MASTERS ]"])
        
        with t1:
            c_grids, c_counties = st.columns(2)
            with c_grids:
                st.markdown("#### 🥇 THE CENTURY CLUB (GRIDS)")
                grids = df.groupby(['DXer', 'Band'])['Station_Grid'].nunique().reset_index(name='Grids').sort_values('Grids', ascending=False)
                grids['Status'] = grids['Grids'].apply(lambda x: "🟢 MASTER" if x >= 100 else "⏳ IN PROGRESS")
                grids['Progress'] = grids['Grids'].apply(lambda x: 100 if x >= 100 else x)
                st.dataframe(
                    grids[['DXer', 'Band', 'Grids', 'Status', 'Progress']],
                    column_config={
                        "Progress": st.column_config.ProgressColumn("Progress to 100", min_value=0, max_value=100, format="%d%%")
                    }, 
                    hide_index=True, 
                    use_container_width=True
                )
                
            with c_counties:
                st.markdown("#### 🦅 COUNTY MASTER")
                counties = df[df['Country'] == 'United States'].groupby(['DXer', 'Band'])['County'].nunique().reset_index(name='Counties').sort_values('Counties', ascending=False)
                counties['Status'] = counties['Counties'].apply(lambda x: "🟢 MASTER" if x >= 100 else "⏳ IN PROGRESS")
                counties['Progress'] = counties['Counties'].apply(lambda x: 100 if x >= 100 else x)
                st.dataframe(
                    counties[['DXer', 'Band', 'Counties', 'Status', 'Progress']],
                    column_config={
                        "Progress": st.column_config.ProgressColumn("Progress to 100", min_value=0, max_value=100, format="%d%%")
                    }, 
                    hide_index=True, 
                    use_container_width=True
                )
                
        with t2:
            c_grave, c_rover = st.columns(2)
            with c_grave:
                st.markdown("#### 🧟 GRAVEYARD MASTER (MW)")
                st.caption("Requires 3+ logs at 500+ miles on all six graveyard frequencies.")
                
                grave_df = df[(df['Band'] == 'AM') & (df['Distance'] >= 500) & (df['Freq_Num'].isin([1230, 1240, 1340, 1400, 1450, 1460]))]
                grave_counts = grave_df.groupby(['DXer', 'Freq_Num']).size().reset_index(name='Logs')
                grave_met = grave_counts[grave_counts['Logs'] >= 3].groupby('DXer').size().reset_index(name='Frequencies Conquered')
                grave_met['Status'] = grave_met['Frequencies Conquered'].apply(lambda x: "🟢 MASTER" if x == 6 else f"⏳ {x}/6 SECURED")
                grave_met['Progress'] = (grave_met['Frequencies Conquered'] / 6) * 100
                
                st.dataframe(
                    grave_met[['DXer', 'Frequencies Conquered', 'Status', 'Progress']].sort_values('Frequencies Conquered', ascending=False),
                    column_config={
                        "Progress": st.column_config.ProgressColumn("Progress", min_value=0, max_value=100, format="%d%%")
                    }, 
                    hide_index=True, 
                    use_container_width=True
                )
                
            with c_rover:
                st.markdown("#### 🚙 ROVER COMMAND")
                st.caption("Ranking Operators by the number of unique transmission grids activated.")
                rover_df = df[df['Category'].str.contains('ROVER', case=False, na=False)]
                if not rover_df.empty:
                    rovers = rover_df.groupby('DXer')['Category'].nunique().reset_index(name='Grids Activated').sort_values('Grids Activated', ascending=False)
                    st.dataframe(rovers, hide_index=True, use_container_width=True)
                else:
                    st.info("No Rover telemetry detected in current databank.")

    # --- VIEW 3: ES-CLOUD TRACKER ---
    elif st.session_state.dash_nav == "ES_TRACKER":
        st.markdown("### ☁️ SPORADIC-E CLOUD RADAR")
        st.caption("Visualizing the geographic mid-points of all logs tagged as 'Sporadic E'.")
        
        es_df = df[df['Prop_Mode'].str.upper() == 'SPORADIC E'].copy()
        if es_df.empty:
            st.warning("No Sporadic E telemetry found in current filter parameters.")
        else:
            es_df['Mid_Lat'] = (es_df['DX_Lat'] + es_df['ST_Lat']) / 2
            es_df['Mid_Lon'] = (es_df['DX_Lon'] + es_df['ST_Lon']) / 2
            es_df = es_df.dropna(subset=['Mid_Lat', 'Mid_Lon'])
            
            layers = [pdk.Layer(
                'HeatmapLayer', 
                data=es_df[['Mid_Lat', 'Mid_Lon', 'DXer']], 
                get_position='[Mid_Lon, Mid_Lat]',
                radius_pixels=65, 
                intensity=2.0, 
                threshold=0.03, 
                color_range=[[19, 154, 155, 50], [27, 210, 212, 100], [150, 240, 240, 150], [200, 250, 250, 200], [255, 255, 255, 255]]
            )]
            st.pydeck_chart(pdk.Deck(map_style='https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json', initial_view_state=pdk.ViewState(latitude=38, longitude=-95, zoom=3.4), layers=layers))
            
    # --- VIEW 4: FREQUENCY TUNER ---
    elif st.session_state.dash_nav == "TUNER":
        st.markdown("### 🎚️ SIGNAL FORENSICS TUNER")
        st.caption("Use the Coarse (1.0 MHz) or Fine (0.2 MHz) buttons to tune the dial, or enter a specific frequency directly.")
        
        current = st.session_state.selected_mhz
        base_freq = 87.7 if current in ["TUNE...", None] else current
        
        t1, t2, t3, t4, t5 = st.columns([1, 1, 3, 1, 1])
        if t1.button("⏪ -1.0", use_container_width=True): 
            st.session_state.selected_mhz = round(base_freq - 1.0, 1)
            st.rerun()
        if t2.button("◀ -0.2", use_container_width=True): 
            st.session_state.selected_mhz = round(base_freq - 0.2, 1)
            st.rerun()
        
        with t3:
            if current in ["TUNE...", None]: 
                st.markdown('<div class="lcd-screen">TUNE...</div>', unsafe_allow_html=True)
            else: 
                st.markdown(f'<div class="lcd-screen">{current:.1f} <span class="lcd-unit">MHz</span></div>', unsafe_allow_html=True)
            st.text_input("DIRECT ENTRY (e.g. 921 for 92.1)", key="freq_direct_entry", on_change=lambda: st.session_state.update(selected_mhz=round(float(str(st.session_state.freq_direct_entry).replace('.','').ljust(3,'0')[:-1] + '.' + str(st.session_state.freq_direct_entry).replace('.','').ljust(3,'0')[-1]), 1) if st.session_state.freq_direct_entry else "TUNE..."))
            
        if t4.button("+0.2 ▶", use_container_width=True): 
            st.session_state.selected_mhz = round(base_freq + 0.2, 1)
            st.rerun()
        if t5.button("+1.0 ⏩", use_container_width=True): 
            st.session_state.selected_mhz = round(base_freq + 1.0, 1)
            st.rerun()
        
        if current not in ["TUNE...", None]:
            st.markdown("---")
            f_df = df[df['Freq_Num'] == current]
            if f_df.empty:
                st.warning("No signal intelligence recorded on this frequency.")
            else:
                c1, c2, c3 = st.columns(3)
                c1.markdown('<div class="stat-header">TOTAL LOGS</div>', unsafe_allow_html=True)
                c1.markdown(f'<div class="stat-val">{len(f_df):,}</div>', unsafe_allow_html=True)
                
                c2.markdown('<div class="stat-header">UNIQUE DXERS</div>', unsafe_allow_html=True)
                c2.markdown(f'<div class="stat-val">{f_df["DXer"].nunique():,}</div>', unsafe_allow_html=True)
                
                c3.markdown('<div class="stat-header">UNIQUE STATIONS</div>', unsafe_allow_html=True)
                c3.markdown(f'<div class="stat-val">{f_df["Callsign"].nunique():,}</div>', unsafe_allow_html=True)
                
                st.dataframe(f_df[['DXer', 'Date_Str', 'Time_Str', 'Callsign', 'City', 'State', 'Distance', 'SDR_Used']], hide_index=True, use_container_width=True)
