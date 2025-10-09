import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import difflib

# ------------------------
# Configurations
# ------------------------
REQUIRED_ATTRIBUTES = {
    "posted_dt": {
        "mandatory": False,
        "possible_names": [
            "posted_dt", "posted_date", "posting_date", "gl_date", "entry_date",
            "transaction_date", "journal_date", "posting_dt", "value_date",
        ],
    },
    "account_category": {
        "mandatory": True,
        "possible_names": [
            "account_category", "acct_category", "gl_category", "category",
        ],
    },
    "debit": {
        "mandatory": False,
        "possible_names": [
            "debit", "debit_amount", "dr_amount", "debits", "amount_dr",
        ],
    },
    "credit": {
        "mandatory": False,
        "possible_names": [
            "credit", "credit_amount", "cr_amount", "credits", "amount_cr",
        ],
    },
    "amount": {
        "mandatory": False,
        "possible_names": [
            "amount", "amt", "value", "transaction_amount",
        ],
    },
}

# ------------------------
# Helper Functions
# ------------------------
def find_best_match(columns, possible_names):
    for name in possible_names:
        for col in columns:
            if name.lower() == col.lower():
                return col
    matches = difflib.get_close_matches(possible_names[0], columns, n=1, cutoff=0.6)
    return matches[0] if matches else None


def detect_header(df):
    """
    Automatically detect header row in uploaded CSV/Excel
    """
    header_row = 0
    for i, row in df.iterrows():
        if any(str(cell).lower() in [name.lower() for attr in REQUIRED_ATTRIBUTES.values() for name in attr["possible_names"]] for cell in row):
            header_row = i
            break
    df.columns = df.iloc[header_row]
    df = df.drop(range(header_row + 1))
    df = df.reset_index(drop=True)
    return df


# ------------------------
# GL Analysis Logic
# ------------------------
def analyze_gl(df, user_mapping=None):
    try:
        df.columns = df.columns.str.strip().str.lower()

        # Ensure account_category column exists
        account_col = find_best_match(df.columns, REQUIRED_ATTRIBUTES["account_category"]["possible_names"])
        if not account_col:
            st.error("❌ No valid account column found. Cannot compute KPIs.")
            return

        # Detect debit, credit, amount columns
        debit_col = find_best_match(df.columns, REQUIRED_ATTRIBUTES["debit"]["possible_names"])
        credit_col = find_best_match(df.columns, REQUIRED_ATTRIBUTES["credit"]["possible_names"])
        amount_col = find_best_match(df.columns, REQUIRED_ATTRIBUTES["amount"]["possible_names"])

        # Handle Trial Balance calculation
        if not debit_col and not credit_col:
            if not amount_col:
                st.error("❌ No valid debit, credit, or amount column found for total calculation.")
                return

            tb_df = df.groupby(account_col).agg(
                total_amount=(amount_col, "sum")
            ).reset_index()
        else:
            if debit_col not in df.columns:
                df["temp_debit"] = 0
                debit_col = "temp_debit"
            if credit_col not in df.columns:
                df["temp_credit"] = 0
                credit_col = "temp_credit"

            tb_df = df.groupby(account_col).agg(
                total_debit=(debit_col, "sum"),
                total_credit=(credit_col, "sum")
            ).reset_index()

        # ------------------------
        # Trial Balance Chart
        # ------------------------
        st.subheader("📊 Trial Balance Summary")
        st.dataframe(tb_df)

        if "total_amount" in tb_df.columns:
            fig = go.Figure(
                data=[
                    go.Bar(
                        x=tb_df[account_col],
                        y=tb_df["total_amount"],
                        name="Total Amount",
                        marker_color="indigo",
                    )
                ]
            )
        else:
            fig = go.Figure(
                data=[
                    go.Bar(
                        x=tb_df[account_col],
                        y=tb_df["total_debit"],
                        name="Total Debit",
                        marker_color="green",
                    ),
                    go.Bar(
                        x=tb_df[account_col],
                        y=tb_df["total_credit"],
                        name="Total Credit",
                        marker_color="orange",
                    ),
                ]
            )

        fig.update_layout(
            title="Trial Balance Overview",
            xaxis_title="Account Category",
            yaxis_title="Amount",
            barmode="group",
            height=500,
        )
        st.plotly_chart(fig)

    except Exception as e:
        st.error(f"❌ Error during analysis: {e}")


# ------------------------
# Streamlit App
# ------------------------
st.set_page_config(page_title="GL Analyzer", layout="wide")

st.title("📘 General Ledger Analyzer")

uploaded_file = st.file_uploader("Upload GL File (CSV or Excel)", type=["csv", "xlsx"])

if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith(".csv"):
            df_raw = pd.read_csv(uploaded_file, header=None)
        else:
            df_raw = pd.read_excel(uploaded_file, header=None)

        df_raw = detect_header(df_raw)

        st.success("✅ File uploaded successfully. Preview below:")
        st.dataframe(df_raw.head())

        analyze_gl(df_raw)

    except Exception as e:
        st.error(f"❌ Error reading file: {e}")
