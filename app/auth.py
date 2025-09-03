from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash

from .models import db, User
from .crypto import hmac_index, encrypt_field

bp = Blueprint("auth", __name__)
login_manager = LoginManager()
login_manager.login_view = "auth.login"


@login_manager.user_loader
def load_user(user_id: str):
    try:
        return User.query.get(int(user_id))
    except Exception:
        return None


@bp.route("/login", methods=["GET", "POST"])
def login():
    # Apply a per-request limit safely if limiter exists
    lim = getattr(current_app, "limiter", None)
    if lim:
        # This no-op wrapped with .limit() will still count towards the rate limit.
        lim.limit("10/minute")(lambda: None)()

    if request.method == "GET":
        return render_template("login.html")

    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""

    if not username or not password:
        flash("Username and password are required.", "warning")
        return redirect(url_for("auth.login"))

    u = User.query.filter_by(username_hmac=hmac_index(username)).first()
    if not u or not check_password_hash(u.password_hash, password):
        flash("Invalid credentials.", "danger")
        return redirect(url_for("auth.login"))

    login_user(u)
    flash("Logged in.", "success")
    # Go to calendar by default
    return redirect(url_for("booking.calendar_view"))


@bp.route("/register", methods=["GET", "POST"])
def register():
    # Optional: you can remove this whole route if you don't expose self-signup.
    lim = getattr(current_app, "limiter", None)
    if lim:
        lim.limit("5/minute")(lambda: None)()

    if request.method == "GET":
        return render_template("register.html")

    username = (request.form.get("username") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    confirm = request.form.get("confirm") or ""

    if not username or not email or not password:
        flash("All fields are required.", "warning")
        return redirect(url_for("auth.register"))
    if password != confirm:
        flash("Passwords do not match.", "warning")
        return redirect(url_for("auth.register"))

    # Check if user/email exists via HMAC indexes
    if User.query.filter_by(username_hmac=hmac_index(username)).first():
        flash("Username already taken.", "warning")
        return redirect(url_for("auth.register"))
    if User.query.filter_by(email_hmac=hmac_index(email)).first():
        flash("Email already registered.", "warning")
        return redirect(url_for("auth.register"))

    u = User(
        username_enc=encrypt_field(username),
        email_enc=encrypt_field(email),
        username_hmac=hmac_index(username),
        email_hmac=hmac_index(email),
        password_hash=generate_password_hash(password),
        role="user",
    )
    db.session.add(u)
    db.session.commit()

    flash("Account created. Please log in.", "success")
    return redirect(url_for("auth.login"))


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out.", "success")
    return redirect(url_for("auth.login"))
