"""Add the run_ssot command to nautobot-server."""

from django.core.management.base import BaseCommand
from nautobot_device_onboarding.network_importer.adapters.nautobot.adapter import NautobotOrmAdapter
from nautobot_device_onboarding.network_importer.adapters.network_device.adapter import NetworkImporterAdapter

from nautobot_device_onboarding.network_importer.test_file import data
from nautobot_device_onboarding.tests.mock.nautobot.basic import data as nautobot_data
from nautobot_device_onboarding.tests.mock.network_device.basic import data as network_data

# from diffsync.logging import enable_console_logging
# enable_console_logging(verbosity=0)  # Show WARNING and ERROR logs only
# enable_console_logging(verbosity=1)  # Also include INFO logs
# enable_console_logging(verbosity=2)  # Also include DEBUG logs

class Command(BaseCommand):
    """Boilerplate Command to inherit from BaseCommand."""

    help = "Run SSOT."

    def handle(self, *args, **kwargs):
        """Add handler for run_config_backup."""
        nautobot_adapter = NautobotOrmAdapter()
        # nautobot_adapter.load()
        # nautobot_adapter.load_from_dict(data)
        # print(nautobot_adapter.str())
        # print(nautobot_adapter.dict())

        nautobot_adapter = NautobotOrmAdapter()
        nautobot_adapter.load_from_dict(nautobot_data)
        network_adapter = NetworkImporterAdapter()
        network_adapter.load_from_dict(network_data)
        # breakpoint()
        diff_a_b = nautobot_adapter.diff_to(network_adapter)
        print(diff_a_b.str())
