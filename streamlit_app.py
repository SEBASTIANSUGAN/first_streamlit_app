import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# ------------------------
# Configurations
# ------------------------
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
        "mandatory": False,
        "possible_names": [
            "debit_gbp", "debit", "dr", "debit_amount", "debits",
            "debit_value", "debit_in_gbp", "debit_local", "debit_usd","debit_($)"
        ]
    },
    "credit_gbp": {
        "mandatory": False,
        "possible_names": [
            "credit_gbp", "credit", "cr", "credit_amount", "credits",
            "credit_value", "credit_in_gbp", "credit_local", "credit_usd","credit_($)"
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
    df_columns = [c.lower().strip() for c in df.columns]
    col_mapping, missing, present = {}, [], []

    for attr, props in REQUIRED_ATTRIBUTES.items():
        found = None

        # 1️⃣ Direct match
        if attr in df_columns:
            found = attr

        # 2️⃣ User-provided mapping
        elif user_mapping and attr in user_mapping and user_mapping[attr].lower() in df_columns:
            found = user_mapping[attr].lower()

        # 3️⃣ Match from possible names list
        else:
            for alt in props.get("possible_names", []):
                if alt.lower() in df_columns:
                    found = alt.lower()
                    break

        if found:
            col_mapping[attr] = found
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
                             "description", "memo_description", "account_key", "details"]
    account_col = next((c for c in possible_account_cols if c in df.columns), None)

    # Detect debit, credit, or amount columns
    possible_debit_cols = ["debit_gbp", "debit", "dr", "debit_amount", "debits",
                           "debit_value", "debit_in_gbp", "debit_local", "debit_usd", "debit_($)"]
    possible_credit_cols = ["credit_gbp", "credit", "cr", "credit_amount", "credits",
                            "credit_value", "credit_in_gbp", "credit_local", "credit_usd", "credit_($)"]
    possible_amount_cols = ["txn_amt", "transaction_amount", "amount", "value", "net_amount"]
    
    debit_col = next((c for c in possible_debit_cols if c in df.columns), None)
    credit_col = next((c for c in possible_credit_cols if c in df.columns), None)
    amount_col = next((c for c in possible_amount_cols if c in df.columns), None)
    
    # Clean numeric columns
    for col in [debit_col, credit_col, amount_col]:
        if col and col in df.columns:
            df[col] = (df[col].astype(str)
                       .str.replace(",", "")
                       .str.replace(" ", "")
                       .replace("", "0")
                       .astype(float))
    
    # Derive net amount logic
    if debit_col and credit_col:
        df["net_amount"] = df[debit_col].fillna(0) - df[credit_col].fillna(0)
    elif amount_col:
        df["net_amount"] = df[amount_col].fillna(0)
    else:
        st.error("❌ Could not find debit/credit or amount columns for calculation.")
        return df, {}, None

    account_mapping = {
         "Revenue": [
        "sales", "sales return"
        ],
        "COGS": [
            "cost of sales"
        ],
        "OPEX": [
            "staff costs", "bad debt expense", "commissions", "conferences",
            "advertisements", "travel", "entertainment", "office supplies",
            "professional services", "telephone", "utilities", "other expenses",
            "rent", "vehicles", "equipment", "furniture and fixtures"
        ],
        "Other Income": [
            "interest income", "dividend income", "gain/loss on sales of asset",
            "exchange gain"
        ],
        "Other Expense": [
            "interest expense", "amortization of intangible assets",
            "depreciation", "exchange loss", "taxation", "adjusting"
        ]
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

    # Trial Balance
    if debit_col and debit_col in df.columns:
        df[debit_col] = df[debit_col].fillna(0)
    if credit_col and credit_col in df.columns:
        df[credit_col] = df[credit_col].fillna(0)
    
    # Handle aggregation logic
    if debit_col and credit_col:
        tb_df = df.groupby("account_category").agg(
            total_debit=(debit_col, "sum"),
            total_credit=(credit_col, "sum")
        ).reset_index()
        tb_df["balance"] = tb_df["total_debit"] - tb_df["total_credit"]
    elif amount_col and amount_col in df.columns:
        df[amount_col] = df[amount_col].fillna(0)
        tb_df = df.groupby("account_category").agg(
            total_amount=(amount_col, "sum")
        ).reset_index()
        tb_df["balance"] = tb_df["total_amount"]
    else:
        st.error("❌ No valid debit, credit, or amount column found for balance calculation.")
        return df, kpis, summary_df
    
    st.subheader("Trial Balance")
    st.dataframe(tb_df, use_container_width=True)
    
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

    # ------------------------
    # Enhanced Header Row Detection
    # ------------------------
    header_keywords = [
    # Amounts
    "debit", "credit", "amount", "balance", "debit_amount", "credit_amount", 
    "net_amount", "total", "transaction_amount", "value", "dr", "cr", 
    "debit_gbp", "credit_gbp", "amount_gbp",

    # Dates
    "gl_date", "posted_date", "posting_date", "transaction_date", "doc_date", 
    "journal_date", "date", "entry_date", "value_date", "fiscal_period", 
    "period", "fiscal_year", "year", "month",

    # Accounts
    "gl_account", "account", "account_number", "account_no", "account_name", 
    "main_account", "ledger_account", "account_code", "coa_code", "coa_name", 
    "chart_of_account",

    # Document / Reference
    "doc_no", "document_no", "document_number", "voucher_no", "journal_id", 
    "journal_no", "reference", "reference_no", "ref_no", "batch_no", 
    "entry_id", "transaction_id",

    # Description / Memo
    "description", "memo", "memo_description", "narration", "remarks", 
    "comments", "details", "line_description", "transaction_description",

    # Department / Organization
    "department", "department_name", "cost_center", "costcentre", "division", 
    "business_unit", "unit", "entity", "company", "company_name", "location", 
    "region", "branch",

    # People / Vendor / Customer
    "vendor", "vendor_name", "supplier", "supplier_name", "customer", 
    "customer_name", "employee", "employee_name", "partner", "client",

    # Product / Item / Project
    "product", "product_name", "item", "item_name", "project", "project_name", 
    "job", "job_name", "work_order", "work_order_no",

    # Transaction Type / Category
    "transaction_type", "transaction_category", "entry_type", "journal_type", 
    "posting_type", "record_type", "gl_type", "account_type", "source", 
    "source_system", "module",

    # Miscellaneous
    "currency", "currency_code", "fx_rate", "exchange_rate", "status", "flag", 
    "approved_by", "created_by", "updated_by", "timestamp"
]


    header_row_idx = None

    for i, row in df_raw.iterrows():
        row_str = " ".join([str(x).lower() for x in row.tolist() if pd.notna(x)])
        match_count = sum(1 for kw in header_keywords if kw in row_str)
        if match_count >= 3:
            header_row_idx = i
            break

    if header_row_idx is None:
        st.error("❌ Could not detect a valid header row. Please ensure your file contains Debit/Credit or standard GL columns.")
    else:
        st.success(f"✅ Header row detected at line {header_row_idx + 1}")
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file, header=header_row_idx)
        else:
            df = pd.read_excel(uploaded_file, header=header_row_idx)

        df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
        analyze_gl(df)
