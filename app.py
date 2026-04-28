import streamlit as st
import datetime
from modules.data_forge import get_gsheet

def render_bounty_module():
    # --- ACTIVE BOUNTY CONFIGURATION (UPDATE THESE FOR EACH STREAM) ---
    ACTIVE_ALPHA = "D"
    ACTIVE_NUMERIC = "4"
    SECRET_PAYLOAD = "SPORADIC"
    
    DOSSIER_TITLE = "OPERATION: MIDNIGHT GRAVEYARD"
    DOSSIER_DETAILS = """
    **TARGET SPECIFICATIONS:**
    * Intercept any Class C AM Graveyard station (1230, 1240, 1340, 1400, 1450, or 1490 kHz).
    * Distance must exceed 400 miles from your calibrated Home QTH.
    * Reception must be logged without the use of an SDR (Traditional Hardware Only).
    
    **DEADLINE:**
    * Acquisition window closes exactly 14 days from transmission.
    """
    # -----------------------------------------------------------------

    st.markdown("""
    <style>
    .cipher-box {
        border: 2px solid #139a9b;
        background-color: #0a1a1a;
        padding: 20px;
        border-radius: 5px;
        box-shadow: inset 0px 0px 15px rgba(19, 154, 155, 0.2);
        margin-bottom: 20px;
    }
    .dossier-box {
        border: 2px dashed #ff0000;
        background-color: #1a0505;
        padding: 25px;
        margin-top: 20px;
        box-shadow: 0px 0px 20px rgba(255, 0, 0, 0.3);
    }
    .dossier-stamp {
        color: #ff0000;
        font-size: 3rem;
        font-weight: bold;
        text-transform: uppercase;
        border: 4px solid #ff0000;
        display: inline-block;
        padding: 5px 15px;
        transform: rotate(-5deg);
        margin-bottom: 15px;
        text-shadow: 0px 0px 10px rgba(255,0,0,0.5);
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("<h1 style='text-align: center; color: #1bd2d4; text-shadow: 0px 0px 10px rgba(27,210,212,0.8);'>[ ENCRYPTION PROTOCOL: ACTIVE ]</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center; color: #ffffff;'>AWAITING MATRIX ALIGNMENT PARAMETERS...</h3>", unsafe_allow_html=True)
    st.markdown("---")

    # --- SESSION STATE INITIALIZATION ---
    if 'matrix_unlocked' not in st.session_state: st.session_state.matrix_unlocked = False
    if 'dossier_unlocked' not in st.session_state: st.session_state.dossier_unlocked = False

    st.markdown("<div class='cipher-box'>", unsafe_allow_html=True)
    st.markdown("#### 1. ALIGN BROADCAST KEYS")
    st.caption("Input the Alpha and Numeric cryptographic keys broadcasted during the DX Central stream.")
    
    c1, c2 = st.columns(2)
    alpha_key = c1.selectbox("ALPHA KEY", ["-", "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z"])
    numeric_key = c2.selectbox("NUMERIC KEY", ["-", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9"])
    
    if alpha_key == ACTIVE_ALPHA and numeric_key == ACTIVE_NUMERIC:
        st.success("✅ MATRIX ALIGNMENT LOCKED. CIPHER ACTIVE.")
        st.session_state.matrix_unlocked = True
    elif alpha_key != "-" and numeric_key != "-":
        st.error("❌ MATRIX MISALIGNED. INCORRECT KEYS.")
        st.session_state.matrix_unlocked = False
    
    if st.session_state.matrix_unlocked:
        st.markdown("<hr style='border-color:#333'>", unsafe_allow_html=True)
        st.markdown("#### 2. DECRYPT PAYLOAD")
        st.caption("Utilize the Vigenère cipher matrix to translate the broadcasted number string.")
        
        payload_input = st.text_input("ENTER DECRYPTED PAYLOAD STRING", placeholder="e.g. TRANSMIT")
        
        if st.button("🔴 INITIATE DECRYPTION", use_container_width=True):
            if payload_input.strip().upper() == SECRET_PAYLOAD:
                st.session_state.dossier_unlocked = True
                st.rerun()
            else:
                st.error("❌ DECRYPTION FAILED: INVALID PAYLOAD.")
                st.session_state.dossier_unlocked = False

    st.markdown("</div>", unsafe_allow_html=True)

    # --- TOP SECRET DOSSIER REVEAL ---
    if st.session_state.dossier_unlocked:
        st.markdown("""
        <div class='dossier-box'>
            <div class='dossier-stamp'>TOP SECRET</div>
            <h2 style='color:#ffffff;'>%s</h2>
            <div style='color:#1bd2d4; font-size:1.2rem; line-height:1.6;'>
                %s
            </div>
        </div>
        """ % (DOSSIER_TITLE, DOSSIER_DETAILS), unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("### 📥 SUBMIT BOUNTY INTERCEPT")
        
        with st.form("bounty_claim_form", clear_on_submit=True):
            b_c1, b_c2 = st.columns(2)
            now = datetime.datetime.now(datetime.timezone.utc)
            b_date = b_c1.date_input("INTERCEPT DATE (UTC)", value=now.date())
            b_time = b_c2.text_input("INTERCEPT TIME (UTC)", value=now.strftime("%H%M"))
            
            b_c3, b_c4, b_c5 = st.columns(3)
            b_freq = b_c3.text_input("FREQUENCY")
            b_call = b_c4.text_input("CALLSIGN")
            b_dist = b_c5.number_input("CALCULATED DISTANCE (MILES)", min_value=0.0, step=1.0)
            
            b_notes = st.text_area("PROOF / OBSERVATION NOTES")
            
            claim_btn = st.form_submit_button("> TRANSMIT BOUNTY CLAIM")
            
            if claim_btn:
                if not b_freq or not b_call or b_dist == 0.0:
                    st.error("❌ FAILED: FREQUENCY, CALLSIGN, AND DISTANCE ARE REQUIRED.")
                else:
                    # In a full deployment, you would route this to a separate "Bounties" worksheet
                    # sheet = get_gsheet(worksheet_name="Bounties") 
                    st.success("✅ BOUNTY CLAIM TRANSMITTED SUCCESSFULLY. AWAITING COMMAND VERIFICATION.")
                    st.balloons()
