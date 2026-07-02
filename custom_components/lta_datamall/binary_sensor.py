"""Binary sensor platform for LTA DataMall: flood alerts and train service
alerts. Both are global, always-on datasets - see sensor.py's module
docstring for the tiering rationale.
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ALERT_TRAIN_LINES,
    DOMAIN,
    EP_FLOOD_ALERTS,
    EP_TRAIN_SERVICE_ALERTS,
    GROUP_ENVIRONMENT,
    GROUP_RAIL,
    MAX_ATTR_LIST_ITEMS,
)
from .coordinator import LTACoordinator
from .entity import LTABaseEntity, group_device_info


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up LTA DataMall binary sensors for a config entry."""
    runtime = hass.data[DOMAIN][entry.entry_id]
    global_coordinators: dict[str, LTACoordinator] = runtime["global"]
    environment_device = group_device_info(entry, *GROUP_ENVIRONMENT)
    rail_device = group_device_info(entry, *GROUP_RAIL)

    entities: list[BinarySensorEntity] = [
        FloodAlertBinarySensor(global_coordinators[EP_FLOOD_ALERTS], entry, environment_device)
    ]
    train_coordinator = global_coordinators[EP_TRAIN_SERVICE_ALERTS]
    for line in ALERT_TRAIN_LINES:
        entities.append(TrainServiceAlertBinarySensor(train_coordinator, entry, rail_device, line))

    async_add_entities(entities)


class FloodAlertBinarySensor(LTABaseEntity, BinarySensorEntity):
    """On when PUB has one or more active flood alerts."""

    _attr_name = "Flood Alert"
    _attr_device_class = "safety"

    def __init__(self, coordinator: LTACoordinator, entry: ConfigEntry, device) -> None:
        super().__init__(coordinator, f"{entry.entry_id}_flood_alert", device)

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data or []
        return {"alerts": data[:MAX_ATTR_LIST_ITEMS]}


def _parse_train_alerts(raw: Any) -> dict[str, dict]:
    """Normalise the Train Service Alerts response into {line: segment_info}.

    The Train Service Alerts endpoint returns ``value`` as a single object,
    not a list - e.g. normal operation is {"value": {"Status": 1, ...}} and a
    disruption is {"value": {"Status": 2, "AffectedSegments": [{"Line": ...}]}}.
    Some OData responses do wrap single records in a one-element list though,
    so accept both shapes to be safe.
    """
    if not isinstance(raw, dict):
        return {}
    value = raw.get("value")
    if isinstance(value, list):
        record = value[0] if value else {}
    elif isinstance(value, dict):
        record = value
    else:
        record = {}
    if record.get("Status") != 2:
        return {}
    by_line: dict[str, dict] = {}
    for segment in record.get("AffectedSegments", []):
        line = segment.get("Line")
        if line:
            by_line[line] = segment
    return by_line


class TrainServiceAlertBinarySensor(LTABaseEntity, BinarySensorEntity):
    """On when the given train line currently has a disruption/major delay."""

    _attr_device_class = "problem"

    def __init__(self, coordinator: LTACoordinator, entry: ConfigEntry, device, line: str) -> None:
        super().__init__(coordinator, f"{entry.entry_id}_train_alert_{line}", device)
        self._line = line
        self._attr_name = f"{line} Line Service Alert"

    @property
    def is_on(self) -> bool:
        return self._line in _parse_train_alerts(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict:
        segment = _parse_train_alerts(self.coordinator.data).get(self._line)
        if not segment:
            return {}
        return {
            "direction": segment.get("Direction"),
            "stations": segment.get("Stations"),
            "free_public_bus": segment.get("FreePublicBus"),
            "free_mrt_shuttle": segment.get("FreeMRTShuttle"),
            "mrt_shuttle_direction": segment.get("MRTShuttleDirection"),
            "message": segment.get("Message"),
        }
