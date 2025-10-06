import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# ------------------------
# Configurations
# ------------------------
REQUIRED_ATTRIBUTES = {
    "posted_dt": {"mandatory": False},
    "doc_dt": {"mandatory": False},
    "doc": {"mandatory": False},
    "memo_description": {"mandatory": False},
    "department_name": {"mandatory": False},
    "supplier_name": {"mandatory": False},
    "item_name": {"mandatory": False},
    "customer_name": {"mandatory": False},
    "jnl": {"mandatory": False},
    "curr": {"mandatory": False},
    "txn_amt": {"mandatory": False},
    "debit_gbp": {"mandatory": True},
    "credit_gbp": {"mandatory": True},
    "balance_gbp": {"mandatory": False},
}

CUSTOM_MAPPING = {
    "memo/description": "memo_description",
    "debit_(gbp)": "debit_gbp",
    "credit_(gbp)": "credit_gbp",
    "balance_(gbp)": "balance_gbp",
}

ATTRIBUTE_DEPENDENCIES = {
    "debit_gbp": ["Revenue", "COGS", "OPEX", "Gross Profit", "EBITDA", "Net Profit"],
    "credit_gbp": ["Revenue", "COGS", "OPEX", "Gross Profit", "EBITDA", "Net Profit"],
    "balance_gbp": ["Net Profit"],
    "txn_amt": ["Revenue", "COGS", "OPEX"],
    "curr": ["Revenue", "COGS", "OPEX"],
    "jnl": ["OPEX", "COGS"],
    "posted_dt": ["Revenue trends", "Period-based KPIs"],
    "doc_dt": ["Revenue trends", "Period-based KPIs"],
    "doc": ["Audit/Traceability"],
    "memo_description": ["OPEX Classification", "COGS Classification"],
    "department_name": ["OPEX Classification"],
    "supplier_name": ["COGS Classification"],
    "item_name": ["COGS Classification"],
    "customer_name": ["Revenue Classification"]
}

# ------------------------
# Validation + Mapping
# ------------------------
def validate_and_map_attributes(df, user_mapping=None):
    df.rename(columns=CUSTOM_MAPPING, inplace=True)
    df_columns = df.columns.tolist()
    col_mapping, missing, present = {}, [], []

    for attr, props in REQUIRED_ATTRIBUTES.items():
        if attr in df_columns:
            col_mapping[attr] = attr
            present.append(attr)
        elif user_mapping and attr in user_mapping and user_mapping[attr] in df_columns:
            col_mapping[attr] = user_mapping[attr]
            present.append(attr)
        else:
            missing.append(attr)

    return col_mapping, missing, present

# ------------------------
# GL Analyzer
# ------------------------
def analyze_gl(df, user_mapping=None, show_plot=True):
    col_mapping, missing, present = validate_and_map_attributes(df, user_mapping)
    mandatory_missing = [m for m in missing if REQUIRED_ATTRIBUTES[m]["mandatory"]]
    optional_missing = [m for m in missing if not REQUIRED_ATTRIBUTES[m]["mandatory"]]

    # Side by side layout
    col1, col2 = st.columns([1, 2], gap="large")

    with col1:
        if mandatory_missing or optional_missing:
            st.subheader("Interactive Attribute Mapping")
            for attr in mandatory_missing + optional_missing:
                col = st.selectbox(
                    f"Map '{attr}' to a column (skip if not available)",
                    options=[""] + list(df.columns),
                    key=attr
                )
                if col != "":
                    if user_mapping is None:
                        user_mapping = {}
                    user_mapping[attr] = col

            col_mapping, missing, present = validate_and_map_attributes(df, user_mapping)
            mandatory_missing = [m for m in missing if REQUIRED_ATTRIBUTES[m]["mandatory"]]

        if mandatory_missing:
            st.error(f"Mandatory attributes missing: {mandatory_missing}. Cannot compute KPIs.")
            return df, {}, None

        st.success("All required attributes found or mapped!")

    with col2:
        st.subheader("Attribute Impact on Metrics")
        attr_impact_data = []
        for attr in REQUIRED_ATTRIBUTES.keys():
            status = "✅ Present" if attr in present else "⚠️ Missing"
            affected_metrics = ATTRIBUTE_DEPENDENCIES.get(attr, ["General KPIs"])
            attr_impact_data.append({
                "Attribute": attr,
                "Status": status,
                "Affected Metrics": ", ".join(affected_metrics)
            })
        st.dataframe(pd.DataFrame(attr_impact_data), use_container_width=True)

    # ========================
    # Continue with KPI calculation
    # ========================
    possible_account_cols = ["account_name", "account", "gl_account", "account_code",
                             "description", "memo_description"]
    account_col = next((c for c in possible_account_cols if c in df.columns), None)

    possible_debit_cols = ["debit", "debit_gbp", "debits", "dr"]
    possible_credit_cols = ["credit", "credit_gbp", "credits", "cr"]

    debit_col = next((c for c in possible_debit_cols if c in df.columns), None)
    credit_col = next((c for c in possible_credit_cols if c in df.columns), None)

    df = df[~df[account_col].astype(str).str.lower().str.contains("total|sum")]
    df = df[df[account_col].notna()]
    df = df[df[debit_col].notna() | df[credit_col].notna()]

    for col in [debit_col, credit_col]:
        df[col] = (df[col].astype(str)
                   .str.replace(",", "")
                   .str.replace(" ", "")
                   .replace("", "0")
                   .astype(float))

    df["net_amount"] = df[debit_col].fillna(0) - df[credit_col].fillna(0)

    account_mapping = {
        "Revenue": ["revenue", "sales", "subscription", "license", "saas", "renewal"],
        "COGS": ["cogs", "cost", "goods", "inventory", "hosting", "support"],
        "OPEX": ["expense", "operating", "salary", "rent", "utilities", "marketing", "wages"],
        "Other Income": ["interest", "misc", "gain"],
        "Other Expense": ["interest", "depreciation", "amortization", "loss"]
    }

    def classify_account(account_name):
        if pd.isna(account_name):
            return "Unclassified"
        name = str(account_name).lower().replace(" ", "")
        for category, keywords in account_mapping.items():
            if any(k in name for k in keywords):
                return category
        return "Unclassified"

    df["account_category"] = df[account_col].apply(classify_account)

    total = df["net_amount"].sum()
    revenue = df[df["account_category"] == "Revenue"]["net_amount"].sum()
    cogs = df[df["account_category"] == "COGS"]["net_amount"].sum()
    opex = df[df["account_category"] == "OPEX"]["net_amount"].sum()
    other_income = df[df["account_category"] == "Other Income"]["net_amount"].sum()
    other_expense = df[df["account_category"] == "Other Expense"]["net_amount"].sum()

    gross_profit = revenue - cogs
    ebitda = gross_profit - opex
    net_profit = ebitda + other_income - other_expense

    kpis = {
        "Revenue": revenue,
        "COGS": cogs,
        "OPEX": opex,
        "Gross Profit": gross_profit,
        "EBITDA": ebitda,
        "Other Income": other_income,
        "Other Expense": other_expense,
        "Net Profit": net_profit
    }

    summary_df = df.groupby("account_category")["net_amount"].sum().reset_index()
    summary_df = summary_df.sort_values(by="net_amount", ascending=False).reset_index(drop=True)

    # Visualization
    if show_plot:
        st.subheader("Financial Metrics Visualization")
        fig = go.Figure()
        colors = ["#3c92cf", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f"]

        for i, (metric, value) in enumerate(kpis.items()):
            fig.add_trace(go.Bar(
                x=[metric],
                y=[value],
                text=f"{value:,.0f}",
                textposition='auto',
                marker_color=colors[i % len(colors)]
            ))

        fig.update_layout(
            title="Financial KPIs",
            yaxis_title="Amount (£)",
            xaxis_title="Metrics",
            template="plotly_white",
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            showlegend=False
        )

        st.plotly_chart(fig, use_container_width=True)

    # ========================
    # KPI values + Summary side by side
    # ========================
    st.markdown("---")
    col3, col4 = st.columns([1, 1], gap="large")

    with col3:
        st.subheader("KPIs")
        kpi_df = pd.DataFrame(list(kpis.items()), columns=["Metric", "Value"])
        kpi_df["Value"] = kpi_df["Value"].apply(lambda x: f"{x:,.2f}")
        st.dataframe(kpi_df, use_container_width=True)

    with col4:
        st.subheader("Summary by Account Category")
        st.dataframe(summary_df, use_container_width=True)

    # ------------------------
    # Additional Financial Metrics
    # ------------------------
    # Trend Metrics
    trend_metrics = {}
    if "posted_dt" in df.columns:
        df["posted_dt"] = pd.to_datetime(df["posted_dt"])
        ref_date = df["posted_dt"].max()
        for window in [7, 30, 90]:
            start_date = ref_date - pd.Timedelta(days=window)
            subset = df[df["posted_dt"] >= start_date]
            trend_metrics[f"L{window}_total"] = subset["net_amount"].sum()

    st.subheader("Trend Metrics (L7, L30, L90)")
    st.dataframe(pd.DataFrame([trend_metrics]), use_container_width=True)

    # Trial Balance
    tb_df = df.groupby("account_category").agg(
        total_debit=("debit_gbp", "sum"),
        total_credit=("credit_gbp", "sum")
    ).reset_index()
    tb_df["balance"] = tb_df["total_debit"] - tb_df["total_credit"]

    st.subheader("Trial Balance")
    st.dataframe(tb_df, use_container_width=True)

    # Profit & Loss
    pl_df = df.groupby("account_category").agg(
        pl_amount=("net_amount", "sum")
    ).reset_index()

    st.subheader("Profit & Loss")
    st.dataframe(pl_df, use_container_width=True)

    # Balance Sheet
    bs_df = df.groupby("account_category").agg(
        bs_balance=("net_amount", "sum")
    ).reset_index()

    st.subheader("Balance Sheet")
    st.dataframe(bs_df, use_container_width=True)

    return df, kpis, summary_df

# ------------------------
# Streamlit App
# ------------------------
st.title("Interactive GL Analyzer")

uploaded_file = st.file_uploader("Upload your GL file (Excel/CSV)", type=["xlsx", "csv"])

if uploaded_file is not None:
    if uploaded_file.name.endswith(".csv"):
        df_raw = pd.read_csv(uploaded_file, header=None)
    else:
        df_raw = pd.read_excel(uploaded_file, header=None)

    header_row_idx = None
    for i, row in df_raw.iterrows():
        row_str = " ".join([str(x).lower() for x in row.tolist() if pd.notna(x)])
        if "debit" in row_str and "credit" in row_str:
            header_row_idx = i
            break

    if header_row_idx is None:
        st.error("Could not detect header row with Debit/Credit columns")
    else:
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file, header=header_row_idx)
        else:
            df = pd.read_excel(uploaded_file, header=header_row_idx)

        df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
        analyze_gl(df)
