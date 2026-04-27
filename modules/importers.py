import pandas as pd
import re
import csv
import io
import math
import unicodedata

def clean_callsign(call):
    if not call or pd.isna(call): 
        return ""
    call = str(call).strip().upper()
    call = re.sub(r'\s+R:.*$', '', call)
    call = call.replace('-FM', '')
    call = re.sub(r'\s+FM\b', '', call)
    return call.strip('- ')

def simplify_string(s):
    if not s or pd.isna(s): 
        return ""
    s = str(s).upper()
    s = unicodedata.normalize('NFD', s).encode('ascii', 'ignore').decode('utf-8')
    s = s.replace(' DX', '')
    return re.sub(r'[^A-Z0-9]', '', s)

def super_clean(s):
    if not s or pd.isna(s): 
        return ""
    s = str(s).upper()
    s = unicodedata.normalize('NFD', s).encode('ascii', 'ignore').decode('utf-8')
    s = re.sub(r'[^A-Z0-9]', '', s)
    if s.endswith('FM'): 
        s = s[:-2]
    return s

def standardize_cuban_station(call, freq, country):
    if str(country).strip() != "Cuba" or not call or pd.isna(call): 
        return call
    
    call_lower = str(call).lower()
    
    try: 
        freq_str = str(int(float(str(freq).replace(',', '.'))))
    except Exception: 
        freq_str = str(freq).strip()
        
    cuban_networks = {
        r'reloj': 'Radio Reloj', 
        r'rebelde': 'Radio Rebelde', 
        r'progres[s]*o': 'Radio Progreso',
        r'enc[iy]clopedia': 'Radio Enciclopedia', 
        r'music[al]*\s*nacional|cmbf': 'Radio Musical Nacional',
        r'ciudad\s*de\s*h[ab|av]ana': 'Radio Ciudad de Habana', 
        r'guam[aá]': 'Radio Guamá',
        r'mart[ií]': 'Radio Martí', 
        r'victori[a]': 'Radio Victoria', 
        r'cadena\s*agramonte': 'Radio Cadena Agramonte'
    }
    
    std_name = None
    for pattern, true_name in cuban_networks.items():
        if re.search(pattern, call_lower):
            std_name = true_name
            break
            
    if not std_name:
        std_name = re.sub(r'^r\.\s*', 'Radio ', str(call), flags=re.IGNORECASE)
        if re.match(r'^CM[A-Z]{2}$', std_name.upper()): 
            std_name = std_name.upper()
        else: 
            std_name = std_name.title()
            
    if freq_str and f"({freq_str})" not in std_name: 
        return f"{std_name} ({freq_str})"
    
    return std_name

def format_date_import(date_str):
    try:
        date_str = str(date_str).strip()
        if not date_str or date_str == "<Skip>": 
            return ""
        
        if "-" in date_str and len(date_str.split("-")[0]) == 4: 
            d = pd.to_datetime(date_str)
        else: 
            d = pd.to_datetime(date_str, dayfirst=True)
            
        return d.strftime("%m/%d/%Y")
    except Exception: 
        return date_str

def format_time_import(time_str):
    try:
        time_str = str(time_str).strip()
        if not time_str or time_str == "<Skip>": 
            return ""
            
        if re.match(r'^\d{3,4}$', time_str): 
            return time_str.zfill(4)
            
        d = pd.to_datetime(time_str)
        return d.strftime("%H%M")
    except Exception: 
        return time_str

def map_mw_prop(prop_raw):
    if not prop_raw or pd.isna(prop_raw): 
        return "Other"
    p = str(prop_raw).lower()
    if "day" in p or "ground" in p: 
        return "Groundwave - Daytime"
    if "night" in p or "sky" in p or "dx" in p: 
        return "Skywave - Nighttime"
    if "sunset" in p or "dusk" in p: 
        return "Grayline - Sunset"
    if "sunrise" in p or "dawn" in p: 
        return "Grayline - Sunrise"
    return "Other"

def map_fm_prop(prop_raw):
    if not prop_raw or pd.isna(prop_raw): 
        return "Other"
    p = str(prop_raw).upper()
    if "ES" in p or "SPORADIC" in p: 
        return "Sporadic E"
    if "TR" in p or "TROPO" in p: 
        return "Tropo"
    if "MS" in p or "METEOR" in p: 
        return "Meteor Scatter"
    if "AU" in p or "AURORA" in p: 
        return "Aurora"
    if "LOS" in p or "LOCAL" in p: 
        return "Local"
    return "Other"

def calculate_distance(lat1, lon1, lat2, lon2):
    if pd.isna(lat1) or pd.isna(lon1) or pd.isna(lat2) or pd.isna(lon2): 
        return 0.0
    try:
        lat1 = float(lat1)
        lon1 = float(lon1)
        lat2 = float(lat2)
        lon2 = float(lon2)
        
        if (lat1 == 0.0 and lon1 == 0.0) or (lat2 == 0.0 and lon2 == 0.0): 
            return 0.0
            
        R = 3958.8 
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
        return round(2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a)), 1)
    except Exception: 
        return 0.0

def get_idx(guess_list, cols):
    for g in guess_list:
        for idx, c in enumerate(cols):
            if str(g).lower() in str(c).lower(): 
                return idx
    return 0

def find_col(df, possible_names):
    for n in possible_names:
        for col in df.columns:
            if str(n).lower() == str(col).lower().strip(): 
                return col
    for n in possible_names:
        for col in df.columns:
            if str(n).lower() in str(col).lower(): 
                return col
    return None

def handle_mw_file_upload(uploaded_file):
    content = ""
    for enc in ['utf-8', 'latin-1', 'cp1252']:
        try:
            uploaded_file.seek(0)
            content = uploaded_file.read().decode(enc)
            break
        except Exception: 
            continue
            
    if not content: 
        raise ValueError("Unable to decode file. Encoding failure.")
        
    lines = content.splitlines()
    best_row = 0
    best_sep = ","
    
    keywords = ['khz', 'freq', 'mhz', 'program', 'station', 'itu', 'propa', 'date', 'utc', 'call', 'qrb', 'sinpo', 'remarks', 'details']
    
    for i, line in enumerate(lines[:50]):
        line_lower = line.lower()
        if sum(1 for kw in keywords if kw in line_lower) >= 3 and len(line) < 300:
            best_row = i
            c_comma = line.count(",")
            c_semi = line.count(";")
            c_tab = line.count("\t")
            max_d = max(c_comma, c_semi, c_tab)
            if max_d == c_semi: 
                best_sep = ";"
            elif max_d == c_tab: 
                best_sep = "\t"
            else: 
                best_sep = ","
            break
            
    if best_row == 0:
        max_delims = 0
        for i, line in enumerate(lines[:50]):
            c_comma = line.count(",")
            c_semi = line.count(";")
            c_tab = line.count("\t")
            current_max = max(c_comma, c_semi, c_tab)
            if current_max > max_delims and len(line) < 300:
                max_delims = current_max
                best_row = i
                if c_semi == current_max: 
                    best_sep = ";"
                elif c_tab == current_max: 
                    best_sep = "\t"
                else: 
                    best_sep = ","

    header_line_raw = next(csv.reader([lines[best_row]], delimiter=best_sep))
    header_line = [h.strip(' \'"') for h in header_line_raw]
    num_cols = len(header_line)
    parsed_data = []
    
    for line in lines[best_row+1:]:
        if not line.strip(): 
            continue
        
        cols = next(csv.reader([line], delimiter=best_sep))
        
        if len(cols) > num_cols:
            merged_last = best_sep.join(cols[num_cols-1:])
            cols = cols[:num_cols-1] + [merged_last]
        elif len(cols) < num_cols:
            cols.extend([""] * (num_cols - len(cols)))
            
        cols = [c.strip(' \'"') for c in cols]
        parsed_data.append(cols)
        
    unique_headers = []
    for j, h in enumerate(header_line):
        h_str = str(h) if h else f"Unnamed_{j}"
        if h_str in unique_headers: 
            h_str = f"{h_str}_{j}"
        unique_headers.append(h_str)
        
    return pd.DataFrame(parsed_data, columns=unique_headers)

def handle_fm_file_upload(uploaded_file):
    content = ""
    for enc in ['utf-8', 'latin-1', 'cp1252']:
        try:
            uploaded_file.seek(0)
            content = uploaded_file.read().decode(enc)
            break
        except Exception: 
            continue
            
    if not content: 
        raise ValueError("Unable to decode file. Encoding failure.")
        
    lines = content.splitlines()
    best_row = 0
    best_sep = ","
    
    keywords = [
        'khz', 'freq', 'mhz', 'program', 'station', 'itu', 'propa', 'date', 'utc', 'call', 
        'qrb', 'sinpo', 'remarks', 'details', 'timestamp', 'city', 'state', 'distance', 
        'mode', 'comments'
    ]
    
    for i, line in enumerate(lines[:50]):
        line_lower = line.lower()
        if sum(1 for kw in keywords if kw in line_lower) >= 3 and len(line) < 300:
            best_row = i
            c_comma = line.count(",")
            c_semi = line.count(";")
            c_tab = line.count("\t")
            max_d = max(c_comma, c_semi, c_tab)
            if max_d == c_semi: 
                best_sep = ";"
            elif max_d == c_tab: 
                best_sep = "\t"
            else: 
                best_sep = ","
            break
            
    try:
        df = pd.read_csv(io.StringIO(content), sep=best_sep, skiprows=best_row, engine='python', on_bad_lines='skip')
    except Exception:
        df = pd.read_csv(io.StringIO(content), sep=best_sep, skiprows=best_row, on_bad_lines='skip')
        
    df.columns = [str(c).strip(' \'"') for c in df.columns]
    
    if 'Location' in df.columns:
        df = df.drop(columns=['Location'])
    if 'Signature' in df.columns:
        df = df.drop(columns=['Signature'])
        
    return df
