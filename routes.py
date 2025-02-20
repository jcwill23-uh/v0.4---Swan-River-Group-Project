from flask import Blueprint, render_template
from app import db, User

# Create a Blueprint for basic user routes
basic_user_bp = Blueprint("basic_user", __name__)
user_bp = Blueprint("user", __name__)

@basic_user_bp.route("/basic_user_view")
def basic_user_view():
    return render_template("basic_user_view.html")

@basic_user_bp.route("/basic_user_edit")
def basic_user_edit():
    return render_template("basic_user_edit.html")

# Pulls user's data
@user_bp.route("/user/profile")
def user_profile():
    if "user" not in session:
        return jsonify({"error": "User not logged in"}), 401

    email = session["user"].get("email")
    user = User.query.filter_by(email=email).first()
    
    if not user:
        return jsonify({"error": "User not found"}), 404

    return jsonify({
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "status": user.status
    })
