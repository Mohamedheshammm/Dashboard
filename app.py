import streamlit as st
import pandas as pd
import numpy as np
import re

st.set_page_config(page_title="Collections Dashboard", layout="wide")

st.markdown("""
    <style>
    [data-testid="stSidebar"] { background-color: #0d1b2a; }
    [data-testid="stSidebar"] * { color: #ffffff !important; }
    .header-blue-banner {
        background-color: #0f2b5c; color: white; padding: 8px 12px;
        border-radius: 4px 4px 0 0; font-weight: bold; font-size: 14px;
    }
    .stDataFrame { margin-top: -5px; }
    </style>
""", unsafe_allow_html=True)

st.sidebar.markdown("## 📊 DASHBOARDS")
page = st.sidebar.radio("", ["👥 Team Performance", "📈 Portfolio Analysis", "🎯 Daily Target", "📊 Agent Performance"])

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
    df.columns = df.columns.astype(str).str.strip()
    
    # Detect Officer Name Column
    off_col_name = None
    for c in df.columns:
        c_clean = c.lower().replace("_", "").replace(" ", "")
        if any(k in c_clean for k in ["officer", "agent", "collector", "user", "name"]):
            off_col_name = c
            break
    if not off_col_name:
        off_col_name = df.columns[1]

    # Detect Loan ID Column in Main File
    main_id_col = None
    for c in df.columns:
        c_clean = c.lower().replace("_", "").replace(" ", "")
        if any(k in c_clean for k in ["loanid", "id", "contract", "account"]):
            main_id_col = c
            break
    if not main_id_col:
        main_id_col = df.columns[0]

    # Detect Principal / Bucket Value Column
    prin_cols = [c for c in df.columns if any(k in c.lower() for k in ['principal', 'rem', 'bal', 'amount', 'b1', 'bucket1'])]
    p_col = prin_cols[0] if prin_cols else df.columns[2]

    # Detect Cycle Column
    cycle_col = next((c for c in df.columns if 'cycle' in c.lower()), None)
    df['cycle_clean'] = df[cycle_col].astype(str).str.upper().str.strip() if cycle_col else ""

    filtered_df = df.copy()
    filtered_df['payment_val'] = 0.0
    filtered_df['vf_cash_val'] = 0.0

    # ------------------- MATCHING LOGIC FOR STATUS -------------------
    if update_df is not None:
        update_df.columns = update_df.columns.astype(str).str.strip()
        
        up_id_col = next((c for c in update_df.columns if 'loan' in c.lower() or 'id' in c.lower()), update_df.columns[0])
        status_col = next((c for c in update_df.columns if 'status' in c.lower()), update_df.columns[1] if len(update_df.columns) > 1 else None)

        def norm_key(v):
            return re.sub(r'\.0$', '', str(v).strip().lower())

        filtered_df['match_key'] = filtered_df[main_id_col].apply(norm_key)
        update_df['match_key'] = update_df[up_id_col].apply(norm_key)

        if status_col:
            # Clean Status Text
            update_df['status_clean'] = update_df[status_col].astype(str).str.upper().str.strip()
            
            # Cases considered PAID for Bucket 1
            paid_keywords = ['SETTLED', 'PARTIAL', 'CURRENT', 'PAID', 'SETTLE']
            pattern = '|'.join(paid_keywords)

            # Get Loan IDs that are paid
            paid_ids = set(update_df[update_df['status_clean'].str.contains(pattern, na=False)]['match_key'])

            # Calculate Payment Value (If paid, take Principal / Bucket 1 Value, else 0)
            filtered_df['payment_val'] = np.where(
                filtered_df['match_key'].isin(paid_ids),
                pd.to_numeric(filtered_df[p_col], errors='coerce').fillna(0),
                0.0
            )

        vf_col = next((c for c in update_df.columns if 'vf' in c.lower() or 'vodafone' in c.lower()), None)
        if vf_col:
            update_df['clean_vf'] = pd.to_numeric(update_df[vf_col], errors='coerce').fillna(0)
            vf_map = update_df.groupby('match_key')['clean_vf'].sum().to_dict()
            filtered_df['vf_cash_val'] = filtered_df['match_key'].map(vf_map).fillna(0.0)

        total_collected = filtered_df['payment_val'].sum()
        st.sidebar.success(f"✅ Matching Completed! Total Collected: {total_collected:,.0f}")

    # ------------------- TABLE GENERATION -------------------
    def process_bucket_data(sub_df, target_val):
        if sub_df.empty:
            return pd.DataFrame(), 0, 0, 0

        tot_in = sub_df['payment_val'].sum()
        tot_vf = sub_df['vf_cash_val'].sum()
        pct_in = (tot_in / target_val * 100) if target_val > 0 else 0

        tbl = sub_df.groupby(off_col_name).agg(
            Principal=(p_col, lambda x: pd.to_numeric(x, errors='coerce').fillna(0).sum()),
            DAILY_IN=('payment_val', 'sum'),
            VF_CASH=('vf_cash_val', lambda x: x.sum() if x.sum() > 0 else 0),
            TOTAL_IN=('payment_val', 'sum')
        ).reset_index()

        tot_prin = tbl['Principal'].sum()
        tbl['TARGET $'] = (tbl['Principal'] / tot_prin * target_val) if tot_prin > 0 else 0
        tbl['REMAINING'] = tbl['TARGET $'] - tbl['TOTAL_IN']
        tbl['% TARGET'] = np.where(tbl['TARGET $'] > 0, (tbl['TOTAL_IN'] / tbl['TARGET $']) * 100, 0)

        tbl = tbl.sort_values(by='% TARGET', ascending=False).reset_index(drop=True)
        tbl.index = tbl.index + 1
        tbl.index.name = '#'

        tbl.rename(columns={
            off_col_name: 'NAME',
            'DAILY_IN': 'DAILY IN',
            'VF_CASH': '📲 VF CASH',
            'TOTAL_IN': 'TOTAL IN'
        }, inplace=True)

        return tbl[['NAME', 'TARGET $', 'DAILY IN', '📲 VF CASH', 'TOTAL IN', 'REMAINING', '% TARGET']], tot_in, tot_vf, pct_in

    # Render Bucket Tables
    col1, col2 = st.columns(2)
    with col1:
        t1 = st.number_input("Target C1 (EGP):", value=31985781.0, step=100000.0)
        c1_df = filtered_df[filtered_df['cycle_clean'].str.contains('1|C1|CYCLE-1', na=False)]
        if c1_df.empty: c1_df = filtered_df.iloc[:len(filtered_df)//2]
        tbl1, in1, vf1, pct1 = process_bucket_data(c1_df, t1)

        st.markdown(f"<div class='header-blue-banner'>C1 — BUCKET-1 <br/><small style='color:#facc15;'>Target: {t1:,.0f} - IN: {in1:,.0f} - {pct1:.2f}%</small></div>", unsafe_allow_html=True)
        if not tbl1.empty:
            st.dataframe(tbl1.style.format({'TARGET $': '{:,.0f}', 'DAILY IN': '{:,.0f}', '📲 VF CASH': lambda x: f"{x:,.0f}" if isinstance(x, (int, float)) and x > 0 else "—", 'TOTAL IN': '{:,.0f}', 'REMAINING': '{:,.0f}', '% TARGET': '{:.2f}%'}), height=(len(tbl1)+1)*35+10, use_container_width=True)

    with col2:
        t2 = st.number_input("Target C16 (EGP):", value=5183574.0, step=100000.0)
        c2_df = filtered_df[filtered_df['cycle_clean'].str.contains('16|C16|CYCLE-2|2', na=False)]
        if c2_df.empty: c2_df = filtered_df.iloc[len(filtered_df)//2:]
        tbl2, in2, vf2, pct2 = process_bucket_data(c2_df, t2)

        st.markdown(f"<div class='header-blue-banner'>C16 — BUCKET-1 <br/><small style='color:#facc15;'>Target: {t2:,.0f} - IN: {in2:,.0f} - {pct2:.2f}%</small></div>", unsafe_allow_html=True)
        if not tbl2.empty:
            st.dataframe(tbl2.style.format({'TARGET $': '{:,.0f}', 'DAILY IN': '{:,.0f}', '📲 VF CASH': lambda x: f"{x:,.0f}" if isinstance(x, (int, float)) and x > 0 else "—", 'TOTAL IN': '{:,.0f}', 'REMAINING': '{:,.0f}', '% TARGET': '{:.2f}%'}), height=(len(tbl2)+1)*35+10, use_container_width=True)
else:
    st.info("💡 Please upload your Main Portfolio Excel file in the sidebar.")
