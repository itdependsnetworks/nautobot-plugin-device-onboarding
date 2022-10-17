"""Add the run_ssot command to nautobot-server."""

from django.core.management.base import BaseCommand
from nautobot_device_onboarding.network_importer.adapters.nautobot.adapter import NautobotOrmAdapter

from nautobot_device_onboarding.network_importer.test_file import data


class Command(BaseCommand):
    """Boilerplate Command to inherit from BaseCommand."""

    help = "Run SSOT."

    def handle(self, *args, **kwargs):
        """Add handler for run_config_backup."""
        orm_adapter = NautobotOrmAdapter()
        # orm_adapter.load()
        orm_adapter.load_from_dict(data)
        # print(orm_adapter.str())
        print(orm_adapter.dict())
