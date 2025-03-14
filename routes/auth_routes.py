from flask import Blueprint, session, redirect, url_for, render_template, request, flash
import logging
from models import User, db
import msal 
import requests
from config import Config

CLIENT_ID = Config.CLIENT_ID
CLIENT_SECRET = Config.CLIENT_SECRET
AUTHORITY = Config.AUTHORITY
REDIRECT_URI = Config.REDIRECT_URI
SCOPE = Config.SCOPE

# Initialize logger
logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/')
def index():
    return render_template('index.html')

@auth_bp.route('/login')
def login():
    redirect_uri = url_for('auth.authorized', _external=True)
    return render_template('login.html')

@auth_bp.route('/azure_login')
def azure_login():
    session['state'] = 'random_state'
    redirect_uri = url_for('auth.authorized', _external=True)
    auth_url = _build_auth_url(redirect_uri=redirect_uri)
    return redirect(auth_url)

@auth_bp.route('/callback')
def authorized():
    try:
        code = request.args.get('code')
        if not code:
            return redirect(url_for('auth.index'))

        redirect_uri = url_for('auth.authorized', _external=True)
        token = _get_token_from_code(code, redirect_uri=redirect_uri)
        user_info = _get_user_info(token)
        email = user_info.get('mail') or user_info.get('userPrincipalName')

        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(
                first_name=user_info.get('givenName', 'Unknown'),
                middle_name=None,
                last_name=user_info.get('surname', 'Unknown'),
                email=email,
                role='basicuser',
                status='active'
            )
            db.session.add(user)
            db.session.commit()

        if user.status.lower() != "active":
            flash("Account suspended. Please contact support.", "error")
            return redirect(url_for('auth.login'))

        session['user'] = {
            'first_name': user.first_name,
            'middle_name': user.middle_name if user.middle_name else "",
            'last_name': user.last_name,
            'email': user.email,
            'role': user.role,
            'status': user.status
        }

        if user.role == 'admin':
            return redirect(url_for('admin.admin_home'))
        return redirect(url_for('user.basic_user_home'))
    except Exception as e:
        logger.error(f"Error during authentication: {str(e)}")
        flash("An error occurred while logging in.", "error")
        return redirect(url_for('auth.login'))

def _build_auth_url(scopes=None, state=None, redirect_uri=None):
    app = msal.PublicClientApplication(Config.CLIENT_ID, authority=Config.AUTHORITY)
    return app.get_authorization_request_url(scopes or Config.SCOPE, state=state, redirect_uri=redirect_uri)

def _get_token_from_code(code, redirect_uri):
    client = msal.ConfidentialClientApplication(Config.CLIENT_ID, authority=Config.AUTHORITY, client_credential=Config.CLIENT_SECRET)
    result = client.acquire_token_by_authorization_code(code, scopes=Config.SCOPE, redirect_uri=redirect_uri)
    return result.get("access_token")

def _get_user_info(token):
    """Retrieve user info from Microsoft Graph API."""
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get('https://graph.microsoft.com/v1.0/me', headers=headers)
    return response.json()

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.index'))

