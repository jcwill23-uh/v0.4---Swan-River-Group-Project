from flask import Flask, redirect, url_for, session, request, render_template, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_session import Session
from oauthlib.oauth2 import WebApplicationClient
from requests_oauthlib import OAuth2Session
import os
import secrets
import base64
import hashlib
import requests

app = Flask(__name__, template_folder='docs')
app.secret_key = 'swanRiver'  # Replace with a real secret key

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    'DATABASE_URL',
    'mssql+pyodbc://jcwill23@cougarnet.uh.edu@swan-river-user-information:{Superman517071!}@swan-river-user-information.database.windows.net/User%20Information?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

if __name__ == "__main__":
    app.run(debug=True)

Session(app)

# Azure AD credentials
CLIENT_ID = '7d3a3c1c-46ec-4247-9ed4-ef0d1526c5b9'  # Replace with your Application (client) ID
CLIENT_SECRET = '1pF8Q~cPp9z-i_1N3gkeN4FN4t3gT9_7fcl-Tcek'  # Replace with your client secret
AUTHORITY = 'https://login.microsoftonline.com/170bbabd-a2f0-4c90-ad4b-0e8f0f0c4259'
REDIRECT_URI = 'https://jcwill23-uh.github.io/Swan-River-Group-Project/basic_user_home.html'
SCOPE = ['User.Read', 'Files.ReadWrite', 'email', 'openid', 'profile']

# OAuth2 session
client = WebApplicationClient(CLIENT_ID)

def generate_pkce_pair():
    code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b'=').decode('utf-8')
    code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode('utf-8')).digest()).rstrip(b'=').decode('utf-8')
    return code_verifier, code_challenge

@app.route('/')
def home():
    return render_template('login.html')

@app.route('/authorize')
def authorize():
    token = client.fetch_token(
        f'{AUTHORITY}/oauth2/v2.0/token',
        authorization_response=request.url,
        client_secret=CLIENT_SECRET
    )

    # Fetch user info from Microsoft Graph API
    user_info = requests.get('https://graph.microsoft.com/v1.0/me', headers={
        'Authorization': f'Bearer {token["access_token"]}'
    }).json()

    user_email = user_info.get('mail') or user_info.get('userPrincipalName')
    user_name = user_info.get('displayName')

    # Check if user exists in the database
    user = User.query.filter_by(email=user_email).first()

    if not user:
        # Create a new user with role "basicuser"
        new_user = User(name=user_name, email=user_email, role="basicuser")
        db.session.add(new_user)
        db.session.commit()

    # Store user session
    session['user'] = {
        'name': user_name,
        'email': user_email,
        'role': user.role if user else "basicuser"
    }

    return redirect(url_for('home'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

# Import User model
from models import User

@app.route('/users', methods=['GET'])
def get_users():
    users = User.query.all()
    return jsonify([{"id": user.id, "name": user.name, "email": user.email, "role": user.role, "status": user.status} for user in users])

@app.route('/users', methods=['POST'])
def create_user():
    data = request.json
    new_user = User(name=data['name'], email=data['email'], role=data.get('role', 'basicuser'))
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"message": "User created successfully"}), 201

@app.route('/user/profile', methods=['GET'])
def get_user_profile():
    if 'user' not in session:
        return jsonify({"error": "User not authenticated"}), 401

    user_email = session['user']['email']
    user = User.query.filter_by(email=user_email).first()

    if not user:
        return jsonify({"error": "User not found"}), 404

    return jsonify({
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "status": user.status
    })

@app.route('/user/profile/update', methods=['PUT'])
def update_user_profile():
    if 'user' not in session:
        return jsonify({"error": "User not authenticated"}), 401

    user_email = session['user']['email']
    user = User.query.filter_by(email=user_email).first()

    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.json
    user.name = data.get('name', user.name)
    user.email = data.get('email', user.email)

    db.session.commit()
    return jsonify({"message": "Profile updated successfully"})

@app.route('/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    db.session.delete(user)
    db.session.commit()
    return jsonify({"message": "User deleted successfully"})

@app.route('/users/deactivate/<int:user_id>', methods=['POST'])
def deactivate_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    user.status = "deactivated"
    db.session.commit()
    return jsonify({"message": "User deactivated successfully"})

@app.before_first_request
def setup_db():
    db.create_all()

if __name__ == '__main__':
    setup_db()
    app.run(debug=True)
    

# Routes for database as an admin
@app.route('/admin/all_users', methods=['GET'])
def get_all_users():
    if 'user' not in session or session['user']['role'] != 'admin':
        return jsonify({"error": "Unauthorized"}), 403

    users = User.query.all()
    user_list = [{
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "status": user.status
    } for user in users]

    return jsonify(user_list)

@app.route('/admin/create_user', methods=['POST'])
def create_user():
    if 'user' not in session or session['user']['role'] != 'admin':
        return jsonify({"error": "Unauthorized"}), 403

    data = request.json
    new_user = User(
        name=data['name'],
        email=data['email'],
        role=data['role'],
        status=data['status']
    )

    db.session.add(new_user)
    db.session.commit()
    return jsonify({"message": "User created successfully"}), 201

@app.route('/admin/update_user/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    if 'user' not in session or session['user']['role'] != 'admin':
        return jsonify({"error": "Unauthorized"}), 403

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.json
    user.name = data.get('name', user.name)
    user.email = data.get('email', user.email)
    user.role = data.get('role', user.role)
    user.status = data.get('status', user.status)

    db.session.commit()
    return jsonify({"message": "User updated successfully"}), 200

@app.route('/admin/deactivate_user/<int:user_id>', methods=['PUT'])
def deactivate_user(user_id):
    if 'user' not in session or session['user']['role'] != 'admin':
        return jsonify({"error": "Unauthorized"}), 403

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    user.status = 'deactivated'
    db.session.commit()
    return jsonify({"message": "User deactivated"}), 200
