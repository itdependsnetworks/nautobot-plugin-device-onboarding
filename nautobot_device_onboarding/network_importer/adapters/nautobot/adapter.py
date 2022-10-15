"""NautobotAPIAdapter class."""
import imp
import logging
from operator import index
import warnings

from packaging.version import Version, InvalidVersion
from nornir import InitNornir
from netutils.ip import is_ip



from nautobot_plugin_nornir.plugins.inventory.nautobot_orm import NautobotORMInventory
from nautobot.dcim.models import Device, Site

from nornir.core.plugins.inventory import InventoryPluginRegister
InventoryPluginRegister.register("nautobot-inventory", NautobotORMInventory)

from diffsync.exceptions import ObjectAlreadyExists, ObjectNotFound
from nautobot_device_onboarding.network_importer.adapters.nautobot.models import (  # pylint: disable=import-error
    NautobotSite,
    NautobotDevice,
    NautobotInterface,
    # NautobotIPAddress,
    # NautobotCable,
    NautobotPrefix,
    NautobotVlan,
)
from nautobot.users.models import User
import uuid
from django.test.client import RequestFactory
request = RequestFactory().request(SERVER_NAME="WebRequestContext")
request.id = uuid.uuid4()
request.user = User.objects.get(username="admin")



# import nautobot_device_onboarding.network_importer.config as config  # pylint: disable=import-error
from nautobot_device_onboarding.network_importer.adapters.base import BaseAdapter  # pylint: disable=import-error

# from nautobot_device_onboarding.network_importer.adapters.nautobot.tasks import query_device_info_from_nautobot
# from nautobot_device_onboarding.network_importer.adapters.nautobot.settings import InventorySettings, AdapterSettings

warnings.filterwarnings("ignore", category=DeprecationWarning)

with warnings.catch_warnings():
    warnings.filterwarnings("ignore", category=DeprecationWarning)

LOGGER = logging.getLogger("network-importer")


from graphene_django.settings import graphene_settings
from graphql import get_default_backend
from graphql.error import GraphQLSyntaxError
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




class NautobotOrmAdapter(BaseAdapter):
    """Adapter to import Data from a Nautobot Server over its API."""

    site = NautobotSite
    device = NautobotDevice
    interface = NautobotInterface
    # ip_address = NautobotIPAddress
    # cable = NautobotCable
    vlan = NautobotVlan
    prefix = NautobotPrefix

    top_level = ["site", "device"]#, "cable"]

    # nautobot = None

    # settings_class = AdapterSettings

    # type = "Nautobot"

    # query_device_info_from_nautobot = query_device_info_from_nautobot

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
        """Initialize pynautobot and load all data from nautobot in the local cache."""
        sites = {}
        device_names = []
        device_ids = []

        # results = self.nornir.run(task=query_device_info_from_nautobot)
        with InitNornir(
            runner={
                "plugin": "threaded",
            },
            logging={"enabled": False},
            inventory={
                "plugin": "nautobot-inventory",
                "options": {
                    "credentials_class": "nautobot_plugin_nornir.plugins.credentials.env_vars.CredentialsEnvVars",
                    "params": {},
                    "queryset": Device.objects.filter(site__slug='ams01'),
                },
            },
        ) as nornir_obj:
 
            for device_obj in nornir_obj.inventory.hosts:
                # print(device_obj)
                # if items[0].failed:
                #     continue

                result = nornir_obj.inventory.hosts[device_obj]
                site_name = result.data.get("site")

                if site_name not in sites:
                    site_id = Site.objects.get(slug=site_name)
                    site = self.site(name=site_name, remote_id=str(site_id.pk))
                    sites[site_name] = site
                    self.add(site)
                else:
                    site = sites[site_name]

                device = self.device(name=device_obj, site_name=site_name, remote_id=str(result.data.get("id")))
                device_names.append(device_obj)
                device_ids.append(str(result.data.get("id")))

                if is_ip(result.hostname):
                    device.primary_ip = result.hostname

                # device = self.apply_model_flag(device, nb_device)
                self.add(device)
                print(device)
                print(device.primary_ip)

        print(sites)
        # # Load Prefix and Vlan per site
        for site_name, value in sites.items():
            site_variables = {"site_id": value.remote_id}
            document = backend.document_from_string(schema, SITE_QUERY)
            gql_result = document.execute(context_value=request, variable_values=site_variables)
            data = gql_result.data
            self.load_nautobot_prefix(sites[site_name], data)
            self.load_nautobot_vlan(sites[site_name], data)

        # Load interfaces and IP addresses for each devices
        # devices = self.get_all(self.device)
        for index, device_name in enumerate(device_names):
            device_variables = {"device_id": device_ids[index]}
            document = backend.document_from_string(schema, DEVICE_QUERY)
            gql_result = document.execute(context_value=request, variable_values=device_variables)
            data = gql_result.data
            site = sites[device.site_name]
            # device_names.append(device.name)
            self.load_nautobot_device(site, device, data)

        # # Load Cabling
        # for site in self.get_all(self.site):
        #     self.load_nautobot_cable(site=site, device_names=device_names)

    def load_nautobot_device(self, site, device, data):
        """Import all interfaces and IP address from Nautobot for a given device.
        Args:
            site (NautobotSite): Site the device is part of
            device (DiffSyncModel): Device to import
        """
        self.load_nautobot_interface(site, device, data)
    #     self.load_nautobot_ip_address(site=site, device=device)

    def load_nautobot_prefix(self, site, site_data):
        """Import all prefixes from Nautobot for a given site.
        Args:
            site (NautobotSite): Site to import prefix for
        """
        # if not config.SETTINGS.main.import_prefixes:
        #     return

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
        # if config.SETTINGS.main.import_vlans in [False, "no"]:
        #     return

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
        self, device, intf, int_data, site=None
    ):  # pylint: disable=too-many-branches,too-many-statements
        """Convert PyNautobot interface object to NautobotInterface model.
        Args:
            site (NautobotSite): [description]
            device (NautobotDevice): [description]
            intf (pynautobot interface object): [description]
        """
        # {
        #     "id": "ca405466-3e29-4079-bb9e-909fc5c87cd6",
        #     "name": "Ethernet1/1",
        #     "description": "",
        #     "mtu": None,
        #     "mode": None,
        #     "type": "A_100GBASE_X_QSFP28",
        #     "connected_endpoint": {"__typename": "InterfaceType"},
        #     "ip_addresses": [
        #         {"id": "6abc3fa2-ec9c-46d6-a2fc-bf1fe7ceaed3", "address": "10.11.192.0/32"}
        #     ],
        #     "cable": {
        #         "termination_a_type": "dcim.interface",
        #         "status": {"name": "Connected"},
        #         "color": "",
        #     },
        #     "lag": None,
        #     "tagged_vlans": [],
        #     "untagged_vlan": None,
        # }

        interface = self.interface(
            name=int_data["name"],
            device_name=device.name,
            remote_id=int_data["id"],
            description=int_data["description"] or None,
            mtu=int_data["mtu"],
        )

        import_vlans = False
        # if config.SETTINGS.main.import_vlans not in [False, "no"]:
        #     import_vlans = True

        # # Define status if it's enabled in the config file
        # if config.SETTINGS.main.import_intf_status:
        #     interface.active = intf.enabled

        # Identify if the interface is physical or virtual and if it's part of a Lag
        print(int_data)
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
        if int_data["mode"] == "access":
            interface.switchport_mode = "ACCESS"
            interface.mode = interface.switchport_mode
        elif int_data["mode"] == "tagged":
            interface.switchport_mode = "TRUNK"
            interface.mode = interface.switchport_mode
        elif not int_data["mode"] and int_data['tagged_vlans']:
            interface.switchport_mode = "NONE"
            interface.mode = "L3_SUB_VLAN"
        else:
            interface.switchport_mode = "NONE"
            interface.mode = "NONE"

        # TODO: This should not ever matter, there is no speed in a Nautobot interface. Hardcoding for now, revisit
        interface.speed = 10
        # # Identify Interface Speed based on the type
        # if intf.type and intf.type.value == 800:
        #     interface.speed = 1000000000
        # elif intf.type and intf.type.value == 1100:
        #     interface.speed = 1000000000
        # elif intf.type and intf.type.value == 1200:
        #     interface.speed = 10000000000
        # elif intf.type and intf.type.value == 1350:
        #     interface.speed = 25000000000
        # elif intf.type and intf.type.value == 1400:
        #     interface.speed = 40000000000
        # elif intf.type and intf.type.value == 1600:
        #     interface.speed = 100000000000

        if site and int_data.get('tagged_vlans') and import_vlans:
            for vid in [v["vid"] for v in int_data['tagged_vlans']]:
                try:
                    vlan = self.get(self.vlan, identifier=dict(vid=vid, site_name=site.name))
                    interface.allowed_vlans.append(vlan.get_unique_id())
                except ObjectNotFound:
                    LOGGER.debug("%s | VLAN %s is not present for site %s", self.name, vid, site.name)

        if site and int_data["untagged_vlan"] and import_vlans:
            try:
                vlan = self.get(self.vlan, identifier=dict(vid=int_data["untagged_vlan"]["vid"], site_name=site.name))
                interface.access_vlan = vlan.get_unique_id()
            except ObjectNotFound:
                LOGGER.debug("%s | VLAN %s is not present for site %s", self.name, int_data["untagged_vlan"]["vid"], site.name)

        if int_data.get("connected_endpoint", {}).get("__typename"):
            interface.connected_endpoint_type = int_data["connected_endpoint"]["__typename"]

        new_intf, created = self.get_or_add(interface)
        if created:
            device.add_child(new_intf)

        return new_intf

    def load_nautobot_interface(self, site, device, device_data):
        """Import all interfaces & Ips from Nautobot for a given device.

        Args:
            site (NautobotSite): DiffSync object representing a site
            device (NautobotDevice): DiffSync object representing the device
        """
        # intfs = self.nautobot.dcim.interfaces.filter(device=device.name)
        # print(device_data)
        intfs = device_data["device"]["interfaces"]
        # print(intfs)
        for intf in intfs:
            print(intf)
            self.convert_interface_from_nautobot(device, intfs, intf, site)

        LOGGER.debug("%s | Found %s interfaces for %s", self.name, len(intfs), device.name)

    # name: str
    # device_name: str

    # description: Optional[str]
    # mtu: Optional[int]
    # speed: Optional[int]
    # mode: Optional[str]  # TRUNK, ACCESS, L3, NONE
    # switchport_mode: Optional[str] = "NONE"
    # active: Optional[bool]
    # is_virtual: Optional[bool]
    # is_lag: Optional[bool]
    # is_lag_member: Optional[bool]
    # parent: Optional[str]

    # lag_members: List[str] = list()
    # allowed_vlans: List[str] = list()
    # access_vlan: Optional[str]

    # ips: List[str] = list()

    # def load_nautobot_ip_address(self, site, device):  # pylint: disable=unused-argument
    #     """Import all IP addresses from Nautobot for a given device.
    #     Args:
    #         site (NautobotSite): DiffSync object representing a site
    #         device (NautobotDevice): DiffSync object representing the device
    #     """
    #     if not config.SETTINGS.main.import_ips:
    #         return

    #     ips = self.nautobot.ipam.ip_addresses.filter(device=device.name)
    #     for ipaddr in ips:
    #         ip_address = self.ip_address.create_from_pynautobot(diffsync=self, obj=ipaddr, device_name=device.name)
    #         ip_address, _ = self.get_or_add(ip_address)

    #         interface = self.get(
    #             self.interface, identifier=dict(device_name=device.name, name=ip_address.interface_name)
    #         )
    #         try:
    #             interface.add_child(ip_address)
    #         except ObjectAlreadyExists:
    #             LOGGER.error(
    #                 "%s | Duplicate IP found for %s (%s) ; IP already imported.", self.name, ip_address, device.name
    #             )

    #     LOGGER.debug("%s | Found %s ip addresses for %s", self.name, len(ips), device.name)

    # def load_nautobot_cable(self, site, device_names):
    #     """Import all Cables from Nautobot for a given site.
    #     If both devices at each end of the cables are not in the list of device_names, the cable will be ignored.
    #     Args:
    #         site (Site): Site object to import cables for
    #         device_names (list): List of device names that are part of the inventory
    #     """
    #     cables = self.nautobot.dcim.cables.filter(site=site.name)

    #     nbr_cables = 0
    #     for nb_cable in cables:
    #         if nb_cable.termination_a_type != "dcim.interface" or nb_cable.termination_b_type != "dcim.interface":
    #             continue

    #         if (nb_cable.termination_a.device.name not in device_names) and (
    #             nb_cable.termination_b.device.name not in device_names
    #         ):
    #             LOGGER.debug(
    #                 "%s | Skipping cable %s because neither devices (%s, %s) is in the list of devices",
    #                 self.name,
    #                 nb_cable.id,
    #                 nb_cable.termination_a.device.name,
    #                 nb_cable.termination_b.device.name,
    #             )
    #             continue

    #         # Disabling this check for now until we are able to allow user to control how cabling should be imported
    #         # if nb_cable.termination_a.device.name not in device_names:
    #         #     LOGGER.debug(
    #         #         "%s | Skipping cable %s because %s is not in the list of devices",
    #         #         self.name,
    #         #         nb_cable.id,
    #         #         nb_cable.termination_a.device.name,
    #         #     )
    #         #     continue

    #         # if nb_cable.termination_b.device.name not in device_names:
    #         #     LOGGER.debug(
    #         #         "%s | Skipping cable %s because %s is not in the list of devices",
    #         #         self.name,
    #         #         nb_cable.id,
    #         #         nb_cable.termination_b.device.name,
    #         #     )
    #         #     continue

    #         cable = self.cable(
    #             device_a_name=nb_cable.termination_a.device.name,
    #             interface_a_name=nb_cable.termination_a.name,
    #             device_z_name=nb_cable.termination_b.device.name,
    #             interface_z_name=nb_cable.termination_b.name,
    #             remote_id=nb_cable.id,
    #             status="connected",
    #         )

    #         try:
    #             self.add(cable)
    #         except ObjectAlreadyExists:
    #             pass

    #         nbr_cables += 1

    #     LOGGER.debug("%s | Found %s cables in nautobot for %s", self.name, nbr_cables, site.name)

    # def get_intf_from_nautobot(self, device_name, intf_name):
    #     """Get an interface from Nautobot based on the name of the device and the name of the interface.
    #     Exactly one return must be returned from Nautobot, the function will return False if more than 1 result are returned.
    #     Args:
    #         device_name (str): name of the device in nautobot
    #         intf_name (str): name of the interface in Nautobot
    #     Returns:
    #         NautobotInterface, bool: Interface in DiffSync format
    #     """
    #     intfs = self.nautobot.dcim.interfaces.filter(name=intf_name, device=device_name)

    #     if len(intfs) == 0:
    #         # LOGGER.debug("Unable to find the interface in Nautobot for %s %s, nothing returned", device_name, intf_name)
    #         return False

    #     if len(intfs) > 1:
    #         LOGGER.warning(
    #             "Unable to find the proper interface in Nautobot for %s %s, more than 1 element returned",
    #             device_name,
    #             intf_name,
    #         )
    #         return False

    #     intf = self.interface(name=intf_name, device_name=device_name, remote_id=intfs[0].id)
    #     intf = self.apply_model_flag(intf, intfs[0])

    #     if intfs[0].connected_endpoint_type:
    #         intf.connected_endpoint_type = intfs[0].connected_endpoint_type

    #     self.add(intf)

    #     return intf