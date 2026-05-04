import streamlit as st
import pandas as pd
import datetime
from modules.data_forge import load_global_dashboard_data

def render_terminal_home(awards_active=True, bounty_active=True):
    st.markdown('<div class="typewriter">GREETINGS, FELLOW SIGNAL TRAVELER.<br>WOULD YOU LIKE TO PLAY A GAME?<span class="blink">_</span></div>', unsafe_allow_html=True)
    
    if "gcp_service_account" not in st.secrets:
        st.error("🚨 [ SYSTEM ALERT ] DATALINK OFFLINE. Streamlit Secrets not configured. Logs cannot be submitted to the Google Sheet.")
    if not awards_active:
        st.warning("⚠️ AWARDS MODULE OFFLINE. Ensure 'modules/awards.py' is deployed to activate Century Club notifications.")
    if not bounty_active:
        st.warning("⚠️ BOUNTY MODULE OFFLINE. Ensure 'modules/bounty.py' is deployed.")
        
    st.write("Use the **[ SYSTEM COMMAND MENU ]** in the sidebar to navigate the mainframe.")
    
    # --- LOAD DATABANK ---
    df = load_global_dashboard_data()
    
    st.markdown("---")
    
    if not df.empty:
        # --- 1. MOST RECENT INTERCEPTS (ROTATING TICKER) ---
        st.markdown("### 📡 MOST RECENT INTERCEPT REPORTS", unsafe_allow_html=True)
        
        # Grab bottom 5 rows (most recently appended), reverse so newest is first
        recent_logs = df.tail(5).iloc[::-1]
        
        ticker_html = "<div class='log-ticker-container'>"
        for i, (_, r) in enumerate(recent_logs.iterrows()):
            # Location Formatting
            dx_loc = f"{r.get('DXer_City', '')}, {r.get('DXer_State', '')}" if r.get('DXer_Country') == "United States" else f"{r.get('DXer_City', '')}, {r.get('DXer_Country', '')}"
            st_loc = f"{r.get('City', '')}, {r.get('State', '')}" if r.get('Country') == "United States" else f"{r.get('City', '')}, {r.get('Country', '')}"
            
            # Conditional Formatting
            prop = f" | {r.get('Prop_Mode', '')}" if r.get('Band') in ['FM', 'NWR'] and pd.notna(r.get('Prop_Mode')) and r.get('Prop_Mode') != " - " else ""
            grid = f" | Grid: {r.get('Station_Grid', '')}" if r.get('Country') == "United States" and pd.notna(r.get('Station_Grid')) and str(r.get('Station_Grid')).strip() not in ["-", ""] else ""
            county = f" | {r.get('County', '')} Co." if r.get('Country') == "United States" and pd.notna(r.get('County')) and str(r.get('County')).strip() not in ["-", ""] else ""
            
            # The Full String
            log_str = f"<b style='color:#1bd2d4;'>{r.get('DXer', 'Unknown')}</b> ({dx_loc}) | {r.get('Date_Str', '')} {r.get('Time_Str', '')}z | {r.get('Band', '')}{prop} | {r.get('Freq_Num', '')} | <b style='color:#ffffff;'>{r.get('Callsign', '')}</b> | {st_loc} | {r.get('Country', '')} | {r.get('Distance', 0):.0f} mi{grid}{county}"
            
            ticker_html += f"<div class='log-slide' style='animation-delay: {i*5}s;'>{log_str}</div>"
        ticker_html += "</div>"
        
        st.markdown(f"""
        <style>
        .log-ticker-container {{ position: relative; height: 50px; overflow: hidden; background: rgba(19, 154, 155, 0.05); border: 1px dashed #139a9b; display: flex; align-items: center; justify-content: center; margin-bottom: 25px; border-radius: 5px;}}
        .log-slide {{ position: absolute; width: 100%; text-align: center; opacity: 0; animation: logFade 25s infinite; color: #a3e8e9; font-size: 1.15rem; padding: 0 15px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;}}
        @keyframes logFade {{
            0%, 16% {{ opacity: 1; z-index: 10; }}
            20%, 100% {{ opacity: 0; z-index: 0; }}
        }}
        </style>
        {ticker_html}
        """, unsafe_allow_html=True)

        # --- 2. REAL-TIME PROPAGATION ALERTS ---
        st.markdown("### 🚨 REAL-TIME PROPAGATION ALERTS", unsafe_allow_html=True)
        
        # Calculate Current UTC - 30 Minutes
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        thirty_mins_ago = now_utc - datetime.timedelta(minutes=30)
        
        def parse_dt(d_str, t_str):
            try:
                return datetime.datetime.strptime(f"{d_str} {str(t_str).zfill(4)}", "%m/%d/%Y %H%M").replace(tzinfo=datetime.timezone.utc)
            except:
                return datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
        
        # Analyze only the last 500 records to save memory processing time
        df_recent = df.tail(500).copy()
        df_recent['Rec_DT'] = df_recent.apply(lambda row: parse_dt(row['Date_Str'], row['Time_Str']), axis=1)
        
        live_logs = df_recent[df_recent['Rec_DT'] >= thirty_mins_ago]
        
        if live_logs.empty:
            st.markdown("""
            <div class='classified-box' style='padding: 10px; margin-top: 5px; margin-bottom: 25px; text-align: center; color: #1bd2d4; opacity: 0.7;'>
                [ NO ACTIVE PROPAGATION ALERTS DETECTED IN THE LAST 30 MINUTES ]
            </div>
            """, unsafe_allow_html=True)
        else:
            def get_path_str(r):
                dx_loc = r.get('DXer_State', '') if r.get('DXer_Country') == "United States" else r.get('DXer_Country', '')
                st_loc = r.get('State', '') if r.get('Country') == "United States" else r.get('Country', '')
                return f"{dx_loc} to {st_loc}"

            mw_paths, fm_es_paths, fm_tr_paths, nwr_es_paths, nwr_tr_paths = set(), set(), set(), set(), set()
            mw_local_countries = ['United States', 'Canada', 'Mexico', 'Cuba', 'Bahamas', 'Puerto Rico']
            
            for _, r in live_logs.iterrows():
                band = r.get('Band')
                path = get_path_str(r)
                
                if band == 'AM':
                    dx_ctry = str(r.get('DXer_Country', '')).strip()
                    st_ctry = str(r.get('Country', '')).strip()
                    
                    if (dx_ctry == 'United States' and st_ctry not in mw_local_countries) or \
                       (dx_ctry not in mw_local_countries and st_ctry == 'United States'):
                        mw_paths.add(path)
                        
                elif band == 'FM':
                    if r.get('Prop_Mode') == 'Sporadic E':
                        fm_es_paths.add(path)
                    elif r.get('Prop_Mode') == 'Tropo' and float(r.get('Distance', 0)) >= 500:
                        fm_tr_paths.add(path)
                        
                elif band == 'NWR':
                    if r.get('Prop_Mode') == 'Sporadic E':
                        nwr_es_paths.add(path)
                    elif r.get('Prop_Mode') == 'Tropo' and float(r.get('Distance', 0)) >= 500:
                        nwr_tr_paths.add(path)
                        
            has_alerts = False
            alerts_html = ""
            
            if mw_paths:
                has_alerts = True
                alerts_html += f"<div style='margin-bottom: 8px;'><b style='color:#ffa500; letter-spacing: 1px;'>MW: ENHANCED</b> | {', '.join(sorted(mw_paths))}</div>"
            if fm_es_paths:
                has_alerts = True
                alerts_html += f"<div style='margin-bottom: 8px;'><b style='color:#39ff14; letter-spacing: 1px;'>FM: SPORADIC Es ALERT</b> | {', '.join(sorted(fm_es_paths))}</div>"
            if fm_tr_paths:
                has_alerts = True
                alerts_html += f"<div style='margin-bottom: 8px;'><b style='color:#39ff14; letter-spacing: 1px;'>FM: ENHANCED TROPO (500+ mi)</b> | {', '.join(sorted(fm_tr_paths))}</div>"
            if nwr_es_paths:
                has_alerts = True
                alerts_html += f"<div style='margin-bottom: 8px;'><b style='color:#1bd2d4; letter-spacing: 1px;'>NWR: SPORADIC Es ALERT</b> | {', '.join(sorted(nwr_es_paths))}</div>"
            if nwr_tr_paths:
                has_alerts = True
                alerts_html += f"<div style='margin-bottom: 8px;'><b style='color:#1bd2d4; letter-spacing: 1px;'>NWR: ENHANCED TROPO (500+ mi)</b> | {', '.join(sorted(nwr_tr_paths))}</div>"
                
            if has_alerts:
                st.markdown(f"""
                <div class='classified-box' style='padding: 15px; margin-top: 5px; margin-bottom: 25px; border-color: #ffa500; background-color: rgba(255, 165, 0, 0.05); font-size: 1.15rem;'>
                    {alerts_html}
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class='classified-box' style='padding: 10px; margin-top: 5px; margin-bottom: 25px; text-align: center; color: #1bd2d4; opacity: 0.7;'>
                    [ NO ACTIVE PROPAGATION ALERTS DETECTED IN THE LAST 30 MINUTES ]
                </div>
                """, unsafe_allow_html=True)

    st.markdown("### 📡 COMMUNIQUE FROM HIGH COMMAND")
    st.info("**ATTENTION ALL AGENTS:** Due to feedback from field operatives, we have re-calibrated the multiplier logic. Moving forward, individual States and Provinces within the **United States, Canada, and Mexico** will each independently count as a multiplier. For all other international intercepts, agents will receive a single multiplier for the **Country** as a whole.")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    col_news, col_contact = st.columns([2, 1])
    
    with col_news:
        st.markdown("### 💾 DECRYPTED PATCH NOTES (CHANGELOG)")
        st.markdown("""
        <div class='classified-box' style='height: 350px; overflow-y: auto;'>
            <b style='color:#1bd2d4;'>[ 2026-05-04 21:57 UTC | v1.1.3 ] GEOSPATIAL INTELLIGENCE UPGRADE:</b> Deployed propagation mode filters (Tropo, Sporadic E, etc.) across all interactive maps for FM and NWR bands. Integrated dynamic active target counters above the HUD to provide instant geospatial context.<br><br>
            <b style='color:#1bd2d4;'>[ 2026-05-04 21:08 UTC | v1.1.2 ] DATA SANITIZATION & METRIC CONVERSION UPDATE:</b> Deployed an intelligent Metric Conversion Engine to handle European comma-decimal distances in bulk imports automatically. Tightened Agent Authentication protocols to prevent blank profile coordinates and ensure accurate distance telemetry.<br><br>
            <b style='color:#1bd2d4;'>[ 2026-05-04 18:52 UTC | v1.1.1 ] INTELLIGENCE MATRIX OPTIMIZED:</b> Fixed progress percentage anomalies on NWR Grid and County ledgers. Appended dynamic [ GLOBAL TOTAL ] rows to all classification matrix tables.<br><br>
            <b style='color:#1bd2d4;'>[ 2026-05-04 18:04 UTC | v1.1.0 ] AGENT DOSSIER & UI OVERHAUL:</b> Deployed the Agent Dossier for deep-dive personal telemetry. Upgraded terminal inputs to tactical pill switches. Added Personal Telemetry data isolation toggle, force-refresh datalink, and enhanced identity sanitization for bulletproof log matching.<br><br>
            <b style='color:#1bd2d4;'>[ 2026-05-02 22:30 UTC | v1.0.4 ] TERMINAL HUD UPGRADE:</b> Deployed Real-Time Propagation Alerts and Live Intercept Ticker. Geospatial caches re-engineered to resolve Gridsquare and County drop-off anomalies.<br><br>
            <b style='color:#1bd2d4;'>[ 2026-05-02 21:00 UTC | v1.0.1 ] SCORING MATRIX RECALIBRATED:</b> Fixed the scoring matrix so that the only multipliers are US States, Canadian Provinces, and Mexican States, alongside a single multiplier per international country.<br><br>
            <b style='color:#1bd2d4;'>[ 2026-05-01 23:00 UTC | v1.0.0 ] SYSTEM ONLINE:</b> Official launch of Operation SUMMER OF DX (DEFCON 6). All tracking databanks and tactical radars initialized.
        </div>
        """, unsafe_allow_html=True)
        
    with col_contact:
        st.markdown("### ⚠️ SECURE COMM LINK")
        st.markdown("""
        <div class='classified-box' style='text-align: center; height: 350px;'>
            If you encounter systemic anomalies, rendering bugs, or require intel clarification, contact High Command immediately:<br><br>
            <b style='font-size: 1.4rem; color: #1bd2d4;'><a href='mailto:admin@summerofdx.com' style='color:#1bd2d4; text-decoration:none;'>admin@summerofdx.com</a></b><br><br>
            <i>Please include your Agent Identity and any active Terminal Error Codes in your transmission.</i>
        </div>
        """, unsafe_allow_html=True)
