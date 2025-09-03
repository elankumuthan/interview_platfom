from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user
from datetime import datetime
import pytz
from .models import db, Booking, User
from .forms import BookingForm
from .scheduler import schedule_booking_job

bp = Blueprint("booking", __name__)

@bp.route("/")
def index():
    return render_template("index.html")

@bp.route("/calendar")
@login_required
def calendar_view():
    # shows blocked (approved/running) slots without names to non-admins
    return render_template("calendar.html")

@bp.route("/api/availability")
@login_required
def api_availability():
    # Return events for FullCalendar
    # Users see only 'Unavailable'. Admins see usernames.
    events = []
    for b in Booking.query.all():
        title = "Unavailable"
        if current_user.is_admin():
            u = b.user.username
            title = f"{u} ({b.status})"
        events.append({
            "id": b.id,
            "title": title,
            "start": b.start_at_utc.isoformat(),
            "end": b.end_at_utc.isoformat(),
            "color": "#8888ff" if b.status in ("approved","running") else "#cccccc"
        })
    return jsonify(events)

@bp.route("/book", methods=["GET","POST"])
@login_required
def book():
    form = BookingForm()
    if form.validate_on_submit():
        tz = pytz.timezone("Asia/Singapore")
        start_local = tz.localize(datetime.combine(form.date.data, form.start_time.data))
        end_local   = tz.localize(datetime.combine(form.date.data, form.end_time.data))
        start_utc, end_utc = start_local.astimezone(pytz.utc), end_local.astimezone(pytz.utc)

        # Basic overlap check against approved/running bookings
        overlap = Booking.query.filter(
            Booking.status.in_(("approved","running")),
            Booking.end_at_utc > start_utc,
            Booking.start_at_utc < end_utc
        ).first()
        if overlap:
            flash("That time window is blocked. Pick another time.", "warning")
            return redirect(url_for("booking.book"))

        b = Booking(user_id=current_user.id, start_at_utc=start_utc, end_at_utc=end_utc, status="pending")
        db.session.add(b); db.session.commit()
        flash("Slot requested. Awaiting admin approval.", "success")
        return redirect(url_for("booking.calendar_view"))
    return render_template("book.html", form=form)
