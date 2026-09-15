import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="iScore Stats Tracker", layout="wide")
st.title("⚾ Caribe Performance Dashboard")

# NEW CODE (Multi-file upload)
uploaded_files = st.file_uploader("Upload iScore Game Log CSVs", type=["csv"], accept_multiple_files=True)

if uploaded_files:
    # Combines all uploaded CSVs into one master season table
    df = pd.concat([pd.read_csv(file) for file in uploaded_files], ignore_index=True)
    cols = df.columns.tolist()
    
    player_col_guess = next((c for c in cols if 'player' in c.lower() or 'name' in c.lower()), cols[0])
    date_col_guess = next((c for c in cols if 'date' in c.lower() or 'game' in c.lower()), cols[0])
    
    player_col = st.sidebar.selectbox("Player Name Column", cols, index=cols.index(player_col_guess))
    date_col = st.sidebar.selectbox("Date Column", cols, index=cols.index(date_col_guess))
    
    players = df[player_col].dropna().unique().tolist()
    selected_players = st.sidebar.multiselect("Select Player(s)", players, default=players[:1] if players else [])
    
    numeric_cols = df.select_dtypes(include=['float64', 'int64']).columns.tolist()
    selected_metrics = st.sidebar.multiselect("Select Stats", numeric_cols, default=numeric_cols[:2] if numeric_cols else [])
    
    if selected_players and selected_metrics:
        filtered_df = df[df[player_col].isin(selected_players)].copy()
        
        melted_df = filtered_df.melt(id_vars=[date_col, player_col], value_vars=selected_metrics, 
                                     var_name="Category", value_name="Stat Value")
                                     
        fig = px.line(melted_df, x=date_col, y="Stat Value", color=player_col, facet_row="Category",
                      markers=True, height=250 * len(selected_metrics))
        fig.update_yaxes(matches=None) 
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Select a player and category to display charts.")
