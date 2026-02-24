"""
E-Commerce Cash Flow Forecasting - Streamlit App
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sys
from pathlib import Path

# Add utils to path
sys.path.append(str(Path(__file__).parent))

from utils.data_loader import load_olist_data, filter_to_analysis_period, get_data_summary
from utils.cash_inflows import (
    calculate_cash_receipt_timing,
    calculate_refunds,
    build_cash_flow_revenue
)
from utils.cash_outflows import (
    calculate_cogs_and_inventory,
    calculate_variable_costs,
    calculate_shipping_costs,
    calculate_processing_fees,
    calculate_fixed_costs,
    consolidate_cash_outflows
)
from utils.cash_flow_model import (
    build_daily_cash_flow,
    calculate_running_balance,
    flag_risk_periods,
    calculate_monthly_summary,
    calculate_key_metrics,
    run_scenario_analysis
)

# Page config
st.set_page_config(
    page_title="Cash Flow Forecaster",
    layout="wide"
)

# Title
st.title(" E-Commerce Cash Flow Forecasting")
st.markdown("**Interactive analysis of marketplace cash flow dynamics**")

# Sidebar - Parameters
st.sidebar.header(" Model Parameters")

st.sidebar.subheader("Analysis Period")
start_date = st.sidebar.date_input("Start Date", value=pd.to_datetime("2017-07-01"))
end_date = st.sidebar.date_input("End Date", value=pd.to_datetime("2018-07-31"))

st.sidebar.subheader("Cost Assumptions")
cogs_pct = st.sidebar.slider("COGS %", 0.40, 0.80, 0.60, 0.01)
marketing_pct = st.sidebar.slider("Marketing %", 0.05, 0.25, 0.12, 0.01)
platform_fee_pct = st.sidebar.slider("Platform Fees %", 0.05, 0.15, 0.10, 0.01)
processing_fee_pct = st.sidebar.slider("Processing Fees %", 0.02, 0.05, 0.035, 0.005)
monthly_fixed_costs = st.sidebar.number_input(
    "Monthly Fixed Costs (BRL)",
    min_value=10000,
    max_value=100000,
    value=25000,
    step=5000
)

st.sidebar.subheader("Cash Position")
opening_balance = st.sidebar.number_input(
    "Opening Balance (BRL)",
    min_value=0,
    max_value=2000000,
    value=500000,
    step=50000
)

st.sidebar.subheader("Payment Timing (days)")
payment_delays = {
    'credit_card': st.sidebar.number_input("Credit Card", 1, 7, 3),
    'boleto': st.sidebar.number_input("Boleto", 1, 5, 1),
    'debit_card': st.sidebar.number_input("Debit Card", 1, 5, 2),
    'voucher': st.sidebar.number_input("Voucher", 1, 5, 2),
    'not_defined': st.sidebar.number_input("Not Defined", 1, 7, 3)
}

# Thresholds
danger_threshold = 100000
critical_threshold = 50000

# Load data
st.header(" Data Loading")

with st.spinner("Loading data..."):
    orders, payments, order_items = load_olist_data(
        'data_raw/olist_orders_dataset.csv',
        'data_raw/olist_order_payments_dataset.csv',
        'data_raw/olist_order_items_dataset.csv'
    )

if orders is None:
    st.error("Failed to load data. Please check file paths.")
    st.stop()

# Filter data
orders_filtered = filter_to_analysis_period(orders, str(start_date), str(end_date))
filtered_order_ids = orders_filtered['order_id'].unique()
payments_filtered = payments[payments['order_id'].isin(filtered_order_ids)].copy()

# Summary
summary = get_data_summary(orders_filtered, payments_filtered)

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total Orders", f"{summary['total_orders']:,}")
with col2:
    st.metric("Total Revenue", f"BRL {summary['total_revenue']:,.0f}")
with col3:
    st.metric("Avg Order Value", f"BRL {summary['avg_order_value']:,.0f}")
with col4:
    st.metric("Analysis Period", f"{(summary['date_range'][1] - summary['date_range'][0]).days} days")

# Run model
with st.spinner("Building cash flow model..."):

    # Phase 2: Cash Inflows
    daily_cash_inflows = calculate_cash_receipt_timing(
        orders_filtered,
        payments_filtered,
        payment_delays
    )

    daily_refunds = calculate_refunds(
        orders,
        payments_filtered,
        str(start_date),
        str(end_date)
    )

    cash_flow_revenue = build_cash_flow_revenue(
        daily_cash_inflows,
        daily_refunds,
        str(start_date),
        str(end_date)
    )

    # Phase 3: Cash Outflows
    orders_with_payments = orders_filtered.merge(payments_filtered, on='order_id', how='left')

    inventory_cash_outflows, order_revenue = calculate_cogs_and_inventory(
        orders_with_payments,
        cogs_pct,
        str(start_date),
        str(end_date)
    )

    marketing, platform_fees = calculate_variable_costs(
        order_revenue,
        marketing_pct,
        platform_fee_pct
    )

    daily_shipping = calculate_shipping_costs(orders_filtered, order_items)

    processing_fees = calculate_processing_fees(cash_flow_revenue, processing_fee_pct)

    fixed_costs_df = calculate_fixed_costs(
        str(start_date),
        str(end_date),
        monthly_fixed_costs
    )

    cash_outflows = consolidate_cash_outflows(
        inventory_cash_outflows,
        daily_shipping,
        processing_fees,
        marketing,
        platform_fees,
        fixed_costs_df,
        str(start_date),
        str(end_date)
    )

    # Phase 4: Cash Flow Model
    daily_cash_flow = build_daily_cash_flow(cash_flow_revenue, cash_outflows)
    daily_cash_flow = calculate_running_balance(daily_cash_flow, opening_balance)
    daily_cash_flow = flag_risk_periods(daily_cash_flow, danger_threshold, critical_threshold)
    monthly_summary = calculate_monthly_summary(daily_cash_flow)
    metrics = calculate_key_metrics(daily_cash_flow, monthly_summary, opening_balance)

st.success(" Model complete!")

# Display Key Metrics
st.header(" Key Metrics")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "Net Cash Flow",
        f"BRL {metrics['net_cash_flow']:,.0f}",
        delta=f"{metrics['net_margin']:.1f}%"
    )

with col2:
    st.metric(
        "Current Balance",
        f"BRL {metrics['current_balance']:,.0f}",
        delta=f"{((metrics['current_balance'] - opening_balance) / opening_balance * 100):.1f}%"
    )

with col3:
    st.metric(
        "Runway Remaining",
        f"{metrics['runway_months']:.1f} months" if metrics['runway_months'] != float('inf') else "Infinite"
    )

with col4:
    risk_days = metrics['warning_days'] + metrics['critical_days'] + metrics['insolvent_days']
    st.metric(
        "Days at Risk",
        f"{risk_days}",
        delta=f"{(risk_days / len(daily_cash_flow) * 100):.1f}%"
    )

# Main Dashboard
st.header(" Cash Flow Dashboard")

fig = make_subplots(
    rows=3, cols=1,
    subplot_titles=(
        'Daily Cash Inflows vs Outflows',
        'Running Cash Balance',
        'Monthly Net Cash Flow'
    ),
    vertical_spacing=0.1,
    row_heights=[0.33, 0.33, 0.33]
)

# Chart 1: Inflows vs Outflows
fig.add_trace(
    go.Scatter(
        x=daily_cash_flow['date'],
        y=daily_cash_flow['net_cash_inflow'],
        fill='tozeroy',
        name='Cash Inflows',
        line=dict(color='green'),
        fillcolor='rgba(0, 255, 0, 0.2)'
    ),
    row=1, col=1
)

fig.add_trace(
    go.Scatter(
        x=daily_cash_flow['date'],
        y=-daily_cash_flow['total_outflows'],
        fill='tozeroy',
        name='Cash Outflows',
        line=dict(color='red'),
        fillcolor='rgba(255, 0, 0, 0.2)'
    ),
    row=1, col=1
)

# Chart 2: Running Balance
fig.add_trace(
    go.Scatter(
        x=daily_cash_flow['date'],
        y=daily_cash_flow['running_balance'],
        name='Cash Balance',
        line=dict(color='blue', width=2)
    ),
    row=2, col=1
)

# Add threshold lines
fig.add_hline(
    y=danger_threshold,
    line_dash="dash",
    line_color="orange",
    row=2, col=1
)

fig.add_hline(
    y=critical_threshold,
    line_dash="dash",
    line_color="red",
    row=2, col=1
)

fig.add_hline(
    y=0,
    line_dash="solid",
    line_color="black",
    row=2, col=1
)

# Chart 3: Monthly bars
colors = ['green' if x >= 0 else 'red' for x in monthly_summary['net_cash_flow']]

fig.add_trace(
    go.Bar(
        x=monthly_summary['month'],
        y=monthly_summary['net_cash_flow'],
        name='Monthly Net Flow',
        marker_color=colors
    ),
    row=3, col=1
)

fig.update_layout(
    height=1400,
    showlegend=True,
    hovermode='x unified'
)

fig.update_xaxes(title_text="Date", row=3, col=1)
fig.update_yaxes(title_text="Amount (BRL)", row=1, col=1)
fig.update_yaxes(title_text="Balance (BRL)", row=2, col=1)
fig.update_yaxes(title_text="Net Cash Flow (BRL)", row=3, col=1)

st.plotly_chart(fig, use_container_width=True)

# Scenario Analysis
st.header(" Scenario Analysis")

scenarios = {
    'Base Case': 1.0,
    'Sales Drop 20%': 0.8,
    'Sales Growth 20%': 1.2,
    'Sales Drop 40%': 0.6
}

scenario_results = run_scenario_analysis(daily_cash_flow, opening_balance, scenarios)

fig_scenario = go.Figure()

colors_map = {
    'Base Case': 'blue',
    'Sales Drop 20%': 'orange',
    'Sales Growth 20%': 'green',
    'Sales Drop 40%': 'red'
}

for scenario_name, data in scenario_results.items():
    fig_scenario.add_trace(
        go.Scatter(
            x=data['dates'],
            y=data['balance'],
            name=scenario_name,
            line=dict(color=colors_map.get(scenario_name, 'gray'), width=2)
        )
    )

fig_scenario.add_hline(
    y=danger_threshold,
    line_dash="dash",
    line_color="black",
    annotation_text="Warning Threshold"
)

fig_scenario.add_hline(y=0, line_dash="solid", line_color="black")

fig_scenario.update_layout(
    title="Cash Balance Under Different Revenue Scenarios",
    xaxis_title="Date",
    yaxis_title="Cash Balance (BRL)",
    hovermode='x unified',
    height=500
)

st.plotly_chart(fig_scenario, use_container_width=True)

# Cost Breakdown
st.header(" Cost Breakdown")

cost_data = {
    'Category': ['Inventory', 'Marketing', 'Platform Fees', 'Shipping', 'Processing', 'Fixed Costs'],
    'Amount': [
        cash_outflows['inventory_payment'].sum(),
        cash_outflows['marketing_expense'].sum(),
        cash_outflows['platform_fee'].sum(),
        cash_outflows['shipping_cost'].sum(),
        cash_outflows['processing_fee'].sum(),
        cash_outflows['fixed_costs'].sum()
    ]
}

cost_df = pd.DataFrame(cost_data)
cost_df['Percentage'] = (cost_df['Amount'] / cost_df['Amount'].sum() * 100).round(1)

fig_pie = go.Figure(data=[
    go.Pie(
        labels=cost_df['Category'],
        values=cost_df['Amount'],
        textinfo='label+percent',
        hovertemplate='%{label}<br>BRL %{value:,.0f}<extra></extra>'
    )
])

fig_pie.update_layout(
    title="Total Cash Outflows by Category",
    height=500
)

col1, col2 = st.columns([1, 1])

with col1:
    st.plotly_chart(fig_pie, use_container_width=True)

with col2:
    st.dataframe(
        cost_df.style.format({
            'Amount': 'BRL {:,.0f}',
            'Percentage': '{:.1f}%'
        }),
        height=300
    )

# Download Data
st.header(" Download Results")

col1, col2 = st.columns(2)

with col1:
    csv_daily = daily_cash_flow.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="Download Daily Cash Flow",
        data=csv_daily,
        file_name="daily_cash_flow.csv",
        mime="text/csv"
    )

with col2:
    csv_monthly = monthly_summary.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="Download Monthly Summary",
        data=csv_monthly,
        file_name="monthly_summary.csv",
        mime="text/csv"
    )


st.header(" Future Cash Flow Forecast")

st.info(" Using Prophet to forecast future cash flow based on historical patterns (seasonality, trends)")

forecast_months = st.slider("Months to forecast ahead", 1, 12, 3)

if st.button("Generate Forecast"):

    with st.spinner("Training forecast model..."):

        # Import forecasting functions
        from utils.forecasting import (
            prepare_historical_data_for_prophet,
            train_revenue_forecast_model,
            generate_revenue_forecast,
            apply_cash_flow_model_to_forecast,
            extend_running_balance,
            calculate_forecast_metrics
        )

        # Prepare historical data
        historical_revenue = prepare_historical_data_for_prophet(daily_cash_flow)

        # Train model
        model = train_revenue_forecast_model(historical_revenue)

        # Generate forecast
        forecast_revenue = generate_revenue_forecast(model, forecast_months)

        # Calculate average daily shipping for forecast
        avg_daily_shipping = daily_shipping['shipping_cost'].mean()

        # Apply cash flow model to forecast
        forecast_df = apply_cash_flow_model_to_forecast(
            forecast_revenue,
            cogs_pct,
            marketing_pct,
            platform_fee_pct,
            processing_fee_pct,
            avg_daily_shipping,
            monthly_fixed_costs
        )

        # Project running balance
        current_balance = daily_cash_flow['running_balance'].iloc[-1]
        forecast_df = extend_running_balance(daily_cash_flow, forecast_df, current_balance)

        # Get only future dates (exclude historical)
        last_historical_date = daily_cash_flow['date'].max()
        future_only = forecast_df[forecast_df['date'] > last_historical_date].copy()

        # Calculate metrics
        forecast_metrics = calculate_forecast_metrics(future_only)

    st.success(" Forecast complete!")

    # Display forecast metrics
    st.subheader(" Forecast Summary")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Forecasted Ending Balance",
            f"BRL {forecast_metrics['ending_balance']:,.0f}"
        )

    with col2:
        st.metric(
            "Avg Monthly Burn",
            f"BRL {forecast_metrics['avg_monthly_burn']:,.0f}"
        )

    with col3:
        if forecast_metrics['insolvency_date']:
            st.metric(
                " Insolvency Date",
                forecast_metrics['insolvency_date'].strftime('%Y-%m-%d'),
                delta=f"{forecast_metrics['days_to_insolvency']} days"
            )
        else:
            st.metric(
                " Insolvency Risk",
                "None detected"
            )

    with col4:
        st.metric(
            "Forecast Confidence",
            f"±BRL {(forecast_metrics['ending_balance_best'] - forecast_metrics['ending_balance_worst'])/2:,.0f}"
        )

    # Visualization 1: Revenue Forecast
    st.subheader(" Revenue Forecast")

    fig_revenue_forecast = go.Figure()

    # Historical
    fig_revenue_forecast.add_trace(
        go.Scatter(
            x=historical_revenue['ds'],
            y=historical_revenue['y'],
            name='Historical Revenue',
            line=dict(color='blue')
        )
    )

    # Forecast
    fig_revenue_forecast.add_trace(
        go.Scatter(
            x=forecast_revenue['ds'],
            y=forecast_revenue['yhat'],
            name='Forecast',
            line=dict(color='orange', dash='dash')
        )
    )

    # Confidence interval
    fig_revenue_forecast.add_trace(
        go.Scatter(
            x=forecast_revenue['ds'],
            y=forecast_revenue['yhat_upper'],
            fill=None,
            mode='lines',
            line_color='rgba(200,200,200,0.3)',
            showlegend=False
        )
    )

    fig_revenue_forecast.add_trace(
        go.Scatter(
            x=forecast_revenue['ds'],
            y=forecast_revenue['yhat_lower'],
            fill='tonexty',
            mode='lines',
            fillcolor='rgba(200,200,200,0.2)',
            line_color='rgba(200,200,200,0.3)',
            name='Confidence Interval'
        )
    )

    fig_revenue_forecast.update_layout(
        title="Revenue Forecast with Confidence Intervals",
        xaxis_title="Date",
        yaxis_title="Revenue (BRL)",
        hovermode='x unified',
        height=500
    )

    st.plotly_chart(fig_revenue_forecast, use_container_width=True)

    # Visualization 2: Cash Balance Forecast
    st.subheader(" Cash Balance Forecast")

    fig_balance_forecast = go.Figure()

    # Historical balance
    fig_balance_forecast.add_trace(
        go.Scatter(
            x=daily_cash_flow['date'],
            y=daily_cash_flow['running_balance'],
            name='Historical Balance',
            line=dict(color='blue', width=2)
        )
    )

    # Forecasted balance (base case)
    fig_balance_forecast.add_trace(
        go.Scatter(
            x=future_only['date'],
            y=future_only['running_balance'],
            name='Forecast (Base Case)',
            line=dict(color='orange', width=2, dash='dash')
        )
    )

    # Best case
    fig_balance_forecast.add_trace(
        go.Scatter(
            x=future_only['date'],
            y=future_only['running_balance_best'],
            name='Best Case',
            line=dict(color='green', width=1, dash='dot')
        )
    )

    # Worst case
    fig_balance_forecast.add_trace(
        go.Scatter(
            x=future_only['date'],
            y=future_only['running_balance_worst'],
            name='Worst Case',
            line=dict(color='red', width=1, dash='dot')
        )
    )

    # Thresholds
    fig_balance_forecast.add_hline(
        y=danger_threshold,
        line_dash="dash",
        line_color="orange",
        annotation_text="Warning"
    )

    fig_balance_forecast.add_hline(
        y=0,
        line_dash="solid",
        line_color="black",
        annotation_text="Insolvency"
    )

    fig_balance_forecast.update_layout(
        title="Projected Cash Balance (Base/Best/Worst Case)",
        xaxis_title="Date",
        yaxis_title="Cash Balance (BRL)",
        hovermode='x unified',
        height=600
    )

    st.plotly_chart(fig_balance_forecast, use_container_width=True)

    # Business Recommendations Based on Forecast
    st.subheader(" Forecast-Based Recommendations")

    if forecast_metrics['insolvency_date']:
        st.error(f"""
         **CRITICAL: Insolvency projected within {forecast_metrics['days_to_insolvency']} days**

        **Immediate Actions Required:**
        1. Secure emergency financing of BRL {abs(forecast_metrics['ending_balance']):,.0f}+ within {forecast_metrics['days_to_insolvency']//7} weeks
        2. Implement aggressive cost reduction (target: BRL {abs(forecast_metrics['avg_monthly_burn']*0.3):,.0f}/month savings)
        3. Accelerate revenue collection (reduce payment delays, offer discounts for early payment)
        4. Consider bridge loan or line of credit
        """)

    elif forecast_metrics['ending_balance'] < 100000:
        st.warning(f"""
         **WARNING: Low cash balance projected**

        Ending balance: BRL {forecast_metrics['ending_balance']:,.0f}

        **Recommended Actions:**
        1. Line up credit facility (BRL 200-300K) as safety net
        2. Review and optimize cash conversion cycle
        3. Focus on high-margin products/services
        """)

    else:
        st.success(f"""
         **Cash position appears stable**

        Projected ending balance: BRL {forecast_metrics['ending_balance']:,.0f}

        **Growth Opportunities:**
        1. Consider strategic investments in inventory for upcoming peak season
        2. Test increased marketing spend in high-ROI channels
        3. Expand product lines with healthy margins
        """)

    # Download forecast
    st.subheader(" Download Forecast Data")

    csv_forecast = future_only.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="Download Forecast CSV",
        data=csv_forecast,
        file_name=f"cash_flow_forecast_{forecast_months}months.csv",
        mime="text/csv"
    )

# Footer
st.markdown("---")
st.markdown("""
**About this model:**
Built using Olist Brazilian E-commerce dataset. Assumptions include payment timing delays,
inventory purchase cycles, and operating expense estimates. In a real client engagement,
all assumptions would be validated against actual financial data.
""")
