"""
Admin Panel Routes
===================
Separate, locked-down blueprint for platform administrators.
Every route here requires a valid JWT AND user.is_admin == True.

Provides:
  - Admin login (reuses normal auth but checks is_admin)
  - Dashboard summary stats
  - User list + detail + plan/credit management
  - File list with AI/local verification status + manual override
  - Analysis history across all users
  - Payment / subscription history
"""
import os
from datetime import datetime, timedelta
from functools import wraps

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, create_access_token
from flask_bcrypt import Bcrypt

from database import db, User, ExcelFile, Analysis, Payment, AuditLog

admin_bp = Blueprint('admin', __name__)
bcrypt = Bcrypt()


# ── Admin-only guard ────────────────────────────────────────────────────
def admin_required(fn):
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        identity = get_jwt_identity()
        user = User.query.get(int(identity))
        if not user or not user.is_admin:
            return jsonify({'error': 'Admin access required'}), 403
        return fn(*args, **kwargs)
    return wrapper


# ── Login ────────────────────────────────────────────────────────────────
@admin_bp.route('/login', methods=['POST'])
def admin_login():
    data = request.get_json() or {}
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''

    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400

    user = User.query.filter_by(email=email).first()
    if not user or not bcrypt.check_password_hash(user.password_hash, password):
        return jsonify({'error': 'Invalid credentials'}), 401

    if not user.is_admin:
        return jsonify({'error': 'This account does not have admin access'}), 403

    if not user.is_active:
        return jsonify({'error': 'Account is disabled'}), 403

    user.last_login = datetime.utcnow()
    db.session.commit()

    access_token = create_access_token(identity=str(user.id))
    return jsonify({
        'access_token': access_token,
        'user': user.to_dict(),
    }), 200


@admin_bp.route('/me', methods=['GET'])
@admin_required
def admin_me():
    identity = get_jwt_identity()
    user = User.query.get(int(identity))
    return jsonify({'user': user.to_dict()}), 200


# ── Dashboard summary ───────────────────────────────────────────────────
@admin_bp.route('/stats', methods=['GET'])
@admin_required
def stats():
    total_users = User.query.count()
    total_files = ExcelFile.query.count()
    total_analyses = Analysis.query.count()

    files_verified_ai    = ExcelFile.query.filter_by(ai_verified=True, ai_verification_method='ai').count()
    files_verified_local = ExcelFile.query.filter_by(ai_verified=True, ai_verification_method='local').count()
    files_failed_verify  = ExcelFile.query.filter_by(ai_verified=False).count()
    files_pending_verify = ExcelFile.query.filter(ExcelFile.ai_verified.is_(None)).count()

    plan_counts = {}
    for plan in ['free', 'daily', 'weekly', 'monthly', 'yearly']:
        plan_counts[plan] = User.query.filter_by(plan=plan).count()

    total_revenue = db.session.query(db.func.sum(Payment.amount)).filter_by(status='paid').scalar() or 0

    week_ago = datetime.utcnow() - timedelta(days=7)
    new_users_week = User.query.filter(User.created_at >= week_ago).count()
    new_files_week = ExcelFile.query.filter(ExcelFile.created_at >= week_ago).count()

    return jsonify({
        'total_users': total_users,
        'total_files': total_files,
        'total_analyses': total_analyses,
        'verification': {
            'verified_by_ai': files_verified_ai,
            'verified_by_local': files_verified_local,
            'failed_verification': files_failed_verify,
            'pending_verification': files_pending_verify,
        },
        'plan_distribution': plan_counts,
        'total_revenue': float(total_revenue),
        'new_users_this_week': new_users_week,
        'new_files_this_week': new_files_week,
    }), 200


# ── Users ────────────────────────────────────────────────────────────────
@admin_bp.route('/users', methods=['GET'])
@admin_required
def list_users():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    search = request.args.get('search', '').strip()
    plan_filter = request.args.get('plan', '').strip()

    query = User.query
    if search:
        like = f"%{search}%"
        query = query.filter(db.or_(User.email.ilike(like), User.username.ilike(like), User.full_name.ilike(like)))
    if plan_filter:
        query = query.filter_by(plan=plan_filter)

    query = query.order_by(User.created_at.desc())
    total = query.count()
    users = query.offset((page - 1) * per_page).limit(per_page).all()

    result = []
    for u in users:
        d = u.to_dict()
        d['file_count'] = ExcelFile.query.filter_by(user_id=u.id).count()
        d['analysis_count'] = Analysis.query.filter_by(user_id=u.id).count()
        result.append(d)

    return jsonify({
        'users': result,
        'total': total,
        'page': page,
        'per_page': per_page,
        'total_pages': (total + per_page - 1) // per_page,
    }), 200


@admin_bp.route('/users/<int:user_id>', methods=['GET'])
@admin_required
def get_user_detail(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    files = ExcelFile.query.filter_by(user_id=user_id).order_by(ExcelFile.created_at.desc()).all()
    analyses = Analysis.query.filter_by(user_id=user_id).order_by(Analysis.created_at.desc()).limit(20).all()
    payments = Payment.query.filter_by(user_id=user_id).order_by(Payment.created_at.desc()).all()

    return jsonify({
        'user': user.to_dict(),
        'files': [f.to_dict() for f in files],
        'recent_analyses': [a.to_dict() for a in analyses],
        'payments': [p.to_dict() for p in payments],
    }), 200


@admin_bp.route('/users/<int:user_id>', methods=['PATCH'])
@admin_required
def update_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    data = request.get_json() or {}

    if 'plan' in data:
        user.plan = data['plan']
    if 'download_credits' in data:
        user.download_credits = max(0, int(data['download_credits']))
    if 'is_active' in data:
        user.is_active = bool(data['is_active'])
    if 'is_admin' in data:
        user.is_admin = bool(data['is_admin'])
    if 'is_verified' in data:
        user.is_verified = bool(data['is_verified'])

    db.session.commit()
    return jsonify({'user': user.to_dict()}), 200


@admin_bp.route('/users/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    identity = get_jwt_identity()
    if int(identity) == user_id:
        return jsonify({'error': 'You cannot delete your own admin account'}), 400

    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    db.session.delete(user)
    db.session.commit()
    return jsonify({'message': 'User deleted'}), 200


# ── Files (with AI / local verification status) ─────────────────────────
@admin_bp.route('/files', methods=['GET'])
@admin_required
def list_files():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    verified_filter = request.args.get('verified', '').strip()    # 'true' | 'false' | 'pending'
    type_filter = request.args.get('data_type', '').strip()
    search = request.args.get('search', '').strip()

    query = ExcelFile.query
    if search:
        query = query.filter(ExcelFile.original_name.ilike(f"%{search}%"))
    if type_filter:
        query = query.filter_by(detected_data_type=type_filter)
    if verified_filter == 'true':
        query = query.filter_by(ai_verified=True)
    elif verified_filter == 'false':
        query = query.filter_by(ai_verified=False)
    elif verified_filter == 'pending':
        query = query.filter(ExcelFile.ai_verified.is_(None))

    query = query.order_by(ExcelFile.created_at.desc())
    total = query.count()
    files = query.offset((page - 1) * per_page).limit(per_page).all()

    result = []
    for f in files:
        d = f.to_dict()
        owner = User.query.get(f.user_id)
        d['owner_email'] = owner.email if owner else None
        d['owner_username'] = owner.username if owner else None
        result.append(d)

    return jsonify({
        'files': result,
        'total': total,
        'page': page,
        'per_page': per_page,
        'total_pages': (total + per_page - 1) // per_page,
    }), 200


@admin_bp.route('/files/<int:file_id>/reverify', methods=['POST'])
@admin_required
def reverify_file(file_id):
    """Manually re-run AI/local verification for a single file (e.g. after a quota reset)."""
    import json as _json
    from services.ai_verification import verify_file_data_type
    from routes.universal_analysis import _detect_data_type

    excel_file = ExcelFile.query.get(file_id)
    if not excel_file:
        return jsonify({'error': 'File not found'}), 404

    columns_meta = _json.loads(excel_file.columns_meta or '[]')
    detected = _detect_data_type(columns_meta)
    excel_file.detected_data_type = detected

    use_ai = (request.get_json() or {}).get('use_ai', True)
    verification = verify_file_data_type(
        detected_type=detected,
        columns_meta=columns_meta,
        file_name=excel_file.original_name,
        use_ai=use_ai,
    )
    excel_file.ai_verified = verification['verified']
    excel_file.ai_verification_method = verification['method']
    excel_file.ai_verification_notes = verification['notes']
    excel_file.ai_verified_at = datetime.utcnow()
    db.session.commit()

    return jsonify({'file': excel_file.to_dict()}), 200


@admin_bp.route('/files/<int:file_id>/override', methods=['POST'])
@admin_required
def override_verification(file_id):
    """Admin manually marks a file as verified/unverified with their own note."""
    excel_file = ExcelFile.query.get(file_id)
    if not excel_file:
        return jsonify({'error': 'File not found'}), 404

    data = request.get_json() or {}
    excel_file.ai_verified = bool(data.get('verified', True))
    excel_file.ai_verification_method = 'manual'
    excel_file.ai_verification_notes = data.get('notes', 'Manually overridden by admin.')
    excel_file.ai_verified_at = datetime.utcnow()
    db.session.commit()

    return jsonify({'file': excel_file.to_dict()}), 200


# ── Analyses (platform-wide) ─────────────────────────────────────────────
@admin_bp.route('/analyses', methods=['GET'])
@admin_required
def list_analyses():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    query = Analysis.query.order_by(Analysis.created_at.desc())
    total = query.count()
    analyses = query.offset((page - 1) * per_page).limit(per_page).all()

    result = []
    for a in analyses:
        d = a.to_dict()
        owner = User.query.get(a.user_id)
        d['owner_email'] = owner.email if owner else None
        excel_file = ExcelFile.query.get(a.file_id)
        d['file_name'] = excel_file.original_name if excel_file else None
        result.append(d)

    return jsonify({
        'analyses': result,
        'total': total,
        'page': page,
        'per_page': per_page,
        'total_pages': (total + per_page - 1) // per_page,
    }), 200


# ── Payments / subscriptions ──────────────────────────────────────────────
@admin_bp.route('/payments', methods=['GET'])
@admin_required
def list_payments():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    query = Payment.query.order_by(Payment.created_at.desc())
    total = query.count()
    payments = query.offset((page - 1) * per_page).limit(per_page).all()

    result = []
    for p in payments:
        d = p.to_dict()
        owner = User.query.get(p.user_id)
        d['owner_email'] = owner.email if owner else None
        result.append(d)

    return jsonify({
        'payments': result,
        'total': total,
        'page': page,
        'per_page': per_page,
        'total_pages': (total + per_page - 1) // per_page,
    }), 200
