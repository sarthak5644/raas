"""
Excel Analytics Platform - Main Application Entry Point
Professional Industry-Grade System
"""
import os
from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_bcrypt import Bcrypt
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv

from database import db
from routes.auth import auth_bp
from routes.excel import excel_bp
from routes.analysis import analysis_bp
from routes.universal_analysis import universal_bp
from sarthak.engineering.engineering_routes import engineering_bp
from sarthak.management.management_routes import management_bp
from sarthak.environmental.environmental_routes import environmental_bp
from sarthak.health.health_routes import health_bp
from routes.reports import reports_bp
from routes.payment import payment_bp
from routes.user import user_bp
from routes.admin import admin_bp

load_dotenv()

def create_app():
    app = Flask(__name__)
    
    # ─── Configuration ─────────────────────────────────────────────
    import secrets as _secrets
    # Use env secrets in production; generate a strong random one if missing.
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY') or _secrets.token_hex(32)
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY') or _secrets.token_hex(32)
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = 3600  # 1 hour
    app.config['JWT_REFRESH_TOKEN_EXPIRES'] = 2592000  # 30 days
    
    # Database
    db_path = os.path.join(os.path.dirname(__file__), 'database', 'analytics.db')
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
        'DATABASE_URL', f'sqlite:///{db_path}'
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # File Upload
    app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), '..', 'uploads')
    app.config['REPORTS_FOLDER'] = os.path.join(os.path.dirname(__file__), '..', 'reports')
    app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max
    app.config['ALLOWED_EXTENSIONS'] = {'xlsx', 'xls', 'csv', 'xlsm', 'xlsb'}
    
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['REPORTS_FOLDER'], exist_ok=True)

    # Stripe
    app.config['STRIPE_SECRET_KEY'] = os.getenv('STRIPE_SECRET_KEY', '')
    app.config['STRIPE_PUBLISHABLE_KEY'] = os.getenv('STRIPE_PUBLISHABLE_KEY', '')
    
    # Gemini AI
    app.config['GEMINI_API_KEY'] = os.getenv('GEMINI_API_KEY', '')
    
    # ─── Extensions ─────────────────────────────────────────────────
    db.init_app(app)
    JWTManager(app)
    Bcrypt(app)
    # Build the allowed-origins list. NEVER fall back to '*' when
    # supports_credentials is True — that combination is a security hole.
    _allowed_origins = ['http://localhost:3000', 'http://localhost:5173']
    _frontend_url = os.getenv('FRONTEND_URL', '').strip()
    if _frontend_url and _frontend_url != '*':
        _allowed_origins.append(_frontend_url)
    CORS(app,
         origins=_allowed_origins,
         supports_credentials=True,
         allow_headers=['Content-Type', 'Authorization'],
         methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
    
    limiter = Limiter(
        get_remote_address,
        app=app,
        default_limits=["200 per hour", "50 per minute"],
        storage_uri="memory://"
    )
    
    # ─── Blueprints ──────────────────────────────────────────────────
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(excel_bp, url_prefix='/api/excel')
    app.register_blueprint(analysis_bp, url_prefix='/api/analysis')
    app.register_blueprint(universal_bp, url_prefix='/api/universal')
    app.register_blueprint(engineering_bp, url_prefix='/api/engineering')
    app.register_blueprint(management_bp, url_prefix='/api/management')
    app.register_blueprint(environmental_bp, url_prefix='/api/environmental')
    app.register_blueprint(health_bp, url_prefix='/api/healthcare')
    app.register_blueprint(reports_bp, url_prefix='/api/reports')
    app.register_blueprint(payment_bp, url_prefix='/api/payment')
    app.register_blueprint(user_bp, url_prefix='/api/user')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    
    # ─── Security headers on every response ──────────────────────────
    @app.after_request
    def set_security_headers(response):
        # Prevent MIME-type sniffing
        response.headers['X-Content-Type-Options'] = 'nosniff'
        # Prevent clickjacking (don't allow the app in an iframe)
        response.headers['X-Frame-Options'] = 'DENY'
        # Legacy XSS filter for old browsers
        response.headers['X-XSS-Protection'] = '1; mode=block'
        # Only send the origin on cross-origin requests, not the full URL
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        # Restrict powerful browser features
        response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        # A conservative content security policy for the JSON API
        response.headers['Content-Security-Policy'] = "default-src 'self'; frame-ancestors 'none'"
        return response

    # ─── Health Check ────────────────────────────────────────────────
    @app.route('/api/health')
    def health():
        return {'status': 'healthy', 'version': '1.0.0', 'platform': 'Excel Analytics Pro'}
    
    # ─── Error Handlers ──────────────────────────────────────────────
    @app.errorhandler(400)
    def bad_request(e):
        return {'error': 'Bad request', 'message': str(e)}, 400
    
    @app.errorhandler(401)
    def unauthorized(e):
        return {'error': 'Unauthorized', 'message': 'Authentication required'}, 401
    
    @app.errorhandler(403)
    def forbidden(e):
        return {'error': 'Forbidden', 'message': 'Access denied'}, 403
    
    @app.errorhandler(404)
    def not_found(e):
        return {'error': 'Not found', 'message': str(e)}, 404
    
    @app.errorhandler(413)
    def file_too_large(e):
        return {'error': 'File too large', 'message': 'Maximum file size is 50MB'}, 413
    
    @app.errorhandler(429)
    def rate_limit(e):
        return {'error': 'Rate limit exceeded', 'message': str(e)}, 429
    
    @app.errorhandler(500)
    def internal_error(e):
        return {'error': 'Internal server error', 'message': 'Please try again later'}, 500
    
    with app.app_context():
        db.create_all()
    
    return app

if __name__ == '__main__':
    app = create_app()
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_ENV', 'development') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug)
