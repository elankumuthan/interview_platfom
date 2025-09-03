from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from datetime import datetime, timezone
import pytz

_scheduler = None

def init_scheduler(app):
    global _scheduler
    # Persistent jobstore in the same DB
    jobstores = {"default": SQLAlchemyJobStore(url=app.config["SQLALCHEMY_DATABASE_URI"])}
    _scheduler = BackgroundScheduler(jobstores=jobstores, timezone="Asia/Singapore")
    _scheduler.start()

    # Expose on app if you want
    app.scheduler = _scheduler

def schedule_booking_job(booking_id: int, start_at_utc: datetime):
    # run_date expects local tz (scheduler tz). Convert UTC -> Asia/Singapore.
    tz = pytz.timezone("Asia/Singapore")
    run_local = start_at_utc.replace(tzinfo=timezone.utc).astimezone(tz)
    _scheduler.add_job(
        func=_job_run_booking,
        trigger="date",
        run_date=run_local,
        args=[booking_id],
        id=f"booking-{booking_id}",
        replace_existing=True,
        misfire_grace_time=3600
    )

def run_booking_now(booking_id: int):
    _scheduler.add_job(
        func=_job_run_booking,
        trigger="date",
        run_date=datetime.now(pytz.timezone("Asia/Singapore")),
        args=[booking_id],
        id=f"booking-now-{booking_id}",
        replace_existing=True
    )

def _job_run_booking(booking_id: int):
    # Import inside to avoid circulars
    from flask import current_app
    from .models import db, Booking, User
    from .vm_management import perform_vm_sequence

    with current_app.app_context():
        booking = db.session.get(Booking, booking_id)
        if not booking or booking.status not in ("approved", "pending"):
            return
        booking.status = "running"; db.session.commit()

        user = db.session.get(User, booking.user_id)
        try:
            # Disk name pattern: <username>-kali2-disk-YYYYMMDDHHMMSS
            disk_name = perform_vm_sequence(username=user.username)
            booking.disk_name = disk_name
            booking.status = "running"  # or keep running until you add an auto-complete
            db.session.commit()
        except Exception as e:
            booking.status = "failed"
            db.session.commit()
            raise
