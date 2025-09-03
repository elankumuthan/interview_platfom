# app/azure_orchestrator.py
from __future__ import annotations
import os
from datetime import datetime, timezone
from flask import current_app
from .models import db, Booking

def run_booking(booking: Booking):
    """
    Do the actual Azure work for a booking.
    This version logs steps and updates DB. Replace the 'REAL AZURE CALLS' block with your code.
    """
    app = current_app

    # Decide a disk name; adjust to your rule (<name>-kali2-disk).
    # Using username here; sanitize if needed.
    disk_name = f"{booking.user.username}-kali2-disk"

    target_vm = os.getenv("AZ_VM_NAME", "user2-kali-vm")
    rg       = os.getenv("AZ_RESOURCE_GROUP", "")
    subs     = os.getenv("AZ_SUBSCRIPTION_ID", "")
    location = os.getenv("AZ_LOCATION", "")

    app.logger.info("[AZ] Booking %s -> VM:%s RG:%s SUB:%s disk:%s",
                    booking.id, target_vm, rg, subs, disk_name)

    # --- REAL AZURE CALLS GO HERE -----------------------------------------
    #
    # Example if you have vm_management_functions.py with these helpers:
    #
    #   import vm_management_functions as vmf
    #   vmf.stop_vm(subs, rg, target_vm)
    #   vmf.create_disk_from_source(subs, rg, disk_name, source_disk_or_snapshot, location)
    #   vmf.swap_os_disk(subs, rg, target_vm, disk_name)
    #   vmf.start_vm(subs, rg, target_vm)
    #
    # Make sure these functions raise on failure so we can mark the booking failed.
    #
    # ----------------------------------------------------------------------

    # For now, just log + mark as running to prove the job pipeline works.
    booking.status   = "running"
    booking.disk_name = disk_name
    booking.started_at_utc = datetime.now(timezone.utc)
    db.session.commit()

    app.logger.info("[AZ] Marked booking %s as running; disk=%s", booking.id, disk_name)
