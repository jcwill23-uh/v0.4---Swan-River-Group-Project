from flask import Blueprint, render_template

# Create a Blueprint for basic user routes
basic_user_bp = Blueprint("basic_user", __name__)

@basic_user_bp.route("/basic_user_view")
def basic_user_view():
    return render_template("basic_user_view.html")

@basic_user_bp.route("/basic_user_edit")
def basic_user_edit():
    return render_template("basic_user_edit.html")
