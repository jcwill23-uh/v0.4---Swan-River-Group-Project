from database import db
from datetime import datetime

class User(db.Model):
    __tablename__ = 'User'
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    middle_name = db.Column(db.String(50), nullable=True)
    last_name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    role = db.Column(db.String(50), default="basicuser")
    status = db.Column(db.String(20), default="active")
    signature_url = db.Column(db.String(255), nullable=True)
    pdf_url = db.Column(db.String(255), nullable=True)

class ReleaseFormRequest(db.Model):
    __tablename__ = 'release_form_request'
    id = db.Column(db.Integer, primary_key=True)
    student_name = db.Column(db.String(100), nullable=False)
    peoplesoft_id = db.Column(db.String(10), nullable=False)
    password = db.Column(db.String(10), nullable=False)
    campus = db.Column(db.String(50), nullable=False)
    categories = db.Column(db.String(255), nullable=False)
    specific_info = db.Column(db.String(255), nullable=False)
    release_to = db.Column(db.String(255), nullable=False)
    purpose = db.Column(db.String(255), nullable=False)
    signature_url = db.Column(db.String(255), nullable=True)
    pdf_url = db.Column(db.String(255), nullable=True)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    approval_status = db.Column(db.String(20), default="pending")
