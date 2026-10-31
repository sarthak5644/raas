"""
Management, Commerce & Business Analytics Service (RaaS Stage-2, Component 4)
================================================================================
Same architecture as sarthak/engineering/engineering_analytics.py:
  - Individual analysis functions: fn(df, parameters) -> dict
  - MANAGEMENT_MODULES: catalog driving the frontend UI (module -> sub-tests -> inputs)
  - run_management_analysis(): dispatcher
  - suggest_management_analyses(): column-driven recommendations for a given file

Unlike Engineering (which cleanly splits data-driven vs parameter-only at the
MODULE level), Management mixes both WITHIN modules — e.g. Finance has both
Benford's Law (needs a column) and NPV (pure numbers). So "needs a file" is
tracked per ANALYSIS via DATA_DRIVEN_ANALYSES, not per module.

8 modules (matching RaaS Component 4's own category list):
    1. Finance & Accounting
    2. Marketing Analytics
    3. Sales & Revenue Analytics
    4. Operations & Supply Chain
    5. HR Analytics
    6. Project & Risk Management
    7. Business Intelligence
    8. Trade, Logistics & Value Chain
"""
import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import brentq
import statsmodels.api as sm


def _err(msg: str) -> dict:
    return {'error': msg}


def _numeric_series(df: pd.DataFrame, column: str) -> pd.Series:
    if df is None or column not in (df.columns if df is not None else []):
        return pd.Series(dtype=float)
    return pd.to_numeric(df[column], errors='coerce').dropna()


def _num(parameters: dict, key: str, default=None):
    val = parameters.get(key, default)
    if val is None:
        raise KeyError(key)
    return float(val)


# ══════════════════════════════════════════════════════════════════════════
# ANALYSES THAT READ THE UPLOADED FILE (everything else is parameter-only)
# ══════════════════════════════════════════════════════════════════════════
DATA_DRIVEN_ANALYSES = {
    'benford_first_digit_test',
    'price_elasticity_analysis',
    'consumer_behaviour_regression',
    'sales_trend_forecast',
    'rfm_analysis',
    'abc_inventory_analysis',
    'hr_attrition_model',
    'employee_productivity_summary',
    'trade_balance_growth',
    'export_concentration_index',
}

PREMIUM_ANALYSES = {
    'consumer_behaviour_regression',
    'hr_attrition_model',
    'rfm_analysis',
    'altman_z_score',
    'benford_first_digit_test',
    'critical_path_method',
    'sales_trend_forecast',
}


# ══════════════════════════════════════════════════════════════════════════
# 1. FINANCE & ACCOUNTING
# ══════════════════════════════════════════════════════════════════════════
def financial_ratios(df: pd.DataFrame, parameters: dict) -> dict:
    try:
        ca = _num(parameters, 'current_assets')
        cl = _num(parameters, 'current_liabilities')
        debt = _num(parameters, 'total_debt')
        equity = _num(parameters, 'equity')
        net_income = _num(parameters, 'net_income')
        total_assets = _num(parameters, 'total_assets')
        revenue = _num(parameters, 'revenue')

        return {
            'type': 'financial_ratios',
            'current_ratio': round(ca / cl, 4),
            'debt_equity_ratio': round(debt / equity, 4),
            'return_on_assets': round(net_income / total_assets, 4),
            'return_on_equity': round(net_income / equity, 4),
            'net_profit_margin': round(net_income / revenue, 4),
        }
    except (KeyError, ZeroDivisionError) as e:
        return _err(f'Missing or invalid input: {e}')


def npv_irr(df: pd.DataFrame, parameters: dict) -> dict:
    """parameters: cashflows (number_array, cashflows[0] typically negative), discount_rate (fraction, e.g. 0.1)"""
    try:
        cashflows = [float(x) for x in parameters.get('cashflows', [])]
        rate = float(parameters.get('discount_rate', 0.1))
        if len(cashflows) < 2:
            return _err('Provide at least 2 cashflows (period 0 outlay + at least one inflow)')

        npv = sum(cf / ((1 + rate) ** t) for t, cf in enumerate(cashflows))

        irr = None
        try:
            f = lambda r: sum(cf / ((1 + r) ** t) for t, cf in enumerate(cashflows))
            if f(-0.99) * f(10) < 0:
                irr = brentq(f, -0.99, 10)
        except Exception:
            irr = None

        return {
            'type': 'npv_irr',
            'discount_rate': rate,
            'npv': round(npv, 4),
            'irr': round(irr, 6) if irr is not None else None,
            'irr_note': None if irr is not None else 'IRR could not be found in the -99%..1000% range (cashflow signs may not change)',
        }
    except Exception as e:
        return _err(str(e))


def altman_z_score(df: pd.DataFrame, parameters: dict) -> dict:
    try:
        wc = _num(parameters, 'working_capital')
        ta = _num(parameters, 'total_assets')
        re = _num(parameters, 'retained_earnings')
        ebit = _num(parameters, 'ebit')
        mve = _num(parameters, 'market_value_equity')
        tl = _num(parameters, 'total_liabilities')
        sales = _num(parameters, 'sales')

        x1, x2, x3 = wc / ta, re / ta, ebit / ta
        x4, x5 = mve / tl, sales / ta
        z = 1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * x4 + 1.0 * x5

        zone = 'Safe Zone (low bankruptcy risk)' if z > 2.99 else \
               'Grey Zone (some risk)' if z > 1.81 else 'Distress Zone (high bankruptcy risk)'

        return {
            'type': 'altman_z_score',
            'z_score': round(z, 4),
            'x1_working_capital_to_assets': round(x1, 4),
            'x2_retained_earnings_to_assets': round(x2, 4),
            'x3_ebit_to_assets': round(x3, 4),
            'x4_equity_to_liabilities': round(x4, 4),
            'x5_sales_to_assets': round(x5, 4),
            'zone': zone,
        }
    except (KeyError, ZeroDivisionError) as e:
        return _err(f'Missing or invalid input: {e}')


def _leading_digit(x: float):
    x = abs(x)
    if x == 0:
        return None
    while x < 1:
        x *= 10
    while x >= 10:
        x /= 10
    return int(x)


def benford_first_digit_test(df: pd.DataFrame, parameters: dict) -> dict:
    """parameters: column (a numeric amounts column, e.g. transaction values)"""
    column = parameters.get('column')
    series = _numeric_series(df, column)
    series = series[series != 0]
    if len(series) < 30:
        return _err('Need at least 30 non-zero values for a meaningful Benford test')

    digits = series.apply(_leading_digit).dropna().astype(int)
    observed = digits.value_counts(normalize=True).reindex(range(1, 10), fill_value=0).sort_index()
    expected = pd.Series({d: np.log10(1 + 1 / d) for d in range(1, 10)})

    chi2, p_value = stats.chisquare(observed.values * len(digits), expected.values * len(digits))

    return {
        'type': 'benford_first_digit_test',
        'column': column,
        'n': int(len(digits)),
        'chi_square': round(float(chi2), 4),
        'p_value': round(float(p_value), 6),
        'interpretation': 'Distribution deviates significantly from Benford\'s Law — worth investigating' if p_value < 0.05
                          else 'Distribution is consistent with Benford\'s Law',
        'digit_distribution': [
            {'digit': d, 'observed_pct': round(float(observed[d]) * 100, 2), 'expected_pct': round(float(expected[d]) * 100, 2)}
            for d in range(1, 10)
        ],
    }


# ══════════════════════════════════════════════════════════════════════════
# 2. MARKETING ANALYTICS
# ══════════════════════════════════════════════════════════════════════════
def campaign_metrics(df: pd.DataFrame, parameters: dict) -> dict:
    try:
        impressions = _num(parameters, 'impressions')
        clicks = _num(parameters, 'clicks')
        conversions = _num(parameters, 'conversions')
        cost = _num(parameters, 'cost')
        revenue = _num(parameters, 'revenue')

        return {
            'type': 'campaign_metrics',
            'CTR': round(clicks / impressions, 4),
            'conversion_rate': round(conversions / clicks, 4),
            'CPC': round(cost / clicks, 4),
            'CPA': round(cost / conversions, 4),
            'ROI': round((revenue - cost) / cost, 4),
        }
    except (KeyError, ZeroDivisionError) as e:
        return _err(f'Missing or invalid input: {e}')


def ab_test(df: pd.DataFrame, parameters: dict) -> dict:
    try:
        from statsmodels.stats.proportion import proportions_ztest
        success_a = _num(parameters, 'success_a')
        n_a = _num(parameters, 'n_a')
        success_b = _num(parameters, 'success_b')
        n_b = _num(parameters, 'n_b')

        count = np.array([success_a, success_b])
        nobs = np.array([n_a, n_b])
        z_stat, p_value = proportions_ztest(count, nobs)

        return {
            'type': 'ab_test',
            'rate_a': round(success_a / n_a, 4),
            'rate_b': round(success_b / n_b, 4),
            'z_statistic': round(float(z_stat), 4),
            'p_value': round(float(p_value), 6),
            'significant': bool(p_value < 0.05),
            'interpretation': 'Statistically significant difference between A and B' if p_value < 0.05
                              else 'No statistically significant difference detected',
        }
    except (KeyError, ZeroDivisionError) as e:
        return _err(f'Missing or invalid input: {e}')


def price_elasticity_analysis(df: pd.DataFrame, parameters: dict) -> dict:
    """parameters: price_col, quantity_col (rows assumed time-ordered)"""
    price_col = parameters.get('price_col')
    qty_col = parameters.get('quantity_col')
    if df is None or price_col not in df.columns or qty_col not in df.columns:
        return _err('price_col and quantity_col must be valid columns')

    data = df[[price_col, qty_col]].apply(pd.to_numeric, errors='coerce').dropna()
    if len(data) < 3:
        return _err('Need at least 3 rows of price/quantity data')

    price_pct = data[price_col].pct_change()
    qty_pct = data[qty_col].pct_change()
    with np.errstate(divide='ignore', invalid='ignore'):
        elasticity = np.where(price_pct != 0, qty_pct / price_pct, np.nan)
    elasticity = pd.Series(elasticity).replace([np.inf, -np.inf], np.nan).dropna()

    if elasticity.empty:
        return _err('Could not compute elasticity — price does not change across rows')

    avg_e = float(elasticity.mean())
    interpretation = 'Elastic demand (sensitive to price)' if abs(avg_e) > 1 else 'Inelastic demand (less sensitive to price)'

    return {
        'type': 'price_elasticity_analysis',
        'n_periods': int(len(elasticity)),
        'average_elasticity': round(avg_e, 4),
        'median_elasticity': round(float(elasticity.median()), 4),
        'interpretation': interpretation,
        'sample_elasticity': [round(float(v), 4) for v in elasticity.tolist()[:20]],
    }


def consumer_behaviour_regression(df: pd.DataFrame, parameters: dict) -> dict:
    """parameters: dependent_var (column_numeric), independent_vars (column_list)"""
    dep = parameters.get('dependent_var')
    indep = parameters.get('independent_vars', [])
    if df is None or not dep or not indep or dep not in df.columns:
        return _err('dependent_var and independent_vars are required and must be valid columns')
    missing = [c for c in indep if c not in df.columns]
    if missing:
        return _err(f'Unknown independent_vars columns: {missing}')

    data = df[[dep] + indep].apply(pd.to_numeric, errors='coerce').dropna()
    if len(data) < len(indep) + 2:
        return _err('Not enough complete rows to fit this regression')

    X = sm.add_constant(data[indep])
    y = data[dep]
    try:
        model = sm.OLS(y, X, missing='drop').fit(cov_type='HC3')
    except Exception as e:
        return _err(f'Regression failed: {e}')

    coef_table = [{
        'variable': 'const' if name == 'const' else name,
        'coef': round(float(model.params[name]), 4),
        'std_err': round(float(model.bse[name]), 4),
        't_value': round(float(model.tvalues[name]), 4),
        'p_value': round(float(model.pvalues[name]), 6),
    } for name in model.params.index]

    return {
        'type': 'consumer_behaviour_regression',
        'dependent_var': dep,
        'r_squared': round(float(model.rsquared), 4),
        'adj_r_squared': round(float(model.rsquared_adj), 4),
        'n_obs': int(model.nobs),
        'table': coef_table,
    }


# ══════════════════════════════════════════════════════════════════════════
# 3. SALES & REVENUE ANALYTICS
# ══════════════════════════════════════════════════════════════════════════
def cagr_calc(df: pd.DataFrame, parameters: dict) -> dict:
    try:
        begin = _num(parameters, 'beginning_value')
        end = _num(parameters, 'ending_value')
        years = _num(parameters, 'years')
        if begin <= 0 or years <= 0:
            return _err('beginning_value and years must be > 0')
        cagr = (end / begin) ** (1 / years) - 1
        return {'type': 'cagr', 'beginning_value': begin, 'ending_value': end, 'years': years, 'cagr_pct': round(cagr * 100, 4)}
    except (KeyError, ZeroDivisionError) as e:
        return _err(f'Missing or invalid input: {e}')


def sales_trend_forecast(df: pd.DataFrame, parameters: dict) -> dict:
    """parameters: sales_col, future_periods (default 5). Uses row order as the time index."""
    sales_col = parameters.get('sales_col')
    future_periods = int(parameters.get('future_periods', 5))
    if df is None or sales_col not in df.columns:
        return _err('sales_col must be a valid column')

    series = pd.to_numeric(df[sales_col], errors='coerce').dropna().reset_index(drop=True)
    if len(series) < 4:
        return _err('Need at least 4 data points to fit a trend')

    t = np.arange(len(series))
    X = sm.add_constant(t)
    model = sm.OLS(series.values, X).fit()

    future_t = np.arange(len(series), len(series) + future_periods)
    future_X = sm.add_constant(future_t, has_constant='add')
    forecast = model.predict(future_X)

    history_curve = [{'period': int(i), 'value': round(float(v), 2), 'kind': 'actual'} for i, v in enumerate(series)]
    forecast_curve = [{'period': int(p), 'value': round(float(v), 2), 'kind': 'forecast'} for p, v in zip(future_t, forecast)]

    return {
        'type': 'sales_trend_forecast',
        'slope': round(float(model.params[1]), 4),
        'intercept': round(float(model.params[0]), 4),
        'r_squared': round(float(model.rsquared), 4),
        'forecast_periods': future_periods,
        'curve': history_curve + forecast_curve,
    }


def customer_lifetime_value(df: pd.DataFrame, parameters: dict) -> dict:
    try:
        apv = _num(parameters, 'avg_purchase_value')
        freq = _num(parameters, 'purchase_frequency')
        lifespan = _num(parameters, 'customer_lifespan')
        clv = apv * freq * lifespan
        return {'type': 'customer_lifetime_value', 'avg_purchase_value': apv, 'purchase_frequency': freq,
                'customer_lifespan': lifespan, 'clv': round(clv, 4)}
    except KeyError as e:
        return _err(f'Missing input: {e}')


def rfm_analysis(df: pd.DataFrame, parameters: dict) -> dict:
    """parameters: customer_col, date_col, amount_col"""
    customer_col = parameters.get('customer_col')
    date_col = parameters.get('date_col')
    amount_col = parameters.get('amount_col')
    needed = [customer_col, date_col, amount_col]
    if df is None or any(c not in df.columns for c in needed):
        return _err('customer_col, date_col and amount_col must all be valid columns')

    data = df[needed].copy()
    data[date_col] = pd.to_datetime(data[date_col], errors='coerce')
    data[amount_col] = pd.to_numeric(data[amount_col], errors='coerce')
    data = data.dropna()
    if data[customer_col].nunique() < 5:
        return _err('Need at least 5 distinct customers for meaningful RFM segmentation')

    reference_date = data[date_col].max() + pd.Timedelta(days=1)
    grouped = data.groupby(customer_col)
    rfm = pd.DataFrame({
        'recency': grouped[date_col].apply(lambda x: (reference_date - x.max()).days),
        'frequency': grouped[amount_col].count(),
        'monetary': grouped[amount_col].sum(),
    })

    try:
        rfm['R_score'] = pd.qcut(rfm['recency'], 5, labels=[5, 4, 3, 2, 1], duplicates='drop').astype(int)
        rfm['F_score'] = pd.qcut(rfm['frequency'].rank(method='first'), 5, labels=[1, 2, 3, 4, 5], duplicates='drop').astype(int)
        rfm['M_score'] = pd.qcut(rfm['monetary'], 5, labels=[1, 2, 3, 4, 5], duplicates='drop').astype(int)
    except Exception:
        # Falls back to plain ranks if there isn't enough variation for quintiles
        rfm['R_score'] = pd.qcut(rfm['recency'].rank(method='first'), min(5, rfm.shape[0]), labels=False, duplicates='drop') + 1
        rfm['F_score'] = pd.qcut(rfm['frequency'].rank(method='first'), min(5, rfm.shape[0]), labels=False, duplicates='drop') + 1
        rfm['M_score'] = pd.qcut(rfm['monetary'].rank(method='first'), min(5, rfm.shape[0]), labels=False, duplicates='drop') + 1

    rfm['RFM_score'] = rfm['R_score'] + rfm['F_score'] + rfm['M_score']
    top = rfm.sort_values('RFM_score', ascending=False).head(15).reset_index()

    return {
        'type': 'rfm_analysis',
        'n_customers': int(rfm.shape[0]),
        'avg_recency_days': round(float(rfm['recency'].mean()), 2),
        'avg_frequency': round(float(rfm['frequency'].mean()), 2),
        'avg_monetary': round(float(rfm['monetary'].mean()), 2),
        'top_customers': [{
            'customer': str(row[customer_col]),
            'recency': int(row['recency']), 'frequency': int(row['frequency']),
            'monetary': round(float(row['monetary']), 2), 'rfm_score': int(row['RFM_score']),
        } for _, row in top.iterrows()],
    }


# ══════════════════════════════════════════════════════════════════════════
# 4. OPERATIONS & SUPPLY CHAIN
# ══════════════════════════════════════════════════════════════════════════
def economic_order_quantity(df: pd.DataFrame, parameters: dict) -> dict:
    try:
        demand = _num(parameters, 'demand')
        ordering_cost = _num(parameters, 'ordering_cost')
        holding_cost = _num(parameters, 'holding_cost')
        if holding_cost <= 0:
            return _err('holding_cost must be > 0')
        eoq = np.sqrt((2 * demand * ordering_cost) / holding_cost)
        return {'type': 'economic_order_quantity', 'demand': demand, 'ordering_cost': ordering_cost,
                'holding_cost': holding_cost, 'eoq': round(float(eoq), 4)}
    except (KeyError, ZeroDivisionError) as e:
        return _err(f'Missing or invalid input: {e}')


def reorder_point(df: pd.DataFrame, parameters: dict) -> dict:
    try:
        avg_daily_demand = _num(parameters, 'avg_daily_demand')
        lead_time_days = _num(parameters, 'lead_time_days')
        safety_stock = _num(parameters, 'safety_stock')
        rop = avg_daily_demand * lead_time_days + safety_stock
        return {'type': 'reorder_point', 'avg_daily_demand': avg_daily_demand, 'lead_time_days': lead_time_days,
                'safety_stock': safety_stock, 'reorder_point': round(rop, 4)}
    except KeyError as e:
        return _err(f'Missing input: {e}')


def abc_inventory_analysis(df: pd.DataFrame, parameters: dict) -> dict:
    """parameters: item_col, annual_value_col"""
    item_col = parameters.get('item_col')
    value_col = parameters.get('annual_value_col')
    if df is None or item_col not in df.columns or value_col not in df.columns:
        return _err('item_col and annual_value_col must be valid columns')

    data = df[[item_col, value_col]].copy()
    data[value_col] = pd.to_numeric(data[value_col], errors='coerce')
    data = data.dropna().sort_values(value_col, ascending=False).reset_index(drop=True)
    if data.empty:
        return _err('No usable numeric data in annual_value_col')

    total = data[value_col].sum()
    data['cumulative_value'] = data[value_col].cumsum()
    data['cumulative_pct'] = data['cumulative_value'] / total * 100
    data['category'] = np.select(
        [data['cumulative_pct'] <= 80, data['cumulative_pct'] <= 95], ['A', 'B'], default='C')

    counts = data['category'].value_counts().to_dict()
    curve = [{'item_rank': i + 1, 'cumulative_pct': round(float(v), 2)}
              for i, v in enumerate(data['cumulative_pct'].tolist())]

    return {
        'type': 'abc_inventory_analysis',
        'total_items': int(len(data)),
        'category_A_count': int(counts.get('A', 0)),
        'category_B_count': int(counts.get('B', 0)),
        'category_C_count': int(counts.get('C', 0)),
        'top_items': [{'item': str(r[item_col]), 'value': round(float(r[value_col]), 2), 'category': r['category']}
                       for _, r in data.head(10).iterrows()],
        'curve': curve[:60],
    }


def supply_chain_kpis(df: pd.DataFrame, parameters: dict) -> dict:
    try:
        on_time = _num(parameters, 'on_time_full_orders')
        total_orders = _num(parameters, 'total_orders')
        cogs = _num(parameters, 'cogs')
        avg_inventory = _num(parameters, 'avg_inventory')
        otif = (on_time / total_orders) * 100
        turnover = cogs / avg_inventory
        return {'type': 'supply_chain_kpis', 'OTIF_pct': round(otif, 4), 'inventory_turnover': round(turnover, 4)}
    except (KeyError, ZeroDivisionError) as e:
        return _err(f'Missing or invalid input: {e}')


# ══════════════════════════════════════════════════════════════════════════
# 5. HR ANALYTICS
# ══════════════════════════════════════════════════════════════════════════
def hr_attrition_model(df: pd.DataFrame, parameters: dict) -> dict:
    """parameters: target_col (binary 0/1 or Yes/No), feature_cols (column_list, numeric)"""
    target_col = parameters.get('target_col')
    feature_cols = parameters.get('feature_cols', [])
    if df is None or not target_col or target_col not in df.columns or not feature_cols:
        return _err('target_col and feature_cols are required and must be valid columns')
    missing = [c for c in feature_cols if c not in df.columns]
    if missing:
        return _err(f'Unknown feature_cols columns: {missing}')

    data = df[[target_col] + feature_cols].copy()
    if not pd.api.types.is_numeric_dtype(data[target_col]):
        data[target_col] = data[target_col].astype(str).str.strip().str.lower().map(
            {'yes': 1, 'no': 0, 'true': 1, 'false': 0, '1': 1, '0': 0})
    data[feature_cols] = data[feature_cols].apply(pd.to_numeric, errors='coerce')
    data = data.dropna()
    if data.empty or data[target_col].nunique() < 2:
        return _err('Not enough valid rows, or target_col is not binary after cleaning')

    X = sm.add_constant(data[feature_cols])
    y = data[target_col].astype(int)
    try:
        model = sm.Logit(y, X).fit(disp=0)
    except Exception as e:
        return _err(f'Logistic regression failed to converge: {e}')

    coef_table = [{
        'variable': name,
        'coef': round(float(model.params[name]), 4),
        'odds_ratio': round(float(np.exp(model.params[name])), 4),
        'p_value': round(float(model.pvalues[name]), 6),
    } for name in model.params.index]

    preds = (model.predict(X) >= 0.5).astype(int)
    accuracy = float((preds == y).mean())

    return {
        'type': 'hr_attrition_model',
        'n_obs': int(model.nobs),
        'pseudo_r_squared': round(float(model.prsquared), 4),
        'accuracy': round(accuracy, 4),
        'table': coef_table,
    }


def employee_productivity_summary(df: pd.DataFrame, parameters: dict) -> dict:
    """parameters: output_col, input_col"""
    output_col = parameters.get('output_col')
    input_col = parameters.get('input_col')
    if df is None or output_col not in df.columns or input_col not in df.columns:
        return _err('output_col and input_col must be valid columns')

    data = df[[output_col, input_col]].apply(pd.to_numeric, errors='coerce').dropna()
    data = data[data[input_col] != 0]
    if data.empty:
        return _err('No valid rows (input_col must be non-zero)')

    productivity = data[output_col] / data[input_col]
    hist, edges = np.histogram(productivity, bins=15)
    histogram = [{'bin_start': round(float(edges[i]), 3), 'bin_end': round(float(edges[i + 1]), 3), 'count': int(hist[i])}
                 for i in range(len(hist))]

    return {
        'type': 'employee_productivity_summary',
        'n': int(len(productivity)),
        'mean_productivity': round(float(productivity.mean()), 4),
        'median_productivity': round(float(productivity.median()), 4),
        'min_productivity': round(float(productivity.min()), 4),
        'max_productivity': round(float(productivity.max()), 4),
        'histogram': histogram,
    }


# ══════════════════════════════════════════════════════════════════════════
# 6. PROJECT & RISK MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════
def pert_expected_time(df: pd.DataFrame, parameters: dict) -> dict:
    try:
        o = _num(parameters, 'optimistic')
        m = _num(parameters, 'most_likely')
        p = _num(parameters, 'pessimistic')
        te = (o + 4 * m + p) / 6
        variance = ((p - o) / 6) ** 2
        return {'type': 'pert_expected_time', 'optimistic': o, 'most_likely': m, 'pessimistic': p,
                'expected_time': round(te, 4), 'variance': round(variance, 4), 'std_dev': round(float(np.sqrt(variance)), 4)}
    except KeyError as e:
        return _err(f'Missing input: {e}')


def critical_path_method(df: pd.DataFrame, parameters: dict) -> dict:
    """parameters: tasks -> [{name, duration, dependencies:[...]}, ...]"""
    tasks_list = parameters.get('tasks', [])
    if not tasks_list:
        return _err('tasks is required')

    tasks = {}
    for t in tasks_list:
        name = t.get('name')
        if not name:
            continue
        tasks[name] = {'duration': float(t.get('duration', 0)), 'dependencies': t.get('dependencies', [])}

    unknown_deps = {d for t in tasks.values() for d in t['dependencies'] if d not in tasks}
    if unknown_deps:
        return _err(f'Unknown dependency task name(s): {sorted(unknown_deps)}')

    earliest_finish = {}
    visiting = set()

    def compute_finish(task):
        if task in earliest_finish:
            return earliest_finish[task]
        if task in visiting:
            raise ValueError(f'Circular dependency detected involving "{task}"')
        visiting.add(task)
        deps = tasks[task]['dependencies']
        duration = tasks[task]['duration']
        earliest_finish[task] = duration if not deps else duration + max(compute_finish(d) for d in deps)
        visiting.discard(task)
        return earliest_finish[task]

    try:
        for task in tasks:
            compute_finish(task)
    except ValueError as e:
        return _err(str(e))

    project_duration = max(earliest_finish.values())
    critical_tasks = [t for t, f in earliest_finish.items() if f == project_duration]

    return {
        'type': 'critical_path_method',
        'project_duration': round(project_duration, 4),
        'critical_tasks': critical_tasks,
        'task_finish_times': [{'task': t, 'earliest_finish': round(f, 4), 'is_critical': t in critical_tasks}
                                for t, f in earliest_finish.items()],
    }


def expected_monetary_value(df: pd.DataFrame, parameters: dict) -> dict:
    try:
        probs = [float(x) for x in parameters.get('probabilities', [])]
        impacts = [float(x) for x in parameters.get('impacts', [])]
        if not probs or len(probs) != len(impacts):
            return _err('probabilities and impacts must be non-empty and the same length')
        emv = float(np.sum(np.array(probs) * np.array(impacts)))
        breakdown = [{'scenario': i + 1, 'probability': p, 'impact': imp, 'contribution': round(p * imp, 4)}
                     for i, (p, imp) in enumerate(zip(probs, impacts))]
        return {'type': 'expected_monetary_value', 'emv': round(emv, 4), 'breakdown': breakdown}
    except Exception as e:
        return _err(str(e))


def scenario_analysis(df: pd.DataFrame, parameters: dict) -> dict:
    try:
        base_value = _num(parameters, 'base_value')
        scenarios = parameters.get('scenarios', [])
        if not scenarios:
            return _err('scenarios is required')
        results = [{'scenario': s['name'], 'change_pct': round(float(s['change']) * 100, 2),
                    'projected_value': round(base_value * (1 + float(s['change'])), 4)} for s in scenarios]
        return {'type': 'scenario_analysis', 'base_value': base_value, 'scenarios': results}
    except (KeyError, ValueError) as e:
        return _err(f'Missing or invalid input: {e}')


# ══════════════════════════════════════════════════════════════════════════
# 7. BUSINESS INTELLIGENCE
# ══════════════════════════════════════════════════════════════════════════
def business_kpi_summary(df: pd.DataFrame, parameters: dict) -> dict:
    try:
        revenue = _num(parameters, 'revenue')
        cost = _num(parameters, 'cost')
        customers = _num(parameters, 'customers')
        orders = _num(parameters, 'orders')
        profit = revenue - cost
        return {
            'type': 'business_kpi_summary',
            'revenue': revenue, 'cost': cost, 'profit': round(profit, 4),
            'profit_margin_pct': round(profit / revenue * 100, 4) if revenue else None,
            'average_order_value': round(revenue / orders, 4) if orders else None,
            'revenue_per_customer': round(revenue / customers, 4) if customers else None,
        }
    except KeyError as e:
        return _err(f'Missing input: {e}')


# ══════════════════════════════════════════════════════════════════════════
# 8. TRADE, LOGISTICS & VALUE CHAIN
# ══════════════════════════════════════════════════════════════════════════
def trade_balance_growth(df: pd.DataFrame, parameters: dict) -> dict:
    """parameters: exports_col, imports_col (rows assumed time-ordered)"""
    exports_col = parameters.get('exports_col')
    imports_col = parameters.get('imports_col')
    if df is None or exports_col not in df.columns or imports_col not in df.columns:
        return _err('exports_col and imports_col must be valid columns')

    data = df[[exports_col, imports_col]].apply(pd.to_numeric, errors='coerce').dropna().reset_index(drop=True)
    if data.empty:
        return _err('No usable numeric data in the selected columns')

    balance = data[exports_col] - data[imports_col]
    export_growth = data[exports_col].pct_change() * 100
    import_growth = data[imports_col].pct_change() * 100

    curve = [{'period': i, 'exports': round(float(e), 2), 'imports': round(float(m), 2), 'balance': round(float(b), 2)}
             for i, (e, m, b) in enumerate(zip(data[exports_col], data[imports_col], balance))]

    return {
        'type': 'trade_balance_growth',
        'n_periods': int(len(data)),
        'avg_trade_balance': round(float(balance.mean()), 2),
        'avg_export_growth_pct': round(float(export_growth.mean()), 4),
        'avg_import_growth_pct': round(float(import_growth.mean()), 4),
        'curve': curve[:100],
    }


def export_concentration_index(df: pd.DataFrame, parameters: dict) -> dict:
    """parameters: export_value_col — HHI across whatever rows represent (products/markets/etc.)"""
    col = parameters.get('export_value_col')
    series = _numeric_series(df, col)
    series = series[series > 0]
    if series.empty:
        return _err(f"Column '{col}' has no usable positive numeric data")

    shares = series / series.sum()
    hhi = float((shares ** 2).sum())
    diversification = 1 - hhi

    concentration = 'Highly concentrated (few dominant items)' if hhi > 0.25 else \
                     'Moderately concentrated' if hhi > 0.15 else 'Well diversified'

    return {
        'type': 'export_concentration_index',
        'n_items': int(len(series)),
        'hhi': round(hhi, 4),
        'diversification_index': round(diversification, 4),
        'interpretation': concentration,
    }


def landed_cost(df: pd.DataFrame, parameters: dict) -> dict:
    try:
        cif = _num(parameters, 'cif_price')
        duty = _num(parameters, 'duty')
        freight = _num(parameters, 'freight')
        insurance = _num(parameters, 'insurance')
        handling = _num(parameters, 'handling')
        compliance = _num(parameters, 'compliance_cost', 0)
        total = cif + duty + freight + insurance + handling + compliance
        return {'type': 'landed_cost', 'cif_price': cif, 'duty': duty, 'freight': freight,
                'insurance': insurance, 'handling': handling, 'compliance_cost': compliance,
                'total_landed_cost': round(total, 4)}
    except KeyError as e:
        return _err(f'Missing input: {e}')


def logistics_cost_share(df: pd.DataFrame, parameters: dict) -> dict:
    try:
        transport = _num(parameters, 'transport')
        storage = _num(parameters, 'storage')
        inventory = _num(parameters, 'inventory')
        insurance = _num(parameters, 'insurance')
        handling = _num(parameters, 'handling', 0)
        sales = _num(parameters, 'sales')
        total = transport + storage + inventory + insurance + handling
        share = (total / sales) * 100 if sales else None
        return {'type': 'logistics_cost_share', 'total_logistics_cost': round(total, 4),
                'logistics_cost_share_pct': round(share, 4) if share is not None else None}
    except KeyError as e:
        return _err(f'Missing input: {e}')


# ══════════════════════════════════════════════════════════════════════════
# CATALOG (drives the frontend UI)
# ══════════════════════════════════════════════════════════════════════════
_MANAGEMENT_MODULES = {
    "Finance": {
        "label": "Finance & Accounting",
        "description": "Financial ratios, NPV/IRR, Altman Z-Score bankruptcy risk, Benford's Law fraud test",
        "items": [
            {"key": "fin_1", "analysis_id": "financial_ratios", "label": "Financial Ratios", "number": "1.1",
             "premium": False, "needs_dataframe": False, "inputs": [
                {"name": "current_assets", "type": "number", "label": "Current Assets"},
                {"name": "current_liabilities", "type": "number", "label": "Current Liabilities"},
                {"name": "total_debt", "type": "number", "label": "Total Debt"},
                {"name": "equity", "type": "number", "label": "Shareholders' Equity"},
                {"name": "net_income", "type": "number", "label": "Net Income"},
                {"name": "total_assets", "type": "number", "label": "Total Assets"},
                {"name": "revenue", "type": "number", "label": "Revenue"},
             ]},
            {"key": "fin_2", "analysis_id": "npv_irr", "label": "NPV & IRR", "number": "1.2",
             "premium": False, "needs_dataframe": False, "inputs": [
                {"name": "cashflows", "type": "number_array", "label": "Cashflows (period 0, 1, 2… — e.g. -1000, 300, 400, 500)"},
                {"name": "discount_rate", "type": "number", "label": "Discount Rate (fraction, e.g. 0.1 for 10%)"},
             ]},
            {"key": "fin_3", "analysis_id": "altman_z_score", "label": "Altman Z-Score (Bankruptcy Risk)", "number": "1.3",
             "premium": True, "needs_dataframe": False, "inputs": [
                {"name": "working_capital", "type": "number", "label": "Working Capital"},
                {"name": "total_assets", "type": "number", "label": "Total Assets"},
                {"name": "retained_earnings", "type": "number", "label": "Retained Earnings"},
                {"name": "ebit", "type": "number", "label": "EBIT"},
                {"name": "market_value_equity", "type": "number", "label": "Market Value of Equity"},
                {"name": "total_liabilities", "type": "number", "label": "Total Liabilities"},
                {"name": "sales", "type": "number", "label": "Sales"},
             ]},
            {"key": "fin_4", "analysis_id": "benford_first_digit_test", "label": "Benford's Law Fraud Test", "number": "1.4",
             "premium": True, "needs_dataframe": True, "inputs": [
                {"name": "column", "type": "column_numeric", "label": "Transaction / Amount Column"},
             ]},
        ],
    },
    "Marketing": {
        "label": "Marketing Analytics",
        "description": "Campaign metrics, A/B testing, price elasticity, consumer behaviour regression",
        "items": [
            {"key": "mkt_1", "analysis_id": "campaign_metrics", "label": "Campaign Metrics", "number": "2.1",
             "premium": False, "needs_dataframe": False, "inputs": [
                {"name": "impressions", "type": "number", "label": "Impressions"},
                {"name": "clicks", "type": "number", "label": "Clicks"},
                {"name": "conversions", "type": "number", "label": "Conversions"},
                {"name": "cost", "type": "number", "label": "Cost"},
                {"name": "revenue", "type": "number", "label": "Revenue"},
             ]},
            {"key": "mkt_2", "analysis_id": "ab_test", "label": "A/B Testing", "number": "2.2",
             "premium": False, "needs_dataframe": False, "inputs": [
                {"name": "success_a", "type": "number", "label": "Successes — Variant A"},
                {"name": "n_a", "type": "number", "label": "Total Users — Variant A"},
                {"name": "success_b", "type": "number", "label": "Successes — Variant B"},
                {"name": "n_b", "type": "number", "label": "Total Users — Variant B"},
             ]},
            {"key": "mkt_3", "analysis_id": "price_elasticity_analysis", "label": "Price Elasticity of Demand", "number": "2.3",
             "premium": False, "needs_dataframe": True, "inputs": [
                {"name": "price_col", "type": "column_numeric", "label": "Price Column"},
                {"name": "quantity_col", "type": "column_numeric", "label": "Quantity Column"},
             ]},
            {"key": "mkt_4", "analysis_id": "consumer_behaviour_regression", "label": "Consumer Behaviour Regression", "number": "2.4",
             "premium": True, "needs_dataframe": True, "inputs": [
                {"name": "dependent_var", "type": "column_numeric", "label": "Dependent Variable (e.g. Purchase Intent)"},
                {"name": "independent_vars", "type": "column_list", "label": "Independent Variable Columns (comma-separated)"},
             ]},
        ],
    },
    "Sales": {
        "label": "Sales & Revenue Analytics",
        "description": "CAGR, sales trend forecasting, customer lifetime value, RFM segmentation",
        "items": [
            {"key": "sal_1", "analysis_id": "cagr_calc", "label": "CAGR", "number": "3.1",
             "premium": False, "needs_dataframe": False, "inputs": [
                {"name": "beginning_value", "type": "number", "label": "Beginning Value"},
                {"name": "ending_value", "type": "number", "label": "Ending Value"},
                {"name": "years", "type": "number", "label": "Number of Years"},
             ]},
            {"key": "sal_2", "analysis_id": "sales_trend_forecast", "label": "Sales Trend Forecast", "number": "3.2",
             "premium": True, "needs_dataframe": True, "inputs": [
                {"name": "sales_col", "type": "column_numeric", "label": "Sales Column (row order = time)"},
                {"name": "future_periods", "type": "number", "label": "Periods to Forecast", "required": False},
             ]},
            {"key": "sal_3", "analysis_id": "customer_lifetime_value", "label": "Customer Lifetime Value", "number": "3.3",
             "premium": False, "needs_dataframe": False, "inputs": [
                {"name": "avg_purchase_value", "type": "number", "label": "Average Purchase Value"},
                {"name": "purchase_frequency", "type": "number", "label": "Purchase Frequency (per period)"},
                {"name": "customer_lifespan", "type": "number", "label": "Customer Lifespan (periods)"},
             ]},
            {"key": "sal_4", "analysis_id": "rfm_analysis", "label": "RFM Analysis", "number": "3.4",
             "premium": True, "needs_dataframe": True, "inputs": [
                {"name": "customer_col", "type": "column_categorical", "label": "Customer ID Column"},
                {"name": "date_col", "type": "column_date", "label": "Transaction Date Column"},
                {"name": "amount_col", "type": "column_numeric", "label": "Amount Column"},
             ]},
        ],
    },
    "Operations": {
        "label": "Operations & Supply Chain",
        "description": "EOQ, reorder point, ABC inventory analysis, OTIF & inventory turnover",
        "items": [
            {"key": "ops_1", "analysis_id": "economic_order_quantity", "label": "Economic Order Quantity (EOQ)", "number": "4.1",
             "premium": False, "needs_dataframe": False, "inputs": [
                {"name": "demand", "type": "number", "label": "Annual Demand"},
                {"name": "ordering_cost", "type": "number", "label": "Ordering Cost per Order"},
                {"name": "holding_cost", "type": "number", "label": "Holding Cost per Unit"},
             ]},
            {"key": "ops_2", "analysis_id": "reorder_point", "label": "Reorder Point", "number": "4.2",
             "premium": False, "needs_dataframe": False, "inputs": [
                {"name": "avg_daily_demand", "type": "number", "label": "Average Daily Demand"},
                {"name": "lead_time_days", "type": "number", "label": "Lead Time (days)"},
                {"name": "safety_stock", "type": "number", "label": "Safety Stock"},
             ]},
            {"key": "ops_3", "analysis_id": "abc_inventory_analysis", "label": "ABC Inventory Analysis", "number": "4.3",
             "premium": False, "needs_dataframe": True, "inputs": [
                {"name": "item_col", "type": "column_categorical", "label": "Item / SKU Column"},
                {"name": "annual_value_col", "type": "column_numeric", "label": "Annual Value Column"},
             ]},
            {"key": "ops_4", "analysis_id": "supply_chain_kpis", "label": "OTIF & Inventory Turnover", "number": "4.4",
             "premium": False, "needs_dataframe": False, "inputs": [
                {"name": "on_time_full_orders", "type": "number", "label": "On-Time-In-Full Orders"},
                {"name": "total_orders", "type": "number", "label": "Total Orders"},
                {"name": "cogs", "type": "number", "label": "Cost of Goods Sold (COGS)"},
                {"name": "avg_inventory", "type": "number", "label": "Average Inventory"},
             ]},
        ],
    },
    "HR": {
        "label": "HR Analytics",
        "description": "Attrition modelling (logistic regression) and employee productivity analysis",
        "items": [
            {"key": "hr_1", "analysis_id": "hr_attrition_model", "label": "HR Attrition Model", "number": "5.1",
             "premium": True, "needs_dataframe": True, "inputs": [
                {"name": "target_col", "type": "column_categorical", "label": "Attrition Column (Yes/No or 1/0)"},
                {"name": "feature_cols", "type": "column_list", "label": "Predictor Columns (comma-separated, numeric)"},
             ]},
            {"key": "hr_2", "analysis_id": "employee_productivity_summary", "label": "Employee Productivity Analysis", "number": "5.2",
             "premium": False, "needs_dataframe": True, "inputs": [
                {"name": "output_col", "type": "column_numeric", "label": "Output Column"},
                {"name": "input_col", "type": "column_numeric", "label": "Input Column (e.g. hours worked)"},
             ]},
        ],
    },
    "ProjectRisk": {
        "label": "Project & Risk Management",
        "description": "PERT expected time, Critical Path Method, Expected Monetary Value, scenario analysis",
        "items": [
            {"key": "pr_1", "analysis_id": "pert_expected_time", "label": "PERT Expected Time", "number": "6.1",
             "premium": False, "needs_dataframe": False, "inputs": [
                {"name": "optimistic", "type": "number", "label": "Optimistic Time"},
                {"name": "most_likely", "type": "number", "label": "Most Likely Time"},
                {"name": "pessimistic", "type": "number", "label": "Pessimistic Time"},
             ]},
            {"key": "pr_2", "analysis_id": "critical_path_method", "label": "Critical Path Method (CPM)", "number": "6.2",
             "premium": True, "needs_dataframe": False, "inputs": [
                {"name": "tasks", "type": "task_list", "label": "Tasks (name, duration, dependencies)"},
             ]},
            {"key": "pr_3", "analysis_id": "expected_monetary_value", "label": "Expected Monetary Value (EMV)", "number": "6.3",
             "premium": False, "needs_dataframe": False, "inputs": [
                {"name": "probabilities", "type": "number_array", "label": "Probabilities (e.g. 0.3, 0.5, 0.2)"},
                {"name": "impacts", "type": "number_array", "label": "Impacts / Payoffs (same order)"},
             ]},
            {"key": "pr_4", "analysis_id": "scenario_analysis", "label": "Scenario Analysis", "number": "6.4",
             "premium": False, "needs_dataframe": False, "inputs": [
                {"name": "base_value", "type": "number", "label": "Base Value"},
                {"name": "scenarios", "type": "scenario_list", "label": "Scenarios (name, % change)"},
             ]},
        ],
    },
    "BusinessIntelligence": {
        "label": "Business Intelligence",
        "description": "Core KPI / business dashboard summary",
        "items": [
            {"key": "bi_1", "analysis_id": "business_kpi_summary", "label": "Business KPI Summary", "number": "7.1",
             "premium": False, "needs_dataframe": False, "inputs": [
                {"name": "revenue", "type": "number", "label": "Revenue"},
                {"name": "cost", "type": "number", "label": "Cost"},
                {"name": "customers", "type": "number", "label": "Number of Customers"},
                {"name": "orders", "type": "number", "label": "Number of Orders"},
             ]},
        ],
    },
    "Trade": {
        "label": "Trade, Logistics & Value Chain",
        "description": "Trade balance & growth, export concentration (HHI), landed cost, logistics cost share",
        "items": [
            {"key": "tr_1", "analysis_id": "trade_balance_growth", "label": "Trade Balance & Growth", "number": "8.1",
             "premium": False, "needs_dataframe": True, "inputs": [
                {"name": "exports_col", "type": "column_numeric", "label": "Exports Column (row order = time)"},
                {"name": "imports_col", "type": "column_numeric", "label": "Imports Column (row order = time)"},
             ]},
            {"key": "tr_2", "analysis_id": "export_concentration_index", "label": "Export Concentration Index (HHI)", "number": "8.2",
             "premium": False, "needs_dataframe": True, "inputs": [
                {"name": "export_value_col", "type": "column_numeric", "label": "Export Value Column (by product/market)"},
             ]},
            {"key": "tr_3", "analysis_id": "landed_cost", "label": "Landed Cost", "number": "8.3",
             "premium": False, "needs_dataframe": False, "inputs": [
                {"name": "cif_price", "type": "number", "label": "CIF Price"},
                {"name": "duty", "type": "number", "label": "Duty"},
                {"name": "freight", "type": "number", "label": "Freight"},
                {"name": "insurance", "type": "number", "label": "Insurance"},
                {"name": "handling", "type": "number", "label": "Handling"},
                {"name": "compliance_cost", "type": "number", "label": "Compliance Cost (optional)", "required": False},
             ]},
            {"key": "tr_4", "analysis_id": "logistics_cost_share", "label": "Logistics Cost Share of Sales", "number": "8.4",
             "premium": False, "needs_dataframe": False, "inputs": [
                {"name": "transport", "type": "number", "label": "Transport Cost"},
                {"name": "storage", "type": "number", "label": "Storage Cost"},
                {"name": "inventory", "type": "number", "label": "Inventory Cost"},
                {"name": "insurance", "type": "number", "label": "Insurance Cost"},
                {"name": "handling", "type": "number", "label": "Handling Cost (optional)", "required": False},
                {"name": "sales", "type": "number", "label": "Sales"},
             ]},
        ],
    },
}

MANAGEMENT_MODULES = _MANAGEMENT_MODULES

_ANALYSIS_ROUTER = {
    'financial_ratios': financial_ratios,
    'npv_irr': npv_irr,
    'altman_z_score': altman_z_score,
    'benford_first_digit_test': benford_first_digit_test,
    'campaign_metrics': campaign_metrics,
    'ab_test': ab_test,
    'price_elasticity_analysis': price_elasticity_analysis,
    'consumer_behaviour_regression': consumer_behaviour_regression,
    'cagr_calc': cagr_calc,
    'sales_trend_forecast': sales_trend_forecast,
    'customer_lifetime_value': customer_lifetime_value,
    'rfm_analysis': rfm_analysis,
    'economic_order_quantity': economic_order_quantity,
    'reorder_point': reorder_point,
    'abc_inventory_analysis': abc_inventory_analysis,
    'supply_chain_kpis': supply_chain_kpis,
    'hr_attrition_model': hr_attrition_model,
    'employee_productivity_summary': employee_productivity_summary,
    'pert_expected_time': pert_expected_time,
    'critical_path_method': critical_path_method,
    'expected_monetary_value': expected_monetary_value,
    'scenario_analysis': scenario_analysis,
    'business_kpi_summary': business_kpi_summary,
    'trade_balance_growth': trade_balance_growth,
    'export_concentration_index': export_concentration_index,
    'landed_cost': landed_cost,
    'logistics_cost_share': logistics_cost_share,
}


def get_management_catalog() -> dict:
    modules = []
    for key, mod in _MANAGEMENT_MODULES.items():
        modules.append({
            'module_key': key,
            'label': mod['label'],
            'description': mod['description'],
            'items': mod['items'],
        })
    return {'modules': modules}


def run_management_analysis(analysis_id: str, df: pd.DataFrame, parameters: dict) -> dict:
    fn = _ANALYSIS_ROUTER.get(analysis_id)
    if not fn:
        return _err(f"'{analysis_id}' is not a recognised management analysis")
    try:
        return fn(df, parameters or {})
    except Exception as e:
        return _err(f'Unexpected error running {analysis_id}: {e}')


# ══════════════════════════════════════════════════════════════════════════
# SMART SUGGESTIONS — inspect a file's columns_meta and recommend specific
# management sub-tests, mirroring engineering_analytics.suggest_engineering_analyses().
# ══════════════════════════════════════════════════════════════════════════
def _is_id_col(c: dict) -> bool:
    n = c.get('name', '').lower()
    return 'id' in n or 'respondent' in n


def suggest_management_analyses(columns_meta: list) -> dict:
    if not columns_meta:
        return {'recommended': [], 'numeric_columns': [], 'categorical_columns': [], 'date_columns': []}

    numeric = [c for c in columns_meta if c.get('python_type') in ('integer', 'float') and not _is_id_col(c)]
    categorical = [c for c in columns_meta if c.get('python_type') == 'string' and not _is_id_col(c)]
    dates = [c for c in columns_meta if c.get('python_type') in ('datetime', 'date_string')]
    id_like = [c for c in columns_meta if _is_id_col(c) and c.get('python_type') == 'string']

    names_lower = {c['name'].lower(): c['name'] for c in columns_meta}
    recommended = []

    def find_col(keywords, pool):
        for c in pool:
            n = c['name'].lower()
            if any(k in n for k in keywords):
                return c['name']
        return None

    # ── Benford's Law: any numeric column that reads like a monetary amount ──
    amount_col = find_col(['amount', 'value', 'price', 'transaction', 'revenue', 'cost', 'sales'], numeric)
    if amount_col:
        recommended.append({
            'module_key': 'Finance', 'analysis_id': 'benford_first_digit_test', 'item_key': 'fin_4',
            'label': "Benford's Law Fraud Test",
            'reason': f"'{amount_col}' looks like a transaction amount — Benford's Law can flag anomalous digit patterns.",
            'prefill': {'column': amount_col},
        })

    # ── Price Elasticity: a price column and a quantity column both present ──
    price_col = find_col(['price', 'rate'], numeric)
    qty_col = find_col(['quantity', 'qty', 'units', 'volume'], numeric)
    if price_col and qty_col and price_col != qty_col:
        recommended.append({
            'module_key': 'Marketing', 'analysis_id': 'price_elasticity_analysis', 'item_key': 'mkt_3',
            'label': 'Price Elasticity of Demand',
            'reason': f"'{price_col}' and '{qty_col}' look like a price/quantity pair — measure demand sensitivity to price.",
            'prefill': {'price_col': price_col, 'quantity_col': qty_col},
        })

    # ── Sales Trend Forecast: any column that reads like a sales/revenue series ──
    sales_col = find_col(['sales', 'revenue'], numeric)
    if sales_col:
        recommended.append({
            'module_key': 'Sales', 'analysis_id': 'sales_trend_forecast', 'item_key': 'sal_2',
            'label': 'Sales Trend Forecast',
            'reason': f"'{sales_col}' looks like a sales/revenue series — project the next few periods with a trend line.",
            'prefill': {'sales_col': sales_col, 'future_periods': 5},
        })

    # ── RFM Analysis: a customer ID + a date column + an amount column ──
    customer_col = find_col(['customer'], id_like) or find_col(['customer'], categorical)
    date_col = dates[0]['name'] if dates else None
    if customer_col and date_col and amount_col:
        recommended.append({
            'module_key': 'Sales', 'analysis_id': 'rfm_analysis', 'item_key': 'sal_4',
            'label': 'RFM Analysis',
            'reason': f"'{customer_col}', '{date_col}' and '{amount_col}' together support Recency/Frequency/Monetary customer segmentation.",
            'prefill': {'customer_col': customer_col, 'date_col': date_col, 'amount_col': amount_col},
        })

    # ── ABC Inventory: an item/SKU-like categorical column + a value column ──
    item_col = find_col(['item', 'sku', 'product'], categorical) or find_col(['item', 'sku', 'product'], id_like)
    value_col = find_col(['value', 'annual'], numeric) or amount_col
    if item_col and value_col:
        recommended.append({
            'module_key': 'Operations', 'analysis_id': 'abc_inventory_analysis', 'item_key': 'ops_3',
            'label': 'ABC Inventory Analysis',
            'reason': f"'{item_col}' with '{value_col}' can be ranked into A/B/C inventory value tiers.",
            'prefill': {'item_col': item_col, 'annual_value_col': value_col},
        })

    # ── HR Attrition: a Yes/No-like binary column named attrition/churn/left ──
    attrition_col = None
    for c in categorical:
        n = c['name'].lower()
        if any(k in n for k in ['attrition', 'churn', 'left', 'resigned', 'turnover']):
            attrition_col = c['name']
            break
    if attrition_col and len(numeric) >= 1:
        feature_cols = [c['name'] for c in numeric[:3]]
        recommended.append({
            'module_key': 'HR', 'analysis_id': 'hr_attrition_model', 'item_key': 'hr_1',
            'label': 'HR Attrition Model',
            'reason': f"'{attrition_col}' looks like an attrition/churn flag — model it against {', '.join(feature_cols)}.",
            'prefill': {'target_col': attrition_col, 'feature_cols': feature_cols},
        })

    # ── Employee Productivity: an output column + an input (hours/effort) column ──
    output_col = find_col(['output'], numeric)
    input_col = find_col(['input', 'hours', 'effort'], numeric)
    if output_col and input_col and output_col != input_col:
        recommended.append({
            'module_key': 'HR', 'analysis_id': 'employee_productivity_summary', 'item_key': 'hr_2',
            'label': 'Employee Productivity Analysis',
            'reason': f"'{output_col}' over '{input_col}' gives a productivity ratio per row.",
            'prefill': {'output_col': output_col, 'input_col': input_col},
        })

    # ── Trade Balance: both an exports and an imports column present ──
    exports_col = find_col(['export'], numeric)
    imports_col = find_col(['import'], numeric)
    if exports_col and imports_col:
        recommended.append({
            'module_key': 'Trade', 'analysis_id': 'trade_balance_growth', 'item_key': 'tr_1',
            'label': 'Trade Balance & Growth',
            'reason': f"'{exports_col}' and '{imports_col}' — compute trade balance and period-over-period growth.",
            'prefill': {'exports_col': exports_col, 'imports_col': imports_col},
        })

    # ── Export Concentration: an export-value-like column with no import counterpart ──
    if exports_col and not imports_col:
        recommended.append({
            'module_key': 'Trade', 'analysis_id': 'export_concentration_index', 'item_key': 'tr_2',
            'label': 'Export Concentration Index (HHI)',
            'reason': f"'{exports_col}' can be checked for concentration risk across products/markets.",
            'prefill': {'export_value_col': exports_col},
        })

    return {
        'recommended': recommended,
        'numeric_columns': [c['name'] for c in numeric],
        'categorical_columns': [c['name'] for c in categorical],
        'date_columns': [c['name'] for c in dates],
    }
    