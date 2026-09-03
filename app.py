import streamlit as st
import pandas as pd
import numpy as np

# Page Configuration
st.set_page_config(page_title="Collections Daily Report", layout="wide")

# Custom CSS for Exact Original Dashboard Styling
st.markdown("""
    <style>
    .main-container { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
    .top-header-bar { background-color: #0d1b2a; color: white; padding: 10px 20px; border-radius: 4px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; }
    .bucket-card { background-color: #ffffff; border: 1px solid #dcdcdc; border-radius: 4px; padding: 10px; margin-bottom: 10px; }
    .bucket-title { font-weight: bold; font-size: 14px; color: #1e3a8a; }
    .metric-red { color: #dc2626; font-weight: bold; }
    .metric-green { color: #16a34a; font-weight: bold; }
    .section-banner { background-color: #0f2b5c; color: white; padding: 8px 12px; font-weight: bold; font-size: 14px; border-radius: 4px 4px 0px 0px; display: flex; justify-content: space-between; }
    .stDataFrame { margin-top: -10px; }
    </style>
""", unsafe_allow_html=True)

# Navigation Sidebar
st.sidebar.title("⚡ Navigation")
page = st.sidebar.radio("Go to:", ["Daily Target", "Agent Performance"])

st.sidebar.markdown("---")
st.sidebar.header("📁 Data Source")
uploaded_file = st.sidebar.file_uploader("Upload Excel Sheet", type=["xlsx", "xls"])

@st.cache_data
def load_data(file):
    if file is not None:
        return pd.read_excel(file)
    return None

df = load_data(uploaded_file)

if df is not None:
    # Identify Fixed vs Date Columns
    fixed_cols = ['customer_id', 'loan_id', 'remaining_principal', 'status', 
                  'cycle_name', 'Officer', 'Type', 'Non-Starter', 
                  'Principal Type', "Call Or Don't Call", 'Risk', 'Update']
    
    date_cols = [col for col in df.columns if col not in fixed_cols]
    
    # Normalize Cycles
    df['cycle_clean'] = df['cycle_name'].astype(str).str.upper().str.strip()

    # Officer Filter
    all_officers = sorted(df['Officer'].dropna().unique().tolist())
    selected_officers = st.sidebar.multiselect("Filter Officers:", all_officers, default=all_officers)
    filtered_df = df[df['Officer'].isin(selected_officers)].copy()

    selected_date = st.sidebar.selectbox("Select Payment Date Column:", date_cols if date_cols else [None])

    # Convert payment column safely to numeric
    if selected_date and selected_date in filtered_df.columns:
        filtered_df['payment_val'] = pd.to_numeric(filtered_df[selected_date], errors='coerce').fillna(0)
    else:
        filtered_df['payment_val'] = 0

    # Helper function for conditional color text formatting
    def color_performance(val):
        if pd.isna(val):
            return ''
        if isinstance(val, (int, float)):
            if val > 20:
                return 'color: #16a34a; font-weight: bold;'
            elif val > 10:
                return 'color: #d97706; font-weight: bold;'
            else:
                return 'color: #dc2626; font-weight: bold;'
        return ''

    # PAGE 1: DAILY TARGET (Matching Screen 1)
    if page == "Daily Target":
        # Upper Summary Cards
        total_target = filtered_df['remaining_principal'].sum()
        total_in = filtered_df['payment_val'].sum()
        remaining = total_target - total_in
        pct_target = (total_in / total_target * 100) if total_target > 0 else 0

        # Global Top Metric Bar
        st.markdown(f"""
        <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 10px; border-radius: 6px; margin-bottom: 15px;">
            <span style="font-weight:bold; font-size:12px; color:#475569;">TOTAL DAILY TARGET: </span><span style="font-size:16px; font-weight:bold; color:#0f172a;">{total_target:,.0f}</span> | 
            <span style="font-weight:bold; font-size:12px; color:#475569;">TOTAL IN: </span><span style="font-size:16px; font-weight:bold; color:#16a34a;">{total_in:,.0f}</span> | 
            <span style="font-weight:bold; font-size:12px; color:#475569;">REMAINING: </span><span style="font-size:16px; font-weight:bold; color:#dc2626;">{remaining:,.0f}</span> | 
            <span style="font-weight:bold; font-size:12px; color:#475569;">% FROM TARGET: </span><span style="font-size:16px; font-weight:bold; color:#dc2626;">{pct_target:.2f}%</span>
        </div>
        """, unsafe_allow_html=True)

        col_left, col_right = st.columns(2)

        def render_daily_table(sub_df, title_label):
            st.markdown(f"<div class='section-banner'><span>{title_label}</span></div>", unsafe_allow_html=True)
            if sub_df.empty:
                st.info("No records found.")
                return

            tbl = sub_df.groupby('Officer').agg(
                TARGET_B=('remaining_principal', 'sum'),
                DAILY_IN=('payment_val', 'sum'),
                TOTAL_IN=('payment_val', 'sum'),
                PAID_CLIENTS=('payment_val', lambda x: (x > 0).sum())
            ).reset_index()

            tbl['REMAINING'] = tbl['TARGET_B'] - tbl['TOTAL_IN']
            tbl['% TARGET'] = np.where(tbl['TARGET_B'] > 0, (tbl['TOTAL_IN'] / tbl['TARGET_B']) * 100, 0)
            
            tbl = tbl.sort_values(by='% TARGET', ascending=False).reset_index(drop=True)
            tbl.index = tbl.index + 1
            tbl.index.name = '#'

            # Rename Columns to match exact screenshot
            tbl.rename(columns={
                'Officer': 'NAME',
                'TARGET_B': 'TARGET B',
                'DAILY_IN': 'DAILY IN',
                'TOTAL_IN': 'TOTAL IN',
                'PAID_CLIENTS': '# PAID',
                'REMAINING': 'REMAINING',
                '% TARGET': '% TARGET'
            }, inplace=True)

            styled_tbl = tbl.style.format({
                'TARGET B': '{:,.0f}',
                'DAILY IN': '{:,.0f}',
                'TOTAL IN': '{:,.0f}',
                '# PAID': '{:d}',
                'REMAINING': '{:,.0f}',
                '% TARGET': '{:.2f}%'
            }).applymap(color_performance, subset=['% TARGET'])

            st.dataframe(styled_tbl, height=(len(tbl) + 1) * 35 + 10, use_container_width=True)

        with col_left:
            c1_df = filtered_df[filtered_df['cycle_clean'].str.contains('1|CYCLE-1', na=False)]
            render_daily_table(c1_df, "C1 — BUCKET-1")

        with col_right:
            c2_df = filtered_df[filtered_df['cycle_clean'].str.contains('2|CYCLE-2|C16', na=False)]
            render_daily_table(c2_df, "C16 — BUCKET-1")

    # PAGE 2: AGENT PERFORMANCE (Matching Screen 2)
    elif page == "Agent Performance":
        col_p1, col_p2 = st.columns(2)

        def render_performance_table(sub_df, title_label):
            st.markdown(f"<div class='section-banner'><span>{title_label}</span></div>", unsafe_allow_html=True)
            if sub_df.empty:
                st.info("No records found.")
                return

            perf = sub_df.groupby('Officer').agg(
                Principal=('remaining_principal', 'sum'),
                Paid_Cases=('payment_val', lambda x: (x > 0).sum())
            ).reset_index()

            tot_p = perf['Principal'].sum()
            perf['PRINCIPAL %'] = (perf['Principal'] / tot_p * 100) if tot_p > 0 else 0
            perf = perf.sort_values(by='PRINCIPAL %', ascending=False).reset_index(drop=True)

            perf['RANK'] = perf.index + 1
            perf['DIFF %'] = perf['PRINCIPAL %'].diff().abs().fillna(0)
            perf['DIFF $'] = perf['Principal'].diff().abs().fillna(0)
            perf['FROM TARGET (95%)'] = perf['PRINCIPAL %'] * 0.95

            perf.rename(columns={'Officer': 'NAME', 'Paid_Cases': '# PAID'}, inplace=True)
            perf = perf[['NAME', 'PRINCIPAL %', 'RANK', 'DIFF %', 'DIFF $', 'FROM TARGET (95%)', '# PAID']]

            styled_perf = perf.style.format({
                'PRINCIPAL %': '{:.2f}%',
                'RANK': '{:d}',
                'DIFF %': '¬ {:.2f}%',
                'DIFF $': '¬ {:,.0f}',
                'FROM TARGET (95%)': '{:.2f}%',
                '# PAID': '{:d}'
            }).applymap(color_performance, subset=['PRINCIPAL %', 'FROM TARGET (95%)'])

            st.dataframe(styled_perf, height=(len(perf) + 1) * 35 + 10, use_container_width=True)

        with col_p1:
            c1_sub = filtered_df[filtered_df['cycle_clean'].str.contains('1|CYCLE-1', na=False)]
            render_performance_table(c1_sub, "Cycle-1 / BUCKET-1")

        with col_p2:
            c2_sub = filtered_df[filtered_df['cycle_clean'].str.contains('2|CYCLE-2|C16', na=False)]
            render_performance_table(c2_sub, "Cycle-2 / BUCKET-1")

else:
    st.info("💡 Please upload your Excel sheet in the sidebar to display the Dashboard.")
