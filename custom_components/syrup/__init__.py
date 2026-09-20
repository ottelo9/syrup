"""SYRUP - SYR Safe-T+ Connect ohne Cloud.

Die Integration stellt den Endpunkt bereit, den die Control-Box sonst in der
Herstellercloud anspricht. Damit das Geraet hier landet, muss
``iot1.syrconnect.de`` im lokalen Netz auf diese Home-Assistant-Instanz
zeigen -- siehe README.
"""

from __future__ import annotations

import logging

from aiohttp import web
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.components.http import HomeAssistantView

from . import codec
from .const import (
    CONF_POLL_INTERVAL,
    CONF_RELAY_URL,
    CONF_SERIAL,
    DEFAULT_POLL_INTERVAL,
    DEVICE_ENDPOINT,
    DOMAIN,
    SIGNAL_UPDATE,
)

VIEW_REGISTERED = f"{DOMAIN}_view_registered"
from .protocol import DeviceMessage, build_cloud_response, parse_device_message

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.VALVE]


class SyrupHub:
    """Haelt den Zustand eines Geraets und die offenen Schaltbefehle."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.serial: str = entry.data[CONF_SERIAL]
        self.poll_interval: int = entry.options.get(
            CONF_POLL_INTERVAL, entry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
        )
        self.relay_url: str = entry.options.get(
            CONF_RELAY_URL, entry.data.get(CONF_RELAY_URL, "")
        )
        self.message: DeviceMessage | None = None
        self.pending: dict[str, str] = {}
        self.last_seen: float | None = None

    @property
    def signal(self) -> str:
        return f"{SIGNAL_UPDATE}_{self.serial}"

    def queue_command(self, param: str, value: str) -> None:
        """Einen Befehl fuer die naechste Antwort an das Geraet vormerken."""
        self.pending[param] = value

    def apply(self, message: DeviceMessage) -> None:
        self.message = message
        self.last_seen = self.hass.loop.time()
        async_dispatcher_send(self.hass, self.signal)


class SyrupDeviceView(HomeAssistantView):
    """Nimmt die Meldungen der Control-Box entgegen."""

    url = DEVICE_ENDPOINT
    name = f"api:{DOMAIN}"
    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def post(self, request: web.Request) -> web.Response:
        body = await request.text()
        try:
            payload, cp = codec.extract_payload(body)
            key = codec.find_key(payload)
            inner = codec.decode(payload, key)
        except codec.DecodeError as err:
            _LOGGER.warning("Nachricht nicht lesbar: %s", err)
            return web.Response(status=400, text="")

        message = parse_device_message(inner)
        _LOGGER.debug("Von %s (Schluessel 0x%02X): %s", message.serial, key, inner)

        hub = self._find_hub(message.serial)
        if hub is None:
            _LOGGER.info(
                "Meldung von unbekanntem Geraet %s - Integration dafuer nicht eingerichtet",
                message.serial,
            )
            return await self._respond(None, key, cp, body)

        hub.apply(message)
        return await self._respond(hub, key, cp, body)

    def _find_hub(self, serial: str | None) -> SyrupHub | None:
        hubs: dict[str, SyrupHub] = self.hass.data.get(DOMAIN, {})
        if serial:
            for hub in hubs.values():
                if hub.serial == serial:
                    return hub
        return None

    async def _respond(
        self, hub: SyrupHub | None, key: int, cp: str, body: str
    ) -> web.Response:
        """Antworten -- entweder selbst oder durch Weiterreichen an die Cloud.

        Liegt ein Schaltbefehl an, antwortet die Integration selbst, weil die
        Cloud den Befehl nicht kennt.
        """
        relay_url = hub.relay_url if hub else ""
        if relay_url and not (hub and hub.pending):
            if relayed := await self._relay(relay_url, body):
                return relayed

        commands = {}
        if hub and hub.pending:
            commands = dict(hub.pending)
            hub.pending.clear()
        interval = hub.poll_interval if hub else DEFAULT_POLL_INTERVAL
        inner = build_cloud_response(commands=commands, poll_interval=interval)
        # Denselben Schluessel benutzen, den das Geraet gerade geschickt hat.
        return web.Response(
            text=codec.build_body(inner, key, cp),
            content_type="text/xml",
            charset="utf-8",
        )

    async def _relay(self, url: str, body: str) -> web.Response | None:
        """Die Nachricht an die echte Cloud weitergeben und deren Antwort nehmen."""
        session = async_get_clientsession(self.hass)
        try:
            async with session.post(
                url,
                data=body.encode("utf-8"),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10,
            ) as response:
                text = await response.text()
                return web.Response(
                    text=text, content_type="text/xml", charset="utf-8"
                )
        except Exception as err:  # noqa: BLE001 - Cloud darf ausfallen
            _LOGGER.warning("Weiterleitung an %s fehlgeschlagen: %s", url, err)
            return None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Eine eingerichtete Control-Box aufsetzen."""
    hubs = hass.data.setdefault(DOMAIN, {})
    if not hass.data.get(VIEW_REGISTERED):
        hass.http.register_view(SyrupDeviceView(hass))
        hass.data[VIEW_REGISTERED] = True
    hubs[entry.entry_id] = SyrupHub(hass, entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_options))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Eine Control-Box wieder entfernen."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded


async def _async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
