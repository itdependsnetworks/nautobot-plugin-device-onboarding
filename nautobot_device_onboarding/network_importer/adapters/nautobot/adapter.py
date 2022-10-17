"""NautobotAPIAdapter class."""
import logging
import warnings

from graphene_django.settings import graphene_settings
from graphql import get_default_backend

from django.conf import settings

PLUGIN_SETTINGS = settings.PLUGINS_CONFIG.get("nautobot_device_onboarding", {})

from nautobot_plugin_nornir.plugins.inventory.nautobot_orm import NautobotORMInventory
from nautobot.dcim.models import Device, Site

from nornir.core.plugins.inventory import InventoryPluginRegister

InventoryPluginRegister.register("nautobot-inventory", NautobotORMInventory)

from diffsync.exceptions import ObjectAlreadyExists, ObjectNotFound
from nautobot_device_onboarding.network_importer.adapters.nautobot.models import (  # pylint: disable=import-error
    NautobotSite,
    NautobotDevice,
    NautobotInterface,
    NautobotIPAddress,
    NautobotCable,
    NautobotPrefix,
    NautobotVlan,
)
from nautobot.users.models import User
import uuid
from django.test.client import RequestFactory

request = RequestFactory().request(SERVER_NAME="WebRequestContext")
request.id = uuid.uuid4()
request.user = User.objects.get(username="admin")

from nautobot_device_onboarding.network_importer.adapters.base import BaseAdapter  # pylint: disable=import-error

warnings.filterwarnings("ignore", category=DeprecationWarning)

with warnings.catch_warnings():
    warnings.filterwarnings("ignore", category=DeprecationWarning)

LOGGER = logging.getLogger("network-importer")


def smart_del(dictionary, key):
    try:
        del dictionary[key]
    except KeyError:
        pass
    return dictionary


backend = get_default_backend()
schema = graphene_settings.SCHEMA
SITE_QUERY = """query ($site_id: ID!) {
  site(id: $site_id) {
    name
    devices {
      name
    }
    tags {
      name
      id
    }
    vlans {
      id
      vid
      tags {
        name
        id
      }
    }
    prefixes {
      id
      network
      prefix
      tags {
        name
        id
      }
    }
  }
}"""

DEVICE_QUERY = """query ($device_id: ID!) {
  device(id: $device_id) {
    name
    site {
      id
      name
    }
    interfaces {
      id
      name
      description
      mtu
      mode
      type
      status {
        slug
      }
      connected_endpoint {
        __typename
      }
      ip_addresses {
        id
        address
      }
      cable {
        termination_a_type
        status {
          name
        }
        color
      }
      lag {
        id
        enabled
        name
        member_interfaces {
          name
          enabled
        }
      }
      tagged_vlans {
        id
        vid
      }
      untagged_vlan {
        id
        vid
      }
    }
  }
}"""

CABLE_QUERY = """query ($site_id: String) {
  cables(site_id: [$site_id]) {
    id
    termination_a_id
    termination_b_id
    termination_a_type
    termination_b_type
  }
}"""


class NautobotOrmAdapter(BaseAdapter):
    """Adapter to import Data from a Nautobot Server over its API."""

    site = NautobotSite
    device = NautobotDevice
    interface = NautobotInterface
    ip_address = NautobotIPAddress
    cable = NautobotCable
    vlan = NautobotVlan
    prefix = NautobotPrefix

    top_level = ["site", "device", "cable"]

    # settings_class = AdapterSettings

    type = "Nautobot"

    def __init__(self, *args, **kwargs): # REMOVE????
        """Ensure the cable is unique by ordering the devices alphabetically."""
        self._interface_dict = {}
        super().__init__(*args, **kwargs)

    # def _is_tag_present(self, nautobot_obj):
    #     """Find if tag is present for a given object."""
    #     if isinstance(nautobot_obj, dict) and not nautobot_obj.get("tags", None):  # pylint: disable=no-else-return
    #         return False
    #     elif not isinstance(nautobot_obj, dict):  # pylint: disable=no-else-return
    #         try:
    #             nautobot_obj["tags"]
    #         except AttributeError:
    #             return False
    #     elif not nautobot_obj["tags"]:
    #         return False

    #     for tag in self.settings.model_flag_tags:
    #         if tag in nautobot_obj["tags"]:
    #             LOGGER.debug(
    #                 "Tag (%s) found for object %s. Marked for diffsync flag assignment.",
    #                 tag,
    #                 nautobot_obj,
    #             )
    #             return True
    #     return False

    # def apply_model_flag(self, diffsync_obj, nautobot_obj):
    #     """Helper function for DiffSync Flag assignment."""
    #     model_flag = self.settings.model_flag

    #     if model_flag and self._is_tag_present(nautobot_obj):
    #         LOGGER.info(
    #             "DiffSync model flag (%s) applied to object %s",
    #             model_flag,
    #             nautobot_obj,
    #         )
    #         diffsync_obj.model_flags = model_flag
    #     return diffsync_obj

    def load(self):
        """Initialize and load all data from nautobot in the local cache."""
        self.load_inventory()

        # Load Prefix and Vlan per site
        for site in self.get_all(self.site):
            site_variables = {"site_id": site.remote_id}
            document = backend.document_from_string(schema, SITE_QUERY)
            gql_result = document.execute(context_value=request, variable_values=site_variables)
            data = gql_result.data
            self.load_nautobot_prefix(site, data)
            self.load_nautobot_vlan(site, data)

        # Load interfaces and IP addresses for each devices
        for device in self.get_all(self.device):
            device_variables = {"device_id": device.remote_id}
            document = backend.document_from_string(schema, DEVICE_QUERY)
            gql_result = document.execute(context_value=request, variable_values=device_variables)
            data = gql_result.data
            site = self.get(self.site, device.site_name)
            self.load_nautobot_device(site, device, data)

        # Load Cabling
        if PLUGIN_SETTINGS.get("import_cabling") in ["lldp", "cdp"]:
            for site in self.get_all(self.site):
                site_variables = {"site_id": site.remote_id}
                document = backend.document_from_string(schema, CABLE_QUERY)
                gql_result = document.execute(context_value=request, variable_values=site_variables)
                data = gql_result.data
                self.load_nautobot_cable(site, data)

        # for _site in data["site"].values():
        #     # _site = smart_del(_site, "prefixes")
        #     # _site = smart_del(_site, "vlans")
        #     self.add(self.site(**_site))
        # for _device in data["device"].values():
        #     _device = smart_del(_device, "interface")
        #     self.add(self.device(**_device))
        # for _cable in data["cable"].values():
        #     self.add(self.cable(**_cable))
        # for key, _interface in data["interface"].items():
        #     self.add(self.interface(**_interface))
        #     # interface = self.interface(**_interface)
        #     # self.add(interface)
        #     # device = self.get(NautobotDevice, _interface["device_name"])
        #     # device.add_child(interface)
        # for _prefix in data["prefix"].values():
        #     self.add(self.prefix(**_prefix))
        # for _vlan in data["vlan"].values():
        #     self.add(self.vlan(**_vlan))
        # for _ip_address in data["ip_address"].values():
        #     self.add(self.ip_address(**_ip_address))

    def load_nautobot_device(self, site, device, data):
        """Import all interfaces and IP address from Nautobot for a given device.
        Args:
            site (NautobotSite): Site the device is part of
            device (DiffSyncModel): Device to import
        """
        intfs = data["device"]["interfaces"]
        for intf in intfs:
            self.convert_interface_from_nautobot(device, intf, site)

        LOGGER.debug("%s | Found %s interfaces for %s", self.name, len(intfs), device.name)

    def load_nautobot_prefix(self, site, site_data):
        """Import all prefixes from Nautobot for a given site.
        Args:
            site (NautobotSite): Site to import prefix for
        """
        # Adapter Model methods not accounted for
        # vlan: Optional[str]

        if PLUGIN_SETTINGS.get("import_prefixes") is False:
            return

        prefixes = site_data["site"]["prefixes"]

        for nb_prefix in prefixes:

            prefix = self.prefix(
                prefix=nb_prefix["prefix"],
                site_name=site_data["site"]["name"],
                remote_id=nb_prefix["id"],
            )
            # prefix = self.apply_model_flag(prefix, nb_prefix)

            # if nb_prefix.vlan:
            #     prefix.vlan = self.vlan.create_unique_id(vid=nb_prefix.vlan.vid, site_name=site.name)

            self.add(prefix)
            site.add_child(prefix)

    def load_nautobot_vlan(self, site, vlan_data):
        """Import all vlans from Nautobot for a given site.
        Args:
            site (NautobotSite): Site to import vlan for
        """
        if PLUGIN_SETTINGS.get("import_vlans") is not True:
            return

        vlans = vlan_data["site"]["vlans"]

        for nb_vlan in vlans:
            vlan = self.vlan(
                vid=nb_vlan["vid"],
                site_name=vlan_data["site"]["name"],
                associated_devices=[item["name"] for item in vlan_data["site"]["devices"]],
                remote_id=nb_vlan["id"],
            )
            self.add(vlan)
            site.add_child(vlan)

    def convert_interface_from_nautobot(
        self, device, int_data, site=None
    ):  # pylint: disable=too-many-branches,too-many-statements
        """Convert PyNautobot interface object to NautobotInterface model.
        Args:
            site (NautobotSite): [description]
            device (NautobotDevice): [description]
            intf (pynautobot interface object): [description]
        """
        # Adapter Model methods not accounted for
        # speed: Optional[int]
        # lag_members: List[str] = list()
        # allowed_vlans: List[str] = list()
        # access_vlan: Optional[str]

        interface = self.interface(
            name=int_data["name"],
            device_name=device.name,
            remote_id=int_data["id"],
            description=int_data["description"] or None,
            mtu=int_data["mtu"],
        )

        import_vlans = True
        if PLUGIN_SETTINGS.get("import_vlans") is not True:
            import_vlans = False

        # Define status if it's enabled in the config file
        if PLUGIN_SETTINGS.get("import_intf_status") is True:
            if int_data["status"]["slug"] == "active":
                interface.active = True
            else:
                interface.active = False

        # Identify if the interface is physical or virtual and if it's part of a Lag
        if int_data["type"] == "lag":
            interface.is_lag = True
            interface.is_virtual = False
        elif int_data["type"] == "virtual":
            interface.is_virtual = True
            interface.is_lag = False
        else:
            interface.is_lag = False
            interface.is_virtual = False

        if int_data["lag"]:
            interface.is_lag_member = True
            interface.is_lag = False
            interface.is_virtual = False
            parent_interface_uid = self.interface(name=int_data["lag"], device_name=device.name).get_unique_id()
            interface.parent = parent_interface_uid

        # identify Interface Mode
        if int_data["mode"] == "ACCESS":
            interface.switchport_mode = "ACCESS"
            interface.mode = interface.switchport_mode
        elif int_data["mode"] == "TAGGED":
            interface.switchport_mode = "TRUNK"
            interface.mode = interface.switchport_mode
        # This logic seems off to me? Why would the mode be L3_SUB?
        elif not int_data["mode"] and int_data["tagged_vlans"]:
            interface.switchport_mode = "NONE"
            interface.mode = "L3_SUB_VLAN"
        else:
            interface.switchport_mode = "NONE"
            interface.mode = "NONE"

        # TODO: Update and verify this logic
        # if site and int_data.get('tagged_vlans') and import_vlans:
        #     for vid in [v["vid"] for v in int_data['tagged_vlans']]:
        #         try:
        #             vlan = self.get(self.vlan, identifier=dict(vid=vid, site_name=site.name))
        #             interface.allowed_vlans.append(vlan.get_unique_id())
        #         except ObjectNotFound:
        #             LOGGER.debug("%s | VLAN %s is not present for site %s", self.name, vid, site.name)

        # if site and int_data["untagged_vlan"] and import_vlans:
        #     try:
        #         vlan = self.get(self.vlan, identifier=dict(vid=int_data["untagged_vlan"]["vid"], site_name=site.name))
        #         interface.access_vlan = vlan.get_unique_id()
        #     except ObjectNotFound:
        #         LOGGER.debug("%s | VLAN %s is not present for site %s", self.name, int_data["untagged_vlan"]["vid"], site.name)

        if int_data["connected_endpoint"]:
            interface.connected_endpoint_type = int_data["connected_endpoint"]["__typename"]

        new_intf, created = self.get_or_add(interface)
        if created:
            device.add_child(new_intf)

        # GraphQL returns [] when empty, so can just loop through nothing with no effect
        for ip_addr in int_data["ip_addresses"]:
            ip_address = self.ip_address(
                interface_name=int_data["name"],
                device_name=device.name,
                remote_id=ip_addr["id"],
                address=ip_addr["address"],
            )

            # Note: There was a duplicate check (ObjectAlreadyExists), does not seem to be a valid use case and we should
            # fail fast. Potentially incorrect thought process
            self.add(ip_address)
            new_intf.add_child(ip_address)
        self._interface_dict[new_intf.remote_id] = new_intf

        return new_intf

    def load_nautobot_cable(self, site, cable_data):
        """Import all Cables from Nautobot for a given site.
        If both devices at each end of the cables are not in the list of device_id_map, the cable will be ignored.
        Args:
            site (Site): Site object to import cables for
            device_id_map (dict): Dict of device IDs and names that are part of the inventory
        """
        # Adapter Model methods not accounted for
        # source: Optional[str]
        # is_valid: bool = True
        # error: Optional[str]
        cables = cable_data["cables"]
        device_names = [device.name for device in self.get_all(self.device)]

        nbr_cables = 0
        for nb_cable in cables:
            if nb_cable["termination_a_type"] != "dcim.interface" or nb_cable["termination_b_type"] != "dcim.interface":
                continue
            term_a_device_name = self._interface_dict[nb_cable["termination_a_id"]].device_name
            term_b_device_name = self._interface_dict[nb_cable["termination_b_id"]].device_name
            term_a_interface_name = self._interface_dict[nb_cable["termination_a_id"]].name
            term_b_interface_name = self._interface_dict[nb_cable["termination_b_id"]].name

            if (term_a_device_name not in device_names) and (term_b_device_name not in device_names):
                LOGGER.debug(
                    "%s | Skipping cable %s because neither devices (%s, %s) is in the list of devices",
                    self.name,
                    nb_cable.id,
                    term_a_device_name,
                    term_b_device_name,
                )
                continue

            # Disabling this check for now until we are able to allow user to control how cabling should be imported
            # if term_a_device_name not in device_names:
            #     LOGGER.debug(
            #         "%s | Skipping cable %s because %s is not in the list of devices",
            #         self.name,
            #         nb_cable.id,
            #         term_a_device_name,
            #     )
            #     continue

            # if term_b_device_name not in device_names:
            #     LOGGER.debug(
            #         "%s | Skipping cable %s because %s is not in the list of devices",
            #         self.name,
            #         nb_cable.id,
            #         term_b_device_name,
            #     )
            #     continue

            cable = self.cable(
                device_a_name=term_a_device_name,
                interface_a_name=term_a_interface_name,
                device_z_name=term_b_device_name,
                interface_z_name=term_b_interface_name,
                remote_id=nb_cable["id"],
                status="connected",
            )

            try:
                self.add(cable)
            except ObjectAlreadyExists:
                pass

            nbr_cables += 1

        LOGGER.debug("%s | Found %s cables in nautobot for %s", self.name, nbr_cables, site.name)
