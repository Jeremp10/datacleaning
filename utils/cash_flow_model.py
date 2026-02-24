"""
Phase 4: Cash Flow Model & Analysis
"""
import pandas as pd
import numpy as np

def build_daily_cash_flow(cash_flow_revenue, cash_outflows):
    """Combine inflows and outflows into complete cash flow statement"""

    daily_cash_flow = cash_flow_revenue[['date', 'net_cash_inflow']].merge(
        cash_outflows[[
            'date', 'inventory_payment', 'shipping_cost',
            'processing_fee', 'marketing_expense',
            'platform_fee', 'fixed_costs', 'total_outflows'
        ]],
        on='date',
        how='outer'
    ).fillna(0)

    # Sort and calculate net flow
    daily_cash_flow = daily_cash_flow.sort_values('date').reset_index(drop=True)
    daily_cash_flow['net_daily_cash_flow'] = (
        daily_cash_flow['net_cash_inflow'] -
        daily_cash_flow['total_outflows']
    )

    return daily_cash_flow

def calculate_running_balance(daily_cash_flow, opening_balance):
    """Calculate cumulative cash balance"""

    daily_cash_flow['running_balance'] = (
        opening_balance +
        daily_cash_flow['net_daily_cash_flow'].cumsum()
    )

    return daily_cash_flow

def flag_risk_periods(daily_cash_flow, danger_threshold, critical_threshold):
    """Flag days by cash risk level"""

    daily_cash_flow['cash_status'] = 'healthy'
    daily_cash_flow.loc[daily_cash_flow['running_balance'] < danger_threshold, 'cash_status'] = 'warning'
    daily_cash_flow.loc[daily_cash_flow['running_balance'] < critical_threshold, 'cash_status'] = 'critical'
    daily_cash_flow.loc[daily_cash_flow['running_balance'] < 0, 'cash_status'] = 'insolvent'

    return daily_cash_flow

def calculate_monthly_summary(daily_cash_flow):
    """Aggregate to monthly summary"""

    daily_cash_flow['month'] = daily_cash_flow['date'].dt.to_period('M')

    monthly_summary = daily_cash_flow.groupby('month').agg(
        total_inflows=('net_cash_inflow', 'sum'),
        total_outflows=('total_outflows', 'sum'),
        net_cash_flow=('net_daily_cash_flow', 'sum'),
        closing_balance=('running_balance', 'last'),
        lowest_balance=('running_balance', 'min')
    ).reset_index()

    monthly_summary['month'] = monthly_summary['month'].dt.to_timestamp()

    return monthly_summary

def calculate_key_metrics(daily_cash_flow, monthly_summary, opening_balance):
    """Calculate summary metrics for dashboard"""

    total_revenue = daily_cash_flow['net_cash_inflow'].sum()
    total_outflows = daily_cash_flow['total_outflows'].sum()
    net_cash_flow = daily_cash_flow['net_daily_cash_flow'].sum()
    net_margin = (net_cash_flow / total_revenue) * 100 if total_revenue > 0 else 0

    current_balance = daily_cash_flow['running_balance'].iloc[-1]
    peak_balance = daily_cash_flow['running_balance'].max()
    lowest_balance = daily_cash_flow['running_balance'].min()

    # Risk days
    warning_days = len(daily_cash_flow[daily_cash_flow['cash_status'] == 'warning'])
    critical_days = len(daily_cash_flow[daily_cash_flow['cash_status'] == 'critical'])
    insolvent_days = len(daily_cash_flow[daily_cash_flow['cash_status'] == 'insolvent'])

    # Runway
    avg_monthly_burn = net_cash_flow / len(monthly_summary)
    runway_months = abs(current_balance / avg_monthly_burn) if avg_monthly_burn < 0 else float('inf')

    # Best/worst months
    best_month = monthly_summary.loc[monthly_summary['net_cash_flow'].idxmax()]
    worst_month = monthly_summary.loc[monthly_summary['net_cash_flow'].idxmin()]

    profitable_months = len(monthly_summary[monthly_summary['net_cash_flow'] > 0])

    metrics = {
        'total_revenue': total_revenue,
        'total_outflows': total_outflows,
        'net_cash_flow': net_cash_flow,
        'net_margin': net_margin,
        'opening_balance': opening_balance,
        'current_balance': current_balance,
        'peak_balance': peak_balance,
        'lowest_balance': lowest_balance,
        'warning_days': warning_days,
        'critical_days': critical_days,
        'insolvent_days': insolvent_days,
        'runway_months': runway_months,
        'best_month': best_month,
        'worst_month': worst_month,
        'profitable_months': profitable_months,
        'total_months': len(monthly_summary)
    }

    return metrics

def run_scenario_analysis(daily_cash_flow, opening_balance, scenarios):
    """
    Run what-if scenarios with different revenue multipliers

    Parameters:
    - daily_cash_flow: Base case cash flow
    - opening_balance: Starting cash
    - scenarios: Dict like {'Base Case': 1.0, 'Sales Drop 20%': 0.8}

    Returns:
    - Dict of scenario_name: running_balance_series
    """

    scenario_results = {}

    for scenario_name, multiplier in scenarios.items():
        scenario_inflows = daily_cash_flow['net_cash_inflow'] * multiplier
        scenario_net = scenario_inflows - daily_cash_flow['total_outflows']
        scenario_balance = opening_balance + scenario_net.cumsum()

        scenario_results[scenario_name] = {
            'dates': daily_cash_flow['date'],
            'balance': scenario_balance
        }

    return scenario_results
