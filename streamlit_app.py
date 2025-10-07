import streamlit as st
import pandas as pd
import io

# -----------------------------------
# Required attributes and explanations
# -----------------------------------
REQUIRED_ATTRIBUTES = {
    "jnl": {
        "mandatory": False,
        "description": "Used for journal-level aggregation and reconciliation across entries."
    },
    "curr": {
        "mandatory": False,
        "description": "Required to identify the currency for conversion and financial rollups."
    },
    "txn_amt": {
        "mandatory": False,
        "description": "Used to compute transactional-level amounts contributing to Trial Balance and Net Profit."
    },
    "debit_gbp": {
        "mandatory": True,
        "description": "Required to calculate Trial Balance, Net Profit, and other GBP-based metrics."
    },
    "credit_gbp": {
        "mandatory": True,
        "description": "Required to calculate Trial Balance, Net Profit, and other GBP-based metrics."
    },
    "account_category": {
        "mandatory": True,
        "description": "Needed to categorize accounts into Assets, Liabilities, Expenses, and Income."
    }
}

# -----------------------------------
# Function to validate attributes
# -----------------------------------
def validate_attributes(df):
    missing_attributes = []
    for attr, meta in REQUIRED_ATTRIBUTES.items():
        if attr not in df.columns:
            missing_attributes.append({
                "Attribute": attr,
                "Mandatory": "Yes" if meta["mandatory"] else "No",
                "Description": meta["description"]
            })
    return pd.DataFrame(missing_attributes)

# -----------------------------------
# Streamlit UI
# -----------------------------------
st.title("🔍 FP&A Attribute Validation Tool")

uploaded_file = st.file_uploader("Upload your GL file (CSV or Excel)", type=["csv", "xlsx"])

if uploaded_file:
    # Read file
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    st.success(f"✅ File uploaded successfully: {uploaded_file.name}")
    st.write("### Preview of Uploaded Data")
    st.dataframe(df.head())

    # Validate attributes
    st.write("### Missing Required Attributes")
    missing_df = validate_attributes(df)

    if missing_df.empty:
        st.success("🎉 All required attributes are present!")
    else:
        # Display table with tooltips (hover info)
        def format_with_tooltip(row):
            tooltip = row["Description"]
            attr = row["Attribute"]
            return f"{attr} ℹ️", tooltip

        st.markdown("Hover over the ℹ️ icon to see why the attribute is required.")
        styled_df = missing_df.copy()
        styled_df["Attribute"] = styled_df.apply(lambda row: f'<span title="{row["Description"]}">{row["Attribute"]} ℹ️</span>', axis=1)
        st.write(styled_df[["Attribute", "Mandatory"]].to_html(escape=False, index=False), unsafe_allow_html=True)

        st.warning("⚠️ Please provide a mapping for these attributes before running FP&A calculations.")
else:
    st.info("Please upload a file to start the validation.")

# -----------------------------------
# Optional: Instructions / Help section
# -----------------------------------
with st.expander("ℹ️ Help: Why validate attributes?"):
    st.write("""
    - This tool ensures all required attributes are available for FP&A calculations like Trial Balance and Net Profit.
    - Missing attributes can lead to incomplete or inaccurate financial metrics.
    - Hover over each attribute to see why it’s important.
    """)
