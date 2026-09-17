from flask import Blueprint, redirect, render_template, url_for
from flask_login import current_user

public_bp = Blueprint("public", __name__, template_folder="../templates/public")


@public_bp.route("/")
def home():
    if current_user.is_authenticated:
        return redirect(url_for("auth.post_login_redirect"))
    return render_template("public/home.html")
