"""
Universal Analytics Engine Routes (RaaS Stage-1)
=================================================
Exposes the Stage-1 analytics catalog to the frontend.
IMPORTANT: Purely additive — does NOT modify routes/analysis.py.
"""
import json
import pandas as pd

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from database import db, User, ExcelFile, Analysis
from services.universal_analytics import (
    run_universal_analysis, get_catalog, suggest_analyses, PREMIUM_ANALYSES
)

universal_bp = Blueprint('universal', __name__)


# ── DataFrame loader ───────────────────────────────────────────────────────
def load_dataframe(excel_file: ExcelFile, sheet_name: str = None) -> pd.DataFrame:
    """Load a file's data with smart header-row detection and optional sheet."""
    try:
        from services.excel_service import _read_sheet_smart
        is_csv = (excel_file.file_type == 'csv')
        if is_csv:
            df = _read_sheet_smart(excel_file.file_path, is_csv=True)
        else:
            # If no sheet given, read the first sheet
            sn = sheet_name if sheet_name else 0
            df = _read_sheet_smart(excel_file.file_path, sheet_name=sn, is_csv=False)
        return _strip_non_data_columns(df)
    except Exception:
        # Fallback to plain read if smart read fails
        try:
            if excel_file.file_type == 'csv':
                for enc in ['utf-8', 'latin-1', 'iso-8859-1']:
                    try:
                        df = pd.read_csv(excel_file.file_path, encoding=enc, low_memory=False)
                        return _strip_non_data_columns(df)
                    except Exception:
                        continue
                return pd.DataFrame()
            kwargs = {'sheet_name': sheet_name} if sheet_name else {'sheet_name': 0}
            df = pd.read_excel(excel_file.file_path, **kwargs)
            return _strip_non_data_columns(df)
        except Exception:
            return pd.DataFrame()


_IGNORED_COL_NAMES = {'tests', 'test', 'data types', 'data type', 'notes', 'legend'}


def _strip_non_data_columns(df: pd.DataFrame) -> pd.DataFrame:
    drop = []
    for c in df.columns:
        name = str(c).strip()
        if name.lower().startswith('unnamed'):
            drop.append(c)
        elif name.lower() in _IGNORED_COL_NAMES:
            drop.append(c)
        elif df[c].isna().all():
            drop.append(c)
    return df.drop(columns=drop) if drop else df


# ══════════════════════════════════════════════════════════════════════════
#  EXACT TEST + SUB-TEST CATALOG per data type
#  Matched to the 8 RaaS Excel reference files.
#
#  Structure per entry:
#    {
#      "key":       unique string used as React key & result storage key
#      "analysis_id": the backend analysis function id to call
#      "label":     display text
#      "is_parent": True = section header (bold, no checkbox)
#                   False = sub-test (has checkbox + Run button)
#      "default":   pre-checked or not
#      "number":    display number like "1.1", "2.3" etc (empty for parents)
#    }
# ══════════════════════════════════════════════════════════════════════════

_CATALOG = {

    # ─────────────────────────────────────────────────────────────────────────
    # NOMINAL — Categories with no natural order (Gender, State, Industry)
    # Reference: Standard nominal analysis (no separate Excel file uploaded)
    # ─────────────────────────────────────────────────────────────────────────
    "Nominal": [
        {"key":"nom_p1",  "analysis_id":"summary_statistics_uae", "label":"Descriptive Statistics",                    "is_parent":True,  "default":False, "number":""},
        {"key":"nom_1_1", "analysis_id":"summary_statistics_uae", "label":"Frequency Tables",                          "is_parent":False, "default":True,  "number":"1.1"},
        {"key":"nom_1_2", "analysis_id":"summary_statistics_uae", "label":"Percentage Tables",                         "is_parent":False, "default":True,  "number":"1.2"},
        {"key":"nom_1_3", "analysis_id":"summary_statistics_uae", "label":"Mode",                                      "is_parent":False, "default":True,  "number":"1.3"},
        {"key":"nom_p2",  "analysis_id":"chi_square",             "label":"Hypothesis Testing",                        "is_parent":True,  "default":False, "number":""},
        {"key":"nom_2_1", "analysis_id":"summary_statistics_uae", "label":"Cross-Tabulations",                         "is_parent":False, "default":False, "number":"2.1"},
        {"key":"nom_2_2", "analysis_id":"chi_square",             "label":"Chi-Square Tests",                          "is_parent":False, "default":True,  "number":"2.2"},
        {"key":"nom_p3",  "analysis_id":"viz_bar_chart",          "label":"Data Visualization",                        "is_parent":True,  "default":False, "number":""},
        {"key":"nom_3_1", "analysis_id":"viz_bar_chart",          "label":"Bar Charts",                                "is_parent":False, "default":True,  "number":"3.1"},
    ],

    # ─────────────────────────────────────────────────────────────────────────
    # ORDINAL — Ordered categories (Education Level, Satisfaction, Rating)
    # Reference: RaaS_Ordinal_Data_Sample.xlsx
    # Columns: Education_Level, Income_Category, Customer_Satisfaction,
    #          Performance_Rating, Purchase_Frequency
    # Tests from file: Frequency Tables, Percentage Tables, Median, Percentiles,
    #   Quartiles (with coded ordinal values), Rank-based Analysis,
    #   Cross-tabulations, Chi-Square Tests,
    #   Ordered category visualizations (Bar Charts)
    # ─────────────────────────────────────────────────────────────────────────
    "Ordinal": [
        {"key":"ord_p1",  "analysis_id":"summary_statistics_uae", "label":"Descriptive Statistics",                    "is_parent":True,  "default":False, "number":""},
        {"key":"ord_1_1", "analysis_id":"summary_statistics_uae", "label":"Frequency Tables",                          "is_parent":False, "default":True,  "number":"1.1"},
        {"key":"ord_1_2", "analysis_id":"summary_statistics_uae", "label":"Percentage Tables",                         "is_parent":False, "default":True,  "number":"1.2"},
        {"key":"ord_1_3", "analysis_id":"summary_statistics_uae", "label":"Median",                                    "is_parent":False, "default":True,  "number":"1.3"},
        {"key":"ord_1_4", "analysis_id":"summary_statistics_uae", "label":"Percentiles",                               "is_parent":False, "default":True,  "number":"1.4"},
        {"key":"ord_1_5", "analysis_id":"summary_statistics_uae", "label":"Quartiles (coded ordinal values)",          "is_parent":False, "default":False, "number":"1.5"},
        {"key":"ord_1_6", "analysis_id":"summary_statistics_uae", "label":"Rank-based Analysis",                       "is_parent":False, "default":False, "number":"1.6"},
        {"key":"ord_p2",  "analysis_id":"chi_square",             "label":"Hypothesis Testing",                        "is_parent":True,  "default":False, "number":""},
        {"key":"ord_2_1", "analysis_id":"summary_statistics_uae", "label":"Cross-Tabulations",                         "is_parent":False, "default":False, "number":"2.1"},
        {"key":"ord_2_2", "analysis_id":"chi_square",             "label":"Chi-Square Tests",                          "is_parent":False, "default":True,  "number":"2.2"},
        {"key":"ord_p3",  "analysis_id":"viz_bar_chart",          "label":"Visualization",                             "is_parent":True,  "default":False, "number":""},
        {"key":"ord_3_1", "analysis_id":"viz_bar_chart",          "label":"Ordered Category Bar Charts",               "is_parent":False, "default":True,  "number":"3.1"},
    ],

    # ─────────────────────────────────────────────────────────────────────────
    # BINARY — Yes/No, True/False columns
    # Reference: RaaS_Binary_Data_Sample.xlsx
    # Columns: Employed, Owns_House, Has_Health_Insurance,
    #          Uses_Digital_Payments, Loan_Defaulted, Purchased_Product
    # Tests from file: Frequency Tables, Percentage Tables, Mode,
    #   Cross-tabulations, Chi-Square Tests,
    #   Binary Logistic Regression (after coding Yes=1, No=0),
    #   Bar Charts, Proportion Analysis
    # ─────────────────────────────────────────────────────────────────────────
    "Binary": [
        {"key":"bin_p1",  "analysis_id":"summary_statistics_uae", "label":"Descriptive Statistics",                    "is_parent":True,  "default":False, "number":""},
        {"key":"bin_1_1", "analysis_id":"summary_statistics_uae", "label":"Frequency Tables",                          "is_parent":False, "default":True,  "number":"1.1"},
        {"key":"bin_1_2", "analysis_id":"summary_statistics_uae", "label":"Percentage Tables",                         "is_parent":False, "default":True,  "number":"1.2"},
        {"key":"bin_1_3", "analysis_id":"summary_statistics_uae", "label":"Mode",                                      "is_parent":False, "default":True,  "number":"1.3"},
        {"key":"bin_p2",  "analysis_id":"chi_square",             "label":"Hypothesis Testing",                        "is_parent":True,  "default":False, "number":""},
        {"key":"bin_2_1", "analysis_id":"summary_statistics_uae", "label":"Cross-Tabulations",                         "is_parent":False, "default":False, "number":"2.1"},
        {"key":"bin_2_2", "analysis_id":"chi_square",             "label":"Chi-Square Tests",                          "is_parent":False, "default":True,  "number":"2.2"},
        {"key":"bin_2_3", "analysis_id":"summary_statistics_uae", "label":"Proportion Analysis",                       "is_parent":False, "default":False, "number":"2.3"},
        {"key":"bin_p3",  "analysis_id":"logistic_regression",    "label":"Regression Analysis",                       "is_parent":True,  "default":False, "number":""},
        {"key":"bin_3_1", "analysis_id":"logistic_regression",    "label":"Binary Logistic Regression (Yes=1, No=0)",  "is_parent":False, "default":True,  "number":"3.1"},
        {"key":"bin_p4",  "analysis_id":"viz_bar_chart",          "label":"Visualization",                             "is_parent":True,  "default":False, "number":""},
        {"key":"bin_4_1", "analysis_id":"viz_bar_chart",          "label":"Bar Charts",                                "is_parent":False, "default":True,  "number":"4.1"},
    ],

    # ─────────────────────────────────────────────────────────────────────────
    # CONTINUOUS — Measured float values (Income, Age, Height, Weight, Sales)
    # Reference: RaaS_Continuous_Numerical_Data_Sample.xlsx
    # Columns: Monthly_Income_INR, Age_Years, Height_cm, Weight_kg,
    #          Monthly_Sales_Lakh_INR, Productivity_Score
    # Tests from file (exact):
    #   1. Descriptive Statistics: Mean, Median, Mode, Variance, Std Dev, CV, Skewness, Kurtosis
    #   2. Summary Statistics: Percentiles, Quartiles, Missing Values, Frequency Distributions
    #   3. Hypothesis Testing: One-Sample t-test, Independent t-test, Paired t-test, ANOVA, F-test
    #   4. Regression Analysis: Linear Regression, Quantile Regression
    #   5. Visualization: Histogram, Scatter Plot, Box Plot, Correlation Heatmap, Line Charts
    # ─────────────────────────────────────────────────────────────────────────
    "Continuous": [
        {"key":"con_p1",  "analysis_id":"descriptive_statistics", "label":"Descriptive Statistics",                    "is_parent":True,  "default":False, "number":""},
        {"key":"con_1_1", "analysis_id":"descriptive_statistics", "label":"Mean",                                      "is_parent":False, "default":True,  "number":"1.1"},
        {"key":"con_1_2", "analysis_id":"descriptive_statistics", "label":"Median",                                    "is_parent":False, "default":True,  "number":"1.2"},
        {"key":"con_1_3", "analysis_id":"descriptive_statistics", "label":"Mode",                                      "is_parent":False, "default":True,  "number":"1.3"},
        {"key":"con_1_4", "analysis_id":"descriptive_statistics", "label":"Variance",                                  "is_parent":False, "default":True,  "number":"1.4"},
        {"key":"con_1_5", "analysis_id":"descriptive_statistics", "label":"Standard Deviation",                        "is_parent":False, "default":True,  "number":"1.5"},
        {"key":"con_1_6", "analysis_id":"descriptive_statistics", "label":"Coefficient of Variation",                  "is_parent":False, "default":True,  "number":"1.6"},
        {"key":"con_1_7", "analysis_id":"descriptive_statistics", "label":"Skewness",                                  "is_parent":False, "default":True,  "number":"1.7"},
        {"key":"con_1_8", "analysis_id":"descriptive_statistics", "label":"Kurtosis",                                  "is_parent":False, "default":True,  "number":"1.8"},
        {"key":"con_p2",  "analysis_id":"summary_statistics_uae", "label":"Summary Statistics",                        "is_parent":True,  "default":False, "number":""},
        {"key":"con_2_1", "analysis_id":"summary_statistics_uae", "label":"Percentiles",                               "is_parent":False, "default":True,  "number":"2.1"},
        {"key":"con_2_2", "analysis_id":"summary_statistics_uae", "label":"Quartiles",                                 "is_parent":False, "default":True,  "number":"2.2"},
        {"key":"con_2_3", "analysis_id":"summary_statistics_uae", "label":"Missing Values",                            "is_parent":False, "default":True,  "number":"2.3"},
        {"key":"con_2_4", "analysis_id":"summary_statistics_uae", "label":"Frequency Distributions",                   "is_parent":False, "default":False, "number":"2.4"},
        {"key":"con_p3",  "analysis_id":"one_sample_ttest",       "label":"Hypothesis Testing",                        "is_parent":True,  "default":False, "number":""},
        {"key":"con_3_1", "analysis_id":"one_sample_ttest",       "label":"One-Sample t-Test",                         "is_parent":False, "default":False, "number":"3.1"},
        {"key":"con_3_2", "analysis_id":"independent_ttest",      "label":"Independent t-Test",                        "is_parent":False, "default":False, "number":"3.2"},
        {"key":"con_3_3", "analysis_id":"paired_ttest",           "label":"Paired t-Test",                             "is_parent":False, "default":False, "number":"3.3"},
        {"key":"con_3_4", "analysis_id":"anova",                  "label":"ANOVA",                                     "is_parent":False, "default":False, "number":"3.4"},
        {"key":"con_3_5", "analysis_id":"f_test",                 "label":"F-Test",                                    "is_parent":False, "default":False, "number":"3.5"},
        {"key":"con_p4",  "analysis_id":"linear_regression",      "label":"Regression Analysis",                       "is_parent":True,  "default":False, "number":""},
        {"key":"con_4_1", "analysis_id":"linear_regression",      "label":"Linear Regression",                         "is_parent":False, "default":False, "number":"4.1"},
        {"key":"con_4_2", "analysis_id":"quantile_regression",    "label":"Quantile Regression",                       "is_parent":False, "default":False, "number":"4.2"},
        {"key":"con_p5",  "analysis_id":"viz_histogram",          "label":"Visualization",                             "is_parent":True,  "default":False, "number":""},
        {"key":"con_5_1", "analysis_id":"viz_histogram",          "label":"Histogram",                                 "is_parent":False, "default":True,  "number":"5.1"},
        {"key":"con_5_2", "analysis_id":"viz_scatter",            "label":"Scatter Plot",                              "is_parent":False, "default":False, "number":"5.2"},
        {"key":"con_5_3", "analysis_id":"viz_boxplot",            "label":"Box Plot",                                  "is_parent":False, "default":True,  "number":"5.3"},
        {"key":"con_5_4", "analysis_id":"viz_correlation_heatmap","label":"Correlation Heatmap",                       "is_parent":False, "default":False, "number":"5.4"},
        {"key":"con_5_5", "analysis_id":"viz_line_chart",         "label":"Line Charts",                               "is_parent":False, "default":False, "number":"5.5"},
    ],

    # ─────────────────────────────────────────────────────────────────────────
    # DISCRETE — Countable integers (Children, Employees, Orders, Visits)
    # Reference: RaaS_Discrete_Numerical_Data_Sample.xlsx
    # Columns: Number_of_Children, Number_of_Employees, Number_of_Factory_Units,
    #          Monthly_Orders_Received, Products_Purchased, Customer_Visits_Per_Month
    # Tests from file (exact):
    #   1. Descriptive Statistics: Mean, Median, Mode, Min/Max, Range, Variance,
    #      Std Dev, CV, Skewness, Kurtosis
    #   2. Summary Statistics: Count, Missing Values, Unique Values, Percentiles,
    #      Quartiles, Frequency Tables
    #   3. Hypothesis Testing: One-sample t-test, Independent t-test, Paired t-test,
    #      ANOVA, F-test
    #   4. Regression: Linear Regression, Quantile Regression
    #   5. Visualization: Histogram, Box Plot, Bar Chart, Scatter Plot, Correlation Heatmap
    # ─────────────────────────────────────────────────────────────────────────
    "Discrete": [
        {"key":"dis_p1",  "analysis_id":"descriptive_statistics", "label":"Descriptive Statistics",                    "is_parent":True,  "default":False, "number":""},
        {"key":"dis_1_1", "analysis_id":"descriptive_statistics", "label":"Mean",                                      "is_parent":False, "default":True,  "number":"1.1"},
        {"key":"dis_1_2", "analysis_id":"descriptive_statistics", "label":"Median",                                    "is_parent":False, "default":True,  "number":"1.2"},
        {"key":"dis_1_3", "analysis_id":"descriptive_statistics", "label":"Mode",                                      "is_parent":False, "default":True,  "number":"1.3"},
        {"key":"dis_1_4", "analysis_id":"descriptive_statistics", "label":"Min / Max",                                 "is_parent":False, "default":True,  "number":"1.4"},
        {"key":"dis_1_5", "analysis_id":"descriptive_statistics", "label":"Range",                                     "is_parent":False, "default":True,  "number":"1.5"},
        {"key":"dis_1_6", "analysis_id":"descriptive_statistics", "label":"Variance",                                  "is_parent":False, "default":True,  "number":"1.6"},
        {"key":"dis_1_7", "analysis_id":"descriptive_statistics", "label":"Standard Deviation",                        "is_parent":False, "default":True,  "number":"1.7"},
        {"key":"dis_1_8", "analysis_id":"descriptive_statistics", "label":"Coefficient of Variation",                  "is_parent":False, "default":True,  "number":"1.8"},
        {"key":"dis_1_9", "analysis_id":"descriptive_statistics", "label":"Skewness",                                  "is_parent":False, "default":False, "number":"1.9"},
        {"key":"dis_1_10","analysis_id":"descriptive_statistics", "label":"Kurtosis",                                  "is_parent":False, "default":False, "number":"1.10"},
        {"key":"dis_p2",  "analysis_id":"summary_statistics_uae", "label":"Summary Statistics",                        "is_parent":True,  "default":False, "number":""},
        {"key":"dis_2_1", "analysis_id":"summary_statistics_uae", "label":"Count",                                     "is_parent":False, "default":True,  "number":"2.1"},
        {"key":"dis_2_2", "analysis_id":"summary_statistics_uae", "label":"Missing Values",                            "is_parent":False, "default":True,  "number":"2.2"},
        {"key":"dis_2_3", "analysis_id":"summary_statistics_uae", "label":"Unique Values",                             "is_parent":False, "default":True,  "number":"2.3"},
        {"key":"dis_2_4", "analysis_id":"summary_statistics_uae", "label":"Percentiles",                               "is_parent":False, "default":False, "number":"2.4"},
        {"key":"dis_2_5", "analysis_id":"summary_statistics_uae", "label":"Quartiles",                                 "is_parent":False, "default":False, "number":"2.5"},
        {"key":"dis_2_6", "analysis_id":"summary_statistics_uae", "label":"Frequency Tables",                          "is_parent":False, "default":True,  "number":"2.6"},
        {"key":"dis_p3",  "analysis_id":"one_sample_ttest",       "label":"Hypothesis Testing",                        "is_parent":True,  "default":False, "number":""},
        {"key":"dis_3_1", "analysis_id":"one_sample_ttest",       "label":"One-Sample t-Test",                         "is_parent":False, "default":False, "number":"3.1"},
        {"key":"dis_3_2", "analysis_id":"independent_ttest",      "label":"Independent t-Test",                        "is_parent":False, "default":False, "number":"3.2"},
        {"key":"dis_3_3", "analysis_id":"paired_ttest",           "label":"Paired t-Test",                             "is_parent":False, "default":False, "number":"3.3"},
        {"key":"dis_3_4", "analysis_id":"anova",                  "label":"ANOVA",                                     "is_parent":False, "default":False, "number":"3.4"},
        {"key":"dis_3_5", "analysis_id":"f_test",                 "label":"F-Test",                                    "is_parent":False, "default":False, "number":"3.5"},
        {"key":"dis_p4",  "analysis_id":"linear_regression",      "label":"Regression",                                "is_parent":True,  "default":False, "number":""},
        {"key":"dis_4_1", "analysis_id":"linear_regression",      "label":"Linear Regression",                         "is_parent":False, "default":False, "number":"4.1"},
        {"key":"dis_4_2", "analysis_id":"quantile_regression",    "label":"Quantile Regression",                       "is_parent":False, "default":False, "number":"4.2"},
        {"key":"dis_p5",  "analysis_id":"viz_histogram",          "label":"Visualization",                             "is_parent":True,  "default":False, "number":""},
        {"key":"dis_5_1", "analysis_id":"viz_histogram",          "label":"Histogram",                                 "is_parent":False, "default":True,  "number":"5.1"},
        {"key":"dis_5_2", "analysis_id":"viz_boxplot",            "label":"Box Plot",                                  "is_parent":False, "default":True,  "number":"5.2"},
        {"key":"dis_5_3", "analysis_id":"viz_bar_chart",          "label":"Bar Chart",                                 "is_parent":False, "default":True,  "number":"5.3"},
        {"key":"dis_5_4", "analysis_id":"viz_scatter",            "label":"Scatter Plot",                              "is_parent":False, "default":False, "number":"5.4"},
        {"key":"dis_5_5", "analysis_id":"viz_correlation_heatmap","label":"Correlation Heatmap",                       "is_parent":False, "default":False, "number":"5.5"},
    ],

    # ─────────────────────────────────────────────────────────────────────────
    # TIME SERIES — Sequential observations over time
    # Reference: RaaS_Time_Series_Dataset.xlsx
    # Columns: Month (Jan-2024…), Sales_Revenue_INR_Lakh, Units_Sold,
    #          Customer_Visits, Marketing_Spend_INR_Lakh, Average_Price_INR,
    #          Inflation_Rate_Percent
    # Tests from file (exact):
    #   1. Time Series Analysis: Moving Average, Trend Analysis, Growth Rate Analysis,
    #      Seasonal Decomposition, Stationarity Tests (ADF/KPSS), ARIMA, Forecasting
    #   2. Regression Analysis: Sales vs Marketing Spend, Sales vs Inflation,
    #      Price vs Units Sold
    #   3. Visualization: Line Charts, Trend Lines, Forecast Plots, Rolling Averages
    # ─────────────────────────────────────────────────────────────────────────
    "TimeSeries": [
        {"key":"ts_p1",  "analysis_id":"moving_average",          "label":"Time Series Analysis",                      "is_parent":True,  "default":False, "number":""},
        {"key":"ts_1_1", "analysis_id":"moving_average",          "label":"Moving Average",                            "is_parent":False, "default":True,  "number":"1.1"},
        {"key":"ts_1_2", "analysis_id":"moving_average",          "label":"Trend Analysis",                            "is_parent":False, "default":True,  "number":"1.2"},
        {"key":"ts_1_3", "analysis_id":"moving_average",          "label":"Growth Rate Analysis",                      "is_parent":False, "default":False, "number":"1.3"},
        {"key":"ts_1_4", "analysis_id":"seasonal_decomposition",  "label":"Seasonal Decomposition",                    "is_parent":False, "default":False, "number":"1.4"},
        {"key":"ts_1_5", "analysis_id":"time_series_adf",         "label":"Stationarity Tests (ADF / KPSS)",           "is_parent":False, "default":True,  "number":"1.5"},
        {"key":"ts_1_6", "analysis_id":"time_series_arima",       "label":"ARIMA",                                     "is_parent":False, "default":False, "number":"1.6"},
        {"key":"ts_1_7", "analysis_id":"time_series_arima",       "label":"Forecasting",                               "is_parent":False, "default":False, "number":"1.7"},
        {"key":"ts_p2",  "analysis_id":"linear_regression",       "label":"Regression Analysis",                       "is_parent":True,  "default":False, "number":""},
        {"key":"ts_2_1", "analysis_id":"linear_regression",       "label":"Sales vs Marketing Spend",                  "is_parent":False, "default":False, "number":"2.1"},
        {"key":"ts_2_2", "analysis_id":"linear_regression",       "label":"Sales vs Inflation",                        "is_parent":False, "default":False, "number":"2.2"},
        {"key":"ts_2_3", "analysis_id":"linear_regression",       "label":"Price vs Units Sold",                       "is_parent":False, "default":False, "number":"2.3"},
        {"key":"ts_p3",  "analysis_id":"viz_line_chart",          "label":"Visualization",                             "is_parent":True,  "default":False, "number":""},
        {"key":"ts_3_1", "analysis_id":"viz_line_chart",          "label":"Line Charts",                               "is_parent":False, "default":True,  "number":"3.1"},
        {"key":"ts_3_2", "analysis_id":"viz_line_chart",          "label":"Trend Lines",                               "is_parent":False, "default":False, "number":"3.2"},
        {"key":"ts_3_3", "analysis_id":"viz_line_chart",          "label":"Forecast Plots",                            "is_parent":False, "default":False, "number":"3.3"},
        {"key":"ts_3_4", "analysis_id":"moving_average",          "label":"Rolling Averages",                          "is_parent":False, "default":False, "number":"3.4"},
    ],

    # ─────────────────────────────────────────────────────────────────────────
    # PANEL — Multiple entities over multiple time periods
    # Reference: RaaS_Panel_Data_Dataset.xlsx
    # Columns: State, Year (2016–2025), GSDP_Crore_INR, Population_Lakh,
    #          Employment_Rate_Percent, MSME_Units, Exports_Crore_INR,
    #          Capital_Investment_Crore_INR
    # Tests from file (exact):
    #   1. Panel Data Analysis: Pooled OLS, Fixed Effects Model, Random Effects Model,
    #      Hausman Test, Between Estimator, Within Estimator
    #   2. Regression Examples: Impact of MSMEs on Exports, Impact of Investment on GSDP,
    #      Employment-Growth Relationship
    #   3. Visualization: Multi-State Trend Lines, Heatmaps, State Comparison Charts,
    #      Panel Growth Analysis
    # ─────────────────────────────────────────────────────────────────────────
    "Panel": [
        {"key":"pan_p1",  "analysis_id":"pooled_ols",             "label":"Panel Data Analysis",                       "is_parent":True,  "default":False, "number":""},
        {"key":"pan_1_1", "analysis_id":"pooled_ols",             "label":"Pooled OLS",                                "is_parent":False, "default":True,  "number":"1.1"},
        {"key":"pan_1_2", "analysis_id":"fixed_effects",          "label":"Fixed Effects Model",                       "is_parent":False, "default":True,  "number":"1.2"},
        {"key":"pan_1_3", "analysis_id":"random_effects",         "label":"Random Effects Model",                      "is_parent":False, "default":False, "number":"1.3"},
        {"key":"pan_1_4", "analysis_id":"pooled_ols",             "label":"Hausman Test (FE vs RE selection)",         "is_parent":False, "default":False, "number":"1.4"},
        {"key":"pan_1_5", "analysis_id":"fixed_effects",          "label":"Between Estimator",                         "is_parent":False, "default":False, "number":"1.5"},
        {"key":"pan_1_6", "analysis_id":"fixed_effects",          "label":"Within Estimator",                          "is_parent":False, "default":False, "number":"1.6"},
        {"key":"pan_p2",  "analysis_id":"linear_regression",      "label":"Regression Examples",                       "is_parent":True,  "default":False, "number":""},
        {"key":"pan_2_1", "analysis_id":"linear_regression",      "label":"Impact of MSMEs on Exports",                "is_parent":False, "default":False, "number":"2.1"},
        {"key":"pan_2_2", "analysis_id":"linear_regression",      "label":"Impact of Investment on GSDP",              "is_parent":False, "default":False, "number":"2.2"},
        {"key":"pan_2_3", "analysis_id":"linear_regression",      "label":"Employment-Growth Relationship",             "is_parent":False, "default":False, "number":"2.3"},
        {"key":"pan_p3",  "analysis_id":"viz_line_chart",         "label":"Visualization",                             "is_parent":True,  "default":False, "number":""},
        {"key":"pan_3_1", "analysis_id":"viz_line_chart",         "label":"Multi-State Trend Lines",                   "is_parent":False, "default":True,  "number":"3.1"},
        {"key":"pan_3_2", "analysis_id":"viz_correlation_heatmap","label":"Heatmaps",                                  "is_parent":False, "default":False, "number":"3.2"},
        {"key":"pan_3_3", "analysis_id":"viz_bar_chart",          "label":"State Comparison Charts",                   "is_parent":False, "default":False, "number":"3.3"},
        {"key":"pan_3_4", "analysis_id":"viz_line_chart",         "label":"Panel Growth Analysis",                     "is_parent":False, "default":False, "number":"3.4"},
    ],

    # ─────────────────────────────────────────────────────────────────────────
    # MIXED — Survey data with both categorical and numeric columns
    # Reference: RaaS_Mixed_Survey_Dataset.xlsx
    # Nominal columns: Gender, State, Employment_Type
    # Ordinal columns: Education_Level, Income_Category, Customer_Satisfaction
    # Continuous columns: Age_Years, Monthly_Income_INR, Monthly_Expenditure_INR,
    #                     Productivity_Score, Purchase_Amount_INR
    # Tests from file (exact):
    #   Descriptive Statistics, Summary Statistics, Frequency Tables, Cross Tabulation,
    #   Chi-Square Test, Independent t-Test, ANOVA, Linear Regression,
    #   Logistic Regression (after creating binary target), Quantile Regression,
    #   Correlation Analysis, Histograms, Box Plots, Scatter Plots, Heatmaps
    # ─────────────────────────────────────────────────────────────────────────
    "Mixed": [
        {"key":"mix_p1",  "analysis_id":"descriptive_statistics", "label":"Descriptive Statistics",                    "is_parent":True,  "default":False, "number":""},
        {"key":"mix_1_1", "analysis_id":"descriptive_statistics", "label":"Descriptive Statistics",                    "is_parent":False, "default":True,  "number":"1.1"},
        {"key":"mix_1_2", "analysis_id":"summary_statistics_uae", "label":"Summary Statistics",                        "is_parent":False, "default":True,  "number":"1.2"},
        {"key":"mix_1_3", "analysis_id":"summary_statistics_uae", "label":"Frequency Tables",                          "is_parent":False, "default":True,  "number":"1.3"},
        {"key":"mix_1_4", "analysis_id":"summary_statistics_uae", "label":"Cross Tabulation",                          "is_parent":False, "default":False, "number":"1.4"},
        {"key":"mix_p2",  "analysis_id":"chi_square",             "label":"Hypothesis Testing",                        "is_parent":True,  "default":False, "number":""},
        {"key":"mix_2_1", "analysis_id":"chi_square",             "label":"Chi-Square Test",                           "is_parent":False, "default":False, "number":"2.1"},
        {"key":"mix_2_2", "analysis_id":"independent_ttest",      "label":"Independent t-Test",                        "is_parent":False, "default":False, "number":"2.2"},
        {"key":"mix_2_3", "analysis_id":"anova",                  "label":"ANOVA",                                     "is_parent":False, "default":False, "number":"2.3"},
        {"key":"mix_p3",  "analysis_id":"linear_regression",      "label":"Regression Analysis",                       "is_parent":True,  "default":False, "number":""},
        {"key":"mix_3_1", "analysis_id":"linear_regression",      "label":"Linear Regression",                         "is_parent":False, "default":False, "number":"3.1"},
        {"key":"mix_3_2", "analysis_id":"logistic_regression",    "label":"Logistic Regression (after binary target)", "is_parent":False, "default":False, "number":"3.2"},
        {"key":"mix_3_3", "analysis_id":"quantile_regression",    "label":"Quantile Regression",                       "is_parent":False, "default":False, "number":"3.3"},
        {"key":"mix_3_4", "analysis_id":"viz_correlation_heatmap","label":"Correlation Analysis",                      "is_parent":False, "default":False, "number":"3.4"},
        {"key":"mix_p4",  "analysis_id":"viz_histogram",          "label":"Visualization",                             "is_parent":True,  "default":False, "number":""},
        {"key":"mix_4_1", "analysis_id":"viz_histogram",          "label":"Histograms",                                "is_parent":False, "default":True,  "number":"4.1"},
        {"key":"mix_4_2", "analysis_id":"viz_boxplot",            "label":"Box Plots",                                 "is_parent":False, "default":True,  "number":"4.2"},
        {"key":"mix_4_3", "analysis_id":"viz_scatter",            "label":"Scatter Plots",                             "is_parent":False, "default":False, "number":"4.3"},
        {"key":"mix_4_4", "analysis_id":"viz_correlation_heatmap","label":"Heatmaps",                                  "is_parent":False, "default":False, "number":"4.4"},
        {"key":"mix_4_5", "analysis_id":"viz_bar_chart",          "label":"Bar Charts",                                "is_parent":False, "default":True,  "number":"4.5"},
    ],
}

_TYPE_INFO = {
    "Nominal":    ("Nominal / Categorical Data",   "Unordered categories (Gender, State, Industry, Blood Group)"),
    "Ordinal":    ("Ordinal Data",                 "Ordered categories (Education Level, Satisfaction Rating, Performance)"),
    "Binary":     ("Binary Data",                  "Yes/No, True/False columns (Employed, Owns House, Loan Defaulted)"),
    "Continuous": ("Continuous Numerical Data",    "Measured numeric values (Income, Age, Height, Productivity Score)"),
    "Discrete":   ("Discrete Numerical Data",      "Countable integers (Number of Children, Employees, Monthly Orders)"),
    "TimeSeries": ("Time Series Data",             "Sequential observations over time (Monthly Sales, Inflation Rate)"),
    "Panel":      ("Panel Data",                   "Entities observed over multiple time periods (States × Years)"),
    "Mixed":      ("Mixed / Survey Data",          "Mix of nominal, ordinal and continuous variables (survey datasets)"),
}


def _detect_data_type(columns_meta: list) -> str:
    """Detect data type from columns_meta. Priority: Panel > TimeSeries > Binary > Nominal > Ordinal > Discrete > Continuous > Mixed"""
    if not columns_meta:
        return "Mixed"

    numeric = [c for c in columns_meta if c.get('python_type') in ('integer', 'float')]
    text    = [c for c in columns_meta if c.get('python_type') == 'string']
    dates   = [c for c in columns_meta if c.get('python_type') in ('datetime', 'date_string')]

    non_id_num  = [c for c in numeric if 'id' not in c.get('name','').lower() and 'respondent' not in c.get('name','').lower()]
    non_id_text = [c for c in text    if 'id' not in c.get('name','').lower() and 'respondent' not in c.get('name','').lower()]

    names_set = set(c.get('name','').lower() for c in columns_meta)
    joined    = ' '.join(names_set)

    # 1. Panel
    has_entity = any(n in names_set for n in ['state','country','region','district','province'])
    has_year   = 'year' in names_set or any(
        c.get('python_type') == 'integer' and c.get('name','').lower() in ('year','yr')
        for c in columns_meta
    )
    if has_entity and has_year and len(non_id_num) >= 3:
        return "Panel"

    # 2. TimeSeries
    # A real date/time column present:
    has_real_date = len(dates) > 0
    has_time_name = any(c.get('name','').lower() in ('month','date','week','quarter','period','time','day','year_month','month_year')
                        for c in columns_meta)
    has_time = has_real_date or has_time_name

    # 2a. Pure time series: a date + numeric measures, at most 1 category column
    if has_time and len(non_id_num) >= 2 and len(non_id_text) <= 1:
        return "TimeSeries"

    # 2b. Time series WITH categories (e.g. a Sales Report: Date + Customer + Product
    #     + Qty/Rate/Total). If there's a genuine DATE column and at least 2 numeric
    #     measures to track over time, treat it as TimeSeries even when a few
    #     categorical label columns are present.
    if has_real_date and len(non_id_num) >= 2:
        return "TimeSeries"

    # 3. Binary
    binary_hit, text_with_top = 0, 0
    for c in non_id_text:
        top = c.get('top_values', [])
        if not top:
            continue
        text_with_top += 1
        vals = {str(v.get('value','')).strip().lower() for v in top}
        if vals and vals.issubset({'yes','no','true','false','1','0','y','n','pass','fail','active','inactive'}):
            binary_hit += 1
    if text_with_top >= 2 and binary_hit / text_with_top >= 0.5:
        return "Binary"

    # 4. Nominal
    if len(non_id_text) >= 2 and len(non_id_num) <= 1 and not dates:
        ordinal_kw = ['level','rating','rank','grade','satisfaction','performance','frequency','stage','priority','tier']
        if any(kw in joined for kw in ordinal_kw):
            return "Ordinal"
        return "Nominal"

    # 5. Ordinal
    if len(non_id_text) >= 1 and len(non_id_num) <= 2 and not dates:
        ordinal_kw = ['level','rating','rank','grade','satisfaction','performance','frequency','stage','priority']
        if any(kw in joined for kw in ordinal_kw):
            return "Ordinal"
        if len(non_id_num) == 0:
            return "Nominal"

    # 6. Discrete / Continuous
    if len(non_id_text) == 0 and len(non_id_num) > 0:
        if all(c.get('python_type') == 'integer' for c in non_id_num):
            return "Discrete"
        return "Continuous"

    return "Mixed"


def _build_smart_catalog(columns_meta: list) -> dict:
    """
    Build the hierarchical catalog the frontend needs.
    Returns:
      detected_type, type_label, type_description,
      numeric_columns, categorical_columns, date_columns, all_columns,
      items: [ {key, analysis_id, label, is_parent, default, number, premium} ]
    """
    dtype = _detect_data_type(columns_meta)
    label, desc = _TYPE_INFO.get(dtype, ("Mixed Data", "Mixed variable types"))
    items = _CATALOG.get(dtype, _CATALOG["Mixed"])

    # Mark premium items
    result_items = []
    for item in items:
        entry = dict(item)
        entry['premium'] = entry['analysis_id'] in PREMIUM_ANALYSES
        result_items.append(entry)

    # Build column lists
    numeric_cols = [c['name'] for c in columns_meta
                    if c.get('python_type') in ('integer','float')
                    and 'id' not in c.get('name','').lower()
                    and 'respondent' not in c.get('name','').lower()]
    cat_cols     = [c['name'] for c in columns_meta
                    if c.get('python_type') == 'string'
                    and 'id' not in c.get('name','').lower()
                    and 'respondent' not in c.get('name','').lower()]
    date_cols    = [c['name'] for c in columns_meta
                    if c.get('python_type') in ('datetime','date_string')]
    all_cols     = [c['name'] for c in columns_meta]

    return {
        'detected_type':       dtype,
        'type_label':          label,
        'type_description':    desc,
        'numeric_columns':     numeric_cols,
        'categorical_columns': cat_cols,
        'date_columns':        date_cols,
        'all_columns':         all_cols,
        'items':               result_items,   # flat list with is_parent flag
    }


# ── Routes ─────────────────────────────────────────────────────────────────

@universal_bp.route('/catalog', methods=['GET'])
@jwt_required()
def catalog():
    return jsonify(get_catalog()), 200


@universal_bp.route('/smart-catalog/<int:file_id>', methods=['GET'])
@jwt_required()
def smart_catalog(file_id):
    identity = get_jwt_identity()
    excel_file = ExcelFile.query.filter_by(id=file_id, user_id=int(identity)).first()
    if not excel_file:
        return jsonify({'error': 'File not found'}), 404

    columns_meta = json.loads(excel_file.columns_meta or '[]')
    result       = _build_smart_catalog(columns_meta)
    return jsonify(result), 200


@universal_bp.route('/suggest/<int:file_id>', methods=['GET'])
@jwt_required()
def suggest(file_id):
    identity = get_jwt_identity()
    excel_file = ExcelFile.query.filter_by(id=file_id, user_id=int(identity)).first()
    if not excel_file:
        return jsonify({'error': 'File not found'}), 404

    columns_meta = json.loads(excel_file.columns_meta or '[]')
    result = suggest_analyses(columns_meta)
    return jsonify(result), 200


@universal_bp.route('/run', methods=['POST'])
@jwt_required()
def run():
    identity = get_jwt_identity()
    user     = User.query.get(int(identity))
    if not user:
        return jsonify({'error': 'User not found'}), 404

    data          = request.get_json() or {}
    file_id       = data.get('file_id')
    analysis_type = data.get('analysis_type')   # the analysis_id (backend function name)
    parameters    = data.get('parameters') or {}

    if not file_id or not analysis_type:
        return jsonify({'error': 'file_id and analysis_type are required'}), 400

    excel_file = ExcelFile.query.filter_by(id=file_id, user_id=user.id).first()
    if not excel_file:
        return jsonify({'error': 'File not found'}), 404
    if excel_file.status != 'ready':
        return jsonify({'error': 'File is not ready for analysis'}), 400

    is_premium = analysis_type in PREMIUM_ANALYSES

    # Every analysis (premium or standard) consumes 1 credit, regardless of plan.
    # Block the run BEFORE it executes if the user has no credits left.
    if user.download_credits <= 0:
        return jsonify({
            'error': 'You have no download credits remaining. Please upgrade your plan or buy more credits.',
            'upgrade_required': True,
            'credits_remaining': user.download_credits,
        }), 403

    df = load_dataframe(excel_file)
    if df.empty:
        return jsonify({'error': 'Could not read data from this file'}), 400

    result = run_universal_analysis(df, analysis_type, parameters)
    if 'error' in result and len(result) == 1:
        return jsonify({'error': result['error']}), 400

    label    = result.get('type', analysis_type).replace('_', ' ').title()
    analysis = Analysis(
        user_id=user.id,
        file_id=file_id,
        analysis_type=f"uae_{analysis_type}",
        title=f"{label} — {excel_file.original_name}",
        prompt=json.dumps(parameters),
        result=json.dumps(result, default=str),
        ai_narrative=None,
        status='done' if 'error' not in result else 'error',
        is_premium=is_premium,
    )
    db.session.add(analysis)
    # Deduct 1 credit for every successfully completed analysis (all plans)
    if 'error' not in result:
        user.download_credits = max(0, user.download_credits - 1)
    db.session.commit()

    return jsonify({
        'analysis': analysis.to_dict(),
        'result': result,
        'credits_remaining': user.download_credits,
    }), 200


@universal_bp.route('/history/<int:file_id>', methods=['GET'])
@jwt_required()
def history(file_id):
    identity = get_jwt_identity()
    analyses = Analysis.query.filter(
        Analysis.user_id == int(identity),
        Analysis.file_id == file_id,
        Analysis.analysis_type.like('uae_%'),
    ).order_by(Analysis.created_at.desc()).all()
    return jsonify({'analyses': [a.to_dict() for a in analyses]}), 200


# Backward-compat alias
get_smart_catalog = _build_smart_catalog