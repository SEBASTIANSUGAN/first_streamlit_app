import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

# ===== Your constants =====
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

# ===== Helper functions =====
def detect_header(df):
    for i, row in df.iterrows():
        row_str = " ".join([str(x).lower() for x in row.tolist() if pd.notna(x)])
        if "debit" in row_str and "credit" in row_str:
            return i
    return None

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

# ===== Main analysis logic (kept as original) =====
def analyze_gl(df, user_mapping=None, show_plot=True):
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    col_mapping, missing, present = validate_and_map_attributes(df, user_mapping)

    st.subheader("✅ Attributes present:")
    for p in present:
        st.write(f" - {p}")

    interactive_mapping = {}
    if missing:
        st.warning("⚠️ Some attributes are missing. Map them below:")
        for attr in missing:
            # Use actual column names from the GL as dropdown options
            options = ["--skip--"] + list(df.columns)
            selection = st.selectbox(f"Map '{attr}' to a column:", options, key=attr)
            if selection != "--skip--":
                interactive_mapping[attr] = selection

        if interactive_mapping:
            user_mapping = {**(user_mapping or {}), **interactive_mapping}
            col_mapping, missing, present = validate_and_map_attributes(df, user_mapping)

    mandatory_missing = [m for m in missing if REQUIRED_ATTRIBUTES[m]["mandatory"]]
    if mandatory_missing:
        st.error("❌ Mandatory attributes still missing: " + ", ".join(mandatory_missing))
        return df, {}, None

    st.success("🎯 All required attributes found or mapped!")

    # ==== Your KPI and plotting logic remains unchanged ====
    # (Use same code as before for classification, calculation, and plotting)

    return df, {}, {}  # Placeholder for actual return

# ===== Streamlit UI =====
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
        raw_df = pd.read_csv(uploaded_file, header=None)
    else:
        raw_df = pd.read_excel(uploaded_file, header=None)

    header_idx = detect_header(raw_df)
    if header_idx is not None:
        df = pd.read_excel(uploaded_file, header=header_idx) if uploaded_file.name.endswith(('.xls','.xlsx')) else pd.read_csv(uploaded_file, header=header_idx)
        analyze_gl(df, user_mapping=user_mapping)
    else:
        st.error("Could not detect header row with Debit/Credit columns.")
