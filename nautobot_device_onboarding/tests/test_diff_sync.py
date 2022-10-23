from hashlib import new
from django.test import TestCase
from django.apps import apps


from nautobot.dcim.models import Site, DeviceRole, DeviceType, Manufacturer, Device, Interface, Platform
from nautobot.ipam.models import IPAddress, VLAN, Prefix
from nautobot.extras.models.statuses import Status

from nautobot_device_onboarding.models import OnboardingTask
from nautobot_device_onboarding.models import OnboardingDevice
from nautobot_device_onboarding.choices import OnboardingStatusChoices

# from nautobot_device_onboarding.network_importer.models import Prefix
from nautobot_device_onboarding.tests.mock.nautobot.basic import data as nautobot_data
from nautobot_device_onboarding.tests.mock.network_device.basic import data as network_data

from nautobot_device_onboarding.network_importer.adapters.nautobot.adapter import NautobotOrmAdapter
from nautobot_device_onboarding.network_importer.adapters.network_device.adapter import NetworkImporterAdapter
import copy


# class TestNautobotSite(NautobotMixin, NautobotSite):
#     """Extension of the Site model."""


# class TestNautobotDevice(NautobotMixin, NautobotDevice):
#     """Extension of the Device model."""


def return_relevant_keys(_dict, interested, modelClass):
    new = modelClass()

    for key, value in _dict.items():
        if key in interested:
            setattr(new, key, value)
        if key == "slug" and not _dict.get("name"):
            setattr(new, "name", value)
        if key == "pk":
            setattr(new, "id", value)
    return new


class OnboardingDeviceModelTestCase(TestCase):
    """Test the Onboarding models."""

    def setUp(self):
        """Setup objects for Onboarding Model tests."""
        site_obj = return_relevant_keys(nautobot_data["site"]["ams01"], ["slug", "pk"], Site)
        site_obj.save()

        manufacturer = Manufacturer.objects.create(name="Cisco", slug="cisco")
        device_role = DeviceRole.objects.create(name="Switch", slug="switch")
        device_type = DeviceType.objects.create(slug="C9410R", model="C9410R", manufacturer=manufacturer)
        platform = Platform.objects.create(name="ios", slug="ios")

        _status = nautobot_data["status"]["active"]
        status = Status.objects.create(slug=_status["slug"], name=_status["name"], pk=_status["pk"])
        ContentType = apps.get_model("contenttypes.ContentType")
        ct = ContentType.objects.get_for_model(Device)
        status.content_types.add(ct)
        ct = ContentType.objects.get_for_model(Interface)
        status.content_types.add(ct)
        ct = ContentType.objects.get_for_model(IPAddress)
        status.content_types.add(ct)
        ct = ContentType.objects.get_for_model(VLAN)
        status.content_types.add(ct)
        ct = ContentType.objects.get_for_model(Prefix)
        status.content_types.add(ct)

        status.save()

        for item, value in nautobot_data["device"].items():
            obj = Device.objects.create(
                platform=platform,
                pk=value["pk"],
                id=value["pk"],
                device_role=device_role,
                device_type=device_type,
                site=site_obj,
            )
            obj.slug = value["slug"]
            obj.name = value["slug"]
            obj.status = status
            obj.save()

            primary_ip = nautobot_data["device"][item]["primary_ip"]
            ip_key = [k for k, v in nautobot_data["ip_address"].items() if v["address"].split("/")[0] == primary_ip][0]
            interface = nautobot_data["ip_address"][ip_key]["interface"]
            interface_key = [
                k
                for k, v in nautobot_data["interface"].items()
                if v["name"] == interface and v["device"] == value["slug"]
            ][0]

            ip_dict = nautobot_data["ip_address"][ip_key]
            ip_obj = return_relevant_keys(ip_dict, ["name", "pk", "mode"], IPAddress)
            ip_obj.address = ip_dict["address"].split("/")[0]
            ip_obj.prefix_length = ip_dict["address"].split("/")[1]
            ip_obj.status = status
            ip_obj.validated_save()

            int_obj = return_relevant_keys(nautobot_data["interface"][interface_key], ["name", "pk"], Interface)
            if nautobot_data["interface"][interface_key]["mode"] != "NONE":
                int_obj.mode = nautobot_data["interface"][interface_key]["mode"]
            int_obj.device = obj
            int_obj.ip_addresses.add(ip_obj)
            int_obj.status = status
            int_obj.type = "10gbase-t"
            int_obj.validated_save()
            obj.primary_ip4 = ip_obj
            obj.validated_save()
        nautobot_adapter = NautobotOrmAdapter()
        nautobot_adapter.load()

        nautobot_adapter_from_data = NautobotOrmAdapter()
        nautobot_adapter_from_data.load_from_dict(nautobot_data)

        _diff = nautobot_adapter.diff_from(nautobot_adapter_from_data)

        nautobot_adapter.sync_from(nautobot_adapter_from_data, diff=_diff)

    def test_site_created_with_expected_pk(self):
        """Verify that OnboardingDevice is auto-created."""
        onboarding_device = Site.objects.get(slug="ams01")
        self.assertEqual(str(onboarding_device.pk), "6cd7cf29-a053-4a4c-bad8-1a00a333a859")

    def test_first_create(self):
        nautobot_adapter = NautobotOrmAdapter()
        nautobot_adapter.load()
        local_nautobot_data = copy.deepcopy(nautobot_data)

        local_nautobot_data["interface"]["ams01-edge-01__Ethernet3/1"] = {
            "name": "Ethernet3/1",
            "device": "ams01-edge-01",
            "mode": "access",
            "description": "",
            "active": True,
            # "is_virtual": False,
            "is_lag": False,
            "type": "10gbase-t",
            "tagged_vlans": [],
            "status": "active",
        }
        local_nautobot_data["device"]["ams01-edge-01"]["interfaces"].append("ams01-edge-01__Ethernet3/1")

        nautobot_adapter_from_data = NautobotOrmAdapter()
        nautobot_adapter_from_data.load_from_dict(local_nautobot_data)
        _diff = nautobot_adapter.diff_from(nautobot_adapter_from_data)
        nautobot_adapter.sync_from(nautobot_adapter_from_data)
        self.assertEqual(Interface.objects.filter(name="Ethernet3/1").count(), 1)

    def test_first_update(self):
        nautobot_adapter = NautobotOrmAdapter()
        nautobot_adapter.load()
        local_nautobot_data = copy.deepcopy(nautobot_data)
        local_nautobot_data["interface"]["ams01-edge-01__Ethernet1/1"]["description"] = "new description"

        nautobot_adapter_from_data = NautobotOrmAdapter()
        nautobot_adapter_from_data.load_from_dict(local_nautobot_data)
        _diff = nautobot_adapter.diff_from(nautobot_adapter_from_data)
        nautobot_adapter.sync_from(nautobot_adapter_from_data)
        self.assertEqual(Interface.objects.filter(description="new description")[0].description, "new description")

    def test_first_delete(self):
        nautobot_adapter = NautobotOrmAdapter()
        nautobot_adapter.load()
        local_nautobot_data = copy.deepcopy(nautobot_data)
        del local_nautobot_data["interface"]["ams01-edge-01__Ethernet1/1"]
        local_nautobot_data["device"]["ams01-edge-01"]["interfaces"].remove("ams01-edge-01__Ethernet1/1")

        nautobot_adapter_from_data = NautobotOrmAdapter()
        nautobot_adapter_from_data.load_from_dict(local_nautobot_data)
        _diff = nautobot_adapter.diff_from(nautobot_adapter_from_data)
        nautobot_adapter.sync_from(nautobot_adapter_from_data)
        self.assertEqual(Interface.objects.filter(name="Ethernet1/1").count(), 2)
