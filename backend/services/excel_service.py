"""
Excel Service - File parsing, metadata extraction, quality analysis
"""
import os
import json
import uuid
import hashlib
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Any


ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'csv', 'xlsm', 'xlsb'}


def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def secure_filename_custom(filename: str) -> str:
    """Generate a secure unique filename."""
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else 'xlsx'
    unique_id = str(uuid.uuid4()).replace('-', '')
    return f"{unique_id}.{ext}"


def get_column_analysis(df: pd.DataFrame) -> List[Dict]:
    """Detailed per-column analysis."""
    cols_meta = []
    for col in df.columns:
        series = df[col]
        dtype = str(series.dtype)
        missing = int(series.isna().sum())
        unique = int(series.nunique())
        
        py_type = infer_column_type(series)
        col_info = {
            'name': str(col),
            'dtype': dtype,
            'python_type': py_type,
            'stat_type': infer_statistical_type(series, str(col), list(df.columns)),
            'missing_count': missing,
            'missing_pct': round(missing / len(df) * 100, 2) if len(df) > 0 else 0,
            'unique_values': unique,
            'unique_pct': round(unique / len(df) * 100, 2) if len(df) > 0 else 0,
            'is_nullable': missing > 0,
        }
        
        # Numeric stats
        if pd.api.types.is_numeric_dtype(series):
            col_info.update({
                'min': safe_val(series.min()),
                'max': safe_val(series.max()),
                'mean': safe_val(series.mean()),
                'median': safe_val(series.median()),
                'std': safe_val(series.std()),
                'sum': safe_val(series.sum()),
                'has_negatives': bool((series < 0).any()),
                'has_zeros': bool((series == 0).any()),
                'outliers': count_outliers(series),
            })
        elif pd.api.types.is_string_dtype(series) or series.dtype == object:
            non_null = series.dropna()
            col_info.update({
                'sample_values': [str(v) for v in non_null.head(5).tolist()],
                'max_length': int(non_null.astype(str).str.len().max()) if len(non_null) > 0 else 0,
                'min_length': int(non_null.astype(str).str.len().min()) if len(non_null) > 0 else 0,
                'top_values': safe_value_counts(series),
            })
        elif pd.api.types.is_datetime64_any_dtype(series):
            col_info.update({
                'min_date': str(series.min()) if not series.isna().all() else None,
                'max_date': str(series.max()) if not series.isna().all() else None,
                'date_range_days': (series.max() - series.min()).days if not series.isna().all() else 0,
            })
        
        cols_meta.append(col_info)
    
    return cols_meta


# ── Statistical type constants ───────────────────────────────────────────
_ORDINAL_KW   = ['level','rating','rank','grade','satisfaction','performance',
                  'frequency','stage','priority','tier','education','income_cat',
                  'income_category','class','scale']
_TIME_KW      = ['month','date','week','quarter','period','time','month_year','year_month']
_BINARY_VALS  = {'yes','no','true','false','1','0','y','n',
                  'pass','fail','active','inactive','present','absent'}
_PANEL_ENTITY = ['state','country','region','district','province','city','entity']


def infer_statistical_type(series: pd.Series, col_name: str,
                            all_col_names: list = None) -> str:
    """
    Classify a single column into one of the 8 statistical variable types:
      Identifier | Nominal | Ordinal | Binary | Discrete | Continuous |
      TimeSeries | Panel (Entity) | Panel (Time) | Panel (Measure)

    Parameters
    ----------
    series       : the pandas Series for this column
    col_name     : column name (used for keyword matching)
    all_col_names: list of ALL column names in the DataFrame (used to detect Panel datasets)
    """
    name   = col_name.lower().strip()
    unique = series.nunique()
    py_t   = infer_column_type(series)   # 'integer','float','string','boolean','datetime'
    all_names = [c.lower() for c in (all_col_names or [])]

    # ── Identifier ──────────────────────────────────────────────────────
    if name in ('id', 'respondent_id', 'respondent id') or name.endswith('_id'):
        return 'Identifier'

    # ── Panel dataset detection ──────────────────────────────────────────
    has_entity = any(k in n for n in all_names for k in _PANEL_ENTITY)
    has_year   = 'year' in all_names or 'yr' in all_names
    if has_entity and has_year:
        if name == 'year' or name == 'yr':
            return 'Panel (Time)'
        if any(k in name for k in _PANEL_ENTITY):
            return 'Panel (Entity)'
        if py_t in ('integer', 'float'):
            return 'Panel (Measure)'

    # ── Time index columns ───────────────────────────────────────────────
    # Only match if the column name IS a time keyword, or STARTS with it
    # followed by a separator — prevents 'monthly_income' matching 'month'
    def _is_time_col(n, k):
        if n == k:
            return True
        # starts with keyword and next char is a separator
        if n.startswith(k) and len(n) > len(k) and n[len(k)] in ('_', '-', ' ', '.'):
            return True
        return False
    if any(_is_time_col(name, k) for k in _TIME_KW):
        return 'TimeSeries'
    if py_t in ('datetime', 'date_string'):
        return 'TimeSeries'
    if name == 'year' and py_t == 'integer':
        return 'TimeSeries'

    # ── String / categorical columns ─────────────────────────────────────
    if py_t == 'string':
        # Binary: exactly 2 unique values that are yes/no-like
        if unique == 2:
            top_vals = {str(v).strip().lower() for v in series.dropna().unique()}
            if top_vals.issubset(_BINARY_VALS):
                return 'Binary'
        # Ordinal: name contains an ordering keyword
        if any(k in name for k in _ORDINAL_KW):
            return 'Ordinal'
        return 'Nominal'

    # ── Boolean ──────────────────────────────────────────────────────────
    if py_t == 'boolean':
        return 'Binary'

    # ── Numeric columns ──────────────────────────────────────────────────
    if py_t == 'integer':
        return 'Discrete'
    if py_t == 'float':
        return 'Continuous'

    return 'Unknown'


def infer_column_type(series: pd.Series) -> str:
    if pd.api.types.is_integer_dtype(series):
        return 'integer'
    elif pd.api.types.is_float_dtype(series):
        return 'float'
    elif pd.api.types.is_bool_dtype(series):
        return 'boolean'
    elif pd.api.types.is_datetime64_any_dtype(series):
        return 'datetime'
    else:
        # Try to detect dates in object columns
        sample = series.dropna().head(10)
        try:
            pd.to_datetime(sample)
            return 'date_string'
        except:
            pass
        return 'string'


def safe_val(val):
    if pd.isna(val) or val is None:
        return None
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.floating,)):
        return float(val)
    return val


def count_outliers(series: pd.Series) -> int:
    try:
        q1 = series.quantile(0.25)
        q3 = series.quantile(0.75)
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        return int(((series < lower) | (series > upper)).sum())
    except:
        return 0


def safe_value_counts(series: pd.Series, n=5) -> List:
    try:
        counts = series.value_counts().head(n)
        return [{'value': str(k), 'count': int(v)} for k, v in counts.items()]
    except:
        return []


# ── Junk column names that are NOT real data ──────────────────────────────
_JUNK_COL_NAMES = {
    'tests', 'test', 'data types', 'data type', 'notes', 'legend',
    'description', 'remarks', 'comments', 'unnamed',
}

def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove all non-data columns before analysis:
      - Unnamed: N  columns (Excel artefacts)
      - Columns whose name is a known junk label (Tests, Data Types, Notes…)
      - Columns that are 100% empty (all NaN)
    This ensures columns_meta stored in the DB only reflects REAL data columns,
    so the file-type detection logic works correctly.
    """
    import re as _re
    n_rows = len(df)
    drop = []
    for c in df.columns:
        name = str(c).strip().lower()
        if name.startswith('unnamed'):
            drop.append(c)
        elif _re.fullmatch(r'column_\d+', name):
            # Auto-generated placeholder name (from a blank header cell) — drop it
            drop.append(c)
        elif name in _JUNK_COL_NAMES:
            drop.append(c)
        elif df[c].isna().all():
            drop.append(c)
        elif n_rows > 0 and df[c].notna().sum() <= max(1, int(n_rows * 0.03)):
            # Column is >97% empty — almost certainly a spacer/junk column
            drop.append(c)
    return df.drop(columns=drop) if drop else df


def calculate_data_quality_score(df: pd.DataFrame, columns_meta: List[Dict]) -> float:
    """Calculate a 0-100 data quality score."""
    scores = []
    
    # Completeness: % of non-missing values
    total_cells = df.shape[0] * df.shape[1]
    missing_cells = df.isna().sum().sum()
    completeness = (1 - missing_cells / total_cells) * 100 if total_cells > 0 else 100
    scores.append(('completeness', completeness, 40))
    
    # Uniqueness: penalize if >30% rows are duplicates
    dup_count = df.duplicated().sum()
    uniqueness = (1 - dup_count / len(df)) * 100 if len(df) > 0 else 100
    scores.append(('uniqueness', uniqueness, 20))
    
    # Consistency: penalize mixed types (columns with many different inferred types)
    consistency = 80  # Base score; improves with proper typing
    scores.append(('consistency', consistency, 20))
    
    # Validity: penalize excessive outliers
    outlier_cols = [c for c in columns_meta if c.get('outliers', 0) > len(df) * 0.1]
    validity = max(0, 100 - len(outlier_cols) * 10)
    scores.append(('validity', validity, 20))
    
    total_weight = sum(w for _, _, w in scores)
    weighted_score = sum(score * weight for _, score, weight in scores) / total_weight
    return round(min(100, max(0, weighted_score)), 1)


def get_file_insights(df: pd.DataFrame, columns_meta: List[Dict]) -> Dict:
    """Generate insights about the file."""
    numeric_cols = [c['name'] for c in columns_meta if c['python_type'] in ('integer', 'float')]
    text_cols = [c['name'] for c in columns_meta if c['python_type'] == 'string']
    date_cols = [c['name'] for c in columns_meta if c['python_type'] in ('datetime', 'date_string')]
    
    warnings = []
    suggestions = []
    
    # Warnings
    high_missing = [c for c in columns_meta if c['missing_pct'] > 30]
    if high_missing:
        warnings.append(f"{len(high_missing)} column(s) have >30% missing data: {', '.join(c['name'] for c in high_missing[:3])}")
    
    dup_count = int(df.duplicated().sum())
    if dup_count > 0:
        warnings.append(f"Found {dup_count} duplicate rows")
    
    all_missing = [c for c in columns_meta if c['missing_pct'] == 100]
    if all_missing:
        warnings.append(f"{len(all_missing)} column(s) are completely empty")
    
    # Suggestions based on content
    if numeric_cols:
        suggestions.append('Statistical Summary & Distribution Analysis')
        suggestions.append('Correlation Heatmap')
        if len(numeric_cols) >= 2:
            suggestions.append('Scatter Plot Analysis')
    if date_cols:
        suggestions.append('Time Series Trend Analysis')
        suggestions.append('Seasonal Decomposition')
    if text_cols:
        suggestions.append('Category Distribution Analysis')
        suggestions.append('Frequency Analysis & Word Cloud')
    if len(numeric_cols) >= 3:
        suggestions.append('PCA / Dimensionality Analysis')
        suggestions.append('Outlier Detection')
    suggestions.append('AI-Powered Narrative Report')
    suggestions.append('Data Quality Assessment')
    
    return {
        'numeric_columns': numeric_cols,
        'text_columns': text_cols,
        'date_columns': date_cols,
        'warnings': warnings,
        'suggestions': suggestions[:8],
        'summary': {
            'total_rows': len(df),
            'total_cols': len(df.columns),
            'numeric_cols_count': len(numeric_cols),
            'text_cols_count': len(text_cols),
            'date_cols_count': len(date_cols),
            'duplicate_rows': dup_count,
            'fully_missing_cols': len(all_missing),
        }
    }


def get_recommended_analyses(df: pd.DataFrame, columns_meta: List[Dict]) -> List[Dict]:
    """Recommend specific analyses based on data."""
    numeric_cols = [c['name'] for c in columns_meta if c['python_type'] in ('integer', 'float')]
    date_cols = [c['name'] for c in columns_meta if c['python_type'] in ('datetime', 'date_string')]
    text_cols = [c['name'] for c in columns_meta if c['python_type'] == 'string']
    
    analyses = []
    
    analyses.append({
        'id': 'summary_statistics',
        'title': 'Summary Statistics',
        'description': 'Mean, median, std deviation, min, max for all numeric columns',
        'icon': 'chart-bar',
        'category': 'descriptive',
        'is_free': True,
        'columns_needed': numeric_cols[:5]
    })
    
    analyses.append({
        'id': 'data_quality',
        'title': 'Data Quality Report',
        'description': 'Missing values, duplicates, outliers, and quality score analysis',
        'icon': 'shield-check',
        'category': 'quality',
        'is_free': True,
        'columns_needed': []
    })
    
    if len(numeric_cols) >= 2:
        analyses.append({
            'id': 'correlation_matrix',
            'title': 'Correlation Matrix',
            'description': 'Identify relationships between numeric variables',
            'icon': 'grid',
            'category': 'statistical',
            'is_free': False,
            'columns_needed': numeric_cols[:10]
        })
    
    if date_cols and numeric_cols:
        analyses.append({
            'id': 'time_series',
            'title': 'Time Series Analysis',
            'description': 'Trends, seasonality, and forecasting',
            'icon': 'trending-up',
            'category': 'temporal',
            'is_free': False,
            'columns_needed': [date_cols[0]] + numeric_cols[:3]
        })
    
    if numeric_cols:
        analyses.append({
            'id': 'distribution',
            'title': 'Distribution Analysis',
            'description': 'Histograms, box plots, outlier detection',
            'icon': 'bar-chart-2',
            'category': 'statistical',
            'is_free': True,
            'columns_needed': numeric_cols[:5]
        })
    
    if text_cols:
        analyses.append({
            'id': 'category_analysis',
            'title': 'Category Analysis',
            'description': 'Frequency counts, pie charts for categorical data',
            'icon': 'pie-chart',
            'category': 'descriptive',
            'is_free': True,
            'columns_needed': text_cols[:5]
        })
    
    if len(numeric_cols) >= 2:
        analyses.append({
            'id': 'scatter_analysis',
            'title': 'Scatter Plot Analysis',
            'description': 'Visualize relationships between pairs of variables',
            'icon': 'scatter',
            'category': 'visual',
            'is_free': False,
            'columns_needed': numeric_cols[:4]
        })
    
    analyses.append({
        'id': 'ai_insights',
        'title': 'AI-Powered Insights (Gemini)',
        'description': 'Advanced AI analysis, narrative report, actionable recommendations',
        'icon': 'cpu',
        'category': 'ai',
        'is_free': False,
        'columns_needed': []
    })
    
    return analyses


def _detect_header_row(raw_df: pd.DataFrame, max_scan: int = 15) -> int:
    """
    Find the real header row in a messy sheet.

    Many real-world business files have title rows, dates, blank rows, or
    merged cells above the actual column headers. This scans the first
    `max_scan` rows and picks the row most likely to be the true header.

    Scoring heuristic for each candidate row R:
      + lots of non-empty cells in R (a header names many columns)
      + cells in R are mostly text (labels), not numbers
      + the rows BELOW R contain a good amount of numeric / varied data
      - penalise rows that look like a single title (only 1-2 filled cells)

    Returns the 0-based index of the best header row (0 if none is clearly better).
    """
    n_rows, n_cols = raw_df.shape
    if n_rows == 0 or n_cols == 0:
        return 0

    scan = min(max_scan, n_rows - 1)
    best_row, best_score = 0, -1e9

    for r in range(scan + 1):
        row = raw_df.iloc[r]
        non_empty = row.notna().sum()
        if non_empty == 0:
            continue

        # How many cells in this row are text (label-like) vs numeric?
        text_cells = 0
        numeric_cells = 0
        for v in row.dropna():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                numeric_cells += 1
            else:
                # try to parse as number
                try:
                    float(str(v).replace(',', '').strip())
                    numeric_cells += 1
                except (ValueError, TypeError):
                    text_cells += 1

        # Look at the up-to-10 rows BELOW this one — a real header is followed by data
        below = raw_df.iloc[r + 1: r + 11]
        below_numeric = 0
        below_filled = 0
        for _, brow in below.iterrows():
            for v in brow.dropna():
                below_filled += 1
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    below_numeric += 1
                else:
                    try:
                        float(str(v).replace(',', '').strip())
                        below_numeric += 1
                    except (ValueError, TypeError):
                        pass

        # ── Score ──
        # A real header row is: (1) mostly TEXT labels, (2) fills many columns,
        # (3) followed by rows that contain real (often numeric) data.
        fill_ratio = non_empty / n_cols
        text_ratio = text_cells / max(non_empty, 1)
        below_rows = max(len(below), 1)
        below_fill_ratio = below_filled / (below_rows * n_cols)   # how full the data below is

        # Base score rewards a wide, text-heavy row with data underneath
        score = (text_ratio * 45) + (fill_ratio * 25) + (below_fill_ratio * 20)

        # Strong bonus: header is text AND the rows below are numeric (classic table)
        if text_ratio >= 0.8 and below_numeric > 0:
            score += 25

        # Penalise a lone title/section row (only 1-2 cells filled on a wide sheet)
        if non_empty <= 2 and n_cols > 4:
            score -= 60
        # Heavily penalise a row that is itself mostly numeric — that's DATA, not a header
        if numeric_cells > 0 and text_cells == 0 and non_empty > 2:
            score -= 80
        elif numeric_cells > text_cells and non_empty > 3:
            score -= 40

        # Prefer earlier rows when scores are close (headers sit above data)
        score -= r * 0.5

        if score > best_score:
            best_score, best_row = score, r

    return best_row


def _read_sheet_smart(file_path: str, sheet_name=None, is_csv: bool = False) -> pd.DataFrame:
    """
    Read a sheet/CSV, auto-detecting the real header row so that files with
    title rows / blank rows / sub-headers above the data are parsed correctly.
    """
    read_kwargs = dict(header=None)
    # First read with NO header to inspect the raw layout
    if is_csv:
        raw = None
        for enc in ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']:
            try:
                raw = pd.read_csv(file_path, encoding=enc, low_memory=False, header=None)
                break
            except UnicodeDecodeError:
                continue
        if raw is None:
            return pd.DataFrame()
    else:
        raw = pd.read_excel(file_path, sheet_name=sheet_name, header=None)

    if raw.empty:
        return pd.DataFrame()

    header_row = _detect_header_row(raw)

    # Re-read using the detected header row
    if is_csv:
        for enc in ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']:
            try:
                df = pd.read_csv(file_path, encoding=enc, low_memory=False, header=header_row)
                break
            except UnicodeDecodeError:
                continue
    else:
        df = pd.read_excel(file_path, sheet_name=sheet_name, header=header_row)

    # Forward-fill merged-cell header names that pandas leaves as Unnamed
    new_cols = []
    last_valid = None
    for i, c in enumerate(df.columns):
        cs = str(c).strip()
        if cs.startswith('Unnamed') or cs == '' or cs == 'nan':
            # keep a unique placeholder; clean_dataframe will drop truly empty ones
            new_cols.append(f'Column_{i}')
        else:
            last_valid = cs
            new_cols.append(cs)
    df.columns = new_cols

    # Drop rows that are completely empty (leftover spacer rows)
    df = df.dropna(how='all').reset_index(drop=True)
    return df


def parse_excel_file(file_path: str, file_type: str) -> Dict[str, Any]:
    """Parse Excel/CSV file and return comprehensive metadata."""
    result = {
        'success': False,
        'error': None,
        'sheets': [],
        'columns_meta': [],
        'insights': {},
        'recommended_analyses': [],
        'summary': {}
    }
    
    try:
        sheets_meta = []
        all_dfs = {}
        
        if file_type == 'csv':
            # Smart-read with automatic header-row detection
            df = _read_sheet_smart(file_path, is_csv=True)
            all_dfs['Sheet1'] = df
        else:
            xl = pd.ExcelFile(file_path)
            for sheet_name in xl.sheet_names:
                try:
                    # Smart-read each sheet, auto-detecting the real header row
                    df = _read_sheet_smart(file_path, sheet_name=sheet_name, is_csv=False)
                    all_dfs[sheet_name] = df
                except Exception:
                    all_dfs[sheet_name] = pd.DataFrame()
        
        total_rows = 0
        total_cols = 0
        
        for sheet_name, df in all_dfs.items():
            rows, cols = df.shape
            total_rows += rows
            total_cols = max(total_cols, cols)
            
            # Fix column names
            df.columns = [str(c).strip() if str(c) != 'nan' else f'Column_{i}' 
                         for i, c in enumerate(df.columns)]
            
            missing = int(df.isna().sum().sum())
            dups = int(df.duplicated().sum())
            
            # Clean junk/Unnamed columns from this sheet before analysis
            clean_df = clean_dataframe(df)
            clean_rows = len(clean_df)
            clean_cols = len(clean_df.columns)
            sheet_col_meta = get_column_analysis(clean_df) if clean_rows > 0 and clean_cols > 0 else []

            sheets_meta.append({
                'name': sheet_name,
                'rows': rows,
                'cols': clean_cols,
                'cells': rows * clean_cols,
                'missing_values': missing,
                'missing_pct': round(missing / (rows * clean_cols) * 100, 2) if rows * clean_cols > 0 else 0,
                'duplicate_rows': dups,
                'column_names': [c['name'] for c in sheet_col_meta][:50],
                'columns': sheet_col_meta,
            })
        
        # Use the largest/first sheet for detailed analysis
        primary_df = max(all_dfs.values(), key=lambda d: d.shape[0] * d.shape[1])
        primary_df.columns = [str(c).strip() if str(c) != 'nan' else f'Column_{i}' 
                              for i, c in enumerate(primary_df.columns)]
        
        # ── Strip junk/Unnamed/empty columns BEFORE analysis ────────────
        # This is critical: columns_meta must only contain REAL data columns
        # so the file-type identifier (detect_data_type) works correctly.
        primary_df = clean_dataframe(primary_df)
        
        columns_meta = get_column_analysis(primary_df)
        insights = get_file_insights(primary_df, columns_meta)
        recommended = get_recommended_analyses(primary_df, columns_meta)
        quality_score = calculate_data_quality_score(primary_df, columns_meta)
        
        total_missing = sum(s['missing_values'] for s in sheets_meta)
        total_dups = sum(s['duplicate_rows'] for s in sheets_meta)
        
        result.update({
            'success': True,
            'sheet_count': len(all_dfs),
            'total_rows': total_rows,
            'total_cols': total_cols,
            'total_cells': total_rows * total_cols,
            'missing_values': total_missing,
            'duplicate_rows': total_dups,
            'data_quality_score': quality_score,
            'sheets': sheets_meta,
            'columns_meta': columns_meta,
            'insights': insights,
            'recommended_analyses': recommended,
        })
        
    except Exception as e:
        result['error'] = str(e)
    
    return result