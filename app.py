import os
import urllib.parse
import logging
from flask import Flask, redirect, url_for, session, request, render_template, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_session import Session
# NEXT 3 LINES ARE FOR TESTING... FOR NOW
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
import urllib.parse
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

# Ensure the session directory exists
os.makedirs(app.config['SESSION_FILE_DIR'], exist_ok=True)

# Azure SQL Database setup
# Configure Database URI using the new method
params = urllib.parse.quote_plus(
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=tcp:swan-river-user-information.database.windows.net,1433;"
    "DATABASE=pythonSQL;"
    "UID=jcwill23@cougarnet.uh.edu;"
    "PWD=H1ghLander;"
    "TrustServerCertificate=yes;"
    "Connection Timeout=30"
)
# Configure SQLAlchemy engine with pool pre-ping enabled
app.config['SQLALCHEMY_DATABASE_URI'] = f"mssql+pyodbc:///?odbc_connect={params}"
engine = create_engine(
    f"mssql+pyodbc:///?odbc_connect={params}",
    pool_pre_ping=True,       # Ensures stale connections are removed
    pool_recycle=1800,        # Recycles connections after 30 minutes
    pool_size=5,              # Maximum connections in the pool
    max_overflow=10           # Allow temporary extra connections
)

# Initialize database and session
db = SQLAlchemy(app)

# User Model
class User(db.Model):
    __tablename__ = 'User' # Explicitly sets table name to match table in Azure database
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    role = db.Column(db.String(50), default="basicuser")
    status = db.Column(db.String(20), default="active")

# Azure AD configuration
CLIENT_ID = "7fbeba40-e221-4797-8f8a-dc364de519c7"
CLIENT_SECRET = "x2T8Q~yVzAOoC~r6FYtzK6sqCJQR_~RCVH5-dcw8"
TENANT_ID = "170bbabd-a2f0-4c90-ad4b-0e8f0f0c4259"
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
REDIRECT_URI = "https://swan-river-group-project.azurewebsites.net/auth/callback"
SCOPE = ['User.Read']


# Routes
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
        if not token:
            return "Error: Failed to retrieve access token", 500

        user_info = _get_user_info(token)
        if not user_info:
            return "Error: Failed to retrieve user info", 500

        # Ensure a valid email is present
        email = user_info.get('mail') or user_info.get('userPrincipalName')
        if not email:
            return "Error: User email not found in authentication response", 500

        # Check if user exists
        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(
                name=user_info.get('displayName', 'Unknown'),
                email=email,
                role='basicuser'
            )
            db.session.add(user)  # Add new user only if not found

        user.status = "active"  # Update user status
        db.session.commit()  # Save changes

        # Store user info in session
        session['user'] = {'name': user.name, 'email': user.email, 'role': user.role}

        # Redirect based on role
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

@app.route('/basic_user_home')
def basic_user_home():
    if 'user' not in session:
        return redirect(url_for('index'))
    return render_template('basic_user_home.html', user_name=session['user']['displayName'])

@app.route('/basic_user_view')
def basic_user_view():
    if 'user' not in session:
        return redirect(url_for('index'))
    user = session['user']
    return render_template("basic_user_view.html", user=user)

@app.route('/basic_user_edit')
def basic_user_edit():
    return render_template("basic_user_edit.html")

# Admin routes
@app.route('/admin_home')
def admin_home():
    if 'user' not in session or session['user'].get('role') != "admin":
        return redirect(url_for('index'))  # Redirect non-admin users to home

    return render_template('admin.html', user_name=session['user']['name'])

@app.route('/user/profile')
def user_profile():
    if "user" not in session:
        return jsonify({"error": "User not logged in"}), 401
    user = User.query.filter_by(email=session['user'].get('email')).first()
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify({"name": user.name, "email": user.email, "role": user.role, "status": user.status})

@app.route('/user/profile/update', methods=['PUT'])
def update_user_profile():
    if "user" not in session:
        return jsonify({"error": "User not logged in"}), 401
    user = User.query.filter_by(email=session['user'].get('email')).first()
    if not user:
        return jsonify({"error": "User not found"}), 404
    data = request.get_json()
    user.name = data.get("name", user.name)
    db.session.commit()
    return jsonify({"message": "Profile updated successfully!"})

# Helper functions
def _build_auth_url(scopes=None, state=None):
    return msal.PublicClientApplication(CLIENT_ID, authority=AUTHORITY).get_authorization_request_url(
        scopes, state=state, redirect_uri=REDIRECT_URI)

def _get_token_from_code(code):
    client = msal.ConfidentialClientApplication(CLIENT_ID, authority=AUTHORITY, client_credential=CLIENT_SECRET)
    result = client.acquire_token_by_authorization_code(code, scopes=SCOPE, redirect_uri=REDIRECT_URI)
    return result.get("access_token")

def _get_user_info(token):
    user_info = requests.get('https://graph.microsoft.com/v1.0/me', headers={'Authorization': 'Bearer ' + token}).json()
    user_info['role'] = 'basicuser'
    user_info['status'] = 'active'
    return user_info

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run()
