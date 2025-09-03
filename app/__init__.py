import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask
from dotenv import load_dotenv
from .models import db, migrate, JobLog
from .auth import login_manager
from .scheduler import init_scheduler


def _setup_logging(app: Flask):
    # Console logs (docker)
    root = logging.getLogger()
    root.setLevel(os.environ.get("LOG_LEVEL", "INFO"))
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s"))
    root.handlers = [ch]

    # Optional file log
    if os.environ.get("FILE_LOG", "").lower() == "1":
        fh = RotatingFileHandler("/tmp/app.log", maxBytes=5_000_000, backupCount=2)
        fh.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s"))
        root.addHandler(fh)

    # Azure SDK logs (noisy — keep WARNING unless debugging)
    logging.getLogger("azure").setLevel(os.environ.get("AZURE_LOG_LEVEL", "WARNING"))
    logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(
        os.environ.get("AZURE_HTTP_LOG_LEVEL", "WARNING")
    )


def log_db(level: str, action: str, message: str, booking_id=None, **ctx):
    """Persist a structured log row; never crash caller on error."""
    try:
        rec = JobLog(level=level.upper(), action=action, message=message, booking_id=booking_id, context=ctx or None)
        db.session.add(rec)
        db.session.commit()
    except Exception as e:
        logging.getLogger(__name__).warning("Failed to write JobLog: %s", e)


def create_app():
    load_dotenv()
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ["DATABASE_URL"]
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SITE_NAME"] = os.environ.get("SITE_NAME", "Interview Booking")
    app.config["SCHEDULER_ENABLED"] = os.environ.get("SCHEDULER_ENABLED", "1") == "1"

    _setup_logging(app)
    app.log_db = log_db  # allow current_app.log_db(...)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    # Blueprints
    from .auth import bp as auth_bp
    from .bookings import bp as booking_bp
    from .admin import bp as admin_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(booking_bp)
    app.register_blueprint(admin_bp)

    # Scheduler
    if app.config["SCHEDULER_ENABLED"]:
        init_scheduler(app)

    @app.get("/health")
    def health():
        return {"ok": True}

    # CLI: init DB + admin user
    @app.cli.command("db_init")
    def db_init():
        from .models import User
        from werkzeug.security import generate_password_hash
        from .crypto import hmac_index, encrypt_field

        with app.app_context():
            db.create_all()  # creates new tables like job_log if missing
            admin_user = os.environ.get("ADMIN_USERNAME", "interviewadmin")
            admin_pass = os.environ.get("ADMIN_PASSWORD", "ChangeMeNow!")
            admin_email = os.environ.get("ADMIN_EMAIL", "admin@example.com")

            existing = User.query.filter_by(username_hmac=hmac_index(admin_user)).first()
            if not existing:
                u = User(
                    username_enc=encrypt_field(admin_user),
                    email_enc=encrypt_field(admin_email),
                    username_hmac=hmac_index(admin_user),
                    email_hmac=hmac_index(admin_email),
                    password_hash=generate_password_hash(admin_pass),
                    role="admin",
                )
                db.session.add(u)
                db.session.commit()
                print(f"Created admin user '{admin_user}'")
            else:
                print("Admin user exists")

    return app
