"""
Universal Analytics Engine (RaaS Stage-1)
==========================================
Implements the full Stage-1 analytical services catalog:

  1. Descriptive Statistics
  2. Summary Statistics (numeric + categorical)
  3. Hypothesis Testing (t-tests, ANOVA, chi-square, F-test)
  4. Regression Analysis (linear, logistic, multinomial, quantile)
  5. Time Series Analysis (moving average, ADF, ARIMA, seasonal decomposition)
  6. Panel Data Analysis (pooled OLS, fixed effects, random effects)
  7. Data Visualization (chart-ready JSON for histogram, bar, line,
     scatter, box plot, correlation heatmap)

Design notes
------------
- This module is purely additive. It does NOT modify or call into
  services/learning_module.py or the Gemini AI flow in routes/analysis.py.
  Those remain completely untouched.
- Every function returns plain JSON-serialisable Python objects
  (dict / list / float / int / str) — no numpy types, no statsmodels
  Result objects — so it can be dumped directly with `json.dumps`.
- Heavy optional dependencies (statsmodels, scikit-learn, linearmodels)
  are imported lazily inside each function and fail gracefully with a
  clear error message if not installed, so the rest of the platform
  keeps working even if one optional package is missing.
"""

import math
import numpy as np
import pandas as pd


# ────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────

def _clean_number(value):
    """Convert numpy / pandas scalar to a JSON-safe Python float or None."""
    try:
        if value is None:
            return None
        if isinstance(value, (list, tuple)):
            return [_clean_number(v) for v in value]
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return None
        return round(f, 6)
    except (TypeError, ValueError):
        return None


def _numeric_columns(df: pd.DataFrame):
    return df.select_dtypes(include=[np.number]).columns.tolist()


def _categorical_columns(df: pd.DataFrame):
    return df.select_dtypes(include=['object', 'category', 'bool']).columns.tolist()


def _datetime_columns(df: pd.DataFrame):
    cols = df.select_dtypes(include=['datetime64[ns]', 'datetime64']).columns.tolist()
    # Also detect columns that *look* like dates by name/content
    for c in df.columns:
        if c in cols:
            continue
        name = str(c).lower()
        if any(k in name for k in ['date', 'time', 'day', 'month', 'year', 'period']):
            try:
                pd.to_datetime(df[c].dropna().head(20))
                cols.append(c)
            except Exception:
                pass
    return cols


def _interpret(p_value, alpha=0.05):
    if p_value is None:
        return 'Inconclusive'
    return 'Reject H0 — statistically significant' if p_value < alpha else 'Fail to reject H0 — not statistically significant'


# ────────────────────────────────────────────────────────────────────────────
# 1. Descriptive Statistics
# ────────────────────────────────────────────────────────────────────────────

def descriptive_statistics(df: pd.DataFrame, parameters=None) -> dict:
    """Mean, median, mode, min, max, range, variance, std, CV, skew, kurtosis.

    Optional parameter `columns`: list of column names to restrict the
    analysis to. If omitted/empty, runs on every numeric column (default
    behaviour, unchanged).
    """
    parameters = parameters or {}
    numeric_df = df.select_dtypes(include=[np.number])

    selected = parameters.get('columns') or []
    if selected:
        missing = [c for c in selected if c not in numeric_df.columns]
        if missing:
            return {'error': f'Column(s) not found or not numeric: {", ".join(missing)}'}
        numeric_df = numeric_df[selected]

    if numeric_df.empty:
        return {'error': 'No numeric columns found for descriptive statistics.'}

    rows = []
    for col in numeric_df.columns:
        series = numeric_df[col].dropna()
        if series.empty:
            continue
        mean = series.mean()
        std = series.std()
        mode_vals = series.mode()
        rows.append({
            'column': col,
            'count': int(series.count()),
            'mean': _clean_number(mean),
            'median': _clean_number(series.median()),
            'mode': _clean_number(mode_vals.iloc[0]) if not mode_vals.empty else None,
            'min': _clean_number(series.min()),
            'max': _clean_number(series.max()),
            'range': _clean_number(series.max() - series.min()),
            'variance': _clean_number(series.var()),
            'std_dev': _clean_number(std),
            'coefficient_of_variation_pct': _clean_number((std / mean) * 100) if mean else None,
            'skewness': _clean_number(series.skew()),
            'kurtosis': _clean_number(series.kurtosis()),
        })

    return {
        'type': 'descriptive_statistics',
        'category': 'Descriptive Statistics',
        'columns_analyzed': [r['column'] for r in rows],
        'results': rows,
    }


# ────────────────────────────────────────────────────────────────────────────
# 2. Summary Statistics (numeric + categorical)
# ────────────────────────────────────────────────────────────────────────────

def summary_statistics_uae(df: pd.DataFrame, parameters=None) -> dict:
    """Compact numeric + categorical overview: count, missing, unique, percentiles.

    Optional parameter `columns`: list of column names to restrict the
    analysis to (applies to both numeric and categorical columns). If
    omitted/empty, runs on every column (default behaviour, unchanged).
    """
    parameters = parameters or {}
    selected = parameters.get('columns') or []

    numeric_df = df.select_dtypes(include=[np.number])
    cat_df = df.select_dtypes(include=['object', 'category', 'bool'])

    if selected:
        numeric_df = numeric_df[[c for c in selected if c in numeric_df.columns]]
        cat_df = cat_df[[c for c in selected if c in cat_df.columns]]

    numeric_rows = []
    if not numeric_df.empty:
        desc = numeric_df.describe().T
        for col in numeric_df.columns:
            row = desc.loc[col]
            numeric_rows.append({
                'column': col,
                'count': int(row.get('count', 0)),
                'mean': _clean_number(row.get('mean')),
                'std': _clean_number(row.get('std')),
                'min': _clean_number(row.get('min')),
                'q25': _clean_number(row.get('25%')),
                'median': _clean_number(row.get('50%')),
                'q75': _clean_number(row.get('75%')),
                'max': _clean_number(row.get('max')),
                'missing_values': int(df[col].isna().sum()),
                'missing_percentage': _clean_number(df[col].isna().sum() / len(df) * 100) if len(df) else 0,
                'unique_values': int(df[col].nunique()),
            })

    categorical_rows = []
    for col in cat_df.columns:
        series = cat_df[col].dropna()
        if series.empty:
            continue
        vc = series.value_counts()
        total = len(series)
        categorical_rows.append({
            'column': col,
            'unique_categories': int(series.nunique()),
            'most_frequent': str(vc.index[0]),
            'most_frequent_count': int(vc.iloc[0]),
            'missing_values': int(df[col].isna().sum()),
            'missing_percentage': _clean_number(df[col].isna().sum() / len(df) * 100) if len(df) else 0,
            'frequency_table': [
                {'value': str(k), 'count': int(v), 'percentage': _clean_number(v / total * 100)}
                for k, v in vc.head(10).items()
            ],
        })

    return {
        'type': 'summary_statistics_uae',
        'category': 'Summary Statistics',
        'row_count': int(len(df)),
        'column_count': int(len(df.columns)),
        'numeric_summary': numeric_rows,
        'categorical_summary': categorical_rows,
    }


# ────────────────────────────────────────────────────────────────────────────
# 3. Hypothesis Testing
# ────────────────────────────────────────────────────────────────────────────

def one_sample_ttest(df: pd.DataFrame, parameters: dict) -> dict:
    from scipy import stats
    column = parameters.get('column')
    population_mean = float(parameters.get('population_mean', 0))

    if column not in df.columns:
        return {'error': f'Column "{column}" not found.'}

    data = pd.to_numeric(df[column], errors='coerce').dropna()
    if len(data) < 2:
        return {'error': 'Not enough numeric data points (need at least 2).'}

    t_stat, p_value = stats.ttest_1samp(data, population_mean)
    return {
        'type': 'one_sample_ttest',
        'category': 'Hypothesis Testing',
        'test': 'One-sample t-test',
        'column': column,
        'sample_mean': _clean_number(data.mean()),
        'population_mean': population_mean,
        'sample_size': int(len(data)),
        't_statistic': _clean_number(t_stat),
        'p_value': _clean_number(p_value),
        'interpretation': _interpret(p_value),
    }


def independent_ttest(df: pd.DataFrame, parameters: dict) -> dict:
    from scipy import stats
    value_col = parameters.get('value_col') or _first_numeric_col(df)
    # prefer a categorical column with exactly 2 groups; else first categorical
    group_col = parameters.get('group_col')
    if not group_col:
        two_grp = [c for c in _all_categorical_cols(df) if df[c].nunique() == 2]
        group_col = two_grp[0] if two_grp else _first_categorical_col(df)
    group1 = parameters.get('group1')
    group2 = parameters.get('group2')

    if not value_col or not group_col or value_col not in df.columns or group_col not in df.columns:
        return {'error': 'Independent t-Test needs one numeric column and one group column.'}

    groups_available = df[group_col].dropna().unique().tolist()
    if group1 is None or group2 is None:
        if len(groups_available) < 2:
            return {'error': f'Column "{group_col}" needs at least 2 distinct groups.'}
        group1, group2 = groups_available[0], groups_available[1]

    data1 = pd.to_numeric(df[df[group_col] == group1][value_col], errors='coerce').dropna()
    data2 = pd.to_numeric(df[df[group_col] == group2][value_col], errors='coerce').dropna()

    if len(data1) < 2 or len(data2) < 2:
        return {'error': 'Each group needs at least 2 numeric data points.'}

    t_stat, p_value = stats.ttest_ind(data1, data2, equal_var=False)
    return {
        'type': 'independent_ttest',
        'category': 'Hypothesis Testing',
        'test': 'Independent two-sample t-test (Welch)',
        'value_col': value_col,
        'group_col': group_col,
        'group1': str(group1),
        'group2': str(group2),
        'group1_mean': _clean_number(data1.mean()),
        'group2_mean': _clean_number(data2.mean()),
        'group1_n': int(len(data1)),
        'group2_n': int(len(data2)),
        't_statistic': _clean_number(t_stat),
        'p_value': _clean_number(p_value),
        'interpretation': _interpret(p_value),
    }


def paired_ttest(df: pd.DataFrame, parameters: dict) -> dict:
    from scipy import stats
    before_col = parameters.get('before_col')
    after_col = parameters.get('after_col')

    for c in (before_col, after_col):
        if c not in df.columns:
            return {'error': f'Column "{c}" not found.'}

    paired = df[[before_col, after_col]].apply(pd.to_numeric, errors='coerce').dropna()
    if len(paired) < 2:
        return {'error': 'Not enough paired numeric observations (need at least 2).'}

    t_stat, p_value = stats.ttest_rel(paired[before_col], paired[after_col])
    return {
        'type': 'paired_ttest',
        'category': 'Hypothesis Testing',
        'test': 'Paired t-test',
        'before_col': before_col,
        'after_col': after_col,
        'mean_before': _clean_number(paired[before_col].mean()),
        'mean_after': _clean_number(paired[after_col].mean()),
        'mean_difference': _clean_number((paired[after_col] - paired[before_col]).mean()),
        'sample_size': int(len(paired)),
        't_statistic': _clean_number(t_stat),
        'p_value': _clean_number(p_value),
        'interpretation': _interpret(p_value),
    }


def one_way_anova(df: pd.DataFrame, parameters: dict) -> dict:
    from scipy import stats
    value_col = parameters.get('value_col') or _first_numeric_col(df)
    group_col = parameters.get('group_col') or _first_categorical_col(df)
    if not value_col or not group_col or value_col not in df.columns or group_col not in df.columns:
        return {'error': 'ANOVA needs one numeric column and one category column.'}

    groups = []
    group_names = []
    group_summaries = []
    for name, group in df.groupby(group_col):
        series = pd.to_numeric(group[value_col], errors='coerce').dropna()
        if len(series) >= 2:
            groups.append(series)
            group_names.append(str(name))
            group_summaries.append({
                'group': str(name),
                'n': int(len(series)),
                'mean': _clean_number(series.mean()),
                'std': _clean_number(series.std()),
            })

    if len(groups) < 2:
        return {'error': f'Need at least 2 groups with 2+ numeric values each in "{group_col}".'}

    f_stat, p_value = stats.f_oneway(*groups)
    return {
        'type': 'anova',
        'category': 'Hypothesis Testing',
        'test': 'One-way ANOVA',
        'value_col': value_col,
        'group_col': group_col,
        'groups': group_summaries,
        'f_statistic': _clean_number(f_stat),
        'p_value': _clean_number(p_value),
        'interpretation': _interpret(p_value),
    }


def chi_square_test(df: pd.DataFrame, parameters: dict) -> dict:
    from scipy import stats
    # Auto-pick two different categorical columns if not provided
    cat_cols = _all_categorical_cols(df)
    col1 = parameters.get('col1') or (cat_cols[0] if len(cat_cols) >= 1 else None)
    col2 = parameters.get('col2') or (cat_cols[1] if len(cat_cols) >= 2 else None)
    if not col1 or not col2 or col1 not in df.columns or col2 not in df.columns:
        return {'error': 'Chi-Square needs two category columns.'}

    table = pd.crosstab(df[col1], df[col2])
    if table.shape[0] < 2 or table.shape[1] < 2:
        return {'error': 'Both columns need at least 2 distinct categories each.'}

    chi2, p_value, dof, expected = stats.chi2_contingency(table)
    return {
        'type': 'chi_square',
        'category': 'Hypothesis Testing',
        'test': 'Chi-square test of independence',
        'col1': col1,
        'col2': col2,
        'chi_square_statistic': _clean_number(chi2),
        'p_value': _clean_number(p_value),
        'degrees_of_freedom': int(dof),
        'observed_table': {
            'columns': [str(c) for c in table.columns.tolist()],
            'index': [str(i) for i in table.index.tolist()],
            'values': table.values.tolist(),
        },
        'interpretation': _interpret(p_value),
    }


def f_test_variance(df: pd.DataFrame, parameters: dict) -> dict:
    from scipy import stats
    value_col = parameters.get('value_col') or _first_numeric_col(df)
    # prefer a categorical column with exactly 2 groups; else first categorical
    group_col = parameters.get('group_col')
    if not group_col:
        two_grp = [c for c in _all_categorical_cols(df) if df[c].nunique() == 2]
        group_col = two_grp[0] if two_grp else _first_categorical_col(df)
    group1 = parameters.get('group1')
    group2 = parameters.get('group2')

    if not value_col or not group_col or value_col not in df.columns or group_col not in df.columns:
        return {'error': 'Independent t-Test needs one numeric column and one group column.'}

    groups_available = df[group_col].dropna().unique().tolist()
    if group1 is None or group2 is None:
        if len(groups_available) < 2:
            return {'error': f'Column "{group_col}" needs at least 2 distinct groups.'}
        group1, group2 = groups_available[0], groups_available[1]

    data1 = pd.to_numeric(df[df[group_col] == group1][value_col], errors='coerce').dropna()
    data2 = pd.to_numeric(df[df[group_col] == group2][value_col], errors='coerce').dropna()

    if len(data1) < 2 or len(data2) < 2:
        return {'error': 'Each group needs at least 2 numeric data points.'}

    var1 = np.var(data1, ddof=1)
    var2 = np.var(data2, ddof=1)
    if var2 == 0:
        return {'error': f'Variance of group "{group2}" is zero — F-test undefined.'}

    f_stat = var1 / var2
    dfn = len(data1) - 1
    dfd = len(data2) - 1
    p_value = 2 * min(
        stats.f.cdf(f_stat, dfn, dfd),
        1 - stats.f.cdf(f_stat, dfn, dfd)
    )

    return {
        'type': 'f_test',
        'category': 'Hypothesis Testing',
        'test': 'F-test for equality of variances',
        'value_col': value_col,
        'group_col': group_col,
        'group1': str(group1),
        'group2': str(group2),
        'variance1': _clean_number(var1),
        'variance2': _clean_number(var2),
        'f_statistic': _clean_number(f_stat),
        'p_value': _clean_number(p_value),
        'interpretation': _interpret(p_value),
    }


# ────────────────────────────────────────────────────────────────────────────
# 4. Regression Analysis
# ────────────────────────────────────────────────────────────────────────────

def _prep_xy(df, dependent_var, independent_vars):
    cols = [dependent_var] + list(independent_vars)
    missing = [c for c in cols if c not in df.columns]
    if missing:
        return None, None, f'Column(s) not found: {", ".join(missing)}'

    data = df[cols].apply(pd.to_numeric, errors='coerce').dropna()
    if len(data) < len(independent_vars) + 2:
        return None, None, 'Not enough complete numeric rows for this regression.'

    X = data[independent_vars]
    y = data[dependent_var]
    return X, y, None


def _prep_xy_classification(df, dependent_var, independent_vars):
    """Like _prep_xy, but the dependent variable is kept as-is (categorical/text),
    while independent variables are coerced to numeric. Used for logistic and
    multinomial logit, where the outcome is a category, not a continuous number."""
    cols = [dependent_var] + list(independent_vars)
    missing = [c for c in cols if c not in df.columns]
    if missing:
        return None, None, f'Column(s) not found: {", ".join(missing)}'

    data = df[cols].copy()
    for c in independent_vars:
        data[c] = pd.to_numeric(data[c], errors='coerce')
    data = data.dropna()

    if len(data) < len(independent_vars) + 2:
        return None, None, 'Not enough complete rows for this regression.'

    X = data[independent_vars]
    y = data[dependent_var]
    return X, y, None


def linear_regression(df: pd.DataFrame, parameters: dict) -> dict:
    try:
        import statsmodels.api as sm
    except ImportError:
        return {'error': 'statsmodels is not installed on the server.'}

    nums = _all_numeric_cols(df)
    dependent_var = parameters.get('dependent_var') or (nums[0] if len(nums) >= 1 else None)
    independent_vars = parameters.get('independent_vars') or [c for c in nums if c != dependent_var][:3]
    if not dependent_var or not independent_vars:
        return {'error': 'Linear Regression needs at least two numeric columns (one target + one predictor).'}

    X, y, err = _prep_xy(df, dependent_var, independent_vars)
    if err:
        return {'error': err}

    X_const = sm.add_constant(X)
    model = sm.OLS(y, X_const, missing='drop').fit()

    coefficients = []
    for name in X_const.columns:
        coefficients.append({
            'variable': name,
            'coefficient': _clean_number(model.params.get(name)),
            'std_error': _clean_number(model.bse.get(name)),
            't_value': _clean_number(model.tvalues.get(name)),
            'p_value': _clean_number(model.pvalues.get(name)),
        })

    return {
        'type': 'linear_regression',
        'category': 'Regression Analysis',
        'dependent_var': dependent_var,
        'independent_vars': independent_vars,
        'observations': int(model.nobs),
        'r_squared': _clean_number(model.rsquared),
        'adj_r_squared': _clean_number(model.rsquared_adj),
        'f_statistic': _clean_number(model.fvalue),
        'f_pvalue': _clean_number(model.f_pvalue),
        'coefficients': coefficients,
        'equation': _build_equation(dependent_var, coefficients),
    }


def _build_equation(dependent_var, coefficients):
    parts = []
    for c in coefficients:
        coef = c['coefficient']
        if coef is None:
            continue
        var = 'Intercept' if c['variable'] == 'const' else c['variable']
        parts.append(f"{coef:+.4f}·{var}" if var != 'Intercept' else f"{coef:+.4f}")
    return f"{dependent_var} = " + ' '.join(parts) if parts else None


def logistic_regression(df: pd.DataFrame, parameters: dict) -> dict:
    try:
        import statsmodels.api as sm
    except ImportError:
        return {'error': 'statsmodels is not installed on the server.'}

    # Auto-pick a binary column as target + numeric predictors
    dependent_var = parameters.get('dependent_var')
    if not dependent_var:
        binary_cols = [c for c in df.columns if not _is_junk(c) and df[c].nunique() == 2
                       and 'id' not in str(c).lower()]
        dependent_var = binary_cols[0] if binary_cols else None
    nums = _all_numeric_cols(df)
    independent_vars = parameters.get('independent_vars') or [c for c in nums if c != dependent_var][:3]
    if not dependent_var or not independent_vars:
        return {'error': 'Logistic Regression needs a binary target column and numeric predictors. This dataset may not have a binary column.'}

    X, y, err = _prep_xy_classification(df, dependent_var, independent_vars)
    if err:
        return {'error': err}

    unique_y = sorted(y.unique().tolist(), key=lambda v: str(v))
    if len(unique_y) != 2:
        return {'error': f'Logistic regression requires a binary dependent variable. "{dependent_var}" has {len(unique_y)} unique values: {unique_y[:5]}'}

    # map to 0/1
    y_bin = (y == unique_y[1]).astype(int)
    X_const = sm.add_constant(X)

    try:
        model = sm.Logit(y_bin, X_const, missing='drop').fit(disp=0)
    except Exception as e:
        return {'error': f'Logistic regression failed to converge: {e}'}

    coefficients = []
    for name in X_const.columns:
        coef = model.params.get(name)
        coefficients.append({
            'variable': name,
            'coefficient': _clean_number(coef),
            'odds_ratio': _clean_number(math.exp(coef)) if coef is not None else None,
            'std_error': _clean_number(model.bse.get(name)),
            'p_value': _clean_number(model.pvalues.get(name)),
        })

    return {
        'type': 'logistic_regression',
        'category': 'Regression Analysis',
        'dependent_var': dependent_var,
        'positive_class': str(unique_y[1]),
        'negative_class': str(unique_y[0]),
        'independent_vars': independent_vars,
        'observations': int(model.nobs),
        'pseudo_r_squared': _clean_number(model.prsquared),
        'log_likelihood': _clean_number(model.llf),
        'coefficients': coefficients,
    }


def multinomial_logit(df: pd.DataFrame, parameters: dict) -> dict:
    try:
        import statsmodels.api as sm
    except ImportError:
        return {'error': 'statsmodels is not installed on the server.'}

    # Auto-pick a binary column as target + numeric predictors
    dependent_var = parameters.get('dependent_var')
    if not dependent_var:
        binary_cols = [c for c in df.columns if not _is_junk(c) and df[c].nunique() == 2
                       and 'id' not in str(c).lower()]
        dependent_var = binary_cols[0] if binary_cols else None
    nums = _all_numeric_cols(df)
    independent_vars = parameters.get('independent_vars') or [c for c in nums if c != dependent_var][:3]
    if not dependent_var or not independent_vars:
        return {'error': 'Logistic Regression needs a binary target column and numeric predictors. This dataset may not have a binary column.'}

    X, y, err = _prep_xy_classification(df, dependent_var, independent_vars)
    if err:
        return {'error': err}

    unique_y = sorted(y.unique().tolist(), key=lambda v: str(v))
    if len(unique_y) < 3:
        return {'error': f'Multinomial logistic regression requires 3+ categories in "{dependent_var}" (found {len(unique_y)}).'}
    if len(unique_y) > 8:
        return {'error': f'Too many categories ({len(unique_y)}) in "{dependent_var}" for multinomial regression.'}

    # Map categories to integer codes 0..k-1 for MNLogit
    cat_to_code = {cat: i for i, cat in enumerate(unique_y)}
    y_coded = y.map(cat_to_code)

    X_const = sm.add_constant(X)
    try:
        model = sm.MNLogit(y_coded, X_const, missing='drop').fit(disp=0)
    except Exception as e:
        return {'error': f'Multinomial logistic regression failed: {e}'}

    params = model.params  # DataFrame: rows=vars, cols=outcome categories (excluding base)
    coefficients = []
    for outcome_col in params.columns:
        for var_name in params.index:
            coefficients.append({
                'outcome': str(unique_y[outcome_col + 1]) if outcome_col + 1 < len(unique_y) else str(outcome_col),
                'variable': var_name,
                'coefficient': _clean_number(params.loc[var_name, outcome_col]),
            })

    return {
        'type': 'multinomial_logit',
        'category': 'Regression Analysis',
        'dependent_var': dependent_var,
        'categories': [str(u) for u in unique_y],
        'base_category': str(unique_y[0]),
        'independent_vars': independent_vars,
        'observations': int(model.nobs),
        'log_likelihood': _clean_number(model.llf),
        'coefficients': coefficients,
    }


def quantile_regression(df: pd.DataFrame, parameters: dict) -> dict:
    try:
        import statsmodels.formula.api as smf
    except ImportError:
        return {'error': 'statsmodels is not installed on the server.'}

    nums = _all_numeric_cols(df)
    dependent_var = parameters.get('dependent_var') or (nums[0] if len(nums) >= 1 else None)
    independent_vars = parameters.get('independent_vars') or [c for c in nums if c != dependent_var][:3]
    quantiles = parameters.get('quantiles') or [0.25, 0.5, 0.75]

    if not dependent_var or not independent_vars:
        return {'error': 'Quantile Regression needs at least two numeric columns.'}

    cols = [dependent_var] + list(independent_vars)
    missing = [c for c in cols if c not in df.columns]
    if missing:
        return {'error': f'Column(s) not found: {", ".join(missing)}'}

    data = df[cols].apply(pd.to_numeric, errors='coerce').dropna()
    if len(data) < len(independent_vars) + 2:
        return {'error': 'Not enough complete numeric rows for quantile regression.'}

    # sanitise column names for the formula API (no spaces/special chars)
    safe_map = {c: f'v{i}' for i, c in enumerate(cols)}
    safe_data = data.rename(columns=safe_map)
    formula = f"{safe_map[dependent_var]} ~ " + ' + '.join(safe_map[c] for c in independent_vars)

    results_by_quantile = []
    for q in quantiles:
        try:
            model = smf.quantreg(formula, safe_data).fit(q=q)
            coefficients = [
                {'variable': cols[list(safe_map.values()).index(name)] if name in safe_map.values() else name,
                 'coefficient': _clean_number(model.params.get(name))}
                for name in model.params.index
            ]
            results_by_quantile.append({
                'quantile': q,
                'observations': int(model.nobs),
                'coefficients': coefficients,
            })
        except Exception as e:
            results_by_quantile.append({'quantile': q, 'error': str(e)})

    return {
        'type': 'quantile_regression',
        'category': 'Regression Analysis',
        'dependent_var': dependent_var,
        'independent_vars': independent_vars,
        'results_by_quantile': results_by_quantile,
    }


# ────────────────────────────────────────────────────────────────────────────
# 5. Time Series Analysis
# ────────────────────────────────────────────────────────────────────────────

def _first_date_col(df):
    """Find the first column that looks like a date/time index."""
    TIME_KW = ('month','date','week','quarter','period','time','year')
    # First: column name contains a time keyword
    for c in df.columns:
        if _is_junk(c):
            continue
        if any(k in str(c).lower() for k in TIME_KW):
            return c
    # Second: any column that parses as datetime
    for c in df.columns:
        if _is_junk(c):
            continue
        try:
            parsed = pd.to_datetime(df[c], errors='coerce')
            if parsed.notna().sum() >= len(df) * 0.7:
                return c
        except Exception:
            pass
    return None

def _prep_timeseries(df, date_col, value_col):
    # Auto-select a date column and a numeric value column if not provided
    if not date_col:
        date_col = _first_date_col(df)
    if not value_col:
        nums = _all_numeric_cols(df)
        # don't use the date col as the value col
        value_col = next((c for c in nums if c != date_col), None)
    if not date_col or not value_col or date_col not in df.columns or value_col not in df.columns:
        return None, 'Time series needs a date column and a numeric value column.', None, None

    data = df[[date_col, value_col]].copy()
    data[value_col] = pd.to_numeric(data[value_col], errors='coerce')
    data = data.dropna()
    try:
        data[date_col] = pd.to_datetime(data[date_col])
    except Exception:
        return None, f'Column "{date_col}" could not be parsed as dates.', None, None

    data = data.sort_values(date_col)
    if len(data) < 4:
        return None, 'Not enough time-ordered data points (need at least 4).', None, None
    return data, None, date_col, value_col


def moving_average(df: pd.DataFrame, parameters: dict) -> dict:
    date_col = parameters.get('date_col')
    value_col = parameters.get('value_col')
    window = int(parameters.get('window', 3))

    data, err, date_col, value_col = _prep_timeseries(df, date_col, value_col)
    if err:
        return {'error': err}

    data[f'ma_{window}'] = data[value_col].rolling(window=window).mean()

    series = [
        {
            'date': row[date_col].strftime('%Y-%m-%d'),
            'value': _clean_number(row[value_col]),
            'moving_average': _clean_number(row[f'ma_{window}']),
        }
        for _, row in data.tail(200).iterrows()
    ]

    return {
        'type': 'moving_average',
        'category': 'Time Series Analysis',
        'date_col': date_col,
        'value_col': value_col,
        'window': window,
        'points': len(data),
        'series': series,
    }


def time_series_adf(df: pd.DataFrame, parameters: dict) -> dict:
    try:
        from statsmodels.tsa.stattools import adfuller
    except ImportError:
        return {'error': 'statsmodels is not installed on the server.'}

    value_col = parameters.get('value_col') or _first_numeric_col(df)
    if not value_col or value_col not in df.columns:
        return {'error': 'ADF test needs a numeric column.'}

    data = pd.to_numeric(df[value_col], errors='coerce').dropna()
    if len(data) < 8:
        return {'error': 'Not enough data points for ADF test (need at least 8).'}

    result = adfuller(data)
    return {
        'type': 'time_series_adf',
        'category': 'Time Series Analysis',
        'test': 'Augmented Dickey-Fuller Test',
        'value_col': value_col,
        'adf_statistic': _clean_number(result[0]),
        'p_value': _clean_number(result[1]),
        'lags_used': int(result[2]),
        'observations': int(result[3]),
        'critical_values': {k: _clean_number(v) for k, v in result[4].items()},
        'interpretation': 'Stationary (no unit root)' if result[1] < 0.05 else 'Non-stationary (unit root present)',
    }


def time_series_arima(df: pd.DataFrame, parameters: dict) -> dict:
    try:
        from statsmodels.tsa.arima.model import ARIMA
    except ImportError:
        return {'error': 'statsmodels is not installed on the server.'}

    date_col = parameters.get('date_col')
    value_col = parameters.get('value_col')
    order = tuple(parameters.get('order', [1, 1, 1]))
    forecast_steps = int(parameters.get('forecast_steps', 5))

    data, err, date_col, value_col = _prep_timeseries(df, date_col, value_col)
    if err:
        return {'error': err}
    if len(data) < 10:
        return {'error': 'ARIMA needs at least 10 time-ordered observations.'}

    series = data.set_index(date_col)[value_col]

    try:
        model = ARIMA(series, order=order)
        fitted = model.fit()
        forecast = fitted.forecast(steps=forecast_steps)
    except Exception as e:
        return {'error': f'ARIMA model failed to fit: {e}'}

    last_date = series.index[-1]
    freq = pd.infer_freq(series.index) or 'D'
    try:
        future_dates = pd.date_range(start=last_date, periods=forecast_steps + 1, freq=freq)[1:]
    except Exception:
        future_dates = [last_date + pd.Timedelta(days=i + 1) for i in range(forecast_steps)]

    return {
        'type': 'time_series_arima',
        'category': 'Time Series Analysis',
        'date_col': date_col,
        'value_col': value_col,
        'order': list(order),
        'aic': _clean_number(fitted.aic),
        'bic': _clean_number(fitted.bic),
        'forecast': [
            {'date': str(d.date()) if hasattr(d, 'date') else str(d), 'forecast': _clean_number(v)}
            for d, v in zip(future_dates, forecast.tolist())
        ],
    }


def seasonal_decomposition_uae(df: pd.DataFrame, parameters: dict) -> dict:
    try:
        from statsmodels.tsa.seasonal import seasonal_decompose
    except ImportError:
        return {'error': 'statsmodels is not installed on the server.'}

    date_col = parameters.get('date_col')
    value_col = parameters.get('value_col')
    period = parameters.get('period')

    data, err, date_col, value_col = _prep_timeseries(df, date_col, value_col)
    if err:
        return {'error': err}

    if not period:
        period = 12 if len(data) >= 24 else max(2, len(data) // 2)
    period = int(period)

    if len(data) < period * 2:
        return {'error': f'Need at least {period * 2} observations for period={period}.'}

    series = data.set_index(date_col)[value_col]
    try:
        result = seasonal_decompose(series, model='additive', period=period)
    except Exception as e:
        return {'error': f'Seasonal decomposition failed: {e}'}

    def to_series(component):
        out = []
        for d, v in component.dropna().tail(100).items():
            out.append({'date': str(d.date()) if hasattr(d, 'date') else str(d), 'value': _clean_number(v)})
        return out

    return {
        'type': 'seasonal_decomposition',
        'category': 'Time Series Analysis',
        'date_col': date_col,
        'value_col': value_col,
        'period': period,
        'trend': to_series(result.trend),
        'seasonal': to_series(result.seasonal),
        'residual': to_series(result.resid),
    }


# ────────────────────────────────────────────────────────────────────────────
# 6. Panel Data Analysis
# ────────────────────────────────────────────────────────────────────────────

def _prep_panel(df, entity_col, time_col, dependent_var, independent_vars):
    cols = [entity_col, time_col, dependent_var] + list(independent_vars)
    missing = [c for c in cols if c not in df.columns]
    if missing:
        return None, f'Column(s) not found: {", ".join(missing)}'

    data = df[cols].copy()
    for c in [dependent_var] + list(independent_vars):
        data[c] = pd.to_numeric(data[c], errors='coerce')
    data = data.dropna()

    if data[entity_col].nunique() < 2:
        return None, f'Need at least 2 distinct entities in "{entity_col}".'
    if data[time_col].nunique() < 2:
        return None, f'Need at least 2 distinct time periods in "{time_col}".'

    data = data.set_index([entity_col, time_col])
    return data, None


def _panel_summary(results, model_name, dependent_var, independent_vars):
    try:
        params = results.params
        pvalues = results.pvalues
        coefficients = [
            {'variable': name, 'coefficient': _clean_number(params[name]), 'p_value': _clean_number(pvalues[name])}
            for name in params.index
        ]
    except Exception:
        coefficients = []

    return {
        'category': 'Panel Data Analysis',
        'model': model_name,
        'dependent_var': dependent_var,
        'independent_vars': independent_vars,
        'observations': _clean_number(getattr(results, 'nobs', None)),
        'r_squared': _clean_number(getattr(results, 'rsquared', None)),
        'coefficients': coefficients,
    }


def pooled_ols_model(df: pd.DataFrame, parameters: dict) -> dict:
    try:
        from linearmodels.panel import PooledOLS
        import statsmodels.api as sm
    except ImportError:
        return {'error': 'linearmodels package is not installed on the server. Run: pip install linearmodels'}

    entity_col = parameters.get('entity_col')
    time_col = parameters.get('time_col')
    dependent_var = parameters.get('dependent_var')
    independent_vars = parameters.get('independent_vars') or []

    data, err = _prep_panel(df, entity_col, time_col, dependent_var, independent_vars)
    if err:
        return {'error': err}

    y = data[dependent_var]
    X = sm.add_constant(data[independent_vars])

    try:
        model = PooledOLS(y, X)
        results = model.fit(cov_type='robust')
    except Exception as e:
        return {'error': f'Pooled OLS failed: {e}'}

    out = {'type': 'pooled_ols', **_panel_summary(results, 'Pooled OLS', dependent_var, independent_vars)}
    return out


def fixed_effects_model(df: pd.DataFrame, parameters: dict) -> dict:
    try:
        from linearmodels.panel import PanelOLS
        import statsmodels.api as sm
    except ImportError:
        return {'error': 'linearmodels package is not installed on the server. Run: pip install linearmodels'}

    entity_col = parameters.get('entity_col')
    time_col = parameters.get('time_col')
    dependent_var = parameters.get('dependent_var')
    independent_vars = parameters.get('independent_vars') or []

    data, err = _prep_panel(df, entity_col, time_col, dependent_var, independent_vars)
    if err:
        return {'error': err}

    y = data[dependent_var]
    X = sm.add_constant(data[independent_vars])

    try:
        model = PanelOLS(y, X, entity_effects=True)
        results = model.fit(cov_type='robust')
    except Exception as e:
        return {'error': f'Fixed effects model failed: {e}'}

    return {'type': 'fixed_effects', **_panel_summary(results, 'Fixed Effects (entity)', dependent_var, independent_vars)}


def random_effects_model(df: pd.DataFrame, parameters: dict) -> dict:
    try:
        from linearmodels.panel import RandomEffects
        import statsmodels.api as sm
    except ImportError:
        return {'error': 'linearmodels package is not installed on the server. Run: pip install linearmodels'}

    entity_col = parameters.get('entity_col')
    time_col = parameters.get('time_col')
    dependent_var = parameters.get('dependent_var')
    independent_vars = parameters.get('independent_vars') or []

    data, err = _prep_panel(df, entity_col, time_col, dependent_var, independent_vars)
    if err:
        return {'error': err}

    y = data[dependent_var]
    X = sm.add_constant(data[independent_vars])

    try:
        model = RandomEffects(y, X)
        results = model.fit()
    except Exception as e:
        return {'error': f'Random effects model failed: {e}'}

    return {'type': 'random_effects', **_panel_summary(results, 'Random Effects', dependent_var, independent_vars)}


# ────────────────────────────────────────────────────────────────────────────
# 7. Data Visualization — returns chart-ready JSON (Recharts compatible)
# ────────────────────────────────────────────────────────────────────────────

# ── Auto-column-selection helpers ─────────────────────────────────────────
_JUNK_COLS = {'tests','test','data types','data type','notes','legend','description','remarks','comments'}

def _is_junk(col):
    return str(col).strip().lower() in _JUNK_COLS or str(col).lower().startswith('unnamed')

def _first_numeric_col(df, exclude_id=True):
    """Return the first meaningful numeric column."""
    for c in df.columns:
        if _is_junk(c):
            continue
        name = str(c).lower()
        if exclude_id and ('id' in name or 'respondent' in name):
            continue
        s = pd.to_numeric(df[c], errors='coerce')
        if s.notna().sum() > 0:
            return c
    return None

def _is_text_col(df, c):
    """True if the column is textual/categorical (not numeric), robust to object/str/category dtypes."""
    if pd.api.types.is_numeric_dtype(df[c]):
        return False
    if pd.api.types.is_datetime64_any_dtype(df[c]):
        return False
    return True

def _first_categorical_col(df):
    """Return the first meaningful categorical (text) column with a small number of categories."""
    for c in df.columns:
        if _is_junk(c):
            continue
        name = str(c).lower()
        if 'id' in name or 'respondent' in name:
            continue
        if _is_text_col(df, c):
            nun = df[c].nunique()
            if 1 < nun <= 50:
                return c
    return None

def _all_categorical_cols(df):
    out = []
    for c in df.columns:
        if _is_junk(c):
            continue
        name = str(c).lower()
        if 'id' in name or 'respondent' in name:
            continue
        if _is_text_col(df, c) and 1 < df[c].nunique() <= 50:
            out.append(c)
    return out

def _all_numeric_cols(df):
    out = []
    for c in df.columns:
        if _is_junk(c):
            continue
        name = str(c).lower()
        if 'id' in name or 'respondent' in name:
            continue
        s = pd.to_numeric(df[c], errors='coerce')
        if s.notna().sum() > 0:
            out.append(c)
    return out


def viz_histogram(df: pd.DataFrame, parameters: dict) -> dict:
    column = parameters.get('column') or _first_numeric_col(df)
    bins = int(parameters.get('bins', 20))
    if column is None or column not in df.columns:
        return {'error': 'No numeric column available for a histogram.'}

    series = pd.to_numeric(df[column], errors='coerce').dropna()
    if series.empty:
        return {'error': f'Column "{column}" has no numeric data.'}

    counts, edges = np.histogram(series, bins=bins)
    data = [
        {'bin': f'{_clean_number(edges[i])}–{_clean_number(edges[i + 1])}', 'count': int(counts[i])}
        for i in range(len(counts))
    ]
    return {'type': 'histogram', 'category': 'Data Visualization', 'column': column, 'data': data}


def viz_bar_chart(df: pd.DataFrame, parameters: dict) -> dict:
    column = parameters.get('column') or _first_categorical_col(df) or _first_numeric_col(df)
    top_n = int(parameters.get('top_n', 15))
    if column is None or column not in df.columns:
        return {'error': 'No suitable column available for a bar chart.'}

    counts = df[column].dropna().astype(str).value_counts().head(top_n)
    data = [{'category': str(k), 'count': int(v)} for k, v in counts.items()]
    return {'type': 'bar_chart', 'category': 'Data Visualization', 'column': column, 'data': data}


def viz_line_chart(df: pd.DataFrame, parameters: dict) -> dict:
    date_col = parameters.get('date_col')
    value_col = parameters.get('value_col')
    data, err, date_col, value_col = _prep_timeseries(df, date_col, value_col)
    if err:
        return {'error': err}

    series = [
        {'date': row[date_col].strftime('%Y-%m-%d'), 'value': _clean_number(row[value_col])}
        for _, row in data.tail(300).iterrows()
    ]
    return {'type': 'line_chart', 'category': 'Data Visualization', 'date_col': date_col, 'value_col': value_col, 'data': series}


def viz_scatter(df: pd.DataFrame, parameters: dict) -> dict:
    nums = _all_numeric_cols(df)
    x_col = parameters.get('x_col') or (nums[0] if len(nums) >= 1 else None)
    y_col = parameters.get('y_col') or (nums[1] if len(nums) >= 2 else None)
    if x_col is None or y_col is None or x_col not in df.columns or y_col not in df.columns:
        return {'error': 'Need at least two numeric columns for a scatter plot.'}

    data = df[[x_col, y_col]].apply(pd.to_numeric, errors='coerce').dropna()
    if data.empty:
        return {'error': 'No numeric data available for the selected columns.'}

    sample = data.sample(min(500, len(data)), random_state=42) if len(data) > 500 else data
    points = [{'x': _clean_number(r[x_col]), 'y': _clean_number(r[y_col])} for _, r in sample.iterrows()]

    correlation = _clean_number(data[x_col].corr(data[y_col]))
    return {
        'type': 'scatter', 'category': 'Data Visualization',
        'x_col': x_col, 'y_col': y_col, 'correlation': correlation,
        'points': points,
    }


def viz_boxplot(df: pd.DataFrame, parameters: dict) -> dict:
    column = parameters.get('column') or _first_numeric_col(df)
    if column is None or column not in df.columns:
        return {'error': 'No numeric column available for a box plot.'}

    series = pd.to_numeric(df[column], errors='coerce').dropna()
    if series.empty:
        return {'error': f'Column "{column}" has no numeric data.'}

    q1, q2, q3 = series.quantile([0.25, 0.5, 0.75])
    iqr = q3 - q1
    lower_fence = q1 - 1.5 * iqr
    upper_fence = q3 + 1.5 * iqr
    outliers = series[(series < lower_fence) | (series > upper_fence)]

    return {
        'type': 'boxplot', 'category': 'Data Visualization', 'column': column,
        'min': _clean_number(series.min()), 'q1': _clean_number(q1), 'median': _clean_number(q2),
        'q3': _clean_number(q3), 'max': _clean_number(series.max()),
        'lower_fence': _clean_number(lower_fence), 'upper_fence': _clean_number(upper_fence),
        'outliers': [_clean_number(v) for v in outliers.head(30).tolist()],
        'outliers_count': int(len(outliers)),
    }


def viz_correlation_heatmap(df: pd.DataFrame, parameters: dict) -> dict:
    parameters = parameters or {}
    numeric_df = df.select_dtypes(include=[np.number])

    selected = parameters.get('columns') or []
    if selected:
        missing = [c for c in selected if c not in numeric_df.columns]
        if missing:
            return {'error': f'Column(s) not found or not numeric: {", ".join(missing)}'}
        numeric_df = numeric_df[selected]

    if numeric_df.shape[1] < 2:
        return {'error': 'Need at least 2 numeric columns for a correlation heatmap.'}

    cols = numeric_df.columns.tolist()[:15]
    corr = numeric_df[cols].corr().round(4)
    return {
        'type': 'correlation_heatmap', 'category': 'Data Visualization',
        'columns': cols, 'matrix': corr.values.tolist(),
    }


# ────────────────────────────────────────────────────────────────────────────
# Master dispatcher — mirrors run_raas_stage1() from the spec document
# ────────────────────────────────────────────────────────────────────────────

DISPATCH = {
    'descriptive_statistics':  descriptive_statistics,
    'summary_statistics_uae':  summary_statistics_uae,
    'one_sample_ttest':        one_sample_ttest,
    'independent_ttest':       independent_ttest,
    'paired_ttest':            paired_ttest,
    'anova':                   one_way_anova,
    'chi_square':              chi_square_test,
    'f_test':                  f_test_variance,
    'linear_regression':       linear_regression,
    'logistic_regression':     logistic_regression,
    'multinomial_logit':       multinomial_logit,
    'quantile_regression':     quantile_regression,
    'moving_average':          moving_average,
    'time_series_adf':         time_series_adf,
    'time_series_arima':       time_series_arima,
    'seasonal_decomposition':  seasonal_decomposition_uae,
    'pooled_ols':              pooled_ols_model,
    'fixed_effects':           fixed_effects_model,
    'random_effects':          random_effects_model,
    'viz_histogram':           viz_histogram,
    'viz_bar_chart':           viz_bar_chart,
    'viz_line_chart':          viz_line_chart,
    'viz_scatter':             viz_scatter,
    'viz_boxplot':             viz_boxplot,
    'viz_correlation_heatmap': viz_correlation_heatmap,
}

# Analyses that require a download credit / paid plan on the free tier
PREMIUM_ANALYSES = {
    'multinomial_logit', 'quantile_regression', 'time_series_arima',
    'seasonal_decomposition', 'pooled_ols', 'fixed_effects', 'random_effects',
}


def run_universal_analysis(df: pd.DataFrame, analysis_type: str, parameters: dict = None) -> dict:
    """Master dispatcher — routes to the correct Stage-1 analysis function."""
    parameters = parameters or {}
    fn = DISPATCH.get(analysis_type)
    if not fn:
        return {'error': f'Unknown analysis type "{analysis_type}". '
                          f'Available: {", ".join(sorted(DISPATCH.keys()))}'}
    try:
        return fn(df, parameters)
    except Exception as e:
        return {'error': f'Analysis failed: {str(e)}'}


# ────────────────────────────────────────────────────────────────────────────
# Catalog — describes every analysis for the frontend (labels, inputs needed)
# ────────────────────────────────────────────────────────────────────────────

CATALOG = [
    # 1. Descriptive Statistics
    {'id': 'descriptive_statistics', 'category': 'Descriptive Statistics', 'label': 'Descriptive Statistics',
     'description': 'Mean, median, mode, range, variance, std dev, coefficient of variation, skewness, kurtosis for every numeric column.',
     'premium': False, 'params': [
        {'name': 'columns', 'label': 'Variables to Include (optional — leave empty for all)', 'type': 'numeric_column_multi', 'required': False},
    ]},

    # 2. Summary Statistics
    {'id': 'summary_statistics_uae', 'category': 'Summary Statistics', 'label': 'Summary Statistics',
     'description': 'Count, missing values, unique values, percentiles for numeric columns and frequency tables for categorical columns.',
     'premium': False, 'params': [
        {'name': 'columns', 'label': 'Variables to Include (optional — leave empty for all)', 'type': 'any_column_multi', 'required': False},
    ]},

    # 3. Hypothesis Testing
    {'id': 'one_sample_ttest', 'category': 'Hypothesis Testing', 'label': 'One-Sample t-Test',
     'description': 'Compare a column\'s mean against a known/expected value.',
     'premium': False, 'params': [
        {'name': 'column', 'label': 'Numeric Column', 'type': 'numeric_column', 'required': True},
        {'name': 'population_mean', 'label': 'Expected / Population Mean', 'type': 'number', 'required': True, 'default': 0},
    ]},
    {'id': 'independent_ttest', 'category': 'Hypothesis Testing', 'label': 'Independent Two-Sample t-Test',
     'description': 'Compare the means of a numeric column between two groups of a categorical column.',
     'premium': False, 'params': [
        {'name': 'value_col', 'label': 'Numeric Column', 'type': 'numeric_column', 'required': True},
        {'name': 'group_col', 'label': 'Group Column', 'type': 'categorical_column', 'required': True},
        {'name': 'group1', 'label': 'Group 1 (optional)', 'type': 'group_value', 'required': False},
        {'name': 'group2', 'label': 'Group 2 (optional)', 'type': 'group_value', 'required': False},
    ]},
    {'id': 'paired_ttest', 'category': 'Hypothesis Testing', 'label': 'Paired t-Test',
     'description': 'Compare two related numeric columns (e.g. before vs after).',
     'premium': False, 'params': [
        {'name': 'before_col', 'label': '"Before" Column', 'type': 'numeric_column', 'required': True},
        {'name': 'after_col', 'label': '"After" Column', 'type': 'numeric_column', 'required': True},
    ]},
    {'id': 'anova', 'category': 'Hypothesis Testing', 'label': 'One-Way ANOVA',
     'description': 'Compare the mean of a numeric column across 3 or more groups.',
     'premium': False, 'params': [
        {'name': 'value_col', 'label': 'Numeric Column', 'type': 'numeric_column', 'required': True},
        {'name': 'group_col', 'label': 'Group Column', 'type': 'categorical_column', 'required': True},
    ]},
    {'id': 'chi_square', 'category': 'Hypothesis Testing', 'label': 'Chi-Square Test',
     'description': 'Test whether two categorical columns are statistically related.',
     'premium': False, 'params': [
        {'name': 'col1', 'label': 'Categorical Column 1', 'type': 'categorical_column', 'required': True},
        {'name': 'col2', 'label': 'Categorical Column 2', 'type': 'categorical_column', 'required': True},
    ]},
    {'id': 'f_test', 'category': 'Hypothesis Testing', 'label': 'F-Test for Equality of Variances',
     'description': 'Compare the variance (spread) of a numeric column between two groups.',
     'premium': False, 'params': [
        {'name': 'value_col', 'label': 'Numeric Column', 'type': 'numeric_column', 'required': True},
        {'name': 'group_col', 'label': 'Group Column', 'type': 'categorical_column', 'required': True},
        {'name': 'group1', 'label': 'Group 1 (optional)', 'type': 'group_value', 'required': False},
        {'name': 'group2', 'label': 'Group 2 (optional)', 'type': 'group_value', 'required': False},
    ]},

    # 4. Regression Analysis
    {'id': 'linear_regression', 'category': 'Regression Analysis', 'label': 'Linear Regression',
     'description': 'Model a numeric outcome as a linear function of one or more numeric predictors (OLS).',
     'premium': False, 'params': [
        {'name': 'dependent_var', 'label': 'Dependent Variable (Y)', 'type': 'numeric_column', 'required': True},
        {'name': 'independent_vars', 'label': 'Independent Variables (X)', 'type': 'numeric_column_multi', 'required': True},
    ]},
    {'id': 'logistic_regression', 'category': 'Regression Analysis', 'label': 'Logistic Regression',
     'description': 'Model a binary outcome (e.g. yes/no, 0/1) as a function of numeric predictors.',
     'premium': False, 'params': [
        {'name': 'dependent_var', 'label': 'Dependent Variable (binary)', 'type': 'any_column', 'required': True},
        {'name': 'independent_vars', 'label': 'Independent Variables (X)', 'type': 'numeric_column_multi', 'required': True},
    ]},
    {'id': 'multinomial_logit', 'category': 'Regression Analysis', 'label': 'Multinomial Logistic Regression',
     'description': 'Model an outcome with 3+ unordered categories as a function of numeric predictors.',
     'premium': True, 'params': [
        {'name': 'dependent_var', 'label': 'Dependent Variable (3+ categories)', 'type': 'any_column', 'required': True},
        {'name': 'independent_vars', 'label': 'Independent Variables (X)', 'type': 'numeric_column_multi', 'required': True},
    ]},
    {'id': 'quantile_regression', 'category': 'Regression Analysis', 'label': 'Quantile (Quartile) Regression',
     'description': 'Model the 25th, 50th and 75th percentiles of the outcome — useful when relationships differ across the distribution.',
     'premium': True, 'params': [
        {'name': 'dependent_var', 'label': 'Dependent Variable (Y)', 'type': 'numeric_column', 'required': True},
        {'name': 'independent_vars', 'label': 'Independent Variables (X)', 'type': 'numeric_column_multi', 'required': True},
    ]},

    # 5. Time Series Analysis
    {'id': 'moving_average', 'category': 'Time Series Analysis', 'label': 'Moving Average',
     'description': 'Smooth a time series using a rolling-window average.',
     'premium': False, 'params': [
        {'name': 'date_col', 'label': 'Date Column', 'type': 'date_column', 'required': True},
        {'name': 'value_col', 'label': 'Value Column', 'type': 'numeric_column', 'required': True},
        {'name': 'window', 'label': 'Window Size', 'type': 'number', 'required': False, 'default': 3},
    ]},
    {'id': 'time_series_adf', 'category': 'Time Series Analysis', 'label': 'Stationarity Test (ADF)',
     'description': 'Augmented Dickey-Fuller test — checks whether a series is stationary (required before forecasting).',
     'premium': False, 'params': [
        {'name': 'value_col', 'label': 'Value Column', 'type': 'numeric_column', 'required': True},
    ]},
    {'id': 'time_series_arima', 'category': 'Time Series Analysis', 'label': 'ARIMA Forecast',
     'description': 'Fit an ARIMA model and forecast future values.',
     'premium': True, 'params': [
        {'name': 'date_col', 'label': 'Date Column', 'type': 'date_column', 'required': True},
        {'name': 'value_col', 'label': 'Value Column', 'type': 'numeric_column', 'required': True},
        {'name': 'forecast_steps', 'label': 'Forecast Steps', 'type': 'number', 'required': False, 'default': 5},
    ]},
    {'id': 'seasonal_decomposition', 'category': 'Time Series Analysis', 'label': 'Seasonal Decomposition',
     'description': 'Split a time series into trend, seasonal and residual components.',
     'premium': True, 'params': [
        {'name': 'date_col', 'label': 'Date Column', 'type': 'date_column', 'required': True},
        {'name': 'value_col', 'label': 'Value Column', 'type': 'numeric_column', 'required': True},
        {'name': 'period', 'label': 'Seasonal Period (optional)', 'type': 'number', 'required': False},
    ]},

    # 6. Panel Data Analysis
    {'id': 'pooled_ols', 'category': 'Panel Data Analysis', 'label': 'Pooled OLS',
     'description': 'Basic panel regression that ignores entity/time structure.',
     'premium': True, 'params': [
        {'name': 'entity_col', 'label': 'Entity Column (e.g. company, region)', 'type': 'categorical_column', 'required': True},
        {'name': 'time_col', 'label': 'Time Column', 'type': 'any_column', 'required': True},
        {'name': 'dependent_var', 'label': 'Dependent Variable (Y)', 'type': 'numeric_column', 'required': True},
        {'name': 'independent_vars', 'label': 'Independent Variables (X)', 'type': 'numeric_column_multi', 'required': True},
    ]},
    {'id': 'fixed_effects', 'category': 'Panel Data Analysis', 'label': 'Fixed Effects Model',
     'description': 'Controls for unobserved characteristics that are constant within each entity.',
     'premium': True, 'params': [
        {'name': 'entity_col', 'label': 'Entity Column (e.g. company, region)', 'type': 'categorical_column', 'required': True},
        {'name': 'time_col', 'label': 'Time Column', 'type': 'any_column', 'required': True},
        {'name': 'dependent_var', 'label': 'Dependent Variable (Y)', 'type': 'numeric_column', 'required': True},
        {'name': 'independent_vars', 'label': 'Independent Variables (X)', 'type': 'numeric_column_multi', 'required': True},
    ]},
    {'id': 'random_effects', 'category': 'Panel Data Analysis', 'label': 'Random Effects Model',
     'description': 'Assumes entity-specific effects are random and uncorrelated with predictors.',
     'premium': True, 'params': [
        {'name': 'entity_col', 'label': 'Entity Column (e.g. company, region)', 'type': 'categorical_column', 'required': True},
        {'name': 'time_col', 'label': 'Time Column', 'type': 'any_column', 'required': True},
        {'name': 'dependent_var', 'label': 'Dependent Variable (Y)', 'type': 'numeric_column', 'required': True},
        {'name': 'independent_vars', 'label': 'Independent Variables (X)', 'type': 'numeric_column_multi', 'required': True},
    ]},

    # 7. Data Visualization
    {'id': 'viz_histogram', 'category': 'Data Visualization', 'label': 'Histogram',
     'description': 'Distribution of a numeric column across bins.',
     'premium': False, 'params': [
        {'name': 'column', 'label': 'Numeric Column', 'type': 'numeric_column', 'required': True},
        {'name': 'bins', 'label': 'Number of Bins', 'type': 'number', 'required': False, 'default': 20},
    ]},
    {'id': 'viz_bar_chart', 'category': 'Data Visualization', 'label': 'Bar Chart',
     'description': 'Frequency of each category in a column.',
     'premium': False, 'params': [
        {'name': 'column', 'label': 'Categorical Column', 'type': 'categorical_column', 'required': True},
        {'name': 'top_n', 'label': 'Top N Categories', 'type': 'number', 'required': False, 'default': 15},
    ]},
    {'id': 'viz_line_chart', 'category': 'Data Visualization', 'label': 'Line Chart (Time Series)',
     'description': 'A value plotted over time.',
     'premium': False, 'params': [
        {'name': 'date_col', 'label': 'Date Column', 'type': 'date_column', 'required': True},
        {'name': 'value_col', 'label': 'Value Column', 'type': 'numeric_column', 'required': True},
    ]},
    {'id': 'viz_scatter', 'category': 'Data Visualization', 'label': 'Scatter Plot',
     'description': 'Relationship between two numeric columns plus correlation coefficient.',
     'premium': False, 'params': [
        {'name': 'x_col', 'label': 'X-Axis Column', 'type': 'numeric_column', 'required': True},
        {'name': 'y_col', 'label': 'Y-Axis Column', 'type': 'numeric_column', 'required': True},
    ]},
    {'id': 'viz_boxplot', 'category': 'Data Visualization', 'label': 'Box Plot',
     'description': 'Quartiles, median and outliers of a numeric column.',
     'premium': False, 'params': [
        {'name': 'column', 'label': 'Numeric Column', 'type': 'numeric_column', 'required': True},
    ]},
    {'id': 'viz_correlation_heatmap', 'category': 'Data Visualization', 'label': 'Correlation Heatmap',
     'description': 'Pairwise correlation between all numeric columns.',
     'premium': False, 'params': [
        {'name': 'columns', 'label': 'Variables to Include (optional — leave empty for all, min 2)', 'type': 'numeric_column_multi', 'required': False},
    ]},
]


def get_catalog():
    """Return the full Stage-1 analysis catalog, grouped by category."""
    grouped = {}
    for item in CATALOG:
        grouped.setdefault(item['category'], []).append(item)
    return {
        'categories': list(grouped.keys()),
        'analyses': CATALOG,
        'grouped': grouped,
    }


def suggest_analyses(columns_meta: list) -> dict:
    """
    Suggest which Stage-1 analyses are applicable to a file, based on the
    dtype/python_type AND cardinality already stored on the ExcelFile record
    (columns_meta). This does NOT touch the learning module — it is a
    separate, lightweight structural check used only to highlight relevant
    analyses in the UI.

    Key principle: only suggest an analysis if the data can ACTUALLY run it,
    not just if the right column types exist. For example:
    - Multinomial Logistic Regression needs a categorical column with 3-8 categories
    - Paired t-Test needs at least 2 numeric columns (not just 1)
    - Chi-Square needs 2 categorical columns each with 2+ categories
    - Panel Data needs an entity column with 2+ groups AND a time column AND 2+ numeric cols
    """
    IGNORED_COLUMN_NAMES = {
        'tests', 'test', 'data types', 'data type', 'notes', 'legend',
        'respondent_id', 'id', 'sr_no', 'sr. no.', 'serial_no', 's.no',
        'data types', 'data type',
    }

    numeric_cols = []
    categorical_cols = []
    date_like_cols = []
    time_identifier_cols = []

    # Cardinality info — needed for smarter suggestions
    binary_categorical_cols = []       # exactly 2 unique values → logistic regression outcome
    multi_categorical_cols = []        # 3-8 unique values → multinomial logit outcome
    high_cardinality_cat_cols = []     # 9+ unique values → entity col for panel
    low_cardinality_cat_cols = []      # 2-20 unique values → group col for t-test/ANOVA/chi-square
    many_numeric_cols = []             # numeric cols excluding obvious ID columns

    for col in columns_meta:
        name = col.get('name', '')
        name_lower = str(name).strip().lower()

        # Skip legend/notes/ID columns
        if name_lower in IGNORED_COLUMN_NAMES:
            continue
        if name_lower.startswith('unnamed'):
            continue

        dtype = str(col.get('dtype', '')).lower()
        python_type = str(col.get('python_type', '')).lower()
        n_unique = col.get('unique_values', col.get('n_unique', None))
        try:
            n_unique = int(n_unique) if n_unique is not None else None
        except (TypeError, ValueError):
            n_unique = None

        is_numeric = (
            'int' in dtype or 'float' in dtype or
            'int' in python_type or 'float' in python_type
        )
        is_date_typed = (
            'datetime' in dtype or 'datetime' in python_type or
            'date_string' in python_type or python_type == 'date'
        )

        if is_date_typed:
            date_like_cols.append(name)
            time_identifier_cols.append(name)

        elif is_numeric:
            numeric_cols.append(name)

            # Year-like integer column → also usable as panel time identifier
            if 'int' in dtype or 'int' in python_type:
                if name_lower in ('year',) or name_lower.endswith('_year') or name_lower.startswith('year_'):
                    time_identifier_cols.append(name)

            # Exclude obvious ID/serial columns from regression predictors
            is_id_col = (
                name_lower in ('respondent_id', 'id', 'sr_no', 'serial_no', 'index') or
                name_lower.endswith('_id') or
                name_lower.startswith('id_') or
                (n_unique is not None and n_unique > 100 and name_lower.endswith('id'))
            )
            if not is_id_col:
                many_numeric_cols.append(name)

        else:
            # Non-numeric, non-date → categorical
            is_date_by_name = any(k in name_lower for k in ['date', 'datetime'])
            if is_date_by_name:
                date_like_cols.append(name)
                time_identifier_cols.append(name)
            else:
                categorical_cols.append(name)

                # Cardinality-based sub-classification
                if n_unique is not None:
                    if n_unique == 2:
                        binary_categorical_cols.append(name)
                        low_cardinality_cat_cols.append(name)
                    elif 3 <= n_unique <= 8:
                        multi_categorical_cols.append(name)
                        low_cardinality_cat_cols.append(name)
                    elif 9 <= n_unique <= 20:
                        low_cardinality_cat_cols.append(name)
                    elif n_unique > 20:
                        high_cardinality_cat_cols.append(name)
                else:
                    # No cardinality info available — be permissive
                    low_cardinality_cat_cols.append(name)
                    multi_categorical_cols.append(name)
                    binary_categorical_cols.append(name)

    # ── Smarter applicability rules ──────────────────────────────────────

    def is_applicable(item_id, category):
        n_num = len(numeric_cols)
        n_usable_num = len(many_numeric_cols)
        n_cat = len(categorical_cols)
        n_low_cat = len(low_cardinality_cat_cols)
        n_date = len(date_like_cols)

        # ── Descriptive / Summary: need at least 1 numeric or 1 categorical
        if item_id == 'descriptive_statistics':
            return n_num >= 1

        if item_id == 'summary_statistics_uae':
            return n_num >= 1 or n_cat >= 1

        # ── Hypothesis Testing ───────────────────────────────────────────

        if item_id == 'one_sample_ttest':
            # Need at least 1 usable numeric column (not just an ID)
            return n_usable_num >= 1

        if item_id == 'independent_ttest':
            # Need 1 numeric + 1 categorical group column with 2+ groups
            return n_usable_num >= 1 and n_low_cat >= 1

        if item_id == 'paired_ttest':
            # Need 2+ numeric columns that could represent before/after pairs
            # Only suggest if there are genuinely multiple numeric measurement cols
            return n_usable_num >= 2

        if item_id == 'anova':
            # Need 1 numeric + 1 categorical with ideally 3+ groups
            # (but we allow 2+ since we can't always know group count)
            return n_usable_num >= 1 and n_low_cat >= 1

        if item_id == 'chi_square':
            # Need 2 categorical columns each with 2+ categories
            return n_low_cat >= 2

        if item_id == 'f_test':
            # Need 1 numeric + 1 categorical group column
            return n_usable_num >= 1 and n_low_cat >= 1

        # ── Regression ───────────────────────────────────────────────────

        if item_id == 'linear_regression':
            # Need 2+ usable numeric cols (1 Y + at least 1 X)
            return n_usable_num >= 2

        if item_id == 'logistic_regression':
            # Need a binary outcome (2 unique values — Yes/No, 0/1, True/False)
            # + at least 1 predictor. For pure binary datasets, binary columns
            # themselves can serve as predictors (after encoding), so we accept
            # either usable numeric predictors OR additional binary columns.
            has_binary_outcome = len(binary_categorical_cols) >= 1
            has_predictors = n_usable_num >= 1 or len(binary_categorical_cols) >= 2
            return has_binary_outcome and has_predictors

        if item_id == 'multinomial_logit':
            # Need a categorical column with 3-8 unique values as a genuine
            # multi-class outcome variable (not just a demographic grouper)
            real_multi = [c for c in multi_categorical_cols
                         if c.lower() not in (
                             'gender', 'sex', 'marital_status', 'marital status',
                             'education_level', 'education level', 'income_category',
                             'income category', 'customer_satisfaction',
                             'customer satisfaction', 'performance_rating',
                             'performance rating', 'purchase_frequency',
                             'purchase frequency', 'employment_type', 'employment type',
                             'blood_group', 'blood group', 'state', 'region',
                             'industry', 'district', 'city', 'country',
                         )]
            return len(real_multi) >= 1 and n_usable_num >= 1

        if item_id == 'paired_ttest':
            # Only suggest paired t-test if there are column name pairs that
            # suggest before/after structure (e.g. Pre_Score/Post_Score,
            # Before_X/After_X, Test1/Test2). Generic numeric columns without
            # this naming pattern are unlikely to be paired measurements.
            all_names_lower = [col.get('name','').lower() for col in columns_meta]
            has_before_after = any(
                n.startswith(('pre_', 'before_', 'baseline_', 'pre ', 'before '))
                or n.endswith(('_pre', '_before', '_baseline'))
                for n in all_names_lower
            ) and any(
                n.startswith(('post_', 'after_', 'followup_', 'post ', 'after '))
                or n.endswith(('_post', '_after', '_followup'))
                for n in all_names_lower
            )
            return has_before_after and n_usable_num >= 2

        if item_id == 'f_test':
            # F-test for equality of variances needs a group column with exactly
            # 2 groups — same as independent t-test requirement
            return n_usable_num >= 1 and len(binary_categorical_cols) >= 1

        if item_id == 'time_series_adf':
            # ADF stationarity test makes sense only for time series data
            # (file has a date column). Running it on cross-sectional numeric
            # data is technically possible but rarely what the user needs.
            return n_date >= 1 and n_num >= 1

        if item_id == 'quantile_regression':
            # Same requirement as linear regression
            return n_usable_num >= 2

        # ── Time Series ──────────────────────────────────────────────────

        if item_id == 'moving_average':
            return n_date >= 1 and n_num >= 1

        if item_id == 'time_series_adf':
            return n_num >= 1  # just needs a numeric series

        if item_id == 'time_series_arima':
            return n_date >= 1 and n_num >= 1

        if item_id == 'seasonal_decomposition':
            return n_date >= 1 and n_num >= 1

        # ── Panel Data ───────────────────────────────────────────────────

        if category == 'Panel Data Analysis':
            # Need: entity col (categorical, any cardinality) +
            #        time col (date or year-int) +
            #        2+ numeric cols (dependent + at least 1 predictor)
            return (
                n_cat >= 1 and
                len(time_identifier_cols) >= 1 and
                n_usable_num >= 2
            )

        # ── Data Visualization ───────────────────────────────────────────

        if item_id == 'viz_histogram':
            return n_usable_num >= 1

        if item_id == 'viz_bar_chart':
            return n_low_cat >= 1

        if item_id == 'viz_line_chart':
            return n_date >= 1 and n_num >= 1

        if item_id == 'viz_scatter':
            return n_usable_num >= 2

        if item_id == 'viz_boxplot':
            return n_usable_num >= 1

        if item_id == 'viz_correlation_heatmap':
            return n_usable_num >= 2

        # Default: allow if basic column requirements are met
        return True

    suggestions = []
    for item in CATALOG:
        if is_applicable(item['id'], item['category']):
            suggestions.append(item['id'])
            
        

    return {
        'numeric_columns': numeric_cols,
        'categorical_columns': categorical_cols,
        'date_columns': date_like_cols,
        'suggested_analyses': suggestions,
    }
    # Alias for backwards compatibility
get_smart_catalog = get_catalog