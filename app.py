import streamlit as st
import pandas as pd
import numpy as np

# Set Page Config
st.set_page_config(page_title="Collections Performance Dashboard", layout="wide")

# Custom CSS for UI styling
st.markdown("""
    <style>
    .main-header { font-size: 24px; font-weight: bold; color: #1E3A8A; margin-bottom: 20px; }
    .kpi-card { background-color: #F3F4F6; padding: 15px; border-radius: 8px; border-left: 5px solid #1D4ED8; }
    .stTable { font-size: 13px; }
    </style>
""", unsafe_allow_html=True)

# Sidebar Navigation
st.sidebar.title("📌 Navigation")
page = st.sidebar.radio("Go to Page:", ["🎯 Daily Target", "📊 Agent Performance"])

st.sidebar.markdown("---")
st.sidebar.header("📁 Data Management")
uploaded_file = st.sidebar.file_uploader("Upload Excel File", type=["xlsx", "xls"])

@st.cache_data
def load_data(file):
    if file is not None:
        return pd.read_excel(file)
    else:
        try:
            return pd.read_excel("Dashboard Sep updated Mohamed Hesham.xlsx")
        except:
            return None

df = load_data(uploaded_file)

if df is not None:
    # Extract date columns from the sheet
    fixed_cols = ['customer_id', 'loan_id', 'remaining_principal', 'status', 
                  'cycle_name', 'Officer', 'Type', 'Non-Starter', 
                  'Principal Type', "Call Or Don't Call", 'Risk', 'Update']
    
    date_cols = [col for col in df.columns if col not in fixed_cols]

    # Normalize Cycle Names
    df['cycle_clean'] = df['cycle_name'].astype(str).str.upper().str.strip()

    # PAGE 1: DAILY TARGET
    if page == "🎯 Daily Target":
        st.markdown("<div class='main-header'>🎯 Collections Daily Target Dashboard</div>", unsafe_allow_html=True)

        # Date Selector for Daily Tracking
        selected_date = st.sidebar.selectbox("Select Date for Daily In", date_cols if date_cols else [None])

        # KPI Summary Bar
        c1_df = df[df['cycle_clean'].str.contains('1|CYCLE-1', na=False)]
        c2_df = df[df['cycle_clean'].str.contains('2|CYCLE-2', na=False)]

        total_target = df['remaining_principal'].sum()
        
        # Calculate Daily Collected Amount
        if selected_date:
            daily_in = pd.to_numeric(df[selected_date], errors='coerce').fillna(0).sum()
        else:
            daily_in = 0

        pct_achieved = (daily_in / total_target * 100) if total_target > 0 else 0

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("TOTAL TARGET", f"{total_target:,.0f} EGP")
        k2.metric("TOTAL DAILY IN", f"{daily_in:,.0f} EGP")
        k3.metric("REMAINING TARGET", f"{total_target - daily_in:,.0f} EGP")
        k4.metric("% ACHIEVED", f"{pct_achieved:.2f}%")

        st.markdown("---")

        # Side-by-side view for C1 and C2 Target Tables
        col_c1, col_c2 = st.columns(2)

        with col_c1:
            st.subheader("🔵 C1 - BUCKET-1 (Cycle 1)")
            if not c1_df.empty:
                c1_summary = c1_df.groupby('Officer').agg(
                    TARGET=('remaining_principal', 'sum')
                ).reset_index()
                
                if selected_date:
                    c1_summary['DAILY IN'] = c1_df.groupby('Officer')[selected_date].apply(lambda x: pd.to_numeric(x, errors='coerce').fillna(0).sum()).values
                else:
                    c1_summary['DAILY IN'] = 0

                c1_summary['REMAINING'] = c1_summary['TARGET'] - c1_summary['DAILY IN']
                c1_summary['% TARGET'] = (c1_summary['DAILY IN'] / c1_summary['TARGET']) * 100

                st.dataframe(
                    c1_summary.style.format({
                        "TARGET": "{:,.0f}",
                        "DAILY IN": "{:,.0f}",
                        "REMAINING": "{:,.0f}",
                        "% TARGET": "{:.2f}%"
                    }),
                    use_container_width=True
                )

        with col_c2:
            st.subheader("🟣 C16 - BUCKET-1 (Cycle 2)")
            if not c2_df.empty:
                c2_summary = c2_df.groupby('Officer').agg(
                    TARGET=('remaining_principal', 'sum')
                ).reset_index()

                if selected_date:
                    c2_summary['DAILY IN'] = c2_df.groupby('Officer')[selected_date].apply(lambda x: pd.to_numeric(x, errors='coerce').fillna(0).sum()).values
                else:
                    c2_summary['DAILY IN'] = 0

                c2_summary['REMAINING'] = c2_summary['TARGET'] - c2_summary['DAILY IN']
                c2_summary['% TARGET'] = (c2_summary['DAILY IN'] / c2_summary['TARGET']) * 100

                st.dataframe(
                    c2_summary.style.format({
                        "TARGET": "{:,.0f}",
                        "DAILY IN": "{:,.0f}",
                        "REMAINING": "{:,.0f}",
                        "% TARGET": "{:.2f}%"
                    }),
                    use_container_width=True
                )

    # PAGE 2: AGENT PERFORMANCE
    elif page == "📊 Agent Performance":
        st.markdown("<div class='main-header'>📊 Agents Collection Performance Ranking</div>", unsafe_allow_html=True)

        col_p1, col_p2 = st.columns(2)

        def build_performance_table(sub_df, title):
            st.subheader(title)
            if not sub_df.empty:
                perf = sub_df.groupby('Officer').agg(
                    Total_Cases=('loan_id', 'count'),
                    Principal=('remaining_principal', 'sum')
                ).reset_index()

                total_p = perf['Principal'].sum()
                perf['PRINCIPAL %'] = (perf['Principal'] / total_p) * 100
                perf = perf.sort_values(by='PRINCIPAL %', ascending=False).reset_index(drop=True)
                
                perf['RANK'] = perf.index + 1
                perf['DIFF %'] = perf['PRINCIPAL %'].diff().fillna(0).abs()
                perf['DIFF $'] = perf['Principal'].diff().fillna(0).abs()
                perf['FROM TARGET (95%)'] = perf['PRINCIPAL %'] * 0.95

                # Rearrange columns
                perf = perf[['Officer', 'PRINCIPAL %', 'RANK', 'DIFF %', 'DIFF $', 'FROM TARGET (95%)']]
                perf.rename(columns={'Officer': 'NAME'}, inplace=True)

                st.dataframe(
                    perf.style.format({
                        "PRINCIPAL %": "{:.2f}%",
                        "RANK": "{:d}",
                        "DIFF %": "¬ {:.2f}%",
                        "DIFF $": "¬ {:,.0f}",
                        "FROM TARGET (95%)": "{:.2f}%"
                    }),
                    use_container_width=True
                )

        with col_p1:
            c1_sub = df[df['cycle_clean'].str.contains('1|CYCLE-1', na=False)]
            build_performance_table(c1_sub, "Cycle-1 / BUCKET-1 Performance")

        with col_p2:
            c2_sub = df[df['cycle_clean'].str.contains('2|CYCLE-2', na=False)]
            build_performance_table(c2_sub, "Cycle-2 / BUCKET-1 Performance")

else:
    st.info("💡 Please upload an Excel file to visualize the dashboard.")
