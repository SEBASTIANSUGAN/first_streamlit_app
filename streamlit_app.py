import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# ------------------------
# Configuration
# ------------------------
REQUIRED_ATTRIBUTES = {
    "posted_dt": {"mandatory": False},
    "doc_dt": {"mandatory": False},
    "doc": {"mandatory": False},
    "memo_description": {"mandatory": False},
    "department_name": {"mandatory": False},
    "supplier_name": {"mandatory": False},
    "item_name": {"mandatory": False},
    "customer_name": {"mandatory": False},
    "supplier": {"mandatory": False},
    "jnl": {"mandatory": False},
    "curr": {"mandatory": False},
    "txn_amt": {"mandatory": False}
}

ATTRIBUTE_DEPENDENCIES = {
    "posted_dt": ["Time-based KPIs"],
    "doc_dt": ["Time-based KPIs"],
    "txn_amt": ["Financial KPIs", "Summary by Account Category"],
    "jnl": ["Journal-specific KPIs"],
    "curr": ["Currency conversion KPIs"],
    "supplier_name": ["Vendor analysis"],
    "customer_name": ["Customer analysis"]
}

# ------------------------
# Validation Functions
# ------------------------
def validate_and_map_attributes(df, user_mapping=None):
    df_cols = [c.lower().strip() for c in df.columns]
    col_mapping, missing, present = {}, [], []

    for attr in REQUIRED_ATTRIBUTES:
        mapped_col = None
        if user_mapping and attr in user_mapping and user_mapping[attr] in df.columns:
            mapped_col = user_mapping[attr]
        else:
            for col in df_cols:
                if attr in col:
                    mapped_col = col
                    break

        if mapped_col:
            col_mapping[attr] = mapped_col
            present.append(attr)
        else:
            missing.append(attr)

    return col_mapping, missing, present

# ------------------------
# GL Analysis
# ------------------------
def analyze_gl(file_path, user_mapping=None):
    if file_path.endswith(".csv"):
        df = pd.read_csv(file_path)
    else:
        df = pd.read_excel(file_path)

    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    # Validate attributes
    col_mapping, missing, present = validate_and_map_attributes(df, user_mapping)
    mandatory_missing = [m for m in missing if REQUIRED_ATTRIBUTES[m]["mandatory"]]
    optional_missing = [m for m in missing if not REQUIRED_ATTRIBUTES[m]["mandatory"]]

    # ------------------------
    # Layout: Attribute Mapping & Impact
    # ------------------------
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
            status = "Present" if attr in present else "Missing"
            affected_metrics = ATTRIBUTE_DEPENDENCIES.get(attr, ["General KPIs"])
            attr_impact_data.append({
                "Attribute": attr,
                "Status": status,
                "Affected Metrics": ", ".join(affected_metrics)
            })

        st.dataframe(pd.DataFrame(attr_impact_data), use_container_width=True)

    st.markdown("---")

    # ------------------------
    # Layout: KPI Metrics & Summary
    # ------------------------
    col3, col4 = st.columns(2, gap="large")

    with col3:
        st.subheader("KPI Metrics")
        kpi_data = {
            "Metric": ["Total Transactions", "Unique Suppliers", "Unique Customers"],
            "Value": [
                len(df),
                df[col_mapping.get("supplier_name")].nunique() if "supplier_name" in col_mapping else "N/A",
                df[col_mapping.get("customer_name")].nunique() if "customer_name" in col_mapping else "N/A"
            ]
        }
        st.dataframe(pd.DataFrame(kpi_data), use_container_width=True)

    with col4:
        st.subheader("Summary by Account Category")
        if "txn_amt" in col_mapping:
            fig = go.Figure()
            summary = df.groupby(col_mapping.get("department_name", "department_name"), dropna=False)[
                col_mapping["txn_amt"]
            ].sum().reset_index()

            fig.add_trace(go.Bar(
                x=summary[col_mapping.get("department_name", "department_name")],
                y=summary[col_mapping["txn_amt"]],
                marker_color="steelblue"
            ))

            fig.update_layout(
                title="Txn Amount by Department",
                xaxis_title="Department",
                yaxis_title="Total Amount",
                margin=dict(l=40, r=40, t=40, b=40)
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("Transaction amount not available for summary.")

    return df, col_mapping, present

# ------------------------
# Streamlit UI
# ------------------------
def main():
    st.title("GL Attribute Validation & KPI Analyzer")
    st.write("Upload a GL file to validate attributes, map missing fields, and analyze KPIs.")

    uploaded_file = st.file_uploader("Upload GL file", type=["csv", "xlsx"])
    if uploaded_file is not None:
        df, col_mapping, present = analyze_gl(uploaded_file)

if __name__ == "__main__":
    main()
