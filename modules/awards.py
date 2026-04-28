import streamlit as st
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_manual_claim_email(user_email, dxer_name, band, category):
    admin_email = "w4lvhsc@gmail.com"
    try:
        smtp_server = st.secrets["smtp"]["server"]
        smtp_port = st.secrets["smtp"]["port"]
        smtp_user = st.secrets["smtp"]["email"]
        smtp_pass = st.secrets["smtp"]["password"]

        # Email strictly to Admin/High Command
        msg_admin = MIMEMultipart()
        msg_admin['From'] = f"Mainframe Alert <{smtp_user}>"
        msg_admin['To'] = admin_email
        msg_admin['Subject'] = f"AWARD CLAIM: {dxer_name} - {band} {category}"
        
        body_admin = f"""Admin Alert: Commendation Request Submitted

DXer: {dxer_name}
Band: {band}
Category: {category}
User Email: {user_email}

Please review the databanks for their current {category.lower()} count and issue the appropriate Century Club or Endorsement certificate.
"""
        msg_admin.attach(MIMEText(body_admin, 'plain'))

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg_admin)
        server.quit()
        return True
    except Exception as e:
        print(f"SMTP Error: {e}")
        return False

@st.dialog("COMMENDATION REQUEST: CENTURY CLUB")
def manual_award_claim_popup(category):
    st.markdown(f"<h3 style='color:#1bd2d4; text-align:center;'>REQUEST {category.upper()} CERTIFICATION</h3>", unsafe_allow_html=True)
    st.markdown("Do you qualify for a Century Club award or a new Endorsement tier? Fill out the form below to transmit your request to High Command.")
    
    with st.form("award_claim_form"):
        # Auto-pulls their name from the session state if available
        op_name = st.session_state.get('operator_profile', {}).get('name', '')
        
        dxer_name = st.text_input("AGENT IDENTITY (CALLSIGN/HANDLE)", value=op_name)
        user_email = st.text_input("SECURE EMAIL UPLINK (REQUIRED)")
        band = st.selectbox("TARGET BAND", ["MW", "FM", "NWR"])
        
        st.markdown("<br>", unsafe_allow_html=True)
        submitted = st.form_submit_button("🔴 TRANSMIT REQUEST TO HIGH COMMAND", use_container_width=True)
        
        if submitted:
            if not dxer_name or not user_email:
                st.error("AGENT IDENTITY AND EMAIL UPLINK ARE REQUIRED.")
            else:
                with st.spinner("Encrypting transmission..."):
                    success = send_manual_claim_email(user_email, dxer_name, band, category)
                    if success:
                        st.success("✅ TRANSMISSION SUCCESSFUL. HIGH COMMAND HAS BEEN NOTIFIED.")
                    else:
                        st.error("❌ DATALINK FAILED. Check SMTP Configuration in Streamlit Secrets.")
