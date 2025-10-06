import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
from datetime import timedelta

# ==========================================
# CONFIGURATION
# ==========================================
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

# ==========================================
# HELPER FUNCTIONS
# ==========================================
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

def trial_balance(df, account_col, debit_col, credit_col):
    tb = df.groupby(account_col, dropna=False).agg(
        total_debit=(debit_col, 'sum'),
        total_credit=(credit_col, 'sum')
    ).reset_index()
    tb['balance'] = tb['total_debit'] - tb['total_credit']
    return tb

def profit_and_loss(df, account_col, debit_col, credit_col):
    pl_df = df.copy()
    pl_df['amount'] = pl_df[debit_col].fillna(0) - pl_df[credit_col].fillna(0)
    pl_summary = pl_df.groupby(account_col)['amount'].sum().reset_index()
    return pl_summary.sort_values(by='amount', ascending=False)

def balance_sheet(df, account_col, debit_col, credit_col):
    df['balance'] = df[debit_col].fillna(0) - df[credit_col].fillna(0)
    bs_df = df.groupby(account_col)['balance'].sum().reset_index()
    return bs_df.sort_values(by='balance', ascending=False)

# ==========================================
# MAIN ANALYSIS FUNCTION
# ==========================================
def analyze_gl(df, user_mapping=None, show_plot=True, output_dir="gl_output"):
    col_mapping, missing, present = validate_and_map_attributes(df, user_mapping)
    mandatory_missing = [m for m in missing if REQUIRED_ATTRIBUTES[m]["mandatory"]]
    
    if mandatory_missing:
        st.error(f"Mandatory attributes missing: {mandatory_missing}. Cannot compute KPIs.")
        return df, {}, None
    st.success("All required attributes found or mapped!")

    # Determine key columns
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
        "EBITDA": ebitda,
        "Other Income": other_income,
        "Other Expense": other_expense,
        "Net Profit": net_profit
    }

    # Financial sheets
    tb_df = trial_balance(df, account_col, debit_col, credit_col)
    pl_df = profit_and_loss(df, account_col, debit_col, credit_col)
    bs_df = balance_sheet(df, account_col, debit_col, credit_col)
    summary_df = df.groupby("account_category")["net_amount"].sum().reset_index().sort_values(by="net_amount", ascending=False)

    # Trend Metrics
    trend_metrics = {}
    if "posted_dt" in df.columns:
        df["posted_dt"] = pd.to_datetime(df["posted_dt"])
        ref_date = df["posted_dt"].max()
        for window in [7, 30, 90]:
            start_date = ref_date - timedelta(days=window)
            subset = df[df["posted_dt"] >= start_date]
            trend_metrics[f"L{window}_total"] = subset["net_amount"].sum()
        st.write("📈 Trend Metrics:", trend_metrics)

    # Plotting
    if show_plot:
        metrics = list(kpis.keys())
        values = list(kpis.values())
        plt.figure(figsize=(8,5))
        bars = plt.bar(metrics, values, color=["green","red","blue","orange","purple","cyan","magenta","brown"])
        plt.title("Financial Metrics")
        plt.ylabel("Amount")
        plt.grid(axis="y", linestyle="--", alpha=0.7)
        for bar in bars:
            yval = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2, yval, f"{yval:,.0f}", ha='center', va='bottom')
        plt.tight_layout()
        st.pyplot(plt)

    # Display summary
    st.subheader("Summary by Account Category")
    st.dataframe(summary_df.style.format({"net_amount": "{:,.2f}"}))

    return df, kpis, summary_df

# ==========================================
# STREAMLIT ENTRY POINT
# ==========================================
st.title("Interactive GL Analyzer")

uploaded_file = st.file_uploader("Upload your GL file (Excel/CSV)", type=["xlsx", "csv"])
if uploaded_file is not None:
    if uploaded_file.name.endswith(".csv"):
        df_raw = pd.read_csv(uploaded_file, header=None)
    else:
        df_raw = pd.read_excel(uploaded_file, header=None)

    # Detect header row automatically
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

        user_mapping = {
            "txn_amt": "transaction_amount",
            "curr": "currency",
            "jnl": "journal_code",
            "posted_dt": "posted_dt"
        }
        analyze_gl(df, user_mapping=user_mapping)
