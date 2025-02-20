import os
import logging
from flask import Flask, redirect, url_for, session, request, render_template, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_session import Session
from models import db
import msal
import requests
from dotenv import load_dotenv
from routes import user_bp

app.register_blueprint(user_bp)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__, template_folder='docs', static_folder='docs')
app.secret_key = os.getenv('SECRET_KEY')  # Required for session management

# **Fix: Properly Configure Session Storage**
app.config['SESSION_TYPE'] = 'filesystem'  # Ensures session storage is properly configured
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_FILE_DIR'] = '/tmp/flask_session'  # Set directory for file-based session storage
app.config['SESSION_FILE_THRESHOLD'] = 100  # Limit session files
app.config['SQALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

from routes import user_bp
app.register_blueprint(user_bp)

# Ensure the session directory exists
os.makedirs(app.config['SESSION_FILE_DIR'], exist_ok=True)

# Azure AD configuration
CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
TENANT_ID = os.getenv('TENANT_ID')
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
REDIRECT_URI = os.getenv('REDIRECT_URI')
SCOPE = ['User.Read']

# Database configuration
DB_SERVER = os.getenv('DB_SERVER', 'swan-river-user-information.database.windows.net')
DB_NAME = os.getenv('DB_NAME', 'UserDatabase')
DB_UID = os.getenv('DB_UID', 'jcwill23@cougarnet.uh.edu')
DB_PWD = os.getenv('DB_PWD', 'H1ghLander')

# Correct SQLAlchemy database URL format
database_url = f"mssql+pyodbc://{DB_UID}:{DB_PWD}@{DB_SERVER}:1433/{DB_NAME}?driver=ODBC+Driver+18+for+SQL+Server"
if not database_url:
    logger.error("DATABASE_URL is not set. Ensure it is configured in Azure.")
    raise ValueError("DATABASE_URL is not set.")
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database and session
db = SQLAlchemy(app)
Session(app)

# User Model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    role = db.Column(db.String(50), default="basicuser")
    status = db.Column(db.String(20), default="active")

# Home page
@app.route('/')
def index():
    return render_template('index.html')

# Login page
@app.route('/login')
def login():
    return render_template('login.html')

# Initiate Microsoft 365 login
@app.route('/azure_login')
def azure_login():
    session['state'] = 'random_state'  # Use a random state for security
    auth_url = _build_auth_url(scopes=SCOPE, state=session['state'])
    logger.info(f"Authorization URL: {auth_url}")  # Debugging
    return redirect(auth_url)

# Callback route after Microsoft 365 login
@app.route('/auth/callback')
def authorized():
    print("Callback route called")  # Debugging
    try:
        if request.args.get('state') != session.get('state'):
            print("State mismatch")  # Debugging
            return redirect(url_for('index'))  # Prevent CSRF attacks

        # Get the authorization code from the request
        code = request.args.get('code')
        if not code:
            print("Authorization code not found")  # Debugging
            return redirect(url_for('index'))

        # Get the access token
        token = _get_token_from_code(code)
        if not token:
            print("Failed to get access token")  # Debugging
            return redirect(url_for('index'))

        # Get user info from Microsoft Graph
        user_info = _get_user_info(token)
        if not user_info:
            print("Failed to get user info")  # Debugging
            return redirect(url_for('index'))

        # Store user info in session
        session['user'] = user_info
        return redirect(url_for('basic_user_home'))

    except Exception as e:
        print(f"Error in callback route: {e}")  # Debugging
        return redirect(url_for('index'))

# Admin home page
@app.route('/admin_home')
def admin_home():
    if not session.get('user') or 'admin' not in session['user'].get('roles', []):
        return redirect(url_for('index'))
    user_name = session['user']['displayName']
    return render_template('admin.html', user_name=user_name)

# Basic user home page
@app.route('/basic_user_home')
def basic_user_home():
    if not session.get('user'):
        return redirect(url_for('index'))
    user_name = session['user']['displayName']
    return render_template('basic_user_home.html', user_name=user_name)

# Logout route
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# Helper function to build the authorization URL
def _build_auth_url(scopes=None, state=None):
    return msal.PublicClientApplication(
        CLIENT_ID, authority=AUTHORITY).get_authorization_request_url(
        scopes, state=state, redirect_uri=REDIRECT_URI)

# Helper function to get the access token
def _get_token_from_code(code):
    try:
        # Initialize the MSAL client
        client = msal.ConfidentialClientApplication(
            CLIENT_ID, authority=AUTHORITY, client_credential=CLIENT_SECRET)

        # Acquire the token using the authorization code
        result = client.acquire_token_by_authorization_code(
            code, scopes=SCOPE, redirect_uri=REDIRECT_URI)

        # Check if the token was acquired successfully
        if "access_token" in result:
            print("Access token acquired successfully")  # Debugging
            return result["access_token"]
        else:
            print("Failed to acquire access token. Response:", result)  # Debugging
            return None

    except Exception as e:
        print(f"Error acquiring token: {e}")  # Debugging
        return None

def _get_user_info(token):
    graph_data = requests.get(
        'https://graph.microsoft.com/v1.0/me',
        headers={'Authorization': 'Bearer ' + token}).json()
    return graph_data

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=8000)
