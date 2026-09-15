import streamlit as st
import pandas as pd
import plotly.express as px
import re

st.set_page_config(page_title="iScore Stats Tracker", layout="wide")
st.title("⚾ Caribe Performance Dashboard")

# 1. EXTRACTOR FUNCTION (Defined inside app.py)
def process_iscore_file(file):
    # Read raw file with no headers to inspect top metadata rows
    if file.name.endswith(('.xls', '.xlsx')):
        raw_df = pd.read_excel(file, header=None)
    else:
        raw_df = pd.read_csv(file, header=None)
    
    date_val = "Unknown Date"
    opp_val = "Opponent"
    game_num = "Game 1"
    header_idx = None

    # Scan top 10 rows for metadata & locate real stat header row
    for idx, row in raw_df.iloc[:10].iterrows():
        row_str = " ".join(row.dropna().astype(str))
        
        # Extract Date
        date_match = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', row_str)
        if date_match and date_val == "Unknown Date":
            date_val = date_match.group(1)
            
        # Extract Opponent
        if " vs " in row_str.lower() or " at " in row_str.lower() or "opponent:" in row_str.lower():
            opp_val = row_str
            
        # Extract Game Number
        game_match = re.search(r'game\s*#?\s*(\d+)', row_str, re.IGNORECASE)
        if game_match:
            game_num = f"Game {game_match.group(1)}"

        # Find row where player stats table begins
        row_values_lower = row.dropna().astype(str).str.lower().tolist()
        if any(term in row_values_lower for term in ['player', 'name', 'batting']):
            header_idx = idx
            break

    # Re-read file starting at the detected stat table header
    file.seek(0)
    if file.name.endswith(('.xls', '.xlsx')):
        df = pd.read_excel(file, header=header_idx if header_idx is not None else 0)
    else:
        df = pd.read_csv(file, header=header_idx if header_idx is not None else 0)

    # Clean empty rows & team totals
    df = df.dropna(how='all')
    first_col = df.columns[0]
    df = df[~df[first_col].astype(str).str.upper().str.contains("TOTAL|TEAM", na=False)]

    # Attach extracted metadata columns
    df['Extracted_Date'] = date_val
    df['Extracted_Opponent'] = opp_val
    df['Extracted_Game'] = game_num
    df['Game_Label'] = f"{date_val} ({game_num}) vs {opp_val}"

    return df


# 2. DASHBOARD FRONTEND & FILE UPLOADER
uploaded_files = st.file_uploader(
    "Upload iScore Game Files (.csv, .xls, .xlsx)", 
    type=["csv", "xls", "xlsx"], 
    accept_multiple_files=True
)

if uploaded_files:
    # Process and merge all uploaded files using the function above
    all_dfs = [process_iscore_file(f) for f in uploaded_files]
    df = pd.concat(all_dfs, ignore_index=True)
    
    cols = df.columns.tolist()
    
    # Auto-detect player column
    player_col_guess = next((c for c in cols if 'player' in c.lower() or 'name' in c.lower()), cols[0])
    
    st.sidebar.header("Controls")
    player_col = st.sidebar.selectbox("Player Column", cols, index=cols.index(player_col_guess))
    
    # Select Players
    players = df[player_col].dropna().unique().tolist()
    selected_players = st.sidebar.multiselect("Select Player(s)", players, default=players[:1] if players else [])
    
    # Select Stat Categories
    numeric_cols = df.select_dtypes(include=['float64', 'int64']).columns.tolist()
    selected_metrics = st.sidebar.multiselect("Select Categories to Track", numeric_cols, default=numeric_cols[:2] if numeric_cols else [])
    
    if selected_players and selected_metrics:
        filtered_df = df[df[player_col].isin(selected_players)].copy()
        
        # Melt data for multi-stat charts
        melted_df = filtered_df.melt(
            id_vars=['Game_Label', player_col], 
            value_vars=selected_metrics, 
            var_name="Category", 
            value_name="Stat Value"
        )
        
        # Generate chart using extracted Game_Label (Date + Game# + Opponent)
        fig = px.line(
            melted_df, 
            x='Game_Label', 
            y="Stat Value", 
            color=player_col, 
            facet_row="Category",
            markers=True, 
            height=270 * len(selected_metrics)
        )
        
        fig.update_yaxes(matches=None)
        fig.update_xaxes(title_text="Game Details")
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Show data table
        st.subheader("📊 Match Log & Stats")
        st.dataframe(filtered_df[['Game_Label', player_col] + selected_metrics])
    else:
        st.info("Please select at least one player and one category.")
