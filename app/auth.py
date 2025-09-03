from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from .models import db, User
from .forms import RegisterForm, LoginForm
from .security import hash_password, verify_password
from .crypto import hmac_index
from werkzeug.security import check_password_hash  # (not used anymore)

bp = Blueprint("auth", __name__)
login_manager = LoginManager()
login_manager.login_view = "auth.login"

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

@bp.route("/register", methods=["GET","POST"])
def register():
    if current_user.is_authenticated: return redirect(url_for("booking.index"))
    form = RegisterForm()
    if form.validate_on_submit():
        idx = hmac_index(form.username.data)
        if User.query.filter_by(username_hmac=idx).first():
            flash("Username already taken", "warning")
        else:
            u = User(
                username=form.username.data,
                email=form.email.data,
                role="user",
                password_hash=hash_password(form.password.data)
            )
            db.session.add(u); db.session.commit()
            flash("Account created. Please log in.", "success")
            return redirect(url_for("auth.login"))
    return render_template("register.html", form=form)

@bp.route("/login", methods=["GET","POST"])
def login():
    # limit brute force (needs limiter init in app)
    current_app.limiter.limit("10/minute")(lambda: None)()
    if current_user.is_authenticated: return redirect(url_for("booking.index"))
    form = LoginForm()
    if form.validate_on_submit():
        idx = hmac_index(form.username.data)
        u = User.query.filter_by(username_hmac=idx).first()
        if u and verify_password(u.password_hash, form.password.data):
            login_user(u)
            return redirect(url_for("booking.index"))
        flash("Invalid credentials", "danger")
    return render_template("login.html", form=form)

@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out", "info")
    return redirect(url_for("auth.login"))