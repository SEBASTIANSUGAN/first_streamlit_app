import pandas as pd
import streamlit as st
import plotly.graph_objects as go

# =======================
# Constants & Mappings
# =======================
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

# =======================
# Functions
# =======================
def validate_and_map_attributes(df, user_mapping=None):
    df.rename(columns=CUSTOM_MAPPING, inplace=True)
    df_columns = df.columns.tolist()
    col_mapping = {}
    missing = []
    present = []

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

def analyze_gl(df, user_mapping=None):
    col_mapping, missing, present = validate_and_map_attributes(df, user_mapping)

    st.subheader("Attributes Check")
    st.markdown("**Attributes Present:**")
    for p in present:
        affected_metrics = ATTRIBUTE_DEPENDENCIES.get(p, ["General KPIs"])
        st.write(f" - {p} (affects: {', '.join(affected_metrics)})")

    if missing:
        st.markdown("**Missing Attributes:**")
        for m in missing:
            affected_metrics = ATTRIBUTE_DEPENDENCIES.get(m, ["General KPIs"])
            st.write(f" - {m} (affects: {', '.join(affected_metrics)})")

        # Interactive mapping
        mapping = {}
        for m in missing:
            col = st.selectbox(f"Map missing attribute '{m}' to actual column:", options=[""] + list(df.columns))
            if col:
                mapping[m] = col

        if mapping:
            user_mapping = {**(user_mapping or {}), **mapping}
            col_mapping, missing, present = validate_and_map_attributes(df, user_mapping)

    # Early exit if mandatory columns still missing
    mandatory_missing = [m for m in missing if REQUIRED_ATTRIBUTES[m]["mandatory"]]
    if mandatory_missing:
        st.error(f"Mandatory columns still missing: {mandatory_missing}")
        return df, {}, None

    # Determine key columns
    possible_account_cols = ["account_name", "account", "gl_account", "account_code",
                             "description", "memo_description"]
    account_col = next((c for c in possible_account_cols if c in df.columns), None)
    debit_col = next((c for c in ["debit", "debit_gbp", "debits", "dr"] if c in df.columns), None)
    credit_col = next((c for c in ["credit", "credit_gbp", "credits", "cr"] if c in df.columns), None)

    if not account_col or not debit_col or not credit_col:
        st.error("Required account/debit/credit columns not found.")
        return df, {}, None

    # Clean data
    df = df[~df[account_col].astype(str).str.lower().str.contains("total|sum")]
    df = df[df[account_col].notna()]
    df = df[df[debit_col].notna() | df[credit_col].notna()]

    for col in [debit_col, credit_col]:
        df[col] = (df[col].astype(str).str.replace(",", "").str.replace(" ", "").replace("", "0").astype(float))

    df["net_amount"] = df[debit_col] - df[credit_col]

    # Account classification
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

    # KPI calculations
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
        "Net Profit": net_profit
    }

    # 3D Plot using Plotly
    fig = go.Figure(data=[go.Bar3d(
        x=list(kpis.keys()),
        y=[0]*len(kpis),
        z=[0]*len(kpis),
        dx=[0.5]*len(kpis),
        dy=[0.5]*len(kpis),
        dz=list(kpis.values()),
        text=[f"{v:,.0f}" for v in kpis.values()],
        hoverinfo='x+dz+text',
        marker=dict(color=['green','red','blue','orange','purple'])
    )])

    fig.update_layout(
        title='Financial Metrics (3D)',
        scene=dict(
            xaxis_title='Metrics',
            yaxis_title='',
            zaxis_title='Amount'
        )
    )

    st.plotly_chart(fig, use_container_width=True)

    return df, kpis, df.groupby("account_category")["net_amount"].sum().reset_index()

# =======================
# Streamlit UI
# =======================
st.title("Interactive General Ledger Analyzer")

uploaded_file = st.file_uploader("Upload GL file (Excel/CSV)", type=["xlsx","csv"])

if uploaded_file:
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file, header=None)

    # Detect header row
    header_row_idx = 0
    for i, row in df.iterrows():
        row_str = " ".join([str(x).lower() for x in row.tolist() if pd.notna(x)])
        if "debit" in row_str and "credit" in row_str:
            header_row_idx = i
            break

    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file, header=header_row_idx)
    else:
        df = pd.read_excel(uploaded_file, header=header_row_idx)

    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]

    df, kpis, summary_df = analyze_gl(df)
