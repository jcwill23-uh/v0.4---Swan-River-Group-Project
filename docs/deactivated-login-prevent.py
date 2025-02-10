from flask import session, redirect, url_for, flash
from werkzeug.security import check_password_hash
from models import User

def login_user(email, password):
    user = User.query.filter_by(email=email).first()
    
    if user and check_password_hash(user.password, password):
        if not user.is_active:
            flash("Your account has been deactivated. Contact an administrator.", "danger")
            return redirect(url_for("login"))
        
        session["user_id"] = user.id  # Store user in session
        return redirect(url_for("dashboard"))
    
    flash("Invalid credentials", "danger")
    return redirect(url_for("login"))
