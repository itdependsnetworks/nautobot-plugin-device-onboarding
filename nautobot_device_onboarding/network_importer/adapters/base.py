"""BaseAdapter for the network importer."""
import inspect
from diffsync import DiffSync, DiffSyncModel
from diffsync.exceptions import ObjectNotFound
from nornir import InitNornir
from netutils.ip import is_ip

from nautobot_device_onboarding.network_importer.models import Site, Device, Interface, IPAddress, Cable, Vlan, Prefix

from typing import List, Text, Type, Union


class BaseAdapter(DiffSync):
    """Base Adapter for the network importer."""

    site = Site
    device = Device
    interface = Interface
    ip_address = IPAddress
    # cable = Cable
    vlan = Vlan
    prefix = Prefix

    # settings_class = None
    # settings = None

    # def __init__(self, nornir, settings):
    #     """Initialize the base adapter and store the Nornir object locally."""
    #     super().__init__()
    #     self.nornir = nornir
    #     self.settings = self._validate_settings(settings)

    def _validate_settings(self, settings):
        """Load and validate the configuration based on the settings_class."""
        if self.settings_class:
            if settings and isinstance(settings, dict):
                return self.settings_class(**settings)  # pylint: disable=not-callable

            return self.settings_class()  # pylint: disable=not-callable

        return settings

    def load(self):
        """Load the local cache with data from the remove system."""
        raise NotImplementedError

    def load_inventory(self):
        """Initialize and load all data from nautobot in the local cache."""
        sites = {}

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
                    "queryset": Device.objects.filter(site__slug="ams01"),
                },
            },
        ) as nornir_obj:

            for device_obj in nornir_obj.inventory.hosts:
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

                if is_ip(result.hostname):
                    device.primary_ip = result.hostname

                self.add(device)

    def load_from_dict(self, data):
        """Load the data from a dictionary."""
        if hasattr(self, "top_level") and isinstance(getattr(self, "top_level"), list):
            value_order = self.top_level.copy()
        else:
            value_order = []

        for item in dir(self):
            _method = getattr(self, item)
            if item in value_order:
                continue
            if inspect.isclass(_method) and issubclass(_method, DiffSyncModel):
                value_order.append(item)
        for key in value_order:
            model_type = getattr(self, key)
            for values in data.get(key, {}).values():
                self.add(model_type(**values))

    def get_or_create_vlan(self, vlan, site=None):
        """Check if a vlan already exist before creating it. Returns the existing object if it already exist.

        Args:
            vlan (Vlan): Vlan object
            site (Site, optional): Site Object. Defaults to None.

        Returns:
            (Vlan, bool): return a tuple with the vlan and a bool to indicate of the vlan was created or not
        """
        modelname = vlan.get_type()
        uid = vlan.get_unique_id()

        try:
            return self.get(modelname, uid), False
        except ObjectNotFound:
            pass

        self.add(vlan)
        if site:
            site.add_child(vlan)

        return vlan, True

    def get_or_add(self, obj):
        """Add a new object or retrieve it if it already exists.

        Args:
            obj (DiffSyncModel): DiffSyncModel oject

        Returns:
            DiffSyncModel: DiffSyncObject retrieved from the datastore
            Bool: True if the object was created
        """
        modelname = obj.get_type()
        uid = obj.get_unique_id()

        try:
            return self.get(modelname, uid), False
        except ObjectNotFound:
            pass

        self.add(obj)

        return obj, True

    def get_by_attr(
        self,
        uid: Text,
        model: Union[Text, "DiffSyncModel", Type["DiffSyncModel"]],
        field: Text,
    ) -> List["DiffSyncModel"]:
        """Get multiple objects from the store by their unique IDs/Keys and type.

        Args:
            uids: List of unique id / key identifying object in the database.
            model: DiffSyncModel class or instance, or modelname string, that defines the type of the objects to retrieve

        Raises:
            ObjectNotFound: if any of the requested UIDs are not found in the store
        """
        for item in self.get_all(model):
            print(item)
            if hasattr(item, field) and getattr(item, field) == uid:
                return item
        raise ObjectNotFound(f"The model: {model} did not have an attribute: {field} of value: {uid} was not found")
