"""
Excel File Routes - Upload, parsing, metadata retrieval
"""
import os
import json
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename

from database import db, User, ExcelFile, AuditLog
from services.excel_service import allowed_file, secure_filename_custom, parse_excel_file
from services.ai_verification import verify_file_data_type

excel_bp = Blueprint('excel', __name__)


@excel_bp.route('/upload', methods=['POST'])
@jwt_required()
def upload_file():
    identity = get_jwt_identity()
    user = User.query.get(int(identity))
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'File type not allowed. Supported: xlsx, xls, csv, xlsm, xlsb'}), 400
    
    # Check file size (50MB limit)
    file.seek(0, 2)
    file_size = file.tell()
    file.seek(0)
    
    if file_size > 50 * 1024 * 1024:
        return jsonify({'error': 'File too large. Maximum size is 50MB'}), 413
    
    if file_size == 0:
        return jsonify({'error': 'File is empty'}), 400
    
    # Check user upload limits based on plan
    file_count = ExcelFile.query.filter_by(user_id=user.id).count()
    limits = {'free': 5, 'daily': 10, 'weekly': 40, 'monthly': 150, 'yearly': 999}
    limit = limits.get(user.plan, 5)
    
    if file_count >= limit:
        return jsonify({
            'error': f'Upload limit reached for {user.plan} plan ({limit} files). Please upgrade.',
            'upgrade_required': True
        }), 403
    
    # Save file
    original_name = file.filename
    file_ext = original_name.rsplit('.', 1)[1].lower() if '.' in original_name else 'xlsx'
    stored_name = secure_filename_custom(original_name)
    upload_folder = current_app.config['UPLOAD_FOLDER']
    file_path = os.path.join(upload_folder, stored_name)
    
    file.save(file_path)
    
    # Create DB record
    excel_file = ExcelFile(
        user_id=user.id,
        original_name=original_name,
        stored_name=stored_name,
        file_path=file_path,
        file_size=file_size,
        file_type=file_ext,
        status='processing'
    )
    db.session.add(excel_file)
    db.session.commit()
    
    # Parse file
    try:
        parse_result = parse_excel_file(file_path, file_ext)
        
        if parse_result['success']:
            excel_file.sheet_count = parse_result['sheet_count']
            excel_file.total_rows = parse_result['total_rows']
            excel_file.total_cols = parse_result['total_cols']
            excel_file.total_cells = parse_result['total_cells']
            excel_file.missing_values = parse_result['missing_values']
            excel_file.duplicate_rows = parse_result['duplicate_rows']
            excel_file.data_quality_score = parse_result['data_quality_score']
            excel_file.columns_meta = json.dumps(parse_result['columns_meta'])
            excel_file.sheets_meta = json.dumps(parse_result['sheets'])
            excel_file.file_insights = json.dumps(parse_result['insights'])
            excel_file.recommended_analyses = json.dumps(parse_result['recommended_analyses'])
            excel_file.status = 'ready'

            # ── Detect data type + verify it (AI or local fallback) ────
            try:
                from datetime import datetime as _dt
                from routes.universal_analysis import _detect_data_type
                detected = _detect_data_type(parse_result['columns_meta'])
                excel_file.detected_data_type = detected

                verification = verify_file_data_type(
                    detected_type=detected,
                    columns_meta=parse_result['columns_meta'],
                    file_name=original_name,
                    use_ai=True,
                )
                excel_file.ai_verified = verification['verified']
                excel_file.ai_verification_method = verification['method']
                excel_file.ai_verification_notes = verification['notes']
                excel_file.ai_verified_at = _dt.utcnow()
            except Exception as verify_err:
                # Verification failure should never block the upload itself
                excel_file.ai_verified = None
                excel_file.ai_verification_notes = f"Verification skipped: {str(verify_err)[:150]}"
        else:
            excel_file.status = 'error'
            excel_file.error_message = parse_result.get('error', 'Unknown error')
    except Exception as e:
        excel_file.status = 'error'
        excel_file.error_message = str(e)
    
    db.session.commit()
    
    # Audit log
    log = AuditLog(
        user_id=user.id,
        action='upload_file',
        resource_type='excel_file',
        resource_id=excel_file.id,
        ip_address=request.remote_addr,
        details=json.dumps({'filename': original_name, 'size': file_size})
    )
    db.session.add(log)
    db.session.commit()
    
    return jsonify({
        'message': 'File uploaded and analyzed successfully',
        'file': excel_file.to_dict()
    }), 201


@excel_bp.route('/files', methods=['GET'])
@jwt_required()
def get_files():
    identity = get_jwt_identity()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    files = ExcelFile.query.filter_by(user_id=int(identity))\
        .order_by(ExcelFile.created_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'files': [f.to_dict() for f in files.items],
        'total': files.total,
        'pages': files.pages,
        'current_page': files.page
    }), 200


@excel_bp.route('/files/<int:file_id>', methods=['GET'])
@jwt_required()
def get_file(file_id):
    identity = get_jwt_identity()
    excel_file = ExcelFile.query.filter_by(id=file_id, user_id=int(identity)).first()
    
    if not excel_file:
        return jsonify({'error': 'File not found'}), 404
    
    return jsonify({'file': excel_file.to_dict()}), 200


@excel_bp.route('/files/<int:file_id>', methods=['DELETE'])
@jwt_required()
def delete_file(file_id):
    identity = get_jwt_identity()
    excel_file = ExcelFile.query.filter_by(id=file_id, user_id=int(identity)).first()
    
    if not excel_file:
        return jsonify({'error': 'File not found'}), 404
    
    # Delete physical file
    if os.path.exists(excel_file.file_path):
        os.remove(excel_file.file_path)
    
    db.session.delete(excel_file)
    db.session.commit()
    
    return jsonify({'message': 'File deleted successfully'}), 200


@excel_bp.route('/files/<int:file_id>/preview', methods=['GET'])
@jwt_required()
def preview_file(file_id):
    """Get first 100 rows of data for preview."""
    import pandas as pd
    
    identity = get_jwt_identity()
    excel_file = ExcelFile.query.filter_by(id=file_id, user_id=int(identity)).first()
    
    if not excel_file:
        return jsonify({'error': 'File not found'}), 404
    
    if excel_file.status != 'ready':
        return jsonify({'error': 'File not ready for preview'}), 400
    
    try:
        if excel_file.file_type == 'csv':
            df = pd.read_csv(excel_file.file_path, nrows=100)
        else:
            df = pd.read_excel(excel_file.file_path, nrows=100)
        
        df = df.fillna('')
        
        return jsonify({
            'columns': list(df.columns),
            'rows': df.values.tolist(),
            'total_preview_rows': len(df)
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
