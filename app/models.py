from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import JSONB

db = SQLAlchemy()
migrate = Migrate()


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username_enc = db.Column(db.LargeBinary, nullable=False)
    email_enc = db.Column(db.LargeBinary, nullable=False)
    username_hmac = db.Column(db.String(64), nullable=False, index=True, unique=True)
    email_hmac = db.Column(db.String(64), nullable=False, index=True, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="user")


class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_hmac = db.Column(db.String(64), nullable=False, index=True)
    start_at = db.Column(db.DateTime(timezone=True), nullable=False)
    end_at = db.Column(db.DateTime(timezone=True), nullable=False)
    approved = db.Column(db.Boolean, default=False, nullable=False)
    vm_name = db.Column(db.String(128), nullable=True)
    disk_name = db.Column(db.String(128), nullable=True)

    # Quick status fields for visibility
    last_run_at = db.Column(db.DateTime(timezone=True))
    last_status = db.Column(db.String(32))
    last_error = db.Column(db.Text)


class JobLog(db.Model):
    __tablename__ = "job_log"
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    level = db.Column(db.String(16), nullable=False)   # INFO/WARN/ERROR
    action = db.Column(db.String(64), nullable=False)  # run_booking/start_vm/swap_os_disk/...
    booking_id = db.Column(db.Integer, db.ForeignKey("booking.id"), nullable=True, index=True)
    message = db.Column(db.Text, nullable=False)
    context = db.Column(JSONB, nullable=True)

    booking = db.relationship("Booking", backref="logs")
