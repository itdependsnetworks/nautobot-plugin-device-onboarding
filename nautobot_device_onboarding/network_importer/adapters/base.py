"""BaseAdapter for the network importer."""
import inspect
from diffsync import DiffSync, DiffSyncModel
from diffsync.exceptions import ObjectNotFound
from nornir import InitNornir
from netutils.ip import is_ip


from nautobot_device_onboarding.network_importer.models import (
    Site,
    Device,
    Interface,
    IPAddress,
    # Cable,
    Vlan,
    Prefix,
    Status,
)

from nautobot.dcim import models
from nautobot.extras import models as extras_models


class BaseAdapter(DiffSync):
    """Base Adapter for the network importer."""

    site = Site
    device = Device
    interface = Interface
    ip_address = IPAddress
    # cable = Cable
    vlan = Vlan
    status = Status
    prefix = Prefix
    _unique_data = {}

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

    def add(self, obj, *args, **kwargs):
        """Override add method to stuff data into dictionary based on the `_unique_fields`."""
        super().add(obj, *args, **kwargs)
        modelname = obj._modelname

        for attr in getattr(obj, "_unique_fields", []):
            if hasattr(obj, attr):
                if not self._unique_data.get(modelname):
                    self._unique_data[modelname] = {}
                if not self._unique_data[modelname].get(attr):
                    self._unique_data[modelname][attr] = {}
                self._unique_data[modelname][attr][getattr(obj, attr)] = obj

    def load(self):
        """Load the local cache with data from the remove system."""
        raise NotImplementedError

    def load_inventory(self):
        """Initialize and load all data from nautobot in the local cache."""
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
                    "queryset": models.Device.objects.filter(site__slug="ams01"),
                },
            },
        ) as nornir_obj:

            for device_obj in nornir_obj.inventory.hosts:
                result = nornir_obj.inventory.hosts[device_obj]
                site_slug = result.data.get("site")

                try:
                    site = self.get(self.site, site_slug)
                except ObjectNotFound:
                    site_id = models.Site.objects.get(slug=site_slug)
                    site = self.site(slug=site_slug, pk=str(site_id.pk))
                    self.add(site)

                device = self.device(slug=device_obj, site=site_slug, pk=str(result.data.get("id")))

                if is_ip(result.hostname):
                    device.primary_ip = result.hostname

                self.add(device)
            for status in extras_models.Status.objects.all():
                _st = self.status(slug=status.slug, name=status.name, pk=str(status.pk))
                self.add(_st)

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
