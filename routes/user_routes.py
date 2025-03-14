from flask import Blueprint, session, render_template, request, jsonify, redirect, url_for
from models import User, ReleaseFormRequest, db
import logging
from azure.storage.blob import BlobServiceClient
from datetime import datetime
import subprocess

user_bp = Blueprint('user', __name__)
logger = logging.getLogger(__name__)

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

@user_bp.route('/basic_user_home')
def basic_user_home():
    if 'user' not in session:
        return redirect(url_for('auth.index'))
    return render_template('basic_user_home.html', user=session['user'])

@user_bp.route('/basic_user_view')
def basic_user_view():
    if 'user' not in session:
        return redirect(url_for('index'))
    return render_template("basic_user_view.html", user=session['user'])

@user_bp.route('/basic_user_edit')
def basic_user_edit():
    if 'user' not in session:
        return redirect(url_for('index'))
    return render_template("basic_user_edit.html", user=session['user'])

@user_bp.route('/basic_user_forms')
def basic_user_forms():
    if 'user' not in session:
        return redirect(url_for('auth.index'))
    email = session['user']['email']
    user = User.query.filter_by(email=email).first()
    signature_url = user.signature_url if user else ""
    return render_template("basic_user_forms.html", user=session['user'], signature_url=signature_url)

@user_bp.route('/basic_user_release')
def basic_user_release():
    if 'user' not in session:
        return redirect(url_for('index'))
    # Fetch user's signature from the database
    email = session['user']['email']
    user = User.query.filter_by(email=email).first()
    # Get the signature URL (if exists)
    signature_url = user.signature_url if user and user.signature_url else ""
    return render_template("basic_user_release.html", user=session['user'], signature_url=signature_url)

@user_bp.route('/basic_user_ssn')
def basic_user_ssn():
    if 'user' not in session:
        return redirect(url_for('index'))
    # Fetch user's signature from the database
    email = session['user']['email']
    user = User.query.filter_by(email=email).first()
    # Get the signature URL (if exists)
    signature_url = user.signature_url if user and user.signature_url else ""
    return render_template("basic_user_ssn.html", user=session['user'], signature_url=signature_url)

@user_bp.route('/basic_user_form_status')
def basic_user_form_status():
    if 'user' not in session:
        return redirect(url_for('index'))
    
    # Fetch user's email from session
    email = session['user']['email']
    user = User.query.filter_by(email=email).first()
    
    # Fetch release form requests for this user by matching their name
    user_full_name = f"{user.first_name} {user.middle_name or ''} {user.last_name}".strip()
    requests = ReleaseFormRequest.query.filter(
        ReleaseFormRequest.student_name.like(f"%{user_full_name}%")
    ).all()
    
    return render_template("basic_user_form_status.html", user=session['user'], requests=requests)

@user_bp.route('/submit_release_form', methods=['POST'])
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

        user = User.query.filter_by(email=session["user"]["email"]).first()
        if not user:
            return jsonify({"error": "User not found"}), 404

        pdf_dir = "/mnt/data"
        os.makedirs(pdf_dir, exist_ok=True)
        tex_file_path = os.path.join(pdf_dir, f"form_{new_request.id}.tex")
        pdf_file_path = os.path.join(pdf_dir, f"form_{new_request.id}.pdf")

        with open(tex_file_path, "w") as tex_file:
            tex_file.write(generate_latex_content(new_request, user))

        try:
            result = subprocess.run(
                ["/usr/bin/pdflatex", "-output-directory", pdf_dir, tex_file_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True
            )
        except subprocess.CalledProcessError as e:
            return jsonify({"error": f"PDF generation failed: {e.stderr.decode()}"}), 500
        except FileNotFoundError:
            return jsonify({"error": "pdflatex not found. Make sure LaTeX is installed."}), 500

        blob_name = f"release_forms/form_{new_request.id}.pdf"
        blob_client = pdf_container_client.get_blob_client(blob_name)

        with open(pdf_file_path, "rb") as data:
            blob_client.upload_blob(data, overwrite=True)

        new_request.pdf_url = f"https://{pdf_blob_service.account_name}.blob.core.windows.net/{PDF_CONTAINER_NAME}/{blob_name}"
        user.pdf_url = f"https://{pdf_blob_service.account_name}.blob.core.windows.net/{PDF_CONTAINER_NAME}/{blob_name}"
        db.session.commit()

        return jsonify({"message": "Form submitted successfully", "pdf_url": new_request.pdf_url}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Generate latex content for release form
def generate_latex_content(form, user):
    # Ensure signature file path is valid
    if form.signature_url and form.signature_url.strip():
        signature_path = form.signature_url
    else:
        signature_path = "/mnt/data/default-signature.png"  # Ensure a default exists

    print(f"Using signature path: {signature_path}")  # Debugging output

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
        \\IfFileExists{{{signature_path}}}{{\\includegraphics[width=0.3\\textwidth]{{{signature_path}}}}}{{\\textbf{{No signature on file.}}}}
    \\end{{center}}
    
    \\vfill
    \\noindent
    Date: \\today
    
    \\end{{document}}
    """
    return latex_content

# Update user profile
@user_bp.route('/user/profile/update', methods=['PUT'])
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

# Upload user signature to Azure Blob Storage
@user_bp.route('/upload_signature', methods=['POST'])
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
        blob_list = signature_container_client.list_blobs(name_starts_with=blob_name)
        if any(blob_list):
            blob_client.delete_blob()

        # Upload new signature
        blob_client.upload_blob(file.read(), overwrite=True)

        # Generate the URL
        signature_url = f"https://{STORAGE_ACCOUNT_NAME}.blob.core.windows.net/{SIGNATURE_CONTAINER_NAME}/{blob_name}"

        # Update database
        user.signature_url = signature_url
        db.session.commit()

        return jsonify({"message": "Signature uploaded successfully!", "signature_url": signature_url})

    except Exception as e:
        logging.error(f"Error uploading signature: {str(e)}")
        return jsonify({"error": f"Error uploading signature: {str(e)}"}), 500