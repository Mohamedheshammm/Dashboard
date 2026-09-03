import streamlit as st
import pandas as pd
import numpy as np

# Page Configuration & Styling
st.set_page_config(page_title="Collections Dashboard", layout="wide")

st.markdown("""
    <style>
    /* Sidebar Styling */
    [data-testid="stSidebar"] {
        background-color: #0d1b2a;
    }
    [data-testid="stSidebar"] * {
        color: #ffffff !important;
    }
    
    /* Top Summary Bar */
    .top-summary-bar {
        background-color: #f8fafc;
        border: 1px solid #cbd5e1;
        padding: 8px 15px;
        border-radius: 4px;
        margin-bottom: 12px;
        font-size: 13px;
        font-family: sans-serif;
    }

    /* Blue Header Card */
    .header-blue-banner {
        background-color: #0f2b5c;
        color: white;
        padding: 8px 12px;
        border-radius: 4px 4px 0 0;
        font-weight: bold;
        font-size: 14px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    /* Table Compact Styling */
    .stDataFrame { margin-top: -5px; }
    </style>
""", unsafe_allow_html=True)

# ------------------- SIDEBAR NAVIGATION -------------------
st.sidebar.markdown("## 📊 DASHBOARDS")
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
st.sidebar.markdown("## 🛠️ TOOLS & DATA")
uploaded_main = st.sidebar.file_uploader("📂 Import Historical / Data", type=["xlsx", "xls"])
uploaded_update = st.sidebar.file_uploader("📤 Upload Update (Payments)", type=["xlsx", "xls"])

@st.cache_data
def load_excel(file):
    if file is not None:
        return pd.read_excel(file)
    return None

df = load_excel(uploaded_main)
update_df = load_excel(uploaded_update)

if df is not None:
    # Standardize Column Names and Identify Dynamic Date Columns
    fixed_cols = ['customer_id', 'loan_id', 'remaining_principal', 'status', 
                  'cycle_name', 'Officer', 'Type', 'Non-Starter', 
                  'Principal Type', "Call Or Don't Call", 'Risk', 'Update']
    
    date_cols = [col for col in df.columns if col not in fixed_cols]
    df['cycle_clean'] = df['cycle_name'].astype(str).str.upper().str.strip()

    # Officer Filter
    all_officers = sorted(df['Officer'].dropna().unique().tolist())
    selected_officers = st.sidebar.multiselect("Filter Officers:", all_officers, default=all_officers)
    filtered_df = df[df['Officer'].isin(selected_officers)].copy()

    selected_date = st.sidebar.selectbox("Select Date for Collections:", date_cols if date_cols else [None])

    # ------------------- ROBUST PAYMENT PROCESSING -------------------
    filtered_df['payment_val'] = 0.0

    if update_df is not None:
        # Find ID column in Update file (loan_id or customer_id)
        id_col_update = None
        for col in update_df.columns:
            col_str = str(col).lower().replace("_", "").replace(" ", "")
            if "loanid" in col_str or "loan" in col_str or "customerid" in col_str:
                id_col_update = col
                break

        # Find Numeric/Payment Amount column in Update file
        pay_col_update = None
        for col in update_df.columns:
            if col != id_col_update:
                converted = pd.to_numeric(update_df[col], errors='coerce')
                if converted.notna().sum() > 0 and converted.sum() > 0:
                    pay_col_update = col
                    break

        if id_col_update and pay_col_update:
            # Clean IDs for precise matching
            filtered_df['match_key'] = filtered_df['loan_id'].astype(str).str.strip().str.split('.').str[0]
            update_df['match_key'] = update_df[id_col_update].astype(str).str.strip().str.split('.').str[0]
            update_df['clean_amount'] = pd.to_numeric(update_df[pay_col_update], errors='coerce').fillna(0)

            # Map payments to main portfolio
            pay_map = update_df.groupby('match_key')['clean_amount'].sum().to_dict()
            filtered_df['payment_val'] = filtered_df['match_key'].map(pay_map).fillna(0.0)

    elif selected_date and selected_date in filtered_df.columns:
        filtered_df['payment_val'] = pd.to_numeric(filtered_df[selected_date], errors='coerce').fillna(0.0)

    # ------------------- HELPER DATA PROCESSOR -------------------
    def process_bucket_data(sub_df, target_val):
        if sub_df.empty:
            return pd.DataFrame(), 0, 0

        tot_in = sub_df['payment_val'].sum()
        pct_in = (tot_in / target_val * 100) if target_val > 0 else 0

        tbl = sub_df.groupby('Officer').agg(
            Principal=('remaining_principal', 'sum'),
            DAILY_IN=('payment_val', 'sum'),
            TOTAL_IN=('payment_val', 'sum'),
            PAID_COUNT=('payment_val', lambda x: (x > 0).sum())
        ).reset_index()

        tot_prin = tbl['Principal'].sum()
        tbl['TARGET B'] = (tbl['Principal'] / tot_prin * target_val) if tot_prin > 0 else 0
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

        return tbl[['NAME', 'TARGET B', 'DAILY IN', 'TOTAL IN', '# PAID', 'REMAINING', '% TARGET']], tot_in, pct_in

    # ------------------- PAGE: DAILY TARGET -------------------
    if page == "🎯 Daily Target":
        total_target_all = filtered_df['remaining_principal'].sum()
        total_in_all = filtered_df['payment_val'].sum()
        remaining_all = total_target_all - total_in_all
        pct_all = (total_in_all / total_target_all * 100) if total_target_all > 0 else 0

        st.markdown(f"""
        <div class="top-summary-bar">
            <b>TOTAL DAILY TARGET:</b> {total_target_all:,.0f} | 
            <b>TOTAL IN:</b> <span style="color:green; font-weight:bold;">{total_in_all:,.0f}</span> | 
            <b>REMAINING:</b> <span style="color:red; font-weight:bold;">{remaining_all:,.0f}</span> | 
            <b>% FROM TARGET:</b> <span style="color:red; font-weight:bold;">{pct_all:.2f}%</span>
        </div>
        """, unsafe_allow_html=True)

        col1, col2 = st.columns(2)

        with col1:
            t1 = st.number_input("Target for C1 — BUCKET-1 (EGP):", value=40000000.0, step=1000000.0)
            c1_df = filtered_df[filtered_df['cycle_clean'].str.contains('1|CYCLE-1', na=False)]
            tbl1, in1, pct1 = process_bucket_data(c1_df, t1)

            st.markdown(f"""
            <div class="header-blue-banner">
                <span>C1 — BUCKET-1 &nbsp;&nbsp; <small style='color:#facc15;'>Target: {t1:,.0f} - IN: {in1:,.0f} - {pct1:.2f}%</small></span>
            </div>
            """, unsafe_allow_html=True)

            if not tbl1.empty:
                st.dataframe(
                    tbl1.style.format({
                        'TARGET B': '{:,.0f}',
                        'DAILY IN': '{:,.0f}',
                        'TOTAL IN': '{:,.0f}',
                        '# PAID': '{:d}',
                        'REMAINING': '{:,.0f}',
                        '% TARGET': '{:.2f}%'
                    }),
                    height=(len(tbl1) + 1) * 35 + 10,
                    use_container_width=True
                )

        with col2:
            t2 = st.number_input("Target for C16 — BUCKET-1 (EGP):", value=10000000.0, step=1000000.0)
            c2_df = filtered_df[filtered_df['cycle_clean'].str.contains('2|CYCLE-2|C16', na=False)]
            tbl2, in2, pct2 = process_bucket_data(c2_df, t2)

            st.markdown(f"""
            <div class="header-blue-banner">
                <span>C16 — BUCKET-1 &nbsp;&nbsp; <small style='color:#facc15;'>Target: {t2:,.0f} - IN: {in2:,.0f} - {pct2:.2f}%</small></span>
            </div>
            """, unsafe_allow_html=True)

            if not tbl2.empty:
                st.dataframe(
                    tbl2.style.format({
                        'TARGET B': '{:,.0f}',
                        'DAILY IN': '{:,.0f}',
                        'TOTAL IN': '{:,.0f}',
                        '# PAID': '{:d}',
                        'REMAINING': '{:,.0f}',
                        '% TARGET': '{:.2f}%'
                    }),
                    height=(len(tbl2) + 1) * 35 + 10,
                    use_container_width=True
                )

    # ------------------- PAGE: AGENT PERFORMANCE -------------------
    elif page == "📊 Agent Performance":
        col1, col2 = st.columns(2)

        def render_agent_perf(sub_df, title):
            st.markdown(f"<div class='header-blue-banner'><span>{title}</span></div>", unsafe_allow_html=True)
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
            render_agent_perf(c1_sub, "Cycle-1 / BUCKET-1")

        with col2:
            c2_sub = filtered_df[filtered_df['cycle_clean'].str.contains('2|CYCLE-2|C16', na=False)]
            render_agent_perf(c2_sub, "Cycle-2 / BUCKET-1")

    else:
        st.info(f"Page **{page}** is ready.")

else:
    st.info("💡 Please upload your Main Portfolio Excel file in the sidebar to view the Dashboard.")
