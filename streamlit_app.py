import pandas as pd
import streamlit as st

# ==== Configuration ====
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

# ==== Functions ====
def analyze_gl(df: pd.DataFrame, user_mapping=None):
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    # Apply auto-mapping
    for old, new in CUSTOM_MAPPING.items():
        if old in df.columns and new not in df.columns:
            df.rename(columns={old: new}, inplace=True)

    # Attributes check
    missing, present = [], []
    for attr, meta in REQUIRED_ATTRIBUTES.items():
        if attr not in df.columns:
            missing.append((attr, meta["mandatory"]))
        else:
            present.append(attr)

    # Apply user-provided mapping (from Streamlit)
    if user_mapping:
        df.rename(columns=user_mapping, inplace=True)
        # Re-check after mapping
        missing = [(a, m) for a, m in missing if a not in df.columns]
        present = list(set(df.columns).intersection(REQUIRED_ATTRIBUTES.keys()))

    return df, present, missing


# ==== Streamlit UI ====
st.set_page_config(page_title="GL Analyzer", layout="wide")

st.title("General Ledger Analyzer")
st.write("Upload your GL file (CSV or Excel) and validate required attributes.")

# File upload
uploaded_file = st.file_uploader("Upload GL file", type=["csv", "xlsx"])

if uploaded_file:
    # Load file
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    st.subheader(" Sample Data")
    st.dataframe(df.head())

    # Run initial analysis
    df, present, missing = analyze_gl(df)

    st.subheader(" Attributes Present")
    st.write(present)

    if missing:
        st.subheader(" Missing Attributes")
        st.write(missing)

        st.info("Provide custom mapping for missing attributes (optional ones can be skipped).")

        user_mapping = {}
        for attr, mandatory in missing:
            col_name = st.selectbox(
                f"Map column for **{attr}** ({'Mandatory' if mandatory else 'Optional'})",
                options=[""] + list(df.columns),
                key=attr,
            )
            if col_name:
                user_mapping[col_name] = attr

        if st.button("Apply Mapping"):
            df, present, missing = analyze_gl(df, user_mapping=user_mapping)
            st.success(" Mapping applied!")
            st.write("Now Present:", present)
            st.write("Still Missing:", missing)

    if all(attr in df.columns for attr in ["debit_gbp", "credit_gbp"]):
        st.subheader("Finance KPIs (Example)")
        revenue = df["credit_gbp"].sum()
        expense = df["debit_gbp"].sum()
        profit = revenue - expense

        st.metric("Revenue", f"£{revenue:,.2f}")
        st.metric("Expense", f"£{expense:,.2f}")
        st.metric("Profit", f"£{profit:,.2f}")

