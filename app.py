import os
import urllib.parse
import logging
from flask import Flask, redirect, url_for, session, request, render_template, jsonify, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from functools import wraps
import msal
import requests
import pyodbc
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient
from datetime import datetime
import subprocess

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

# ---- Database Models ----

# User Model
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

from datetime import datetime

# Release Form Request Model
class ReleaseFormRequest(db.Model):
    __tablename__ = 'release_form_request'
    
    id = db.Column(db.Integer, primary_key=True)
    student_name = db.Column(db.String(100), nullable=False)
    peoplesoft_id = db.Column(db.String(10), nullable=False)
    password = db.Column(db.String(10), nullable=False)
    campus = db.Column(db.String(50), nullable=False)
    categories = db.Column(db.String(255), nullable=False)  # Comma-separated categories
    specific_info = db.Column(db.String(255), nullable=False)  # Comma-separated specific info
    release_to = db.Column(db.String(255), nullable=False)
    purpose = db.Column(db.String(255), nullable=False)  # Comma-separated purposes
    signature_url = db.Column(db.String(255), nullable=True)
    pdf_url = db.Column(db.String(255), nullable=True) # Store PDF location
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)

# Request Form Model
class RequestForm(db.Model):
    __tablename__ = 'request_form'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, nullable=False)
    form_type = db.Column(db.String(100), nullable=False)
    request_data = db.Column(db.Text, nullable=False)
    approval_status = db.Column(db.String(20), default="pending")
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)

# Approval Model
class Approval(db.Model):
    __tablename__ = 'approval'
    
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey('request_form.id'), nullable=False)
    approver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default="pending")
    comments = db.Column(db.Text, nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)

# User Signature Model
class UserSignature(db.Model):
    __tablename__ = 'user_signature'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    signature_url = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=True)

# ---- API Routes ----

# Route to handle form submission
@app.route('/submit_release_form', methods=['POST'])
def submit_release_form():
    try:
        import os

        data = request.form
        is_final_submission = data.get("final_submission") == "true"

        student_name = (data.get('first_name') or "").strip() + " " + (data.get('middle_name') or "").strip() + " " + (data.get('last_name') or "").strip()
        peoplesoft_id = (data.get('peoplesoftID') or "").strip()
        password = (data.get('password') or "").strip()
        campus = (data.get('campus') or "").strip()
        categories = ','.join(request.form.getlist('categories'))
        specific_info = ','.join(request.form.getlist('info'))
        release_to = (data.get('releaseTo') or "").strip()
        purpose = ','.join(request.form.getlist('purpose'))
        signature_url = data.get('signature_url', None)

        # Save form request in database
        new_request = ReleaseFormRequest(
            student_name=student_name,
            peoplesoft_id=peoplesoft_id,
            password=password,
            campus=campus,
            categories=categories,
            specific_info=specific_info,
            release_to=release_to,
            purpose=purpose,
            signature_url=signature_url,
            submitted_at=None if not is_final_submission else datetime.utcnow()
        )
        db.session.add(new_request)
        db.session.commit()

        # Fetch User Object Before PDF Generation
        user = User.query.filter_by(email=session["user"]["email"]).first()
        if not user:
            return jsonify({"error": "User not found"}), 404

        # Ensure the directory exists
        pdf_dir = "/mnt/data"
        if not os.path.exists(pdf_dir):
            os.makedirs(pdf_dir)  # Create directory if it doesn't exist

        # Define file paths
        tex_file_path = os.path.join(pdf_dir, f"form_{new_request.id}.tex")
        pdf_file_path = os.path.join(pdf_dir, f"form_{new_request.id}.pdf")

        # Write LaTeX content to the file
        with open(tex_file_path, "w") as tex_file:
            tex_file.write(generate_latex_content(new_request, user))

        # Run pdflatex to generate PDF
        try:
            subprocess.run(["pdflatex", "-output-directory", pdf_dir, tex_file_path], check=True)
        except subprocess.CalledProcessError:
            return jsonify({"error": "PDF generation failed"}), 500

        # Upload PDF to Azure Blob Storage
        blob_name = f"release_forms/form_{new_request.id}.pdf"
        blob_client = pdf_container_client.get_blob_client(blob_name)

        with open(pdf_file_path, "rb") as data:
            blob_client.upload_blob(data, overwrite=True)

        # Store PDF URL in the database
        new_request.pdf_url = f"https://{pdf_blob_service.account_name}.blob.core.windows.net/{PDF_CONTAINER_NAME}/{blob_name}"
        db.session.commit()

        return jsonify({"message": "Form submitted successfully", "pdf_url": new_request.pdf_url}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

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

        logger.info(f"User attempting login: {email}")

        # Fetch user from database
        user = User.query.filter_by(email=email).first()

        if not user:
            logger.info(f"User {email} not found. Creating new basic user.")
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
            db.session.refresh(user)  # Ensure role and status are fresh

        else:
            logger.info(f"User {email} found in database with role: {user.role} and status: {user.status}")

        db.session.refresh(user)  # Refresh to get the latest role and status

        # Check if the user is suspended
        if user.status.lower() != "active":
            logger.warning(f"User {email} is suspended. Redirecting to login.")
            flash("Account suspended. Please contact support.", "error")
            return redirect(url_for('login'))

        # Store user details properly in session
        session['user'] = {
            'first_name': user.first_name,
            'middle_name': user.middle_name if user.middle_name else '',
            'last_name': user.last_name,
            'email': user.email,
            'role': user.role.strip().lower(),
            'status': user.status
        }

        logger.info(f"User {user.email} logged in with role: {session['user']['role']} and status: {session['user']['status']}")

         # Debug before role check
        logger.info(f"Checking role for {user.email}: session['user']['role'] = {session['user']['role']}")

        # Redirect based on role
        if session.get('user', {}).get('role', '').strip().lower() == "admin":
            logger.info(f"Admin {user.email} is being redirected to admin_home")
            return redirect(url_for('admin_home'))
        else:
            return redirect(url_for('basic_user_home'))

    except Exception as e:
        logger.error(f"Internal Server Error: {str(e)}", exc_info=True)
        flash("An error occurred while logging in. Please try again.", "error")
        return redirect(url_for('login'))


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# Basic User Routes
@app.route('/basic_user_home')
def basic_user_home():
    if 'user' not in session:
        return redirect(url_for('index'))
    return render_template(
        'basic_user_home.html',
        user_name=f"{session['user']['first_name']} {session['user'].get('middle_name', '').strip()} {session['user']['last_name']}".strip()
    )

@app.route('/basic_user_view')
def basic_user_view():
    if 'user' not in session:
        return redirect(url_for('index'))
    return render_template("basic_user_view.html", user=session['user'])

@app.route('/basic_user_edit')
def basic_user_edit():
    if 'user' not in session:
        return redirect(url_for('index'))
    return render_template("basic_user_edit.html", user=session['user'])

@app.route('/basic_user_forms')
def basic_user_forms():
    if 'user' not in session:
        return redirect(url_for('index'))
    # Fetch user's signature from the database
    email = session['user']['email']
    user = User.query.filter_by(email=email).first()
    # Get the signature URL (if exists)
    signature_url = user.signature_url if user and user.signature_url else ""
    return render_template("basic_user_forms.html", user=session['user'])

@app.route('/basic_user_release')
def basic_user_release():
    if 'user' not in session:
        return redirect(url_for('index'))
    # Fetch user's signature from the database
    email = session['user']['email']
    user = User.query.filter_by(email=email).first()
    # Get the signature URL (if exists)
    signature_url = user.signature_url if user and user.signature_url else ""
    return render_template("basic_user_release.html", user=session['user'], signature_url=signature_url)

@app.route('/basic_user_ssn')
def basic_user_ssn():
    if 'user' not in session:
        return redirect(url_for('index'))
    # Fetch user's signature from the database
    email = session['user']['email']
    user = User.query.filter_by(email=email).first()
    # Get the signature URL (if exists)
    signature_url = user.signature_url if user and user.signature_url else ""
    return render_template("basic_user_ssn.html", user=session['user'], signature_url=signature_url)

@app.route('/basic_user_form_status')
def basic_user_form_status():
    if 'user' not in session:
        return redirect(url_for('index'))
    # Fetch user's signature from the database
    email = session['user']['email']
    user = User.query.filter_by(email=email).first()
    return render_template("basic_user_form_status.html", user=session['user'])

# Generate PDF upon submission
@app.route('/generate_pdf/<int:form_id>', methods=['GET'])
def generate_pdf(form_id):
    # Retrieve form data
    form = ReleaseFormRequest.query.get(form_id)
    if not form:
        return jsonify({"error": "Form not found"}), 404

    user = User.query.filter_by(email=session["user"]["email"]).first()
    if not user:
        return jsonify({"error": "User not found"}), 404

    # Prepare data for LaTeX
    tex_file_path = f"/mnt/data/form_{form_id}.tex"
    with open(tex_file_path, "w") as tex_file:
        tex_file.write(generate_latex_content(form, user))

    # Compile LaTeX to PDF using Makefile
    try:
        subprocess.run(["make", f"form_{form_id}.pdf"], check=True, cwd="/mnt/data")
    except subprocess.CalledProcessError as e:
        return jsonify({"error": f"PDF generation failed: {e}"}), 500

    pdf_file_path = f"/mnt/data/form_{form_id}.pdf"

    # Save to database (assuming we store the file in Azure)
    blob_name = f"release_forms/form_{form_id}.pdf"
    blob_client = pdf_container_client.get_blob_client(blob_name)
    with open(pdf_file_path, "rb") as data:
        blob_client.upload_blob(data, overwrite=True)

    form.pdf_url = f"https://{pdf_blob_service.account_name}.blob.core.windows.net/{PDF_CONTAINER_NAME}/{blob_name}"
    db.session.commit()

    return send_file(pdf_file_path, as_attachment=True)

# Generate latex content for release form
def generate_latex_content(form, user):
    latex_content = f"""
    \\documentclass{{article}}
    \\usepackage{{graphicx}}
    \\usepackage{{datetime}}
    
    \\begin{{document}}
    
    \\title{{Authorization to Release Educational Records}}
    \\author{{University of Houston}}
    \\date{{\\today}}
    
    \\maketitle
    
    \\noindent
    I \\textbf{{{form.student_name}}}, hereby voluntarily authorize officials in the University of Houston - {form.campus} to disclose personally identifiable information from my educational records.
    
    \\section*{{Categories of Information to Release}}
    {form.categories}
    
    \\section*{{Specifically Authorized Information}}
    {form.specific_info}
    
    \\section*{{Release To}}
    \\textbf{{{form.release_to}}} for the purpose of \\textbf{{{form.purpose}}}.
    
    \\section*{{Password for Phone Verification}}
    {form.password}
    
    \\section*{{Signature}}
    \\begin{{center}}
        \\includegraphics[width=0.3\\textwidth]{{{form.signature_url}}}
    \\end{{center}}
    
    \\vfill
    \\noindent
    Date: \\today
    
    \\end{{document}}
    """
    return latex_content

# Admin Routes
@app.route('/admin_home')
def admin_home():
    if 'user' not in session:
        return redirect(url_for('index'))
    return render_template(
        'admin.html',
        user_name=f"{session['user']['first_name']} {session['user'].get('middle_name', '').strip()} {session['user']['last_name']}".strip()
    )

@app.route('/admin_create_user')
def admin_create_user():
    if 'user' not in session:
        return redirect(url_for('index'))
    return render_template('admin-create-user.html')

@app.route('/admin_delete_user')
def admin_delete_user():
    if 'user' not in session:
        return redirect(url_for('index'))
    return render_template('admin-delete-user.html')

@app.route('/admin_edit_profile')
def admin_edit_profile():
    if 'user' not in session:
        return redirect(url_for('index'))
    return render_template('admin-edit-profile.html', user=session['user'])

@app.route('/admin_update_user')
def admin_update_user():
    if 'user' not in session:
        return redirect(url_for('index'))
    return render_template('admin-update-user.html')

@app.route('/admin_view_profile')
def admin_view_profile():
    if 'user' not in session:
        return redirect(url_for('index'))
    return render_template('admin-view-profile.html', user=session['user'])

@app.route('/admin_view_users')
def admin_view_users():
    if 'user' not in session:
        return redirect(url_for('index'))
    return render_template('admin-view-user.html')

@app.route('/admin_user_forms')
def admin_user_forms():
    if 'user' not in session:
        return redirect(url_for('index'))
    return render_template('admin-user-forms.html')

@app.route('/admin_request_forms')
def admin_request_forms():
    if 'user' not in session:
        return redirect(url_for('index'))

    # Fetch all submitted forms
    requests = ReleaseFormRequest.query.all()
    return render_template('admin-request-forms.html', requests=requests)

@app.route('/admin_previous_forms')
def admin_previous_forms():
    if 'user' not in session:
        return redirect(url_for('index'))
    return render_template('admin-previous-forms.html')

# Update user profile
@app.route('/user/profile/update', methods=['PUT'])
def update_user_profile():
    if "user" not in session:
        return jsonify({"error": "User not logged in"}), 401

    user = User.query.filter_by(email=session['user']['email']).first()
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json()
    user.first_name = data.get("first_name", user.first_name).strip()
    user.middle_name = data.get("middle_name", user.middle_name).strip() if "middle_name" in data else user.middle_name
    user.last_name = data.get("last_name", user.last_name).strip()
    
    db.session.commit()
    
    session['user'] = {
        'first_name': user.first_name,
        'middle_name': user.middle_name if user.middle_name else '',
        'last_name': user.last_name,
        'email': user.email,
        'role': user.role,
        'status': user.status
    }
    
    return jsonify({"message": "Profile updated successfully!"})

@app.route('/admin/create_user', methods=['POST'])
def create_user():
    if "user" not in session or session["user"]["role"] != "admin":
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json()
    name = data.get("name", "").strip()
    email = data.get("email", "").strip()
    role = data.get("role", "basicuser").strip().lower()
    status = data.get("status", "active").strip().lower()

    if not name or not email:
        return jsonify({"error": "Name and email are required"}), 400

    # Check if the email already exists
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        return jsonify({"error": "User with this email already exists"}), 400

    # Create new user
    new_user = User(name=name, email=email, role=role, status=status)
    db.session.add(new_user)
    db.session.commit()

    logger.info(f"Admin {session['user']['email']} created new user {email} with role {role}")

    return jsonify({"message": "User created successfully!"}), 201

# Update user information in database
@app.route('/admin/update_user/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    if "user" not in session or session["user"]["role"] != "admin":
        return jsonify({"error": "Unauthorized"}), 403

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON received"}), 400  # New check to prevent JSON errors

        # Validate required fields
        required_fields = ["first_name", "last_name", "role", "status"]
        for field in required_fields:
            if field not in data or not isinstance(data[field], str) or not data[field].strip():
                return jsonify({"error": f"Missing or invalid field: {field}"}), 400

        user.first_name = data["first_name"].strip()
        user.middle_name = data.get("middle_name", "").strip()  # Handle optional middle name
        user.last_name = data["last_name"].strip()
        user.role = data["role"].strip().lower()
        user.status = data["status"].strip().lower()

        db.session.commit()

        logger.info(f"Admin {session['user']['email']} updated user {user.email}")

        return jsonify({"message": "User updated successfully!"}), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"Database error: {str(e)}")
        return jsonify({"error": "Database error, could not update user"}), 500


# Suspend user's account
@app.route('/admin/deactivate_user/<int:user_id>', methods=['PUT'])
def deactivate_user(user_id):
    if "user" not in session or session["user"]["role"] != "admin":
        return jsonify({"error": "Unauthorized"}), 403

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json()
    new_status = data.get("status", "deactivated").strip().lower()

    # Ensure the status is valid
    if new_status not in ["active", "deactivated"]:
        return jsonify({"error": "Invalid status value"}), 400

    user.status = new_status
    db.session.commit()

    logger.info(f"Admin {session['user']['email']} suspended user {user.email}")

    return jsonify({"message": "User suspended successfully!"}), 200

# Fetch all users in database
@app.route('/admin/all_users')
def all_users():
    users = User.query.all()
    return jsonify([
        {
            "id": user.id,
            "first_name": user.first_name if user.first_name else "",
            "middle_name": user.middle_name if user.middle_name else "",
            "last_name": user.last_name if user.last_name else "",
            "email": user.email,
            "role": user.role,
            "status": user.status
        }
        for user in users
    ])

# Admin retrieve submitted PDF's
@app.route('/admin_get_pdf/<int:form_id>', methods=['GET'])
def admin_get_pdf(form_id):
    form = ReleaseFormRequest.query.get(form_id)
    if not form or not form.pdf_url:
        return jsonify({"error": "PDF not found"}), 404
    return redirect(form.pdf_url)

# Azure Blob Storage Configuration - USER'S SIGNATURE PHOTO
SIGNATURE_STORAGE_CONNECTION_STRING = "DefaultEndpointsProtocol=https;AccountName=usersignatures;AccountKey=rGwYQGqikAfq0XDTasLRbd5HTQkbVW2s8NClGZ9NGdCknqdp8MBGEo8/WEdd/GO205SYcwyOz+cL+ASt/PQdPQ==;EndpointSuffix=core.windows.net"
SIGNATURE_CONTAINER_NAME = "signatures"
STORAGE_ACCOUNT_NAME = "usersignatures"

# Azure Blob Storage Configuration - PDF's
PDF_STORAGE_CONNECTION_STRING = "DefaultEndpointsProtocol=https;AccountName=swanriverpdfs;AccountKey=ngToSF78m/0QeZVrW6cgw4xbRfhC+5AsuLJzB0vXoLroL7diVT59uvpIiklgcpc7UqyVHjVH9k5q+AStzdWBMw==;EndpointSuffix=core.windows.net"
PDF_CONTAINER_NAME = "releaseforms"

# Initialize Azure Blob Clients
signature_blob_service = BlobServiceClient.from_connection_string(SIGNATURE_STORAGE_CONNECTION_STRING)
pdf_blob_service = BlobServiceClient.from_connection_string(PDF_STORAGE_CONNECTION_STRING)

# Container Clients
signature_container_client = signature_blob_service.get_container_client(SIGNATURE_CONTAINER_NAME)
pdf_container_client = pdf_blob_service.get_container_client(PDF_CONTAINER_NAME)

# Upload user signature to Azure Blob Storage
@app.route('/upload_signature', methods=['POST'])
def upload_user_signature():
    if "user" not in session:
        return jsonify({"error": "User not logged in"}), 401

    email = session["user"]["email"]
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"error": "User not found"}), 404

    if "signature" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["signature"]
    
    try:
        # Ensure file type is allowed
        if file.filename == "":
            return jsonify({"error": "Invalid file name"}), 400
        
        allowed_extensions = {"png", "jpg", "jpeg"}
        if file.filename.split(".")[-1].lower() not in allowed_extensions:
            return jsonify({"error": "Invalid file format. Only PNG, JPG, and JPEG are allowed."}), 400

        blob_name = f"signatures/user_{user.id}.png"
        blob_client = signature_container_client.get_blob_client(blob_name)

        # Delete old signature if exists
        blob_list = container_client.list_blobs(name_starts_with=blob_name)
        if any(blob_list):
            blob_client.delete_blob()

        # Upload new signature
        blob_client.upload_blob(file.read(), overwrite=True)

        # Generate the URL
        signature_url = f"https://{STORAGE_ACCOUNT_NAME}.blob.core.windows.net/{CONTAINER_NAME}/{blob_name}"

        # Update database
        user.signature_url = signature_url
        db.session.commit()

        return jsonify({"message": "Signature uploaded successfully!", "signature_url": signature_url})

    except Exception as e:
        logging.error(f"Error uploading signature: {str(e)}")
        return jsonify({"error": f"Error uploading signature: {str(e)}"}), 500
  
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
