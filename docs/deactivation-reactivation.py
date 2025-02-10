from flask import Blueprint, request, redirect, url_for, flash
from models import db, User

admin_bp = Blueprint("admin", __name__)

@admin_bp.route("/admin/deactivate/<int:user_id>", methods=["POST"])
def deactivate_user(user_id):
    user = User.query.get(user_id)
    if user:
        user.is_active = False
        db.session.commit()
        flash(f"User {user.name} has been deactivated.", "success")
    return redirect(url_for("admin_dashboard"))

@admin_bp.route("/admin/reactivate/<int:user_id>", methods=["POST"])
def reactivate_user(user_id):
    user = User.query.get(user_id)
    if user:
        user.is_active = True
        db.session.commit()
        flash(f"User {user.name} has been reactivated.", "success")
    return redirect(url_for("admin_dashboard"))
