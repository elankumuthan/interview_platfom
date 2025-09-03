# app/auth.py
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from .models import db, User
from .forms import LoginForm
from .crypto import hmac_index
from .extensions import limiter  # use the shared limiter instance

bp = Blueprint("auth", __name__)
login_manager = LoginManager()
login_manager.login_view = "auth.login"

@login_manager.user_loader
def load_user(user_id):
    try:
        return User.query.get(int(user_id))
    except Exception:
        return None

@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10/minute", methods=["POST"], error_message="Too many login attempts, please wait a minute and try again.")
def login():
    # Always create a form so GET renders can use {{ form.* }}
    form = LoginForm()

    if request.method == "GET":
        return render_template("login.html", form=form)

    # POST:
    if form.validate_on_submit():
        username = (form.username.data or "").strip()
        password = form.password.data or ""

        user = User.query.filter_by(username_hmac=hmac_index(username)).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user, remember=form.remember_me.data if hasattr(form, "remember_me") else False)
            flash("Welcome back!", "success")
            next_url = request.args.get("next") or url_for("booking.calendar_view")
            return redirect(next_url)

        flash("Invalid username or password.", "danger")
        return render_template("login.html", form=form), 401

    # Form failed validation (e.g., CSRF)
    return render_template("login.html", form=form), 400

@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
