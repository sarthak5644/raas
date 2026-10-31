"""
Database Models - Excel Analytics Platform
"""
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(255))
    phone = db.Column(db.String(20))
    avatar_url = db.Column(db.String(500))
    is_verified = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    is_admin = db.Column(db.Boolean, default=False)
    plan = db.Column(db.String(50), default='free')  # free, basic, pro, enterprise
    plan_expiry = db.Column(db.DateTime)
    stripe_customer_id = db.Column(db.String(255))
    download_credits = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    # Relationships
    files = db.relationship('ExcelFile', backref='owner', lazy=True, cascade='all, delete-orphan')
    analyses = db.relationship('Analysis', backref='user', lazy=True, cascade='all, delete-orphan')
    payments = db.relationship('Payment', backref='user', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'username': self.username,
            'full_name': self.full_name,
            'phone': self.phone,
            'avatar_url': self.avatar_url,
            'is_verified': self.is_verified,
            'plan': self.plan,
            'plan_expiry': self.plan_expiry.isoformat() if self.plan_expiry else None,
            'download_credits': self.download_credits,
            'is_admin': self.is_admin,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat(),
        }


class ExcelFile(db.Model):
    __tablename__ = 'excel_files'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    original_name = db.Column(db.String(500), nullable=False)
    stored_name = db.Column(db.String(500), nullable=False, unique=True)
    file_path = db.Column(db.String(1000), nullable=False)
    file_size = db.Column(db.Integer)  # bytes
    file_type = db.Column(db.String(20))  # xlsx, csv, etc.
    
    # Analysis metadata
    sheet_count = db.Column(db.Integer)
    total_rows = db.Column(db.Integer)
    total_cols = db.Column(db.Integer)
    total_cells = db.Column(db.Integer)
    missing_values = db.Column(db.Integer, default=0)
    duplicate_rows = db.Column(db.Integer, default=0)
    data_quality_score = db.Column(db.Float)
    
    # Detailed metadata stored as JSON
    columns_meta = db.Column(db.Text)  # JSON
    sheets_meta = db.Column(db.Text)   # JSON
    file_insights = db.Column(db.Text) # JSON
    recommended_analyses = db.Column(db.Text)  # JSON
    
    status = db.Column(db.String(50), default='processing')  # processing, ready, error
    error_message = db.Column(db.Text)

    # ── AI / system verification of the uploaded file ──────────────────
    detected_data_type = db.Column(db.String(50))      # Nominal, Binary, Continuous, etc.
    ai_verified = db.Column(db.Boolean, default=None)   # True/False/None(not yet checked)
    ai_verification_method = db.Column(db.String(20))   # 'ai' or 'local'
    ai_verification_notes = db.Column(db.Text)          # short explanation
    ai_verified_at = db.Column(db.DateTime)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    analyses = db.relationship('Analysis', backref='file', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'original_name': self.original_name,
            'file_size': self.file_size,
            'file_type': self.file_type,
            'sheet_count': self.sheet_count,
            'total_rows': self.total_rows,
            'total_cols': self.total_cols,
            'total_cells': self.total_cells,
            'missing_values': self.missing_values,
            'duplicate_rows': self.duplicate_rows,
            'data_quality_score': self.data_quality_score,
            'columns_meta': json.loads(self.columns_meta) if self.columns_meta else [],
            'sheets_meta': json.loads(self.sheets_meta) if self.sheets_meta else [],
            'file_insights': json.loads(self.file_insights) if self.file_insights else {},
            'recommended_analyses': json.loads(self.recommended_analyses) if self.recommended_analyses else [],
            'status': self.status,
            'error_message': self.error_message,
            'detected_data_type': self.detected_data_type,
            'ai_verified': self.ai_verified,
            'ai_verification_method': self.ai_verification_method,
            'ai_verification_notes': self.ai_verification_notes,
            'ai_verified_at': self.ai_verified_at.isoformat() if self.ai_verified_at else None,
            'created_at': self.created_at.isoformat(),
        }


class Analysis(db.Model):
    __tablename__ = 'analyses'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    file_id = db.Column(db.Integer, db.ForeignKey('excel_files.id'), nullable=False)
    
    analysis_type = db.Column(db.String(100))  # summary, correlation, forecast, etc.
    title = db.Column(db.String(500))
    prompt = db.Column(db.Text)  # user's question or request
    result = db.Column(db.Text)  # JSON - charts, tables, insights
    ai_narrative = db.Column(db.Text)  # Gemini AI narrative
    
    tokens_used = db.Column(db.Integer, default=0)
    status = db.Column(db.String(50), default='pending')  # pending, done, error
    is_premium = db.Column(db.Boolean, default=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'file_id': self.file_id,
            'analysis_type': self.analysis_type,
            'title': self.title,
            'prompt': self.prompt,
            'result': json.loads(self.result) if self.result else {},
            'ai_narrative': self.ai_narrative,
            'tokens_used': self.tokens_used,
            'status': self.status,
            'is_premium': self.is_premium,
            'created_at': self.created_at.isoformat(),
        }


class Report(db.Model):
    __tablename__ = 'reports'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    file_id = db.Column(db.Integer, db.ForeignKey('excel_files.id'))
    analysis_id = db.Column(db.Integer, db.ForeignKey('analyses.id'))
    
    title = db.Column(db.String(500))
    report_type = db.Column(db.String(100))  # pdf, dashboard, excel
    file_path = db.Column(db.String(1000))
    is_paid = db.Column(db.Boolean, default=False)
    price = db.Column(db.Float, default=0.0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'report_type': self.report_type,
            'is_paid': self.is_paid,
            'price': self.price,
            'created_at': self.created_at.isoformat(),
        }


class Payment(db.Model):
    __tablename__ = 'payments'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    stripe_session_id = db.Column(db.String(500))
    stripe_payment_intent = db.Column(db.String(500))
    amount = db.Column(db.Float)
    currency = db.Column(db.String(10), default='inr')
    status = db.Column(db.String(50))  # pending, paid, failed, refunded
    plan = db.Column(db.String(50))    # basic, pro, enterprise, credits
    credits_added = db.Column(db.Integer, default=0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'amount': self.amount,
            'currency': self.currency,
            'status': self.status,
            'plan': self.plan,
            'credits_added': self.credits_added,
            'created_at': self.created_at.isoformat(),
        }


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(200))
    resource_type = db.Column(db.String(100))
    resource_id = db.Column(db.Integer)
    ip_address = db.Column(db.String(50))
    user_agent = db.Column(db.String(500))
    details = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
