import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# =========================
# Configuration
# =========================
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

# =========================
# Functions
# =========================
def request_custom_mapping(df, missing_attrs):
    """Ask user to map missing attributes to actual columns via Streamlit selectboxes."""
    mapping = {}
    st.write("### Map Missing Attributes")
    for attr in missing_attrs:
        col = st.selectbox(
            f"Select column for '{attr}' (optional, skip if not available)",
            options=[None] + list(df.columns),
            index=0,
            key=attr
        )
        if col:
            mapping[attr] = col
    return mapping


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


def analyze_gl(df, user_mapping=None):
    col_mapping, missing, present = validate_and_map_attributes(df, user_mapping)

    # Separate mandatory and optional
    mandatory_missing = [m for m in missing if REQUIRED_ATTRIBUTES[m]["mandatory"]]
    optional_missing = [m for m in missing if not REQUIRED_ATTRIBUTES[m]["mandatory"]]

    # Interactive mapping for missing attributes
    if mandatory_missing + optional_missing:
        extra_mapping = request_custom_mapping(df, mandatory_missing + optional_missing)
        user_mapping = {**(user_mapping or {}), **extra_mapping}
        col_mapping, missing, present = validate_and_map_attributes(df, user_mapping)
        mandatory_missing = [m for m in missing if REQUIRED_ATTRIBUTES[m]["mandatory"]]

    # Stop if mandatory attributes are missing
    if mandatory_missing:
        st.error(f"Missing mandatory attributes: {mandatory_missing}. Cannot continue.")
        return None, None, None, None, None

    # Show attribute mapping info
    st.write("### Attribute Status")
    for attr in REQUIRED_ATTRIBUTES:
        if attr in present:
            st.success(f"{attr} → Present (affects: {', '.join(ATTRIBUTE_DEPENDENCIES.get(attr, []))})")
        else:
            st.warning(f"{attr} → Missing (affects: {', '.join(ATTRIBUTE_DEPENDENCIES.get(attr, []))})")

    # Identify columns
    account_col = next((c for c in ["account_name", "account", "gl_account", "account_code", "description", "memo_description"] if c in df.columns), None)
    debit_col = next((c for c in ["debit", "debit_gbp", "debits", "dr"] if c in df.columns), None)
    credit_col = next((c for c in ["credit", "credit_gbp", "credits", "cr"] if c in df.columns), None)

    # Clean and calculate
    df = df[~df[account_col].astype(str).str.lower().str.contains("total|sum")]
    df = df[df[account_col].notna()]
    df = df[df[debit_col].notna() | df[credit_col].notna()]

    for col in [debit_col, credit_col]:
        df[col] = (df[col].astype(str).str.replace(",", "").str.replace(" ", "").replace("", "0").astype(float))

    df["net_amount"] = df[debit_col].fillna(0) - df[credit_col].fillna(0)

    # Account classification
    account_mapping = {
        "Revenue": ["revenue", "sales", "subscription", "license", "saas", "renewal"],
        "COGS": ["cogs", "cost", "goods", "inventory", "hosting", "support"],
        "OPEX": ["expense", "operating", "salary", "rent", "utilities", "marketing", "wages"],
        "Other Income": ["interest", "misc", "gain"],
        "Other Expense": ["interest", "depreciation", "amortization", "loss"]
    }

    def classify_account(name):
        if pd.isna(name):
            return "Unclassified"
        name = str(name).lower().replace(" ", "")
        for cat, keywords in account_mapping.items():
            if any(k in name for k in keywords):
                return cat
        return "Unclassified"

    df["account_category"] = df[account_col].apply(classify_account)

    # Calculate KPIs
    kpis = {}
    for cat in ["Revenue", "COGS", "OPEX", "Other Income", "Other Expense"]:
        kpis[cat] = df[df["account_category"] == cat]["net_amount"].sum()

    gross_profit = kpis["Revenue"] - kpis["COGS"]
    ebitda = gross_profit - kpis["OPEX"]
    net_profit = ebitda + kpis["Other Income"] - kpis["Other Expense"]

    kpis.update({
        "Gross Profit": gross_profit,
        "EBITDA": ebitda,
        "Net Profit": net_profit
    })

    summary_df = df.groupby("account_category")["net_amount"].sum().reset_index().sort_values(by="net_amount", ascending=False)

    return df, kpis, summary_df, account_col, (debit_col, credit_col)


# =========================
# Streamlit App
# =========================
st.title("Interactive GL Analyzer")

uploaded_file = st.file_uploader("Upload your GL file (CSV or Excel)", type=["csv", "xlsx"])
if uploaded_file:
    # Load file
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    df, kpis, summary_df, account_col, debit_credit_cols = analyze_gl(df)

    if df is not None:
        st.write("### Summary Table")
        st.dataframe(summary_df)

        # Plotly attractive 3D-like bar chart
        metrics = list(kpis.keys())
        values = list(kpis.values())

        fig = go.Figure(data=[go.Bar(
            x=metrics,
            y=values,
            marker=dict(color=values, colorscale='Viridis', line=dict(color='rgb(8,48,107)', width=1.5)),
            text=[f"{v:,.0f}" for v in values],
            textposition='auto'
        )])

        fig.update_layout(title="Financial Metrics", yaxis_title="Amount (£)", template="plotly_dark")
        st.plotly_chart(fig)
