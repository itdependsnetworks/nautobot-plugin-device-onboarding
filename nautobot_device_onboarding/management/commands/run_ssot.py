"""Add the run_ssot command to nautobot-server."""

import uuid
from django.test.client import RequestFactory
from django.core.management.base import BaseCommand
from nautobot.users.models import User

from nautobot_device_onboarding.network_importer.adapters.nautobot.adapter import NautobotOrmAdapter
from nautobot_device_onboarding.network_importer.adapters.network_device.adapter import NetworkImporterAdapter
from nautobot_device_onboarding.tests.mock.network_device.basic import data as network_data


class Command(BaseCommand):
    """Boilerplate Command to Sync from Network Device data dictionary."""

    help = "Sync from Network Device data dictionary."

    def handle(self, *args, **kwargs):
        """Add handler for `run_ssot`."""
        request = RequestFactory().request(SERVER_NAME="WebRequestContext")
        request.id = uuid.uuid4()
        request.user = User.objects.get(username="admin")

        nautobot_adapter = NautobotOrmAdapter(request)
        nautobot_adapter.load()

        network_adapter = NetworkImporterAdapter()
        network_adapter.load_from_dict(network_data)

        _diff = nautobot_adapter.diff_from(network_adapter)
        nautobot_adapter.sync_from(network_adapter, diff=_diff)
