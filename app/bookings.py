# app/bookings.py
from __future__ import annotations
import os
from datetime import datetime, timedelta
import pytz
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from .models import db, Booking
from .forms import BookingForm
from .scheduler import schedule_booking_job

bp = Blueprint("booking", __name__)

# Config toggles (read env directly so you don't have to change create_app)
DEFAULT_TZ = os.getenv("DEFAULT_TZ", "Asia/Singapore")
AUTO_APPROVE_ON_SUBMIT = os.getenv("AUTO_APPROVE_ON_SUBMIT", "false").lower() == "true"
MIN_DURATION_MINUTES = int(os.getenv("MIN_DURATION_MINUTES", "30"))
MAX_DURATION_HOURS = float(os.getenv("MAX_DURATION_HOURS", "6"))


@bp.route("/")
def index():
    return render_template("index.html")


@bp.route("/calendar")
@login_required
def calendar_view():
    # Calendar UI
    return render_template("calendar.html")


@bp.route("/api/availability")
@login_required
def api_availability():
    """
    FullCalendar feed.
    - Non-admins: just see 'Unavailable' for approved/running blocks
    - Admins: see username + status for all bookings
    """
    events = []
    # Show everything to admins; show only 'approved'/'running' as blocks to users
    if current_user.is_admin():
        qs = Booking.query.order_by(Booking.start_at_utc.asc()).all()
    else:
        qs = Booking.query.filter(Booking.status.in_(("approved", "running")))\
                          .order_by(Booking.start_at_utc.asc()).all()

    for b in qs:
        if current_user.is_admin():
            title = f"{b.user.username} ({b.status})"
            color = "#4f46e5" if b.status in ("approved", "running") else "#9ca3af"
        else:
            title = "Unavailable"
            color = "#8888ff"

        events.append({
            "id": b.id,
            "title": title,
            "start": b.start_at_utc.isoformat(),
            "end": b.end_at_utc.isoformat(),
            "color": color
        })
    return jsonify(events)


@bp.route("/book", methods=["GET", "POST"])
@login_required
def book():
    """
    Create a booking. If AUTO_APPROVE_ON_SUBMIT=true (or the user is admin),
    mark it approved and schedule immediately; otherwise leave as pending.
    """
    form = BookingForm()
    if form.validate_on_submit():
        # Resolve timezone
        try:
            tz = pytz.timezone(DEFAULT_TZ)
        except Exception:
            tz = pytz.utc

        # Build localized datetimes from form (date + start_time/end_time)
        start_local = tz.localize(datetime.combine(form.date.data, form.start_time.data))
        end_local   = tz.localize(datetime.combine(form.date.data, form.end_time.data))

        # Normalize to UTC
        start_utc = start_local.astimezone(pytz.utc)
        end_utc   = end_local.astimezone(pytz.utc)

        # Validation: start before end
        if end_utc <= start_utc:
            flash("End time must be after start time.", "danger")
            return redirect(url_for("booking.book"))

        # Validation: reasonable duration
        duration = end_utc - start_utc
        if duration < timedelta(minutes=MIN_DURATION_MINUTES):
            flash(f"Minimum duration is {MIN_DURATION_MINUTES} minutes.", "warning")
            return redirect(url_for("booking.book"))
        if duration > timedelta(hours=MAX_DURATION_HOURS):
            flash(f"Maximum duration is {MAX_DURATION_HOURS:g} hours.", "warning")
            return redirect(url_for("booking.book"))

        # Overlap check against approved/running bookings
        overlap = Booking.query.filter(
            Booking.status.in_(("approved", "running")),
            Booking.end_at_utc > start_utc,
            Booking.start_at_utc < end_utc
        ).first()
        if overlap:
            flash("That time window is blocked. Pick another time.", "warning")
            return redirect(url_for("booking.book"))

        # Decide initial status
        will_auto_approve = AUTO_APPROVE_ON_SUBMIT or current_user.is_admin()
        status = "approved" if will_auto_approve else "pending"

        # Persist booking
        b = Booking(
            user_id=current_user.id,
            start_at_utc=start_utc,
            end_at_utc=end_utc,
            status=status
        )
        db.session.add(b)
        db.session.commit()

        # If approved now, schedule the job right away
        if status == "approved":
            try:
                schedule_booking_job(b.id, b.start_at_utc)
                current_app.logger.info(
                    "[BOOK] Auto-approved & scheduled booking_id=%s for %s",
                    b.id, b.start_at_utc.isoformat()
                )
                flash("Slot booked and scheduled.", "success")
            except Exception as e:
                current_app.logger.exception("[BOOK] Failed to schedule booking %s: %s", b.id, e)
                flash("Booking saved, but scheduling failed. Check logs.", "danger")
        else:
            flash("Slot requested. Awaiting admin approval.", "success")

        return redirect(url_for("booking.calendar_view"))

    return render_template("book.html", form=form)
