from flask import Flask
from dotenv import load_dotenv
import os

from .models import db, migrate
from .auth import login_manager
from .scheduler import init_scheduler

from flask_wtf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


def create_app():
    load_dotenv()

    app = Flask(__name__, template_folder="templates")

    # --- Core config ---
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or os.urandom(32)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ["DATABASE_URL"]
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SITE_NAME"] = os.environ.get("SITE_NAME", "Interview Booking")

    # Encryption/HMAC keys for PII at rest (required)
    # Generate once and set in .env: DATA_ENC_KEY (Fernet base64), DATA_HMAC_KEY (base64 32 bytes)
    app.config["DATA_ENC_KEY"] = os.environ["DATA_ENC_KEY"]
    app.config["DATA_HMAC_KEY"] = os.environ["DATA_HMAC_KEY"]

    # --- Security hardening ---
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=False,  # set True when serving over HTTPS
        WTF_CSRF_TIME_LIMIT=60 * 60 * 8,  # 8h CSRF token life
    )

    # --- Extensions ---
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    csrf = CSRFProtect()
    csrf.init_app(app)

    limiter = Limiter(
    get_remote_address,
    default_limits=["200/day", "50/hour"],
    storage_uri=os.environ.get("RATELIMIT_STORAGE_URI", "memory://"),
    )
    limiter.init_app(app)
    app.limiter = limiter

    # --- Blueprints ---
    from .auth import bp as auth_bp
    from .bookings import bp as booking_bp
    from .admin import bp as admin_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(booking_bp)
    app.register_blueprint(admin_bp)

    # --- Scheduler (persistent job store via SQLAlchemy) ---
    init_scheduler(app)

    # --- Health endpoint ---
    @app.get("/health")
    def health():
        return {"ok": True}

    # --- CLI: init DB & bootstrap admin (encrypted fields, Argon2 password) ---
    @app.cli.command("db_init")
    def db_init():
        with app.app_context():
            db.create_all()

            from .models import User
            from .crypto import hmac_index
            from .security import hash_password

            admin_user = os.environ.get("ADMIN_USERNAME", "admin")
            admin_pass = os.environ.get("ADMIN_PASSWORD", "ChangeMeNow!")
            admin_email = os.environ.get("ADMIN_EMAIL", "admin@example.com")

            existing = User.query.filter_by(username_hmac=hmac_index(admin_user)).first()
            if not existing:
                u = User(
                    username=admin_user,            # encrypted + indexed via model properties
                    email=admin_email,              # encrypted + indexed via model properties
                    role="admin",
                    password_hash=hash_password(admin_pass),  # Argon2id
                )
                db.session.add(u)
                db.session.commit()
                print(f"Created admin user '{admin_user}'")
            else:
                print("Admin user exists")

    return app
