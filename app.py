import streamlit as st
import pandas as pd
import numpy as np
import re

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
        try:
            return pd.read_excel(file)
        except Exception:
            return None
    return None

df = load_excel(uploaded_main)
update_df = load_excel(uploaded_update)

if df is not None:
    # Clean Column Names
    df.columns = df.columns.astype(str).str.strip()
    
    # Identify Main ID / Name Column
    main_id_col = None
    for c in df.columns:
        c_clean = c.lower().replace("_", "").replace(" ", "")
        if any(k in c_clean for k in ["loan", "id", "customer", "contract"]):
            main_id_col = c
            break
    if not main_id_col:
        main_id_col = df.columns[0]

    # Officer Column Identification
    officer_col = [c for c in df.columns if any(k in c.lower() for k in ['officer', 'agent', 'name', 'collector'])]
    off_col_name = officer_col[0] if officer_col else df.columns[1]

    # Cycle Identification
    cycle_col = [c for c in df.columns if 'cycle' in c.lower()]
    df['cycle_clean'] = df[cycle_col[0]].astype(str).str.upper().str.strip() if cycle_col else ""

    fixed_cols = [main_id_col, off_col_name, 'remaining_principal', 'status', 'cycle_name', 'cycle_clean']
    date_cols = [col for col in df.columns if col not in fixed_cols]

    # Officer Filter
    all_officers = sorted(df[off_col_name].dropna().unique().tolist())
    selected_officers = st.sidebar.multiselect("Filter Officers:", all_officers, default=all_officers)
    filtered_df = df[df[off_col_name].isin(selected_officers)].copy()

    selected_date = st.sidebar.selectbox("Select Date for Collections:", date_cols if date_cols else [None])

    # ------------------- POWERFUL PAYMENT MATCHING ENGINE -------------------
    filtered_df['payment_val'] = 0.0

    if update_df is not None:
        update_df.columns = update_df.columns.astype(str).str.strip()
        
        # 1. Detect ID/Key Column in Update File
        up_id_col = None
        for c in update_df.columns:
            c_clean = c.lower().replace("_", "").replace(" ", "")
            if any(k in c_clean for k in ["loan", "id", "customer", "contract", "account", "name", "officer"]):
                up_id_col = c
                break
        if not up_id_col:
            up_id_col = update_df.columns[0]

        # 2. Detect Amount Column in Update File (First Numeric or Highest Sum Column)
        up_amt_col = None
        best_sum = -1
        for c in update_df.columns:
            if c != up_id_col:
                converted = pd.to_numeric(update_df[c], errors='coerce').fillna(0)
                if converted.sum() > best_sum and converted.sum() > 0:
                    best_sum = converted.sum()
                    up_amt_col = c

        if up_id_col and up_amt_col:
            # Clean Keys for Matching (Remove spaces, lowercase, remove trailing .0)
            def clean_key(val):
                s = str(val).strip().lower()
                s = re.sub(r'\.0$', '', s)
                return s

            filtered_df['match_key'] = filtered_df[main_id_col].apply(clean_key)
            update_df['match_key'] = update_df[up_id_col].apply(clean_key)
            update_df['clean_amount'] = pd.to_numeric(update_df[up_amt_col], errors='coerce').fillna(0)

            # Map Payments
            pmt_map = update_df.groupby('match_key')['clean_amount'].sum().to_dict()
            filtered_df['payment_val'] = filtered_df['match_key'].map(pmt_map).fillna(0.0)

            # Secondary Fallback: Try Name matching if ID match yielded 0 total
            if filtered_df['payment_val'].sum() == 0 and off_col_name in filtered_df.columns:
                filtered_df['name_key'] = filtered_df[off_col_name].apply(clean_key)
                update_df['name_key'] = update_df[up_id_col].apply(clean_key)
                name_pmt_map = update_df.groupby('name_key')['clean_amount'].sum().to_dict()
                filtered_df['payment_val'] = filtered_df['name_key'].map(name_pmt_map).fillna(0.0)

            st.success(f"✅ Update File Processed: Matched {up_id_col} → {up_amt_col} | Total In: {filtered_df['payment_val'].sum():,.2f} EGP")

    elif selected_date and selected_date in filtered_df.columns:
        filtered_df['payment_val'] = pd.to_numeric(filtered_df[selected_date], errors='coerce').fillna(0.0)

    # ------------------- HELPER FUNCTION FOR TABLES -------------------
    def process_bucket_data(sub_df, target_val):
        if sub_df.empty:
            return pd.DataFrame(), 0, 0

        tot_in = sub_df['payment_val'].sum()
        pct_in = (tot_in / target_val * 100) if target_val > 0 else 0

        prin_col = [c for c in sub_df.columns if any(k in c.lower() for k in ['principal', 'rem', 'bal'])]
        p_col = prin_col[0] if prin_col else sub_df.columns[2]

        tbl = sub_df.groupby(off_col_name).agg(
            Principal=(p_col, 'sum'),
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
            off_col_name: 'NAME',
            'DAILY_IN': 'DAILY IN',
            'TOTAL_IN': 'TOTAL IN',
            'PAID_COUNT': '# PAID'
        }, inplace=True)

        return tbl[['NAME', 'TARGET B', 'DAILY IN', 'TOTAL IN', '# PAID', 'REMAINING', '% TARGET']], tot_in, pct_in

    # ------------------- PAGE: DAILY TARGET -------------------
    if page == "🎯 Daily Target":
        prin_cols = [c for c in filtered_df.columns if any(k in c.lower() for k in ['principal', 'rem', 'bal'])]
        p_main = prin_cols[0] if prin_cols else filtered_df.columns[2]

        total_target_all = filtered_df[p_main].sum()
        total_in_all = filtered_df['payment_val'].sum()
        remaining_all = total_target_all - total_in_all
        pct_all = (total_in_all / total_target_all * 100) if total_target_all > 0 else 0

        # Top Bar Summary
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
            c1_df = filtered_df[filtered_df['cycle_clean'].str.contains('1|C1|CYCLE-1', na=False)]
            if c1_df.empty:
                c1_df = filtered_df.iloc[:len(filtered_df)//2] # Fallback split if cycle column missing

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
            c2_df = filtered_df[filtered_df['cycle_clean'].str.contains('16|C16|CYCLE-2|2', na=False)]
            if c2_df.empty:
                c2_df = filtered_df.iloc[len(filtered_df)//2:] # Fallback split

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

            prin_cols = [c for c in sub_df.columns if any(k in c.lower() for k in ['principal', 'rem', 'bal'])]
            p_col = prin_cols[0] if prin_cols else sub_df.columns[2]

            perf = sub_df.groupby(off_col_name).agg(
                Principal=(p_col, 'sum'),
                Paid_Cases=('payment_val', lambda x: (x > 0).sum())
            ).reset_index()

            tot_p = perf['Principal'].sum()
            perf['PRINCIPAL %'] = (perf['Principal'] / tot_p * 100) if tot_p > 0 else 0
            perf = perf.sort_values(by='PRINCIPAL %', ascending=False).reset_index(drop=True)

            perf['RANK'] = perf.index + 1
            perf['DIFF %'] = perf['PRINCIPAL %'].diff().abs().fillna(0)
            perf['DIFF $'] = perf['Principal'].diff().abs().fillna(0)
            perf['FROM TARGET (95%)'] = perf['PRINCIPAL %'] * 0.95

            perf.rename(columns={off_col_name: 'NAME', 'Paid_Cases': '# PAID'}, inplace=True)
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
            c1_sub = filtered_df[filtered_df['cycle_clean'].str.contains('1|C1|CYCLE-1', na=False)]
            render_agent_perf(c1_sub if not c1_sub.empty else filtered_df, "Cycle-1 / BUCKET-1")

        with col2:
            c2_sub = filtered_df[filtered_df['cycle_clean'].str.contains('16|C16|CYCLE-2|2', na=False)]
            render_agent_perf(c2_sub if not c2_sub.empty else filtered_df, "Cycle-2 / BUCKET-1")

    else:
        st.info(f"Page **{page}** is ready.")

else:
    st.info("💡 Please upload your Main Portfolio Excel file in the sidebar to view the Dashboard.")
