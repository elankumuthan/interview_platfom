from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import UserMixin
from datetime import datetime, timezone
from sqlalchemy import LargeBinary
from .crypto import enc_str, dec_str, hmac_index

db = SQLAlchemy()
migrate = Migrate()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # encrypted blobs
    _username_enc = db.Column("username_enc", LargeBinary, nullable=False)
    _email_enc    = db.Column("email_enc",    LargeBinary, nullable=False)
    # deterministic HMAC indexes for lookups (no plaintext storage)
    username_hmac = db.Column(db.String(64), unique=True, index=True, nullable=False)
    email_hmac    = db.Column(db.String(64), unique=True, index=True, nullable=False)

    password_hash = db.Column(db.String(255), nullable=False)  # Argon2 hash
    role = db.Column(db.String(16), default="user")

    # properties – app code uses .username / .email; DB stores only enc + hmac
    @property
    def username(self) -> str:
        return dec_str(self._username_enc)

    @username.setter
    def username(self, value: str):
        self._username_enc = enc_str(value)
        self.username_hmac = hmac_index(value)

    @property
    def email(self) -> str:
        return dec_str(self._email_enc)

    @email.setter
    def email(self, value: str):
        self._email_enc = enc_str(value)
        self.email_hmac = hmac_index(value)

    def is_admin(self):
        return self.role == "admin"

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    user = db.relationship("User", backref="bookings")
    start_at_utc = db.Column(db.DateTime, nullable=False)
    end_at_utc = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(16), default="pending")
    disk_name = db.Column(db.String(128))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
