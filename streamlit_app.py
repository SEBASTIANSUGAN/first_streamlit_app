import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

# ====== Your existing constants ======
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

# ====== Functions ======
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

# ====== Main analysis function (interactive) ======
def analyze_gl(uploaded_df, user_mapping=None, show_plot=True):
    df = uploaded_df.copy()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    col_mapping, missing, present = validate_and_map_attributes(df, user_mapping)

    st.subheader("✅ Attributes present:")
    for p in present:
        st.write(f" - {p}")

    interactive_mapping = {}
    if missing:
        st.warning("⚠️ Some attributes are missing. Map them below:")
        for attr in missing:
            options = ["--skip--"] + df.columns.tolist()
            selection = st.selectbox(f"Map '{attr}' to a column:", options, key=attr)
            if selection != "--skip--":
                interactive_mapping[attr] = selection

        # Update mapping
        if interactive_mapping:
            user_mapping = {**(user_mapping or {}), **interactive_mapping}
            col_mapping, missing, present = validate_and_map_attributes(df, user_mapping)

    mandatory_missing = [m for m in missing if REQUIRED_ATTRIBUTES[m]["mandatory"]]
    if mandatory_missing:
        st.error("❌ Mandatory attributes still missing: " + ", ".join(mandatory_missing))
        return df, {}, None

    st.success("🎯 All required attributes found or mapped!")

    # ====== Original KPI logic ======
    possible_account_cols = ["account_name", "account", "gl_account", "account_code",
                             "description", "memo_description"]
    account_col = next((c for c in possible_account_cols if c in df.columns), None)
    possible_debit_cols = ["debit", "debit_gbp", "debits", "dr"]
    possible_credit_cols = ["credit", "credit_gbp", "credits", "cr"]
    debit_col = next((c for c in possible_debit_cols if c in df.columns), None)
    credit_col = next((c for c in possible_credit_cols if c in df.columns), None)

    if not account_col or not debit_col or not credit_col:
        st.error("Could not find required debit/credit/account columns.")
        return df, {}, None

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
        "Total": total,
        "Revenue": revenue,
        "COGS": cogs,
        "Gross Profit": gross_profit,
        "OPEX": opex,
        "EBITDA": ebitda,
        "Other Income": other_income,
        "Other Expense": other_expense,
        "Net Profit": net_profit
    }

    summary_df = df.groupby("account_category")["net_amount"].sum().reset_index()
    summary_df = summary_df.sort_values(by="net_amount", ascending=False)

    # Plot
    if show_plot:
        metrics = ["Revenue", "COGS", "OPEX", "Gross Profit", "Net Profit"]
        values = [revenue, cogs, opex, gross_profit, net_profit]
        fig, ax = plt.subplots(figsize=(8,5))
        bars = ax.bar(metrics, values, color=["green","red","blue","orange","purple"])
        ax.set_title("Financial Metrics")
        ax.set_ylabel("Amount")
        ax.grid(axis="y", linestyle="--", alpha=0.7)
        for bar in bars:
            yval = bar.get_height()
            ax.text(bar.get_x()+bar.get_width()/2, yval, f"{yval:,.0f}", ha='center', va='bottom')
        st.pyplot(fig)

    # Display KPIs & summary
    st.subheader("Finance KPIs")
    for k, v in kpis.items():
        st.write(f"{k}: {v:,.2f}")

    st.subheader("Summary by Account Category")
    st.dataframe(summary_df)

    return df, kpis, summary_df

# ====== Streamlit UI ======
st.title("📊 Interactive General Ledger Analyzer")
uploaded_file = st.file_uploader("Upload Excel/CSV file", type=["xlsx","xls","csv"])

user_mapping = {
    "txn_amt": "transaction_amount",
    "curr": "currency",
    "jnl": "journal_code",
    "Posted dt.": "posted_dt"
}

if uploaded_file:
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file, header=None)
    else:
        df = pd.read_excel(uploaded_file, header=None)
    analyze_gl(uploaded_df=df, user_mapping=user_mapping)
