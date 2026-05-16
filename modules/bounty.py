import streamlit as st
import pandas as pd
import datetime
import io
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from modules.data_forge import load_global_dashboard_data, get_gsheet

# =========================================================================
# 🎯 MISSION CONTROL PARAMETERS (BOUNTY 02)
# =========================================================================
ACTIVE_CODEWORD = "EXILE"
BOUNTY_NAME = "OPERATION BORDER INFILTRATION"
BOUNTY_DESC = "Intercept a broadcast originating from outside your home country at a distance of MORE THAN 1,300 miles. The station must be a NEW catch (not previously logged by you in this challenge)."
DOSSIER_URL = "https://github.com/DXCentral/summer_of_dx/blob/14be16928cb50544e46336d97498d5403e1fd39e/INTERCEPT%20TARGET%20DOSSIER%20-%20ID%20SOD-02-ALLBAND.jpg" 
# =========================================================================

def verify_bounty_eligibility(callsign, country, distance):
    """
    Tactical Verification Engine: Ensures the submitted bounty claim 
    meets the strict parameters of Operation Border Infiltration.
    """
    op_name = str(st.session_state.operator_profile.get('name', 'UNKNOWN')).strip().upper()
    op_country = str(st.session_state.operator_profile.get('country', 'United States')).strip().upper()
    target_country = str(country).strip().upper()
    
    # 1. BORDER CHECK: Must be outside the Agent's Home Country
    if target_country == op_country:
        return False, f"Target country ({country}) matches your Home QTH Country ({st.session_state.operator_profile.get('country')}). Target must be international."
        
    # 2. RANGE CHECK: Must be > 1300 miles
    try:
        dist_float = float(distance)
    except:
        dist_float = 0.0
        
    if dist_float <= 1300.0:
        return False, f"Target distance ({dist_float:,.1f} mi) does not exceed the 1,300 mile minimum threshold."
        
    # 3. NO-RECYCLE CHECK: Must not have been logged in the current challenge
    df = load_global_dashboard_data()
    if not df.empty:
        my_logs = df[df['DXer'].str.upper() == op_name]
        if not my_logs.empty:
            # Strictly check the Callsign (case-insensitive) to prevent recycling
            call_match = my_logs[my_logs['Callsign'].str.upper() == str(callsign).strip().upper()]
            if not call_match.empty:
                return False, f"Target station ({callsign}) is already in your global databank. Bounty targets must be new intercepts."
                
    return True, "Target verified against mission parameters."

def transmit_bounty_email(op_name, target_call, target_freq, target_band, target_city, target_country, target_dist, user_email, notes, audio_file, filename):
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

        body = f"""=========================================================
BOUNTY CLAIM INITIATED: {BOUNTY_NAME}
=========================================================
Agent: {op_name}
Target: {target_call} ({target_freq} {target_band})
Location: {target_city}, {target_country}
Distance: {target_dist} miles
Agent Email: {user_email}
Timestamp: {datetime.datetime.now(datetime.timezone.utc)} UTC

AGENT NOTES:
{notes}

=========================================================
SYSTEM VERIFICATION ROUTINE: 
- BORDER CHECK: PASSED (Target Country != Agent Country)
- RANGE CHECK: PASSED (Distance > 1300 mi)
- RECYCLE CHECK: PASSED (Target not found in Agent's local cache)
=========================================================

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
    st.markdown("""
    <style>
    .cipher-box { border: 2px solid #139a9b; background-color: #0a1a1a; padding: 20px; border-radius: 5px; box-shadow: inset 0px 0px 15px rgba(19, 154, 155, 0.2); margin-bottom: 20px; }
    .dossier-box { border: 2px dashed #ff0000; background-color: #1a0505; padding: 25px; margin-top: 20px; margin-bottom: 25px; box-shadow: 0px 0px 20px rgba(255, 0, 0, 0.3); }
    .comms-box { border: 1px solid #333; background-color: #030303; padding: 20px; border-radius: 3px; font-family: monospace; margin-bottom: 25px; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("<h1 style='text-align: center; color: #1bd2d4; text-shadow: 0px 0px 10px rgba(27,210,212,0.8);'>[ ENCRYPTED INTERCEPT REPORT ]</h1>", unsafe_allow_html=True)
    
    if 'bounty_unlocked' not in st.session_state: 
        st.session_state.bounty_unlocked = False

    if not st.session_state.bounty_unlocked:
        st.markdown("<h3 style='text-align: center; color: #ffffff;'>AWAITING AUTHENTICATION CODEWORD...</h3>", unsafe_allow_html=True)
        st.markdown("---")
        
        st.markdown("<div class='cipher-box'>", unsafe_allow_html=True)
        st.markdown("#### 1. INPUT AUDIO CODEWORD")
        st.caption("Enter the classified string broadcasted on DX Radio to unlock this week's dossier.")
        
        c1, c2 = st.columns([3, 1])
        codeword_input = c1.text_input("AUTHENTICATION CODE", placeholder="e.g. ALPHA1", label_visibility="collapsed")
        
        if c2.button("🔴 VERIFY", use_container_width=True):
            if codeword_input.strip().upper() == ACTIVE_CODEWORD.upper():
                st.session_state.bounty_unlocked = True
                st.success("✅ CODEWORD ACCEPTED. DECRYPTING DOSSIER...")
                st.rerun()
            else:
                st.session_state.bounty_unlocked = False
                st.error("❌ AUTHENTICATION FAILED. INCORRECT CODEWORD.")
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.markdown("<h3 style='text-align: center; color: #39ff14;'>AUTHENTICATED. DOSSIER UNLOCKED.</h3>", unsafe_allow_html=True)
        st.markdown("---")
        
        # Show Image Dossier
        st.image(DOSSIER_URL, use_container_width=True)
        st.markdown("<br>", unsafe_allow_html=True)
        
        st.markdown("<div class='dossier-box'>", unsafe_allow_html=True)
        st.markdown("### 📥 SUBMIT BOUNTY INTERCEPT CLAIM")
        
        op = st.session_state.operator_profile
        op_lat = float(op.get('lat', 0.0))
        op_lon = float(op.get('lon', 0.0))
        
        st.markdown(f"**AGENT:** {op.get('name', 'UNKNOWN').upper()} | **QTH:** {op.get('city', '')}, {op.get('state', '')} ({op.get('country', '')})")
        st.markdown(f"<div style='color: #1bd2d4; font-size: 1.1rem; margin-top: 10px; margin-bottom: 20px;'><b>MISSION PARAMETERS:</b> {BOUNTY_DESC}</div>", unsafe_allow_html=True)
        st.markdown("---")

        with st.form("bounty_claim_form", clear_on_submit=True):
            st.markdown("#### 1. TARGET INFORMATION")
            c1, c2, c3 = st.columns(3)
            b_call = c1.text_input("TARGET CALLSIGN")
            b_freq = c2.text_input("TARGET FREQUENCY (e.g. 102.1 or 1120)")
            b_band = c3.selectbox("BAND", ["AM", "FM", "NWR"])
            
            c4, c5, c6 = st.columns(3)
            b_city = c4.text_input("TARGET CITY")
            b_state = c5.text_input("TARGET STATE/PROVINCE")
            
            # Auto-populate the country dropdown
            import modules.data_forge as df_forge
            country_options = sorted(list(set(df_forge.country_list + ["Canada", "Mexico", "United Kingdom", "Australia", "Other"])))
            b_country = c6.selectbox("TARGET COUNTRY", [""] + country_options)
            
            c7, c8 = st.columns(2)
            b_dist = c7.number_input("CALCULATED DISTANCE (MILES)", min_value=0.0, step=1.0)
            b_date = c8.date_input("RECEPTION DATE (UTC)")
            
            b_notes = st.text_area("INTERCEPT NOTES & EQUIPMENT USED")
            b_email = st.text_input("SECURE EMAIL UPLINK (REQUIRED FOR CONFIRMATION)")
            
            st.markdown("#### 2. UPLOAD AIRCHECK")
            st.caption("Audio proof is required. Please upload an MP3 file (Max length: 30 seconds).")
            st.markdown("<div style='border: 1px dashed #139a9b; padding: 10px; margin-top: 10px; margin-bottom: 10px; background-color: #050505;'>", unsafe_allow_html=True)
            b_audio = st.file_uploader("ATTACH MP3 FILE", type=["mp3", "wav", "m4a"], label_visibility="collapsed")
            st.markdown("</div>", unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            submit_claim = st.form_submit_button("🚀 TRANSMIT CLAIM TO HIGH COMMAND")
            
            if submit_claim:
                if not b_call or not b_country or b_dist == 0.0 or not b_email:
                    st.error("❌ INCOMPLETE DOSSIER. Callsign, Country, Distance, and Email are strictly required.")
                elif not b_audio:
                    st.error("❌ FAILED: AUDIO AIRCHECK REQUIRED TO CLAIM BOUNTY.")
                else:
                    # Run the active validation engine
                    is_valid, reason = verify_bounty_eligibility(b_call, b_country, b_dist)
                    
                    if not is_valid:
                        st.error(f"❌ CLAIM REJECTED: {reason}")
                    else:
                        with st.spinner("Encrypting transmission and uplifting audio to secure email server..."):
                            timestamp = str(datetime.datetime.now(datetime.timezone.utc))
                            filename = f"SODX_Bounty_{op.get('name')}_{b_call}.mp3"
                            
                            # Transmit via Email
                            email_success = transmit_bounty_email(op.get('name'), b_call, b_freq, b_band, b_city, b_country, b_dist, b_email, b_notes, b_audio, filename)
                            
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
                                            b_call,
                                            f"{b_freq} {b_band}",
                                            b_dist,
                                            b_email,
                                            f"{b_city}, {b_state}, {b_country}",
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
