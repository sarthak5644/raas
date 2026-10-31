"""
Health, Medical, Pharmaceutical & Life Sciences Service (RaaS Stage-2, Component 3)
=====================================================================================
Same architecture as sarthak/environmental/environmental_analytics.py:
  - Individual analysis functions: fn(df, parameters) -> dict
  - HEALTH_MODULES: catalog driving the frontend UI
  - run_health_analysis(): dispatcher
  - suggest_health_analyses(): column-driven recommendations for a file

The source document contains two overlapping engines (34 functions in 11
categories, and a 28-module list that adds longitudinal / PK-PD / genetics /
nursing items). They are merged and de-duplicated here into 12 modules:

     1. Biostatistics                      7. Pharmaceutical Analytics
     2. Epidemiology                       8. Meta-Analysis
     3. Diagnostic Testing                 9. Health Economics
     4. Clinical Trials                   10. Life Sciences & Genetics
     5. Survival Analysis                 11. Hospital, Nursing & Outcomes
     6. Medical Count Models              12. Advanced Medical Analytics

No `lifelines` or `scikit-learn` dependency: Kaplan-Meier, log-rank and ROC-AUC
are implemented directly, and Cox PH uses statsmodels' PHReg, so the module
runs on the project's existing stack (numpy, pandas, scipy, statsmodels).

Deliberate corrections vs. the source snippets:
  * Hardy-Weinberg uses 1 degree of freedom (one allele frequency is estimated
    from the data), not the 2 that a plain chi-square over 3 genotypes gives.
  * Dose-response (4PL) fitting uses sensible starting values and bounds; an
    un-seeded curve_fit rarely converges on real dose-response data.
"""
import warnings
import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import curve_fit
from scipy.integrate import solve_ivp
import statsmodels.api as sm

_trapz = getattr(np, 'trapezoid', None) or getattr(np, 'trapz')


# ══════════════════════════════════════════════════════════════════════════
# helpers
# ══════════════════════════════════════════════════════════════════════════
def _err(msg: str) -> dict:
    return {'error': msg}


def _f(x, nd=4):
    """JSON-safe rounded float (NaN / inf / None -> None)."""
    try:
        if x is None:
            return None
        x = float(x)
        if np.isnan(x) or np.isinf(x):
            return None
        return round(x, nd)
    except Exception:
        return None


def _num(parameters: dict, key: str, default=None) -> float:
    val = parameters.get(key, default)
    if val is None or val == '':
        raise KeyError(key)
    return float(val)


def _opt(parameters: dict, key: str):
    val = parameters.get(key)
    return None if val is None or val == '' else float(val)


def _numeric_series(df, column) -> pd.Series:
    if df is None or column not in df.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(df[column], errors='coerce').dropna()


def _need_cols(df, **cols):
    """Return an error dict if any named column is missing, else None."""
    if df is None:
        return _err('This analysis needs an uploaded file')
    for label, col in cols.items():
        if not col or col not in df.columns:
            return _err(f"{label} '{col}' was not found in this sheet")
    return None


_YES = {'yes': 1, 'no': 0, 'true': 1, 'false': 0, '1': 1, '0': 0, 'y': 1, 'n': 0,
        'positive': 1, 'negative': 0, 'pos': 1, 'neg': 0, 'dead': 1, 'alive': 0,
        'deceased': 1, 'event': 1, 'censored': 0, 'treated': 1, 'control': 0,
        'case': 1, 'healthy': 0, 'diseased': 1, 'disease': 1}


_CONTROL_WORDS = {'placebo', 'control', 'ctrl', 'sham', 'untreated', 'comparator', 'reference',
                  'vehicle', 'standard', 'usual care', 'no treatment', 'baseline', 'normal', 'healthy'}


def _to_binary(series: pd.Series):
    """Map a column onto 0/1. Returns (mapped_series, coding_description)
    or (None, None) when the column is not binary."""
    s = series
    if pd.api.types.is_bool_dtype(s):
        return s.astype(float), 'False=0, True=1'
    if pd.api.types.is_numeric_dtype(s):
        vals = sorted(set(s.dropna().unique().tolist()))
        if len(vals) == 1 and vals[0] in (0, 1):
            return s.astype(float), f'all values = {int(vals[0])}'
        if len(vals) == 2:
            lo, hi = vals
            return s.map({lo: 0.0, hi: 1.0}).astype(float), f'{lo:g}=0, {hi:g}=1'
        return None, None
    txt = s.astype(str).str.strip().str.lower()
    mapped = txt.map(_YES)
    notna = s.notna().sum()
    if notna > 0 and mapped.notna().sum() >= 0.9 * notna:
        mapped = mapped.where(s.notna())
        zero_lv = sorted(txt[mapped == 0].unique().tolist())
        one_lv = sorted(txt[mapped == 1].unique().tolist())
        return mapped.astype(float), f"{'/'.join(zero_lv) or '-'}=0, {'/'.join(one_lv) or '-'}=1"
    levels = sorted(txt[s.notna()].unique().tolist())
    if len(levels) == 2:
        # A control / comparator arm must be the reference (0) so that effects
        # read as "treatment minus control". Fall back to alphabetical only
        # when neither label looks like a control group.
        ctrl = [lv for lv in levels if lv in _CONTROL_WORDS or any(w in lv for w in _CONTROL_WORDS)]
        if len(ctrl) == 1:
            zero = ctrl[0]
            one = levels[1] if levels[0] == zero else levels[0]
            how = 'control-like label = 0'
        else:
            zero, one, how = levels[0], levels[1], 'alphabetical - check this is the direction you want'
        mp = {zero: 0.0, one: 1.0}
        return txt.map(mp).where(s.notna()).astype(float), f'{zero}=0, {one}=1 ({how})'
    return None, None


def _two_by_two(parameters: dict):
    a, b, c, d = (_num(parameters, k) for k in ('a', 'b', 'c', 'd'))
    if min(a, b, c, d) < 0:
        raise ValueError('Counts cannot be negative')
    if (a + b) <= 0 or (c + d) <= 0:
        raise ValueError('Each row (exposed / unexposed) must have at least one subject')
    return a, b, c, d


def _coef_table(res, exp_name=None):
    ci = np.asarray(res.conf_int())
    rows = []
    for i, name in enumerate(res.params.index):
        coef = float(res.params.iloc[i])
        row = {'variable': str(name), 'coef': _f(coef), 'std_err': _f(res.bse.iloc[i]),
               'p_value': _f(res.pvalues.iloc[i], 6)}
        if exp_name:
            row[exp_name] = _f(np.exp(coef))
            row[exp_name + '_ci_low'] = _f(np.exp(ci[i, 0]))
            row[exp_name + '_ci_high'] = _f(np.exp(ci[i, 1]))
        rows.append(row)
    return rows


def _thin(rows: list, limit: int = 150) -> list:
    if len(rows) <= limit:
        return rows
    idx = np.unique(np.linspace(0, len(rows) - 1, limit).astype(int))
    return [rows[i] for i in idx]


def _design(df, cols):
    """Numeric design matrix with constant; returns (X, data) or (None, None)."""
    data = df[cols].apply(pd.to_numeric, errors='coerce')
    return data


# ══════════════════════════════════════════════════════════════════════════
# which analyses read the uploaded file
# ══════════════════════════════════════════════════════════════════════════
DATA_DRIVEN_ANALYSES = {
    'health_descriptive_stats', 'disease_risk_logit', 'roc_auc_analysis', 'treatment_effect',
    'kaplan_meier_survival', 'cox_proportional_hazards', 'logrank_survival_test',
    'poisson_regression', 'negative_binomial_regression',
    'dose_response_analysis', 'bioequivalence_analysis', 'pk_analysis', 'pd_analysis',
    'gene_expression_fold_change', 'differential_expression_ttest', 'rna_seq_tpm',
    'gwas_single_snp', 'polygenic_risk_score',
    'health_outcome_regression', 'binary_health_outcome_model', 'satisfaction_summary', 'cronbach_alpha',
    'longitudinal_regression', 'mixed_effects_model', 'non_inferiority_test', 'equivalence_test_tost',
}

PREMIUM_ANALYSES = {
    'roc_auc_analysis', 'cox_proportional_hazards', 'logrank_survival_test', 'negative_binomial_regression',
    'dose_response_analysis', 'bioequivalence_analysis', 'pd_analysis', 'gwas_single_snp',
    'polygenic_risk_score', 'markov_model', 'mixed_effects_model', 'longitudinal_regression',
}


# ══════════════════════════════════════════════════════════════════════════
# 1. BIOSTATISTICS
# ══════════════════════════════════════════════════════════════════════════
def health_descriptive_stats(df, parameters):
    cols = parameters.get('columns') or []
    if df is None or not cols:
        return _err('columns is required')
    missing = [c for c in cols if c not in df.columns]
    if missing:
        return _err(f'Unknown columns: {missing}')
    rows = []
    for c in cols:
        s = _numeric_series(df, c)
        if s.empty:
            continue
        rows.append({'variable': c, 'n': int(len(s)), 'mean': _f(s.mean()), 'sd': _f(s.std()),
                     'min': _f(s.min()), 'q25': _f(s.quantile(.25)), 'median': _f(s.median()),
                     'q75': _f(s.quantile(.75)), 'max': _f(s.max())})
    if not rows:
        return _err('None of the selected columns contain numeric data')
    return {'type': 'health_descriptive_stats', 'n_variables': len(rows), 'table': rows}


def prevalence(df, parameters):
    try:
        cases, total = _num(parameters, 'existing_cases'), _num(parameters, 'total_population')
        if total <= 0 or cases < 0 or cases > total:
            return _err('Need 0 <= existing_cases <= total_population and total_population > 0')
        p = cases / total
        z = 1.96
        denom = 1 + z * z / total
        centre = (p + z * z / (2 * total)) / denom
        half = z * np.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
        return {'type': 'prevalence', 'prevalence_pct': _f(p * 100), 'per_100000': _f(p * 100000, 2),
                'ci95_low_pct': _f((centre - half) * 100), 'ci95_high_pct': _f((centre + half) * 100),
                'ci_method': 'Wilson score'}
    except KeyError as e:
        return _err(f'Missing input: {e}')


def incidence_rate(df, parameters):
    try:
        cases, pop = _num(parameters, 'new_cases'), _num(parameters, 'population_at_risk')
        mult = float(parameters.get('multiplier') or 100000)
        if pop <= 0 or cases < 0:
            return _err('population_at_risk must be > 0 and new_cases >= 0')
        rate = cases / pop * mult
        se = np.sqrt(cases) / pop * mult
        return {'type': 'incidence_rate', 'incidence_rate': _f(rate), 'per': mult,
                'ci95_low': _f(max(0.0, rate - 1.96 * se)), 'ci95_high': _f(rate + 1.96 * se),
                'ci_method': 'Poisson normal approximation'}
    except KeyError as e:
        return _err(f'Missing input: {e}')


def risk_difference(df, parameters):
    try:
        a, b, c, d = _two_by_two(parameters)
        r1, r0 = a / (a + b), c / (c + d)
        rd = r1 - r0
        se = np.sqrt(r1 * (1 - r1) / (a + b) + r0 * (1 - r0) / (c + d))
        return {'type': 'risk_difference', 'risk_exposed': _f(r1), 'risk_unexposed': _f(r0),
                'risk_difference': _f(rd), 'ci95_low': _f(rd - 1.96 * se), 'ci95_high': _f(rd + 1.96 * se),
                'interpretation': 'Exposure increases absolute risk' if rd > 0 else
                                  'Exposure decreases absolute risk' if rd < 0 else 'No difference in absolute risk'}
    except (KeyError, ValueError) as e:
        return _err(f'Invalid input: {e}')


# ══════════════════════════════════════════════════════════════════════════
# 2. EPIDEMIOLOGY
# ══════════════════════════════════════════════════════════════════════════
def relative_risk(df, parameters):
    try:
        a, b, c, d = _two_by_two(parameters)
        if c == 0:
            return _err('Unexposed group has zero cases — relative risk is undefined (try Odds Ratio)')
        rr = (a / (a + b)) / (c / (c + d))
        lo = hi = None
        if a > 0:
            se = np.sqrt(1 / a - 1 / (a + b) + 1 / c - 1 / (c + d))
            lo, hi = np.exp(np.log(rr) - 1.96 * se), np.exp(np.log(rr) + 1.96 * se)
        return {'type': 'relative_risk', 'relative_risk': _f(rr), 'ci95_low': _f(lo), 'ci95_high': _f(hi),
                'interpretation': 'Exposure is associated with higher risk' if rr > 1 else
                                  'Exposure is associated with lower risk' if rr < 1 else 'No association'}
    except (KeyError, ValueError) as e:
        return _err(f'Invalid input: {e}')


def odds_ratio(df, parameters):
    try:
        a, b, c, d = _two_by_two(parameters)
        corrected = False
        if min(a, b, c, d) == 0:
            a, b, c, d = a + .5, b + .5, c + .5, d + .5
            corrected = True
        orr = (a * d) / (b * c)
        se = np.sqrt(1 / a + 1 / b + 1 / c + 1 / d)
        out = {'type': 'odds_ratio', 'odds_ratio': _f(orr),
               'ci95_low': _f(np.exp(np.log(orr) - 1.96 * se)), 'ci95_high': _f(np.exp(np.log(orr) + 1.96 * se)),
               'significant': bool(np.exp(np.log(orr) - 1.96 * se) > 1 or np.exp(np.log(orr) + 1.96 * se) < 1)}
        if corrected:
            out['note'] = 'A zero cell was present, so 0.5 was added to every cell (Haldane-Anscombe correction)'
        return out
    except (KeyError, ValueError) as e:
        return _err(f'Invalid input: {e}')


def sir_model(df, parameters):
    try:
        S0, I0 = _num(parameters, 's0'), _num(parameters, 'i0')
        R0i = float(parameters.get('recovered0') or 0)
        beta, gamma = _num(parameters, 'beta'), _num(parameters, 'gamma')
        days = int(float(parameters.get('days') or 160))
        if S0 < 0 or I0 < 0 or R0i < 0 or beta < 0 or gamma <= 0:
            return _err('s0, i0, recovered0, beta must be >= 0 and gamma > 0')
        if not 1 <= days <= 1000:
            return _err('days must be between 1 and 1000')
        N = S0 + I0 + R0i
        if N <= 0:
            return _err('Total population must be > 0')

        def rhs(t, y):
            S, I, R = y
            return [-beta * S * I / N, beta * S * I / N - gamma * I, gamma * I]

        sol = solve_ivp(rhs, [0, days], [S0, I0, R0i], t_eval=np.arange(0, days + 1), rtol=1e-8, atol=1e-8)
        if not sol.success:
            return _err(f'ODE solver failed: {sol.message}')
        S, I, R = sol.y
        peak = int(np.argmax(I))
        curve = [{'day': int(t), 'susceptible': _f(s, 2), 'infected': _f(i, 2), 'recovered': _f(r, 2)}
                 for t, s, i, r in zip(sol.t, S, I, R)]
        return {'type': 'sir_model', 'population': _f(N, 2), 'basic_reproduction_number': _f(beta / gamma),
                'peak_infected': _f(I[peak], 2), 'peak_day': peak,
                'final_susceptible': _f(S[-1], 2), 'final_recovered': _f(R[-1], 2),
                'attack_rate_pct': _f((N - S[-1]) / N * 100), 'curve': _thin(curve, 200)}
    except KeyError as e:
        return _err(f'Missing input: {e}')


def reproduction_number(df, parameters):
    try:
        beta, gamma = _num(parameters, 'beta'), _num(parameters, 'gamma')
        if gamma <= 0:
            return _err('gamma must be > 0')
        r0 = beta / gamma
        return {'type': 'reproduction_number', 'R0': _f(r0),
                'herd_immunity_threshold_pct': _f(max(0.0, 1 - 1 / r0) * 100) if r0 > 0 else None,
                'interpretation': 'R0 > 1 — outbreak will grow' if r0 > 1 else 'R0 <= 1 — outbreak will die out'}
    except KeyError as e:
        return _err(f'Missing input: {e}')


def disease_risk_logit(df, parameters):
    disease_col, factors = parameters.get('disease_col'), parameters.get('risk_factors') or []
    e = _need_cols(df, disease_col=disease_col)
    if e or not factors:
        return e or _err('risk_factors is required')
    miss = [c for c in factors if c not in df.columns]
    if miss:
        return _err(f'Unknown risk_factors columns: {miss}')
    y, coding = _to_binary(df[disease_col])
    if y is None:
        return _err('disease_col must be binary (0/1, Yes/No, ...)')
    X = df[factors].apply(pd.to_numeric, errors='coerce')
    data = pd.concat([y.rename('_y'), X], axis=1).dropna()
    if len(data) < len(factors) + 10 or data['_y'].nunique() < 2:
        return _err('Not enough complete rows (or only one outcome level) to fit the model')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            res = sm.Logit(data['_y'], sm.add_constant(data[factors])).fit(disp=0)
    except Exception as ex:
        return _err(f'Logistic regression failed (perfect separation or collinearity?): {ex}')
    return {'type': 'disease_risk_logit', 'n_obs': int(res.nobs), 'outcome_coding': coding,
            'pseudo_r_squared': _f(res.prsquared), 'table': _coef_table(res, 'odds_ratio')}


# ══════════════════════════════════════════════════════════════════════════
# 3. DIAGNOSTIC TESTING
# ══════════════════════════════════════════════════════════════════════════
def _div(a, b):
    return a / b if b else None


def diagnostic_metrics(df, parameters):
    try:
        tp, fp, tn, fn = (_num(parameters, k) for k in ('tp', 'fp', 'tn', 'fn'))
        if min(tp, fp, tn, fn) < 0:
            return _err('Counts cannot be negative')
        sens, spec = _div(tp, tp + fn), _div(tn, tn + fp)
        lr_pos = _div(sens, 1 - spec) if sens is not None and spec is not None and spec < 1 else None
        lr_neg = _div(1 - sens, spec) if sens is not None and spec else None
        total = tp + fp + tn + fn
        return {'type': 'diagnostic_metrics', 'sensitivity': _f(sens), 'specificity': _f(spec),
                'ppv': _f(_div(tp, tp + fp)), 'npv': _f(_div(tn, tn + fn)),
                'accuracy': _f(_div(tp + tn, total)), 'prevalence_in_sample': _f(_div(tp + fn, total)),
                'positive_likelihood_ratio': _f(lr_pos), 'negative_likelihood_ratio': _f(lr_neg)}
    except KeyError as e:
        return _err(f'Missing input: {e}')


def roc_auc_analysis(df, parameters):
    true_col, score_col = parameters.get('true_col'), parameters.get('score_col')
    e = _need_cols(df, true_col=true_col, score_col=score_col)
    if e:
        return e
    y, coding = _to_binary(df[true_col])
    if y is None:
        return _err('true_col must be binary (0/1, Yes/No, ...)')
    score = pd.to_numeric(df[score_col], errors='coerce')
    mask = y.notna() & score.notna()
    y, sc = y[mask].astype(int).values, score[mask].values
    P, N = int(y.sum()), int(len(y) - y.sum())
    if P == 0 or N == 0:
        return _err('Both positive and negative cases are needed to compute ROC-AUC')

    order = np.argsort(-sc, kind='mergesort')
    sc_s, y_s = sc[order], y[order]
    tps, fps = np.cumsum(y_s), np.cumsum(1 - y_s)
    idx = np.r_[np.where(np.diff(sc_s))[0], len(y_s) - 1]
    tpr = np.r_[0.0, tps[idx] / P]
    fpr = np.r_[0.0, fps[idx] / N]
    thr = sc_s[idx]
    auc = float(_trapz(tpr, fpr))

    q1, q2 = auc / (2 - auc), 2 * auc ** 2 / (1 + auc)
    se = np.sqrt(max(0.0, (auc * (1 - auc) + (P - 1) * (q1 - auc ** 2) + (N - 1) * (q2 - auc ** 2)) / (P * N)))
    best = int(np.argmax(tpr[1:] - fpr[1:]))
    grade = ('Excellent' if auc >= .9 else 'Good' if auc >= .8 else 'Fair' if auc >= .7 else
             'Poor' if auc >= .6 else 'No better than chance' if auc >= .5 else 'Worse than chance (score may be inverted)')
    curve = _thin([{'fpr': _f(x), 'tpr': _f(t)} for x, t in zip(fpr, tpr)], 120)
    return {'type': 'roc_auc_analysis', 'n': int(len(y)), 'positives': P, 'negatives': N,
            'auc': _f(auc), 'auc_ci95_low': _f(max(0, auc - 1.96 * se)), 'auc_ci95_high': _f(min(1, auc + 1.96 * se)),
            'performance': grade, 'best_threshold_youden': _f(thr[best]),
            'sensitivity_at_best': _f(tpr[1:][best]), 'specificity_at_best': _f(1 - fpr[1:][best]),
            'outcome_coding': coding, 'curve': curve}


# ══════════════════════════════════════════════════════════════════════════
# 4. CLINICAL TRIALS
# ══════════════════════════════════════════════════════════════════════════
def treatment_effect(df, parameters):
    out_col, trt_col = parameters.get('outcome_col'), parameters.get('treatment_col')
    e = _need_cols(df, outcome_col=out_col, treatment_col=trt_col)
    if e:
        return e
    g, coding = _to_binary(df[trt_col])
    if g is None:
        return _err('treatment_col must have exactly two groups (0/1, Yes/No, Drug/Placebo, ...)')
    y = pd.to_numeric(df[out_col], errors='coerce')
    treated, control = y[(g == 1)].dropna(), y[(g == 0)].dropna()
    if len(treated) < 2 or len(control) < 2:
        return _err('Each group needs at least 2 numeric outcome values')
    diff = treated.mean() - control.mean()
    v1, v0, n1, n0 = treated.var(), control.var(), len(treated), len(control)
    se = np.sqrt(v1 / n1 + v0 / n0)
    dof = (v1 / n1 + v0 / n0) ** 2 / ((v1 / n1) ** 2 / (n1 - 1) + (v0 / n0) ** 2 / (n0 - 1)) if se > 0 else n1 + n0 - 2
    t_stat, p = stats.ttest_ind(treated, control, equal_var=False)
    tcrit = stats.t.ppf(.975, dof)
    sp = np.sqrt(((n1 - 1) * v1 + (n0 - 1) * v0) / (n1 + n0 - 2))
    return {'type': 'treatment_effect', 'group_coding': coding, 'n_treated': n1, 'n_control': n0,
            'treated_mean': _f(treated.mean()), 'control_mean': _f(control.mean()),
            'treatment_effect': _f(diff), 'ci95_low': _f(diff - tcrit * se), 'ci95_high': _f(diff + tcrit * se),
            't_statistic': _f(t_stat), 'p_value': _f(p, 6), 'cohens_d': _f(diff / sp) if sp > 0 else None,
            'significant': bool(p < 0.05)}


def two_proportion_ztest(df, parameters):
    try:
        from statsmodels.stats.proportion import proportions_ztest
        s1, n1, s2, n2 = (_num(parameters, k) for k in ('success1', 'n1', 'success2', 'n2'))
        if n1 <= 0 or n2 <= 0 or not (0 <= s1 <= n1) or not (0 <= s2 <= n2):
            return _err('Need 0 <= successes <= n for both groups, with n > 0')
        z, p = proportions_ztest(np.array([s1, s2]), np.array([n1, n2]))
        p1, p2 = s1 / n1, s2 / n2
        se = np.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
        return {'type': 'two_proportion_ztest', 'rate_group1': _f(p1), 'rate_group2': _f(p2),
                'difference': _f(p1 - p2), 'diff_ci95_low': _f(p1 - p2 - 1.96 * se), 'diff_ci95_high': _f(p1 - p2 + 1.96 * se),
                'z_statistic': _f(z), 'p_value': _f(p, 6), 'significant': bool(p < 0.05),
                'interpretation': 'Significant difference' if p < 0.05 else 'No significant difference'}
    except KeyError as e:
        return _err(f'Missing input: {e}')


def sample_size_mean(df, parameters):
    try:
        sd, me = _num(parameters, 'std_dev'), _num(parameters, 'margin_error')
        conf = float(parameters.get('confidence') or 0.95)
        if sd <= 0 or me <= 0 or not 0 < conf < 1:
            return _err('std_dev and margin_error must be > 0 and confidence between 0 and 1')
        z = stats.norm.ppf(1 - (1 - conf) / 2)
        return {'type': 'sample_size_mean', 'z_value': _f(z), 'required_sample_size': int(np.ceil((z * sd / me) ** 2))}
    except KeyError as e:
        return _err(f'Missing input: {e}')


def sample_size_proportion(df, parameters):
    try:
        p, me = _num(parameters, 'expected_proportion'), _num(parameters, 'margin_error')
        conf = float(parameters.get('confidence') or 0.95)
        if not 0 < p < 1 or me <= 0 or not 0 < conf < 1:
            return _err('expected_proportion must be between 0 and 1 (e.g. 0.5), margin_error > 0, confidence between 0 and 1')
        z = stats.norm.ppf(1 - (1 - conf) / 2)
        return {'type': 'sample_size_proportion', 'z_value': _f(z),
                'required_sample_size': int(np.ceil(z ** 2 * p * (1 - p) / me ** 2))}
    except KeyError as e:
        return _err(f'Missing input: {e}')


def number_needed_to_treat(df, parameters):
    try:
        cer, eer = _num(parameters, 'control_event_rate'), _num(parameters, 'treatment_event_rate')
        if not (0 <= cer <= 1 and 0 <= eer <= 1):
            return _err('Event rates must be fractions between 0 and 1 (e.g. 0.20 for 20%)')
        arr = cer - eer
        if arr == 0:
            return _err('Event rates are identical — NNT is undefined (infinite)')
        label = 'NNT (number needed to treat)' if arr > 0 else 'NNH (number needed to harm)'
        return {'type': 'number_needed_to_treat', 'absolute_risk_reduction': _f(arr),
                'relative_risk_reduction_pct': _f(arr / cer * 100) if cer else None,
                'nnt': int(np.ceil(1 / abs(arr))), 'meaning': label}
    except KeyError as e:
        return _err(f'Missing input: {e}')


# ══════════════════════════════════════════════════════════════════════════
# 5. SURVIVAL ANALYSIS
# ══════════════════════════════════════════════════════════════════════════
def _survival_inputs(df, duration_col, event_col):
    e = _need_cols(df, duration_col=duration_col, event_col=event_col)
    if e:
        return None, None, e
    t = pd.to_numeric(df[duration_col], errors='coerce')
    ev, coding = _to_binary(df[event_col])
    if ev is None:
        return None, None, _err('event_col must be binary (1 = event occurred, 0 = censored; or Yes/No)')
    return t, ev, None


def _km_points(times: np.ndarray, events: np.ndarray):
    order = np.argsort(times, kind='mergesort')
    t, e = times[order], events[order]
    ev_times = np.sort(t[e == 1])
    pts, s, n = [(0.0, 1.0)], 1.0, len(t)
    for ut in np.unique(ev_times):
        at_risk = n - np.searchsorted(t, ut, 'left')
        d = np.searchsorted(ev_times, ut, 'right') - np.searchsorted(ev_times, ut, 'left')
        s *= 1 - d / at_risk
        pts.append((float(ut), float(s)))
    return pts


def _median_from(pts):
    for tm, s in pts:
        if s <= 0.5:
            return tm
    return None


def kaplan_meier_survival(df, parameters):
    dur_col, ev_col, grp_col = parameters.get('duration_col'), parameters.get('event_col'), parameters.get('group_col')
    t, ev, e = _survival_inputs(df, dur_col, ev_col)
    if e:
        return e
    frame = pd.DataFrame({'t': t, 'e': ev})
    if grp_col:
        if grp_col not in df.columns:
            return _err(f"group_col '{grp_col}' was not found in this sheet")
        frame['g'] = df[grp_col].astype(str)
    frame = frame.dropna(subset=['t', 'e'])
    frame = frame[frame['t'] >= 0]
    if len(frame) < 5 or frame['e'].sum() < 1:
        return _err('Need at least 5 rows with durations >= 0 and at least one event')

    groups = {'All patients': frame} if not grp_col else \
        {str(k): v for k, v in frame.dropna(subset=['g']).groupby('g')}
    if len(groups) > 8:
        return _err(f'group_col has {len(groups)} levels — choose a column with 8 or fewer groups')

    curves, summary = {}, []
    for name, sub in groups.items():
        pts = _km_points(sub['t'].values.astype(float), sub['e'].values.astype(int))
        curves[name] = pts
        med = _median_from(pts)
        summary.append({'group': name, 'n': int(len(sub)), 'events': int(sub['e'].sum()),
                        'censored': int(len(sub) - sub['e'].sum()),
                        'median_survival': _f(med) if med is not None else 'Not reached'})

    grid = sorted({tm for pts in curves.values() for tm, _ in pts})
    rows = []
    for tm in grid:
        row = {'time': _f(tm)}
        for name, pts in curves.items():
            times_arr = np.array([p[0] for p in pts])
            row[name if grp_col else 'survival'] = _f(pts[np.searchsorted(times_arr, tm, 'right') - 1][1])
        rows.append(row)

    overall_pts = _km_points(frame['t'].values.astype(float), frame['e'].values.astype(int))
    med_all = _median_from(overall_pts)
    return {'type': 'kaplan_meier_survival', 'n': int(len(frame)), 'events': int(frame['e'].sum()),
            'censored': int(len(frame) - frame['e'].sum()),
            'median_survival_overall': _f(med_all) if med_all is not None else 'Not reached',
            'group_summary': summary, 'curve': _thin(rows, 150)}


def cox_proportional_hazards(df, parameters):
    dur_col, ev_col, covs = parameters.get('duration_col'), parameters.get('event_col'), parameters.get('covariates') or []
    t, ev, e = _survival_inputs(df, dur_col, ev_col)
    if e:
        return e
    if not covs:
        return _err('covariates is required')
    miss = [c for c in covs if c not in df.columns]
    if miss:
        return _err(f'Unknown covariates: {miss}')
    X = df[covs].apply(pd.to_numeric, errors='coerce')
    data = pd.concat([t.rename('_t'), ev.rename('_e'), X], axis=1).dropna()
    data = data[data['_t'] > 0]
    if len(data) < len(covs) * 5 + 5 or data['_e'].sum() < len(covs) + 2:
        return _err('Not enough rows / events for this many covariates (aim for >= 10 events per covariate)')
    try:
        from statsmodels.duration.hazard_regression import PHReg
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            res = PHReg(data['_t'].values, data[covs].values.astype(float), status=data['_e'].values.astype(int)).fit(disp=0)
    except Exception as ex:
        return _err(f'Cox model failed to converge (collinear or constant covariate?): {ex}')
    rows = []
    for i, name in enumerate(covs):
        b, se = float(res.params[i]), float(res.bse[i])
        rows.append({'variable': name, 'coef': _f(b), 'hazard_ratio': _f(np.exp(b)),
                     'hr_ci_low': _f(np.exp(b - 1.96 * se)), 'hr_ci_high': _f(np.exp(b + 1.96 * se)),
                     'p_value': _f(res.pvalues[i], 6)})
    return {'type': 'cox_proportional_hazards', 'n_obs': int(len(data)), 'events': int(data['_e'].sum()),
            'log_likelihood': _f(res.llf), 'table': rows}


def logrank_survival_test(df, parameters):
    dur_col, ev_col, grp_col = parameters.get('duration_col'), parameters.get('event_col'), parameters.get('group_col')
    t, ev, e = _survival_inputs(df, dur_col, ev_col)
    if e:
        return e
    e2 = _need_cols(df, group_col=grp_col)
    if e2:
        return e2
    data = pd.DataFrame({'t': t, 'e': ev, 'g': df[grp_col].astype(str).where(df[grp_col].notna())}).dropna()
    levels = sorted(data['g'].unique().tolist())
    if len(levels) != 2:
        return _err(f'Log-rank test here needs exactly 2 groups; group_col has {len(levels)}: {levels[:6]}')
    T, E, G = data['t'].values.astype(float), data['e'].values.astype(int), (data['g'] == levels[0]).values
    O1 = E_exp = V = 0.0
    for ut in np.unique(T[E == 1]):
        at_risk = T >= ut
        n, n1 = at_risk.sum(), (at_risk & G).sum()
        d = ((T == ut) & (E == 1)).sum()
        d1 = ((T == ut) & (E == 1) & G).sum()
        O1 += d1
        E_exp += d * n1 / n
        if n > 1:
            V += d * (n1 / n) * (1 - n1 / n) * (n - d) / (n - 1)
    if V <= 0:
        return _err('Variance is zero — not enough events to compare the groups')
    chi2 = (O1 - E_exp) ** 2 / V
    p = float(stats.chi2.sf(chi2, 1))
    n1_tot = int(G.sum())
    ev1, ev2 = int(E[G].sum()), int(E[~G].sum())
    return {'type': 'logrank_survival_test', 'chi_square': _f(chi2), 'p_value': _f(p, 6), 'significant': bool(p < 0.05),
            'interpretation': 'Survival differs significantly between the groups' if p < 0.05 else 'No significant survival difference',
            'group_summary': [
                {'group': levels[0], 'n': n1_tot, 'observed_events': ev1, 'expected_events': _f(E_exp, 2)},
                {'group': levels[1], 'n': int(len(G) - n1_tot), 'observed_events': ev2, 'expected_events': _f(ev1 + ev2 - E_exp, 2)}]}


# ══════════════════════════════════════════════════════════════════════════
# 6. MEDICAL COUNT MODELS
# ══════════════════════════════════════════════════════════════════════════
def _count_design(df, count_col, predictors):
    e = _need_cols(df, count_col=count_col)
    if e or not predictors:
        return None, None, e or _err('predictors is required')
    miss = [c for c in predictors if c not in df.columns]
    if miss:
        return None, None, _err(f'Unknown predictors: {miss}')
    y = pd.to_numeric(df[count_col], errors='coerce')
    X = df[predictors].apply(pd.to_numeric, errors='coerce')
    data = pd.concat([y.rename('_y'), X], axis=1).dropna()
    if len(data) < len(predictors) + 10:
        return None, None, _err('Not enough complete rows to fit the model')
    if (data['_y'] < 0).any() or (data['_y'] % 1 != 0).any():
        return None, None, _err('count_col must contain non-negative whole numbers')
    return data['_y'], sm.add_constant(data[predictors]), None


def poisson_regression(df, parameters):
    y, X, e = _count_design(df, parameters.get('count_col'), parameters.get('predictors') or [])
    if e:
        return e
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            res = sm.GLM(y, X, family=sm.families.Poisson()).fit()
    except Exception as ex:
        return _err(f'Poisson regression failed: {ex}')
    disp = res.pearson_chi2 / res.df_resid if res.df_resid else None
    return {'type': 'poisson_regression', 'n_obs': int(res.nobs), 'dispersion': _f(disp),
            'overdispersed': bool(disp is not None and disp > 1.5),
            'advice': 'Counts look over-dispersed (dispersion > 1.5) — prefer Negative Binomial regression'
                      if disp is not None and disp > 1.5 else 'Dispersion is acceptable for a Poisson model',
            'table': _coef_table(res, 'incidence_rate_ratio')}


def negative_binomial_regression(df, parameters):
    y, X, e = _count_design(df, parameters.get('count_col'), parameters.get('predictors') or [])
    if e:
        return e
    method, alpha, res = None, None, None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            nb = sm.NegativeBinomial(y, X).fit(disp=0, maxiter=300)
        if np.isfinite(nb.params.values).all():
            res, method, alpha = nb, 'Maximum likelihood (dispersion alpha estimated)', float(nb.params['alpha'])
    except Exception:
        res = None
    if res is None:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                res = sm.GLM(y, X, family=sm.families.NegativeBinomial(alpha=1.0)).fit()
            method, alpha = 'GLM with fixed alpha = 1.0 (ML fit did not converge)', 1.0
        except Exception as ex:
            return _err(f'Negative binomial regression failed: {ex}')
    table = [r for r in _coef_table(res, 'incidence_rate_ratio') if r['variable'] != 'alpha']
    return {'type': 'negative_binomial_regression', 'n_obs': int(res.nobs), 'method': method,
            'alpha_dispersion': _f(alpha), 'table': table}


# ══════════════════════════════════════════════════════════════════════════
# 7. PHARMACEUTICAL ANALYTICS
# ══════════════════════════════════════════════════════════════════════════
def _four_pl(x, bottom, top, ec50, hill):
    return bottom + (top - bottom) / (1 + (x / ec50) ** hill)


def _r2(y, yhat):
    ss_res, ss_tot = np.sum((y - yhat) ** 2), np.sum((y - np.mean(y)) ** 2)
    return 1 - ss_res / ss_tot if ss_tot > 0 else None


def dose_response_analysis(df, parameters):
    dose_col, resp_col = parameters.get('dose_col'), parameters.get('response_col')
    e = _need_cols(df, dose_col=dose_col, response_col=resp_col)
    if e:
        return e
    data = df[[dose_col, resp_col]].apply(pd.to_numeric, errors='coerce').dropna()
    data = data[data[dose_col] > 0].sort_values(dose_col)
    if len(data) < 5 or data[dose_col].nunique() < 4:
        return _err('Need at least 5 rows covering 4+ distinct positive doses for a 4-parameter fit')
    x, y = data[dose_col].values.astype(float), data[resp_col].values.astype(float)
    slope_sign = 1 if np.corrcoef(np.log(x), y)[0, 1] >= 0 else -1
    p0 = [y.min(), y.max(), float(np.median(x)), slope_sign * 1.0 if False else 1.0]
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            popt, _ = curve_fit(_four_pl, x, y, p0=p0, maxfev=20000,
                                bounds=([-np.inf, -np.inf, x.min() / 100, 0.05], [np.inf, np.inf, x.max() * 100, 25]))
    except Exception as ex:
        return _err(f'4-parameter logistic fit did not converge: {ex}')
    fitted = _four_pl(x, *popt)
    curve = _thin([{'dose': _f(a, 6), 'observed': _f(b), 'fitted': _f(c)} for a, b, c in zip(x, y, fitted)], 150)
    # In Y = B + (T-B)/(1+(X/EC50)^h) the response at ZERO dose is T and at
    # INFINITE dose is B, so for an increasing curve the raw "Bottom"/"Top" are
    # swapped. Report them as the lower / upper asymptote plus a direction.
    at_zero, at_inf = float(popt[1]), float(popt[0])
    increasing = at_inf > at_zero
    return {'type': 'dose_response_analysis', 'n': int(len(x)),
            'direction': 'Increasing (stimulatory)' if increasing else 'Decreasing (inhibitory)',
            'bottom': _f(min(at_zero, at_inf)), 'top': _f(max(at_zero, at_inf)),
            'response_at_zero_dose': _f(at_zero), 'response_at_max_dose_limit': _f(at_inf),
            'EC50': _f(popt[2], 6), 'hill_slope': _f(popt[3]), 'r_squared': _f(_r2(y, fitted)), 'curve': curve}


def bioequivalence_analysis(df, parameters):
    test_col, ref_col = parameters.get('test_col'), parameters.get('reference_col')
    e = _need_cols(df, test_col=test_col, reference_col=ref_col)
    if e:
        return e
    data = df[[test_col, ref_col]].apply(pd.to_numeric, errors='coerce').dropna()
    if len(data) < 3 or (data <= 0).any().any():
        return _err('Need at least 3 paired rows, all strictly positive (e.g. AUC or Cmax per subject)')
    diff = np.log(data[test_col].values) - np.log(data[ref_col].values)
    mean_d, se = diff.mean(), stats.sem(diff)
    lo, hi = stats.t.interval(0.90, len(diff) - 1, loc=mean_d, scale=se)
    lo, hi = float(np.exp(lo)), float(np.exp(hi))
    be = lo >= 0.80 and hi <= 1.25
    return {'type': 'bioequivalence_analysis', 'n_pairs': int(len(diff)),
            'geometric_mean_ratio': _f(np.exp(mean_d)), 'ci90_low': _f(lo), 'ci90_high': _f(hi),
            'bioequivalent': bool(be),
            'conclusion': 'Bioequivalent — 90% CI lies within 80%–125%' if be else
                          'Bioequivalence NOT demonstrated — 90% CI falls outside 80%–125%',
            'design_note': 'Assumes paired (crossover-style) data: one test and one reference value per subject'}


def pharmacovigilance_signal(df, parameters):
    try:
        a, b, c, d = _two_by_two(parameters)
        zero = min(a, b, c, d) == 0
        a2, b2, c2, d2 = (a + .5, b + .5, c + .5, d + .5) if zero else (a, b, c, d)
        ror = (a2 * d2) / (b2 * c2)
        se_r = np.sqrt(1 / a2 + 1 / b2 + 1 / c2 + 1 / d2)
        ror_lo, ror_hi = np.exp(np.log(ror) - 1.96 * se_r), np.exp(np.log(ror) + 1.96 * se_r)
        prr = (a2 / (a2 + b2)) / (c2 / (c2 + d2))
        se_p = np.sqrt(1 / a2 - 1 / (a2 + b2) + 1 / c2 - 1 / (c2 + d2))
        n = a + b + c + d
        denom = (a + b) * (c + d) * (a + c) * (b + d)
        chi2 = n * (a * d - b * c) ** 2 / denom if denom else 0.0
        prr_signal = bool(prr >= 2 and chi2 >= 4 and a >= 3)
        out = {'type': 'pharmacovigilance_signal', 'ROR': _f(ror), 'ror_ci95_low': _f(ror_lo), 'ror_ci95_high': _f(ror_hi),
               'ror_signal': bool(ror_lo > 1), 'PRR': _f(prr),
               'prr_ci95_low': _f(np.exp(np.log(prr) - 1.96 * se_p)), 'prr_ci95_high': _f(np.exp(np.log(prr) + 1.96 * se_p)),
               'chi_square': _f(chi2), 'prr_signal_evans_criteria': prr_signal,
               'conclusion': 'Potential safety signal detected' if (ror_lo > 1 or prr_signal) else 'No disproportionality signal'}
        if zero:
            out['note'] = 'A zero cell was present — 0.5 was added to every cell for ROR/PRR'
        return out
    except (KeyError, ValueError) as e:
        return _err(f'Invalid input: {e}')


def pk_analysis(df, parameters):
    tcol, ccol = parameters.get('time_col'), parameters.get('concentration_col')
    e = _need_cols(df, time_col=tcol, concentration_col=ccol)
    if e:
        return e
    data = df[[tcol, ccol]].apply(pd.to_numeric, errors='coerce').dropna().sort_values(tcol)
    data = data.groupby(tcol, as_index=False)[ccol].mean()
    if len(data) < 4:
        return _err('Need at least 4 distinct time points')
    t, c = data[tcol].values.astype(float), data[ccol].values.astype(float)
    auc_t = float(_trapz(c, t))
    imax = int(np.argmax(c))
    out = {'type': 'pk_analysis', 'AUC_0_t': _f(auc_t), 'Cmax': _f(c[imax]), 'Tmax': _f(t[imax]), 'C_last': _f(c[-1])}
    tail_t, tail_c = t[-3:], c[-3:]
    if (tail_c > 0).all() and imax < len(t) - 3:
        slope, intercept, r, _, _ = stats.linregress(tail_t, np.log(tail_c))
        if slope < 0:
            ke = -slope
            out.update({'elimination_rate_ke': _f(ke, 6), 'half_life': _f(np.log(2) / ke),
                        'AUC_0_inf': _f(auc_t + c[-1] / ke), 'terminal_fit_r_squared': _f(r ** 2)})
    out['curve'] = _thin([{'time': _f(a), 'concentration': _f(b)} for a, b in zip(t, c)], 150)
    return out


def pd_analysis(df, parameters):
    ccol, ecol = parameters.get('concentration_col'), parameters.get('effect_col')
    e = _need_cols(df, concentration_col=ccol, effect_col=ecol)
    if e:
        return e
    data = df[[ccol, ecol]].apply(pd.to_numeric, errors='coerce').dropna()
    data = data[data[ccol] >= 0].sort_values(ccol)
    if len(data) < 5:
        return _err('Need at least 5 concentration-effect pairs')
    x, y = data[ccol].values.astype(float), data[ecol].values.astype(float)
    pos = x[x > 0]
    if len(pos) == 0:
        return _err('Concentrations must include positive values')
    emax_f = lambda cc, emax, ec50: emax * cc / (ec50 + cc)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            popt, _ = curve_fit(emax_f, x, y, p0=[max(y.max(), 1e-6), float(np.median(pos))], maxfev=20000,
                                bounds=([-np.inf, pos.min() / 1000], [np.inf, pos.max() * 1000]))
    except Exception as ex:
        return _err(f'Emax model did not converge: {ex}')
    fitted = emax_f(x, *popt)
    return {'type': 'pd_analysis', 'n': int(len(x)), 'Emax': _f(popt[0]), 'EC50': _f(popt[1], 6),
            'r_squared': _f(_r2(y, fitted)),
            'curve': _thin([{'concentration': _f(a, 6), 'observed': _f(b), 'fitted': _f(c)} for a, b, c in zip(x, y, fitted)], 150)}


# ══════════════════════════════════════════════════════════════════════════
# 8. META-ANALYSIS
# ══════════════════════════════════════════════════════════════════════════
def _meta_inputs(parameters):
    eff = np.array([float(x) for x in parameters.get('effect_sizes', [])])
    se = np.array([float(x) for x in parameters.get('standard_errors', [])])
    if len(eff) < 2 or len(eff) != len(se):
        raise ValueError('Provide at least 2 studies, with the same number of effect sizes and standard errors')
    if (se <= 0).any():
        raise ValueError('Every standard error must be > 0')
    return eff, se


def fixed_effect_meta_analysis(df, parameters):
    try:
        eff, se = _meta_inputs(parameters)
    except ValueError as e:
        return _err(str(e))
    w = 1 / se ** 2
    pooled, pse = float(np.sum(w * eff) / np.sum(w)), float(np.sqrt(1 / np.sum(w)))
    z = pooled / pse
    return {'type': 'fixed_effect_meta_analysis', 'n_studies': int(len(eff)), 'pooled_effect': _f(pooled),
            'pooled_se': _f(pse), 'ci95_low': _f(pooled - 1.96 * pse), 'ci95_high': _f(pooled + 1.96 * pse),
            'z_statistic': _f(z), 'p_value': _f(2 * stats.norm.sf(abs(z)), 6),
            'studies': [{'study': i + 1, 'effect': _f(e_), 'se': _f(s_), 'weight_pct': _f(w_ / w.sum() * 100, 2)}
                        for i, (e_, s_, w_) in enumerate(zip(eff, se, w))]}


def meta_analysis_heterogeneity(df, parameters):
    try:
        eff, se = _meta_inputs(parameters)
    except ValueError as e:
        return _err(str(e))
    w = 1 / se ** 2
    pooled = np.sum(w * eff) / np.sum(w)
    Q = float(np.sum(w * (eff - pooled) ** 2))
    dof = len(eff) - 1
    i2 = max(0.0, (Q - dof) / Q * 100) if Q > 0 else 0.0
    c = np.sum(w) - np.sum(w ** 2) / np.sum(w)
    tau2 = max(0.0, (Q - dof) / c) if c > 0 else 0.0
    return {'type': 'meta_analysis_heterogeneity', 'Q': _f(Q), 'degrees_of_freedom': dof,
            'q_p_value': _f(stats.chi2.sf(Q, dof), 6), 'I_squared_pct': _f(i2, 2), 'tau_squared': _f(tau2, 6),
            'interpretation': 'Low heterogeneity' if i2 < 25 else 'Moderate heterogeneity' if i2 < 50 else
                              'Substantial heterogeneity — consider a random-effects model' if i2 < 75 else
                              'Considerable heterogeneity — pooling may not be appropriate'}


# ══════════════════════════════════════════════════════════════════════════
# 9. HEALTH ECONOMICS
# ══════════════════════════════════════════════════════════════════════════
def incremental_cost_effectiveness_ratio(df, parameters):
    try:
        ca, cb = _num(parameters, 'cost_a'), _num(parameters, 'cost_b')
        ea, eb = _num(parameters, 'effect_a'), _num(parameters, 'effect_b')
        dc, de = ca - cb, ea - eb
        if de == 0:
            return _err('Effects are identical — ICER is undefined')
        if dc <= 0 and de > 0:
            verdict = 'Strategy A dominates — cheaper and more effective'
        elif dc >= 0 and de < 0:
            verdict = 'Strategy A is dominated — costlier and less effective'
        elif dc > 0 and de > 0:
            verdict = 'A is more effective but costlier — compare ICER to your willingness-to-pay threshold'
        else:
            verdict = 'A is cheaper but less effective — compare savings per effect lost to your threshold'
        return {'type': 'incremental_cost_effectiveness_ratio', 'incremental_cost': _f(dc), 'incremental_effect': _f(de),
                'icer': _f(dc / de), 'verdict': verdict}
    except KeyError as e:
        return _err(f'Missing input: {e}')


def qaly(df, parameters):
    try:
        ly, u = _num(parameters, 'life_years'), _num(parameters, 'utility_weight')
        if ly < 0 or not 0 <= u <= 1:
            return _err('life_years must be >= 0 and utility_weight between 0 (death) and 1 (perfect health)')
        return {'type': 'qaly', 'life_years': ly, 'utility_weight': u, 'qaly': _f(ly * u)}
    except KeyError as e:
        return _err(f'Missing input: {e}')


def daly(df, parameters):
    try:
        yll, yld = _num(parameters, 'years_life_lost'), _num(parameters, 'years_lived_with_disability')
        if yll < 0 or yld < 0:
            return _err('YLL and YLD cannot be negative')
        return {'type': 'daly', 'years_life_lost': yll, 'years_lived_with_disability': yld, 'daly': _f(yll + yld)}
    except KeyError as e:
        return _err(f'Missing input: {e}')


def budget_impact(df, parameters):
    try:
        pop, up = _num(parameters, 'eligible_population'), _num(parameters, 'uptake_rate')
        cost, comp = _num(parameters, 'cost_per_patient'), float(parameters.get('comparator_cost') or 0)
        if pop < 0 or not 0 <= up <= 1:
            return _err('eligible_population must be >= 0 and uptake_rate a fraction between 0 and 1')
        treated = pop * up
        new, old = treated * cost, treated * comp
        return {'type': 'budget_impact', 'patients_treated': _f(treated, 2), 'new_intervention_cost': _f(new, 2),
                'comparator_cost': _f(old, 2), 'net_budget_impact': _f(new - old, 2)}
    except KeyError as e:
        return _err(f'Missing input: {e}')


def markov_model(df, parameters):
    try:
        init = np.array([float(x) for x in parameters.get('initial_state', [])])
        P = np.array(parameters.get('transition_matrix', []), dtype=float)
        cycles = int(float(parameters.get('cycles') or 20))
        k = len(init)
        if k < 2 or P.shape != (k, k):
            return _err(f'transition_matrix must be a {k}x{k} square matrix matching initial_state ({k} states)')
        if (P < 0).any() or not np.allclose(P.sum(axis=1), 1.0, atol=1e-6):
            return _err('Every row of the transition matrix must be non-negative and sum to 1')
        if abs(init.sum() - 1.0) > 1e-6 and init.sum() <= 0:
            return _err('initial_state must sum to a positive total')
        if not 1 <= cycles <= 500:
            return _err('cycles must be between 1 and 500')
        states = [init]
        for _ in range(cycles):
            states.append(states[-1] @ P)
        arr = np.array(states)
        curve = [{'cycle': i, **{f'state_{j + 1}': _f(v, 4) for j, v in enumerate(row)}} for i, row in enumerate(arr)]
        return {'type': 'markov_model', 'n_states': k, 'cycles': cycles,
                'final_distribution': [{'state': f'state_{j + 1}', 'proportion': _f(v, 4)} for j, v in enumerate(arr[-1])],
                'cumulative_cycles_in_state': [{'state': f'state_{j + 1}', 'expected_cycles': _f(arr[:, j].sum(), 3)} for j in range(k)],
                'curve': _thin(curve, 200)}
    except (ValueError, TypeError) as e:
        return _err(f'Invalid matrix input: {e}')


# ══════════════════════════════════════════════════════════════════════════
# 10. LIFE SCIENCES & GENETICS
# ══════════════════════════════════════════════════════════════════════════
def gene_expression_fold_change(df, parameters):
    tcol, ccol, gcol = parameters.get('treatment_col'), parameters.get('control_col'), parameters.get('gene_col')
    e = _need_cols(df, treatment_col=tcol, control_col=ccol)
    if e:
        return e
    data = pd.DataFrame({'t': pd.to_numeric(df[tcol], errors='coerce'), 'c': pd.to_numeric(df[ccol], errors='coerce')})
    data['gene'] = df[gcol].astype(str) if gcol and gcol in df.columns else (df.index + 1).astype(str)
    data = data.dropna(subset=['t', 'c'])
    usable = data[(data['t'] > 0) & (data['c'] > 0)].copy()
    if usable.empty:
        return _err('No rows with positive expression in both columns')
    usable['fold_change'] = usable['t'] / usable['c']
    usable['log2_fc'] = np.log2(usable['fold_change'])
    fmt = lambda d: [{'gene': r.gene, 'fold_change': _f(r.fold_change), 'log2_fc': _f(r.log2_fc)} for r in d.itertuples()]
    return {'type': 'gene_expression_fold_change', 'n_genes': int(len(usable)), 'excluded_non_positive': int(len(data) - len(usable)),
            'mean_log2_fc': _f(usable['log2_fc'].mean()), 'upregulated_log2fc_ge_1': int((usable['log2_fc'] >= 1).sum()),
            'downregulated_log2fc_le_minus1': int((usable['log2_fc'] <= -1).sum()),
            'top_upregulated': fmt(usable.nlargest(10, 'log2_fc')), 'top_downregulated': fmt(usable.nsmallest(10, 'log2_fc'))}


def differential_expression_ttest(df, parameters):
    tcol, ccol = parameters.get('treatment_col'), parameters.get('control_col')
    e = _need_cols(df, treatment_col=tcol, control_col=ccol)
    if e:
        return e
    t, c = _numeric_series(df, tcol), _numeric_series(df, ccol)
    if len(t) < 2 or len(c) < 2:
        return _err('Each group needs at least 2 numeric values')
    ts, p = stats.ttest_ind(t, c, equal_var=False)
    log2fc = np.log2(t.mean() / c.mean()) if t.mean() > 0 and c.mean() > 0 else None
    return {'type': 'differential_expression_ttest', 'n_treatment': int(len(t)), 'n_control': int(len(c)),
            'mean_treatment': _f(t.mean()), 'mean_control': _f(c.mean()), 'log2_fold_change_of_means': _f(log2fc),
            't_statistic': _f(ts), 'p_value': _f(p, 6), 'significant': bool(p < 0.05)}


def rna_seq_tpm(df, parameters):
    ccol, lcol, gcol = parameters.get('counts_col'), parameters.get('length_col'), parameters.get('gene_col')
    e = _need_cols(df, counts_col=ccol, length_col=lcol)
    if e:
        return e
    data = pd.DataFrame({'counts': pd.to_numeric(df[ccol], errors='coerce'), 'length': pd.to_numeric(df[lcol], errors='coerce')})
    data['gene'] = df[gcol].astype(str) if gcol and gcol in df.columns else (df.index + 1).astype(str)
    data = data.dropna(subset=['counts', 'length'])
    data = data[(data['length'] > 0) & (data['counts'] >= 0)]
    if data.empty or (data['counts'] / (data['length'] / 1000)).sum() == 0:
        return _err('No usable rows (gene length must be > 0 and counts >= 0, with some non-zero counts)')
    rpk = data['counts'] / (data['length'] / 1000)
    data['tpm'] = rpk / rpk.sum() * 1e6
    top = data.nlargest(10, 'tpm')
    return {'type': 'rna_seq_tpm', 'n_genes': int(len(data)), 'tpm_total': _f(data['tpm'].sum(), 2),
            'genes_expressed_tpm_gt_1': int((data['tpm'] > 1).sum()), 'median_tpm': _f(data['tpm'].median()),
            'top_expressed': [{'gene': r.gene, 'counts': _f(r.counts, 2), 'length': _f(r.length, 0), 'tpm': _f(r.tpm, 2)} for r in top.itertuples()]}


def pathway_enrichment(df, parameters):
    try:
        N, K = int(round(_num(parameters, 'total_genes'))), int(round(_num(parameters, 'pathway_genes')))
        n, k = int(round(_num(parameters, 'selected_genes'))), int(round(_num(parameters, 'overlap_genes')))
        if not (0 < K <= N and 0 < n <= N and 0 <= k <= min(K, n)):
            return _err('Need 0 < pathway_genes <= total_genes, 0 < selected_genes <= total_genes, 0 <= overlap <= min(pathway, selected)')
        p = float(stats.hypergeom(N, K, n).sf(k - 1))
        expected = n * K / N
        return {'type': 'pathway_enrichment', 'expected_overlap': _f(expected, 3),
                'fold_enrichment': _f(k / expected) if expected else None, 'p_value': _f(p, 8), 'enriched': bool(p < 0.05)}
    except KeyError as e:
        return _err(f'Missing input: {e}')


def hardy_weinberg_equilibrium(df, parameters):
    try:
        aa, ab, bb = (_num(parameters, k) for k in ('obs_AA', 'obs_Aa', 'obs_aa'))
        n = aa + ab + bb
        if min(aa, ab, bb) < 0 or n <= 0:
            return _err('Genotype counts must be non-negative with a positive total')
        p = (2 * aa + ab) / (2 * n)
        q = 1 - p
        if p <= 0 or q <= 0:
            return _err('Monomorphic locus (one allele only) — HWE cannot be tested')
        exp = [p ** 2 * n, 2 * p * q * n, q ** 2 * n]
        chi2, pv = stats.chisquare([aa, ab, bb], exp, ddof=1)  # df = 3 - 1 - 1 = 1
        return {'type': 'hardy_weinberg_equilibrium', 'p_allele_A': _f(p), 'q_allele_a': _f(q),
                'expected_AA': _f(exp[0], 2), 'expected_Aa': _f(exp[1], 2), 'expected_aa': _f(exp[2], 2),
                'chi_square': _f(chi2), 'degrees_of_freedom': 1, 'p_value': _f(pv, 6),
                'in_equilibrium': bool(pv >= 0.05),
                'interpretation': 'Consistent with Hardy-Weinberg equilibrium' if pv >= 0.05 else 'Deviates from Hardy-Weinberg equilibrium'}
    except KeyError as e:
        return _err(f'Missing input: {e}')


def gwas_single_snp(df, parameters):
    dcol, scol, covs = parameters.get('disease_col'), parameters.get('snp_col'), parameters.get('covariates') or []
    e = _need_cols(df, disease_col=dcol, snp_col=scol)
    if e:
        return e
    miss = [c for c in covs if c not in df.columns]
    if miss:
        return _err(f'Unknown covariates: {miss}')
    y, coding = _to_binary(df[dcol])
    if y is None:
        return _err('disease_col must be binary (case/control, 0/1, Yes/No)')
    X = df[[scol] + covs].apply(pd.to_numeric, errors='coerce')
    data = pd.concat([y.rename('_y'), X], axis=1).dropna()
    if len(data) < 20 or data['_y'].nunique() < 2 or data[scol].nunique() < 2:
        return _err('Need >= 20 complete rows, both cases and controls, and a SNP with variation')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            res = sm.Logit(data['_y'], sm.add_constant(data[[scol] + covs])).fit(disp=0)
    except Exception as ex:
        return _err(f'Logistic model failed: {ex}')
    ci = np.asarray(res.conf_int())
    b = float(res.params[scol])
    maf = float(data[scol].mean() / 2) if data[scol].between(0, 2).all() else None
    return {'type': 'gwas_single_snp', 'snp': scol, 'n_obs': int(res.nobs), 'coefficient': _f(b),
            'odds_ratio_per_allele': _f(np.exp(b)), 'or_ci95_low': _f(np.exp(ci[1, 0])), 'or_ci95_high': _f(np.exp(ci[1, 1])),
            'p_value': _f(res.pvalues[scol], 8), 'genome_wide_significant_p_lt_5e8': bool(res.pvalues[scol] < 5e-8),
            'minor_allele_frequency': _f(maf), 'outcome_coding': coding}


def polygenic_risk_score(df, parameters):
    snps, betas = parameters.get('snp_cols') or [], [float(x) for x in parameters.get('effect_sizes') or []]
    if df is None or not snps:
        return _err('snp_cols is required')
    if len(snps) != len(betas):
        return _err(f'effect_sizes has {len(betas)} values but snp_cols has {len(snps)}')
    miss = [c for c in snps if c not in df.columns]
    if miss:
        return _err(f'Unknown SNP columns: {miss}')
    G = df[snps].apply(pd.to_numeric, errors='coerce').dropna()
    if G.empty:
        return _err('No rows with complete genotype data')
    prs = G.values @ np.array(betas)
    hist, edges = np.histogram(prs, bins=15)
    pct = np.percentile(prs, [20, 40, 60, 80])
    return {'type': 'polygenic_risk_score', 'n_individuals': int(len(prs)), 'n_variants': len(snps),
            'mean_prs': _f(prs.mean()), 'sd_prs': _f(prs.std(ddof=1)) if len(prs) > 1 else None,
            'min_prs': _f(prs.min()), 'max_prs': _f(prs.max()),
            'quintile_cutoffs': [{'quintile_boundary': f'{p}th percentile', 'prs': _f(v)} for p, v in zip([20, 40, 60, 80], pct)],
            'histogram': [{'bin_start': _f(edges[i]), 'bin_end': _f(edges[i + 1]), 'count': int(hist[i])} for i in range(len(hist))]}


# ══════════════════════════════════════════════════════════════════════════
# 11. HOSPITAL, NURSING & OUTCOMES
# ══════════════════════════════════════════════════════════════════════════
def bed_occupancy_rate(df, parameters):
    try:
        ipd, abd = _num(parameters, 'inpatient_days'), _num(parameters, 'available_bed_days')
        if abd <= 0 or ipd < 0:
            return _err('available_bed_days must be > 0 and inpatient_days >= 0')
        r = ipd / abd * 100
        return {'type': 'bed_occupancy_rate', 'bed_occupancy_pct': _f(r),
                'interpretation': 'Very high — little surge capacity' if r > 90 else 'Efficient range (about 80–90%)' if r >= 75
                                  else 'Under-utilised capacity'}
    except KeyError as e:
        return _err(f'Missing input: {e}')


def average_length_of_stay(df, parameters):
    try:
        days, dis = _num(parameters, 'total_inpatient_days'), _num(parameters, 'discharges')
        if dis <= 0 or days < 0:
            return _err('discharges must be > 0 and total_inpatient_days >= 0')
        return {'type': 'average_length_of_stay', 'alos_days': _f(days / dis)}
    except KeyError as e:
        return _err(f'Missing input: {e}')


def nursing_workload(df, parameters):
    try:
        counts = np.array([float(x) for x in parameters.get('patient_counts', [])])
        w = np.array([float(x) for x in parameters.get('acuity_weights', [])])
        if len(counts) == 0 or len(counts) != len(w):
            return _err('patient_counts and acuity_weights must be non-empty and the same length')
        total = float(np.sum(counts * w))
        out = {'type': 'nursing_workload', 'total_patients': _f(counts.sum(), 2), 'workload_points': _f(total, 2)}
        nurses = _opt(parameters, 'number_of_nurses')
        if nurses:
            out['workload_per_nurse'] = _f(total / nurses, 2)
        return out
    except ValueError as e:
        return _err(f'Invalid numbers: {e}')


def nurse_patient_ratio(df, parameters):
    try:
        pts, nurses = _num(parameters, 'number_of_patients'), _num(parameters, 'number_of_nurses')
        if nurses <= 0 or pts < 0:
            return _err('number_of_nurses must be > 0')
        return {'type': 'nurse_patient_ratio', 'patients_per_nurse': _f(pts / nurses, 2),
                'ratio': f'1 : {pts / nurses:.1f}'}
    except KeyError as e:
        return _err(f'Missing input: {e}')


def care_quality_indicators(df, parameters):
    out, readm, dis = {'type': 'care_quality_indicators'}, _opt(parameters, 'readmissions'), _opt(parameters, 'discharges')
    falls, ulcers, pdays = _opt(parameters, 'number_of_falls'), _opt(parameters, 'pressure_ulcers'), _opt(parameters, 'patient_days')
    if readm is not None and dis:
        out['readmission_rate_pct'] = _f(readm / dis * 100)
    if falls is not None and pdays:
        out['falls_per_1000_patient_days'] = _f(falls / pdays * 1000)
    if ulcers is not None and pdays:
        out['pressure_ulcers_per_1000_patient_days'] = _f(ulcers / pdays * 1000)
    if len(out) == 1:
        return _err('Provide at least one complete pair: readmissions + discharges, falls + patient days, or pressure ulcers + patient days')
    return out


def _outcome_design(df, outcome, treatment, risk_factors):
    e = _need_cols(df, outcome=outcome, treatment=treatment)
    if e:
        return None, None, None, e
    miss = [c for c in risk_factors if c not in df.columns]
    if miss:
        return None, None, None, _err(f'Unknown risk_factors: {miss}')
    trt = pd.to_numeric(df[treatment], errors='coerce')
    if trt.notna().sum() < 0.9 * df[treatment].notna().sum():
        trt, _ = _to_binary(df[treatment])
        if trt is None:
            return None, None, None, _err('treatment must be numeric or binary (Yes/No, Drug/Placebo, ...)')
    return trt, pd.to_numeric(df[outcome], errors='coerce'), df[risk_factors].apply(pd.to_numeric, errors='coerce'), None


def health_outcome_regression(df, parameters):
    outcome, treatment, rf = parameters.get('outcome'), parameters.get('treatment'), parameters.get('risk_factors') or []
    trt, y, X, e = _outcome_design(df, outcome, treatment, rf)
    if e:
        return e
    data = pd.concat([y.rename('_y'), trt.rename(treatment), X], axis=1).dropna()
    if len(data) < len(rf) + 8:
        return _err('Not enough complete rows')
    res = sm.OLS(data['_y'], sm.add_constant(data[[treatment] + rf])).fit(cov_type='HC3')
    return {'type': 'health_outcome_regression', 'n_obs': int(res.nobs), 'r_squared': _f(res.rsquared),
            'adj_r_squared': _f(res.rsquared_adj), 'treatment_effect_adjusted': _f(res.params[treatment]),
            'treatment_p_value': _f(res.pvalues[treatment], 6), 'standard_errors': 'HC3 robust', 'table': _coef_table(res)}


def binary_health_outcome_model(df, parameters):
    outcome, treatment, rf = parameters.get('outcome'), parameters.get('treatment'), parameters.get('risk_factors') or []
    e0 = _need_cols(df, outcome=outcome)
    if e0:
        return e0
    yb, coding = _to_binary(df[outcome])
    if yb is None:
        return _err('outcome must be binary (0/1, Yes/No, ...)')
    trt, _, X, e = _outcome_design(df, outcome, treatment, rf)
    if e:
        return e
    data = pd.concat([yb.rename('_y'), trt.rename(treatment), X], axis=1).dropna()
    if len(data) < len(rf) + 12 or data['_y'].nunique() < 2:
        return _err('Not enough complete rows or only one outcome level')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            res = sm.Logit(data['_y'], sm.add_constant(data[[treatment] + rf])).fit(disp=0)
    except Exception as ex:
        return _err(f'Logistic model failed: {ex}')
    return {'type': 'binary_health_outcome_model', 'n_obs': int(res.nobs), 'outcome_coding': coding,
            'adjusted_odds_ratio_treatment': _f(np.exp(res.params[treatment])),
            'treatment_p_value': _f(res.pvalues[treatment], 6), 'pseudo_r_squared': _f(res.prsquared),
            'table': _coef_table(res, 'odds_ratio')}


def satisfaction_summary(df, parameters):
    cols = parameters.get('satisfaction_cols') or []
    if df is None or not cols:
        return _err('satisfaction_cols is required')
    miss = [c for c in cols if c not in df.columns]
    if miss:
        return _err(f'Unknown columns: {miss}')
    data = df[cols].apply(pd.to_numeric, errors='coerce').dropna()
    if data.empty:
        return _err('No complete numeric rows across the selected items')
    return {'type': 'satisfaction_summary', 'n_respondents': int(len(data)), 'n_items': len(cols),
            'overall_satisfaction': _f(data.mean(axis=1).mean()),
            'table': [{'item': c, 'mean': _f(data[c].mean()), 'median': _f(data[c].median()), 'std_dev': _f(data[c].std())} for c in cols]}


def cronbach_alpha(df, parameters):
    items = parameters.get('items') or []
    if df is None or len(items) < 2:
        return _err('Select at least 2 item columns')
    miss = [c for c in items if c not in df.columns]
    if miss:
        return _err(f'Unknown columns: {miss}')
    data = df[items].apply(pd.to_numeric, errors='coerce').dropna()
    if len(data) < 3:
        return _err('Need at least 3 complete respondents')

    def alpha_of(frame):
        k = frame.shape[1]
        tv = frame.sum(axis=1).var(ddof=1)
        return (k / (k - 1)) * (1 - frame.var(axis=0, ddof=1).sum() / tv) if tv > 0 and k > 1 else None

    a = alpha_of(data)
    if a is None:
        return _err('Total-score variance is zero — alpha is undefined')
    drop = [{'item_removed': c, 'alpha_if_deleted': _f(alpha_of(data.drop(columns=[c])))} for c in items] if len(items) > 2 else []
    return {'type': 'cronbach_alpha', 'n_respondents': int(len(data)), 'n_items': len(items), 'cronbach_alpha': _f(a),
            'reliability': 'Excellent' if a >= .9 else 'Good' if a >= .8 else 'Acceptable' if a >= .7 else
                           'Questionable' if a >= .6 else 'Poor', 'alpha_if_item_deleted': drop}


# ══════════════════════════════════════════════════════════════════════════
# 12. ADVANCED MEDICAL ANALYTICS
# ══════════════════════════════════════════════════════════════════════════
def longitudinal_regression(df, parameters):
    outcome, time_var, sid = parameters.get('outcome'), parameters.get('time_var'), parameters.get('subject_id')
    covs = parameters.get('covariates') or []
    e = _need_cols(df, outcome=outcome, time_var=time_var, subject_id=sid)
    if e:
        return e
    miss = [c for c in covs if c not in df.columns]
    if miss:
        return _err(f'Unknown covariates: {miss}')
    data = df[[outcome, time_var] + covs].apply(pd.to_numeric, errors='coerce')
    data['_sid'] = df[sid]
    data = data.dropna()
    if data['_sid'].nunique() < 5 or len(data) < 15:
        return _err('Need at least 5 subjects and 15 repeated observations')
    groups = pd.factorize(data['_sid'])[0]
    res = sm.OLS(data[outcome], sm.add_constant(data[[time_var] + covs])).fit(cov_type='cluster', cov_kwds={'groups': groups})
    return {'type': 'longitudinal_regression', 'n_obs': int(res.nobs), 'n_subjects': int(len(np.unique(groups))),
            'change_per_unit_time': _f(res.params[time_var]), 'time_p_value': _f(res.pvalues[time_var], 6),
            'standard_errors': 'Cluster-robust (by subject)', 'r_squared': _f(res.rsquared), 'table': _coef_table(res)}


def mixed_effects_model(df, parameters):
    outcome, preds, gcol = parameters.get('outcome'), parameters.get('predictors') or [], parameters.get('group_col')
    e = _need_cols(df, outcome=outcome, group_col=gcol)
    if e or not preds:
        return e or _err('predictors is required')
    miss = [c for c in preds if c not in df.columns]
    if miss:
        return _err(f'Unknown predictors: {miss}')
    data = df[[outcome] + preds].apply(pd.to_numeric, errors='coerce')
    data['_g'] = df[gcol]
    data = data.dropna()
    if data['_g'].nunique() < 3 or len(data) < len(preds) + 10:
        return _err('Need at least 3 groups and enough rows for the number of predictors')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            res = sm.MixedLM(data[outcome], sm.add_constant(data[preds]), groups=data['_g']).fit(reml=True)
    except Exception as ex:
        return _err(f'Mixed model failed to converge: {ex}')
    var_u, var_e = float(res.cov_re.iloc[0, 0]), float(res.scale)
    fe = [{'variable': n, 'coef': _f(res.fe_params[n]), 'std_err': _f(res.bse_fe[n]), 'p_value': _f(res.pvalues[n], 6)}
          for n in res.fe_params.index]
    return {'type': 'mixed_effects_model', 'n_obs': int(res.nobs), 'n_groups': int(data['_g'].nunique()),
            'random_intercept_variance': _f(var_u, 6), 'residual_variance': _f(var_e, 6),
            'icc': _f(var_u / (var_u + var_e)) if (var_u + var_e) > 0 else None, 'table': fe}


def _two_columns(df, parameters):
    tcol, ccol = parameters.get('treatment_col'), parameters.get('control_col')
    e = _need_cols(df, treatment_col=tcol, control_col=ccol)
    if e:
        return None, None, e
    t, c = _numeric_series(df, tcol), _numeric_series(df, ccol)
    if len(t) < 3 or len(c) < 3:
        return None, None, _err('Each group needs at least 3 numeric values')
    return t.values.astype(float), c.values.astype(float), None


def non_inferiority_test(df, parameters):
    t, c, e = _two_columns(df, parameters)
    if e:
        return e
    try:
        margin = _num(parameters, 'margin')
    except KeyError:
        return _err('margin is required')
    if margin <= 0:
        return _err('margin must be a positive number (the largest acceptable shortfall)')
    diff = t.mean() - c.mean()
    se = np.sqrt(t.var(ddof=1) / len(t) + c.var(ddof=1) / len(c))
    z = (diff + margin) / se
    p = float(1 - stats.norm.cdf(z))
    lower = diff - 1.645 * se
    return {'type': 'non_inferiority_test', 'mean_treatment': _f(t.mean()), 'mean_control': _f(c.mean()),
            'mean_difference': _f(diff), 'margin': margin, 'lower_bound_one_sided_95': _f(lower),
            'z_statistic': _f(z), 'p_value': _f(p, 6), 'non_inferior': bool(p < 0.05),
            'conclusion': 'Treatment is non-inferior to control' if p < 0.05 else 'Non-inferiority NOT demonstrated',
            'assumption': 'Higher values = better outcome'}


def equivalence_test_tost(df, parameters):
    t, c, e = _two_columns(df, parameters)
    if e:
        return e
    try:
        lo_m, hi_m = _num(parameters, 'lower_margin'), _num(parameters, 'upper_margin')
    except KeyError as k:
        return _err(f'Missing input: {k}')
    if not lo_m < 0 < hi_m:
        return _err('lower_margin must be negative and upper_margin positive (e.g. -2 and 2)')
    diff = t.mean() - c.mean()
    se = np.sqrt(t.var(ddof=1) / len(t) + c.var(ddof=1) / len(c))
    p_lo = float(1 - stats.norm.cdf((diff - lo_m) / se))
    p_hi = float(stats.norm.cdf((diff - hi_m) / se))
    eq = p_lo < 0.05 and p_hi < 0.05
    return {'type': 'equivalence_test_tost', 'mean_difference': _f(diff),
            'ci90_low': _f(diff - 1.645 * se), 'ci90_high': _f(diff + 1.645 * se),
            'p_lower_test': _f(p_lo, 6), 'p_upper_test': _f(p_hi, 6), 'equivalent': bool(eq),
            'conclusion': 'Groups are equivalent within the stated margins' if eq else 'Equivalence NOT demonstrated'}


# ══════════════════════════════════════════════════════════════════════════
# CATALOG
# ══════════════════════════════════════════════════════════════════════════
def _in(name, type_, label, required=True):
    d = {'name': name, 'type': type_, 'label': label}
    if not required:
        d['required'] = False
    return d


def _item(key, analysis_id, label, number, inputs):
    return {'key': key, 'analysis_id': analysis_id, 'label': label, 'number': number,
            'premium': analysis_id in PREMIUM_ANALYSES, 'needs_dataframe': analysis_id in DATA_DRIVEN_ANALYSES,
            'inputs': inputs}


def _2x2(a, b, c, d):
    return [_in('a', 'number', a), _in('b', 'number', b), _in('c', 'number', c), _in('d', 'number', d)]


_2X2_EXPO = _2x2('a — Exposed WITH disease', 'b — Exposed WITHOUT disease',
                 'c — Unexposed WITH disease', 'd — Unexposed WITHOUT disease')

_HEALTH_MODULES = {
    'Biostatistics': {
        'label': 'Biostatistics',
        'description': 'Descriptive health statistics, prevalence, incidence rate, risk difference',
        'items': [
            _item('bs_1', 'health_descriptive_stats', 'Descriptive Health Statistics', '1.1',
                  [_in('columns', 'column_list', 'Numeric Columns (comma-separated)')]),
            _item('bs_2', 'prevalence', 'Prevalence (with 95% CI)', '1.2',
                  [_in('existing_cases', 'number', 'Existing Cases'), _in('total_population', 'number', 'Total Population')]),
            _item('bs_3', 'incidence_rate', 'Incidence Rate', '1.3',
                  [_in('new_cases', 'number', 'New Cases'), _in('population_at_risk', 'number', 'Population at Risk'),
                   _in('multiplier', 'number', 'Per how many people (default 100000)', False)]),
            _item('bs_4', 'risk_difference', 'Risk Difference', '1.4', _2X2_EXPO),
        ]},
    'Epidemiology': {
        'label': 'Epidemiology',
        'description': 'Relative risk, odds ratio, SIR epidemic model, reproduction number, disease-risk logistic model',
        'items': [
            _item('ep_1', 'relative_risk', 'Relative Risk', '2.1', _2X2_EXPO),
            _item('ep_2', 'odds_ratio', 'Odds Ratio', '2.2', _2X2_EXPO),
            _item('ep_3', 'sir_model', 'SIR Epidemic Model', '2.3',
                  [_in('s0', 'number', 'Initial Susceptible (S0)'), _in('i0', 'number', 'Initial Infected (I0)'),
                   _in('recovered0', 'number', 'Initial Recovered (default 0)', False),
                   _in('beta', 'number', 'Transmission Rate β (per day)'), _in('gamma', 'number', 'Recovery Rate γ (per day)'),
                   _in('days', 'number', 'Days to Simulate (default 160)', False)]),
            _item('ep_4', 'reproduction_number', 'Reproduction Number (R0)', '2.4',
                  [_in('beta', 'number', 'Transmission Rate β'), _in('gamma', 'number', 'Recovery Rate γ')]),
            _item('ep_5', 'disease_risk_logit', 'Disease Risk Logistic Regression', '2.5',
                  [_in('disease_col', 'column_any', 'Disease / Outcome Column (binary)'),
                   _in('risk_factors', 'column_list', 'Risk Factor Columns (comma-separated, numeric)')]),
        ]},
    'Diagnostic': {
        'label': 'Diagnostic Testing',
        'description': 'Sensitivity, specificity, PPV, NPV, likelihood ratios, ROC-AUC',
        'items': [
            _item('dx_1', 'diagnostic_metrics', 'Diagnostic Metrics (Sens / Spec / PPV / NPV)', '3.1',
                  [_in('tp', 'number', 'True Positives (TP)'), _in('fp', 'number', 'False Positives (FP)'),
                   _in('tn', 'number', 'True Negatives (TN)'), _in('fn', 'number', 'False Negatives (FN)')]),
            _item('dx_2', 'roc_auc_analysis', 'ROC-AUC Analysis', '3.2',
                  [_in('true_col', 'column_any', 'True Disease Status Column (binary)'),
                   _in('score_col', 'column_numeric', 'Test Score / Predicted Probability Column')]),
        ]},
    'ClinicalTrials': {
        'label': 'Clinical Trials',
        'description': 'Treatment effect, two-proportion test, sample size, number needed to treat',
        'items': [
            _item('ct_1', 'treatment_effect', 'Treatment Effect (with CI & Cohen\'s d)', '4.1',
                  [_in('outcome_col', 'column_numeric', 'Outcome Column'),
                   _in('treatment_col', 'column_any', 'Treatment Group Column (2 groups)')]),
            _item('ct_2', 'two_proportion_ztest', 'Two-Proportion Z-Test', '4.2',
                  [_in('success1', 'number', 'Successes — Group 1'), _in('n1', 'number', 'Total — Group 1'),
                   _in('success2', 'number', 'Successes — Group 2'), _in('n2', 'number', 'Total — Group 2')]),
            _item('ct_3', 'sample_size_mean', 'Sample Size — Mean', '4.3',
                  [_in('std_dev', 'number', 'Expected Standard Deviation'), _in('margin_error', 'number', 'Margin of Error'),
                   _in('confidence', 'number', 'Confidence (default 0.95)', False)]),
            _item('ct_4', 'sample_size_proportion', 'Sample Size — Proportion', '4.4',
                  [_in('expected_proportion', 'number', 'Expected Proportion (0–1, use 0.5 if unknown)'),
                   _in('margin_error', 'number', 'Margin of Error (e.g. 0.05)'),
                   _in('confidence', 'number', 'Confidence (default 0.95)', False)]),
            _item('ct_5', 'number_needed_to_treat', 'Number Needed to Treat (NNT)', '4.5',
                  [_in('control_event_rate', 'number', 'Control Event Rate (fraction, e.g. 0.20)'),
                   _in('treatment_event_rate', 'number', 'Treatment Event Rate (fraction, e.g. 0.12)')]),
        ]},
    'Survival': {
        'label': 'Survival Analysis',
        'description': 'Kaplan-Meier curves, Cox proportional hazards, log-rank test',
        'items': [
            _item('sv_1', 'kaplan_meier_survival', 'Kaplan-Meier Survival Curve', '5.1',
                  [_in('duration_col', 'column_numeric', 'Follow-up Time Column'),
                   _in('event_col', 'column_any', 'Event Column (1 = event, 0 = censored)'),
                   _in('group_col', 'column_any', 'Compare Groups By (optional)', False)]),
            _item('sv_2', 'cox_proportional_hazards', 'Cox Proportional Hazards', '5.2',
                  [_in('duration_col', 'column_numeric', 'Follow-up Time Column'),
                   _in('event_col', 'column_any', 'Event Column (1 = event, 0 = censored)'),
                   _in('covariates', 'column_list', 'Covariate Columns (comma-separated, numeric)')]),
            _item('sv_3', 'logrank_survival_test', 'Log-Rank Test', '5.3',
                  [_in('duration_col', 'column_numeric', 'Follow-up Time Column'),
                   _in('event_col', 'column_any', 'Event Column (1 = event, 0 = censored)'),
                   _in('group_col', 'column_any', 'Group Column (exactly 2 groups)')]),
        ]},
    'CountModels': {
        'label': 'Medical Count Models',
        'description': 'Poisson and negative-binomial regression for visits, admissions, adverse events',
        'items': [
            _item('cm_1', 'poisson_regression', 'Poisson Regression', '6.1',
                  [_in('count_col', 'column_numeric', 'Count Column'),
                   _in('predictors', 'column_list', 'Predictor Columns (comma-separated, numeric)')]),
            _item('cm_2', 'negative_binomial_regression', 'Negative Binomial Regression', '6.2',
                  [_in('count_col', 'column_numeric', 'Count Column'),
                   _in('predictors', 'column_list', 'Predictor Columns (comma-separated, numeric)')]),
        ]},
    'Pharma': {
        'label': 'Pharmaceutical Analytics',
        'description': 'Dose-response (4PL), bioequivalence, pharmacovigilance ROR/PRR, PK and PD modelling',
        'items': [
            _item('ph_1', 'dose_response_analysis', 'Dose-Response (4-Parameter Logistic)', '7.1',
                  [_in('dose_col', 'column_numeric', 'Dose Column'), _in('response_col', 'column_numeric', 'Response Column')]),
            _item('ph_2', 'bioequivalence_analysis', 'Bioequivalence (90% CI, 80–125%)', '7.2',
                  [_in('test_col', 'column_numeric', 'Test Product Column (e.g. AUC)'),
                   _in('reference_col', 'column_numeric', 'Reference Product Column (paired)')]),
            _item('ph_3', 'pharmacovigilance_signal', 'Pharmacovigilance Signal (ROR & PRR)', '7.3',
                  _2x2('a — Drug of interest WITH the event', 'b — Drug of interest WITHOUT the event',
                       'c — All other drugs WITH the event', 'd — All other drugs WITHOUT the event')),
            _item('ph_4', 'pk_analysis', 'PK Analysis (AUC, Cmax, Tmax, half-life)', '7.4',
                  [_in('time_col', 'column_numeric', 'Time Column'), _in('concentration_col', 'column_numeric', 'Concentration Column')]),
            _item('ph_5', 'pd_analysis', 'PD Analysis (Emax Model)', '7.5',
                  [_in('concentration_col', 'column_numeric', 'Concentration Column'), _in('effect_col', 'column_numeric', 'Effect Column')]),
        ]},
    'MetaAnalysis': {
        'label': 'Meta-Analysis',
        'description': 'Fixed-effect pooling, heterogeneity (Q, I², τ²)',
        'items': [
            _item('ma_1', 'fixed_effect_meta_analysis', 'Fixed-Effect Meta-Analysis', '8.1',
                  [_in('effect_sizes', 'number_array', 'Study Effect Sizes (e.g. 0.30, 0.45, 0.12)'),
                   _in('standard_errors', 'number_array', 'Standard Errors (same order)')]),
            _item('ma_2', 'meta_analysis_heterogeneity', 'Heterogeneity (Q & I²)', '8.2',
                  [_in('effect_sizes', 'number_array', 'Study Effect Sizes (e.g. 0.30, 0.45, 0.12)'),
                   _in('standard_errors', 'number_array', 'Standard Errors (same order)')]),
        ]},
    'HealthEconomics': {
        'label': 'Health Economics',
        'description': 'ICER, QALY, DALY, budget impact, Markov cohort model',
        'items': [
            _item('he_1', 'incremental_cost_effectiveness_ratio', 'ICER', '9.1',
                  [_in('cost_a', 'number', 'Cost — Strategy A'), _in('cost_b', 'number', 'Cost — Strategy B (comparator)'),
                   _in('effect_a', 'number', 'Effect (QALYs) — Strategy A'), _in('effect_b', 'number', 'Effect (QALYs) — Strategy B')]),
            _item('he_2', 'qaly', 'QALY', '9.2',
                  [_in('life_years', 'number', 'Life Years'), _in('utility_weight', 'number', 'Utility Weight (0–1)')]),
            _item('he_3', 'daly', 'DALY', '9.3',
                  [_in('years_life_lost', 'number', 'Years of Life Lost (YLL)'),
                   _in('years_lived_with_disability', 'number', 'Years Lived with Disability (YLD)')]),
            _item('he_4', 'budget_impact', 'Budget Impact', '9.4',
                  [_in('eligible_population', 'number', 'Eligible Population'), _in('uptake_rate', 'number', 'Uptake Rate (fraction, e.g. 0.3)'),
                   _in('cost_per_patient', 'number', 'Cost per Patient (new intervention)'),
                   _in('comparator_cost', 'number', 'Cost per Patient (comparator, default 0)', False)]),
            _item('he_5', 'markov_model', 'Markov Cohort Model', '9.5',
                  [_in('initial_state', 'number_array', 'Initial State Distribution (e.g. 1, 0, 0)'),
                   _in('transition_matrix', 'number_matrix', 'Transition Matrix (one row per line, rows sum to 1)'),
                   _in('cycles', 'number', 'Number of Cycles (default 20)', False)]),
        ]},
    'LifeSciences': {
        'label': 'Life Sciences & Genetics',
        'description': 'Fold change, differential expression, RNA-seq TPM, pathway enrichment, Hardy-Weinberg, GWAS, polygenic risk',
        'items': [
            _item('ls_1', 'gene_expression_fold_change', 'Gene Expression Fold Change', '10.1',
                  [_in('treatment_col', 'column_numeric', 'Treatment Expression Column'),
                   _in('control_col', 'column_numeric', 'Control Expression Column'),
                   _in('gene_col', 'column_any', 'Gene Name Column (optional)', False)]),
            _item('ls_2', 'differential_expression_ttest', 'Differential Expression t-Test', '10.2',
                  [_in('treatment_col', 'column_numeric', 'Treatment Samples Column'),
                   _in('control_col', 'column_numeric', 'Control Samples Column')]),
            _item('ls_3', 'rna_seq_tpm', 'RNA-Seq TPM Normalisation', '10.3',
                  [_in('counts_col', 'column_numeric', 'Read Counts Column'), _in('length_col', 'column_numeric', 'Gene Length (bp) Column'),
                   _in('gene_col', 'column_any', 'Gene Name Column (optional)', False)]),
            _item('ls_4', 'pathway_enrichment', 'Pathway Enrichment (Hypergeometric)', '10.4',
                  [_in('total_genes', 'number', 'Total Genes in Background (N)'), _in('pathway_genes', 'number', 'Genes in Pathway (K)'),
                   _in('selected_genes', 'number', 'Selected / Significant Genes (n)'), _in('overlap_genes', 'number', 'Overlap (k)')]),
            _item('ls_5', 'hardy_weinberg_equilibrium', 'Hardy-Weinberg Equilibrium', '10.5',
                  [_in('obs_AA', 'number', 'Observed AA'), _in('obs_Aa', 'number', 'Observed Aa'), _in('obs_aa', 'number', 'Observed aa')]),
            _item('ls_6', 'gwas_single_snp', 'GWAS — Single SNP Association', '10.6',
                  [_in('disease_col', 'column_any', 'Case / Control Column (binary)'),
                   _in('snp_col', 'column_numeric', 'SNP Genotype Column (0/1/2)'),
                   _in('covariates', 'column_list', 'Covariate Columns (optional, comma-separated)', False)]),
            _item('ls_7', 'polygenic_risk_score', 'Polygenic Risk Score', '10.7',
                  [_in('snp_cols', 'column_list', 'SNP Genotype Columns (comma-separated)'),
                   _in('effect_sizes', 'number_array', 'Effect Sizes β (same order/count)')]),
        ]},
    'Hospital': {
        'label': 'Hospital, Nursing & Outcomes',
        'description': 'Bed occupancy, length of stay, nursing workload, care-quality indicators, outcome models, satisfaction',
        'items': [
            _item('ho_1', 'bed_occupancy_rate', 'Bed Occupancy Rate', '11.1',
                  [_in('inpatient_days', 'number', 'Inpatient Days'), _in('available_bed_days', 'number', 'Available Bed Days')]),
            _item('ho_2', 'average_length_of_stay', 'Average Length of Stay (ALOS)', '11.2',
                  [_in('total_inpatient_days', 'number', 'Total Inpatient Days'), _in('discharges', 'number', 'Number of Discharges')]),
            _item('ho_3', 'nursing_workload', 'Nursing Workload', '11.3',
                  [_in('patient_counts', 'number_array', 'Patients per Acuity Level (e.g. 10, 6, 3)'),
                   _in('acuity_weights', 'number_array', 'Acuity Weights (same order, e.g. 1, 2, 4)'),
                   _in('number_of_nurses', 'number', 'Number of Nurses (optional)', False)]),
            _item('ho_4', 'nurse_patient_ratio', 'Nurse-Patient Ratio', '11.4',
                  [_in('number_of_patients', 'number', 'Number of Patients'), _in('number_of_nurses', 'number', 'Number of Nurses')]),
            _item('ho_5', 'care_quality_indicators', 'Care Quality Indicators', '11.5',
                  [_in('readmissions', 'number', 'Readmissions', False), _in('discharges', 'number', 'Discharges', False),
                   _in('number_of_falls', 'number', 'Patient Falls', False), _in('pressure_ulcers', 'number', 'Pressure Ulcers', False),
                   _in('patient_days', 'number', 'Patient Days', False)]),
            _item('ho_6', 'health_outcome_regression', 'Risk-Adjusted Outcome (Linear)', '11.6',
                  [_in('outcome', 'column_numeric', 'Outcome Column (continuous)'), _in('treatment', 'column_any', 'Treatment / Exposure Column'),
                   _in('risk_factors', 'column_list', 'Risk-Adjustment Columns (optional, comma-separated)', False)]),
            _item('ho_7', 'binary_health_outcome_model', 'Risk-Adjusted Outcome (Binary / Logistic)', '11.7',
                  [_in('outcome', 'column_any', 'Outcome Column (binary)'), _in('treatment', 'column_any', 'Treatment / Exposure Column'),
                   _in('risk_factors', 'column_list', 'Risk-Adjustment Columns (optional, comma-separated)', False)]),
            _item('ho_8', 'satisfaction_summary', 'Satisfaction Summary (Likert)', '11.8',
                  [_in('satisfaction_cols', 'column_list', 'Satisfaction Item Columns (comma-separated)')]),
            _item('ho_9', 'cronbach_alpha', "Cronbach's Alpha (Scale Reliability)", '11.9',
                  [_in('items', 'column_list', 'Scale Item Columns (comma-separated, 2+)')]),
        ]},
    'Advanced': {
        'label': 'Advanced Medical Analytics',
        'description': 'Longitudinal regression, mixed-effects models, non-inferiority and equivalence (TOST) testing',
        'items': [
            _item('ad_1', 'longitudinal_regression', 'Longitudinal Regression (cluster-robust)', '12.1',
                  [_in('outcome', 'column_numeric', 'Outcome Column'), _in('time_var', 'column_numeric', 'Time / Visit Column'),
                   _in('subject_id', 'column_any', 'Subject ID Column'),
                   _in('covariates', 'column_list', 'Covariate Columns (optional, comma-separated)', False)]),
            _item('ad_2', 'mixed_effects_model', 'Mixed-Effects Model (random intercept)', '12.2',
                  [_in('outcome', 'column_numeric', 'Outcome Column'),
                   _in('predictors', 'column_list', 'Fixed-Effect Predictor Columns (comma-separated)'),
                   _in('group_col', 'column_any', 'Grouping Column (e.g. patient / site)')]),
            _item('ad_3', 'non_inferiority_test', 'Non-Inferiority Test', '12.3',
                  [_in('treatment_col', 'column_numeric', 'New Treatment Outcomes Column'),
                   _in('control_col', 'column_numeric', 'Control Outcomes Column'),
                   _in('margin', 'number', 'Non-Inferiority Margin Δ (positive number)')]),
            _item('ad_4', 'equivalence_test_tost', 'Equivalence Test (TOST)', '12.4',
                  [_in('treatment_col', 'column_numeric', 'Treatment Outcomes Column'),
                   _in('control_col', 'column_numeric', 'Control Outcomes Column'),
                   _in('lower_margin', 'number', 'Lower Margin (negative, e.g. -2)'),
                   _in('upper_margin', 'number', 'Upper Margin (positive, e.g. 2)')]),
        ]},
}

HEALTH_MODULES = _HEALTH_MODULES

_ANALYSIS_ROUTER = {
    'health_descriptive_stats': health_descriptive_stats, 'prevalence': prevalence, 'incidence_rate': incidence_rate,
    'risk_difference': risk_difference, 'relative_risk': relative_risk, 'odds_ratio': odds_ratio, 'sir_model': sir_model,
    'reproduction_number': reproduction_number, 'disease_risk_logit': disease_risk_logit,
    'diagnostic_metrics': diagnostic_metrics, 'roc_auc_analysis': roc_auc_analysis,
    'treatment_effect': treatment_effect, 'two_proportion_ztest': two_proportion_ztest,
    'sample_size_mean': sample_size_mean, 'sample_size_proportion': sample_size_proportion,
    'number_needed_to_treat': number_needed_to_treat,
    'kaplan_meier_survival': kaplan_meier_survival, 'cox_proportional_hazards': cox_proportional_hazards,
    'logrank_survival_test': logrank_survival_test,
    'poisson_regression': poisson_regression, 'negative_binomial_regression': negative_binomial_regression,
    'dose_response_analysis': dose_response_analysis, 'bioequivalence_analysis': bioequivalence_analysis,
    'pharmacovigilance_signal': pharmacovigilance_signal, 'pk_analysis': pk_analysis, 'pd_analysis': pd_analysis,
    'fixed_effect_meta_analysis': fixed_effect_meta_analysis, 'meta_analysis_heterogeneity': meta_analysis_heterogeneity,
    'incremental_cost_effectiveness_ratio': incremental_cost_effectiveness_ratio, 'qaly': qaly, 'daly': daly,
    'budget_impact': budget_impact, 'markov_model': markov_model,
    'gene_expression_fold_change': gene_expression_fold_change, 'differential_expression_ttest': differential_expression_ttest,
    'rna_seq_tpm': rna_seq_tpm, 'pathway_enrichment': pathway_enrichment,
    'hardy_weinberg_equilibrium': hardy_weinberg_equilibrium, 'gwas_single_snp': gwas_single_snp,
    'polygenic_risk_score': polygenic_risk_score,
    'bed_occupancy_rate': bed_occupancy_rate, 'average_length_of_stay': average_length_of_stay,
    'nursing_workload': nursing_workload, 'nurse_patient_ratio': nurse_patient_ratio,
    'care_quality_indicators': care_quality_indicators, 'health_outcome_regression': health_outcome_regression,
    'binary_health_outcome_model': binary_health_outcome_model, 'satisfaction_summary': satisfaction_summary,
    'cronbach_alpha': cronbach_alpha,
    'longitudinal_regression': longitudinal_regression, 'mixed_effects_model': mixed_effects_model,
    'non_inferiority_test': non_inferiority_test, 'equivalence_test_tost': equivalence_test_tost,
}


def get_health_catalog() -> dict:
    return {'modules': [{'module_key': k, 'label': m['label'], 'description': m['description'], 'items': m['items']}
                        for k, m in _HEALTH_MODULES.items()]}


def run_health_analysis(analysis_id: str, df, parameters: dict) -> dict:
    fn = _ANALYSIS_ROUTER.get(analysis_id)
    if not fn:
        return _err(f"'{analysis_id}' is not a recognised health analysis")
    try:
        return fn(df, parameters or {})
    except Exception as e:
        return _err(f'Unexpected error running {analysis_id}: {e}')


# ══════════════════════════════════════════════════════════════════════════
# SMART SUGGESTIONS
# ══════════════════════════════════════════════════════════════════════════
def _tokens(name: str):
    import re
    return [t for t in re.split(r'[^a-z0-9]+', name.lower()) if t]


def _is_id_col(c: dict) -> bool:
    return 'id' in _tokens(c.get('name', ''))


def suggest_health_analyses(columns_meta: list) -> dict:
    if not columns_meta:
        return {'recommended': [], 'numeric_columns': [], 'categorical_columns': [], 'date_columns': []}

    numeric = [c for c in columns_meta if c.get('python_type') in ('integer', 'float') and not _is_id_col(c)]
    categorical = [c for c in columns_meta if c.get('python_type') == 'string' and not _is_id_col(c)]
    dates = [c for c in columns_meta if c.get('python_type') in ('datetime', 'date_string')]
    everything = [c for c in columns_meta]

    def has(name, kws):
        n = name.lower()
        return any(k in n for k in kws)

    def find(kws, pool):
        for c in pool:
            if has(c['name'], kws):
                return c['name']
        return None

    def is_binary(c):
        return c.get('stat_type') == 'Binary' or c.get('unique_values') == 2

    binary_cols = [c for c in everything if is_binary(c) and not _is_id_col(c)]
    rec = []

    def add(module, aid, key, label, reason, prefill):
        rec.append({'module_key': module, 'analysis_id': aid, 'item_key': key, 'label': label,
                    'reason': reason, 'prefill': prefill})

    # ── survival ────────────────────────────────────────────────────────
    dur = find(['survival', 'duration', 'followup', 'follow_up', 'time_to', 'days', 'months', 'tenure', 'os_time'], numeric)
    evt = next((c['name'] for c in binary_cols if has(c['name'], ['event', 'status', 'death', 'died', 'dead', 'censor', 'relapse', 'progress', 'outcome'])), None)
    if dur and evt and dur != evt:
        add('Survival', 'kaplan_meier_survival', 'sv_1', 'Kaplan-Meier Survival Curve',
            f"'{dur}' (time) with '{evt}' (event flag) is a classic time-to-event layout.", {'duration_col': dur, 'event_col': evt})
        grp = next((c['name'] for c in binary_cols if c['name'] not in (evt,) and has(c['name'], ['arm', 'group', 'treat', 'sex', 'gender', 'stage', 'drug'])), None)
        if grp:
            add('Survival', 'logrank_survival_test', 'sv_3', 'Log-Rank Test',
                f"Compare survival between the two '{grp}' groups.", {'duration_col': dur, 'event_col': evt, 'group_col': grp})
        covs = [c['name'] for c in numeric if c['name'] not in (dur, evt)][:3]
        if covs:
            add('Survival', 'cox_proportional_hazards', 'sv_2', 'Cox Proportional Hazards',
                f"Estimate hazard ratios for {', '.join(covs)} using '{dur}' / '{evt}'.",
                {'duration_col': dur, 'event_col': evt, 'covariates': covs})

    # ── diagnostic ROC ──────────────────────────────────────────────────
    truth = next((c['name'] for c in binary_cols if has(c['name'], ['disease', 'diagnosis', 'diagnos', 'case', 'label', 'actual', 'truth', 'positive', 'condition'])), None)
    score = find(['score', 'prob', 'risk', 'predict', 'biomarker', 'marker', 'level'], numeric)
    if truth and score and truth != score:
        add('Diagnostic', 'roc_auc_analysis', 'dx_2', 'ROC-AUC Analysis',
            f"'{truth}' (true status) vs '{score}' (test score) — measure discrimination.", {'true_col': truth, 'score_col': score})

    # ── treatment effect / outcome models ───────────────────────────────
    trt = next((c['name'] for c in binary_cols if has(c['name'], ['treat', 'arm', 'drug', 'trial', 'intervention', 'placebo', 'group'])), None)
    outcome = find(['outcome', 'response', 'change', 'score', 'bp', 'pressure', 'glucose', 'hba1c', 'cholesterol', 'reduction', 'recovery'], numeric)
    if trt and outcome:
        add('ClinicalTrials', 'treatment_effect', 'ct_1', 'Treatment Effect',
            f"'{trt}' splits patients into two arms — compare '{outcome}' between them.", {'outcome_col': outcome, 'treatment_col': trt})

    # ── disease risk logit ──────────────────────────────────────────────
    disease = next((c['name'] for c in binary_cols if has(c['name'], ['disease', 'diagnosis', 'diabet', 'cancer', 'hypertens', 'infect', 'positive', 'case', 'mortality', 'readmit'])), None)
    factors = [c['name'] for c in numeric if disease and c['name'] != disease][:4]
    if disease and len(factors) >= 1:
        add('Epidemiology', 'disease_risk_logit', 'ep_5', 'Disease Risk Logistic Regression',
            f"'{disease}' is binary — model its odds against {', '.join(factors)}.", {'disease_col': disease, 'risk_factors': factors})

    # ── count models ────────────────────────────────────────────────────
    count = next((c['name'] for c in numeric if c.get('python_type') == 'integer'
                  and has(c['name'], ['count', 'visits', 'admission', 'events', 'episodes', 'cases', 'infections', 'adverse', 'falls'])
                  and not has(c['name'], ['read', 'umi', 'reads'])), None)
    cpred = [c['name'] for c in numeric if c['name'] != count][:3]
    if count and cpred:
        add('CountModels', 'poisson_regression', 'cm_1', 'Poisson Regression',
            f"'{count}' looks like an event count — model its rate against {', '.join(cpred)}.", {'count_col': count, 'predictors': cpred})

    # ── pharma ──────────────────────────────────────────────────────────
    dose, resp = find(['dose', 'concentration_ug', 'drug_conc'], numeric), find(['response', 'effect', 'inhibition', 'viability', 'activity'], numeric)
    if dose and resp and dose != resp:
        add('Pharma', 'dose_response_analysis', 'ph_1', 'Dose-Response (4PL)',
            f"'{dose}' vs '{resp}' — fit a dose-response curve and estimate EC50.", {'dose_col': dose, 'response_col': resp})
    tcol, ccol = find(['time', 'hour', 'hr'], numeric), find(['conc', 'plasma', 'cp'], numeric)
    if tcol and ccol and tcol != ccol:
        add('Pharma', 'pk_analysis', 'ph_4', 'PK Analysis',
            f"'{tcol}' with '{ccol}' is a concentration-time profile — get AUC, Cmax, Tmax and half-life.", {'time_col': tcol, 'concentration_col': ccol})
    test_c, ref_c = find(['test'], numeric), find(['reference', 'ref'], numeric)
    if test_c and ref_c and test_c != ref_c:
        add('Pharma', 'bioequivalence_analysis', 'ph_2', 'Bioequivalence',
            f"'{test_c}' vs '{ref_c}' look like paired test/reference exposures.", {'test_col': test_c, 'reference_col': ref_c})

    # ── life sciences ───────────────────────────────────────────────────
    tr_expr, ct_expr = find(['treat', 'case', 'tumor', 'tumour', 'disease'], numeric), find(['control', 'normal', 'healthy', 'baseline'], numeric)
    if tr_expr and ct_expr and tr_expr != ct_expr:
        gene = find(['gene', 'symbol', 'transcript'], categorical)
        pre = {'treatment_col': tr_expr, 'control_col': ct_expr}
        if gene:
            pre['gene_col'] = gene
        add('LifeSciences', 'gene_expression_fold_change', 'ls_1', 'Gene Expression Fold Change',
            f"'{tr_expr}' vs '{ct_expr}' expression — compute fold change and log2FC per row.", pre)
    cnt, ln = find(['count', 'reads'], numeric), find(['length', 'len', 'bp'], numeric)
    if cnt and ln and cnt != ln:
        add('LifeSciences', 'rna_seq_tpm', 'ls_3', 'RNA-Seq TPM Normalisation',
            f"'{cnt}' and '{ln}' are what TPM normalisation needs.", {'counts_col': cnt, 'length_col': ln})
    snp = find(['snp', 'rs', 'genotype', 'allele'], numeric)
    if snp and truth:
        add('LifeSciences', 'gwas_single_snp', 'ls_6', 'GWAS — Single SNP Association',
            f"'{snp}' genotype against case/control status '{truth}'.", {'disease_col': truth, 'snp_col': snp})

    # ── hospital / satisfaction ─────────────────────────────────────────
    likert = [c['name'] for c in numeric if has(c['name'], ['satisf', 'q1', 'q2', 'q3', 'q4', 'q5', 'item', 'likert', 'rating'])]
    if len(likert) >= 2:
        add('Hospital', 'cronbach_alpha', 'ho_9', "Cronbach's Alpha",
            f"{len(likert)} rating/satisfaction items found — check internal consistency of the scale.", {'items': likert[:8]})
        add('Hospital', 'satisfaction_summary', 'ho_8', 'Satisfaction Summary',
            'Summarise the satisfaction/rating items.', {'satisfaction_cols': likert[:8]})

    # ── longitudinal ────────────────────────────────────────────────────
    sid = next((c['name'] for c in everything if has(c['name'], ['patient', 'subject', 'participant']) and ('id' in _tokens(c['name']) or c.get('python_type') == 'string')), None)
    tvar = find(['visit', 'week', 'month', 'time', 'day'], numeric)
    yvar = find(['score', 'level', 'outcome', 'measure', 'bp', 'weight'], numeric)
    if sid and tvar and yvar and len({tvar, yvar}) == 2:
        add('Advanced', 'longitudinal_regression', 'ad_1', 'Longitudinal Regression',
            f"'{sid}' repeats across '{tvar}' — model change in '{yvar}' with cluster-robust errors.",
            {'outcome': yvar, 'time_var': tvar, 'subject_id': sid})

    # ── generic fallback so clinical files always get something ─────────
    health_numeric = [c['name'] for c in numeric if has(c['name'], ['age', 'bmi', 'bp', 'weight', 'height', 'glucose', 'cholesterol', 'heart', 'pulse', 'hemoglobin', 'creatinine', 'los', 'stay'])]
    if health_numeric:
        add('Biostatistics', 'health_descriptive_stats', 'bs_1', 'Descriptive Health Statistics',
            f"Clinical-looking variables found ({', '.join(health_numeric[:4])}) — start with a descriptive profile.",
            {'columns': health_numeric[:8]})

    return {'recommended': rec, 'numeric_columns': [c['name'] for c in numeric],
            'categorical_columns': [c['name'] for c in categorical], 'date_columns': [c['name'] for c in dates]}
