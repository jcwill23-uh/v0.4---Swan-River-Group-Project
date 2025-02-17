from flask import Flask, redirect, url_for, session, request, render_template, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_session import Session
from flask import send_from_directory
from authlib.integrations.flask_client import OAuth
import os
import requests
import traceback

# Initialize Flask app
app = Flask(__name__, template_folder='docs', static_folder='docs')

# Secure configuration settings
app.config['SESSION_TYPE'] = 'filesystem'  # Prevents session loss in Azure
app.config['SESSION_COOKIE_SECURE'] = True  # Forces HTTPS session cookies
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Prevents JavaScript from accessing cookies
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Allows cross-domain authentication

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    'DATABASE_URL',
    'mssql+pyodbc://jcwill23@cougarnet.uh.edu@swan-river-user-information.database.windows.net/User%20Information'
    '?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database and session
db = SQLAlchemy(app)
Session(app)

# Azure AD OAuth Configuration
CLIENT_ID = "7fbeba40-e221-4797-8f8a-dc364de519c7"
CLIENT_SECRET = "x2T8Q~yVzAOoC~r6FYtzK6sqCJQR_~RCVH5-dcw8"
TENANT_ID = "170bbabd-a2f0-4c90-ad4b-0e8f0f0c4259"
SECRET_KEY= "sWanRivEr"
REDIRECT_URI = 'https://swan-river-group-project.azurewebsites.net/login'
SCOPE = ['User.Read', 'email', 'openid', 'profile']

# Initialize OAuth
oauth = OAuth(app)
oauth.register(
    "microsoft",
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    server_metadata_url=f"{AUTHORITY}/v2.0/.well-known/openid-configuration",
    client_kwargs={"scope": " ".join(SCOPE)},
)

# User Model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    role = db.Column(db.String(50), default="basicuser")
    status = db.Column(db.String(20), default="active")

# Debugging Route (DELETE AFTER TESTING)
@app.route("/routes")
def show_routes():
    return jsonify({rule.rule: rule.endpoint for rule in app.url_map.iter_rules()})    

# Serve static files from the docs folder
@app.route('/docs/<path:filename>')
def serve_docs_static(filename):
    return send_from_directory('docs', filename)

# Function to initialize database
def setup_db():
    with app.app_context():
        db.create_all()

# Home route (Index Page)
@app.route('/')
def index():
    return render_template('index.html')

# Route for login page
@app.route('/login_page')
def login_page():
    return render_template('login.html')

# OAuth Login Route
@app.route('/login', methods=['POST'])
def login():
    try:
        token = oauth.microsoft.authorize_access_token()
        user_info = requests.get(
            'https://graph.microsoft.com/v1.0/me',
            headers={'Authorization': f'Bearer {token["access_token"]}'}
        ).json()

        user_email = user_info.get('mail') or user_info.get('userPrincipalName')
        user_name = user_info.get('displayName')

        if not user_email:
            return jsonify({"error": "Unable to retrieve email from Office365"}), 400

        user = User.query.filter_by(email=user_email).first()
        if not user:
            new_user = User(name=user_name, email=user_email, role="basicuser", status="active")
            db.session.add(new_user)
            db.session.commit()
            user = new_user

        session['user'] = {
            'name': user.name,
            'email': user.email,
            'role': user.role,
            'status': user.status
        }
        session.modified = True  

        # Redirect based on role
        if user.role == "admin":
            return redirect("admin.html")
        return redirect("basic-user-home.html")

    except Exception as e:
        return jsonify({"error": "Authentication failed", "details": str(e)}), 400

# Logout Route
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# Run the app
if __name__ == '__main__':
    setup_db()  # Initialize database tables
    app.run(host='0.0.0.0', port=8000, debug=True, use_reloader=False)
