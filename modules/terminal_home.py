import streamlit as st

def render_terminal_home(awards_active=True, bounty_active=True):
    st.markdown('<div class="typewriter">GREETINGS, FELLOW SIGNAL TRAVELER.<br>WOULD YOU LIKE TO PLAY A GAME?<span class="blink">_</span></div>', unsafe_allow_html=True)
    
    if "gcp_service_account" not in st.secrets:
        st.error("🚨 [ SYSTEM ALERT ] DATALINK OFFLINE. Streamlit Secrets not configured. Logs cannot be submitted to the Google Sheet.")
    if not awards_active:
        st.warning("⚠️ AWARDS MODULE OFFLINE. Ensure 'modules/awards.py' is deployed to activate Century Club notifications.")
    if not bounty_active:
        st.warning("⚠️ BOUNTY MODULE OFFLINE. Ensure 'modules/bounty.py' is deployed.")
        
    st.write("Use the **[ SYSTEM COMMAND MENU ]** in the sidebar to navigate the mainframe.")
    
    st.markdown("---")
    
    st.markdown("### 📡 COMMUNIQUE FROM HIGH COMMAND")
    st.info("**ATTENTION ALL AGENTS:** Due to feedback from field operatives, we have re-calibrated the multiplier logic. Moving forward, individual States and Provinces within the **United States, Canada, and Mexico** will each independently count as a multiplier. For all other international intercepts, agents will receive a single multiplier for the **Country** as a whole.")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    col_news, col_contact = st.columns([2, 1])
    
    with col_news:
        st.markdown("### 💾 DECRYPTED PATCH NOTES (CHANGELOG)")
        st.markdown("""
        <div class='classified-box' style='height: 350px; overflow-y: auto;'>
            <b style='color:#1bd2d4;'>[ 2026-05-02 | v1.0.2 ] GEOSPATIAL & UI OPTIMIZATION:</b> County and Gridsquare tactical maps upgraded with enhanced luminance scaling and density rendering for absolute precision. Intelligence Ledgers reconfigured to eliminate data truncation.<br><br>
            <b style='color:#1bd2d4;'>[ 2026-05-02 | v1.0.1 ] SCORING MATRIX RECALIBRATED:</b> Fixed the scoring matrix so that the only multipliers are US States, Canadian Provinces, and Mexican States, alongside a single multiplier per international country.<br><br>
            <b style='color:#1bd2d4;'>[ 2026-05-01 | v1.0.0 ] SYSTEM ONLINE:</b> Official launch of Operation SUMMER OF DX (DEFCON 6). All tracking databanks and tactical radars initialized.
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
