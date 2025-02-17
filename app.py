from flask import Flask, redirect, url_for, session, request, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_session import Session
import msal
import requests
import os
import logging

# Initialize Flask app
app = Flask(__name__, template_folder='docs', static_folder='docs')
app.secret_key = "sWanRivEr"  # Required for session management

# Azure AD configuration
CLIENT_ID = "7fbeba40-e221-4797-8f8a-dc364de519c7"
CLIENT_SECRET = "x2T8Q~yVzAOoC~r6FYtzK6sqCJQR_~RCVH5-dcw8"
TENANT_ID = "170bbabd-a2f0-4c90-ad4b-0e8f0f0c4259"
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
REDIRECT_URI = 'https://swan-river-group-project.azurewebsites.net/auth/callback'
SCOPE = ['User .Read']

# Secure configuration settings
app.config['SESSION_TYPE'] = 'filesystem'  # Prevents session loss in Azure
app.config['SESSION_COOKIE_SECURE'] = True  # Forces HTTPS session cookies
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Prevents JavaScript from accessing cookies
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Allows cross-domain authentication

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'mssql+pyodbc://jcwill23@cougarnet.uh.edu@swan-river-user-information.database.windows.net/User%20Information?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database and session
db = SQLAlchemy(app)
Session(app)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# User Model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    role = db.Column(db.String(50), default="basicuser")
    status = db.Column(db.String(20), default="active")

# Function to initialize database
def setup_db():
    with app.app_context():
        db.create_all()

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
    logger.info(f"Authorization URL: {auth_url}")  # Logging
    return redirect(auth_url)

# Callback route after Microsoft 365 login
@app.route('/auth/callback')
def authorized():
    logger.info("Callback route called")  # Logging
    try:
        if request.args.get('state') != session.get('state'):
            logger.error("State mismatch")  # Logging
            return redirect(url_for('index'))  # Prevent CSRF attacks

        # Get the authorization code from the request
        code = request.args.get('code')
        if not code:
            logger.error("Authorization code not found")  # Logging
            return redirect(url_for('index'))

        # Get the access token
        token = _get_token_from_code(code)
        if not token:
            logger.error("Failed to get access token")  # Logging
            return redirect(url_for('index'))

        # Get user info from Microsoft Graph
        user_info = _get_user_info(token)
        if not user_info:
            logger.error("Failed to get user info")  # Logging
            return redirect(url_for('index'))

        # Store user info in session
        session['user'] = user_info

        # Check if user exists in database, otherwise create a new user
        user_email = user_info.get('mail') or user_info.get('userPrincipalName')
        user_name = user_info.get('displayName')
        user = User.query.filter_by(email=user_email).first()
        if not user:
            new_user = User(name=user_name, email=user_email, role="basicuser", status="active")
            db.session.add(new_user)
            db.session.commit()
            user = new_user

        # Redirect based on role
        if user.role == 'admin':
            return redirect(url_for('admin'))
        return redirect(url_for('basic_user_home'))

    except Exception as e:
        logger.error(f"Error in callback route: {e}")  # Logging
        return redirect(url_for('index'))

# Success page after login
@app.route('/success')
def success():
    logger.info("Success route called")  # Logging
    if not session.get('user'):
        return redirect(url_for('index'))

    user_email = session['user'].get('mail') or session['user'].get('userPrincipalName')
    user = User.query.filter_by(email=user_email).first()
    
    if user:
        # User exists in the database
        if user.role == 'admin':
            return render_template('admin.html', user_name=user.name)
        else:
            return redirect(url_for('basic_user_home'))  # Redirect to basic user home
    else:
        # User does not exist in the database, create a new user
        user_name = session['user'].get('displayName')
        new_user = User(name=user_name, email=user_email, role="basicuser", status="active")
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('basic_user_home'))  # Redirect to basic user home after creating the user

# Admin home page
@app.route('/admin')
def admin():
    if not session.get('user'):
        return redirect(url_for('index'))
    user_name = session['user']['displayName']
    return render_template('admin.html', user_name=user_name)

# Basic user home page
@app.route('/basic-user-home')
def basic_user_home():
    if not session.get('user'):
        return redirect(url_for('index'))
    user_name = session['user']['displayName']
    return render_template('basic_user_home.html', user_name=user_name)

# Admin view profile page
@app.route('/admin-view-profile')
def admin_view_profile():
    if not session.get('user'):
        return redirect(url_for('index'))
    user_name = session['user']['displayName']
    return render_template('admin-view-profile.html', user_name=user_name)

@app.route('/admin-edit-profile')
def admin_edit_profile():
    if not session.get('user'):
        return redirect(url_for('index'))
    user_name = session['user']['displayName']
    return render_template('admin-edit-profile.html', user_name=user_name)

@app.route('/admin-create-user')
def admin_create_user():
    if not session.get('user'):
        return redirect(url_for('index'))
    user_name = session['user']['displayName']
    return render_template('admin-create-user.html', user_name=user_name)

@app.route('/admin-view-user')
def admin_view_user():
    if not session.get('user'):
        return redirect(url_for('index'))
    user_name = session['user']['displayName']
    return render_template('admin-view-user.html', user_name=user_name)

@app.route('/admin-update-user')
def admin_update_user():
    if not session.get('user'):
        return redirect(url_for('index'))
    user_name = session['user']['displayName']
    return render_template('admin-update-user.html', user_name=user_name)

@app.route('/admin-delete-user')
def admin_delete_user():
    if not session.get('user'):
        return redirect(url_for('index'))
    user_name = session['user']['displayName']
    return render_template('admin-delete-user.html', user_name=user_name)

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
            logger.info("Access token acquired successfully")  # Logging
            return result["access_token"]
        else:
            logger.error(f"Failed to acquire access token. Response: {result}")  # Logging
            return None

    except Exception as e:
        logger.error(f"Error acquiring token: {e}")  # Logging
        return None

# Helper function to get user info from Microsoft Graph
def _get_user_info(token):
    graph_data = requests.get(
        'https://graph.microsoft.com/v1.0/me',
        headers={'Authorization': 'Bearer ' + token}).json()
    return graph_data

if __name__ == '__main__':
    setup_db()  # Initialize database tables
    app.run(host='0.0.0.0', port=5000)

