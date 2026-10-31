"""
Analysis Routes - AI-powered Excel analysis using Gemini
"""
import os
import json
import pandas as pd
import numpy as np
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from database import db, User, ExcelFile, Analysis, AuditLog

analysis_bp = Blueprint('analysis', __name__)


def get_gemini_client():
    """Initialize Gemini AI client using the new google-genai SDK."""
    try:
        from google import genai
        api_key = os.getenv('GEMINI_API_KEY', '').strip()
        if not api_key:
            return None
        return genai.Client(api_key=api_key)
    except ImportError:
        return None


def load_dataframe(excel_file: ExcelFile, sheet_name=None) -> pd.DataFrame:
    """Load a dataframe from an excel file.

    If sheet_name is provided (Excel files only), that specific sheet is loaded.
    Otherwise defaults to the first sheet (sheet index 0) — same as before.
    """
    if excel_file.file_type == 'csv':
        for enc in ['utf-8', 'latin-1', 'iso-8859-1']:
            try:
                return pd.read_csv(excel_file.file_path, encoding=enc, low_memory=False)
            except:
                continue
    else:
        return pd.read_excel(excel_file.file_path, sheet_name=sheet_name if sheet_name is not None else 0)
    return pd.DataFrame()


def run_summary_statistics(df: pd.DataFrame) -> dict:
    numeric_df = df.select_dtypes(include=[np.number])
    if numeric_df.empty:
        return {'error': 'No numeric columns found'}
    
    desc = numeric_df.describe().round(4)
    
    charts = []
    for col in numeric_df.columns[:6]:
        values = numeric_df[col].dropna().tolist()
        if values:
            # Create histogram buckets
            mn, mx = min(values), max(values)
            if mn != mx:
                bucket_size = (mx - mn) / 10
                buckets = {}
                for v in values:
                    bucket = int((v - mn) / bucket_size)
                    bucket = min(bucket, 9)
                    label = f"{round(mn + bucket * bucket_size, 2)}"
                    buckets[label] = buckets.get(label, 0) + 1
                charts.append({
                    'type': 'bar',
                    'title': f'Distribution: {col}',
                    'data': [{'x': k, 'y': v} for k, v in buckets.items()]
                })
    
    return {
        'type': 'summary_statistics',
        'columns': list(numeric_df.columns),
        'stats': {
            col: {
                'count': desc.loc['count', col] if col in desc.columns else 0,
                'mean': desc.loc['mean', col] if col in desc.columns else 0,
                'std': desc.loc['std', col] if col in desc.columns else 0,
                'min': desc.loc['min', col] if col in desc.columns else 0,
                'q25': desc.loc['25%', col] if col in desc.columns else 0,
                'median': desc.loc['50%', col] if col in desc.columns else 0,
                'q75': desc.loc['75%', col] if col in desc.columns else 0,
                'max': desc.loc['max', col] if col in desc.columns else 0,
            } for col in numeric_df.columns
        },
        'charts': charts
    }


def run_correlation_matrix(df: pd.DataFrame) -> dict:
    numeric_df = df.select_dtypes(include=[np.number])
    if numeric_df.shape[1] < 2:
        return {'error': 'Need at least 2 numeric columns for correlation'}
    
    corr = numeric_df.corr().round(4)
    cols = list(corr.columns[:12])  # limit to 12 cols
    corr = corr.loc[cols, cols]
    
    # Find strong correlations
    strong_corrs = []
    for i, c1 in enumerate(cols):
        for j, c2 in enumerate(cols):
            if i < j:
                val = corr.loc[c1, c2]
                if abs(val) > 0.5:
                    strong_corrs.append({'col1': c1, 'col2': c2, 'correlation': float(val)})
    
    strong_corrs.sort(key=lambda x: abs(x['correlation']), reverse=True)
    
    return {
        'type': 'correlation_matrix',
        'columns': cols,
        'matrix': corr.values.tolist(),
        'strong_correlations': strong_corrs[:10]
    }


def run_distribution_analysis(df: pd.DataFrame) -> dict:
    numeric_df = df.select_dtypes(include=[np.number])
    charts = []
    
    for col in numeric_df.columns[:6]:
        series = numeric_df[col].dropna()
        if len(series) == 0:
            continue
        
        q1 = float(series.quantile(0.25))
        q3 = float(series.quantile(0.75))
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        outliers = series[(series < lower) | (series > upper)].tolist()
        
        charts.append({
            'column': col,
            'type': 'box',
            'min': float(series.min()),
            'q1': q1,
            'median': float(series.median()),
            'q3': q3,
            'max': float(series.max()),
            'mean': float(series.mean()),
            'std': float(series.std()),
            'outliers_count': len(outliers),
            'outliers_sample': outliers[:10],
            'skewness': float(series.skew()),
            'kurtosis': float(series.kurtosis()),
        })
    
    return {
        'type': 'distribution',
        'columns_analyzed': [c['column'] for c in charts],
        'distributions': charts
    }


def run_category_analysis(df: pd.DataFrame) -> dict:
    text_cols = df.select_dtypes(include=['object']).columns.tolist()
    results = []
    
    for col in text_cols[:6]:
        series = df[col].dropna()
        vc = series.value_counts()
        total = len(series)
        
        results.append({
            'column': col,
            'unique_values': int(series.nunique()),
            'total_values': total,
            'top_10': [
                {'value': str(k), 'count': int(v), 'pct': round(v/total*100, 2)}
                for k, v in vc.head(10).items()
            ]
        })
    
    return {
        'type': 'category_analysis',
        'columns': results
    }


def run_data_quality(df: pd.DataFrame, file_meta: dict) -> dict:
    total_cells = df.shape[0] * df.shape[1]
    missing_per_col = df.isna().sum()
    missing_total = int(missing_per_col.sum())
    dup_rows = int(df.duplicated().sum())
    
    col_quality = []
    for col in df.columns:
        series = df[col]
        missing = int(series.isna().sum())
        col_quality.append({
            'column': col,
            'missing': missing,
            'missing_pct': round(missing / len(df) * 100, 2),
            'unique': int(series.nunique()),
            'dtype': str(series.dtype),
        })
    
    return {
        'type': 'data_quality',
        'overall_score': file_meta.get('data_quality_score', 0),
        'total_cells': total_cells,
        'missing_cells': missing_total,
        'missing_pct': round(missing_total / total_cells * 100, 2) if total_cells > 0 else 0,
        'duplicate_rows': dup_rows,
        'duplicate_pct': round(dup_rows / len(df) * 100, 2) if len(df) > 0 else 0,
        'columns_quality': col_quality,
        'empty_columns': [c['column'] for c in col_quality if c['missing_pct'] == 100],
        'high_missing_columns': [c['column'] for c in col_quality if 30 <= c['missing_pct'] < 100],
    }


async def call_gemini_ai(model, prompt: str, data_summary: str) -> str:
    """Call Gemini AI for narrative analysis."""
    full_prompt = f"""
You are a professional data analyst. Analyze the following Excel/CSV data and provide actionable insights.

Data Summary:
{data_summary}

User Question/Task:
{prompt}

Provide:
1. Key findings (3-5 bullet points)
2. Data patterns and trends
3. Anomalies or concerns
4. Actionable recommendations (3-5 bullets)
5. What to do next

Be concise, professional, and data-driven. Use specific numbers from the data.
Format with clear sections and bullet points.
"""
    try:
        response = model.models.generate_content(
            model='gemini-2.5-flash',
            contents=full_prompt
        )
        return response.text
    except Exception as e:
        return f"AI analysis temporarily unavailable: {str(e)}"


@analysis_bp.route('/run', methods=['POST'])
@jwt_required()
def run_analysis():
    identity = get_jwt_identity()
    user = User.query.get(int(identity))
    data = request.get_json()
    
    file_id = data.get('file_id')
    analysis_type = data.get('analysis_type', 'summary_statistics')
    prompt = data.get('prompt', '')
    sheet_name = data.get('sheet_name')  # optional — None = first sheet (unchanged default)
    
    if not file_id:
        return jsonify({'error': 'file_id is required'}), 400
    
    excel_file = ExcelFile.query.filter_by(id=file_id, user_id=user.id).first()
    if not excel_file:
        return jsonify({'error': 'File not found'}), 404
    
    if excel_file.status != 'ready':
        return jsonify({'error': 'File is not ready for analysis'}), 400
    
    # Premium analysis types are tagged for reporting, but EVERY analysis
    # (premium or standard) consumes 1 credit regardless of plan.
    premium_types = ['correlation_matrix', 'time_series', 'scatter_analysis', 'ai_insights']
    is_premium = analysis_type in premium_types

    if user.download_credits <= 0:
        return jsonify({
            'error': 'You have no download credits remaining. Please upgrade your plan or buy more credits.',
            'upgrade_required': True,
            'analysis_type': analysis_type,
            'credits_remaining': user.download_credits,
        }), 403
    
    try:
        df = load_dataframe(excel_file, sheet_name)
        result = {}
        ai_narrative = None
        
        if analysis_type == 'summary_statistics':
            result = run_summary_statistics(df)
        elif analysis_type == 'correlation_matrix':
            result = run_correlation_matrix(df)
        elif analysis_type == 'distribution':
            result = run_distribution_analysis(df)
        elif analysis_type == 'category_analysis':
            result = run_category_analysis(df)
        elif analysis_type == 'data_quality':
            result = run_data_quality(df, excel_file.to_dict())
        elif analysis_type == 'ai_insights':
            # Run all analyses then get AI narrative
            summary = run_summary_statistics(df)
            quality = run_data_quality(df, excel_file.to_dict())
            
            data_summary = f"""
File: {excel_file.original_name}
Rows: {excel_file.total_rows}, Columns: {excel_file.total_cols}
Quality Score: {excel_file.data_quality_score}/100
Missing Values: {excel_file.missing_values}
Duplicate Rows: {excel_file.duplicate_rows}

Column Summary:
{json.dumps(json.loads(excel_file.columns_meta or '[]')[:10], indent=2)}

Statistics:
{json.dumps(summary.get('stats', {}), indent=2)[:2000]}
"""
            model = get_gemini_client()
            if model:
                try:
                    response = model.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=f"Analyze this data professionally:\n{data_summary}\n\nUser question: {prompt or 'Provide comprehensive insights'}"
                    )
                    ai_narrative = response.text
                except Exception as e:
                    ai_narrative = f"AI analysis temporarily unavailable: {str(e)}"
            else:
                ai_narrative = "Gemini AI is not configured. Please add GEMINI_API_KEY to your .env file."
            
            result = {
                'type': 'ai_insights',
                'summary': summary,
                'quality': quality,
            }
        else:
            return jsonify({'error': f'Unknown analysis type: {analysis_type}'}), 400
        
        # Save analysis record
        analysis = Analysis(
            user_id=user.id,
            file_id=file_id,
            analysis_type=analysis_type,
            title=f"{analysis_type.replace('_', ' ').title()} - {excel_file.original_name}",
            prompt=prompt,
            result=json.dumps(result, default=str),
            ai_narrative=ai_narrative,
            status='done',
            is_premium=is_premium
        )
        db.session.add(analysis)
        
        # Deduct 1 credit for every successfully completed analysis (all plans)
        user.download_credits = max(0, user.download_credits - 1)

        db.session.commit()
        
        return jsonify({
            'analysis': analysis.to_dict(),
            'ai_narrative': ai_narrative,
            'credits_remaining': user.download_credits,
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@analysis_bp.route('/history/<int:file_id>', methods=['GET'])
@jwt_required()
def get_analysis_history(file_id):
    identity = get_jwt_identity()
    analyses = Analysis.query.filter_by(
        user_id=int(identity), file_id=file_id
    ).order_by(Analysis.created_at.desc()).all()
    
    return jsonify({'analyses': [a.to_dict() for a in analyses]}), 200


@analysis_bp.route('/<int:analysis_id>', methods=['GET'])
@jwt_required()
def get_analysis(analysis_id):
    identity = get_jwt_identity()
    analysis = Analysis.query.filter_by(
        id=analysis_id, user_id=int(identity)
    ).first()
    
    if not analysis:
        return jsonify({'error': 'Analysis not found'}), 404
    
    return jsonify({'analysis': analysis.to_dict()}), 200