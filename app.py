from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------
st.set_page_config(
    page_title="NovaRetail Customer Intelligence Dashboard",
    page_icon="📊",
    layout="wide",
)

# --------------------------------------------------
# VISUAL THEME
# --------------------------------------------------
COLORS = {
    "revenue": "#4C9BE8",
    "satisfaction": "#31B57B",
    "risk": "#E76F51",
    "opportunity": "#8E7CC3",
    "neutral": "#7A8A99",
}

st.markdown(
    """
    <style>
        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }

        [data-testid="stMetric"] {
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid rgba(255, 255, 255, 0.10);
            border-radius: 12px;
            padding: 18px 20px;
            min-height: 132px;
        }

        [data-testid="stMetricLabel"] {
            font-size: 0.95rem;
            font-weight: 600;
        }

        [data-testid="stMetricValue"] {
            font-size: 2rem;
        }

        .insight-card {
            background: rgba(255, 255, 255, 0.04);
            border-left: 4px solid #4C9BE8;
            border-radius: 8px;
            padding: 14px 16px;
            margin-bottom: 10px;
        }

        .insight-card strong {
            display: block;
            margin-bottom: 4px;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------
# CONSTANTS
# --------------------------------------------------
DATA_FILE = Path(__file__).parent / "NR_dataset.xlsx"
SHEET_NAME = "data"

REQUIRED_COLUMNS = [
    "label",
    "CustomerID",
    "TransactionID",
    "TransactionDate",
    "ProductCategory",
    "PurchaseAmount",
    "CustomerAgeGroup",
    "CustomerGender",
    "CustomerRegion",
    "CustomerSatisfaction",
    "RetailChannel",
]


# --------------------------------------------------
# DATA LOADING AND CLEANING
# --------------------------------------------------
@st.cache_data
def load_data(file_path: Path) -> pd.DataFrame:
    """Load and clean the NovaRetail Excel dataset."""
    try:
        data = pd.read_excel(file_path, sheet_name=SHEET_NAME)
    except FileNotFoundError:
        st.error(
            f"Dataset not found. Confirm that '{DATA_FILE.name}' is in the same "
            "GitHub repository and folder as app.py."
        )
        st.stop()
    except ValueError as exc:
        st.error(
            f"The worksheet '{SHEET_NAME}' could not be read. "
            f"Technical details: {exc}"
        )
        st.stop()
    except Exception as exc:
        st.error(f"The dataset could not be loaded. Technical details: {exc}")
        st.stop()

    data.columns = data.columns.astype(str).str.strip()
    data = data.drop(columns=["idx"], errors="ignore")

    missing_columns = [
        column for column in REQUIRED_COLUMNS if column not in data.columns
    ]
    if missing_columns:
        st.error(
            "The dataset is missing required columns: "
            + ", ".join(missing_columns)
        )
        st.write("Available columns:", list(data.columns))
        st.stop()

    data["TransactionDate"] = pd.to_datetime(
        data["TransactionDate"], errors="coerce"
    )
    data["PurchaseAmount"] = pd.to_numeric(
        data["PurchaseAmount"], errors="coerce"
    )
    data["CustomerSatisfaction"] = pd.to_numeric(
        data["CustomerSatisfaction"], errors="coerce"
    )

    data["label"] = data["label"].fillna("Unclassified").astype(str)
    data["CustomerID"] = data["CustomerID"].astype(str)
    data["TransactionID"] = data["TransactionID"].astype(str)

    essential_columns = [
        "TransactionDate",
        "PurchaseAmount",
        "CustomerSatisfaction",
    ]
    invalid_counts = data[essential_columns].isna().sum()

    if invalid_counts.any():
        st.warning(
            "Some rows contained invalid dates or numeric values and were removed."
        )
        data = data.dropna(subset=essential_columns)

    if data.empty:
        st.error("No usable records remain after cleaning the dataset.")
        st.stop()

    return data


df = load_data(DATA_FILE)


# --------------------------------------------------
# DASHBOARD HEADER
# --------------------------------------------------
st.title("NovaRetail Customer Intelligence Dashboard")
st.caption(
    "Analyze customer value, behavioral segments, satisfaction, and "
    "growth opportunities across NovaRetail."
)


# --------------------------------------------------
# SIDEBAR FILTERS
# --------------------------------------------------
st.sidebar.header("Dashboard Filters")

minimum_date = df["TransactionDate"].min().date()
maximum_date = df["TransactionDate"].max().date()

selected_dates = st.sidebar.date_input(
    "Transaction date range",
    value=(minimum_date, maximum_date),
    min_value=minimum_date,
    max_value=maximum_date,
)

if isinstance(selected_dates, tuple) and len(selected_dates) == 2:
    start_date, end_date = selected_dates
else:
    start_date = end_date = selected_dates

filter_definitions = {
    "Behavioral segment": "label",
    "Customer region": "CustomerRegion",
    "Product category": "ProductCategory",
    "Retail channel": "RetailChannel",
    "Customer gender": "CustomerGender",
    "Customer age group": "CustomerAgeGroup",
}

selected_filters = {}

for display_name, column_name in filter_definitions.items():
    available_values = sorted(
        df[column_name].dropna().astype(str).unique().tolist()
    )
    selected_filters[column_name] = st.sidebar.multiselect(
        display_name,
        options=available_values,
        default=available_values,
    )

filtered_df = df[
    (df["TransactionDate"].dt.date >= start_date)
    & (df["TransactionDate"].dt.date <= end_date)
].copy()

for column_name, selected_values in selected_filters.items():
    filtered_df = filtered_df[
        filtered_df[column_name].astype(str).isin(selected_values)
    ]

if filtered_df.empty:
    st.warning(
        "No records match the selected filters. Adjust one or more filters "
        "to continue."
    )
    st.stop()


# --------------------------------------------------
# KPI CALCULATIONS
# --------------------------------------------------
total_revenue = filtered_df["PurchaseAmount"].sum()
unique_customers = filtered_df["CustomerID"].nunique()
distinct_transactions = filtered_df["TransactionID"].nunique()

transaction_totals = (
    filtered_df.groupby("TransactionID", as_index=False)["PurchaseAmount"]
    .sum()
    .rename(columns={"PurchaseAmount": "TransactionRevenue"})
)

average_order_value = transaction_totals["TransactionRevenue"].mean()
purchase_frequency = (
    distinct_transactions / unique_customers if unique_customers else 0
)

category_revenue = (
    filtered_df.groupby("ProductCategory", as_index=False)["PurchaseAmount"]
    .sum()
    .sort_values("PurchaseAmount", ascending=False)
)

top_category = (
    category_revenue.iloc[0]["ProductCategory"]
    if not category_revenue.empty
    else "N/A"
)

st.subheader("Executive Overview")

kpi_1, kpi_2, kpi_3, kpi_4 = st.columns(4)

kpi_1.metric(
    "Purchase Frequency",
    f"{purchase_frequency:.2f}",
    help="Distinct transactions divided by unique customers.",
)
kpi_2.metric(
    "Average Order Value",
    f"${average_order_value:,.2f}",
    help="Average of transaction-level revenue totals.",
)
kpi_3.metric(
    "Total Revenue",
    f"${total_revenue:,.2f}",
    help=f"Generated by {unique_customers:,} unique customers.",
)
kpi_4.metric(
    "Top Product Category",
    str(top_category),
    help="Product category with the highest filtered revenue.",
)

st.caption(
    f"Filtered activity includes **{unique_customers:,} unique customers** "
    f"and **{distinct_transactions:,} distinct transactions**."
)


# --------------------------------------------------
# REUSABLE AGGREGATION HELPER
# --------------------------------------------------
def revenue_summary(column_name: str) -> pd.DataFrame:
    return (
        filtered_df.groupby(column_name, as_index=False)["PurchaseAmount"]
        .sum()
        .sort_values("PurchaseAmount", ascending=False)
    )


def format_chart(
    figure,
    *,
    height: int = 420,
    show_legend: bool = False,
):
    """Apply consistent formatting to Plotly charts."""
    figure.update_layout(
        height=height,
        margin=dict(l=20, r=20, t=65, b=30),
        showlegend=show_legend,
        hoverlabel=dict(namelength=-1),
    )
    figure.update_traces(
        marker_line_width=0,
        textposition="outside",
        cliponaxis=False,
        selector=dict(type="bar"),
    )
    return figure


# --------------------------------------------------
# CUSTOMER AND SEGMENT ANALYSIS
# --------------------------------------------------
st.divider()
st.subheader("Customer and Segment Analysis")

segment_revenue = revenue_summary("label")
segment_satisfaction = (
    filtered_df.groupby("label", as_index=False)["CustomerSatisfaction"]
    .mean()
    .sort_values("CustomerSatisfaction", ascending=False)
)

chart_1, chart_2 = st.columns(2)

with chart_1:
    fig_segment_revenue = px.bar(
        segment_revenue,
        x="label",
        y="PurchaseAmount",
        title="Revenue by Behavioral Segment",
        labels={
            "label": "Behavioral Segment",
            "PurchaseAmount": "Revenue",
        },
        text_auto=".2s",
        color_discrete_sequence=[COLORS["revenue"]],
    )
    fig_segment_revenue.update_layout(
        xaxis_title="Behavioral Segment",
        yaxis_title="Revenue ($)",
    )
    format_chart(fig_segment_revenue)
    st.plotly_chart(fig_segment_revenue, use_container_width=True)

with chart_2:
    fig_segment_satisfaction = px.bar(
        segment_satisfaction,
        x="label",
        y="CustomerSatisfaction",
        title="Average Satisfaction by Behavioral Segment",
        labels={
            "label": "Behavioral Segment",
            "CustomerSatisfaction": "Average Satisfaction",
        },
        text_auto=".2f",
        color_discrete_sequence=[COLORS["satisfaction"]],
    )
    fig_segment_satisfaction.update_layout(
        xaxis_title="Behavioral Segment",
        yaxis_title="Average Satisfaction",
        yaxis_range=[0, 5.5],
    )
    format_chart(fig_segment_satisfaction)
    st.plotly_chart(fig_segment_satisfaction, use_container_width=True)


# --------------------------------------------------
# TOP CUSTOMER ANALYSIS
# --------------------------------------------------
customer_revenue = (
    filtered_df.groupby("CustomerID", as_index=False)["PurchaseAmount"]
    .sum()
    .rename(columns={"PurchaseAmount": "TotalRevenue"})
    .sort_values("TotalRevenue", ascending=False)
)

top_customers = customer_revenue.head(10).sort_values(
    "TotalRevenue", ascending=True
).copy()
top_customers["CustomerLabel"] = "Customer " + top_customers["CustomerID"]

fig_top_customers = px.bar(
    top_customers,
    x="TotalRevenue",
    y="CustomerLabel",
    orientation="h",
    title="Top 10 Customers by Revenue",
    labels={
        "CustomerLabel": "Customer",
        "TotalRevenue": "Total Revenue",
    },
    text_auto="$.3s",
    color_discrete_sequence=[COLORS["opportunity"]],
)
fig_top_customers.update_layout(
    xaxis_title="Total Revenue ($)",
    yaxis_title="",
)
format_chart(fig_top_customers, height=440)
st.plotly_chart(fig_top_customers, use_container_width=True)


# --------------------------------------------------
# CUSTOMER-LEVEL SUMMARY TABLE
# --------------------------------------------------
customer_transaction_totals = (
    filtered_df.groupby(
        ["CustomerID", "TransactionID"], as_index=False
    )["PurchaseAmount"]
    .sum()
    .rename(columns={"PurchaseAmount": "OrderRevenue"})
)

customer_order_metrics = (
    customer_transaction_totals.groupby("CustomerID", as_index=False)
    .agg(
        DistinctTransactions=("TransactionID", "nunique"),
        AverageOrderValue=("OrderRevenue", "mean"),
    )
)

customer_summary = (
    filtered_df.groupby("CustomerID", as_index=False)
    .agg(
        TotalRevenue=("PurchaseAmount", "sum"),
        AverageSatisfaction=("CustomerSatisfaction", "mean"),
        PrimarySegment=(
            "label",
            lambda values: values.mode().iloc[0]
            if not values.mode().empty
            else "Unclassified",
        ),
    )
    .merge(customer_order_metrics, on="CustomerID", how="left")
    .sort_values("TotalRevenue", ascending=False)
)

customer_summary = customer_summary[
    [
        "CustomerID",
        "TotalRevenue",
        "DistinctTransactions",
        "AverageOrderValue",
        "AverageSatisfaction",
        "PrimarySegment",
    ]
]

st.markdown("#### Customer Value Table")
st.dataframe(
    customer_summary,
    use_container_width=True,
    hide_index=True,
    column_config={
        "CustomerID": st.column_config.TextColumn("Customer ID"),
        "TotalRevenue": st.column_config.NumberColumn(
            "Total Revenue", format="$%.2f"
        ),
        "DistinctTransactions": st.column_config.NumberColumn(
            "Transactions", format="%d"
        ),
        "AverageOrderValue": st.column_config.NumberColumn(
            "Average Order Value", format="$%.2f"
        ),
        "AverageSatisfaction": st.column_config.ProgressColumn(
            "Average Satisfaction",
            min_value=0,
            max_value=5,
            format="%.2f",
        ),
        "PrimarySegment": st.column_config.TextColumn("Primary Segment"),
    },
)


# --------------------------------------------------
# AT-RISK SEGMENT ANALYSIS
# --------------------------------------------------
segment_summary = (
    filtered_df.groupby("label", as_index=False)
    .agg(
        TotalRevenue=("PurchaseAmount", "sum"),
        UniqueCustomers=("CustomerID", "nunique"),
        DistinctTransactions=("TransactionID", "nunique"),
        AverageSatisfaction=("CustomerSatisfaction", "mean"),
    )
)

segment_summary["RevenuePerCustomer"] = (
    segment_summary["TotalRevenue"] / segment_summary["UniqueCustomers"]
)

median_satisfaction = segment_summary["AverageSatisfaction"].median()
median_revenue_per_customer = segment_summary[
    "RevenuePerCustomer"
].median()

segment_summary["RiskFlag"] = (
    (
        segment_summary["AverageSatisfaction"] < median_satisfaction
    )
    & (
        segment_summary["RevenuePerCustomer"]
        < median_revenue_per_customer
    )
).map(
    {
        True: "Potentially At Risk",
        False: "Monitor / Stable",
    }
)

segment_summary = segment_summary.sort_values(
    ["RiskFlag", "AverageSatisfaction", "RevenuePerCustomer"]
)

st.markdown("#### Segment Risk Assessment")
st.caption(
    "A segment is flagged when both its average satisfaction and its "
    "revenue per customer fall below the filtered segment medians."
)
st.dataframe(
    segment_summary,
    use_container_width=True,
    hide_index=True,
    column_config={
        "label": st.column_config.TextColumn("Behavioral Segment"),
        "TotalRevenue": st.column_config.NumberColumn(
            "Total Revenue", format="$%.2f"
        ),
        "UniqueCustomers": st.column_config.NumberColumn(
            "Unique Customers", format="%d"
        ),
        "DistinctTransactions": st.column_config.NumberColumn(
            "Transactions", format="%d"
        ),
        "AverageSatisfaction": st.column_config.ProgressColumn(
            "Average Satisfaction",
            min_value=0,
            max_value=5,
            format="%.2f",
        ),
        "RevenuePerCustomer": st.column_config.NumberColumn(
            "Revenue per Customer", format="$%.2f"
        ),
        "RiskFlag": st.column_config.TextColumn("Assessment"),
    },
)


# --------------------------------------------------
# DYNAMIC KEY INSIGHTS
# --------------------------------------------------
st.divider()
st.subheader("Key Insights")

top_segment_row = segment_revenue.iloc[0]
top_region_row = revenue_summary("CustomerRegion").iloc[0]
top_channel_row = revenue_summary("RetailChannel").iloc[0]
lowest_satisfaction_row = segment_satisfaction.iloc[-1]

top_segment_share = (
    top_segment_row["PurchaseAmount"] / total_revenue * 100
    if total_revenue
    else 0
)
top_region_share = (
    top_region_row["PurchaseAmount"] / total_revenue * 100
    if total_revenue
    else 0
)

insight_1, insight_2 = st.columns(2)

with insight_1:
    st.markdown(
        f"""
        <div class="insight-card">
            <strong>Leading customer segment</strong>
            {top_segment_row["label"]} generated
            ${top_segment_row["PurchaseAmount"]:,.2f}, representing
            {top_segment_share:.1f}% of filtered revenue.
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <div class="insight-card">
            <strong>Regional opportunity</strong>
            {top_region_row["CustomerRegion"]} is the strongest region at
            ${top_region_row["PurchaseAmount"]:,.2f}
            ({top_region_share:.1f}% of revenue).
        </div>
        """,
        unsafe_allow_html=True,
    )

with insight_2:
    st.markdown(
        f"""
        <div class="insight-card">
            <strong>Channel performance</strong>
            {top_channel_row["RetailChannel"]} is the leading retail channel,
            generating ${top_channel_row["PurchaseAmount"]:,.2f}.
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <div class="insight-card">
            <strong>Retention focus</strong>
            {lowest_satisfaction_row["label"]} has the lowest average
            satisfaction score at
            {lowest_satisfaction_row["CustomerSatisfaction"]:.2f} out of 5.
        </div>
        """,
        unsafe_allow_html=True,
    )


# --------------------------------------------------
# INVESTMENT OPPORTUNITY ANALYSIS
# --------------------------------------------------
st.divider()
st.subheader("Growth and Investment Opportunities")

region_revenue = revenue_summary("CustomerRegion")
channel_revenue = revenue_summary("RetailChannel")

growth_chart_1, growth_chart_2 = st.columns(2)

with growth_chart_1:
    fig_category = px.bar(
        category_revenue,
        x="ProductCategory",
        y="PurchaseAmount",
        title="Revenue by Product Category",
        labels={
            "ProductCategory": "Product Category",
            "PurchaseAmount": "Revenue",
        },
        text_auto=".2s",
    )
    fig_category.update_layout(
        xaxis_title="Product Category",
        yaxis_title="Revenue ($)",
    )
    st.plotly_chart(fig_category, use_container_width=True)

with growth_chart_2:
    fig_region = px.bar(
        region_revenue,
        x="CustomerRegion",
        y="PurchaseAmount",
        title="Revenue by Customer Region",
        labels={
            "CustomerRegion": "Customer Region",
            "PurchaseAmount": "Revenue",
        },
        text_auto=".2s",
        color_discrete_sequence=[COLORS["revenue"]],
    )
    fig_region.update_layout(
        xaxis_title="Customer Region",
        yaxis_title="Revenue ($)",
    )
    format_chart(fig_region, height=500)
    st.plotly_chart(fig_region, use_container_width=True)

fig_channel = px.bar(
    channel_revenue,
    x="RetailChannel",
    y="PurchaseAmount",
    title="Revenue by Retail Channel",
    labels={
        "RetailChannel": "Retail Channel",
        "PurchaseAmount": "Revenue",
    },
    text_auto=".2s",
    color_discrete_sequence=[COLORS["satisfaction"]],
)
fig_channel.update_layout(
    xaxis_title="Retail Channel",
    yaxis_title="Revenue ($)",
)
format_chart(fig_channel, height=400)
st.plotly_chart(fig_channel, use_container_width=True)


# --------------------------------------------------
# REVENUE TREND
# --------------------------------------------------
monthly_revenue = (
    filtered_df.assign(
        RevenueMonth=filtered_df["TransactionDate"].dt.to_period("M").dt.to_timestamp()
    )
    .groupby("RevenueMonth", as_index=False)["PurchaseAmount"]
    .sum()
)

fig_monthly = px.line(
    monthly_revenue,
    x="RevenueMonth",
    y="PurchaseAmount",
    markers=True,
    title="Monthly Revenue Trend",
    labels={
        "RevenueMonth": "Month",
        "PurchaseAmount": "Revenue",
    },
    color_discrete_sequence=[COLORS["revenue"]],
)
fig_monthly.update_layout(
    xaxis_title="Month",
    yaxis_title="Revenue ($)",
    xaxis_tickformat="%b %Y",
)
fig_monthly.update_traces(
    line_width=3,
    marker_size=9,
)
format_chart(fig_monthly, height=400)
st.plotly_chart(fig_monthly, use_container_width=True)


# --------------------------------------------------
# RAW DATA AND DOWNLOAD
# --------------------------------------------------
st.divider()

with st.expander("View Filtered Raw Data"):
    st.dataframe(
        filtered_df.sort_values("TransactionDate"),
        use_container_width=True,
        hide_index=True,
    )

csv_data = filtered_df.to_csv(index=False).encode("utf-8")

st.download_button(
    label="Download Filtered Data as CSV",
    data=csv_data,
    file_name="NovaRetail_filtered_data.csv",
    mime="text/csv",
)

st.caption(
    "Dashboard generated from NR_dataset.xlsx and designed for deployment "
    "through GitHub and Streamlit Community Cloud."
)
