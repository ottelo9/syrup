"""Messwerte der Control-Box."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfPressure,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SyrupHub
from .const import DOMAIN
from .entity import SyrupEntity
from .protocol import parse_pressure_mbar, parse_voltage, parse_volume_liters, parse_volume_ml


@dataclass(frozen=True, kw_only=True)
class SyrupSensorDescription(SensorEntityDescription):
    """Beschreibt einen Messwert und wie er aus dem Rohwert entsteht."""

    param: str
    convert: Callable[[str | None], object] = lambda value: value


SENSORS: tuple[SyrupSensorDescription, ...] = (
    SyrupSensorDescription(
        key="pressure",
        param="BAR",
        name="Wasserdruck",
        convert=parse_pressure_mbar,
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.MBAR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SyrupSensorDescription(
        key="volume_total",
        param="VOL",
        name="Gesamtvolumen",
        convert=parse_volume_liters,
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SyrupSensorDescription(
        key="volume_current",
        param="AVO",
        name="Laufende Entnahme",
        convert=parse_volume_ml,
        native_unit_of_measurement=UnitOfVolume.MILLILITERS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SyrupSensorDescription(
        key="supply_voltage",
        param="NET",
        name="Versorgungsspannung",
        convert=parse_voltage,
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrupSensorDescription(
        key="alarm_code",
        param="ALA",
        name="Alarmcode",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrupSensorDescription(
        key="alarm_history",
        param="ALM",
        name="Alarmverlauf",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrupSensorDescription(
        key="service_date",
        param="SRV",
        name="Wartungsdatum",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    hub: SyrupHub = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(SyrupSensor(hub, description) for description in SENSORS)


class SyrupSensor(SyrupEntity, SensorEntity):
    """Ein einzelner Messwert."""

    entity_description: SyrupSensorDescription

    def __init__(self, hub: SyrupHub, description: SyrupSensorDescription) -> None:
        super().__init__(hub, description.key, description.name)
        self.entity_description = description

    @property
    def native_value(self):
        return self.entity_description.convert(self.value_of(self.entity_description.param))
