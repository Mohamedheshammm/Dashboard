import streamlit as st
import pandas as pd
import plotly.express as px

# 1. إعدادات الصفحة
st.set_page_config(page_title="Collections Performance Dashboard", layout="wide")

st.title("📊 Collections Performance & Daily Target Dashboard")

# 2. رفع الملف من الشريط الجانبي
st.sidebar.header("📁 إدارة البيانات والرفع")
uploaded_file = st.sidebar.file_uploader("رفع شيت المتابعة (Excel)", type=["xlsx", "xls"])

if uploaded_file is not None:
    df = pd.read_excel(uploaded_file)
    
    # اختيار فلاتر الموظفين والـ Buckets
    st.sidebar.subheader("🔍 الفلاتر")
    
    statuses = ["الكل"] + list(df['status'].dropna().unique()) if 'status' in df.columns else ["الكل"]
    selected_status = st.sidebar.selectbox("اختر الـ Bucket / Status", statuses)
    
    filtered_df = df.copy()
    if selected_status != "الكل" and 'status' in df.columns:
        filtered_df = filtered_df[filtered_df['status'] == selected_status]

    # 3. حساب الكروت الرئيسية (KPIs)
    total_loans = len(filtered_df)
    total_principal = filtered_df['remaining_principal'].sum() if 'remaining_principal' in filtered_df.columns else 0
    total_officers = filtered_df['Officer'].nunique() if 'Officer' in filtered_df.columns else 0

    kpi1, kpi2, kpi3 = st.columns(3)
    kpi1.metric("إجمالي عدد القروض", f"{total_loans:,}")
    kpi2.metric("إجمالي المبالغ المتبقية (Principal)", f"{total_principal:,.2f} EGP")
    kpi3.metric("عدد ضباط التحصيل (Officers)", f"{total_officers}")

    st.markdown("---")

    # 4. رسوم بيانية وتوزيع الأداء
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📊 توزيع المبالغ حسب الـ Officer")
        if 'Officer' in filtered_df.columns and 'remaining_principal' in filtered_df.columns:
            officer_summary = filtered_df.groupby('Officer')['remaining_principal'].sum().reset_index()
            officer_summary = officer_summary.sort_values(by='remaining_principal', ascending=False).head(15)
            fig_officer = px.bar(officer_summary, x='remaining_principal', y='Officer', orientation='h',
                                 title="أعلى 15 ضابط تحصيل حسـب إجمالي المبالغ")
            st.plotly_chart(fig_officer, use_container_width=True)

    with col2:
        st.subheader("🎯 توزيع الحالات حسب درجة المخاطرة (Risk)")
        if 'Risk' in filtered_df.columns:
            risk_summary = filtered_df['Risk'].value_counts().reset_index()
            risk_summary.columns = ['Risk', 'Count']
            fig_risk = px.pie(risk_summary, names='Risk', values='Count', title="نسب توزيع المخاطر")
            st.plotly_chart(fig_risk, use_container_width=True)

    st.markdown("---")

    # 5. جدول التفاصيل
    st.subheader("📋 تفاصيل البيانات حسب ضباط التحصيل")
    if 'status' in filtered_df.columns and 'Officer' in filtered_df.columns:
        table_summary = filtered_df.groupby(['status', 'Officer']).agg(
            Total_Loans=('loan_id', 'count') if 'loan_id' in filtered_df.columns else ('remaining_principal', 'count'),
            Total_Principal=('remaining_principal', 'sum') if 'remaining_principal' in filtered_df.columns else ('Officer', 'count')
        ).reset_index()

        st.dataframe(
            table_summary.style.format({
                "Total_Loans": "{:,}",
                "Total_Principal": "{:,.2f} EGP"
            }),
            use_container_width=True
        )
    else:
        st.dataframe(filtered_df.head(100), use_container_width=True)

else:
    st.info("💡 مرحباً بك! يرجى رفع ملف Excel الخاص بك من القائمة الجانبية (Sidebar) لبدء تحليل البيانات وعرض الداشبورد.")