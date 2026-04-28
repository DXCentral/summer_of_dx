import streamlit as st
import pandas as pd
import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from modules.data_forge import get_gsheet

def check_thresholds(db_df, dxer_name, new_grid, new_county, band):
    """
    Evaluates the DXer's current Grid/County counts against the master DB + their new submission.
    Returns an award dictionary if a new threshold is reached.
    """
    if db_df.empty: return None
    
    user_logs = db_df[db_df['DXer'] == dxer_name]
    
    # Calculate Grids
    grids = set(user_logs['Station_Grid'].replace(['', ' - ', 'Unknown'], pd.NA).dropna().str[:4].str.upper().tolist())
    if new_grid and len(new_grid) >= 4:
        grids.add(new_grid[:4].upper())
    grid_count = len(grids)

    # Calculate Counties
    counties = set(user_logs['County'].replace(['', ' - ', 'Unknown'], pd.NA).dropna().tolist())
    if new_county and new_county not in ['', ' - ', 'Unknown']:
        counties.add(new_county)
    county_count = len(counties)

    # Dynamic Band Thresholds
    if band == "NWR":
        base_target = 20
        step = 10
    else:
        base_target = 100
        step = 50

    try:
        # Pull the existing claims to ensure we don't spam the user
        main_sheet = get_gsheet()
        award_sheet = main_sheet.spreadsheet.worksheet("Award_Claims")
        claims = award_sheet.get_all_records()
        
        claimed_grid_levels = [int(row['Level']) for row in claims if str(row['DXer']).upper() == dxer_name.upper() and row['Band'] == band and row['Category'] == 'Grids']
        claimed_county_levels = [int(row['Level']) for row in claims if str(row['DXer']).upper() == dxer_name.upper() and row['Band'] == band and row['Category'] == 'Counties']
        
        # Check Grid Thresholds (Reverse order to catch bulk upload jumps)
        grid_levels = [x for x in range(base_target, grid_count + 1, step)]
        for lvl in reversed(grid_levels):
            if lvl not in claimed_grid_levels:
                return {"band": band, "category": "Grids", "level": lvl}
                
        # Check County Thresholds
        county_levels = [x for x in range(base_target, county_count + 1, step)]
        for lvl in reversed(county_levels):
            if lvl not in claimed_county_levels:
                return {"band": band, "category": "Counties", "level": lvl}
                
    except Exception as e:
        print(f"Award Check Failed (Ensure 'Award_Claims' tab exists): {e}")
        pass
        
    return None

def send_award_emails(user_email, dxer_name, band, category, level):
    admin_email = "w4lvhsc@gmail.com"
    try:
        smtp_server = st.secrets["smtp"]["server"]
        smtp_port = st.secrets["smtp"]["port"]
        smtp_user = st.secrets["smtp"]["email"]
        smtp_pass = st.secrets["smtp"]["password"]

        # 1. Email to User
        msg_user = MIMEMultipart()
        msg_user['From'] = f"DX Central High Command <{smtp_user}>"
        msg_user['To'] = user_email
        msg_user['Subject'] = f"CLASSIFIED: {band} {category} Level {level} Clearance Verified"
        
        body_user = f"""AGENT {dxer_name.upper()},

High Command has verified your telemetry. You have successfully achieved {level} confirmed targets in the {band} {category} division.

Your commendation certificate is currently being processed by DX Central Intelligence and will be transmitted to this frequency shortly.

Secure the spectrum,
High Command
summerofdx.com
"""
        msg_user.attach(MIMEText(body_user, 'plain'))

        # 2. Email to Admin
        msg_admin = MIMEMultipart()
        msg_admin['From'] = f"Mainframe Alert <{smtp_user}>"
        msg_admin['To'] = admin_email
        msg_admin['Subject'] = f"AWARD TRIGGERED: {dxer_name} - {band} {category} ({level})"
        
        body_admin = f"""Admin Alert:

DXer: {dxer_name}
Award: {band} {category}
Level: {level}
User Email: {user_email}
Timestamp: {datetime.datetime.now(datetime.timezone.utc)} UTC

Please generate and send the certificate.
"""
        msg_admin.attach(MIMEText(body_admin, 'plain'))

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_pass)
        
        if user_email and user_email != "ON_FILE":
            server.send_message(msg_user)
        server.send_message(msg_admin)
        server.quit()
        return True
    except Exception as e:
        print(f"SMTP Error: {e}")
        return False

@st.dialog("LEVEL 4 CLEARANCE UNLOCKED")
def award_popup():
    award = st.session_state.pending_award
    band = award['band']
    category = award['category'] 
    level = award['level']
    dxer = st.session_state.operator_profile.get("name")

    st.markdown(f"<h3 style='color:#1bd2d4; text-align:center;'>OPERATION ALERT: {band} {category.upper()} MILESTONE REACHED</h3>", unsafe_allow_html=True)
    
    is_base_level = (band in ["AM", "FM"] and level == 100) or (band == "NWR" and level == 20)
    
    if is_base_level:
        award_name = "Century Club" if level == 100 else "NWR Master"
        st.markdown(f"**AGENT {dxer.upper()}, HIGH COMMAND ACKNOWLEDGES YOUR EXCEPTIONAL SIGNAL INTERCEPT CAPABILITIES.**")
        st.markdown(f"You have successfully logged **{level} {category}**, unlocking prestigious **{award_name}** status.")
        st.markdown("Enter your secure routing email below to receive your official commendation certificate.")
        email_input = st.text_input("SECURE EMAIL UPLINK")
    else:
        st.markdown(f"**AGENT {dxer.upper()}, YOUR CONTINUED SURVEILLANCE HAS NOT GONE UNNOTICED.**")
        st.markdown(f"You have reached the **Level {level} Endorsement** for {band} {category}.")
        st.markdown("High Command has been notified of your achievement. If your routing email has changed, enter it below. Otherwise, submit to confirm.")
        email_input = st.text_input("SECURE EMAIL UPLINK (OPTIONAL)", placeholder="Leave blank to use previous email")

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔴 TRANSMIT TO HIGH COMMAND", use_container_width=True):
        if is_base_level and not email_input:
            st.error("EMAIL UPLINK REQUIRED FOR INITIAL CERTIFICATE.")
        else:
            final_email = email_input if email_input else "ON_FILE"
            # Transmit Emails
            send_award_emails(final_email, dxer, band, category, level)
            
            # Log to Sheet to prevent duplicate popups
            main_sheet = get_gsheet()
            if main_sheet:
                award_sheet = main_sheet.spreadsheet.worksheet("Award_Claims")
                award_sheet.append_row([str(datetime.datetime.now(datetime.timezone.utc)), dxer, band, category, level, final_email])
            
            st.session_state.pending_award = None
            st.rerun()
