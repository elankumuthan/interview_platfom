from functools import wraps
from flask import redirect, url_for, flash
from flask_login import current_user

def admin_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if not current_user.is_authenticated or current_user.role != "admin":
            flash("Admin only.", "warning")
            return redirect(url_for("booking.index"))
        return fn(*a, **kw)
    return wrapper
