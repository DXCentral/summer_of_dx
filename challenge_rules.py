import datetime
import pandas as pd

# =========================================================================
# 🎯 DEFCON 6: TEMPORAL PARAMETERS (THE FORM LOCKER)
# *** PRE-FLIGHT TESTING OVERRIDE ACTIVE ***
# All times are handled strictly in UTC to prevent local timezone drift.
# =========================================================================

# 1. THE SUBMISSION WINDOW (When the Terminal accepts data entries)
# OVERRIDE ACTIVE: Temporarily set to April 30 to allow immediate UI access.
# CHANGE THIS BACK TO (2026, 5, 1, 23, 0) BEFORE LAUNCH!
TERMINAL_OPEN = datetime.datetime(2026, 4, 30, 0, 0, tzinfo=datetime.timezone.utc)
TERMINAL_CLOSE = datetime.datetime(2026, 9, 30, 23, 59, 59, tzinfo=datetime.timezone.utc)

# 2. THE RECEPTION WINDOW (When the actual radio catch must have occurred)
# OVERRIDE ACTIVE: Temporarily set to April 30 so your test entries don't fail validation.
# CHANGE THIS BACK TO (2026, 5, 2, 1, 0) BEFORE LAUNCH!
RECEPTION_START = datetime.datetime(2026, 4, 30, 0, 0, tzinfo=datetime.timezone.utc)
RECEPTION_END = datetime.datetime(2026, 8, 31, 23, 59, 59, tzinfo=datetime.timezone.utc)

def is_terminal_open():
    """
    Validates if the current live UTC time is within the active Submission Window.
    Used to lock down the UI forms entirely.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    return TERMINAL_OPEN <= now <= TERMINAL_CLOSE

def is_reception_valid(date_str, time_str):
    """
    Evaluates a manual/quick entry date and time against the Reception Window.
    Expects standard YYYY-MM-DD and HH:MM or HH:MM:SS strings.
    """
    try:
        # Combine strings and convert to a UTC-aware datetime object
        dt_str = f"{date_str} {time_str}"
        reception_dt = pd.to_datetime(dt_str, utc=True)
        return RECEPTION_START <= reception_dt <= RECEPTION_END
    except Exception as e:
        print(f"Temporal Parsing Error: {e}")
        return False # Fail secure

def filter_bulk_dataframe(df, date_col='Date', time_col='Time'):
    """
    Scans a Bulk Import DataFrame and purges any rows outside the Reception Window.
    Returns the sanitized DataFrame and the integer count of purged rows.
    """
    try:
        # Convert the dataframe columns to a temporary UTC datetime series
        combined_dt = pd.to_datetime(df[date_col].astype(str) + ' ' + df[time_col].astype(str), utc=True, errors='coerce')
        
        # Create a boolean mask: True if within window, False if outside
        mask = (combined_dt >= RECEPTION_START) & (combined_dt <= RECEPTION_END)
        
        # Calculate how many rows failed the check
        purged_count = (~mask).sum()
        
        # Apply mask to return only the valid rows
        sanitized_df = df[mask].copy()
        
        return sanitized_df, purged_count
    except Exception as e:
        print(f"Bulk Temporal Filter Error: {e}")
        # If it fails, return an empty DF to prevent illegal data ingestion
        return pd.DataFrame(), len(df)
