from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from .models import db, Booking, JobLog
from .scheduler import run_booking_now

bp = Blueprint("admin", __name__, url_prefix="/admin")


def _is_admin():
    return current_user.is_authenticated and getattr(current_user, "role", "") == "admin"


@bp.before_request
def _guard_admin():
    if not _is_admin():
        return redirect(url_for("auth.login"))


@bp.get("/")
@login_required
def admin_home():
    bookings = Booking.query.order_by(Booking.start_at.desc()).all()
    return render_template("admin.html", bookings=bookings)


@bp.get("/logs")
@login_required
def admin_logs():
    logs = JobLog.query.order_by(JobLog.created_at.desc()).limit(200).all()
    return render_template("logs.html", logs=logs)


@bp.post("/bookings/<int:booking_id>/run-now")
@login_required
def admin_run_now(booking_id):
    run_booking_now(booking_id)
    flash("Job queued to run immediately", "success")
    return redirect(url_for("admin.admin_home"))
