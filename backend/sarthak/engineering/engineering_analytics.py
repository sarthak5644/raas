"""
Engineering Analytics Service (RaaS Stage-2)
=============================================
Mirrors the structure of services/universal_analytics.py (Stage-1) so the
same route/catalog/run pattern can be reused on the frontend.

Exposes 9 Engineering modules, each with its own sub-analyses:
    1. Reliability Analysis
    2. Quality Control
    3. Design of Experiments (DOE)
    4. Optimization
    5. Error Analysis
    6. Simulation (Monte Carlo)
    7. Queuing Analysis
    8. Network Analysis
    9. Numerical Methods

Two kinds of analyses:
  - "data-driven": operate on a column (or columns) of the uploaded
    Excel/CSV file (e.g. Quality Control needs a numeric column).
  - "parameter-only": take manual numeric inputs typed by the user in the
    UI (e.g. Reliability needs failure_rate + time; Optimization needs
    objective coefficients + constraints). These still accept an optional
    dataframe but primarily read from `parameters`.

Every function returns a JSON-serialisable dict with at least a 'type' key.
On failure it returns {'error': '...'} (checked by the route the same way
Stage-1 does).
"""
import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import linprog, minimize
import networkx as nx


# ══════════════════════════════════════════════════════════════════════════
#  PREMIUM GATING (same idea as Stage-1's PREMIUM_ANALYSES)
# ══════════════════════════════════════════════════════════════════════════
PREMIUM_ANALYSES = {
    'weibull_reliability',
    'process_capability',
    'two_way_anova',
    'nonlinear_optimization',
    'monte_carlo_simulation',
    'shortest_path_analysis',
    'solve_ode',
}


def _err(msg: str) -> dict:
    return {'error': msg}


def _numeric_series(df: pd.DataFrame, column: str) -> pd.Series:
    if df is None or column not in df.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(df[column], errors='coerce').dropna()


# ══════════════════════════════════════════════════════════════════════════
# 1. RELIABILITY ANALYSIS
# ══════════════════════════════════════════════════════════════════════════
def reliability_summary(df: pd.DataFrame, parameters: dict) -> dict:
    """
    parameters:
      total_operating_time (float), number_of_failures (float),
      total_repair_time (float, optional), number_of_repairs (float, optional),
      time_horizon (float, optional) - time at which to evaluate R(t)
    """
    try:
        top = float(parameters.get('total_operating_time', 0))
        failures = float(parameters.get('number_of_failures', 0))
        if failures <= 0 or top <= 0:
            return _err('total_operating_time and number_of_failures must be > 0')

        mtbf_val = top / failures
        failure_rate = failures / top
        t = float(parameters.get('time_horizon', mtbf_val))
        reliability_t = float(np.exp(-failure_rate * t))

        result = {
            'type': 'reliability_summary',
            'mtbf': round(mtbf_val, 4),
            'failure_rate': round(failure_rate, 6),
            'time_horizon': t,
            'reliability_at_t': round(reliability_t, 4),
            'failure_probability_at_t': round(1 - reliability_t, 4),
        }

        if 'total_repair_time' in parameters and 'number_of_repairs' in parameters:
            trt = float(parameters['total_repair_time'])
            nr = float(parameters['number_of_repairs'])
            if nr > 0:
                mttr_val = trt / nr
                result['mttr'] = round(mttr_val, 4)
                result['availability'] = round(mtbf_val / (mtbf_val + mttr_val), 4)

        # Reliability curve for charting (0 .. 3x MTBF)
        times = np.linspace(0, max(t, mtbf_val) * 2, 30)
        curve = np.exp(-failure_rate * times)
        result['curve'] = [{'t': round(float(tt), 2), 'reliability': round(float(rr), 4)}
                            for tt, rr in zip(times, curve)]
        return result
    except Exception as e:
        return _err(str(e))


def weibull_reliability(df: pd.DataFrame, parameters: dict) -> dict:
    """
    parameters: beta (shape), eta (scale), time_horizon
    """
    try:
        beta = float(parameters.get('beta', 1.5))
        eta = float(parameters.get('eta', 100))
        t = float(parameters.get('time_horizon', eta))

        r_t = float(np.exp(-((t / eta) ** beta)))
        f_t = 1 - r_t

        times = np.linspace(0.01, eta * 2.5, 40)
        r_curve = np.exp(-((times / eta) ** beta))

        return {
            'type': 'weibull_reliability',
            'beta_shape': beta,
            'eta_scale': eta,
            'time_horizon': t,
            'reliability': round(r_t, 4),
            'failure_probability': round(f_t, 4),
            'curve': [{'t': round(float(tt), 2), 'reliability': round(float(rr), 4)}
                      for tt, rr in zip(times, r_curve)],
        }
    except Exception as e:
        return _err(str(e))


# ══════════════════════════════════════════════════════════════════════════
# 2. QUALITY CONTROL
# ══════════════════════════════════════════════════════════════════════════
def quality_control_limits(df: pd.DataFrame, parameters: dict) -> dict:
    """parameters: column (numeric column with process measurements)"""
    column = parameters.get('column')
    series = _numeric_series(df, column)
    if series.empty:
        return _err(f"Column '{column}' has no usable numeric data")

    mean = float(series.mean())
    std = float(series.std())

    return {
        'type': 'quality_control_limits',
        'column': column,
        'n': int(len(series)),
        'mean': round(mean, 4),
        'std': round(std, 4),
        'ucl': round(mean + 3 * std, 4),
        'lcl': round(mean - 3 * std, 4),
        'chart_points': [{'i': i, 'value': round(float(v), 4)} for i, v in enumerate(series.tolist())],
    }


def process_capability(df: pd.DataFrame, parameters: dict) -> dict:
    """parameters: column, usl, lsl"""
    column = parameters.get('column')
    series = _numeric_series(df, column)
    if series.empty:
        return _err(f"Column '{column}' has no usable numeric data")
    try:
        usl = float(parameters['usl'])
        lsl = float(parameters['lsl'])
    except (KeyError, ValueError, TypeError):
        return _err('usl and lsl are required numeric inputs')

    mean = float(series.mean())
    std = float(series.std())
    if std == 0:
        return _err('Standard deviation is zero; cannot compute capability indices')

    cp = (usl - lsl) / (6 * std)
    cpk = min((usl - mean) / (3 * std), (mean - lsl) / (3 * std))

    interpretation = (
        'Process is highly capable' if cpk >= 1.33 else
        'Process is marginally capable' if cpk >= 1.0 else
        'Process is not capable'
    )

    return {
        'type': 'process_capability',
        'column': column,
        'mean': round(mean, 4),
        'std': round(std, 4),
        'usl': usl,
        'lsl': lsl,
        'Cp': round(cp, 4),
        'Cpk': round(cpk, 4),
        'interpretation': interpretation,
    }


# ══════════════════════════════════════════════════════════════════════════
# 3. DESIGN OF EXPERIMENTS (DOE)
# ══════════════════════════════════════════════════════════════════════════
def one_way_anova(df: pd.DataFrame, parameters: dict) -> dict:
    """parameters: response_col, factor_col"""
    response_col = parameters.get('response_col')
    factor_col = parameters.get('factor_col')
    if df is None or response_col not in df.columns or factor_col not in df.columns:
        return _err('response_col and factor_col must be valid columns')

    data = df[[response_col, factor_col]].dropna()
    groups = [g[response_col].values for _, g in data.groupby(factor_col) if len(g) > 0]
    if len(groups) < 2:
        return _err('Need at least 2 groups (levels) in factor_col to run ANOVA')

    try:
        f_stat, p_value = stats.f_oneway(*groups)
    except Exception as e:
        return _err(f'ANOVA failed: {e}')

    group_means = data.groupby(factor_col)[response_col].mean().round(4).to_dict()

    return {
        'type': 'one_way_anova',
        'response_col': response_col,
        'factor_col': factor_col,
        'f_statistic': round(float(f_stat), 4),
        'p_value': round(float(p_value), 6),
        'group_means': group_means,
        'interpretation': 'Factor significantly affects response' if p_value < 0.05
                          else 'No significant effect detected',
    }


def two_way_anova(df: pd.DataFrame, parameters: dict) -> dict:
    """parameters: response_col, factor1, factor2"""
    import statsmodels.api as sm
    import statsmodels.formula.api as smf

    response_col = parameters.get('response_col')
    factor1 = parameters.get('factor1')
    factor2 = parameters.get('factor2')
    needed = [response_col, factor1, factor2]
    if df is None or any(c not in df.columns for c in needed):
        return _err('response_col, factor1 and factor2 must all be valid columns')

    data = df[needed].dropna()
    if len(data) < 4:
        return _err('Not enough rows to run a two-way ANOVA')

    try:
        formula = f"{response_col} ~ C({factor1}) + C({factor2}) + C({factor1}):C({factor2})"
        model = smf.ols(formula, data=data).fit()
        table = sm.stats.anova_lm(model, typ=2)
    except Exception as e:
        return _err(f'Two-way ANOVA failed: {e}')

    rows = []
    for idx, row in table.iterrows():
        rows.append({
            'source': str(idx),
            'sum_sq': round(float(row['sum_sq']), 4) if not pd.isna(row['sum_sq']) else None,
            'df': round(float(row['df']), 2) if not pd.isna(row['df']) else None,
            'F': round(float(row['F']), 4) if 'F' in row and not pd.isna(row['F']) else None,
            'p_value': round(float(row['PR(>F)']), 6) if 'PR(>F)' in row and not pd.isna(row['PR(>F)']) else None,
        })

    return {
        'type': 'two_way_anova',
        'response_col': response_col,
        'factor1': factor1,
        'factor2': factor2,
        'table': rows,
    }


# ══════════════════════════════════════════════════════════════════════════
# 4. OPTIMIZATION
# ══════════════════════════════════════════════════════════════════════════
def linear_optimization(df: pd.DataFrame, parameters: dict) -> dict:
    """
    parameters:
      objective: [c1, c2, ...]              (coefficients to maximize or minimize)
      constraints: [[a1, a2, ...], ...]     (A_ub rows)
      rhs: [b1, b2, ...]                    (b_ub values, same length as constraints)
      bounds: [[low, high], ...] optional (default 0..None per variable)
      goal: 'maximize' | 'minimize'  (default 'maximize')
    """
    try:
        c = [float(x) for x in parameters.get('objective', [])]
        A = [[float(x) for x in row] for row in parameters.get('constraints', [])]
        b = [float(x) for x in parameters.get('rhs', [])]
        goal = parameters.get('goal', 'maximize')
        bounds = parameters.get('bounds')
        if bounds:
            bounds = [(float(lo) if lo is not None else 0, float(hi) if hi is not None else None)
                      for lo, hi in bounds]
        else:
            bounds = [(0, None)] * len(c)

        if not c or not A or not b:
            return _err('objective, constraints and rhs are all required')
        if any(len(row) != len(c) for row in A):
            return _err('Every constraint row must have the same length as objective')
        if len(A) != len(b):
            return _err('constraints and rhs must have the same number of rows')

        c_solve = [-x for x in c] if goal == 'maximize' else c

        result = linprog(c=c_solve, A_ub=A, b_ub=b, bounds=bounds, method='highs')

        if not result.success:
            return _err(f'Optimization failed: {result.message}')

        objective_value = -result.fun if goal == 'maximize' else result.fun

        return {
            'type': 'linear_optimization',
            'goal': goal,
            'success': True,
            'optimal_value': round(float(objective_value), 4),
            'decision_variables': [round(float(x), 4) for x in result.x],
            'message': result.message,
        }
    except Exception as e:
        return _err(str(e))


def nonlinear_optimization(df: pd.DataFrame, parameters: dict) -> dict:
    """
    parameters:
      expression: a string like "x0**2 + x1**2 - 4*x0" evaluated with numpy
                  ('x' is the vector; use x[0], x[1], ...)
      initial_guess: [x0_start, x1_start, ...]
      bounds: [[low, high], ...] optional
    Note: expression is evaluated in a restricted namespace (numpy as np, x)
    -- no builtins are exposed.
    """
    try:
        expr = parameters.get('expression', '')
        x0 = [float(v) for v in parameters.get('initial_guess', [])]
        bounds = parameters.get('bounds')
        if bounds:
            bounds = [(float(lo) if lo is not None else None, float(hi) if hi is not None else None)
                      for lo, hi in bounds]
        if not expr or not x0:
            return _err('expression and initial_guess are required')

        safe_globals = {'__builtins__': {}, 'np': np}

        def objective(x):
            return eval(expr, safe_globals, {'x': x})

        result = minimize(objective, x0, bounds=bounds)

        return {
            'type': 'nonlinear_optimization',
            'success': bool(result.success),
            'optimal_value': round(float(result.fun), 6),
            'decision_variables': [round(float(v), 6) for v in result.x],
            'message': str(result.message),
            'iterations': int(result.nit) if hasattr(result, 'nit') else None,
        }
    except Exception as e:
        return _err(str(e))


# ══════════════════════════════════════════════════════════════════════════
# 5. ERROR ANALYSIS
# ══════════════════════════════════════════════════════════════════════════
def error_analysis(df: pd.DataFrame, parameters: dict) -> dict:
    """parameters: actual_col, predicted_col"""
    actual_col = parameters.get('actual_col')
    predicted_col = parameters.get('predicted_col')
    if df is None or actual_col not in df.columns or predicted_col not in df.columns:
        return _err('actual_col and predicted_col must be valid columns')

    data = df[[actual_col, predicted_col]].dropna()
    if data.empty:
        return _err('No overlapping non-null rows between the two columns')

    actual = data[actual_col].astype(float).values
    predicted = data[predicted_col].astype(float).values

    abs_err = np.abs(actual - predicted)
    with np.errstate(divide='ignore', invalid='ignore'):
        pct_err = np.where(actual != 0, abs_err / np.abs(actual) * 100, np.nan)

    mae = float(np.mean(abs_err))
    rmse = float(np.sqrt(np.mean((actual - predicted) ** 2)))
    mape = float(np.nanmean(pct_err))

    return {
        'type': 'error_analysis',
        'n': int(len(data)),
        'MAE': round(mae, 4),
        'RMSE': round(rmse, 4),
        'MAPE': round(mape, 4) if not np.isnan(mape) else None,
        'sample_errors': [
            {'actual': round(float(a), 4), 'predicted': round(float(p), 4), 'abs_error': round(float(e), 4)}
            for a, p, e in list(zip(actual, predicted, abs_err))[:20]
        ],
    }


# ══════════════════════════════════════════════════════════════════════════
# 6. SIMULATION (Monte Carlo)
# ══════════════════════════════════════════════════════════════════════════
def monte_carlo_simulation(df: pd.DataFrame, parameters: dict) -> dict:
    """
    parameters:
      inputs: [{name, distribution: 'normal'|'uniform', p1, p2}, ...]
        normal -> p1=mean, p2=std ; uniform -> p1=low, p2=high
      expression: string using the variable names, e.g. "speed * hours * eff"
      n_simulations: int (default 5000, capped at 20000)
    """
    try:
        inputs = parameters.get('inputs', [])
        expr = parameters.get('expression', '')
        n = min(int(parameters.get('n_simulations', 5000)), 20000)
        if not inputs or not expr:
            return _err('inputs and expression are required')

        rng = np.random.default_rng(42)
        samples = {}
        for spec in inputs:
            name = spec['name']
            dist = spec.get('distribution', 'normal')
            p1 = float(spec.get('p1', 0))
            p2 = float(spec.get('p2', 1))
            if dist == 'uniform':
                samples[name] = rng.uniform(p1, p2, n)
            else:
                samples[name] = rng.normal(p1, p2, n)

        safe_globals = {'__builtins__': {}, 'np': np}
        results = eval(expr, safe_globals, samples)
        results = np.asarray(results, dtype=float)

        hist, edges = np.histogram(results, bins=20)
        histogram = [{'bin_start': round(float(edges[i]), 4),
                      'bin_end': round(float(edges[i + 1]), 4),
                      'count': int(hist[i])} for i in range(len(hist))]

        return {
            'type': 'monte_carlo_simulation',
            'n_simulations': n,
            'mean': round(float(np.mean(results)), 4),
            'std': round(float(np.std(results)), 4),
            'min': round(float(np.min(results)), 4),
            'max': round(float(np.max(results)), 4),
            'p5': round(float(np.percentile(results, 5)), 4),
            'p95': round(float(np.percentile(results, 95)), 4),
            'histogram': histogram,
        }
    except Exception as e:
        return _err(str(e))


# ══════════════════════════════════════════════════════════════════════════
# 7. QUEUING ANALYSIS (M/M/1)
# ══════════════════════════════════════════════════════════════════════════
def mm1_queue(df: pd.DataFrame, parameters: dict) -> dict:
    """parameters: arrival_rate (lambda), service_rate (mu)"""
    try:
        arrival_rate = float(parameters.get('arrival_rate', 0))
        service_rate = float(parameters.get('service_rate', 0))
        if arrival_rate <= 0 or service_rate <= 0:
            return _err('arrival_rate and service_rate must be > 0')
        if arrival_rate >= service_rate:
            return _err('Unstable queue: arrival_rate must be less than service_rate')

        rho = arrival_rate / service_rate
        L = arrival_rate / (service_rate - arrival_rate)
        W = 1 / (service_rate - arrival_rate)
        Lq = arrival_rate ** 2 / (service_rate * (service_rate - arrival_rate))
        Wq = arrival_rate / (service_rate * (service_rate - arrival_rate))

        return {
            'type': 'mm1_queue',
            'arrival_rate': arrival_rate,
            'service_rate': service_rate,
            'utilization': round(rho, 4),
            'avg_number_in_system_L': round(L, 4),
            'avg_time_in_system_W': round(W, 4),
            'avg_number_in_queue_Lq': round(Lq, 4),
            'avg_waiting_time_Wq': round(Wq, 4),
        }
    except Exception as e:
        return _err(str(e))


# ══════════════════════════════════════════════════════════════════════════
# 8. NETWORK ANALYSIS (Shortest Path)
# ══════════════════════════════════════════════════════════════════════════
def shortest_path_analysis(df: pd.DataFrame, parameters: dict) -> dict:
    """
    parameters:
      edges: [[node_a, node_b, weight], ...]
      source: str
      target: str
    """
    try:
        edges = parameters.get('edges', [])
        source = parameters.get('source')
        target = parameters.get('target')
        if not edges or source is None or target is None:
            return _err('edges, source and target are required')

        G = nx.Graph()
        for edge in edges:
            u, v, w = edge[0], edge[1], float(edge[2])
            G.add_edge(u, v, weight=w)

        if source not in G or target not in G:
            return _err('source or target node not found in the given edges')

        path = nx.shortest_path(G, source=source, target=target, weight='weight')
        distance = nx.shortest_path_length(G, source=source, target=target, weight='weight')

        return {
            'type': 'shortest_path_analysis',
            'source': source,
            'target': target,
            'shortest_path': path,
            'distance': round(float(distance), 4),
            'nodes': list(G.nodes()),
            'edges': [{'from': u, 'to': v, 'weight': d['weight']} for u, v, d in G.edges(data=True)],
        }
    except nx.NetworkXNoPath:
        return _err(f'No path exists between {parameters.get("source")} and {parameters.get("target")}')
    except Exception as e:
        return _err(str(e))


# ══════════════════════════════════════════════════════════════════════════
# 9. NUMERICAL METHODS
# ══════════════════════════════════════════════════════════════════════════
def newton_raphson(df: pd.DataFrame, parameters: dict) -> dict:
    """
    parameters:
      expression: f(x) as string, e.g. "x**3 - 2*x - 5"
      derivative_expression: f'(x) as string, e.g. "3*x**2 - 2"
      initial_guess: float
      tolerance: float (default 1e-6)
      max_iter: int (default 100)
    """
    try:
        expr = parameters.get('expression', '')
        d_expr = parameters.get('derivative_expression', '')
        x0 = float(parameters.get('initial_guess', 1))
        tol = float(parameters.get('tolerance', 1e-6))
        max_iter = int(parameters.get('max_iter', 100))
        if not expr or not d_expr:
            return _err('expression and derivative_expression are required')

        safe_globals = {'__builtins__': {}, 'np': np}

        def f(x):
            return eval(expr, safe_globals, {'x': x})

        def fp(x):
            return eval(d_expr, safe_globals, {'x': x})

        x = x0
        history = [{'iteration': 0, 'x': round(x, 6), 'f_x': round(float(f(x)), 6)}]
        converged = False
        for i in range(1, max_iter + 1):
            fpx = fp(x)
            if fpx == 0:
                return _err('Derivative is zero; Newton-Raphson cannot continue')
            x_new = x - f(x) / fpx
            history.append({'iteration': i, 'x': round(x_new, 6), 'f_x': round(float(f(x_new)), 6)})
            if abs(x_new - x) < tol:
                x = x_new
                converged = True
                break
            x = x_new

        return {
            'type': 'newton_raphson',
            'root': round(x, 6),
            'converged': converged,
            'iterations_used': len(history) - 1,
            'history': history[:50],
        }
    except Exception as e:
        return _err(str(e))


def trapezoidal_integration(df: pd.DataFrame, parameters: dict) -> dict:
    """
    parameters: expression (f(x) as string), a (lower bound), b (upper bound), n (subintervals, default 1000)
    """
    try:
        expr = parameters.get('expression', '')
        a = float(parameters.get('a'))
        b = float(parameters.get('b'))
        n = int(parameters.get('n', 1000))
        if not expr:
            return _err('expression is required')

        safe_globals = {'__builtins__': {}, 'np': np}
        x = np.linspace(a, b, n + 1)
        y = eval(expr, safe_globals, {'x': x})
        integral = float(np.trapz(y, x))

        # Sample a subset of points for a chart
        step = max(1, n // 40)
        curve = [{'x': round(float(x[i]), 4), 'y': round(float(y[i]), 4)} for i in range(0, n + 1, step)]

        return {
            'type': 'trapezoidal_integration',
            'a': a, 'b': b, 'n': n,
            'integral_estimate': round(integral, 6),
            'curve': curve,
        }
    except Exception as e:
        return _err(str(e))


def solve_ode(df: pd.DataFrame, parameters: dict) -> dict:
    """
    parameters:
      expression: dy/dt = f(t, y) as string using 't' and 'y' (y is scalar), e.g. "-0.1*(y-25)"
      y0: float (initial condition)
      t0, t1: float (time span)
      n_points: int (default 100)
    """
    try:
        from scipy.integrate import solve_ivp

        expr = parameters.get('expression', '')
        y0 = float(parameters.get('y0', 0))
        t0 = float(parameters.get('t0', 0))
        t1 = float(parameters.get('t1', 10))
        n_points = int(parameters.get('n_points', 100))
        if not expr:
            return _err('expression is required')

        safe_globals = {'__builtins__': {}, 'np': np}

        def f(t, y):
            return [eval(expr, safe_globals, {'t': t, 'y': y[0]})]

        t_eval = np.linspace(t0, t1, n_points)
        sol = solve_ivp(f, (t0, t1), [y0], t_eval=t_eval)

        if not sol.success:
            return _err(f'ODE solver failed: {sol.message}')

        curve = [{'t': round(float(tt), 4), 'y': round(float(yy), 4)}
                  for tt, yy in zip(sol.t, sol.y[0])]

        return {
            'type': 'solve_ode',
            'y0': y0, 't0': t0, 't1': t1,
            'final_value': round(float(sol.y[0][-1]), 6),
            'curve': curve,
        }
    except Exception as e:
        return _err(str(e))


# ══════════════════════════════════════════════════════════════════════════
# MODULE / CATALOG DEFINITION (drives the frontend UI)
# ══════════════════════════════════════════════════════════════════════════
_ENGINEERING_MODULES = {
    "Reliability": {
        "label": "Reliability Analysis",
        "description": "MTBF, MTTR, availability, exponential & Weibull reliability curves",
        "needs_dataframe": False,
        "items": [
            {"key": "rel_1", "analysis_id": "reliability_summary", "label": "Reliability Summary (MTBF/MTTR/Availability)",
             "number": "1.1", "premium": False,
             "inputs": [
                 {"name": "total_operating_time", "type": "number", "label": "Total Operating Time"},
                 {"name": "number_of_failures", "type": "number", "label": "Number of Failures"},
                 {"name": "total_repair_time", "type": "number", "label": "Total Repair Time (optional)", "required": False},
                 {"name": "number_of_repairs", "type": "number", "label": "Number of Repairs (optional)", "required": False},
                 {"name": "time_horizon", "type": "number", "label": "Evaluate Reliability at Time t (optional)", "required": False},
             ]},
            {"key": "rel_2", "analysis_id": "weibull_reliability", "label": "Weibull Reliability",
             "number": "1.2", "premium": True,
             "inputs": [
                 {"name": "beta", "type": "number", "label": "Beta (shape parameter)"},
                 {"name": "eta", "type": "number", "label": "Eta (scale parameter)"},
                 {"name": "time_horizon", "type": "number", "label": "Time Horizon"},
             ]},
        ],
    },
    "QualityControl": {
        "label": "Quality Control",
        "description": "Control limits (UCL/LCL), X-bar chart data, Cp/Cpk process capability",
        "needs_dataframe": True,
        "items": [
            {"key": "qc_1", "analysis_id": "quality_control_limits", "label": "Control Limits (UCL/LCL) + X-bar Chart",
             "number": "2.1", "premium": False,
             "inputs": [{"name": "column", "type": "column_numeric", "label": "Process Measurement Column"}]},
            {"key": "qc_2", "analysis_id": "process_capability", "label": "Process Capability (Cp / Cpk)",
             "number": "2.2", "premium": True,
             "inputs": [
                 {"name": "column", "type": "column_numeric", "label": "Process Measurement Column"},
                 {"name": "usl", "type": "number", "label": "Upper Spec Limit (USL)"},
                 {"name": "lsl", "type": "number", "label": "Lower Spec Limit (LSL)"},
             ]},
        ],
    },
    "DOE": {
        "label": "Design of Experiments",
        "description": "One-way and two-way ANOVA for experiment results",
        "needs_dataframe": True,
        "items": [
            {"key": "doe_1", "analysis_id": "one_way_anova", "label": "One-Way ANOVA",
             "number": "3.1", "premium": False,
             "inputs": [
                 {"name": "response_col", "type": "column_numeric", "label": "Response Column"},
                 {"name": "factor_col", "type": "column_categorical", "label": "Factor Column"},
             ]},
            {"key": "doe_2", "analysis_id": "two_way_anova", "label": "Two-Way ANOVA",
             "number": "3.2", "premium": True,
             "inputs": [
                 {"name": "response_col", "type": "column_numeric", "label": "Response Column"},
                 {"name": "factor1", "type": "column_categorical", "label": "Factor 1"},
                 {"name": "factor2", "type": "column_categorical", "label": "Factor 2"},
             ]},
        ],
    },
    "Optimization": {
        "label": "Optimization",
        "description": "Linear programming (max/min) and nonlinear optimization",
        "needs_dataframe": False,
        "items": [
            {"key": "opt_1", "analysis_id": "linear_optimization", "label": "Linear Programming (Max/Min)",
             "number": "4.1", "premium": False,
             "inputs": [
                 {"name": "goal", "type": "select", "label": "Goal", "options": ["maximize", "minimize"]},
                 {"name": "objective", "type": "number_array", "label": "Objective Coefficients (e.g. 3,5)"},
                 {"name": "constraints", "type": "number_matrix", "label": "Constraint Coefficients (rows)"},
                 {"name": "rhs", "type": "number_array", "label": "Constraint RHS values"},
             ]},
            {"key": "opt_2", "analysis_id": "nonlinear_optimization", "label": "Nonlinear Optimization",
             "number": "4.2", "premium": True,
             "inputs": [
                 {"name": "expression", "type": "text", "label": "Objective f(x) e.g. x[0]**2 + x[1]**2 - 4*x[0]"},
                 {"name": "initial_guess", "type": "number_array", "label": "Initial Guess (e.g. 0,0)"},
             ]},
        ],
    },
    "ErrorAnalysis": {
        "label": "Error Analysis",
        "description": "MAE, RMSE, MAPE between actual and predicted values",
        "needs_dataframe": True,
        "items": [
            {"key": "err_1", "analysis_id": "error_analysis", "label": "Error Metrics (MAE / RMSE / MAPE)",
             "number": "5.1", "premium": False,
             "inputs": [
                 {"name": "actual_col", "type": "column_numeric", "label": "Actual Values Column"},
                 {"name": "predicted_col", "type": "column_numeric", "label": "Predicted Values Column"},
             ]},
        ],
    },
    "Simulation": {
        "label": "Simulation",
        "description": "Monte Carlo simulation over user-defined input distributions",
        "needs_dataframe": False,
        "items": [
            {"key": "sim_1", "analysis_id": "monte_carlo_simulation", "label": "Monte Carlo Simulation",
             "number": "6.1", "premium": True,
             "inputs": [
                 {"name": "inputs", "type": "distribution_list", "label": "Input Variables (name, distribution, params)"},
                 {"name": "expression", "type": "text", "label": "Model Expression (e.g. speed * hours * eff)"},
                 {"name": "n_simulations", "type": "number", "label": "Number of Simulations", "required": False},
             ]},
        ],
    },
    "Queuing": {
        "label": "Queuing Analysis",
        "description": "M/M/1 queue: utilization, wait time, queue length",
        "needs_dataframe": False,
        "items": [
            {"key": "q_1", "analysis_id": "mm1_queue", "label": "M/M/1 Queue Metrics",
             "number": "7.1", "premium": False,
             "inputs": [
                 {"name": "arrival_rate", "type": "number", "label": "Arrival Rate (λ)"},
                 {"name": "service_rate", "type": "number", "label": "Service Rate (μ)"},
             ]},
        ],
    },
    "NetworkAnalysis": {
        "label": "Network Analysis",
        "description": "Shortest path / distance across a weighted network",
        "needs_dataframe": False,
        "items": [
            {"key": "net_1", "analysis_id": "shortest_path_analysis", "label": "Shortest Path",
             "number": "8.1", "premium": True,
             "inputs": [
                 {"name": "edges", "type": "edge_list", "label": "Edges (node A, node B, weight)"},
                 {"name": "source", "type": "text", "label": "Source Node"},
                 {"name": "target", "type": "text", "label": "Target Node"},
             ]},
        ],
    },
    "NumericalMethods": {
        "label": "Numerical Methods",
        "description": "Root-finding, integration, and ODE solving",
        "needs_dataframe": False,
        "items": [
            {"key": "num_1", "analysis_id": "newton_raphson", "label": "Newton-Raphson Root Finding",
             "number": "9.1", "premium": False,
             "inputs": [
                 {"name": "expression", "type": "text", "label": "f(x) e.g. x**3 - 2*x - 5"},
                 {"name": "derivative_expression", "type": "text", "label": "f'(x) e.g. 3*x**2 - 2"},
                 {"name": "initial_guess", "type": "number", "label": "Initial Guess"},
             ]},
            {"key": "num_2", "analysis_id": "trapezoidal_integration", "label": "Trapezoidal Integration",
             "number": "9.2", "premium": False,
             "inputs": [
                 {"name": "expression", "type": "text", "label": "f(x) e.g. np.sin(x) + x**2"},
                 {"name": "a", "type": "number", "label": "Lower Bound (a)"},
                 {"name": "b", "type": "number", "label": "Upper Bound (b)"},
             ]},
            {"key": "num_3", "analysis_id": "solve_ode", "label": "Solve ODE (dy/dt = f(t, y))",
             "number": "9.3", "premium": True,
             "inputs": [
                 {"name": "expression", "type": "text", "label": "dy/dt e.g. -0.1*(y-25)"},
                 {"name": "y0", "type": "number", "label": "Initial Value y0"},
                 {"name": "t0", "type": "number", "label": "Start Time"},
                 {"name": "t1", "type": "number", "label": "End Time"},
             ]},
        ],
    },
}

_ANALYSIS_ROUTER = {
    'reliability_summary': reliability_summary,
    'weibull_reliability': weibull_reliability,
    'quality_control_limits': quality_control_limits,
    'process_capability': process_capability,
    'one_way_anova': one_way_anova,
    'two_way_anova': two_way_anova,
    'linear_optimization': linear_optimization,
    'nonlinear_optimization': nonlinear_optimization,
    'error_analysis': error_analysis,
    'monte_carlo_simulation': monte_carlo_simulation,
    'mm1_queue': mm1_queue,
    'shortest_path_analysis': shortest_path_analysis,
    'newton_raphson': newton_raphson,
    'trapezoidal_integration': trapezoidal_integration,
    'solve_ode': solve_ode,
}


# Public alias so route files don't need to import the "private" underscore name
ENGINEERING_MODULES = _ENGINEERING_MODULES


def get_engineering_catalog() -> dict:
    """Returns the full module/sub-analysis catalog for the frontend."""
    modules = []
    for key, mod in _ENGINEERING_MODULES.items():
        modules.append({
            'module_key': key,
            'label': mod['label'],
            'description': mod['description'],
            'needs_dataframe': mod['needs_dataframe'],
            'items': mod['items'],
        })
    return {'modules': modules}


def run_engineering_analysis(analysis_id: str, df: pd.DataFrame, parameters: dict) -> dict:
    """Main dispatcher — same shape as Stage-1's run_universal_analysis."""
    fn = _ANALYSIS_ROUTER.get(analysis_id)
    if not fn:
        return _err(f"'{analysis_id}' is not a recognised engineering analysis")
    try:
        return fn(df, parameters or {})
    except Exception as e:
        return _err(f'Unexpected error running {analysis_id}: {e}')


# ══════════════════════════════════════════════════════════════════════════
# SMART SUGGESTIONS — inspect a file's columns_meta and recommend specific
# engineering sub-tests (with a plain-English reason + pre-filled inputs),
# the same way Stage-1 auto-detects "Nominal / Ordinal / Continuous / …".
#
# Only the data-driven modules (Quality Control, DOE, Error Analysis) can be
# meaningfully suggested from columns alone — the parameter-only modules
# (Reliability, Optimization, Simulation, Queuing, Network, Numerical
# Methods) don't read the file, so they aren't included as "recommended for
# this file", though they stay reachable in the full catalog.
# ══════════════════════════════════════════════════════════════════════════
def _is_id_col(c: dict) -> bool:
    n = c.get('name', '').lower()
    return 'id' in n or 'respondent' in n


def suggest_engineering_analyses(columns_meta: list) -> dict:
    if not columns_meta:
        return {'recommended': [], 'numeric_columns': [], 'categorical_columns': []}

    numeric = [c for c in columns_meta
               if c.get('python_type') in ('integer', 'float') and not _is_id_col(c)]
    categorical = [c for c in columns_meta
                    if c.get('python_type') == 'string' and not _is_id_col(c)]

    numeric_names = [c['name'] for c in numeric]
    categorical_names = [c['name'] for c in categorical]

    recommended = []

    # ── Quality Control: any numeric column measured repeatedly is a
    #    candidate for control limits / X-bar charting. Prefer a column
    #    whose name reads like a measured process quantity. ──────────────
    QC_KEYWORDS = ['measure', 'value', 'score', 'rate', 'time', 'weight',
                   'length', 'width', 'height', 'pressure', 'temp', 'output',
                   'yield', 'thickness', 'diameter', 'reading']
    if numeric:
        qc_col = next((c['name'] for c in numeric
                        if any(k in c['name'].lower() for k in QC_KEYWORDS)), numeric[0]['name'])
        recommended.append({
            'module_key': 'QualityControl',
            'analysis_id': 'quality_control_limits',
            'item_key': 'qc_1',
            'label': 'Control Limits (UCL/LCL) + X-bar Chart',
            'reason': f"'{qc_col}' is a repeated numeric measurement — control limits can flag out-of-spec points.",
            'prefill': {'column': qc_col},
        })

    # ── DOE: a low-cardinality categorical column (a plausible "factor" or
    #    "treatment group") next to a numeric response column. ──────────
    factor_candidates = [c for c in categorical if 2 <= (c.get('unique_values') or 0) <= 10]
    if factor_candidates and numeric:
        factor = factor_candidates[0]['name']
        response = numeric[0]['name']
        recommended.append({
            'module_key': 'DOE',
            'analysis_id': 'one_way_anova',
            'item_key': 'doe_1',
            'label': 'One-Way ANOVA',
            'reason': f"'{factor}' looks like a group/factor column ({factor_candidates[0].get('unique_values')} levels) — test whether it affects '{response}'.",
            'prefill': {'response_col': response, 'factor_col': factor},
        })
        if len(factor_candidates) >= 2:
            factor2 = factor_candidates[1]['name']
            recommended.append({
                'module_key': 'DOE',
                'analysis_id': 'two_way_anova',
                'item_key': 'doe_2',
                'label': 'Two-Way ANOVA',
                'reason': f"Two candidate factors detected ('{factor}', '{factor2}') — check for an interaction effect on '{response}'.",
                'prefill': {'response_col': response, 'factor1': factor, 'factor2': factor2},
            })

    # ── Error Analysis: two numeric columns whose names read like an
    #    actual/predicted pair. Only suggested on a real name match — a
    #    blind "first two numeric columns" fallback isn't reliable enough
    #    to present as a confident recommendation. ───────────────────────
    ACTUAL_KW = ['actual', 'true', 'observed', 'real']
    PREDICTED_KW = ['predicted', 'forecast', 'estimate', 'estimated', 'expected', 'model']
    actual_col = next((c['name'] for c in numeric if any(k in c['name'].lower() for k in ACTUAL_KW)), None)
    predicted_col = next((c['name'] for c in numeric if any(k in c['name'].lower() for k in PREDICTED_KW)), None)
    if actual_col and predicted_col and actual_col != predicted_col:
        recommended.append({
            'module_key': 'ErrorAnalysis',
            'analysis_id': 'error_analysis',
            'item_key': 'err_1',
            'label': 'Error Metrics (MAE / RMSE / MAPE)',
            'reason': f"'{actual_col}' and '{predicted_col}' look like an actual-vs-predicted pair — measure prediction error.",
            'prefill': {'actual_col': actual_col, 'predicted_col': predicted_col},
        })

    return {
        'recommended': recommended,
        'numeric_columns': numeric_names,
        'categorical_columns': categorical_names,
    }