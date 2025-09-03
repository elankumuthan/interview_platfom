# app/scheduler.py
from __future__ import annotations
import logging
from datetime import datetime, timezone
from apscheduler.schedulers.background import BackgroundScheduler

# Global refs so jobs can enter an app context
SCHEDULER: BackgroundScheduler | None = None
APPREF = None

log = logging.getLogger(__name__)

def init_scheduler(app):
    """
    Create and start a BackgroundScheduler and stash it on the app.
    Call this once from create_app().
    """
    global SCHEDULER, APPREF
    if SCHEDULER:
        return SCHEDULER
    APPREF = app
    SCHEDULER = BackgroundScheduler(timezone="UTC")
    SCHEDULER.start()
    app.extensions["scheduler"] = SCHEDULER
    log.info("APScheduler started (timezone=UTC)")
    return SCHEDULER


def _job_run_booking(booking_id: int):
    """
    Actual job body. Runs inside a Flask app context.
    """
    from .models import db, Booking
    from flask import current_app

    app = APPREF
    if not app:
        log.error("No Flask app reference available; cannot run booking_id=%s", booking_id)
        return

    with app.app_context():
        b = Booking.query.get(booking_id)
        if not b:
            app.logger.error("Booking %s not found", booking_id)
            return

        app.logger.info("[JOB] Start booking_id=%s status=%s", b.id, b.status)
        try:
            # Call into the Azure orchestrator (stub logs by default)
            from .azure_orchestrator import run_booking
            run_booking(b)  # should update status/disk_name as appropriate
            app.logger.info("[JOB] Booking %s completed with status=%s disk=%s",
                            b.id, b.status, getattr(b, "disk_name", None))
        except Exception as e:
            app.logger.exception("[JOB] Booking %s failed: %s", b.id, e)
            b.status = "failed"
            db.session.commit()


def schedule_booking_job(booking_id: int, run_at_utc: datetime):
    """
    Public API used by bookings.py — schedule a one-time run at `run_at_utc` (UTC).
    """
    global SCHEDULER
    if SCHEDULER is None and APPREF:
        SCHEDULER = APPREF.extensions.get("scheduler")

    if SCHEDULER is None:
        log.error("Scheduler not initialized; cannot schedule booking_id=%s", booking_id)
        return

    if run_at_utc.tzinfo is None:
        # force UTC if naive
        run_at_utc = run_at_utc.replace(tzinfo=timezone.utc)

    job_id = f"booking-{booking_id}-start"
    SCHEDULER.add_job(
        _job_run_booking,
        "date",
        id=job_id,
        run_date=run_at_utc.astimezone(timezone.utc),
        args=[booking_id],
        replace_existing=True,
        misfire_grace_time=300,
    )
    log.info("Scheduled booking_id=%s at %s (job_id=%s)",
             booking_id, run_at_utc.isoformat(), job_id)


def run_booking_now(booking_id: int):
    """
    Convenience for the admin “Start now” button — just run immediately.
    """
    _job_run_booking(booking_id)
