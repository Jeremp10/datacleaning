import pandas as pd
import numpy as np


def clean_currency(value):
    """Remove currency symbols, commas, and convert to float"""
    if pd.isna(value):
        return None
    # Convert to string, remove $, commas, and whitespace
    cleaned = str(value).replace('$', '').replace(',', '').strip()
    # Handle 'NULL' or empty strings
    if cleaned in ['', 'NULL', 'null']:
        return None
    try:
        return float(cleaned)
    except:
        return None
