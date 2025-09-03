import os
from datetime import datetime
from azure.identity import ClientSecretCredential, DefaultAzureCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.compute.models import Disk, CreationData, DiskSku

SUBSCRIPTION_ID = os.environ["AZURE_SUBSCRIPTION_ID"]
RESOURCE_GROUP  = os.environ["AZ_RESOURCE_GROUP"]
TARGET_VM       = os.environ["AZ_TARGET_VM_NAME"]
SNAPSHOT_NAME   = os.environ["AZ_SNAPSHOT_NAME"]

TENANT_ID  = os.getenv("AZURE_TENANT_ID")
CLIENT_ID  = os.getenv("AZURE_CLIENT_ID")
CLIENT_SEC = os.getenv("AZURE_CLIENT_SECRET")

if TENANT_ID and CLIENT_ID and CLIENT_SEC:
    _cred = ClientSecretCredential(tenant_id=TENANT_ID, client_id=CLIENT_ID, client_secret=CLIENT_SEC)
else:
    _cred = DefaultAzureCredential()

_compute = ComputeManagementClient(_cred, SUBSCRIPTION_ID)

def stop_vm():
    _compute.virtual_machines.begin_deallocate(RESOURCE_GROUP, TARGET_VM).wait()

def start_vm():
    _compute.virtual_machines.begin_start(RESOURCE_GROUP, TARGET_VM).wait()

def create_disk_from_snapshot(prefix: str) -> str:
    snap_id = _compute.snapshots.get(RESOURCE_GROUP, SNAPSHOT_NAME).id
    vm = _compute.virtual_machines.get(RESOURCE_GROUP, TARGET_VM)
    location = vm.location
    name = f"{prefix}-{datetime.utcnow():%Y%m%d%H%M%S}"
    disk = Disk(
        location=location,
        sku=DiskSku(name="Premium_LRS"),
        creation_data=CreationData(create_option="Copy", source_resource_id=snap_id),
        tags={"purpose":"Automated Testing"}
    )
    _compute.disks.begin_create_or_update(RESOURCE_GROUP, name, disk).result()
    return name

def swap_os_disk(new_disk_name: str):
    vm_obj = _compute.virtual_machines.get(RESOURCE_GROUP, TARGET_VM)
    new_id = _compute.disks.get(RESOURCE_GROUP, new_disk_name).id
    vm_obj.storage_profile.os_disk.managed_disk.id = new_id
    vm_obj.storage_profile.os_disk.name = new_disk_name
    _compute.virtual_machines.begin_create_or_update(RESOURCE_GROUP, TARGET_VM, vm_obj).result()

def perform_vm_sequence(username: str) -> str:
    # Deallocate -> Create disk from snapshot -> Swap OS disk -> Start
    stop_vm()
    disk_name = create_disk_from_snapshot(f"{username}-kali2-disk")
    swap_os_disk(disk_name)
    start_vm()
    return disk_name
