"""Alarmmeldung der Control-Box."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SyrupHub
from .const import DOMAIN
from .entity import SyrupEntity

# Im Ruhezustand meldet getALA den Wert FF.
NO_ALARM = "FF"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    hub: SyrupHub = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SyrupAlarm(hub)])


class SyrupAlarm(SyrupEntity, BinarySensorEntity):
    """Meldet, ob das Geraet einen Alarm anzeigt."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, hub: SyrupHub) -> None:
        super().__init__(hub, "alarm", "Alarm")

    @property
    def is_on(self) -> bool | None:
        value = self.value_of("ALA")
        if value is None:
            return None
        return value.strip().upper() != NO_ALARM
