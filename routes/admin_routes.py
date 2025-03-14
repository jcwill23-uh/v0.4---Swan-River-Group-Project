from flask import Blueprint, session, render_template, request, jsonify, redirect, url_for
from models import User, ReleaseFormRequest, db
import logging

admin_bp = Blueprint('admin', __name__)
logger = logging.getLogger(__name__)

@admin_bp.route('/admin_view_users')
def admin_view_users():
    if 'user' not in session or session['user']['role'] != 'admin':
        return redirect(url_for('auth.index'))
    users = User.query.all()
    return render_template('admin-view-user.html', users=users)

@admin_bp.route('/approve_request/<int:request_id>', methods=['POST'])
def approve_request(request_id):
    request_form = ReleaseFormRequest.query.get(request_id)
    if request_form:
        request_form.approval_status = "approved"
        db.session.commit()
        return jsonify({"message": "Request approved successfully"}), 200
    return jsonify({"error": "Request not found"}), 404

@admin_bp.route('/decline_request/<int:request_id>', methods=['POST'])
def decline_request(request_id):
    request_form = ReleaseFormRequest.query.get(request_id)
    if request_form:
        request_form.approval_status = "declined"
        db.session.commit()
        return jsonify({"message": "Request declined successfully"}), 200
    return jsonify({"error": "Request not found"}), 404

# Update user profile
@admin_bp.route('/user/profile/update', methods=['PUT'])
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

# Routing functions for site navigation
@admin_bp.route('/admin_home')
def admin_home():
    if 'user' not in session:
        return redirect(url_for('index'))
    return render_template(
        'admin.html',
        user_name=f"{session['user']['first_name']} {session['user'].get('middle_name', '').strip()} {session['user']['last_name']}".strip()
    )

@admin_bp.route('/admin_create_user')
def admin_create_user():
    if 'user' not in session:
        return redirect(url_for('index'))
    return render_template('admin-create-user.html')

@admin_bp.route('/admin_delete_user')
def admin_delete_user():
    if 'user' not in session:
        return redirect(url_for('index'))
    return render_template('admin-delete-user.html')

@admin_bp.route('/admin_edit_profile')
def admin_edit_profile():
    if 'user' not in session:
        return redirect(url_for('index'))
    return render_template('admin-edit-profile.html', user=session['user'])

@admin_bp.route('/admin_update_user')
def admin_update_user():
    if 'user' not in session:
        return redirect(url_for('index'))
    return render_template('admin-update-user.html')

@admin_bp.route('/admin_view_profile')
def admin_view_profile():
    if 'user' not in session:
        return redirect(url_for('index'))
    return render_template('admin-view-profile.html', user=session['user'])

@admin_bp.route('/admin_user_forms')
def admin_user_forms():
    if 'user' not in session:
        return redirect(url_for('index'))
    return render_template('admin-user-forms.html')

@admin_bp.route('/admin_request_forms')
def admin_request_forms():
    if 'user' not in session:
        return redirect(url_for('index'))
    
    # Fetch all submitted forms
    requests = ReleaseFormRequest.query.all()
    return render_template('admin-request-forms.html', requests=requests)

@admin_bp.route('/admin_previous_forms')
def admin_previous_forms():
    if 'user' not in session:
        return redirect(url_for('index'))
    return render_template('admin-previous-forms.html')

# Create new user
@admin_bp.route('/admin/create_user', methods=['POST'])
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
@admin_bp.route('/admin/update_user/<int:user_id>', methods=['PUT'])
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
@admin_bp.route('/admin/deactivate_user/<int:user_id>', methods=['PUT'])
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
@admin_bp.route('/admin/all_users')
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
@admin_bp.route('/admin_get_pdf/<int:form_id>', methods=['GET'])
def admin_get_pdf(form_id):
    form = ReleaseFormRequest.query.get(form_id)
    if not form or not form.pdf_url:
        return jsonify({"error": "PDF not found"}), 404
    return redirect(form.pdf_url)
