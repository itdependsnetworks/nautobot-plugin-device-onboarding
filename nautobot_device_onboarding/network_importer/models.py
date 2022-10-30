"""DiffSync Models for the network importer."""
from typing import List, Optional


from diffsync import DiffSyncModel


class Site(DiffSyncModel):
    """Site Model based on DiffSyncModel.

    A site must have a unique name and can be composed of Vlans and Prefixes.
    """

    _modelname = "site"
    _identifiers = ("slug",)
    _children = {"vlan": "vlans", "prefix": "prefixes"}
    _generic_relation = {}

    slug: str
    prefixes: List = list()
    vlans: List[str] = list()
    pk: Optional[str]


class Device(DiffSyncModel):
    """Device Model based on DiffSyncModel.

    A device must have a unique name and can be part of a site.
    """

    _modelname = "device"
    _identifiers = ("slug",)
    _attributes = ("site", "primary_ip")
    _children = {"interface": "interfaces"}
    _generic_relation = {}

    slug: str
    site: Optional[str]
    interfaces: List = list()
    primary_ip: Optional[str]
    pk: Optional[str]

    # TODO: Not currently used
    platform: Optional[str]
    model: Optional[str]  # device_type
    device_role: Optional[str]
    vendor: Optional[str]  # a.platform.manufacturer


class Interface(DiffSyncModel):  # pylint: disable=too-many-instance-attributes
    """Interface Model based on DiffSyncModel.

    An interface must be attached to a device and the name must be unique per device.
    """

    _modelname = "interface"
    _identifiers = ("device", "name")
    _shortname = ("name",)
    # TODO: Why are we setting mtu, active, and speed if not actually considered?
    _attributes = (
        "description",
        # "mtu",
        # "is_virtual",
        # "is_lag",
        # "is_lag_member",
        # "parent",
        "mode",
        # "switchport_mode",
        "tagged_vlans",
        "untagged_vlan",
        # "ip_addresses",
        "status",
        "type",
    )
    _children = {"ip_address": "ip_addresses"}
    _foreign_key = {"device": "device", "status": "status"}
    _many_to_many = {"tagged_vlans": "vlan"}
    _generic_relation = {}

    name: str
    device: str
    status: str
    type: str

    description: Optional[str]
    mtu: Optional[int]
    mode: Optional[str]  # TRUNK, ACCESS, L3, NONE
    # is_virtual: Optional[bool]
    # is_lag: Optional[bool]
    ip_addresses: List[str] = list()
    tagged_vlans: List[str] = list()
    untagged_vlan: Optional[str]

    parent: Optional[str]  # Not the same

    speed: Optional[int]  # Not in Nautobot
    switchport_mode: Optional[str] = "NONE"  # Not in Nautobot
    is_lag_member: Optional[bool]  # Not in Nautobot
    active: Optional[bool]  # Not in Nautobot
    lag_members: List[str] = list()  # Not in Nautobot


class IPAddress(DiffSyncModel):
    """IPAddress Model based on DiffSyncModel.

    An IP address must be unique and can be associated with an interface.
    """

    _modelname = "ip_address"
    _identifiers = ("device", "interface", "address")
    _attributes = ("status",)
    _foreign_key = {"status": "status"}
    _many_to_many = {}
    _generic_relation = {
        "interface": {"parent": "interface", "identifiers": ["device", "interface"], "attr": "assigned_object"}
    }

    device: str  # interface.all()[0].device
    interface: str
    address: str
    status: str


class Prefix(DiffSyncModel):
    """Prefix Model based on DiffSyncModel.

    An Prefix must be associated with a Site and must be unique within a site.
    """

    _modelname = "prefix"
    _identifiers = ("site", "prefix")
    _attributes = ("vlan", "status")
    _foreign_key = {"site": "site", "status": "status"}
    _many_to_many = {}
    _generic_relation = {}

    prefix: str
    site: Optional[str]  # site
    vlan: Optional[str]
    status: str


class Vlan(DiffSyncModel):
    """Vlan Model based on DiffSyncModel.

    An Vlan must be associated with a Site and the vlan_id msut be unique within a site.
    """

    _modelname = "vlan"
    _identifiers = ("site", "vid")
    _attributes = ("name", "status")
    _foreign_key = {"site": "site", "status": "status"}
    _many_to_many = {}
    _generic_relation = {}

    vid: int
    site: str
    status: str
    name: Optional[str]

    associations: List[str] = list()

    def add_device(self, device):
        """Add a device to the list of associated devices.

        Args:
            device (str): name of a device to associate with this VLAN
        """
        if device not in self.associations:
            self.associations.append(device)
            self.associations = sorted(self.associations)


class Cable(DiffSyncModel):
    """Cable Model based on DiffSyncModel."""

    _modelname = "cable"
    _identifiers = (
        "termination_a_device",
        "termination_a",
        "termination_b_device",
        "termination_b",
    )
    _generic_relation = {}

    termination_a_device: str  # mapped to _termination_a_device
    termination_a: str
    termination_b_device: str  # mapped to _termination_b_device
    termination_b: str

    source: Optional[str]  # Not in Nautobot
    is_valid: bool = True  # Not in Nautobot
    error: Optional[str]  # Not in Nautobot

    # TODO: This should be moved to the adapter if needed.
    # def __init__(self, *args, **kwargs):
    #     """Ensure the cable is unique by ordering the devices alphabetically."""
    #     if "termination_a_device" not in kwargs or "termination_b_device" not in kwargs:
    #         raise ValueError("termination_a_device and termination_b_device are mandatory")
    #     if not kwargs["termination_a_device"] or not kwargs["termination_b_device"]:
    #         raise ValueError("termination_a_device and termination_b_device are mandatory and must not be None")

    #     keys_to_copy = ["termination_a_device", "termination_a", "termination_b_device", "termination_b"]
    #     ids = {key: kwargs[key] for key in keys_to_copy}

    #     devices = [kwargs["termination_a_device"], kwargs["termination_b_device"]]
    #     if sorted(devices) != devices:
    #         ids["termination_a_device"] = kwargs["termination_b_device"]
    #         ids["termination_a"] = kwargs["termination_b"]
    #         ids["termination_b_device"] = kwargs["termination_a_device"]
    #         ids["termination_b"] = kwargs["termination_a"]

    #     for key in keys_to_copy:
    #         del kwargs[key]

    #     super().__init__(*args, **ids, **kwargs)

    # def get_device_intf(self, side):
    #     """Get the device name and the interface name for a given side.

    #     Args:
    #         side (str): site to query, must be either a or z

    #     Raises:
    #         ValueError: when the side is not either a or z

    #     Returns:
    #         (device (str), interface (str))
    #     """
    #     if side.lower() == "a":
    #         return self.termination_a_device, self.termination_a

    #     if side.lower() == "z":
    #         return self.termination_b_device, self.termination_b

    #     raise ValueError("side must be either 'a' or 'z'")


class Status(DiffSyncModel):
    """Status Model based on DiffSyncModel.

    A status must have a unique name and can be composed of Vlans and Prefixes.
    """

    _modelname = "status"
    _identifiers = ("slug",)
    _attributes = ("name",)
    _generic_relation = {}

    slug: str
    name: str
    pk: Optional[str]
