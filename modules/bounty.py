import streamlit as st
import pandas as pd
import datetime
import io
from modules.data_forge import nwr_db, get_gsheet, get_lat_lon_from_city
from modules.importers import calculate_distance

# Attempt Google Drive API Import (Requires 'google-api-python-client' in requirements.txt)
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseUpload
    DRIVE_AVAILABLE = True
except ImportError:
    DRIVE_AVAILABLE = False

def upload_to_drive(file_obj, filename, folder_id):
    if not DRIVE_AVAILABLE:
        return "ERROR: Google API Client Not Installed."
        
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        credentials = service_account.Credentials.from_service_account_info(
            creds_dict, scopes=['https://www.googleapis.com/auth/drive']
        )
        service = build('drive', 'v3', credentials=credentials)
        
        file_metadata = {
            'name': filename,
            'parents': [folder_id]
        }
        media = MediaIoBaseUpload(io.BytesIO(file_obj.read()), mimetype=file_obj.type, resumable=True)
        file = service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink').execute()
        
        # Grant read access so you can easily view it from the link
        try:
            service.permissions().create(
                fileId=file.get('id'),
                body={'type': 'anyone', 'role': 'reader'}
            ).execute()
        except Exception:
            pass # Non-fatal if permission fails
            
        return file.get('webViewLink')
    except Exception as e:
        return f"UPLOAD FAILED: {e}"

def render_bounty_module():
    # =========================================================================
    # 🎯 MISSION CONTROL PARAMETERS (UPDATE THESE EVERY 2 WEEKS)
    # =========================================================================
    ACTIVE_CODEWORD = "W3ATH3R"
    DOSSIER_URL = "https://raw.githubusercontent.com/DXCentral/summer_of_dx/86f6f7cb38388eaab6dae0940a34b88071687857/INTERCEPT%20TARGET%20DOSSIER%20-%20ID%20SOD-01-NWR.jpg"
    DRIVE_FOLDER_ID = "1mHZjGI5kFXQ9hvADv325cPxlpsKqjdzd"
    TARGET_BAND = "NWR"
    MIN_DISTANCE = 100.0
    # =========================================================================

    st.markdown("""
    <style>
    .cipher-box { border: 2px solid #139a9b; background-color: #0a1a1a; padding: 20px; border-radius: 5px; box-shadow: inset 0px 0px 15px rgba(19, 154, 155, 0.2); margin-bottom: 20px; }
    .dossier-box { border: 2px dashed #ff0000; background-color: #1a0505; padding: 25px; margin-top: 20px; box-shadow: 0px 0px 20px rgba(255, 0, 0, 0.3); }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("<h1 style='text-align: center; color: #1bd2d4; text-shadow: 0px 0px 10px rgba(27,210,212,0.8);'>[ ENCRYPTED INTERCEPT REPORT ]</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center; color: #ffffff;'>AWAITING AUTHENTICATION CODEWORD...</h3>", unsafe_allow_html=True)
    st.markdown("---")

    if 'bounty_unlocked' not in st.session_state: 
        st.session_state.bounty_unlocked = False

    st.markdown("<div class='cipher-box'>", unsafe_allow_html=True)
    st.markdown("#### 1. INPUT AUDIO CODEWORD")
    st.caption("Enter the classified string broadcasted on DX Radio to unlock this week's dossier.")
    
    c1, c2 = st.columns([3, 1])
    codeword_input = c1.text_input("AUTHENTICATION CODE", placeholder="e.g. ALPHA1", label_visibility="collapsed")
    
    if c2.button("🔴 VERIFY", use_container_width=True):
        if codeword_input.strip().upper() == ACTIVE_CODEWORD.upper():
            st.session_state.bounty_unlocked = True
            st.success("✅ CODEWORD ACCEPTED. DECRYPTING DOSSIER...")
        else:
            st.session_state.bounty_unlocked = False
            st.error("❌ AUTHENTICATION FAILED. INCORRECT CODEWORD.")
    st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.bounty_unlocked:
        # Show Image Dossier
        st.image(DOSSIER_URL, use_container_width=True)
        st.markdown("<br>", unsafe_allow_html=True)
        
        st.markdown("<div class='dossier-box'>", unsafe_allow_html=True)
        st.markdown("### 📥 SUBMIT BOUNTY INTERCEPT CLAIM")
        
        op = st.session_state.operator_profile
        op_lat = float(op.get('lat', 0.0))
        op_lon = float(op.get('lon', 0.0))
        
        st.markdown(f"**AGENT:** {op.get('name', 'UNKNOWN').upper()} | **QTH:** {op.get('city', '')}, {op.get('state', '')}")
        st.markdown("---")
        
        # Frequency Filter (Outside form so it can update the station list dynamically)
        valid_freqs = [162.400, 162.425, 162.450, 162.475, 162.500, 162.525, 162.550]
        sel_freq = st.selectbox("1. TARGET FREQUENCY (MHz)", valid_freqs)
        
        # Distance Math & Station Filter
        if nwr_db.empty:
            st.error("DATABANK OFFLINE. Cannot verify target distances.")
            valid_targets = []
        else:
            # Filter DB by frequency
            f_db = nwr_db[nwr_db['Frequency'] == sel_freq].copy()
            
            # Auto-Geocode and Calculate Distances
            dists = []
            for _, r in f_db.iterrows():
                t_lat = float(r.get('LAT', 0.0))
                t_lon = float(r.get('LON', 0.0))
                if t_lat == 0.0 and t_lon == 0.0:
                    t_lat, t_lon = get_lat_lon_from_city(r['City'], r.get('Country', 'United States'))
                dists.append(calculate_distance(op_lat, op_lon, t_lat, t_lon))
            
            f_db['Dist'] = dists
            f_db = f_db[f_db['Dist'] >= MIN_DISTANCE].sort_values('Dist')
            
            valid_targets = f_db.apply(lambda r: f"{r['Callsign']} ({r['City']}, {r['State']}) | {r['Dist']:.1f} mi", axis=1).tolist()

        if not valid_targets:
            st.warning(f"No NWR stations found over {MIN_DISTANCE} miles on {sel_freq} MHz from your location.")
        else:
            with st.form("bounty_claim_form", clear_on_submit=True):
                sel_station_str = st.selectbox("2. SELECT VALID TARGET STATION", valid_targets)
                b_email = st.text_input("3. SECURE EMAIL UPLINK (REQUIRED FOR CONFIRMATION)")
                
                st.markdown("#### 4. UPLOAD AIRCHECK")
                st.caption(f"Audio proof is required. Please upload an MP3 file (Max length: 30 seconds).")
                b_audio = st.file_uploader("ATTACH MP3 FILE", type=["mp3"])
                
                st.markdown("<br>", unsafe_allow_html=True)
                submit_claim = st.form_submit_button("🚀 TRANSMIT CLAIM TO HIGH COMMAND")
                
                if submit_claim:
                    if not b_email:
                        st.error("❌ FAILED: EMAIL UPLINK REQUIRED.")
                    elif not b_audio:
                        st.error("❌ FAILED: AUDIO AIRCHECK REQUIRED TO CLAIM BOUNTY.")
                    else:
                        # Extract Target Info
                        target_call = sel_station_str.split(' ')[0]
                        target_dist = float(sel_station_str.split('|')[1].replace('mi', '').strip())
                        
                        with st.spinner("Encrypting transmission and uploading audio to secure server..."):
                            timestamp = str(datetime.datetime.now(datetime.timezone.utc))
                            filename = f"SODX_Bounty_{op.get('name')}_{target_call}.mp3"
                            
                            # Upload to Google Drive
                            drive_url = upload_to_drive(b_audio, filename, DRIVE_FOLDER_ID)
                            
                            if "ERROR" in drive_url or "FAILED" in drive_url:
                                st.error(f"❌ AUDIO UPLINK FAILED: {drive_url}")
                            else:
                                sheet = get_gsheet()
                                if sheet is None:
                                    st.error("🚨 DATALINK OFFLINE. Streamlit Secrets not configured.")
                                else:
                                    try:
                                        bounty_sheet = sheet.spreadsheet.worksheet("Bounty_Claims")
                                        row_data = [
                                            timestamp,
                                            op.get('name', ''),
                                            target_call,
                                            sel_freq,
                                            target_dist,
                                            b_email,
                                            drive_url,
                                            "PENDING REVIEW"
                                        ]
                                        bounty_sheet.append_row(row_data)
                                        st.success("✅ BOUNTY CLAIM TRANSMITTED SUCCESSFULLY. AWAITING COMMAND VERIFICATION.")
                                        st.balloons()
                                    except Exception as e:
                                        st.error(f"❌ DATABASE WRITE FAILED: {e}")
        st.markdown("</div>", unsafe_allow_html=True)
