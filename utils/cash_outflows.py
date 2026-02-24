"""
Phase 3: Cost Structure Modeling
"""
import pandas as pd
import numpy as np

def calculate_cogs_and_inventory(orders_with_payments, cogs_percentage, start_date, end_date):
    """
    Calculate COGS and model inventory purchases

    Parameters:
    - orders_with_payments: Orders merged with payment data
    - cogs_percentage: COGS as % of revenue (e.g., 0.60)
    - start_date, end_date: Analysis period

    Returns:
    - inventory_cash_outflows: DataFrame with inventory payment dates and amounts
    """

    # Calculate daily revenue and COGS
    order_revenue = orders_with_payments.groupby(
        pd.to_datetime(orders_with_payments['order_purchase_timestamp']).dt.date
    )['payment_value'].sum().reset_index()
    order_revenue.columns = ['date', 'revenue']
    order_revenue['date'] = pd.to_datetime(order_revenue['date'])
    order_revenue['cogs'] = order_revenue['revenue'] * cogs_percentage

    # Calculate monthly COGS for bulk inventory purchases
    order_revenue['month'] = order_revenue['date'].dt.to_period('M')
    monthly_cogs = order_revenue.groupby('month')['cogs'].sum().reset_index()
    monthly_cogs['month'] = monthly_cogs['month'].dt.to_timestamp()

    # Model inventory purchases (15 days before month, Net 30 payment)
    inventory_purchases = []

    for idx, row in monthly_cogs.iterrows():
        purchase_date = row['month'] - pd.Timedelta(days=15)
        purchase_amount = row['cogs'] * 1.0  # Steady-state replenishment

        inventory_purchases.append({
            'date': purchase_date,
            'inventory_purchase': purchase_amount
        })

    inventory_df = pd.DataFrame(inventory_purchases)

    # Apply Net 30 payment terms
    inventory_df['payment_date'] = inventory_df['date'] + pd.Timedelta(days=30)

    # Cash outflow on payment date
    inventory_cash_outflows = inventory_df[['payment_date', 'inventory_purchase']].copy()
    inventory_cash_outflows.columns = ['date', 'inventory_payment']

    return inventory_cash_outflows, order_revenue

def calculate_variable_costs(order_revenue, marketing_pct, platform_fee_pct):
    """Calculate marketing and platform fees"""

    marketing = order_revenue[['date', 'revenue']].copy()
    marketing['marketing_expense'] = marketing['revenue'] * marketing_pct

    platform = order_revenue[['date', 'revenue']].copy()
    platform['platform_fee'] = platform['revenue'] * platform_fee_pct

    return marketing, platform

def calculate_shipping_costs(orders_filtered, order_items):
    """Calculate actual shipping costs from order items"""

    filtered_order_ids = orders_filtered['order_id'].unique()
    order_items_filtered = order_items[order_items['order_id'].isin(filtered_order_ids)].copy()

    shipping_per_order = order_items_filtered.groupby('order_id')['freight_value'].sum().reset_index()

    orders_shipping = orders_filtered[['order_id', 'order_purchase_timestamp']].merge(
        shipping_per_order, on='order_id', how='left'
    )
    orders_shipping['date'] = pd.to_datetime(orders_shipping['order_purchase_timestamp']).dt.date

    daily_shipping = orders_shipping.groupby('date')['freight_value'].sum().reset_index()
    daily_shipping.columns = ['date', 'shipping_cost']
    daily_shipping['date'] = pd.to_datetime(daily_shipping['date'])

    return daily_shipping

def calculate_processing_fees(cash_flow_revenue, processing_fee_pct):
    """Calculate payment processing fees"""

    processing = cash_flow_revenue[['date', 'cash_inflow']].copy()
    processing['processing_fee'] = processing['cash_inflow'] * processing_fee_pct

    return processing

def calculate_fixed_costs(start_date, end_date, monthly_fixed_costs):
    """Calculate daily fixed costs"""

    date_range = pd.date_range(start=start_date, end=end_date, freq='D')

    fixed_costs_df = pd.DataFrame({
        'date': date_range,
        'fixed_costs': monthly_fixed_costs / 30
    })

    return fixed_costs_df

def consolidate_cash_outflows(
    inventory_cash_outflows,
    daily_shipping,
    processing_fees,
    marketing,
    platform_fees,
    fixed_costs_df,
    start_date,
    end_date
):
    """Combine all cost components into single DataFrame"""

    # Create complete date range
    date_range = pd.date_range(start=start_date, end=end_date, freq='D')
    complete_dates = pd.DataFrame({'date': date_range})

    # Merge all components
    cash_outflows = complete_dates.copy()
    cash_outflows = cash_outflows.merge(inventory_cash_outflows, on='date', how='left')
    cash_outflows = cash_outflows.merge(daily_shipping[['date', 'shipping_cost']], on='date', how='left')
    cash_outflows = cash_outflows.merge(processing_fees[['date', 'processing_fee']], on='date', how='left')
    cash_outflows = cash_outflows.merge(marketing[['date', 'marketing_expense']], on='date', how='left')
    cash_outflows = cash_outflows.merge(platform_fees[['date', 'platform_fee']], on='date', how='left')
    cash_outflows = cash_outflows.merge(fixed_costs_df, on='date', how='left')

    # Fill NaN with 0
    cash_outflows = cash_outflows.fillna(0)

    # Calculate total
    cash_outflows['total_outflows'] = (
        cash_outflows['inventory_payment'] +
        cash_outflows['shipping_cost'] +
        cash_outflows['processing_fee'] +
        cash_outflows['marketing_expense'] +
        cash_outflows['platform_fee'] +
        cash_outflows['fixed_costs']
    )

    return cash_outflows
