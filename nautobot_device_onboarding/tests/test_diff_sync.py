"""Unit tests for network_importer sync status."""
import uuid
import copy
from django.test import TestCase

from django.test.client import RequestFactory
from django.contrib.auth import get_user_model

from nautobot.dcim.models import Site, Interface

from nautobot_device_onboarding.tests.mock.network_device.basic import data as network_data

from nautobot_device_onboarding.network_importer.adapters.nautobot.adapter import NautobotOrmAdapter
from nautobot_device_onboarding.network_importer.adapters.network_device.adapter import NetworkImporterAdapter
from nautobot_device_onboarding.network_importer.diff import NetworkImporterDiff


User = get_user_model()


class NetworkImporterModelTestCase(TestCase):
    """Test the Onboarding models."""

    fixtures = ["nautobot_dump.json"]

    def setUp(self):
        """Initialize the Database with some datas."""
        super().setUpTestData()
        self.user = User.objects.create(username="admin", is_active=True, is_superuser=True)
        self.request = RequestFactory().request(SERVER_NAME="WebRequestContext")
        self.request.id = uuid.uuid4()
        self.request.user = self.user

    def test_site_created_from_fixture(self):
        """Verify that OnboardingDevice is auto-created."""
        onboarding_device = Site.objects.get(slug="ams01")
        self.assertIsNotNone(onboarding_device)

    def test_first_create(self):
        nautobot_adapter = NautobotOrmAdapter(self.request)
        nautobot_adapter.load()
        local_network_data = copy.deepcopy(network_data)

        local_network_data["interface"]["ams01-edge-01__Ethernet5/1"] = {
            "name": "Ethernet5/1",
            "device": "ams01-edge-01",
            "mode": "access",
            "description": "",
            "type": "10gbase-t",
            "tagged_vlans": [],
            "status": "active",
        }
        local_network_data["device"]["ams01-edge-01"]["interfaces"].append("ams01-edge-01__Ethernet5/1")

        network_adapter = NetworkImporterAdapter()
        network_adapter.load_from_dict(local_network_data)
        nautobot_adapter.sync_from(network_adapter, diff_class=NetworkImporterDiff)
        self.assertEqual(Interface.objects.filter(name="Ethernet3/1").count(), 1)

    def test_first_update(self):
        nautobot_adapter = NautobotOrmAdapter(self.request)
        nautobot_adapter.load()
        local_network_data = copy.deepcopy(network_data)
        local_network_data["interface"]["ams01-edge-01__Ethernet1/1"]["description"] = "new description"

        network_adapter_from_data = NetworkImporterAdapter()
        network_adapter_from_data.load_from_dict(local_network_data)
        nautobot_adapter.sync_from(network_adapter_from_data, diff_class=NetworkImporterDiff)
        self.assertEqual(Interface.objects.filter(description="new description")[0].description, "new description")

    def test_first_delete(self):
        nautobot_adapter = NautobotOrmAdapter(self.request)
        nautobot_adapter.load()
        local_network_data = copy.deepcopy(network_data)
        del local_network_data["interface"]["ams01-edge-01__Ethernet1/1"]
        local_network_data["device"]["ams01-edge-01"]["interfaces"].remove("ams01-edge-01__Ethernet1/1")

        network_adapter_from_data = NetworkImporterAdapter()
        network_adapter_from_data.load_from_dict(local_network_data)
        nautobot_adapter.sync_from(network_adapter_from_data, diff_class=NetworkImporterDiff)
        self.assertEqual(Interface.objects.filter(name="Ethernet1/1").count(), 2)
