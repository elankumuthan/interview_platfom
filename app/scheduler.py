import logging
from datetime import datetime, timezone
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from flask import current_app
from .models import db, Booking

log = logging.getLogger(__name__)
_scheduler = None
_flask_app = None


def init_scheduler(app):
    global _scheduler, _flask_app
    _flask_app = app
    jobstores = {"default": SQLAlchemyJobStore(url=app.config["SQLALCHEMY_DATABASE_URI"])}
    _scheduler = BackgroundScheduler(jobstores=jobstores, timezone="UTC")
    _scheduler.start()
    log.info("APScheduler started")


def _job_run_booking(booking_id: int):
    # Ensure we have flask app context when job fires
    with _flask_app.app_context():
        try:
            booking = Booking.query.get(booking_id)
            if not booking:
                current_app.log_db("ERROR", "run_booking", "Booking not found", booking_id=booking_id)
                return
            if not booking.approved:
                current_app.log_db("INFO", "run_booking", "Booking not approved; skipping", booking_id=booking.id)
                return

            current_app.log_db(
                "INFO", "run_booking", "Starting workflow",
                booking_id=booking.id, start_at=str(booking.start_at), vm=booking.vm_name, disk=booking.disk_name
            )

            from .vm_management_functions import run_workflow_for_booking
            result = run_workflow_for_booking(booking)  # dict with steps

            booking.last_run_at = datetime.now(timezone.utc)
            booking.last_status = "success"
            booking.last_error = None
            db.session.commit()

            current_app.log_db("INFO", "run_booking", "Workflow finished", booking_id=booking.id, **(result or {}))

        except Exception as e:
            log.exception("Job failed for booking %s", booking_id)
            try:
                booking = Booking.query.get(booking_id)
                if booking:
                    booking.last_run_at = datetime.now(timezone.utc)
                    booking.last_status = "error"
                    booking.last_error = str(e)
                    db.session.commit()
            except Exception:
                pass
            current_app.log_db("ERROR", "run_booking", f"Exception: {e}", booking_id=booking_id)


def schedule_booking(booking: Booking):
    """Call after creating/approving a booking."""
    run_time = booking.start_at.astimezone(timezone.utc)
    job = _scheduler.add_job(
        _job_run_booking,
        trigger="date",
        run_date=run_time,
        args=[booking.id],
        id=f"booking-{booking.id}",
        replace_existing=True,
        coalesce=True,
        misfire_grace_time=300,
        max_instances=1,
    )
    current_app.log_db("INFO", "schedule", "Job scheduled", booking_id=booking.id, run_date=str(run_time))
    return job


def run_booking_now(booking_id: int):
    """Admin button – enqueue immediate run."""
    job = _scheduler.add_job(
        _job_run_booking,
        trigger="date",
        run_date=datetime.now(timezone.utc),
        args=[booking_id],
        id=f"booking-now-{booking_id}",
        replace_existing=True,
    )
    current_app.log_db("INFO", "schedule", "Job queued for immediate run", booking_id=booking_id)
    return job
