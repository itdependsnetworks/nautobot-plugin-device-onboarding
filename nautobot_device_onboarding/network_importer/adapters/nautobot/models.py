"""Extension of the base Models for the NautobotAPIAdapter."""
from ipaddress import ip_address
from itertools import combinations
from typing import Optional
import logging

# import pynautobot
from diffsync.exceptions import ObjectNotFound
from diffsync import DiffSync, DiffSyncModel  # pylint: disable=unused-import

from nautobot.dcim import models as dcim_models
from nautobot.ipam import models as ipam_models
from nautobot.extras import models as extras_models

from nautobot_device_onboarding.network_importer.adapters.nautobot.exceptions import NautobotObjectNotValid
from nautobot_device_onboarding.network_importer.models import (  # pylint: disable=import-error
    Site,
    Device,
    Interface,
    IPAddress,
    Cable,
    Prefix,
    Vlan,
    Status,
)

LOGGER = logging.getLogger(__name__)
import structlog  # type: ignore


def get_fk(fks, diffsync, key, value):
    if key in list(fks.values()):
        _key = [k for k, v in fks.items() if v == key][0]
        key_model = diffsync.meta[_key]
        pk = diffsync.get(key, value).pk
        return key_model.objects.get(pk=pk)


class NautobotMixin:
    @classmethod
    def create(cls, diffsync, ids, attrs):
        self = super().create(ids=ids, diffsync=diffsync, attrs=attrs)
        db_model = cls.Meta.model
        obj = db_model()
        instance_values = {**ids, **attrs}
        combined = list(self._foreign_key.values()) + list(self._many_to_many.values())
        for key, value in instance_values.items():
            if hasattr(self, "_skip") and key in self._skip:
                continue
            elif key not in combined:
                setattr(obj, key, value)
            else:
                if not value:  # need to find the value of the other object, if none exists, that won't work
                    continue
                if key in list(self._foreign_key.values()):
                    db_obj = get_fk(self._foreign_key, diffsync, key, value)
                    setattr(obj, key, db_obj)
                if key in list(self._many_to_many.values()):
                    db_obj = get_fk(self._many_to_many, diffsync, key, value)
                    obj.set(db_obj)
        obj.validated_save()

        return self

    def update(self, attrs):

        db_model = self.Meta.model
        diffsync = self.diffsync
        combined = list(self._foreign_key.values()) + list(self._many_to_many.values())
        instance_values = {**attrs}
        vars = self.get_identifiers()
        for key, val in vars.items():
            if key in list(self._foreign_key.values()):
                db_obj = get_fk(self._foreign_key, diffsync, key, val)
                vars[key] = str(db_obj.pk)
            if key in list(self._many_to_many.values()):
                db_obj = get_fk(self._many_to_many, diffsync, key, val)
                vars[key] = str(db_obj.pk)

        obj = db_model.objects.get(**vars)

        for key, value in instance_values.items():
            if hasattr(self, "_skip") and key in self._skip:
                continue
            elif key not in combined:
                setattr(obj, key, value)
            else:
                if not value:  # need to find the value of the other object, if none exists, that won't work
                    continue
                if key in list(self._foreign_key.values()):
                    db_obj = get_fk(self._foreign_key, diffsync, key, value)
                    setattr(obj, key, db_obj)
                if key in list(self._many_to_many.values()):
                    db_obj = get_fk(self._many_to_many, diffsync, key, value)
                    obj.set(db_obj)
        obj.save()
        return super().update(attrs)

    def delete(self):

        db_model = self.Meta.model
        diffsync = self.diffsync
        vars = self.get_identifiers()
        for key, val in vars.items():
            if key in list(self._foreign_key.values()):
                db_obj = get_fk(self._foreign_key, diffsync, key, val)
                vars[key] = str(db_obj.pk)
            if key in list(self._many_to_many.values()):
                db_obj = get_fk(self._many_to_many, diffsync, key, val)
                vars[key] = str(db_obj.pk)

        obj = db_model.objects.get(**vars)
        obj.delete()

        super().delete()
        return self


class NautobotSite(Site):
    """Extension of the Site model."""

    class Meta:
        model = dcim_models.Site


class NautobotDevice(Device):
    """Extension of the Device model."""

    # device_tag_id: Optional[str]

    class Meta:
        model = dcim_models.Device


#     def get_device_tag_id(self):
#         """Get the Nautobot id of the tag for this device.
#         If the ID is already present locally return it
#         If not try to retrieve it from Nautobot or create it in Nautobot if needed
#         Returns:
#             device_tag_id (str)
#         """
#         if self.device_tag_id:
#             return self.device_tag_id

#         tag = self.diffsync.nautobot.extras.tags.get(name=f"device={self.name}")

#         if not tag:
#             tag = self.diffsync.nautobot.extras.tags.create(name=f"device={self.name}", slug=f"device__{self.name}")

#         self.device_tag_id = tag.id
#         return self.device_tag_id


class NautobotInterface(NautobotMixin, Interface):
    """Extension of the Interface model."""

    _unique_fields = ("pk",)
    pk: Optional[str]
    connected_endpoint_type: Optional[str]

    class Meta:
        model = dcim_models.Interface


class NautobotIPAddress(NautobotMixin, IPAddress):
    """Extension of the IPAddress model."""

    _unique_fields = ("pk",)
    pk: Optional[str]

    class Meta:
        model = ipam_models.IPAddress


class NautobotPrefix(NautobotMixin, Prefix):
    """Extension of the Prefix model."""

    _unique_fields = ("pk",)
    pk: Optional[str]

    class Meta:
        model = ipam_models.Prefix


class NautobotVlan(NautobotMixin, Vlan):
    """Extension of the Vlan model."""

    _unique_fields = ("pk",)
    pk: Optional[str]
    tag_prefix: str = "device="

    class Meta:
        model = ipam_models.VLAN


class NautobotCable(Cable):
    """Extension of the Cable model."""

    _unique_fields = ("pk",)
    pk: Optional[str]
    termination_a_id: Optional[str]
    termination_z_id: Optional[str]

    class Meta:
        model = dcim_models.Cable


class NautobotStatus(Status):
    """Extension of the Status model."""

    class Meta:
        model = extras_models.Status
