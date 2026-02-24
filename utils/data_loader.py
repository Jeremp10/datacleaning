"""
Phase 1: Data Loading and Exploration
"""
import pandas as pd
import streamlit as st

@st.cache_data
def load_olist_data(orders_path, payments_path, items_path):
    """Load Olist datasets with caching"""
    try:
        orders = pd.read_csv(orders_path)
        payments = pd.read_csv(payments_path)
        order_items = pd.read_csv(items_path)
        return orders, payments, order_items
    except FileNotFoundError as e:
        st.error(f"File not found: {e}")
        return None, None, None

def filter_to_analysis_period(orders, start_date, end_date):
    """
    Filter orders to analysis period and valid statuses

    Parameters:
    - orders: DataFrame with order data
    - start_date: Start of analysis period (string 'YYYY-MM-DD')
    - end_date: End of analysis period (string 'YYYY-MM-DD')

    Returns:
    - Filtered orders DataFrame
    """
    orders['order_purchase_timestamp'] = pd.to_datetime(orders['order_purchase_timestamp'])

    # Keep only successful orders in date range
    orders_filtered = orders[
        (orders['order_purchase_timestamp'] >= start_date) &
        (orders['order_purchase_timestamp'] <= end_date) &
        (orders['order_status'].isin(['delivered', 'invoiced', 'shipped']))
    ].copy()

    return orders_filtered

def get_data_summary(orders_filtered, payments_filtered):
    """Generate summary statistics for display"""

    # Total orders
    total_orders = len(orders_filtered)

    # Date range
    date_min = orders_filtered['order_purchase_timestamp'].min()
    date_max = orders_filtered['order_purchase_timestamp'].max()

    # Total revenue
    order_totals = payments_filtered.groupby('order_id')['payment_value'].sum()
    total_revenue = order_totals.sum()

    # Average order value
    avg_order_value = order_totals.mean()

    # Payment method distribution
    payment_methods = payments_filtered['payment_type'].value_counts()

    summary = {
        'total_orders': total_orders,
        'date_range': (date_min, date_max),
        'total_revenue': total_revenue,
        'avg_order_value': avg_order_value,
        'payment_methods': payment_methods
    }

    return summary
