"""
Phase 2: Revenue Timeline & Cash Timing
"""
import pandas as pd
import numpy as np

def calculate_cash_receipt_timing(orders_filtered, payments_filtered, payment_delays):
    """
    Model when cash actually hits bank account based on payment method delays

    Parameters:
    - orders_filtered: Filtered orders DataFrame
    - payments_filtered: Payments DataFrame
    - payment_delays: Dict mapping payment_type to delay in days

    Returns:
    - DataFrame with daily cash inflows
    """

    # Merge orders with payments
    orders_with_payments = orders_filtered.merge(
        payments_filtered,
        on='order_id',
        how='left'
    )

    # Map payment delay
    orders_with_payments['payment_delay_days'] = orders_with_payments['payment_type'].map(payment_delays)

    # Calculate cash receipt date
    orders_with_payments['cash_receipt_date'] = (
        pd.to_datetime(orders_with_payments['order_purchase_timestamp']) +
        pd.to_timedelta(orders_with_payments['payment_delay_days'], unit='D')
    )

    # Aggregate by cash receipt date
    daily_cash_inflows = orders_with_payments.groupby(
        orders_with_payments['cash_receipt_date'].dt.date
    )['payment_value'].sum().reset_index()

    daily_cash_inflows.columns = ['date', 'cash_inflow']
    daily_cash_inflows['date'] = pd.to_datetime(daily_cash_inflows['date'])

    return daily_cash_inflows

def calculate_refunds(orders, payments_filtered, start_date, end_date):
    """Calculate refunds from canceled orders"""

    canceled_orders = orders[
        (orders['order_purchase_timestamp'] >= start_date) &
        (orders['order_purchase_timestamp'] <= end_date) &
        (orders['order_status'] == 'canceled')
    ].copy()

    if len(canceled_orders) == 0:
        return pd.DataFrame(columns=['date', 'refund_outflow'])

    # Get payments for canceled orders
    canceled_payments = canceled_orders.merge(payments_filtered, on='order_id', how='inner')

    # Assume refunds 7 days after cancellation
    canceled_payments['refund_date'] = (
        pd.to_datetime(canceled_payments['order_purchase_timestamp']) +
        pd.Timedelta(days=7)
    ).dt.date

    daily_refunds = canceled_payments.groupby('refund_date')['payment_value'].sum().reset_index()
    daily_refunds.columns = ['date', 'refund_outflow']
    daily_refunds['date'] = pd.to_datetime(daily_refunds['date'])

    return daily_refunds

def build_cash_flow_revenue(daily_cash_inflows, daily_refunds, start_date, end_date):
    """Combine inflows and refunds into complete daily revenue cash flow"""

    # Create complete date range
    date_range = pd.date_range(start=start_date, end=end_date, freq='D')
    complete_dates = pd.DataFrame({'date': date_range})

    # Merge inflows and refunds
    cash_flow_revenue = complete_dates.merge(daily_cash_inflows, on='date', how='left')
    cash_flow_revenue = cash_flow_revenue.merge(daily_refunds, on='date', how='left')

    # Fill NaN with 0
    cash_flow_revenue = cash_flow_revenue.fillna(0)

    # Calculate net inflow
    cash_flow_revenue['net_cash_inflow'] = (
        cash_flow_revenue['cash_inflow'] - cash_flow_revenue['refund_outflow']
    )

    return cash_flow_revenue
