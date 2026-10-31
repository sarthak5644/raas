"""
Environmental, Climate & Sustainability Sciences Service (RaaS Stage-2, Component 6)
========================================================================================
Same architecture as sarthak/management/management_analytics.py:
  - Individual analysis functions: fn(df, parameters) -> dict
  - ENVIRONMENTAL_MODULES: catalog driving the frontend UI
  - run_environmental_analysis(): dispatcher
  - suggest_environmental_analyses(): column-driven recommendations for a file

8 modules, matching Component 6's own category list exactly (8+5+3+3+5+3+6+2 = 35 functions):
    1. Climate Analytics              (8)
    2. Carbon & Energy Analytics      (5)
    3. Environmental Quality          (3)
    4. Biodiversity & Ecology         (3)
    5. Remote Sensing & GIS           (5)
    6. Hydrology                      (3)
    7. Sustainability & ESG           (6)
    8. Risk & Scenario Analysis       (2)

Mann-Kendall / Sen's Slope are implemented from scratch (no pymannkendall
dependency) to avoid requiring an extra pip package beyond the project's
existing stack (numpy, pandas, scipy, statsmodels).
"""
import numpy as np
import pandas as pd
from scipy import stats
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


def _weighted_composite_index(df: pd.DataFrame, indicator_cols: list, weights: list, output_label: str) -> dict:
    """Shared normalize-then-weight formula used by Soil Quality Index,
    Environmental Impact Score, and Sustainability Index — they're all
    `Index = sum(w_i * normalize(X_i))`, just applied to different indicators."""
    if df is None or not indicator_cols:
        return _err('indicator_cols is required')
    missing = [c for c in indicator_cols if c not in df.columns]
    if missing:
        return _err(f'Unknown columns: {missing}')
    if len(weights) != len(indicator_cols):
        return _err('weights must have the same length as indicator_cols')

    data = df[indicator_cols].apply(pd.to_numeric, errors='coerce').dropna()
    if data.empty:
        return _err('No usable numeric rows across the selected indicator columns')

    normed = pd.DataFrame(index=data.index)
    for col in indicator_cols:
        lo, hi = data[col].min(), data[col].max()
        normed[col] = 0.5 if hi == lo else (data[col] - lo) / (hi - lo)

    index_series = sum(normed[c] * w for c, w in zip(indicator_cols, weights))

    hist, edges = np.histogram(index_series, bins=15)
    histogram = [{'bin_start': round(float(edges[i]), 3), 'bin_end': round(float(edges[i + 1]), 3), 'count': int(hist[i])}
                 for i in range(len(hist))]

    ranked = index_series.sort_values(ascending=False)
    top_rows = [{'row': int(idx), output_label: round(float(v), 4)} for idx, v in ranked.head(10).items()]

    return {
        'type': output_label,
        'n_rows': int(len(index_series)),
        'mean': round(float(index_series.mean()), 4),
        'min': round(float(index_series.min()), 4),
        'max': round(float(index_series.max()), 4),
        'histogram': histogram,
        'top_rows': top_rows,
    }


# ══════════════════════════════════════════════════════════════════════════
# ANALYSES THAT READ THE UPLOADED FILE (everything else is parameter-only)
# ══════════════════════════════════════════════════════════════════════════
DATA_DRIVEN_ANALYSES = {
    'climate_trend_analysis',
    'temperature_anomaly',
    'rainfall_variability',
    'standardized_precipitation_index',
    'mann_kendall_trend_test',
    'sens_slope_estimator',
    'climate_arima_forecast',
    'total_carbon_emissions',
    'soil_quality_index',
    'ndvi_analysis',
    'evi_analysis',
    'land_use_change_matrix',
    'environmental_impact_score',
    'sustainability_index',
}

PREMIUM_ANALYSES = {
    'climate_arima_forecast',
    'mann_kendall_trend_test',
    'sens_slope_estimator',
    'soil_quality_index',
    'ndvi_analysis',
    'evi_analysis',
    'environmental_impact_score',
    'sustainability_index',
    'idw_interpolation',
    'pollutant_aqi',
}


# ══════════════════════════════════════════════════════════════════════════
# 1. CLIMATE ANALYTICS
# ══════════════════════════════════════════════════════════════════════════
def climate_trend_analysis(df: pd.DataFrame, parameters: dict) -> dict:
    """parameters: value_col (row order = time)"""
    value_col = parameters.get('value_col')
    if df is None or value_col not in df.columns:
        return _err('value_col must be a valid column')

    series = pd.to_numeric(df[value_col], errors='coerce').dropna().reset_index(drop=True)
    if len(series) < 4:
        return _err('Need at least 4 data points to fit a trend')

    t = np.arange(len(series))
    X = sm.add_constant(t)
    model = sm.OLS(series.values, X).fit(cov_type='HC3')

    curve = [{'period': int(i), 'value': round(float(v), 4), 'fitted': round(float(model.fittedvalues[i]), 4)}
             for i, v in enumerate(series)]

    return {
        'type': 'climate_trend_analysis',
        'slope_per_period': round(float(model.params[1]), 6),
        'p_value': round(float(model.pvalues[1]), 6),
        'r_squared': round(float(model.rsquared), 4),
        'trend_direction': 'Increasing' if model.params[1] > 0 else 'Decreasing',
        'significant': bool(model.pvalues[1] < 0.05),
        'curve': curve[:200],
    }


def temperature_anomaly(df: pd.DataFrame, parameters: dict) -> dict:
    """parameters: temp_col, date_col (optional), baseline_start (optional, 'YYYY-MM-DD'), baseline_end (optional)"""
    temp_col = parameters.get('temp_col')
    date_col = parameters.get('date_col')
    baseline_start = parameters.get('baseline_start')
    baseline_end = parameters.get('baseline_end')
    if df is None or temp_col not in df.columns:
        return _err('temp_col must be a valid column')

    temp = pd.to_numeric(df[temp_col], errors='coerce')

    if date_col and baseline_start and baseline_end and date_col in df.columns:
        dates = pd.to_datetime(df[date_col], errors='coerce')
        mask = (dates >= baseline_start) & (dates <= baseline_end)
        baseline_vals = temp[mask].dropna()
        baseline = float(baseline_vals.mean()) if len(baseline_vals) > 0 else float(temp.dropna().mean())
    else:
        baseline = float(temp.dropna().mean())

    anomaly = (temp - baseline).dropna().reset_index(drop=True)
    if anomaly.empty:
        return _err('No usable numeric data in temp_col')

    curve = [{'period': i, 'anomaly': round(float(v), 4)} for i, v in enumerate(anomaly.tolist()[:200])]

    return {
        'type': 'temperature_anomaly',
        'baseline_mean': round(baseline, 4),
        'mean_anomaly': round(float(anomaly.mean()), 4),
        'max_anomaly': round(float(anomaly.max()), 4),
        'min_anomaly': round(float(anomaly.min()), 4),
        'pct_positive_anomaly': round(float((anomaly > 0).mean() * 100), 2),
        'curve': curve,
    }


def rainfall_variability(df: pd.DataFrame, parameters: dict) -> dict:
    """parameters: rainfall_col"""
    rainfall = _numeric_series(df, parameters.get('rainfall_col'))
    if rainfall.empty:
        return _err('rainfall_col has no usable numeric data')
    if rainfall.mean() == 0:
        return _err('Mean rainfall is zero — coefficient of variation is undefined')

    cv = (rainfall.std() / rainfall.mean()) * 100
    variability = 'Low variability' if cv < 20 else 'Moderate variability' if cv < 30 else 'High variability'

    return {
        'type': 'rainfall_variability',
        'mean_rainfall': round(float(rainfall.mean()), 4),
        'std_rainfall': round(float(rainfall.std()), 4),
        'coefficient_of_variation_pct': round(float(cv), 4),
        'interpretation': variability,
    }


def standardized_precipitation_index(df: pd.DataFrame, parameters: dict) -> dict:
    """parameters: rainfall_col"""
    rainfall = _numeric_series(df, parameters.get('rainfall_col'))
    if rainfall.empty or rainfall.std() == 0:
        return _err('rainfall_col has no usable numeric data (or zero variance)')

    spi = (rainfall - rainfall.mean()) / rainfall.std()

    def classify(v):
        if v <= -2: return 'Extreme Drought'
        if v <= -1.5: return 'Severe Drought'
        if v <= -1: return 'Moderate Drought'
        if v < 1: return 'Near Normal'
        if v < 1.5: return 'Moderately Wet'
        if v < 2: return 'Severely Wet'
        return 'Extremely Wet'

    categories = spi.apply(classify)
    category_counts = categories.value_counts().to_dict()
    curve = [{'period': i, 'spi': round(float(v), 4)} for i, v in enumerate(spi.tolist()[:200])]

    return {
        'type': 'standardized_precipitation_index',
        'n_periods': int(len(spi)),
        'pct_in_drought': round(float((spi <= -1).mean() * 100), 2),
        'category_counts': {k: int(v) for k, v in category_counts.items()},
        'curve': curve,
    }


NOAA_HEAT_INDEX_BANDS = [
    (125, 'Extreme Danger — heat stroke highly likely'),
    (103, 'Danger — heat cramps/exhaustion likely, heat stroke possible'),
    (90, 'Extreme Caution — heat cramps/exhaustion possible'),
    (80, 'Caution — fatigue possible with prolonged exposure'),
]


def heat_index_fahrenheit(df: pd.DataFrame, parameters: dict) -> dict:
    """parameters: temp_f, relative_humidity"""
    try:
        T = _num(parameters, 'temp_f')
        R = _num(parameters, 'relative_humidity')
        HI = (
            -42.379 + 2.04901523 * T + 10.14333127 * R
            - 0.22475541 * T * R - 0.00683783 * T * T
            - 0.05481717 * R * R + 0.00122874 * T * T * R
            + 0.00085282 * T * R * R - 0.00000199 * T * T * R * R
        )
        category = 'No significant risk'
        for threshold, label in NOAA_HEAT_INDEX_BANDS:
            if HI >= threshold:
                category = label
                break
        return {'type': 'heat_index_fahrenheit', 'temp_f': T, 'relative_humidity': R,
                'heat_index': round(float(HI), 2), 'risk_category': category}
    except KeyError as e:
        return _err(f'Missing input: {e}')


def _mann_kendall(series: pd.Series) -> dict:
    x = series.dropna().values
    n = len(x)
    if n < 4:
        raise ValueError('Need at least 4 data points for Mann-Kendall')

    s = 0
    for k in range(n - 1):
        s += np.sum(np.sign(x[k + 1:] - x[k]))

    _, counts = np.unique(x, return_counts=True)
    tie_term = np.sum(counts * (counts - 1) * (2 * counts + 5))
    var_s = (n * (n - 1) * (2 * n + 5) - tie_term) / 18.0

    if s > 0:
        z = (s - 1) / np.sqrt(var_s)
    elif s < 0:
        z = (s + 1) / np.sqrt(var_s)
    else:
        z = 0.0

    p_value = 2 * (1 - stats.norm.cdf(abs(z)))
    trend = 'increasing' if (z > 0 and p_value < 0.05) else 'decreasing' if (z < 0 and p_value < 0.05) else 'no trend'
    tau = s / (0.5 * n * (n - 1))

    return {'s': int(s), 'z': float(z), 'p_value': float(p_value), 'tau': float(tau), 'trend': trend, 'n': n}


def mann_kendall_trend_test(df: pd.DataFrame, parameters: dict) -> dict:
    """parameters: value_col"""
    series = _numeric_series(df, parameters.get('value_col'))
    if series.empty:
        return _err('value_col has no usable numeric data')
    try:
        result = _mann_kendall(series)
    except ValueError as e:
        return _err(str(e))

    return {
        'type': 'mann_kendall_trend_test',
        'n': result['n'],
        's_statistic': result['s'],
        'z_statistic': round(result['z'], 4),
        'p_value': round(result['p_value'], 6),
        'kendalls_tau': round(result['tau'], 4),
        'trend': result['trend'],
        'significant': bool(result['p_value'] < 0.05),
    }


def sens_slope_estimator(df: pd.DataFrame, parameters: dict) -> dict:
    """parameters: value_col"""
    series = _numeric_series(df, parameters.get('value_col')).reset_index(drop=True)
    n = len(series)
    if n < 4:
        return _err('Need at least 4 data points for Sen\'s Slope')

    slopes = []
    for i in range(n - 1):
        for j in range(i + 1, n):
            if j != i:
                slopes.append((series[j] - series[i]) / (j - i))
    slopes = np.array(slopes)
    slope = float(np.median(slopes))
    intercept = float(series.median() - slope * (n - 1) / 2)

    return {
        'type': 'sens_slope_estimator',
        'n': n,
        'sens_slope': round(slope, 6),
        'intercept': round(intercept, 4),
        'direction': 'Increasing' if slope > 0 else 'Decreasing' if slope < 0 else 'Flat',
    }


def climate_arima_forecast(df: pd.DataFrame, parameters: dict) -> dict:
    """parameters: value_col, p, d, q (default 1,1,1), steps (default 10)"""
    value_col = parameters.get('value_col')
    if df is None or value_col not in df.columns:
        return _err('value_col must be a valid column')

    series = pd.to_numeric(df[value_col], errors='coerce').dropna().reset_index(drop=True)
    if len(series) < 10:
        return _err('Need at least 10 data points to fit an ARIMA model')

    p = int(parameters.get('p', 1))
    d = int(parameters.get('d', 1))
    q = int(parameters.get('q', 1))
    steps = min(int(parameters.get('steps', 10)), 50)

    try:
        from statsmodels.tsa.arima.model import ARIMA
        model = ARIMA(series, order=(p, d, q))
        fitted = model.fit()
        forecast = fitted.forecast(steps=steps)
    except Exception as e:
        return _err(f'ARIMA fitting failed: {e}. Try order (1,1,1) or a longer series.')

    history_curve = [{'period': i, 'value': round(float(v), 4), 'kind': 'actual'} for i, v in enumerate(series)]
    forecast_curve = [{'period': len(series) + i, 'value': round(float(v), 4), 'kind': 'forecast'}
                       for i, v in enumerate(forecast)]

    return {
        'type': 'climate_arima_forecast',
        'order': f'({p},{d},{q})',
        'aic': round(float(fitted.aic), 4),
        'forecast_steps': steps,
        'curve': history_curve + forecast_curve,
    }


# ══════════════════════════════════════════════════════════════════════════
# 2. CARBON & ENERGY ANALYTICS
# ══════════════════════════════════════════════════════════════════════════
def total_carbon_emissions(df: pd.DataFrame, parameters: dict) -> dict:
    """parameters: activity_cols (column_list), emission_factors (number_array, same length)"""
    activity_cols = parameters.get('activity_cols', [])
    factors = parameters.get('emission_factors', [])
    if df is None or not activity_cols:
        return _err('activity_cols is required')
    if len(activity_cols) != len(factors):
        return _err('emission_factors must have the same length as activity_cols')
    missing = [c for c in activity_cols if c not in df.columns]
    if missing:
        return _err(f'Unknown columns: {missing}')

    data = df[activity_cols].apply(pd.to_numeric, errors='coerce').fillna(0)
    total = pd.Series(0.0, index=data.index)
    breakdown = []
    for col, factor in zip(activity_cols, factors):
        contribution = data[col] * factor
        total += contribution
        breakdown.append({'activity': col, 'emission_factor': factor, 'total_CO2e': round(float(contribution.sum()), 4)})

    curve = [{'row': i, 'total_CO2e': round(float(v), 4)} for i, v in enumerate(total.tolist()[:200])]

    return {
        'type': 'total_carbon_emissions',
        'n_rows': int(len(total)),
        'grand_total_CO2e': round(float(total.sum()), 4),
        'avg_CO2e_per_row': round(float(total.mean()), 4),
        'breakdown_by_activity': breakdown,
        'curve': curve,
    }


def carbon_intensity(df: pd.DataFrame, parameters: dict) -> dict:
    try:
        total_emissions = _num(parameters, 'total_emissions')
        output = _num(parameters, 'output')
        if output == 0:
            return _err('output must be non-zero')
        return {'type': 'carbon_intensity', 'total_emissions': total_emissions, 'output': output,
                'carbon_intensity': round(total_emissions / output, 6)}
    except KeyError as e:
        return _err(f'Missing input: {e}')


def energy_intensity(df: pd.DataFrame, parameters: dict) -> dict:
    try:
        energy_use = _num(parameters, 'energy_use')
        output = _num(parameters, 'output')
        if output == 0:
            return _err('output must be non-zero')
        return {'type': 'energy_intensity', 'energy_use': energy_use, 'output': output,
                'energy_intensity': round(energy_use / output, 6)}
    except KeyError as e:
        return _err(f'Missing input: {e}')


def renewable_energy_share(df: pd.DataFrame, parameters: dict) -> dict:
    try:
        renewable = _num(parameters, 'renewable_energy')
        total = _num(parameters, 'total_energy')
        if total == 0:
            return _err('total_energy must be non-zero')
        share = (renewable / total) * 100
        return {'type': 'renewable_energy_share', 'renewable_energy': renewable, 'total_energy': total,
                'renewable_share_pct': round(share, 4)}
    except KeyError as e:
        return _err(f'Missing input: {e}')


def carbon_payback_period(df: pd.DataFrame, parameters: dict) -> dict:
    try:
        embodied = _num(parameters, 'embodied_carbon')
        annual_savings = _num(parameters, 'annual_carbon_savings')
        if annual_savings == 0:
            return _err('annual_carbon_savings must be non-zero')
        payback = embodied / annual_savings
        return {'type': 'carbon_payback_period', 'embodied_carbon': embodied,
                'annual_carbon_savings': annual_savings, 'payback_years': round(payback, 4)}
    except KeyError as e:
        return _err(f'Missing input: {e}')


# ══════════════════════════════════════════════════════════════════════════
# 3. ENVIRONMENTAL QUALITY
# ══════════════════════════════════════════════════════════════════════════
def pollutant_aqi(df: pd.DataFrame, parameters: dict) -> dict:
    """parameters: pollutants -> [{name, concentration, c_low, c_high, i_low, i_high}, ...]"""
    pollutants = parameters.get('pollutants', [])
    if not pollutants:
        return _err('pollutants is required')

    table = []
    for p in pollutants:
        try:
            name = p['name']
            c, c_low, c_high, i_low, i_high = (float(p['concentration']), float(p['c_low']),
                                                float(p['c_high']), float(p['i_low']), float(p['i_high']))
            if c_high == c_low:
                return _err(f"c_high and c_low must differ for pollutant '{name}'")
            sub_index = ((i_high - i_low) / (c_high - c_low)) * (c - c_low) + i_low
            table.append({'pollutant': name, 'concentration': c, 'sub_index': round(sub_index, 2)})
        except (KeyError, ValueError) as e:
            return _err(f'Invalid pollutant row: {e}')

    overall = max(t['sub_index'] for t in table)
    dominant = next(t['pollutant'] for t in table if t['sub_index'] == overall)

    category = ('Good' if overall <= 50 else 'Satisfactory' if overall <= 100 else 'Moderate' if overall <= 200
                else 'Poor' if overall <= 300 else 'Very Poor' if overall <= 400 else 'Severe')

    return {'type': 'pollutant_aqi', 'overall_aqi': round(overall, 2), 'dominant_pollutant': dominant,
            'category': category, 'table': table}


def water_quality_index(df: pd.DataFrame, parameters: dict) -> dict:
    try:
        ratings = [float(x) for x in parameters.get('quality_ratings', [])]
        weights = [float(x) for x in parameters.get('weights', [])]
        if not ratings or len(ratings) != len(weights):
            return _err('quality_ratings and weights must be non-empty and the same length')
        wqi = float(np.sum(np.array(ratings) * np.array(weights)) / np.sum(weights))
        category = ('Excellent' if wqi <= 25 else 'Good' if wqi <= 50 else 'Poor' if wqi <= 75
                    else 'Very Poor' if wqi <= 100 else 'Unsuitable for Drinking')
        return {'type': 'water_quality_index', 'wqi': round(wqi, 4), 'category': category}
    except Exception as e:
        return _err(str(e))


def soil_quality_index(df: pd.DataFrame, parameters: dict) -> dict:
    """parameters: soil_parameters (column_list), weights (number_array)"""
    return _weighted_composite_index(df, parameters.get('soil_parameters', []),
                                       [float(x) for x in parameters.get('weights', [])], 'soil_quality_index')


# ══════════════════════════════════════════════════════════════════════════
# 4. BIODIVERSITY & ECOLOGY
# ══════════════════════════════════════════════════════════════════════════
def shannon_diversity_index(df: pd.DataFrame, parameters: dict) -> dict:
    try:
        counts = np.array([float(x) for x in parameters.get('species_counts', [])])
        if len(counts) < 2 or (counts <= 0).any():
            return _err('species_counts must have at least 2 positive values')
        proportions = counts / counts.sum()
        h = float(-np.sum(proportions * np.log(proportions)))
        max_h = float(np.log(len(counts)))
        evenness = h / max_h if max_h > 0 else None
        return {'type': 'shannon_diversity_index', 'n_species': len(counts), 'shannon_index': round(h, 4),
                'max_possible_index': round(max_h, 4), 'evenness': round(evenness, 4) if evenness is not None else None}
    except Exception as e:
        return _err(str(e))


def simpson_diversity_index(df: pd.DataFrame, parameters: dict) -> dict:
    try:
        counts = np.array([float(x) for x in parameters.get('species_counts', [])])
        if len(counts) < 2 or (counts <= 0).any():
            return _err('species_counts must have at least 2 positive values')
        proportions = counts / counts.sum()
        d = float(1 - np.sum(proportions ** 2))
        interpretation = 'High diversity' if d > 0.7 else 'Moderate diversity' if d > 0.4 else 'Low diversity'
        return {'type': 'simpson_diversity_index', 'n_species': len(counts), 'simpson_index': round(d, 4),
                'interpretation': interpretation}
    except Exception as e:
        return _err(str(e))


def ecological_footprint(df: pd.DataFrame, parameters: dict) -> dict:
    try:
        consumption = _num(parameters, 'consumption')
        productivity = _num(parameters, 'productivity')
        if productivity == 0:
            return _err('productivity must be non-zero')
        ef = consumption / productivity
        return {'type': 'ecological_footprint', 'consumption': consumption, 'productivity': productivity,
                'ecological_footprint_gha': round(ef, 4)}
    except KeyError as e:
        return _err(f'Missing input: {e}')


# ══════════════════════════════════════════════════════════════════════════
# 5. REMOTE SENSING & GIS
# ══════════════════════════════════════════════════════════════════════════
def _ndvi_class(v):
    if v < 0: return 'Water / Cloud'
    if v < 0.2: return 'Barren / Built-up'
    if v < 0.4: return 'Sparse Vegetation'
    if v < 0.6: return 'Moderate Vegetation'
    return 'Dense Vegetation'


def ndvi_analysis(df: pd.DataFrame, parameters: dict) -> dict:
    """parameters: nir_col, red_col"""
    nir_col, red_col = parameters.get('nir_col'), parameters.get('red_col')
    if df is None or nir_col not in df.columns or red_col not in df.columns:
        return _err('nir_col and red_col must be valid columns')

    data = df[[nir_col, red_col]].apply(pd.to_numeric, errors='coerce').dropna()
    denom = data[nir_col] + data[red_col]
    data = data[denom != 0]
    if data.empty:
        return _err('No usable rows (NIR + Red must be non-zero)')

    ndvi = (data[nir_col] - data[red_col]) / (data[nir_col] + data[red_col])
    classes = ndvi.apply(_ndvi_class).value_counts().to_dict()
    hist, edges = np.histogram(ndvi, bins=15, range=(-1, 1))
    histogram = [{'bin_start': round(float(edges[i]), 2), 'bin_end': round(float(edges[i + 1]), 2), 'count': int(hist[i])}
                 for i in range(len(hist))]

    return {
        'type': 'ndvi_analysis', 'n': int(len(ndvi)), 'mean_ndvi': round(float(ndvi.mean()), 4),
        'min_ndvi': round(float(ndvi.min()), 4), 'max_ndvi': round(float(ndvi.max()), 4),
        'class_counts': {k: int(v) for k, v in classes.items()}, 'histogram': histogram,
    }


def evi_analysis(df: pd.DataFrame, parameters: dict) -> dict:
    """parameters: nir_col, red_col, blue_col, G,C1,C2,L optional overrides"""
    nir_col, red_col, blue_col = parameters.get('nir_col'), parameters.get('red_col'), parameters.get('blue_col')
    if df is None or any(c not in df.columns for c in [nir_col, red_col, blue_col]):
        return _err('nir_col, red_col and blue_col must all be valid columns')

    G = float(parameters.get('G', 2.5))
    C1 = float(parameters.get('C1', 6))
    C2 = float(parameters.get('C2', 7.5))
    L = float(parameters.get('L', 1))

    data = df[[nir_col, red_col, blue_col]].apply(pd.to_numeric, errors='coerce').dropna()
    denom = data[nir_col] + C1 * data[red_col] - C2 * data[blue_col] + L
    data = data[denom != 0]
    if data.empty:
        return _err('No usable rows (denominator was zero for all rows)')

    evi = G * ((data[nir_col] - data[red_col]) / (data[nir_col] + C1 * data[red_col] - C2 * data[blue_col] + L))
    hist, edges = np.histogram(evi, bins=15)
    histogram = [{'bin_start': round(float(edges[i]), 3), 'bin_end': round(float(edges[i + 1]), 3), 'count': int(hist[i])}
                 for i in range(len(hist))]

    return {'type': 'evi_analysis', 'n': int(len(evi)), 'mean_evi': round(float(evi.mean()), 4),
            'min_evi': round(float(evi.min()), 4), 'max_evi': round(float(evi.max()), 4), 'histogram': histogram}


def land_use_change_matrix(df: pd.DataFrame, parameters: dict) -> dict:
    """parameters: initial_col, final_col (categorical)"""
    initial_col, final_col = parameters.get('initial_col'), parameters.get('final_col')
    if df is None or initial_col not in df.columns or final_col not in df.columns:
        return _err('initial_col and final_col must be valid columns')

    data = df[[initial_col, final_col]].dropna()
    if data.empty:
        return _err('No usable rows')

    matrix = pd.crosstab(data[initial_col], data[final_col])
    unchanged = int(sum(matrix.loc[c, c] for c in matrix.index if c in matrix.columns))
    total = int(matrix.values.sum())

    table = []
    for initial_class in matrix.index:
        for final_class in matrix.columns:
            count = int(matrix.loc[initial_class, final_class])
            if count > 0:
                table.append({'from': str(initial_class), 'to': str(final_class), 'count': count})

    return {
        'type': 'land_use_change_matrix', 'total_observations': total,
        'unchanged_count': unchanged, 'pct_unchanged': round(unchanged / total * 100, 2) if total else 0,
        'pct_changed': round((total - unchanged) / total * 100, 2) if total else 0,
        'table': sorted(table, key=lambda r: -r['count'])[:30],
    }


def haversine_distance(df: pd.DataFrame, parameters: dict) -> dict:
    try:
        lat1, lon1 = _num(parameters, 'lat1'), _num(parameters, 'lon1')
        lat2, lon2 = _num(parameters, 'lat2'), _num(parameters, 'lon2')
        r = 6371
        p1, p2, dlat, dlon = map(np.radians, [lat1, lat2, lat2 - lat1, lon2 - lon1])
        a = np.sin(np.radians(lat2 - lat1) / 2) ** 2 + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
        c = 2 * np.arcsin(np.sqrt(a))
        return {'type': 'haversine_distance', 'lat1': lat1, 'lon1': lon1, 'lat2': lat2, 'lon2': lon2,
                'distance_km': round(float(r * c), 4)}
    except KeyError as e:
        return _err(f'Missing input: {e}')


def idw_interpolation(df: pd.DataFrame, parameters: dict) -> dict:
    """parameters: points -> [{lat, lon, value}, ...], target_lat, target_lon, power (default 2)"""
    try:
        points = parameters.get('points', [])
        target_lat = _num(parameters, 'target_lat')
        target_lon = _num(parameters, 'target_lon')
        power = float(parameters.get('power', 2))
        if len(points) < 2:
            return _err('Provide at least 2 known points')

        def hav(lat1, lon1, lat2, lon2):
            r = 6371
            a = np.sin(np.radians(lat2 - lat1) / 2) ** 2 + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
            return r * 2 * np.arcsin(np.sqrt(a))

        breakdown = []
        weight_sum, weighted_val_sum = 0.0, 0.0
        for p in points:
            lat, lon, val = float(p['lat']), float(p['lon']), float(p['value'])
            d = hav(target_lat, target_lon, lat, lon)
            d = max(d, 1e-10)
            w = 1 / (d ** power)
            weight_sum += w
            weighted_val_sum += w * val
            breakdown.append({'lat': lat, 'lon': lon, 'value': val, 'distance_km': round(float(d), 4), 'weight': round(float(w), 6)})

        interpolated = weighted_val_sum / weight_sum
        return {'type': 'idw_interpolation', 'target_lat': target_lat, 'target_lon': target_lon,
                'interpolated_value': round(float(interpolated), 4), 'points': breakdown}
    except (KeyError, ValueError) as e:
        return _err(f'Missing or invalid input: {e}')


# ══════════════════════════════════════════════════════════════════════════
# 6. HYDROLOGY
# ══════════════════════════════════════════════════════════════════════════
def runoff_rational_method(df: pd.DataFrame, parameters: dict) -> dict:
    try:
        c = _num(parameters, 'runoff_coefficient')
        i = _num(parameters, 'rainfall_intensity')
        a = _num(parameters, 'area')
        q = c * i * a
        return {'type': 'runoff_rational_method', 'runoff_coefficient': c, 'rainfall_intensity': i, 'area': a,
                'runoff_Q': round(q, 4)}
    except KeyError as e:
        return _err(f'Missing input: {e}')


def water_balance(df: pd.DataFrame, parameters: dict) -> dict:
    try:
        p = _num(parameters, 'precipitation')
        et = _num(parameters, 'evapotranspiration')
        q = _num(parameters, 'runoff')
        storage_change = p - et - q
        return {'type': 'water_balance', 'precipitation': p, 'evapotranspiration': et, 'runoff': q,
                'storage_change': round(storage_change, 4)}
    except KeyError as e:
        return _err(f'Missing input: {e}')


def hargreaves_evapotranspiration(df: pd.DataFrame, parameters: dict) -> dict:
    try:
        t_mean = _num(parameters, 't_mean')
        t_max = _num(parameters, 't_max')
        t_min = _num(parameters, 't_min')
        radiation = _num(parameters, 'radiation')
        if t_max < t_min:
            return _err('t_max must be >= t_min')
        et0 = 0.0023 * (t_mean + 17.8) * ((t_max - t_min) ** 0.5) * radiation
        return {'type': 'hargreaves_evapotranspiration', 't_mean': t_mean, 't_max': t_max, 't_min': t_min,
                'radiation': radiation, 'ET0': round(float(et0), 4)}
    except KeyError as e:
        return _err(f'Missing input: {e}')


# ══════════════════════════════════════════════════════════════════════════
# 7. SUSTAINABILITY & ESG
# ══════════════════════════════════════════════════════════════════════════
def environmental_impact_score(df: pd.DataFrame, parameters: dict) -> dict:
    return _weighted_composite_index(df, parameters.get('indicator_cols', []),
                                       [float(x) for x in parameters.get('weights', [])], 'environmental_impact_score')


def life_cycle_assessment(df: pd.DataFrame, parameters: dict) -> dict:
    try:
        activity = [float(x) for x in parameters.get('activity_data', [])]
        factors = [float(x) for x in parameters.get('impact_factors', [])]
        if not activity or len(activity) != len(factors):
            return _err('activity_data and impact_factors must be non-empty and the same length')
        contributions = [round(a * f, 4) for a, f in zip(activity, factors)]
        total = float(sum(contributions))
        breakdown = [{'activity': i + 1, 'activity_value': a, 'impact_factor': f, 'contribution': c}
                     for i, (a, f, c) in enumerate(zip(activity, factors, contributions))]
        return {'type': 'life_cycle_assessment', 'total_impact': round(total, 4), 'breakdown': breakdown}
    except Exception as e:
        return _err(str(e))


def material_flow_balance(df: pd.DataFrame, parameters: dict) -> dict:
    try:
        inputs = _num(parameters, 'inputs')
        outputs = _num(parameters, 'outputs')
        losses = _num(parameters, 'losses')
        stock_change = inputs - outputs - losses
        return {'type': 'material_flow_balance', 'inputs': inputs, 'outputs': outputs, 'losses': losses,
                'stock_change': round(stock_change, 4)}
    except KeyError as e:
        return _err(f'Missing input: {e}')


def circularity_rate(df: pd.DataFrame, parameters: dict) -> dict:
    try:
        reused = _num(parameters, 'reused_material')
        recycled = _num(parameters, 'recycled_material')
        total_input = _num(parameters, 'total_material_input')
        if total_input == 0:
            return _err('total_material_input must be non-zero')
        rate = ((reused + recycled) / total_input) * 100
        interpretation = 'High circularity' if rate > 60 else 'Moderate circularity' if rate > 30 else 'Low circularity'
        return {'type': 'circularity_rate', 'circularity_rate_pct': round(rate, 4), 'interpretation': interpretation}
    except KeyError as e:
        return _err(f'Missing input: {e}')


def sustainability_index(df: pd.DataFrame, parameters: dict) -> dict:
    return _weighted_composite_index(df, parameters.get('indicator_cols', []),
                                       [float(x) for x in parameters.get('weights', [])], 'sustainability_index')


def esg_score(df: pd.DataFrame, parameters: dict) -> dict:
    try:
        e = _num(parameters, 'environment_score')
        s = _num(parameters, 'social_score')
        g = _num(parameters, 'governance_score')
        we = float(parameters.get('weight_environment', 0.33))
        ws = float(parameters.get('weight_social', 0.33))
        wg = float(parameters.get('weight_governance', 0.34))
        score = e * we + s * ws + g * wg
        rating = ('Leader' if score >= 80 else 'Strong' if score >= 60 else 'Average' if score >= 40
                  else 'Laggard' if score >= 20 else 'Poor')
        return {'type': 'esg_score', 'environment_score': e, 'social_score': s, 'governance_score': g,
                'esg_score': round(score, 4), 'rating': f'{rating} (illustrative band, not a rating-agency scale)'}
    except KeyError as e:
        return _err(f'Missing input: {e}')


# ══════════════════════════════════════════════════════════════════════════
# 8. RISK & SCENARIO ANALYSIS
# ══════════════════════════════════════════════════════════════════════════
def climate_risk_score(df: pd.DataFrame, parameters: dict) -> dict:
    try:
        hazard = _num(parameters, 'hazard')
        exposure = _num(parameters, 'exposure')
        vulnerability = _num(parameters, 'vulnerability')
        risk = hazard * exposure * vulnerability
        note = 'Interpretation assumes hazard/exposure/vulnerability are each scaled 0–1'
        return {'type': 'climate_risk_score', 'hazard': hazard, 'exposure': exposure,
                'vulnerability': vulnerability, 'risk_score': round(risk, 6), 'note': note}
    except KeyError as e:
        return _err(f'Missing input: {e}')


def emissions_scenario_analysis(df: pd.DataFrame, parameters: dict) -> dict:
    try:
        base = _num(parameters, 'base_emissions')
        scenarios = parameters.get('scenarios', [])
        if not scenarios:
            return _err('scenarios is required')
        results = [{'scenario': s['name'], 'change_pct': round(float(s['change']) * 100, 2),
                    'projected_emissions': round(base * (1 + float(s['change'])), 4)} for s in scenarios]
        return {'type': 'emissions_scenario_analysis', 'base_emissions': base, 'scenarios': results}
    except (KeyError, ValueError) as e:
        return _err(f'Missing or invalid input: {e}')


# ══════════════════════════════════════════════════════════════════════════
# CATALOG (drives the frontend UI)
# ══════════════════════════════════════════════════════════════════════════
_ENVIRONMENTAL_MODULES = {
    "Climate": {
        "label": "Climate Analytics",
        "description": "Trend analysis, temperature anomalies, drought index, heat index, Mann-Kendall/Sen's slope, ARIMA forecasting",
        "items": [
            {"key": "cl_1", "analysis_id": "climate_trend_analysis", "label": "Climate Trend Analysis", "number": "1.1",
             "premium": False, "needs_dataframe": True, "inputs": [
                {"name": "value_col", "type": "column_numeric", "label": "Value Column (row order = time)"},
             ]},
            {"key": "cl_2", "analysis_id": "temperature_anomaly", "label": "Temperature Anomaly", "number": "1.2",
             "premium": False, "needs_dataframe": True, "inputs": [
                {"name": "temp_col", "type": "column_numeric", "label": "Temperature Column"},
                {"name": "date_col", "type": "column_date", "label": "Date Column (optional, for a baseline window)", "required": False},
                {"name": "baseline_start", "type": "text", "label": "Baseline Start (YYYY-MM-DD, optional)", "required": False},
                {"name": "baseline_end", "type": "text", "label": "Baseline End (YYYY-MM-DD, optional)", "required": False},
             ]},
            {"key": "cl_3", "analysis_id": "rainfall_variability", "label": "Rainfall Variability", "number": "1.3",
             "premium": False, "needs_dataframe": True, "inputs": [
                {"name": "rainfall_col", "type": "column_numeric", "label": "Rainfall Column"},
             ]},
            {"key": "cl_4", "analysis_id": "standardized_precipitation_index", "label": "SPI Drought Index", "number": "1.4",
             "premium": False, "needs_dataframe": True, "inputs": [
                {"name": "rainfall_col", "type": "column_numeric", "label": "Rainfall Column"},
             ]},
            {"key": "cl_5", "analysis_id": "heat_index_fahrenheit", "label": "Heat Index", "number": "1.5",
             "premium": False, "needs_dataframe": False, "inputs": [
                {"name": "temp_f", "type": "number", "label": "Temperature (°F)"},
                {"name": "relative_humidity", "type": "number", "label": "Relative Humidity (%)"},
             ]},
            {"key": "cl_6", "analysis_id": "mann_kendall_trend_test", "label": "Mann-Kendall Trend Test", "number": "1.6",
             "premium": True, "needs_dataframe": True, "inputs": [
                {"name": "value_col", "type": "column_numeric", "label": "Value Column (row order = time)"},
             ]},
            {"key": "cl_7", "analysis_id": "sens_slope_estimator", "label": "Sen's Slope", "number": "1.7",
             "premium": True, "needs_dataframe": True, "inputs": [
                {"name": "value_col", "type": "column_numeric", "label": "Value Column (row order = time)"},
             ]},
            {"key": "cl_8", "analysis_id": "climate_arima_forecast", "label": "ARIMA Forecast", "number": "1.8",
             "premium": True, "needs_dataframe": True, "inputs": [
                {"name": "value_col", "type": "column_numeric", "label": "Value Column (row order = time)"},
                {"name": "p", "type": "number", "label": "AR order (p)", "required": False},
                {"name": "d", "type": "number", "label": "Differencing order (d)", "required": False},
                {"name": "q", "type": "number", "label": "MA order (q)", "required": False},
                {"name": "steps", "type": "number", "label": "Forecast Steps", "required": False},
             ]},
        ],
    },
    "CarbonEnergy": {
        "label": "Carbon & Energy Analytics",
        "description": "Emissions accounting, carbon/energy intensity, renewable share, carbon payback period",
        "items": [
            {"key": "ce_1", "analysis_id": "total_carbon_emissions", "label": "Carbon Emissions Accounting", "number": "2.1",
             "premium": False, "needs_dataframe": True, "inputs": [
                {"name": "activity_cols", "type": "column_list", "label": "Activity Columns (comma-separated)"},
                {"name": "emission_factors", "type": "number_array", "label": "Emission Factors (same order/count as columns)"},
             ]},
            {"key": "ce_2", "analysis_id": "carbon_intensity", "label": "Carbon Intensity", "number": "2.2",
             "premium": False, "needs_dataframe": False, "inputs": [
                {"name": "total_emissions", "type": "number", "label": "Total CO2e Emissions"},
                {"name": "output", "type": "number", "label": "Output (e.g. revenue, units produced)"},
             ]},
            {"key": "ce_3", "analysis_id": "energy_intensity", "label": "Energy Intensity", "number": "2.3",
             "premium": False, "needs_dataframe": False, "inputs": [
                {"name": "energy_use", "type": "number", "label": "Energy Use"},
                {"name": "output", "type": "number", "label": "Output"},
             ]},
            {"key": "ce_4", "analysis_id": "renewable_energy_share", "label": "Renewable Energy Share", "number": "2.4",
             "premium": False, "needs_dataframe": False, "inputs": [
                {"name": "renewable_energy", "type": "number", "label": "Renewable Energy"},
                {"name": "total_energy", "type": "number", "label": "Total Energy"},
             ]},
            {"key": "ce_5", "analysis_id": "carbon_payback_period", "label": "Carbon Payback Period", "number": "2.5",
             "premium": False, "needs_dataframe": False, "inputs": [
                {"name": "embodied_carbon", "type": "number", "label": "Embodied Carbon"},
                {"name": "annual_carbon_savings", "type": "number", "label": "Annual Carbon Savings"},
             ]},
        ],
    },
    "EnvQuality": {
        "label": "Environmental Quality",
        "description": "Air Quality Index, Water Quality Index, Soil Quality Index",
        "items": [
            {"key": "eq_1", "analysis_id": "pollutant_aqi", "label": "Air Quality Index (AQI)", "number": "3.1",
             "premium": True, "needs_dataframe": False, "inputs": [
                {"name": "pollutants", "type": "aqi_pollutant_list", "label": "Pollutants (name, concentration, C_low, C_high, I_low, I_high)"},
             ]},
            {"key": "eq_2", "analysis_id": "water_quality_index", "label": "Water Quality Index (WQI)", "number": "3.2",
             "premium": False, "needs_dataframe": False, "inputs": [
                {"name": "quality_ratings", "type": "number_array", "label": "Quality Ratings (Q_i, e.g. 20, 45, 60)"},
                {"name": "weights", "type": "number_array", "label": "Weights (W_i, same order/count)"},
             ]},
            {"key": "eq_3", "analysis_id": "soil_quality_index", "label": "Soil Quality Index", "number": "3.3",
             "premium": True, "needs_dataframe": True, "inputs": [
                {"name": "soil_parameters", "type": "column_list", "label": "Soil Parameter Columns (comma-separated)"},
                {"name": "weights", "type": "number_array", "label": "Weights (same order/count as columns)"},
             ]},
        ],
    },
    "Biodiversity": {
        "label": "Biodiversity & Ecology",
        "description": "Shannon Index, Simpson Index, Ecological Footprint",
        "items": [
            {"key": "bio_1", "analysis_id": "shannon_diversity_index", "label": "Shannon Diversity Index", "number": "4.1",
             "premium": False, "needs_dataframe": False, "inputs": [
                {"name": "species_counts", "type": "number_array", "label": "Species Counts (e.g. 12, 5, 30, 8)"},
             ]},
            {"key": "bio_2", "analysis_id": "simpson_diversity_index", "label": "Simpson Diversity Index", "number": "4.2",
             "premium": False, "needs_dataframe": False, "inputs": [
                {"name": "species_counts", "type": "number_array", "label": "Species Counts (e.g. 12, 5, 30, 8)"},
             ]},
            {"key": "bio_3", "analysis_id": "ecological_footprint", "label": "Ecological Footprint", "number": "4.3",
             "premium": False, "needs_dataframe": False, "inputs": [
                {"name": "consumption", "type": "number", "label": "Consumption"},
                {"name": "productivity", "type": "number", "label": "Productivity"},
             ]},
        ],
    },
    "RemoteSensing": {
        "label": "Remote Sensing & GIS",
        "description": "NDVI, EVI, land-use change matrix, Haversine distance, IDW spatial interpolation",
        "items": [
            {"key": "rs_1", "analysis_id": "ndvi_analysis", "label": "NDVI", "number": "5.1",
             "premium": True, "needs_dataframe": True, "inputs": [
                {"name": "nir_col", "type": "column_numeric", "label": "NIR Band Column"},
                {"name": "red_col", "type": "column_numeric", "label": "Red Band Column"},
             ]},
            {"key": "rs_2", "analysis_id": "evi_analysis", "label": "EVI", "number": "5.2",
             "premium": True, "needs_dataframe": True, "inputs": [
                {"name": "nir_col", "type": "column_numeric", "label": "NIR Band Column"},
                {"name": "red_col", "type": "column_numeric", "label": "Red Band Column"},
                {"name": "blue_col", "type": "column_numeric", "label": "Blue Band Column"},
             ]},
            {"key": "rs_3", "analysis_id": "land_use_change_matrix", "label": "Land-Use Change Matrix", "number": "5.3",
             "premium": False, "needs_dataframe": True, "inputs": [
                {"name": "initial_col", "type": "column_categorical", "label": "Initial Land-Use Column"},
                {"name": "final_col", "type": "column_categorical", "label": "Final Land-Use Column"},
             ]},
            {"key": "rs_4", "analysis_id": "haversine_distance", "label": "Haversine Distance", "number": "5.4",
             "premium": False, "needs_dataframe": False, "inputs": [
                {"name": "lat1", "type": "number", "label": "Latitude 1"},
                {"name": "lon1", "type": "number", "label": "Longitude 1"},
                {"name": "lat2", "type": "number", "label": "Latitude 2"},
                {"name": "lon2", "type": "number", "label": "Longitude 2"},
             ]},
            {"key": "rs_5", "analysis_id": "idw_interpolation", "label": "IDW Spatial Interpolation", "number": "5.5",
             "premium": True, "needs_dataframe": False, "inputs": [
                {"name": "points", "type": "point_value_list", "label": "Known Points (lat, lon, value)"},
                {"name": "target_lat", "type": "number", "label": "Target Latitude"},
                {"name": "target_lon", "type": "number", "label": "Target Longitude"},
                {"name": "power", "type": "number", "label": "Power Parameter (default 2)", "required": False},
             ]},
        ],
    },
    "Hydrology": {
        "label": "Hydrology",
        "description": "Runoff estimation, water balance, evapotranspiration",
        "items": [
            {"key": "hy_1", "analysis_id": "runoff_rational_method", "label": "Runoff (Rational Method)", "number": "6.1",
             "premium": False, "needs_dataframe": False, "inputs": [
                {"name": "runoff_coefficient", "type": "number", "label": "Runoff Coefficient (C)"},
                {"name": "rainfall_intensity", "type": "number", "label": "Rainfall Intensity (I)"},
                {"name": "area", "type": "number", "label": "Area (A)"},
             ]},
            {"key": "hy_2", "analysis_id": "water_balance", "label": "Water Balance", "number": "6.2",
             "premium": False, "needs_dataframe": False, "inputs": [
                {"name": "precipitation", "type": "number", "label": "Precipitation (P)"},
                {"name": "evapotranspiration", "type": "number", "label": "Evapotranspiration (ET)"},
                {"name": "runoff", "type": "number", "label": "Runoff (Q)"},
             ]},
            {"key": "hy_3", "analysis_id": "hargreaves_evapotranspiration", "label": "Evapotranspiration (Hargreaves)", "number": "6.3",
             "premium": False, "needs_dataframe": False, "inputs": [
                {"name": "t_mean", "type": "number", "label": "Mean Temperature"},
                {"name": "t_max", "type": "number", "label": "Max Temperature"},
                {"name": "t_min", "type": "number", "label": "Min Temperature"},
                {"name": "radiation", "type": "number", "label": "Extraterrestrial Radiation (Ra)"},
             ]},
        ],
    },
    "Sustainability": {
        "label": "Sustainability & ESG",
        "description": "Impact score, life cycle assessment, material flow, circularity rate, sustainability index, ESG score",
        "items": [
            {"key": "su_1", "analysis_id": "environmental_impact_score", "label": "Environmental Impact Score", "number": "7.1",
             "premium": True, "needs_dataframe": True, "inputs": [
                {"name": "indicator_cols", "type": "column_list", "label": "Indicator Columns (comma-separated)"},
                {"name": "weights", "type": "number_array", "label": "Weights (same order/count as columns)"},
             ]},
            {"key": "su_2", "analysis_id": "life_cycle_assessment", "label": "Life Cycle Assessment", "number": "7.2",
             "premium": False, "needs_dataframe": False, "inputs": [
                {"name": "activity_data", "type": "number_array", "label": "Activity Data (e.g. 100, 50, 20)"},
                {"name": "impact_factors", "type": "number_array", "label": "Impact Factors (same order/count)"},
             ]},
            {"key": "su_3", "analysis_id": "material_flow_balance", "label": "Material Flow Analysis", "number": "7.3",
             "premium": False, "needs_dataframe": False, "inputs": [
                {"name": "inputs", "type": "number", "label": "Material Inputs"},
                {"name": "outputs", "type": "number", "label": "Material Outputs"},
                {"name": "losses", "type": "number", "label": "Losses"},
             ]},
            {"key": "su_4", "analysis_id": "circularity_rate", "label": "Circularity Rate", "number": "7.4",
             "premium": False, "needs_dataframe": False, "inputs": [
                {"name": "reused_material", "type": "number", "label": "Reused Material"},
                {"name": "recycled_material", "type": "number", "label": "Recycled Material"},
                {"name": "total_material_input", "type": "number", "label": "Total Material Input"},
             ]},
            {"key": "su_5", "analysis_id": "sustainability_index", "label": "Sustainability Composite Index", "number": "7.5",
             "premium": True, "needs_dataframe": True, "inputs": [
                {"name": "indicator_cols", "type": "column_list", "label": "Indicator Columns (comma-separated)"},
                {"name": "weights", "type": "number_array", "label": "Weights (same order/count as columns)"},
             ]},
            {"key": "su_6", "analysis_id": "esg_score", "label": "ESG Score", "number": "7.6",
             "premium": False, "needs_dataframe": False, "inputs": [
                {"name": "environment_score", "type": "number", "label": "Environment Score (0-100)"},
                {"name": "social_score", "type": "number", "label": "Social Score (0-100)"},
                {"name": "governance_score", "type": "number", "label": "Governance Score (0-100)"},
                {"name": "weight_environment", "type": "number", "label": "Weight — Environment (default 0.33)", "required": False},
                {"name": "weight_social", "type": "number", "label": "Weight — Social (default 0.33)", "required": False},
                {"name": "weight_governance", "type": "number", "label": "Weight — Governance (default 0.34)", "required": False},
             ]},
        ],
    },
    "RiskScenario": {
        "label": "Risk & Scenario Analysis",
        "description": "Climate risk scoring, emissions scenario projections",
        "items": [
            {"key": "rk_1", "analysis_id": "climate_risk_score", "label": "Climate Risk Score", "number": "8.1",
             "premium": False, "needs_dataframe": False, "inputs": [
                {"name": "hazard", "type": "number", "label": "Hazard (0-1)"},
                {"name": "exposure", "type": "number", "label": "Exposure (0-1)"},
                {"name": "vulnerability", "type": "number", "label": "Vulnerability (0-1)"},
             ]},
            {"key": "rk_2", "analysis_id": "emissions_scenario_analysis", "label": "Emissions Scenario Analysis", "number": "8.2",
             "premium": False, "needs_dataframe": False, "inputs": [
                {"name": "base_emissions", "type": "number", "label": "Base Emissions"},
                {"name": "scenarios", "type": "scenario_list", "label": "Scenarios (name, % change)"},
             ]},
        ],
    },
}

ENVIRONMENTAL_MODULES = _ENVIRONMENTAL_MODULES

_ANALYSIS_ROUTER = {
    'climate_trend_analysis': climate_trend_analysis,
    'temperature_anomaly': temperature_anomaly,
    'rainfall_variability': rainfall_variability,
    'standardized_precipitation_index': standardized_precipitation_index,
    'heat_index_fahrenheit': heat_index_fahrenheit,
    'mann_kendall_trend_test': mann_kendall_trend_test,
    'sens_slope_estimator': sens_slope_estimator,
    'climate_arima_forecast': climate_arima_forecast,
    'total_carbon_emissions': total_carbon_emissions,
    'carbon_intensity': carbon_intensity,
    'energy_intensity': energy_intensity,
    'renewable_energy_share': renewable_energy_share,
    'carbon_payback_period': carbon_payback_period,
    'pollutant_aqi': pollutant_aqi,
    'water_quality_index': water_quality_index,
    'soil_quality_index': soil_quality_index,
    'shannon_diversity_index': shannon_diversity_index,
    'simpson_diversity_index': simpson_diversity_index,
    'ecological_footprint': ecological_footprint,
    'ndvi_analysis': ndvi_analysis,
    'evi_analysis': evi_analysis,
    'land_use_change_matrix': land_use_change_matrix,
    'haversine_distance': haversine_distance,
    'idw_interpolation': idw_interpolation,
    'runoff_rational_method': runoff_rational_method,
    'water_balance': water_balance,
    'hargreaves_evapotranspiration': hargreaves_evapotranspiration,
    'environmental_impact_score': environmental_impact_score,
    'life_cycle_assessment': life_cycle_assessment,
    'material_flow_balance': material_flow_balance,
    'circularity_rate': circularity_rate,
    'sustainability_index': sustainability_index,
    'esg_score': esg_score,
    'climate_risk_score': climate_risk_score,
    'emissions_scenario_analysis': emissions_scenario_analysis,
}


def get_environmental_catalog() -> dict:
    modules = []
    for key, mod in _ENVIRONMENTAL_MODULES.items():
        modules.append({
            'module_key': key,
            'label': mod['label'],
            'description': mod['description'],
            'items': mod['items'],
        })
    return {'modules': modules}


def run_environmental_analysis(analysis_id: str, df: pd.DataFrame, parameters: dict) -> dict:
    fn = _ANALYSIS_ROUTER.get(analysis_id)
    if not fn:
        return _err(f"'{analysis_id}' is not a recognised environmental analysis")
    try:
        return fn(df, parameters or {})
    except Exception as e:
        return _err(f'Unexpected error running {analysis_id}: {e}')


# ══════════════════════════════════════════════════════════════════════════
# SMART SUGGESTIONS — inspect a file's columns_meta and recommend specific
# environmental sub-tests, mirroring management_analytics.suggest_management_analyses().
# ══════════════════════════════════════════════════════════════════════════
def _is_id_col(c: dict) -> bool:
    n = c.get('name', '').lower()
    return 'id' in n or 'respondent' in n


def suggest_environmental_analyses(columns_meta: list) -> dict:
    if not columns_meta:
        return {'recommended': [], 'numeric_columns': [], 'categorical_columns': [], 'date_columns': []}

    numeric = [c for c in columns_meta if c.get('python_type') in ('integer', 'float') and not _is_id_col(c)]
    categorical = [c for c in columns_meta if c.get('python_type') == 'string' and not _is_id_col(c)]
    dates = [c for c in columns_meta if c.get('python_type') in ('datetime', 'date_string')]

    def find_col(keywords, pool):
        for c in pool:
            n = c['name'].lower()
            if any(k in n for k in keywords):
                return c['name']
        return None

    recommended = []

    temp_col = find_col(['temp', 'temperature'], numeric)
    if temp_col:
        recommended.append({
            'module_key': 'Climate', 'analysis_id': 'temperature_anomaly', 'item_key': 'cl_2',
            'label': 'Temperature Anomaly',
            'reason': f"'{temp_col}' looks like a temperature series — compute anomalies against its own baseline mean.",
            'prefill': {'temp_col': temp_col},
        })

    rain_col = find_col(['rain', 'precip'], numeric)
    if rain_col:
        recommended.append({
            'module_key': 'Climate', 'analysis_id': 'standardized_precipitation_index', 'item_key': 'cl_4',
            'label': 'SPI Drought Index',
            'reason': f"'{rain_col}' looks like a rainfall series — SPI can flag drought/wet periods.",
            'prefill': {'rainfall_col': rain_col},
        })

    trend_col = temp_col or rain_col or (numeric[0]['name'] if numeric else None)
    if trend_col:
        recommended.append({
            'module_key': 'Climate', 'analysis_id': 'climate_trend_analysis', 'item_key': 'cl_1',
            'label': 'Climate Trend Analysis',
            'reason': f"'{trend_col}' can be tested for a long-term increasing/decreasing trend.",
            'prefill': {'value_col': trend_col},
        })

    nir_col = find_col(['nir'], numeric)
    red_col = find_col(['red'], numeric)
    blue_col = find_col(['blue'], numeric)
    if nir_col and red_col:
        recommended.append({
            'module_key': 'RemoteSensing', 'analysis_id': 'ndvi_analysis', 'item_key': 'rs_1',
            'label': 'NDVI',
            'reason': f"'{nir_col}' and '{red_col}' look like NIR/Red spectral bands — compute vegetation index (NDVI).",
            'prefill': {'nir_col': nir_col, 'red_col': red_col},
        })
        if blue_col:
            recommended.append({
                'module_key': 'RemoteSensing', 'analysis_id': 'evi_analysis', 'item_key': 'rs_2',
                'label': 'EVI',
                'reason': f"'{nir_col}', '{red_col}' and '{blue_col}' together support the Enhanced Vegetation Index.",
                'prefill': {'nir_col': nir_col, 'red_col': red_col, 'blue_col': blue_col},
            })

    landuse_cols = [c['name'] for c in categorical if any(k in c['name'].lower() for k in ['landuse', 'land_use', 'land use', 'landcover', 'land_cover'])]
    if len(landuse_cols) >= 2:
        recommended.append({
            'module_key': 'RemoteSensing', 'analysis_id': 'land_use_change_matrix', 'item_key': 'rs_3',
            'label': 'Land-Use Change Matrix',
            'reason': f"'{landuse_cols[0]}' and '{landuse_cols[1]}' look like before/after land-use classes.",
            'prefill': {'initial_col': landuse_cols[0], 'final_col': landuse_cols[1]},
        })

    emission_col = find_col(['emission', 'co2', 'carbon'], numeric)
    activity_col = find_col(['activity', 'consumption', 'usage'], numeric)
    if emission_col:
        recommended.append({
            'module_key': 'CarbonEnergy', 'analysis_id': 'total_carbon_emissions', 'item_key': 'ce_1',
            'label': 'Carbon Emissions Accounting',
            'reason': f"'{emission_col}' looks like activity/emissions data — total it against an emission factor.",
            'prefill': {'activity_cols': [emission_col], 'emission_factors': [1.0]},
        })

    return {
        'recommended': recommended,
        'numeric_columns': [c['name'] for c in numeric],
        'categorical_columns': [c['name'] for c in categorical],
        'date_columns': [c['name'] for c in dates],
    }