import os
import urllib.parse
import logging
from flask import Flask, redirect, url_for, session, request, render_template, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from functools import wraps
import msal
import requests
import pyodbc
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__, template_folder='docs', static_folder='docs')
app.secret_key = os.getenv('SECRET_KEY')

# Configure session storage
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_FILE_DIR'] = '/tmp/flask_session'
app.config['SESSION_FILE_THRESHOLD'] = 100
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Ensure session directory exists
os.makedirs(app.config['SESSION_FILE_DIR'], exist_ok=True)

# Azure SQL Database setup
params = urllib.parse.quote_plus(
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=tcp:swan-river-user-information.database.windows.net,1433;"
    "DATABASE=UserDatabase;"
    "UID=jcwill23@cougarnet.uh.edu@swan-river-user-information;"
    "PWD=H1ghLander;"
    "Encrypt=yes;"
    "TrustServerCertificate=no;"
    "Connection Timeout=30"
)

# Configure SQLAlchemy engine
engine = create_engine(
    f"mssql+pyodbc:///?odbc_connect={params}",
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_size=5,
    max_overflow=10
)

# Bind engine to SQLAlchemy
app.config['SQLALCHEMY_DATABASE_URI'] = engine.url
db = SQLAlchemy(app)

# User Model
class User(db.Model):
    __tablename__ = 'User'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    role = db.Column(db.String(50), default="basicuser")
    status = db.Column(db.String(20), default="active")

# Azure AD Configuration
CLIENT_ID = "7fbeba40-e221-4797-8f8a-dc364de519c7"
CLIENT_SECRET = "x2T8Q~yVzAOoC~r6FYtzK6sqCJQR_~RCVH5-dcw8"
TENANT_ID = "170bbabd-a2f0-4c90-ad4b-0e8f0f0c4259"
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
REDIRECT_URI = "https://swan-river-group-project.azurewebsites.net/auth/callback"
SCOPE = ['User.Read']

# Authentication Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/azure_login')
def azure_login():
    session['state'] = 'random_state'
    auth_url = _build_auth_url(scopes=SCOPE, state=session['state'])
    return redirect(auth_url)

@app.route('/auth/callback')
def authorized():
    try:
        code = request.args.get('code')
        if not code:
            return redirect(url_for('index'))
        
        token = _get_token_from_code(code)
        user_info = _get_user_info(token)
        email = user_info.get('mail') or user_info.get('userPrincipalName')

        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(name=user_info.get('displayName', 'Unknown'), email=email, role='basicuser')
            db.session.add(user)

        user.status = "active"
        db.session.commit()

        session['user'] = {'name': user.name, 'email': user.email, 'role': user.role}

        if user.role == "admin":
            return redirect(url_for('admin_home'))
        return redirect(url_for('basic_user_home'))

    except Exception as e:
        logger.error(f"Internal Server Error: {str(e)}")
        return f"Internal Server Error: {str(e)}", 500

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# Basic User Routes
@app.route('/basic_user_home')
def basic_user_home():
    if 'user' not in session:
        return redirect(url_for('index'))
    return render_template('basic_user_home.html', user_name=session['user'])

@app.route('/basic_user_view')
def basic_user_view():
    if 'user' not in session:
        return redirect(url_for('index'))
    return render_template("basic_user_view.html", user=session['user'])

@app.route('/basic_user_edit')
def basic_user_edit():
    return render_template("basic_user_edit.html", user=session['user'])

# Admin-Only Decorator
def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if 'user' not in session or session['user'].get('role') != "admin":
            flash("Access denied. Admins only.", "danger")
            return redirect(url_for('index'))
        return func(*args, **kwargs)
    return wrapper

# Admin Routes
@app.route('/admin_home')
@admin_required
def admin_home():
    return render_template('admin.html', user_name=session['user']['name'])

@app.route('/admin/create-user')
@admin_required
def admin_create_user():
    return render_template('admin-create-user.html')

@app.route('/admin/delete-user')
@admin_required
def admin_delete_user():
    return render_template('admin-delete-user.html')

@app.route('/admin/edit-profile')
@admin_required
def admin_edit_profile():
    return render_template('admin-edit-profile.html', user=session['user'])

@app.route('/admin/update-user')
@admin_required
def admin_update_user():
    return render_template('admin-update-user.html')

@app.route('/admin/view-profile')
@admin_required
def admin_view_profile():
    return render_template('admin-view-profile.html', user=session['user'])

@app.route('/admin/view-users')
@admin_required
def admin_view_users():
    return render_template('admin-view-user.html')

# Helper functions
def _build_auth_url(scopes=None, state=None):
    return msal.PublicClientApplication(CLIENT_ID, authority=AUTHORITY).get_authorization_request_url(
        scopes, state=state, redirect_uri=REDIRECT_URI)

def _get_token_from_code(code):
    client = msal.ConfidentialClientApplication(CLIENT_ID, authority=AUTHORITY, client_credential=CLIENT_SECRET)
    result = client.acquire_token_by_authorization_code(code, scopes=SCOPE, redirect_uri=REDIRECT_URI)
    return result.get("access_token")

def _get_user_info(token):
    return requests.get('https://graph.microsoft.com/v1.0/me', headers={'Authorization': 'Bearer ' + token}).json()

# Run Flask App
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run()
    
