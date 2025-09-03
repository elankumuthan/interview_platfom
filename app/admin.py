from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from .models import db, Booking
from .scheduler import schedule_booking_job, run_booking_now

bp = Blueprint("admin", __name__, url_prefix="/admin")

def admin_required(fn):
    from functools import wraps
    @wraps(fn)
    def wrapper(*a, **kw):
        if not current_user.is_authenticated or not current_user.is_admin():
            flash("Admin only.", "warning")
            return redirect(url_for("booking.index"))
        return fn(*a, **kw)
    return wrapper

@bp.route("/")
@login_required
@admin_required
def dashboard():
    bookings = Booking.query.order_by(Booking.start_at_utc.desc()).all()
    return render_template("admin.html", bookings=bookings)

@bp.route("/approve/<int:booking_id>")
@login_required
@admin_required
def approve(booking_id):
    b = db.session.get(Booking, booking_id)
    if not b:
        flash("Not found", "danger"); return redirect(url_for("admin.dashboard"))
    b.status = "approved"; db.session.commit()
    schedule_booking_job(b.id, b.start_at_utc)  # schedule background job at start time
    flash("Approved and scheduled.", "success")
    return redirect(url_for("admin.dashboard"))

@bp.route("/reject/<int:booking_id>")
@login_required
@admin_required
def reject(booking_id):
    b = db.session.get(Booking, booking_id)
    if not b:
        flash("Not found", "danger"); return redirect(url_for("admin.dashboard"))
    b.status = "rejected"; db.session.commit()
    flash("Rejected.", "info")
    return redirect(url_for("admin.dashboard"))

@bp.route("/start_now/<int:booking_id>")
@login_required
@admin_required
def start_now(booking_id):
    run_booking_now(booking_id)
    flash("Start requested.", "success")
    return redirect(url_for("admin.dashboard"))
