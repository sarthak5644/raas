"""
Authentication Routes - Registration, Login, JWT management
"""
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import (
    create_access_token, create_refresh_token, 
    jwt_required, get_jwt_identity, get_jwt
)
from flask_bcrypt import Bcrypt
from datetime import datetime
import re

from database import db, User, AuditLog

auth_bp = Blueprint('auth', __name__)
bcrypt = Bcrypt()

def validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_password(password):
    """Require: 8+ chars, 1 uppercase, 1 lowercase, 1 number, 1 special char"""
    if len(password) < 8:
        return False, "Password must be at least 8 characters"
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r'\d', password):
        return False, "Password must contain at least one number"
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Password must contain at least one special character"
    return True, "Valid"


@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    email = data.get('email', '').strip().lower()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    full_name = data.get('full_name', '').strip()
    phone = data.get('phone', '').strip()
    is_human = data.get('is_human', False)
    
    # Validations
    errors = {}
    if not email:
        errors['email'] = 'Email is required'
    elif not validate_email(email):
        errors['email'] = 'Invalid email format'
    elif User.query.filter_by(email=email).first():
        errors['email'] = 'Email already registered'
    
    if not username:
        errors['username'] = 'Username is required'
    elif len(username) < 3:
        errors['username'] = 'Username must be at least 3 characters'
    elif len(username) > 50:
        errors['username'] = 'Username must be less than 50 characters'
    elif not re.match(r'^[a-zA-Z0-9_]+$', username):
        errors['username'] = 'Username can only contain letters, numbers, underscores'
    elif User.query.filter_by(username=username).first():
        errors['username'] = 'Username already taken'
    
    valid, msg = validate_password(password)
    if not valid:
        errors['password'] = msg

    if full_name and len(full_name) > 50:
        errors['full_name'] = 'Full name must be 50 characters or fewer'

    if phone:
        phone_digits = re.sub(r'\D', '', phone)
        if len(phone_digits) < 10 or len(phone_digits) > 15:
            errors['phone'] = 'Enter a valid phone number (10-15 digits)'

    if not is_human:
        errors['is_human'] = 'Please confirm you are not a robot'

    if errors:
        return jsonify({'error': 'Validation failed', 'details': errors}), 422
    
    # Create user
    hashed = bcrypt.generate_password_hash(password).decode('utf-8')
    user = User(
        email=email,
        username=username,
        password_hash=hashed,
        full_name=full_name,
        phone=phone or None,
        is_verified=True,  # Auto-verify for demo; add email verification in production
        plan='free',
        download_credits=3  # Free credits on signup
    )
    db.session.add(user)
    db.session.commit()
    
    # Audit log
    log = AuditLog(
        user_id=user.id,
        action='register',
        resource_type='user',
        resource_id=user.id,
        ip_address=request.remote_addr,
        user_agent=request.headers.get('User-Agent', '')[:500]
    )
    db.session.add(log)
    db.session.commit()
    
    access_token = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))
    
    return jsonify({
        'message': 'Registration successful! Welcome to Excel Analytics Pro.',
        'user': user.to_dict(),
        'access_token': access_token,
        'refresh_token': refresh_token,
    }), 201


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    identifier = data.get('email', '').strip().lower()
    password = data.get('password', '')
    
    if not identifier or not password:
        return jsonify({'error': 'Email and password are required'}), 400
    
    # Find user by email or username
    user = User.query.filter(
        (User.email == identifier) | (User.username == identifier)
    ).first()
    
    if not user:
        return jsonify({'error': 'Invalid credentials'}), 401
    
    if not user.is_active:
        return jsonify({'error': 'Account has been deactivated. Contact support.'}), 403
    
    if not bcrypt.check_password_hash(user.password_hash, password):
        return jsonify({'error': 'Invalid credentials'}), 401
    
    user.last_login = datetime.utcnow()
    db.session.commit()
    
    log = AuditLog(
        user_id=user.id,
        action='login',
        resource_type='user',
        resource_id=user.id,
        ip_address=request.remote_addr,
        user_agent=request.headers.get('User-Agent', '')[:500]
    )
    db.session.add(log)
    db.session.commit()
    
    access_token = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))
    
    return jsonify({
        'message': 'Login successful',
        'user': user.to_dict(),
        'access_token': access_token,
        'refresh_token': refresh_token,
    }), 200


@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    identity = get_jwt_identity()
    user = User.query.get(int(identity))
    if not user or not user.is_active:
        return jsonify({'error': 'User not found'}), 404
    access_token = create_access_token(identity=identity)
    return jsonify({'access_token': access_token}), 200


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_me():
    identity = get_jwt_identity()
    user = User.query.get(int(identity))
    if not user:
        return jsonify({'error': 'User not found'}), 404
    return jsonify({'user': user.to_dict()}), 200


@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    identity = get_jwt_identity()
    log = AuditLog(
        user_id=int(identity),
        action='logout',
        resource_type='user',
        ip_address=request.remote_addr,
    )
    db.session.add(log)
    db.session.commit()
    return jsonify({'message': 'Logged out successfully'}), 200


@auth_bp.route('/change-password', methods=['PUT'])
@jwt_required()
def change_password():
    identity = get_jwt_identity()
    user = User.query.get(int(identity))
    data = request.get_json()
    
    if not bcrypt.check_password_hash(user.password_hash, data.get('current_password', '')):
        return jsonify({'error': 'Current password is incorrect'}), 400
    
    valid, msg = validate_password(data.get('new_password', ''))
    if not valid:
        return jsonify({'error': msg}), 422
    
    user.password_hash = bcrypt.generate_password_hash(data['new_password']).decode('utf-8')
    db.session.commit()
    
    return jsonify({'message': 'Password changed successfully'}), 200
