"""
User Profile Routes
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from database import db, User, Analysis, ExcelFile, Payment

user_bp = Blueprint('user', __name__)


@user_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    identity = get_jwt_identity()
    user = User.query.get(int(identity))
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    file_count = ExcelFile.query.filter_by(user_id=user.id).count()
    analysis_count = Analysis.query.filter_by(user_id=user.id).count()
    
    return jsonify({
        'user': user.to_dict(),
        'stats': {
            'files_uploaded': file_count,
            'analyses_run': analysis_count,
        }
    }), 200


@user_bp.route('/profile', methods=['PUT'])
@jwt_required()
def update_profile():
    identity = get_jwt_identity()
    user = User.query.get(int(identity))
    data = request.get_json()
    
    if 'full_name' in data:
        user.full_name = data['full_name']
    
    db.session.commit()
    return jsonify({'user': user.to_dict(), 'message': 'Profile updated'}), 200


@user_bp.route('/dashboard-stats', methods=['GET'])
@jwt_required()
def dashboard_stats():
    identity = get_jwt_identity()
    user = User.query.get(int(identity))
    
    file_count = ExcelFile.query.filter_by(user_id=user.id).count()
    analysis_count = Analysis.query.filter_by(user_id=user.id).count()
    
    recent_files = ExcelFile.query.filter_by(user_id=user.id)\
        .order_by(ExcelFile.created_at.desc()).limit(5).all()
    
    recent_analyses = Analysis.query.filter_by(user_id=user.id)\
        .order_by(Analysis.created_at.desc()).limit(5).all()
    
    return jsonify({
        'stats': {
            'total_files': file_count,
            'total_analyses': analysis_count,
            'plan': user.plan,
            'credits': user.download_credits,
        },
        'recent_files': [f.to_dict() for f in recent_files],
        'recent_analyses': [a.to_dict() for a in recent_analyses],
    }), 200
