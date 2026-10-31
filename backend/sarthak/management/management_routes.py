"""
Management, Commerce & Business Analytics Routes (RaaS Stage-2, Component 4)
================================================================================
Mirrors sarthak/engineering/engineering_routes.py exactly in structure:
  GET  /api/management/catalog              -> full module/sub-analysis list
  GET  /api/management/suggest/<file_id>     -> column-driven recommendations
  POST /api/management/run                   -> execute one analysis, deduct 1 credit
  GET  /api/management/history/<file_id>     -> past management analyses for a file
  GET  /api/management/history               -> past management analyses (no file)

IMPORTANT: Purely additive — does NOT modify any other routes file.
"""
import json
import pandas as pd

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from database import db, User, ExcelFile, Analysis
from sarthak.management.management_analytics import (
    run_management_analysis, get_management_catalog, PREMIUM_ANALYSES,
    DATA_DRIVEN_ANALYSES, MANAGEMENT_MODULES, suggest_management_analyses,
)

management_bp = Blueprint('management', __name__)


# ── DataFrame loader (reuses the same smart-read logic as Stage-1/Engineering) ─
def load_dataframe(excel_file: ExcelFile, sheet_name: str = None) -> pd.DataFrame:
    try:
        from services.excel_service import _read_sheet_smart, clean_dataframe
        is_csv = (excel_file.file_type == 'csv')
        if is_csv:
            df = _read_sheet_smart(excel_file.file_path, is_csv=True)
        else:
            sn = sheet_name if sheet_name else 0
            df = _read_sheet_smart(excel_file.file_path, sheet_name=sn, is_csv=False)
        return clean_dataframe(df)
    except Exception:
        try:
            if excel_file.file_type == 'csv':
                for enc in ['utf-8', 'latin-1', 'iso-8859-1']:
                    try:
                        return pd.read_csv(excel_file.file_path, encoding=enc, low_memory=False)
                    except Exception:
                        continue
                return pd.DataFrame()
            kwargs = {'sheet_name': sheet_name} if sheet_name else {'sheet_name': 0}
            return pd.read_excel(excel_file.file_path, **kwargs)
        except Exception:
            return pd.DataFrame()


def _analysis_id_to_module_key(analysis_id: str) -> str:
    for mod_key, mod in MANAGEMENT_MODULES.items():
        for item in mod['items']:
            if item['analysis_id'] == analysis_id:
                return mod_key
    return 'Management'


# ── Routes ─────────────────────────────────────────────────────────────────

@management_bp.route('/catalog', methods=['GET'])
@jwt_required()
def catalog():
    """Returns all 8 modules with their sub-analyses and required input fields."""
    return jsonify(get_management_catalog()), 200


@management_bp.route('/suggest/<int:file_id>', methods=['GET'])
@jwt_required()
def suggest(file_id):
    """Column-driven recommendations for this specific file."""
    identity = get_jwt_identity()
    excel_file = ExcelFile.query.filter_by(id=file_id, user_id=int(identity)).first()
    if not excel_file:
        return jsonify({'error': 'File not found'}), 404

    columns_meta = json.loads(excel_file.columns_meta or '[]')
    result = suggest_management_analyses(columns_meta)
    return jsonify(result), 200


@management_bp.route('/run', methods=['POST'])
@jwt_required()
def run():
    identity = get_jwt_identity()
    user = User.query.get(int(identity))
    if not user:
        return jsonify({'error': 'User not found'}), 404

    data = request.get_json() or {}
    analysis_id = data.get('analysis_type') or data.get('analysis_id')
    parameters = data.get('parameters') or {}
    file_id = data.get('file_id')
    sheet_name = data.get('sheet_name')

    if not analysis_id:
        return jsonify({'error': 'analysis_type (analysis_id) is required'}), 400

    is_premium = analysis_id in PREMIUM_ANALYSES
    needs_dataframe = analysis_id in DATA_DRIVEN_ANALYSES

    # Every analysis (premium or standard) consumes 1 credit, regardless of plan.
    if user.download_credits <= 0:
        return jsonify({
            'error': 'You have no download credits remaining. Please upgrade your plan or buy more credits.',
            'upgrade_required': True,
            'credits_remaining': user.download_credits,
        }), 403

    excel_file = None
    df = None

    if needs_dataframe:
        if not file_id:
            return jsonify({'error': f"'{analysis_id}' requires a file_id — this analysis reads columns from an uploaded file"}), 400
        excel_file = ExcelFile.query.filter_by(id=file_id, user_id=user.id).first()
        if not excel_file:
            return jsonify({'error': 'File not found'}), 404
        if excel_file.status != 'ready':
            return jsonify({'error': 'File is not ready for analysis'}), 400
        df = load_dataframe(excel_file, sheet_name)
        if df.empty:
            return jsonify({'error': 'Could not read data from this file'}), 400
    elif file_id:
        # Parameter-only analysis, but a file_id was still passed (e.g. for
        # history grouping) — load it if valid, but don't fail if it isn't.
        excel_file = ExcelFile.query.filter_by(id=file_id, user_id=user.id).first()

    result = run_management_analysis(analysis_id, df, parameters)
    if 'error' in result and len(result) == 1:
        return jsonify({'error': result['error']}), 400

    module_key = _analysis_id_to_module_key(analysis_id)
    label = result.get('type', analysis_id).replace('_', ' ').title()
    title_suffix = f" — {excel_file.original_name}" if excel_file else ""

    analysis = Analysis(
        user_id=user.id,
        file_id=excel_file.id if excel_file else None,
        analysis_type=f"mgmt_{analysis_id}",
        title=f"[{module_key}] {label}{title_suffix}",
        prompt=json.dumps(parameters, default=str),
        result=json.dumps(result, default=str),
        ai_narrative=None,
        status='done',
        is_premium=is_premium,
    )
    db.session.add(analysis)
    user.download_credits = max(0, user.download_credits - 1)
    db.session.commit()

    return jsonify({
        'analysis': analysis.to_dict(),
        'result': result,
        'credits_remaining': user.download_credits,
    }), 200


@management_bp.route('/history/<int:file_id>', methods=['GET'])
@jwt_required()
def history_for_file(file_id):
    identity = get_jwt_identity()
    analyses = Analysis.query.filter(
        Analysis.user_id == int(identity),
        Analysis.file_id == file_id,
        Analysis.analysis_type.like('mgmt_%'),
    ).order_by(Analysis.created_at.desc()).all()
    return jsonify({'analyses': [a.to_dict() for a in analyses]}), 200


@management_bp.route('/history', methods=['GET'])
@jwt_required()
def history_all():
    """For parameter-only modules that aren't tied to an uploaded file."""
    identity = get_jwt_identity()
    analyses = Analysis.query.filter(
        Analysis.user_id == int(identity),
        Analysis.analysis_type.like('mgmt_%'),
    ).order_by(Analysis.created_at.desc()).limit(50).all()
    return jsonify({'analyses': [a.to_dict() for a in analyses]}), 200
