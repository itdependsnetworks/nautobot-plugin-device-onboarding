"""Management command to destroy and build from test dictionary."""

from django.core.management.base import BaseCommand
from django.core import management
from nautobot.dcim.models import Site, DeviceRole, DeviceType, Manufacturer, Device, Interface, Platform
from nautobot.ipam.models import IPAddress, VLAN, Prefix


def remove():
    """Function to clean up all of the data that would be in Nautobot side of the adapter."""
    [obj.delete() for obj in Device.objects.all()]
    [obj.delete() for obj in VLAN.objects.all()]
    [obj.delete() for obj in Prefix.objects.all()]
    [obj.delete() for obj in DeviceRole.objects.all()]
    [obj.delete() for obj in DeviceType.objects.all()]
    [obj.delete() for obj in Platform.objects.all()]
    [obj.delete() for obj in Manufacturer.objects.all()]
    [obj.delete() for obj in Site.objects.all()]
    [obj.delete() for obj in IPAddress.objects.all()]
    [obj.delete() for obj in Interface.objects.all()]


class Command(BaseCommand):
    """Publish command to destroy and build from test dictionary."""

    help = "Destroy all importable data, initlize base data, and sync from test dictionary."

    def add_arguments(self, parser):
        """Add arguments for dev_destroy_and_build."""
        parser.add_argument("-u", "--user", type=str, required=True, help="Username to create.")
        parser.add_argument("-p", "--password", type=str, required=True, help="Password to create.")
        parser.add_argument("-e", "--email", type=str, required=False, help="Email to create.")

    def handle(self, *args, **kwargs):
        """Add handler for `dev_destroy_and_build`."""
        user = kwargs["user"]
        password = kwargs["password"]
        email = kwargs["email"]
        if not email:
            email = "email@example.com"
        remove()
        management.call_command("dev_init_data", f"---user={user}", f"--password={password}", f"--email={email}")
        management.call_command("run_ssot")
