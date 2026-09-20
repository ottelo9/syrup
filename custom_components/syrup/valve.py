"""Absperrventil der Control-Box.

Das Schalten läuft über einen ``set``-Befehl in der Antwort auf die nächste
Meldung des Geräts. Das Gerät meldet sich im Standardtakt alle 10 Sekunden,
so lange dauert es also maximal, bis ein Befehl greift.

Achtung: dass das Gerät ``setAB`` auf diesem Weg annimmt, ist aus dem Aufbau
der Cloud-Antwort abgeleitet und noch nicht am Gerät verifiziert. Verlasse
dich für den Wasserschaden-Ernstfall nicht darauf, bevor du es geprüft hast.
"""

from __future__ import annotations

from homeassistant.components.valve import (
    ValveDeviceClass,
    ValveEntity,
    ValveEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SyrupHub
from .const import AB_CLOSED, AB_OPEN, DOMAIN
from .entity import SyrupEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    hub: SyrupHub = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SyrupValve(hub)])


class SyrupValve(SyrupEntity, ValveEntity):
    """Das Absperrventil."""

    _attr_device_class = ValveDeviceClass.WATER
    _attr_reports_position = False
    _attr_supported_features = ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE

    def __init__(self, hub: SyrupHub) -> None:
        super().__init__(hub, "valve", "Absperrventil")

    @property
    def is_closed(self) -> bool | None:
        value = self.value_of("AB")
        if value is None:
            return None
        return value.strip() != AB_OPEN

    async def async_open_valve(self) -> None:
        self.hub.queue_command("AB", AB_OPEN)

    async def async_close_valve(self) -> None:
        self.hub.queue_command("AB", AB_CLOSED)
