import os
import logging
from flask import current_app
from azure.identity import DefaultAzureCredential, EnvironmentCredential, AzureAuthorityHosts
from azure.core.exceptions import HttpResponseError
from azure.mgmt.compute import ComputeManagementClient

log = logging.getLogger(__name__)


def _credential():
    # Prefer explicit env-based SP if provided
    if os.getenv("AZURE_CLIENT_ID") and os.getenv("AZURE_TENANT_ID") and os.getenv("AZURE_CLIENT_SECRET"):
        log.info("Azure auth: EnvironmentCredential")
        return EnvironmentCredential(authority=os.getenv("AZURE_AUTHORITY_HOST", AzureAuthorityHosts.AZURE_PUBLIC_CLOUD))
    log.info("Azure auth: DefaultAzureCredential")
    return DefaultAzureCredential(exclude_interactive_browser_credential=True)


def _compute():
    sub_id = os.environ["AZURE_SUBSCRIPTION_ID"]
    return ComputeManagementClient(_credential(), sub_id)


def _hdr_request_ids(poller):
    try:
        return [poller._polling_method._initial_response.http_response.headers.get("x-ms-request-id")]
    except Exception:
        return []


def start_vm(resource_group: str, vm_name: str):
    compute = _compute()
    current_app.log_db("INFO", "start_vm", "Starting VM", vm=vm_name)
    try:
        poller = compute.virtual_machines.begin_start(resource_group, vm_name)
        req_ids = _hdr_request_ids(poller)
        poller.result()
        current_app.log_db("INFO", "start_vm", "VM started", vm=vm_name, request_ids=req_ids)
        return {"started": True, "request_ids": req_ids}
    except HttpResponseError as e:
        rid = getattr(e, "response", None) and e.response.headers.get("x-ms-request-id")
        current_app.log_db("ERROR", "start_vm", f"Azure error: {e}", vm=vm_name, request_id=rid)
        raise


def deallocate_vm(resource_group: str, vm_name: str):
    compute = _compute()
    current_app.log_db("INFO", "deallocate_vm", "Deallocating VM", vm=vm_name)
    poller = compute.virtual_machines.begin_deallocate(resource_group, vm_name)
    req_ids = _hdr_request_ids(poller)
    poller.result()
    current_app.log_db("INFO", "deallocate_vm", "VM deallocated", vm=vm_name, request_ids=req_ids)
    return {"deallocated": True, "request_ids": req_ids}


def attach_os_disk(resource_group: str, vm_name: str, new_disk_id: str):
    compute = _compute()
    vm = compute.virtual_machines.get(resource_group, vm_name)
    vm.storage_profile.os_disk.managed_disk.id = new_disk_id
    current_app.log_db("INFO", "swap_os_disk", "Updating VM OS disk reference", vm=vm_name, new_disk_id=new_disk_id)
    poller = compute.virtual_machines.begin_create_or_update(resource_group, vm_name, vm)
    req_ids = _hdr_request_ids(poller)
    poller.result()
    current_app.log_db("INFO", "swap_os_disk", "OS disk updated", vm=vm_name, request_ids=req_ids)
    return {"swapped": True, "request_ids": req_ids}


def run_workflow_for_booking(booking):
    """
    Flow:
      - deallocate user2-kali-vm
      - swap OS disk to the requested disk
      - start VM
    """
    rg = os.environ["AZURE_RESOURCE_GROUP"]
    vm_target = booking.vm_name or os.environ.get("AZURE_VM_NAME")
    disk_name = booking.disk_name or os.environ.get("AZURE_DISK_NAME")

    assert vm_target, "VM name not set (booking.vm_name or AZURE_VM_NAME)"
    assert disk_name, "Disk name not set (booking.disk_name or AZURE_DISK_NAME)"

    compute = _compute()
    disk = compute.disks.get(rg, disk_name)
    new_disk_id = disk.id

    steps = {}
    steps["deallocate"] = deallocate_vm(rg, vm_target)
    steps["swap"] = attach_os_disk(rg,
