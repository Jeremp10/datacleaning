"""
Phase 5: Cash Flow Forecasting with Prophet
"""
import pandas as pd
import numpy as np
from prophet import Prophet

def prepare_historical_data_for_prophet(daily_cash_flow):
    """
    Prepare historical revenue data for Prophet

    Prophet requires columns named 'ds' (date) and 'y' (value)
    """
    historical_revenue = daily_cash_flow[['date', 'net_cash_inflow']].copy()
    historical_revenue.columns = ['ds', 'y']

    # Remove any zeros or negatives for better modeling
    historical_revenue = historical_revenue[historical_revenue['y'] > 0]

    return historical_revenue

def train_revenue_forecast_model(historical_revenue):
    """
    Train Prophet model on historical revenue

    Configured for e-commerce seasonality patterns:
    - Yearly seasonality: Q4 holiday spike
    - Weekly seasonality: Weekend patterns
    """
    model = Prophet(
        yearly_seasonality=True,     # Capture Q4 seasonality
        weekly_seasonality=True,      # Capture day-of-week patterns
        daily_seasonality=False,      # Not needed for daily aggregates
        seasonality_mode='multiplicative',  # Better for revenue (% changes)
        changepoint_prior_scale=0.05,  # Conservative (less overfitting)
        seasonality_prior_scale=10.0,  # Add this - controls seasonality strength
        interval_width=0.80
    )

    model.fit(historical_revenue)

    return model

def generate_revenue_forecast(model, forecast_months):
    """
    Generate future revenue forecast

    Returns DataFrame with forecasted revenue and confidence intervals
    """
    # Create future dates
    future = model.make_future_dataframe(periods=forecast_months * 30, freq='D')

    # Predict
    forecast = model.predict(future)

    # Clip negative predictions (revenue can't be negative)
    forecast['yhat'] = forecast['yhat'].clip(lower=0)
    forecast['yhat_lower'] = forecast['yhat_lower'].clip(lower=0)
    forecast['yhat_upper'] = forecast['yhat_upper'].clip(lower=0)

    return forecast

def apply_cash_flow_model_to_forecast(
    forecast_revenue,
    cogs_pct,
    marketing_pct,
    platform_fee_pct,
    processing_fee_pct,
    avg_daily_shipping,
    monthly_fixed_costs
):
    """
    Apply cost structure to forecasted revenue to get net cash flow forecast

    Uses same assumptions as historical model
    """
    forecast_df = pd.DataFrame()
    forecast_df['date'] = forecast_revenue['ds']
    forecast_df['forecasted_revenue'] = forecast_revenue['yhat']
    forecast_df['revenue_lower'] = forecast_revenue['yhat_lower']
    forecast_df['revenue_upper'] = forecast_revenue['yhat_upper']

    # Apply cost assumptions (same as historical)
    forecast_df['cogs'] = forecast_df['forecasted_revenue'] * cogs_pct
    forecast_df['marketing'] = forecast_df['forecasted_revenue'] * marketing_pct
    forecast_df['platform_fees'] = forecast_df['forecasted_revenue'] * platform_fee_pct
    forecast_df['processing_fees'] = forecast_df['forecasted_revenue'] * processing_fee_pct
    forecast_df['shipping'] = avg_daily_shipping  # Use historical average
    forecast_df['fixed_costs'] = monthly_fixed_costs / 30

    # Total outflows
    forecast_df['total_outflows'] = (
        forecast_df['cogs'] +
        forecast_df['marketing'] +
        forecast_df['platform_fees'] +
        forecast_df['processing_fees'] +
        forecast_df['shipping'] +
        forecast_df['fixed_costs']
    )

    # Net cash flow
    forecast_df['net_cash_flow'] = forecast_df['forecasted_revenue'] - forecast_df['total_outflows']

    # Best/worst case scenarios
    forecast_df['net_cash_flow_best'] = forecast_df['revenue_upper'] - forecast_df['total_outflows']
    forecast_df['net_cash_flow_worst'] = forecast_df['revenue_lower'] - forecast_df['total_outflows']

    return forecast_df

def extend_running_balance(daily_cash_flow, forecast_df, current_balance):
    """
    Project running cash balance into the future

    Parameters:
    - daily_cash_flow: Historical cash flow
    - forecast_df: Forecasted cash flow
    - current_balance: Last historical balance

    Returns:
    - Extended DataFrame with forecasted running balance
    """
    # Start from current balance
    forecast_df['running_balance'] = current_balance + forecast_df['net_cash_flow'].cumsum()
    forecast_df['running_balance_best'] = current_balance + forecast_df['net_cash_flow_best'].cumsum()
    forecast_df['running_balance_worst'] = current_balance + forecast_df['net_cash_flow_worst'].cumsum()

    # Flag risk periods
    forecast_df['cash_status'] = 'healthy'
    forecast_df.loc[forecast_df['running_balance'] < 100000, 'cash_status'] = 'warning'
    forecast_df.loc[forecast_df['running_balance'] < 50000, 'cash_status'] = 'critical'
    forecast_df.loc[forecast_df['running_balance'] < 0, 'cash_status'] = 'insolvent'

    return forecast_df

def calculate_forecast_metrics(forecast_df):
    """Calculate summary metrics from forecast"""

    # Find insolvency date (if any)
    insolvent = forecast_df[forecast_df['running_balance'] < 0]
    insolvency_date = insolvent['date'].min() if len(insolvent) > 0 else None

    # Average monthly burn
    total_net_flow = forecast_df['net_cash_flow'].sum()
    months = len(forecast_df) / 30
    avg_monthly_burn = total_net_flow / months if months > 0 else 0

    # Ending balance
    ending_balance = forecast_df['running_balance'].iloc[-1]

    # Days until insolvency
    if insolvency_date:
        days_to_insolvency = (insolvency_date - forecast_df['date'].min()).days
    else:
        days_to_insolvency = None

    metrics = {
        'insolvency_date': insolvency_date,
        'days_to_insolvency': days_to_insolvency,
        'avg_monthly_burn': avg_monthly_burn,
        'ending_balance': ending_balance,
        'ending_balance_best': forecast_df['running_balance_best'].iloc[-1],
        'ending_balance_worst': forecast_df['running_balance_worst'].iloc[-1]
    }

    return metrics
