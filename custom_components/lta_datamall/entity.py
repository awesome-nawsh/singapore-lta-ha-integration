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


def group_device_info(entry: ConfigEntry, group_key: str, name: str) -> DeviceInfo:
    """Themed sub-device grouping a subset of the always-on global entities
    (e.g. "Roads & Traffic", "Rail / MRT"). Hangs off the main hub device via
    ``via_device`` so the entities appear in a tidy tree rather than one flat
    list of ~19 items under a single device.
    """
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_group_{group_key}")},
        name=name,
        manufacturer=MANUFACTURER,
        entry_type=DeviceEntryType.SERVICE,
        configuration_url="https://datamall.lta.gov.sg/",
        via_device=(DOMAIN, entry.entry_id),
    )


def tracker_device_info(
    entry: ConfigEntry, tracker_key: str, name: str, parent_group_key: str
) -> DeviceInfo:
    """Device for a single user-added tracker (a bus stop, a carpark, ...).

    Nests under its themed category device (``parent_group_key``, e.g. "bus")
    rather than directly under the hub, so trackers group by type.
    """
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_{tracker_key}")},
        name=name,
        manufacturer=MANUFACTURER,
        via_device=(DOMAIN, f"{entry.entry_id}_group_{parent_group_key}"),
    )


class LTABaseEntity(CoordinatorEntity[LTACoordinator]):
    """Common base for every LTA DataMall entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: LTACoordinator, unique_id: str, device_info: DeviceInfo) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = unique_id
        self._attr_device_info = device_info
