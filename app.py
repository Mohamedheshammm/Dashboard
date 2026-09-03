import streamlit as st
import pandas as pd
import numpy as np

# Page Configuration
st.set_page_config(page_title="Collections Management Dashboard", layout="wide")

# Styling
st.markdown("""
    <style>
    .main-title { font-size: 26px; font-weight: bold; color: #1E3A8A; margin-bottom: 15px; }
    .kpi-card { background-color: #F8FAFC; padding: 15px; border-radius: 8px; border: 1px solid #E2E8F0; text-align: center; }
    </style>
""", unsafe_allow_html=True)

# Navigation
st.sidebar.title("📌 Navigation")
page = st.sidebar.radio("Select View:", ["🎯 Daily Target", "📊 Agent Performance"])

st.sidebar.markdown("---")
st.sidebar.header("📁 Data Source")
uploaded_file = st.sidebar.file_uploader("Upload Collections Excel File", type=["xlsx", "xls"])

@st.cache_data
def load_data(file):
    if file is not None:
        return pd.read_excel(file)
    return None

df = load_data(uploaded_file)

if df is not None:
    # Standardize column structure
    fixed_cols = ['customer_id', 'loan_id', 'remaining_principal', 'status', 
                  'cycle_name', 'Officer', 'Type', 'Non-Starter', 
                  'Principal Type', "Call Or Don't Call", 'Risk', 'Update']
    
    date_cols = [col for col in df.columns if col not in fixed_cols]
    df['cycle_clean'] = df['cycle_name'].astype(str).str.upper().str.strip()

    # Officer Filter Options
    all_officers = sorted(df['Officer'].dropna().unique().tolist())
    selected_officers = st.sidebar.multiselect("Filter Officers (Select to include):", all_officers, default=all_officers)
    
    # Filter dataset
    filtered_df = df[df['Officer'].isin(selected_officers)].copy()

    # Dynamic Daily Selection
    selected_date = st.sidebar.selectbox("Select Date Column for Payments", date_cols if date_cols else [None])

    # Color Styler Helper Function
    def apply_color_gradient(val, min_val, max_val):
        if pd.isna(val) or min_val == max_val:
            return ''
        normalized = (val - min_val) / (max_val - min_val)
        red = int((1 - normalized) * 220)
        green = int(normalized * 180)
        return f'color: rgb({red}, {green}, 50); font-weight: bold;'

    # PAGE 1: DAILY TARGET
    if page == "🎯 Daily Target":
        st.markdown("<div class='main-title'>🎯 Daily Target Distribution & Tracking</div>", unsafe_allow_html=True)

        # Global Daily Target Input
        daily_target_input = st.number_input("Enter Total Daily Target (EGP):", min_value=0.0, value=50000000.0, step=100000.0)

        # Overview Metrics
        total_principal = filtered_df['remaining_principal'].sum()
        total_collected = filtered_df[selected_date].apply(lambda x: pd.to_numeric(x, errors='coerce')).fillna(0).sum() if selected_date else 0
        paid_cases = filtered_df[filtered_df[selected_date] > 0]['loan_id'].nunique() if selected_date else 0

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("TOTAL TARGET", f"{total_principal:,.0f} EGP")
        m2.metric("DAILY TARGET SET", f"{daily_target_input:,.0f} EGP")
        m3.metric("TOTAL IN", f"{total_collected:,.0f} EGP")
        m4.metric("PAID CLIENTS (#)", f"{paid_cases:d}")
        m5.metric("% ACHIEVED", f"{(total_collected / daily_target_input * 100):.2f}%" if daily_target_input > 0 else "0.00%")

        st.markdown("---")

        c1_col, c2_col = st.columns(2)

        # Function to process Daily Target Tables
        def process_daily_target(data_subset, title):
            st.subheader(title)
            if data_subset.empty:
                st.info("No data available.")
                return

            summary = data_subset.groupby('Officer').agg(
                TARGET=('remaining_principal', 'sum'),
                PAID_CLIENTS=(selected_date, lambda x: (pd.to_numeric(x, errors='coerce').fillna(0) > 0).sum()) if selected_date else ('remaining_principal', 'count')
            ).reset_index()

            # Assign Equal Split of Daily Target proportional to remaining balance
            total_rem = summary['TARGET'].sum()
            summary['DAILY TARGET'] = (summary['TARGET'] / total_rem * daily_target_input) if total_rem > 0 else 0

            if selected_date:
                summary['DAILY IN'] = data_subset.groupby('Officer')[selected_date].apply(lambda x: pd.to_numeric(x, errors='coerce').fillna(0).sum()).values
            else:
                summary['DAILY IN'] = 0

            summary['REMAINING'] = summary['TARGET'] - summary['DAILY IN']
            summary['% TARGET'] = np.where(summary['DAILY TARGET'] > 0, (summary['DAILY IN'] / summary['DAILY TARGET']) * 100, 0)

            # Sort by Achievement Rate
            summary = summary.sort_values(by='% TARGET', ascending=False).reset_index(drop=True)

            min_p, max_p = summary['% TARGET'].min(), summary['% TARGET'].max()

            # Styled DataFrame Output (Full Height)
            styled = summary.style.format({
                "TARGET": "{:,.0f}",
                "DAILY TARGET": "{:,.0f}",
                "DAILY IN": "{:,.0f}",
                "REMAINING": "{:,.0f}",
                "% TARGET": "{:.2f}%",
                "PAID_CLIENTS": "{:d}"
            }).applymap(lambda v: apply_color_gradient(v, min_p, max_p), subset=['% TARGET'])

            st.dataframe(styled, height=(len(summary) + 1) * 35 + 10, use_container_width=True)

        with c1_col:
            c1_df = filtered_df[filtered_df['cycle_clean'].str.contains('1|CYCLE-1', na=False)]
            process_daily_target(c1_df, "🔵 C1 - BUCKET 1")

        with c2_col:
            c2_df = filtered_df[filtered_df['cycle_clean'].str.contains('2|CYCLE-2', na=False)]
            process_daily_target(c2_df, "🟣 C2 - BUCKET 1")

    # PAGE 2: AGENT PERFORMANCE
    elif page == "📊 Agent Performance":
        st.markdown("<div class='main-title'>📊 Agents Collection Performance & Ranking</div>", unsafe_allow_html=True)

        p1_col, p2_col = st.columns(2)

        def process_performance(data_subset, title):
            st.subheader(title)
            if data_subset.empty:
                st.info("No data available.")
                return

            perf = data_subset.groupby('Officer').agg(
                Principal=('remaining_principal', 'sum'),
                Paid_Cases=(selected_date, lambda x: (pd.to_numeric(x, errors='coerce').fillna(0) > 0).sum()) if selected_date else ('remaining_principal', 'count')
            ).reset_index()

            total_p = perf['Principal'].sum()
            perf['PRINCIPAL %'] = (perf['Principal'] / total_p) * 100 if total_p > 0 else 0
            perf = perf.sort_values(by='PRINCIPAL %', ascending=False).reset_index(drop=True)

            perf['RANK'] = perf.index + 1
            perf['DIFF %'] = perf['PRINCIPAL %'].diff().abs().fillna(0)
            perf['DIFF $'] = perf['Principal'].diff().abs().fillna(0)
            perf['FROM TARGET (95%)'] = perf['PRINCIPAL %'] * 0.95

            # Formatting Column Names
            perf.rename(columns={'Officer': 'NAME', 'Paid_Cases': 'PAID CLIENTS'}, inplace=True)
            perf = perf[['NAME', 'PRINCIPAL %', 'RANK', 'DIFF %', 'DIFF $', 'FROM TARGET (95%)', 'PAID CLIENTS']]

            min_p, max_p = perf['PRINCIPAL %'].min(), perf['PRINCIPAL %'].max()

            styled = perf.style.format({
                "PRINCIPAL %": "{:.2f}%",
                "RANK": "{:d}",
                "DIFF %": "¬ {:.2f}%",
                "DIFF $": "¬ {:,.0f}",
                "FROM TARGET (95%)": "{:.2f}%",
                "PAID CLIENTS": "{:d}"
            }).applymap(lambda v: apply_color_gradient(v, min_p, max_p), subset=['PRINCIPAL %', 'FROM TARGET (95%)'])

            st.dataframe(styled, height=(len(perf) + 1) * 35 + 10, use_container_width=True)

        with p1_col:
            c1_p = filtered_df[filtered_df['cycle_clean'].str.contains('1|CYCLE-1', na=False)]
            process_performance(c1_p, "Cycle-1 / BUCKET-1 Performance")

        with p2_col:
            c2_p = filtered_df[filtered_df['cycle_clean'].str.contains('2|CYCLE-2', na=False)]
            process_performance(c2_p, "Cycle-2 / BUCKET-1 Performance")

else:
    st.info("💡 Please upload the collections Excel file from the sidebar to activate the dashboard.")
