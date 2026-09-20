"""Gemeinsame Basis fuer alle SYRUP-Entitaeten."""

from __future__ import annotations

from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from . import SyrupHub
from .const import DOMAIN


class SyrupEntity(Entity):
    """Entitaet, die ihre Werte aus der letzten Geraetemeldung zieht."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, hub: SyrupHub, key: str, name: str) -> None:
        self.hub = hub
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"{hub.serial}_{key}"

    @property
    def device_info(self) -> DeviceInfo:
        message = self.hub.message
        return DeviceInfo(
            identifiers={(DOMAIN, self.hub.serial)},
            manufacturer="SYR",
            name=f"SYR {message.values.get('VER', 'Safe-T+')}" if message else "SYR Safe-T+",
            model=message.values.get("VER") if message else None,
            sw_version=message.firmware if message else None,
            serial_number=self.hub.serial,
            connections=(
                {(CONNECTION_NETWORK_MAC, format_mac(message.mac))}
                if message and message.mac
                else set()
            ),
        )

    @property
    def available(self) -> bool:
        return self.hub.message is not None

    def value_of(self, param: str) -> str | None:
        if self.hub.message is None:
            return None
        return self.hub.message.values.get(param)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self.hub.signal, self.async_write_ha_state
            )
        )
