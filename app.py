import streamlit as st
import pandas as pd
import numpy as np

# Page Configuration
st.set_page_config(page_title="Collections Daily Report", layout="wide")

# Custom CSS for Original Dashboard Design
st.markdown("""
    <style>
    [data-testid="stSidebar"] {
        background-color: #0d1b2a;
        color: white;
    }
    [data-testid="stSidebar"] * {
        color: white !important;
    }
    .kpi-row {
        background-color: #f8fafc;
        border: 1px solid #cbd5e1;
        padding: 8px 12px;
        border-radius: 4px;
        margin-bottom: 12px;
        font-size: 13px;
    }
    .bucket-card {
        background-color: #ffffff;
        border: 1px solid #cbd5e1;
        border-radius: 6px;
        padding: 12px;
        margin-bottom: 10px;
    }
    .bucket-header {
        font-size: 12px;
        font-weight: bold;
        color: #1e3a8a;
        margin-bottom: 5px;
    }
    .card-header-blue {
        background-color: #0f2b5c;
        color: white;
        padding: 6px 12px;
        font-weight: bold;
        font-size: 13px;
        border-radius: 4px 4px 0 0;
    }
    .stDataFrame { margin-top: -8px; }
    </style>
""", unsafe_allow_html=True)

# Sidebar Menu
st.sidebar.markdown("### 📊 DASHBOARDS")
page = st.sidebar.radio("", [
    "🎯 Daily Target",
    "📊 Agent Performance"
])

st.sidebar.markdown("---")
st.sidebar.markdown("### 🛠️ TOOLS & DATA")
uploaded_main = st.sidebar.file_uploader("📂 Import Main Portfolio", type=["xlsx", "xls"])
uploaded_update = st.sidebar.file_uploader("📤 Upload Update (Payments)", type=["xlsx", "xls"])

@st.cache_data
def load_data(file):
    if file is not None:
        return pd.read_excel(file)
    return None

df = load_data(uploaded_main)
update_df = load_data(uploaded_update)

if df is not None:
    fixed_cols = ['customer_id', 'loan_id', 'remaining_principal', 'status', 
                  'cycle_name', 'Officer', 'Type', 'Non-Starter', 
                  'Principal Type', "Call Or Don't Call", 'Risk', 'Update']
    
    date_cols = [col for col in df.columns if col not in fixed_cols]
    df['cycle_clean'] = df['cycle_name'].astype(str).str.upper().str.strip()

    # Filter Officers
    all_officers = sorted(df['Officer'].dropna().unique().tolist())
    selected_officers = st.sidebar.multiselect("Filter Officers:", all_officers, default=all_officers)
    filtered_df = df[df['Officer'].isin(selected_officers)].copy()

    selected_date = st.sidebar.selectbox("Select Payment Date Column:", date_cols if date_cols else [None])

    # Calculate Payments from Upload Update or Selected Date Column
    if update_df is not None and 'loan_id' in update_df.columns and 'paid_amount' in update_df.columns:
        paid_map = update_df.groupby('loan_id')['paid_amount'].sum().to_dict()
        filtered_df['payment_val'] = filtered_df['loan_id'].map(paid_map).fillna(0)
    elif selected_date and selected_date in filtered_df.columns:
        filtered_df['payment_val'] = pd.to_numeric(filtered_df[selected_date], errors='coerce').fillna(0)
    else:
        filtered_df['payment_val'] = 0

    # PAGE 1: DAILY TARGET
    if page == "🎯 Daily Target":
        total_target = filtered_df['remaining_principal'].sum()
        total_in = filtered_df['payment_val'].sum()
        remaining = total_target - total_in
        pct_target = (total_in / total_target * 100) if total_target > 0 else 0

        # Global Top Bar
        st.markdown(f"""
        <div class="kpi-row">
            <b>TOTAL DAILY TARGET:</b> {total_target:,.0f} | 
            <b>TOTAL IN:</b> <span style="color:green;">{total_in:,.0f}</span> | 
            <b>REMAINING:</b> <span style="color:red;">{remaining:,.0f}</span> | 
            <b>% FROM TARGET:</b> <span style="color:red;">{pct_target:.2f}%</span>
        </div>
        """, unsafe_allow_html=True)

        col1, col2 = st.columns(2)

        def render_daily_bucket(sub_df, title_label, default_target_val):
            # Upper Bucket Card
            b_in = sub_df['payment_val'].sum()
            
            c_input, _ = st.columns([1, 1])
            with c_input:
                bucket_target = st.number_input(f"Target for {title_label} (EGP):", min_value=0.0, value=float(default_target_val), step=1000000.0)
            
            b_pct = (b_in / bucket_target * 100) if bucket_target > 0 else 0

            st.markdown(f"""
            <div class="bucket-card">
                <div class="bucket-header">{title_label}</div>
                <div style="font-size: 16px; font-weight: bold; color: #1e3a8a;">{bucket_target:,.2f}</div>
                <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 8px;">
                    <div>
                        <span style="font-size: 10px; color: #64748b;">IN TODAY</span><br>
                        <span style="font-size: 18px; font-weight: bold; color: #16a34a;">{b_in:,.0f}</span>
                    </div>
                    <div style="text-align: right;">
                        <span style="font-size: 10px; color: #64748b;">% TARGET</span><br>
                        <span style="font-size: 18px; font-weight: bold; color: #dc2626;">{b_pct:.2f}%</span>
                    </div>
                </div>
                <progress value="{min(b_pct, 100)}" max="100" style="width: 100%; height: 6px; margin-top: 5px;"></progress>
            </div>
            """, unsafe_allow_html=True)

            # Table Header & Data
            st.markdown(f"<div class='card-header-blue'>{title_label}</div>", unsafe_allow_html=True)
            if sub_df.empty:
                st.info("No records found.")
                return

            tbl = sub_df.groupby('Officer').agg(
                Principal=('remaining_principal', 'sum'),
                DAILY_IN=('payment_val', 'sum'),
                TOTAL_IN=('payment_val', 'sum'),
                PAID_COUNT=('payment_val', lambda x: (x > 0).sum())
            ).reset_index()

            tot_rem = tbl['Principal'].sum()
            tbl['TARGET B'] = (tbl['Principal'] / tot_rem * bucket_target) if tot_rem > 0 else 0
            tbl['REMAINING'] = tbl['TARGET B'] - tbl['TOTAL_IN']
            tbl['% TARGET'] = np.where(tbl['TARGET B'] > 0, (tbl['TOTAL_IN'] / tbl['TARGET B']) * 100, 0)

            tbl = tbl.sort_values(by='% TARGET', ascending=False).reset_index(drop=True)
            tbl.index = tbl.index + 1
            tbl.index.name = '#'

            tbl.rename(columns={
                'Officer': 'NAME',
                'DAILY_IN': 'DAILY IN',
                'TOTAL_IN': 'TOTAL IN',
                'PAID_COUNT': '# PAID'
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
            render_daily_bucket(c1_df, "C1 — BUCKET-1", 40000000.0)

        with col2:
            c2_df = filtered_df[filtered_df['cycle_clean'].str.contains('2|CYCLE-2|C16', na=False)]
            render_daily_bucket(c2_df, "C16 — BUCKET-1", 10000000.0)

    # PAGE 2: AGENT PERFORMANCE
    elif page == "📊 Agent Performance":
        col1, col2 = st.columns(2)

        def render_performance_table(sub_df, title_label):
            st.markdown(f"<div class='card-header-blue'>{title_label}</div>", unsafe_allow_html=True)
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
            c1_sub = filtered_df[filtered_df['cycle_clean'].str.contains('1|CYCLE-1', na=False)]
            render_performance_table(c1_sub, "Cycle-1 / BUCKET-1")

        with col2:
            c2_sub = filtered_df[filtered_df['cycle_clean'].str.contains('2|CYCLE-2|C16', na=False)]
            render_performance_table(c2_sub, "Cycle-2 / BUCKET-1")

else:
    st.info("💡 Please upload your Main Portfolio Excel sheet from the sidebar to activate the Dashboard.")
