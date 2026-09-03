import streamlit as st
import pandas as pd
import numpy as np

# Page Config
st.set_page_config(page_title="Collections Dashboard", layout="wide")

# Custom Styling for original UI matching
st.markdown("""
    <style>
    /* Dark Sidebar Menu styling */
    [data-testid="stSidebar"] {
        background-color: #0b132b;
        color: white;
    }
    [data-testid="stSidebar"] * {
        color: white !important;
    }
    .main-header {
        background-color: #1e293b;
        color: white;
        padding: 10px 15px;
        border-radius: 4px;
        font-weight: bold;
        margin-bottom: 15px;
    }
    .kpi-row {
        background-color: #f8fafc;
        border: 1px solid #cbd5e1;
        padding: 8px 12px;
        border-radius: 4px;
        margin-bottom: 12px;
        font-size: 13px;
    }
    .card-header-blue {
        background-color: #1e3a8a;
        color: white;
        padding: 6px 12px;
        font-weight: bold;
        font-size: 13px;
        border-radius: 4px 4px 0 0;
    }
    .stDataFrame { margin-top: -8px; }
    </style>
""", unsafe_allow_html=True)

# Sidebar - Complete Navigation menu matching screenshot
st.sidebar.markdown("### 📊 DASHBOARDS")
page = st.sidebar.radio("", [
    "👥 Team Performance",
    "📈 Portfolio Analysis",
    "🎯 Daily Target",
    "🔄 Daily Movement",
    "📜 Balance History",
    "📸 EOD Snapshot",
    "🛣️ Officer Journey",
    "📊 Agent Performance"
])

st.sidebar.markdown("---")
st.sidebar.markdown("### 🛠️ TOOLS & DATA")
uploaded_file = st.sidebar.file_uploader("📂 Import Historical / Data", type=["xlsx", "xls"])

@st.cache_data
def load_data(file):
    if file is not None:
        return pd.read_excel(file)
    return None

df = load_data(uploaded_file)

if df is not None:
    # Column classifications
    fixed_cols = ['customer_id', 'loan_id', 'remaining_principal', 'status', 
                  'cycle_name', 'Officer', 'Type', 'Non-Starter', 
                  'Principal Type', "Call Or Don't Call", 'Risk', 'Update']
    
    date_cols = [col for col in df.columns if col not in fixed_cols]
    df['cycle_clean'] = df['cycle_name'].astype(str).str.upper().str.strip()

    # Officer Multi-select filter
    all_officers = sorted(df['Officer'].dropna().unique().tolist())
    selected_officers = st.sidebar.multiselect("Filter Officers:", all_officers, default=all_officers)
    filtered_df = df[df['Officer'].isin(selected_officers)].copy()

    selected_date = st.sidebar.selectbox("Select Date for Collections:", date_cols if date_cols else [None])

    # Payment Column calculation
    if selected_date and selected_date in filtered_df.columns:
        filtered_df['payment_val'] = pd.to_numeric(filtered_df[selected_date], errors='coerce').fillna(0)
    else:
        filtered_df['payment_val'] = 0

    # Page 1: Daily Target
    if page == "🎯 Daily Target":
        total_target = filtered_df['remaining_principal'].sum()
        total_in = filtered_df['payment_val'].sum()
        remaining = total_target - total_in
        pct_target = (total_in / total_target * 100) if total_target > 0 else 0

        st.markdown(f"""
        <div class="kpi-row">
            <b>TOTAL DAILY TARGET:</b> {total_target:,.0f} | 
            <b>TOTAL IN:</b> <span style="color:green;">{total_in:,.0f}</span> | 
            <b>REMAINING:</b> <span style="color:red;">{remaining:,.0f}</span> | 
            <b>% FROM TARGET:</b> <span style="color:red;">{pct_target:.2f}%</span>
        </div>
        """, unsafe_allow_html=True)

        col1, col2 = st.columns(2)

        def build_daily_table(sub_data, title):
            st.markdown(f"<div class='card-header-blue'>{title}</div>", unsafe_allow_html=True)
            if sub_data.empty:
                st.info("No Data Available")
                return

            tbl = sub_data.groupby('Officer').agg(
                TARGET_B=('remaining_principal', 'sum'),
                DAILY_IN=('payment_val', 'sum'),
                TOTAL_IN=('payment_val', 'sum'),
                PAID_COUNT=('payment_val', lambda x: (x > 0).sum())
            ).reset_index()

            tbl['REMAINING'] = tbl['TARGET_B'] - tbl['TOTAL_IN']
            tbl['% TARGET'] = np.where(tbl['TARGET_B'] > 0, (tbl['TOTAL_IN'] / tbl['TARGET_B']) * 100, 0)
            
            tbl = tbl.sort_values(by='% TARGET', ascending=False).reset_index(drop=True)
            tbl.index = tbl.index + 1
            tbl.index.name = '#'

            tbl.rename(columns={
                'Officer': 'NAME',
                'TARGET_B': 'TARGET B',
                'DAILY_IN': 'DAILY IN',
                'TOTAL_IN': 'TOTAL IN',
                'PAID_COUNT': '# PAID',
                'REMAINING': 'REMAINING',
                '% TARGET': '% TARGET'
            }, inplace=True)

            st.dataframe(
                tbl.style.format({
                    'TARGET B': '{:,.0f}',
                    'DAILY IN': '{:,.0f}',
                    'TOTAL IN': '{:,.0f}',
                    '# PAID': '{:d}',
                    'REMAINING': '{:,.0f}',
                    '% TARGET': '{:.2f}%'
                }),
                height=(len(tbl) + 1) * 35 + 10,
                use_container_width=True
            )

        with col1:
            c1_df = filtered_df[filtered_df['cycle_clean'].str.contains('1|CYCLE-1', na=False)]
            build_daily_table(c1_df, "C1 — BUCKET-1")

        with col2:
            c2_df = filtered_df[filtered_df['cycle_clean'].str.contains('2|CYCLE-2|C16', na=False)]
            build_daily_table(c2_df, "C16 — BUCKET-1")

    # Page 2: Agent Performance
    elif page == "📊 Agent Performance":
        col1, col2 = st.columns(2)

        def build_performance_table(sub_data, title):
            st.markdown(f"<div class='card-header-blue'>{title}</div>", unsafe_allow_html=True)
            if sub_data.empty:
                st.info("No Data Available")
                return

            perf = sub_data.groupby('Officer').agg(
                Principal=('remaining_principal', 'sum'),
                Paid_Cases=('payment_val', lambda x: (x > 0).sum())
            ).reset_index()

            total_p = perf['Principal'].sum()
            perf['PRINCIPAL %'] = (perf['Principal'] / total_p * 100) if total_p > 0 else 0
            perf = perf.sort_values(by='PRINCIPAL %', ascending=False).reset_index(drop=True)

            perf['RANK'] = perf.index + 1
            perf['DIFF %'] = perf['PRINCIPAL %'].diff().abs().fillna(0)
            perf['DIFF $'] = perf['Principal'].diff().abs().fillna(0)
            perf['FROM TARGET (95%)'] = perf['PRINCIPAL %'] * 0.95

            perf.rename(columns={'Officer': 'NAME', 'Paid_Cases': '# PAID'}, inplace=True)
            perf = perf[['NAME', 'PRINCIPAL %', 'RANK', 'DIFF %', 'DIFF $', 'FROM TARGET (95%)', '# PAID']]

            st.dataframe(
                perf.style.format({
                    'PRINCIPAL %': '{:.2f}%',
                    'RANK': '{:d}',
                    'DIFF %': '¬ {:.2f}%',
                    'DIFF $': '¬ {:,.0f}',
                    'FROM TARGET (95%)': '{:.2f}%',
                    '# PAID': '{:d}'
                }),
                height=(len(perf) + 1) * 35 + 10,
                use_container_width=True
            )

        with col1:
            c1_p = filtered_df[filtered_df['cycle_clean'].str.contains('1|CYCLE-1', na=False)]
            build_performance_table(c1_p, "Cycle-1 / BUCKET-1")

        with col2:
            c2_p = filtered_df[filtered_df['cycle_clean'].str.contains('2|CYCLE-2|C16', na=False)]
            build_performance_table(c2_p, "Cycle-2 / BUCKET-1")

    else:
        st.info(f"Page **{page}** is ready for customization.")

else:
    st.info("💡 Please upload an Excel file from the sidebar to display the Dashboard.")
