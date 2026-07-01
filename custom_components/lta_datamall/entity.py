"""Shared entity/device helpers for LTA DataMall."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import LTACoordinator


def hub_device_info(entry: ConfigEntry) -> DeviceInfo:
    """Device that groups the always-on, Singapore-wide global entities."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="LTA DataMall",
        manufacturer=MANUFACTURER,
        entry_type=DeviceEntryType.SERVICE,
        configuration_url="https://datamall.lta.gov.sg/",
    )


def tracker_device_info(entry: ConfigEntry, tracker_key: str, name: str) -> DeviceInfo:
    """Device for a single user-added tracker (a bus stop, a carpark, ...)."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_{tracker_key}")},
        name=name,
        manufacturer=MANUFACTURER,
        via_device=(DOMAIN, entry.entry_id),
    )


class LTABaseEntity(CoordinatorEntity[LTACoordinator]):
    """Common base for every LTA DataMall entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: LTACoordinator, unique_id: str, device_info: DeviceInfo) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = unique_id
        self._attr_device_info = device_info
