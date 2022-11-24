"""Extension of the base Models for the NautobotORMAdapter."""
import logging
from typing import Optional

from nautobot.dcim import models as dcim_models
from nautobot.ipam import models as ipam_models
from nautobot.extras import models as extras_models

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


def get_fk(fks, diffsync, key, value):
    """Function to get the pk of an object, given information stored in ORM."""
    # fks comes from self._foreign_keys
    # key matches a key in `_foreign_keys` which is the local attribute
    # value is the get_unique_id() we are looking for
    if key in list(fks.keys()):
        model = [val for _key, val in fks.items() if _key == key][0]
        key_model = diffsync.meta[model]
        pkey = diffsync.get(model, value).pk
    return key_model.objects.get(pk=pkey)


class NautobotMixin:
    """MixIn class to handle sync generically."""

    @classmethod
    def create(cls, diffsync, ids, attrs):
        """Create Method to handle generically."""
        self = super().create(ids=ids, diffsync=diffsync, attrs=attrs)
        db_model = cls.Meta.model
        obj = db_model()
        instance_values = {**ids, **attrs}
        combined = (
            list(self._foreign_key.keys()) + list(self._many_to_many.keys()) + list(self._generic_relation.keys())
        )
        for key, value in instance_values.items():
            if hasattr(self, "_skip") and key in self._skip:
                continue
            if key not in combined:
                setattr(obj, key, value)
            else:
                if not value:  # need to find the value of the other object, if none exists, that won't work
                    continue
                if key in list(self._generic_relation.keys()):
                    with_parent = {
                        key: self._generic_relation[key]["parent"] for key in list(self._generic_relation.keys())
                    }
                    with_values = "__".join(
                        [instance_values[key] for key in list(self._generic_relation[key]["identifiers"])]
                    )
                    db_obj = get_fk(with_parent, diffsync, key, with_values)
                    setattr(obj, self._generic_relation[key]["attr"], db_obj)
                if key in list(self._foreign_key.keys()):
                    db_obj = get_fk(self._foreign_key, diffsync, key, value)
                    setattr(obj, key, db_obj)
                if key in list(self._many_to_many.keys()):
                    if isinstance(value, list):
                        for val in value:
                            db_obj = get_fk(self._many_to_many, diffsync, key, val)
                            getattr(obj, key).add(db_obj)
                    else:
                        db_obj = get_fk(self._many_to_many, diffsync, key, value)
                        obj.set(db_obj)

        obj.validated_save()
        if not self.pk:
            setattr(self, "pk", obj.pk)
        return self

    def update(self, attrs):  # pylint: disable=too-many-branches
        """Create Method to handle generically."""
        db_model = self.Meta.model
        diffsync = self.diffsync
        combined = list(self._foreign_key.keys()) + list(self._many_to_many.keys())
        instance_values = {**attrs}
        _vars = self.get_identifiers()
        for key, val in _vars.items():
            if key in list(self._foreign_key.keys()):
                db_obj = get_fk(self._foreign_key, diffsync, key, val)
                _vars[key] = str(db_obj.pk)
            if key in list(self._many_to_many.keys()):
                db_obj = get_fk(self._many_to_many, diffsync, key, val)
                _vars[key] = str(db_obj.pk)

        obj = db_model.objects.get(**_vars)

        for key, value in instance_values.items():
            if hasattr(self, "_skip") and key in self._skip:
                continue
            if key not in combined:
                setattr(obj, key, value)
            else:
                if not value:  # need to find the value of the other object, if none exists, that won't work
                    continue
                if key in list(self._generic_relation.keys()):
                    with_parent = {
                        key: self._generic_relation[key]["parent"] for key in list(self._generic_relation.keys())
                    }
                    with_values = "__".join(
                        [instance_values[key] for key in list(self._generic_relation[key]["identifiers"])]
                    )
                    db_obj = get_fk(with_parent, diffsync, key, with_values)
                    setattr(obj, self._generic_relation[key]["attr"], db_obj)
                if key in list(self._foreign_key.keys()):
                    db_obj = get_fk(self._foreign_key, diffsync, key, value)
                    setattr(obj, key, db_obj)
                if key in list(self._many_to_many.keys()):
                    if isinstance(value, list):
                        for val in value:
                            db_obj = get_fk(self._many_to_many, diffsync, key, val)
                            getattr(obj, key).add(db_obj)
                    else:
                        db_obj = get_fk(self._many_to_many, diffsync, key, value)
                        obj.set(db_obj)
        obj.save()
        return super().update(attrs)

    def delete(self):
        """Create Method to handle generically."""
        db_model = self.Meta.model
        obj = db_model.objects.get(pk=self.pk)
        obj.delete()

        super().delete()
        return self


class NautobotSite(Site):
    """Extension of the Site model."""

    _attributes = ("pk",)
    _unique_fields = ("pk",)

    class Meta:
        """Boilerplate form Meta data for NautobotSite."""

        model = dcim_models.Site


class NautobotDevice(Device):
    """Extension of the Device model."""

    _attributes = ("pk",)
    _unique_fields = ("pk",)

    # device_tag_id: Optional[str]

    class Meta:
        """Boilerplate form Meta data for NautobotDevice."""

        model = dcim_models.Device


class NautobotInterface(NautobotMixin, Interface):
    """Extension of the Interface model."""

    _attributes = Interface._attributes + ("pk",)
    _unique_fields = ("pk",)
    pk: Optional[str]
    connected_endpoint_type: Optional[str]

    class Meta:
        """Boilerplate form Meta data for NautobotInterface."""

        model = dcim_models.Interface


class NautobotIPAddress(NautobotMixin, IPAddress):
    """Extension of the IPAddress model."""

    _attributes = IPAddress._attributes + ("pk",)
    _unique_fields = ("pk",)
    pk: Optional[str]

    class Meta:
        """Boilerplate form Meta data for NautobotIPAddress."""

        model = ipam_models.IPAddress


class NautobotPrefix(NautobotMixin, Prefix):
    """Extension of the Prefix model."""

    _attributes = Prefix._attributes + ("pk",)
    _unique_fields = ("pk",)
    pk: Optional[str]

    class Meta:
        """Boilerplate form Meta data for NautobotPrefix."""

        model = ipam_models.Prefix


class NautobotVlan(NautobotMixin, Vlan):
    """Extension of the Vlan model."""

    _attributes = Vlan._attributes + ("pk",)
    _unique_fields = ("pk",)
    pk: Optional[str]
    tag_prefix: str = "device="

    class Meta:
        """Boilerplate form Meta data for NautobotVlan."""

        model = ipam_models.VLAN


class NautobotCable(Cable):
    """Extension of the Cable model."""

    _attributes = ("pk",)
    _unique_fields = ("pk",)
    pk: Optional[str]
    termination_a_id: Optional[str]
    termination_z_id: Optional[str]

    class Meta:
        """Boilerplate form Meta data for NautobotCable."""

        model = dcim_models.Cable


class NautobotStatus(Status):
    """Extension of the Status model."""

    _unique_fields = ("pk",)
    _attributes = ("pk", "name")

    class Meta:
        """Boilerplate form Meta data for NautobotStatus."""

        model = extras_models.Status
