import os
import logging
from flask import Flask, redirect, url_for, session, request, render_template, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_session import Session
import msal
import requests
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

# Database setup
DB_SERVER = os.getenv('DB_SERVER', 'swan-river-user-information.database.windows.net')
DB_NAME = os.getenv('DB_NAME', 'UserDatabase')
DB_UID = os.getenv('DB_UID', 'jcwill23@cougarnet.uh.edu')
DB_PWD = os.getenv('DB_PWD', 'H1ghLander')

database_url = f"mssql+pyodbc://{DB_UID}:{DB_PWD}@{DB_SERVER}:1433/{DB_NAME}?driver=ODBC+Driver+18+for+SQL+Server"
app.config['SQLALCHEMY_DATABASE_URI'] = database_url

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

# Azure AD configuration
CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
TENANT_ID = os.getenv('TENANT_ID')
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
REDIRECT_URI = os.getenv('REDIRECT_URI')
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
    code = request.args.get('code')
    if not code:
        return redirect(url_for('index'))

    token = _get_token_from_code(code)
    user_info = _get_user_info(token)

    if not user_info:
        return redirect(url_for('index'))

    session['user'] = user_info

    # **Check if user is already in DB**
    existing_user = User.query.filter_by(email=user_info['mail']).first()
    if not existing_user:
        new_user = User(
            name=user_info.get('displayName', 'Unknown'),
            email=user_info['mail'],
            role='basicuser',
            status='active'
        )
        db.session.add(new_user)
        db.session.commit()
        print(f"✅ New user added: {new_user.name}, {new_user.email}")  # Debugging
    else:
        print(f"🔹 User already exists: {existing_user.email}")

    return redirect(url_for('basic_user_home'))

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
    return render_template("basic_user_view.html")

@app.route('/basic_user_edit')
def basic_user_edit():
    return render_template("basic_user_edit.html")

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
    return requests.get('https://graph.microsoft.com/v1.0/me', headers={'Authorization': 'Bearer ' + token}).json()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=8000)
