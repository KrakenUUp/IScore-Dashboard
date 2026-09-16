import streamlit as st
import pandas as pd
import plotly.express as px
import re
import os
import glob

st.set_page_config(page_title="Caribe Stats Tracker", layout="wide")
st.title("⚾ Caribe Performance Dashboard")

TARGET_TEAM = "Caribe"

def parse_caribe_role(text_string):
    """
    Determines if Caribe was Visitor or Home based on text like 'Caribe at Red Sox' or 'Tigers vs Caribe'
    """
    text = text_string.lower()
    
    # Check "at" / "@" notation (Standard: Visitor at Home)
    if " at " in text or " @ " in text:
        parts = re.split(r'\s+(?:at|@)\s+', text)
        if len(parts) >= 2:
            if TARGET_TEAM.lower() in parts[0]:
                return "Visitor", parts[1].title()
            elif TARGET_TEAM.lower() in parts[1]:
                return "Home", parts[0].title()

    # Check "vs" notation (Standard: Home vs Visitor)
    if " vs " in text or " vs. " in text:
        parts = re.split(r'\s+vs\.?\s+', text)
        if len(parts) >= 2:
            if TARGET_TEAM.lower() in parts[0]:
                return "Home", parts[1].title()
            elif TARGET_TEAM.lower() in parts[1]:
                return "Visitor", parts[0].title()

    # Default fallback
    return "Visitor", "Opponent"


def parse_iscore_date(date_str):
    """
    Robustly parses iScore date formats, specifically handling 6-digit MMDDYY (e.g. '051224')
    and standard date strings to return a true datetime object for correct chronological sorting.
    """
    if not date_str:
        return pd.Timestamp(0)
    
    cleaned = re.sub(r'[^0-9]', '', str(date_str))
    
    # Handle iScore MMDDYY format (6 digits)
    if len(cleaned) == 6:
        mm = int(cleaned[0:2])
        dd = int(cleaned[2:4])
        yy = int(cleaned[4:6])
        full_year = yy + 2000
        try:
            return pd.Timestamp(year=full_year, month=mm, day=dd)
        except ValueError:
            pass
            
    # Handle MMDDYYYY format (8 digits)
    elif len(cleaned) == 8:
        mm = int(cleaned[0:2])
        dd = int(cleaned[2:4])
        yyyy = int(cleaned[4:8])
        try:
            return pd.Timestamp(year=yyyy, month=mm, day=dd)
        except ValueError:
            pass

    # Fallback to standard pandas datetime parser
    try:
        dt = pd.to_datetime(date_str)
        return dt if not pd.isna(dt) else pd.Timestamp(0)
    except Exception:
        return pd.Timestamp(0)


def normalize_player_name(name):
    """
    Normalizes player names to group variations together (e.g. 'John', 'John Smith', 'John #10')
    by extracting the primary first name or base identifier.
    """
    if not isinstance(name, str):
        return "Unknown"
    
    cleaned = name.strip()
    if not cleaned:
        return "Unknown"
        
    # Remove jersey numbers like '#10' or '(10)'
    cleaned = re.sub(r'#\d+|\(\d+\)', '', cleaned).strip()
    
    return cleaned


def resolve_unified_player_name(df, player_col):
    """
    Creates a standardized canonical player name column to merge name variations 
    across games (e.g., 'John' in early games and 'John Smith' in later games).
    """
    raw_names = df[player_col].dropna().unique().tolist()
    
    mapping = {}
    for name in raw_names:
        norm = normalize_player_name(name)
        matched_canonical = None
        for canonical in mapping.values():
            if norm.lower().startswith(canonical.lower()) or canonical.lower().startswith(norm.lower()):
                if len(norm) >= len(canonical):
                    matched_canonical = norm
                else:
                    matched_canonical = canonical
                break
        
        if not matched_canonical:
            mapping[name] = norm
        else:
            mapping[name] = matched_canonical
            
    return df[player_col].map(mapping).fillna(df[player_col])


def process_caribe_file(file_obj, filename_hint):
    dfs_from_this_file = []

    try:
        if filename_hint.endswith(('.xls', '.xlsx')):
            excel_file = pd.ExcelFile(file_obj)
            sheet_names = excel_file.sheet_names
        else:
            sheet_names = [None]

        # First pass: determine Caribe's role from headers
        if hasattr(file_obj, 'seek'):
            file_obj.seek(0)
        raw_sample = pd.read_excel(file_obj, sheet_name=0, header=None) if sheet_names[0] else pd.read_csv(file_obj, header=None)
        
        header_text = " ".join(raw_sample.iloc[:5].fillna('').astype(str).values.flatten())
        game_title = filename_hint if "caribe" not in header_text.lower() else header_text
        
        caribe_role, opponent_name = parse_caribe_role(game_title)
        
        # Extract date
        date_match = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', header_text)
        if not date_match:
            six_digit_match = re.search(r'\b(\d{6})\b', header_text)
            if six_digit_match:
                raw_d = six_digit_match.group(1)
                date_val = f"{raw_d[0:2]}/{raw_d[2:4]}/{raw_d[4:6]}"
            else:
                date_val = "Unknown Date"
        else:
            date_val = date_match.group(1)
            
        parsed_dt = parse_iscore_date(date_val)
        game_label = f"{date_val} vs {opponent_name} ({caribe_role})"

        for sheet in sheet_names:
            if sheet:
                if caribe_role == "Visitor" and not sheet.lower().startswith("visitor"):
                    continue
                if caribe_role == "Home" and not sheet.lower().startswith("home"):
                    continue

            if hasattr(file_obj, 'seek'):
                file_obj.seek(0)
            df = pd.read_excel(file_obj, sheet_name=sheet, header=None) if sheet else pd.read_csv(file_obj, header=None)
            
            header_idx = None
            for idx, row in df.iloc[:10].iterrows():
                row_vals = row.dropna().astype(str).str.lower().tolist()
                if any(term in row_vals for term in ['player', 'name', 'batting', 'pitching', 'tot', 'total']):
                    header_idx = idx
                    break

            if hasattr(file_obj, 'seek'):
                file_obj.seek(0)
            df = pd.read_excel(file_obj, sheet_name=sheet, header=header_idx if header_idx is not None else 0) if sheet else pd.read_csv(file_obj, sheet_name=header_idx if header_idx is not None else 0)
            
            df = df.dropna(how='all')
            if not df.empty:
                df['Caribe_Role'] = caribe_role
                df['Opponent'] = opponent_name
                df['Game_Date'] = date_val
                df['__Parsed_Date'] = parsed_dt
                df['Game_Label'] = game_label
                df['Stat_Category'] = sheet if sheet else "Stats"
                
                dfs_from_this_file.append(df)
    except Exception as e:
        st.sidebar.warning(f"Could not parse {filename_hint}: {e}")

    if dfs_from_this_file:
        return pd.concat(dfs_from_this_file, ignore_index=True)
    return pd.DataFrame()


all_dfs = []

# 1. Automatically check local 'data' folder for files committed to GitHub
data_dir = "data"
if os.path.exists(data_dir) and os.path.isdir(data_dir):
    data_files = glob.glob(os.path.join(data_dir, "*.xls*")) + glob.glob(os.path.join(data_dir, "*.csv"))
    for f_path in data_files:
        res_df = process_caribe_file(f_path, os.path.basename(f_path))
        if not res_df.empty:
            all_dfs.append(res_df)

# 2. Allow manual file uploads as backup or supplement
uploaded_files = st.sidebar.file_uploader("Upload iScore Game Files (Optional)", type=["csv", "xls", "xlsx"], accept_multiple_files=True)
if uploaded_files:
    for file in uploaded_files:
        res_df = process_caribe_file(file, file.name)
        if not res_df.empty:
            all_dfs.append(res_df)


if all_dfs:
    df = pd.concat(all_dfs, ignore_index=True)
    
    # CRITICAL SORT FIX: Sort entire dataframe chronologically by true parsed datetime timestamp
    if '__Parsed_Date' in df.columns:
        df = df.sort_values(by=['__Parsed_Date', 'Game_Label'])
    
    cols = [c for c in df.columns if not c.startswith('__')]
    player_col_guess = next((c for c in cols if 'player' in c.lower() or 'name' in c.lower()), cols[0])
    
    st.sidebar.header("Controls")
    player_col = st.sidebar.selectbox("Player / Row Column", cols, index=cols.index(player_col_guess) if player_col_guess in cols else 0)
    
    # Apply player name unification to merge name variations
    canonical_player_col = player_col + "_Canonical"
    df[canonical_player_col] = resolve_unified_player_name(df, player_col)
    
    view_mode = st.sidebar.radio("View Mode", ["Individual Players", "Team Totals Row"])
    
    if view_mode == "Team Totals Row":
        filtered_df = df[df[player_col].astype(str).str.upper().str.contains("TOTAL|TOTALS", na=False)]
        active_player_col = player_col
    else:
        filtered_df = df[~df[player_col].astype(str).str.upper().str.contains("TOTAL|TOTALS", na=False)]
        active_player_col = canonical_player_col
        
        players = filtered_df[active_player_col].dropna().unique().tolist()
        selected_players = st.sidebar.multiselect("Select Player(s)", players, default=players[:3] if players else [])
        filtered_df = filtered_df[filtered_df[active_player_col].isin(selected_players)]

    numeric_cols = filtered_df.select_dtypes(include=['float64', 'int64']).columns.tolist()
    selected_metrics = st.sidebar.multiselect("Select Metrics", numeric_cols, default=numeric_cols[:2] if numeric_cols else [])

    if not filtered_df.empty and selected_metrics:
        melted_df = filtered_df.melt(
            id_vars=['Game_Label', active_player_col], 
            value_vars=selected_metrics, 
            var_name="Category", 
            value_name="Stat Value"
        )
        
        game_order = filtered_df['Game_Label'].unique().tolist()
        
        fig = px.line(
            melted_df, 
            x='Game_Label', 
            y="Stat Value", 
            color=active_player_col, 
            facet_row="Category",
            markers=True, 
            height=270 * len(selected_metrics),
            category_orders={'Game_Label': game_order}
        )
        
        fig.update_traces(
            mode="lines+markers",
            connectgaps=True,
            showlegend=True
        )
        
        fig.update_traces(
            hovertemplate="<b>%{fullData.name}</b><br>Game: %{x}<br>Value: %{y}<extra></extra>"
        )
        
        fig.update_yaxes(matches=None)
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(filtered_df[['Game_Label', active_player_col] + selected_metrics])
    else:
        st.info("Please select at least one player and metric from the sidebar.")
else:
    st.info("👋 Welcome! No files found. Please either upload files using the sidebar uploader or commit your `.xls`, `.xlsx`, or `.csv` files inside a folder named `data/` in your GitHub repository.")
