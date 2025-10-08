import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# =====================================================
# CONFIGURATIONS
# =====================================================

REQUIRED_ATTRIBUTES = {
    "posted_dt": {
        "mandatory": False,
        "possible_names": [
            "posted_dt", "posted_date", "posting_date", "gl_date", "entry_date",
            "transaction_date", "journal_date", "posting_dt", "value_date", "period_date"
        ]
    },
    "doc_dt": {
        "mandatory": False,
        "possible_names": [
            "doc_dt", "document_date", "doc_date", "invoice_date", "bill_date",
            "reference_date", "voucher_date"
        ]
    },
    "doc": {
        "mandatory": False,
        "possible_names": [
            "doc", "document_no", "document_number", "voucher_no", "journal_no",
            "reference_no", "ref_no", "entry_no", "transaction_id", "batch_no"
        ]
    },
    "memo_description": {
        "mandatory": False,
        "possible_names": [
            "memo_description", "description", "memo", "narration", "remarks",
            "line_description", "comments", "details", "gl_description"
        ]
    },
    "department_name": {
        "mandatory": False,
        "possible_names": [
            "department_name", "department", "cost_center", "costcentre",
            "division", "business_unit", "unit", "team", "function"
        ]
    },
    "supplier_name": {
        "mandatory": False,
        "possible_names": [
            "supplier_name", "supplier", "vendor_name", "vendor", "partner",
            "payee", "creditor", "beneficiary"
        ]
    },
    "item_name": {
        "mandatory": False,
        "possible_names": [
            "item_name", "item", "product", "product_name", "sku",
            "material", "material_name", "asset_name"
        ]
    },
    "customer_name": {
        "mandatory": False,
        "possible_names": [
            "customer_name", "customer", "client", "buyer", "account_name",
            "receiver", "payer"
        ]
    },
    "jnl": {
        "mandatory": False,
        "possible_names": [
            "jnl", "journal_type", "entry_type", "transaction_type",
            "record_type", "posting_type", "gl_type"
        ]
    },
    "curr": {
        "mandatory": False,
        "possible_names": [
            "curr", "currency", "currency_code", "fx_currency", "transaction_currency"
        ]
    },
    "txn_amt": {
        "mandatory": False,
        "possible_names": [
            "txn_amt", "transaction_amount", "amount", "value", "net_amount",
            "amount_lcy", "amount_gbp", "amount_usd", "amount_inr"
        ]
    },
    "debit_gbp": {
        "mandatory": True,
        "possible_names": [
            "debit_gbp", "debit", "dr", "debit_amount", "debits",
            "debit_value", "debit_in_gbp", "debit_local", "debit_usd"
        ]
    },
    "credit_gbp": {
        "mandatory": True,
        "possible_names": [
            "credit_gbp", "credit", "cr", "credit_amount", "credits",
            "credit_value", "credit_in_gbp", "credit_local", "credit_usd"
        ]
    },
    "balance_gbp": {
        "mandatory": False,
        "possible_names": [
            "balance_gbp", "balance", "closing_balance", "running_balance",
            "net_balance", "ending_balance", "account_balance"
        ]
    }
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

# =====================================================
# AUTO-DETECTION FUNCTION
# =====================================================

def auto_detect_and_map_columns(df):
    """Automatically detects columns in df that match any of the possible names."""
    df_cols = [c.lower().strip() for c in df.columns]
    col_mapping = {}
    for attr, props in REQUIRED_ATTRIBUTES.items():
        for name in props["possible_names"]:
            if name.lower() in df_cols:
                col_mapping[attr] = name.lower()
                break
    return col_mapping


# =====================================================
# GL ANALYZER
# =====================================================

def analyze_gl(df):
    col_mapping = auto_detect_and_map_columns(df)

    mandatory_missing = [
        attr for attr, props in REQUIRED_ATTRIBUTES.items()
        if props["mandatory"] and attr not in col_mapping
    ]

    if mandatory_missing:
        st.error(f"Mandatory attributes missing: {mandatory_missing}")
        return df, {}, None

    st.success("✅ All required attributes found or mapped!")

    debit_col = col_mapping.get("debit_gbp")
    credit_col = col_mapping.get("credit_gbp")

    possible_account_cols = [
        "account_name", "account", "gl_account", "account_code",
        "description", "memo_description"
    ]
    account_col = next((c for c in possible_account_cols if c in df.columns), None)

    if not account_col:
        st.warning("No account column detected; classification may be limited.")
        account_col = debit_col  # fallback

    for col in [debit_col, credit_col]:
        df[col] = (
            df[col].astype(str)
            .str.replace(",", "")
            .str.replace(" ", "")
            .replace("", "0")
            .astype(float)
        )

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

    kpis = {}
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

    st.subheader("Financial KPIs")
    fig = go.Figure()
    for metric, value in kpis.items():
        fig.add_trace(go.Bar(x=[metric], y=[value], text=f"{value:,.0f}", textposition='auto'))
    st.plotly_chart(fig, use_container_width=True)

    summary_df = df.groupby("account_category")["net_amount"].sum().reset_index()
    st.dataframe(summary_df, use_container_width=True)

    return df, kpis, summary_df


# =====================================================
# STREAMLIT APP
# =====================================================

st.title("🧾 Smart GL Analyzer (Auto Mapping)")

uploaded_file = st.file_uploader("Upload GL File (CSV/Excel)", type=["csv", "xlsx"])

if uploaded_file is not None:
    df = (
        pd.read_csv(uploaded_file)
        if uploaded_file.name.endswith(".csv")
        else pd.read_excel(uploaded_file)
    )
    df.columns = [c.lower().strip().replace(" ", "_") for c in df.columns]
    analyze_gl(df)
