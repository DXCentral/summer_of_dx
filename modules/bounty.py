import streamlit as st
import pandas as pd
import datetime
import io
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from modules.data_forge import nwr_db, get_gsheet, get_lat_lon_from_city
from modules.importers import calculate_distance

def transmit_bounty_email(op_name, target_call, sel_freq, target_dist, user_email, audio_file, filename):
    """
    Securely transmits the Bounty Claim and attached MP3 directly to High Command via SMTP.
    """
    admin_email = "w4lvhsc@gmail.com"
    try:
        smtp_server = st.secrets["smtp"]["server"]
        smtp_port = st.secrets["smtp"]["port"]
        smtp_user = st.secrets["smtp"]["email"]
        smtp_pass = st.secrets["smtp"]["password"]

        msg = MIMEMultipart()
        msg['From'] = f"Mainframe Alert <{smtp_user}>"
        msg['To'] = admin_email
        msg['Subject'] = f"BOUNTY CLAIM: {op_name} ({target_call})"

        body = f"""New Classified Intercept Claim Received:

Agent: {op_name}
Target: {target_call} ({sel_freq} MHz)
Distance: {target_dist} miles
Agent Email: {user_email}
Timestamp: {datetime.datetime.now(datetime.timezone.utc)} UTC

The intercepted audio payload is attached to this transmission.
"""
        msg.attach(MIMEText(body, 'plain'))

        # Attach the MP3 Audio File
        audio_file.seek(0)
        part = MIMEBase('audio', 'mpeg')
        part.set_payload(audio_file.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename="{filename}"')
        msg.attach(part)

        # Transmit
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"SMTP Audio Error: {e}")
        return False


def render_bounty_module():
    # =========================================================================
    # 🎯 MISSION CONTROL PARAMETERS (UPDATE THESE EVERY 2 WEEKS)
    # =========================================================================
    ACTIVE_CODEWORD = "W3ATH3R"
    DOSSIER_URL = "https://raw.githubusercontent.com/DXCentral/summer_of_dx/86f6f7cb38388eaab6dae0940a34b88071687857/INTERCEPT%20TARGET%20DOSSIER%20-%20ID%20SOD-01-NWR.jpg"
    TARGET_BAND = "NWR"
    MIN_DISTANCE = 100.0
    # =========================================================================

    st.markdown("""
    <style>
    .cipher-box { border: 2px solid #139a9b; background-color: #0a1a1a; padding: 20px; border-radius: 5px; box-shadow: inset 0px 0px 15px rgba(19, 154, 155, 0.2); margin-bottom: 20px; }
    .dossier-box { border: 2px dashed #ff0000; background-color: #1a0505; padding: 25px; margin-top: 20px; margin-bottom: 25px; box-shadow: 0px 0px 20px rgba(255, 0, 0, 0.3); }
    .comms-box { border: 1px solid #333; background-color: #030303; padding: 20px; border-radius: 3px; font-family: monospace; margin-bottom: 25px; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("<h1 style='text-align: center; color: #1bd2d4; text-shadow: 0px 0px 10px rgba(27,210,212,0.8);'>[ ENCRYPTED INTERCEPT REPORT ]</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center; color: #ffffff;'>AWAITING AUTHENTICATION CODEWORD...</h3>", unsafe_allow_html=True)
    st.markdown("---")

    if 'bounty_unlocked' not in st.session_state: 
        st.session_state.bounty_unlocked = False

    # --- 1. CODEWORD INPUT (MOVED TO TOP) ---
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

    # --- 2. UNLOCKED DOSSIER & FORM ---
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
                        
                        with st.spinner("Encrypting transmission and uplifting audio to secure email server..."):
                            timestamp = str(datetime.datetime.now(datetime.timezone.utc))
                            filename = f"SODX_Bounty_{op.get('name')}_{target_call}.mp3"
                            
                            # Transmit via Email
                            email_success = transmit_bounty_email(op.get('name'), target_call, sel_freq, target_dist, b_email, b_audio, filename)
                            
                            if not email_success:
                                st.error("❌ AUDIO UPLINK FAILED. Ensure SMTP Secrets are configured.")
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
                                            "DELIVERED VIA SECURE EMAIL",
                                            "PENDING REVIEW"
                                        ]
                                        bounty_sheet.append_row(row_data)
                                        st.success("✅ BOUNTY CLAIM AND AUDIO TRANSMITTED SUCCESSFULLY. AWAITING COMMAND VERIFICATION.")
                                        st.balloons()
                                    except Exception as e:
                                        st.error(f"❌ DATABASE WRITE FAILED: {e}")
        st.markdown("</div>", unsafe_allow_html=True)


    # --- 3. TRANSMISSION SCHEDULE (MOVED TO BOTTOM AS FOOTER) ---
    st.markdown("""
<div class='comms-box'>
<div style='text-align: center; color: #ffaa00; margin-bottom: 15px;'>
=========================================================<br>
// WARNING: RESTRICTED ACCESS //<br>
// HIGH COMMAND - FIELD COMMUNICATIONS DIVISION //<br>
=========================================================
</div>
<p style='color: #ff3333; font-weight: bold; text-align: center;'>WARNING: TRANSMISSION CHANNELS ACTIVELY MONITORED BY UNKNOWN ENTITIES. MAINTAIN STRICT RADIO SILENCE UNTIL PAYLOAD IS ACQUIRED.</p>
<p style='color: #cccccc;'><b>OPERATIVE ADVISORY:</b><br>
All active field agents must maintain receiver synchronization to the following vectors. Intelligence briefings and targeted intercept authorization will be broadcast according to the schedule provided below.</p>
<p style='color: #1bd2d4; margin-top: 20px; border-bottom: 1px solid #1bd2d4; padding-bottom: 5px;'><b>>> APPROVED TRANSMISSION SOURCES <<</b></p>
<ul style='color: #cccccc; list-style-type: square;'>
<li><b>[HF SHORTWAVE]</b> 4.810 MHz USB - STATUS: <span style='color: #ff3333; font-weight: bold;'>[ OFFLINE / HEAVY JAMMING DETECTED ]</span></li>
<li><b>[SATELLITE LINK]</b> DXStar-1, Transponder 16 - STATUS: <span style='color: #39ff14; font-weight: bold;'>[ ACTIVE - ENCRYPTED ]</span></li>
<li><b>[SECURE WEB PROXY]</b> "DX Radio": thisisprobablydxradio.com - STATUS: <span style='color: #39ff14; font-weight: bold;'>[ ACTIVE - PRIMARY UPLINK ]</span></li>
</ul>
<p style='color: #1bd2d4; margin-top: 20px; border-bottom: 1px solid #1bd2d4; padding-bottom: 5px;'><b>>> BROADCAST SCHEDULE <<</b></p>
<ul style='color: #cccccc; list-style-type: square;'>
<li><b>[HF / SATELLITE]</b> Daily @ 0200Z and 0600Z <i>(Awaiting frequency shift orders)</i></li>
<li><b>[SECURE WEB PROXY]</b> Automated intelligence drop approx. Top of the Hour <i>(Note: Automated proxy broadcasts may vary by +/- 2 minutes to evade algorithmic tracking).</i></li>
</ul>
<p style='color: #1bd2d4; margin-top: 20px; border-bottom: 1px solid #1bd2d4; padding-bottom: 5px;'><b>>> FIELD PROTOCOLS & FAILSAFES <<</b></p>
<ul style='color: #cccccc; list-style-type: square;'>
<li><b>ENCRYPTION ROLL:</b> Cipher keys update dynamically at 0000 UTC. Ensure your SDR cryptographic algorithms are synchronized prior to the 0200Z broadcast.</li>
<li><b>ATMOSPHERIC JAMMING:</b> In the event of catastrophic QRM or D-Layer absorption, maintain radio silence and monitor the secure web portal. Do not break cover.</li>
<li><b>ACKNOWLEDGEMENT:</b> No return transmission required. Monitor, log, and report confirmed targets to the SEDAP mainframe.</li>
</ul>
<p style='color: #cccccc; margin-top: 20px;'>Target dossiers rotate every 14 days. To acquire your target, tune your receiver to an active transmission source and listen for the High Command interval signal. The phonetic authentication cipher will follow.</p>
<p style='color: #cccccc;'>Do not transmit the codeword over open channels. Enter the decrypted string below to unlock your target dossier. If intercepted, disavow all knowledge of High Command.</p>
<div style='text-align: center; color: #ffaa00; margin-top: 25px;'>
// HIGH COMMAND ACTUAL - END OF MESSAGE //
</div>
</div>
    """, unsafe_allow_html=True)
