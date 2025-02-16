from flask import Flask, redirect, url_for, session, request, render_template, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_session import Session
from authlib.integrations.flask_client import OAuth
import os
import requests

app = Flask(__name__, template_folder='docs')
app.secret_key = os.getenv("SECRET_KEY", "swanRiver")  # Secure the secret key

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    'DATABASE_URL',
    'mssql+pyodbc://jcwill23@cougarnet.uh.edu@swan-river-user-information.database.windows.net/User%20Information'
    '?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

Session(app)

# Azure AD credentials
CLIENT_ID = os.getenv("CLIENT_ID", "f435d3c1-426e-4490-80c4-ac8ff8c05574")  # Use environment variable
CLIENT_SECRET = os.getenv("CLIENT_SECRET")  # Ensure it's set as an environment variable
AUTHORITY = 'https://login.microsoftonline.com/170bbabd-a2f0-4c90-ad4b-0e8f0f0c4259'
REDIRECT_URI = 'https://swan-river-group-project-egh0hmfcf6c9f2ef.centralus-01.azurewebsites.net/authorize'
SCOPE = ['User.Read', 'email', 'openid', 'profile']

# Initialize OAuth
oauth = OAuth(app)
oauth.register(
    "microsoft",
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    authorize_url=f"{AUTHORITY}/oauth2/v2.0/authorize",
    access_token_url=f"{AUTHORITY}/oauth2/v2.0/token",
    client_kwargs={"scope": " ".join(SCOPE)},
)

# User Model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    role = db.Column(db.String(50), default="basicuser")
    status = db.Column(db.String(20), default="active")

# DELETE LINE 48-51 AFTER TEST
@app.route("/routes")
def show_routes():
    return jsonify({rule.rule: rule.endpoint for rule in app.url_map.iter_rules()})


@app.route('/')
def home():
    return render_template('login.html')

@app.route("/login")
def login():
    return oauth.microsoft.authorize_redirect(REDIRECT_URI)

@app.route('/authorize')
def authorize():
    try:
        token = oauth.microsoft.authorize_access_token()
    except Exception as e:
        return jsonify({"error": "Authentication failed", "details": str(e)}), 400

    # Fetch user info from Microsoft Graph API
    user_info = requests.get('https://graph.microsoft.com/v1.0/me', headers={
        'Authorization': f'Bearer {token["access_token"]}'
    }).json()

    user_email = user_info.get('mail') or user_info.get('userPrincipalName')
    user_name = user_info.get('displayName')

    if not user_email:
        return jsonify({"error": "Unable to retrieve email from Office365"}), 400

    # Check if user exists in the database
    user = User.query.filter_by(email=user_email).first()

    if not user:
        # Create a new user with role "basicuser"
        new_user = User(name=user_name, email=user_email, role="basicuser", status="active")
        db.session.add(new_user)
        db.session.commit()
        user = new_user  # Assign the newly created user

    # Store user session
    session['user'] = {
        'name': user.name,
        'email': user.email,
        'role': user.role,
        'status': user.status
    }

    # Redirect based on role
    if user.role == "admin":
        return redirect("https://jcwill23-uh.github.io/Swan-River-Group-Project/admin.html")
    else:
        return redirect("https://jcwill23-uh.github.io/Swan-River-Group-Project/basic-user-home.html")

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/check_session')
def check_session():
    if 'user' in session:
        return jsonify({
            "logged_in": True,
            "name": session['user']['name'],
            "email": session['user']['email'],
            "role": session['user']['role']
        })
    return jsonify({"logged_in": False})

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

@app.before_first_request
def setup_db():
    db.create_all()

if __name__ == '__main__':
    setup_db()
    app.run(debug=True)

# Admin Routes
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
