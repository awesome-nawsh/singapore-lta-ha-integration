"""The LTA DataMall integration.

Sets up one API client and a set of DataUpdateCoordinators per config entry:
always-on global coordinators for Singapore-wide datasets, lazily-created
shared coordinators for datasets that back item-picking trackers (carpark,
traffic camera), and one dedicated coordinator per tracker that takes a
location/line filter (bus stop, EV postal code, bicycle parking point,
train line crowd density).
"""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .api import LTAApiClient, LTAApiError, LTAAuthError
from .entity import group_device_info, hub_device_info
from .const import (
    CONF_ACCOUNT_KEY,
    CONF_BUS_STOP_CODE,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_POSTAL_CODE,
    CONF_RADIUS_KM,
    CONF_TRACKER_TYPE,
    CONF_TRAIN_LINE,
    DOMAIN,
    EP_CARPARK_AVAILABILITY,
    EP_TRAFFIC_IMAGES,
    GROUP_BICYCLE,
    GROUP_BUS,
    GROUP_CARPARKS,
    GROUP_ENVIRONMENT,
    GROUP_EV,
    GROUP_RAIL,
    GROUP_ROADS,
    GROUP_TAXIS,
    PLATFORMS,
    TRACKER_CATEGORY,
    TRACKER_BICYCLE_PARKING,
    TRACKER_BUS_STOP,
    TRACKER_CAMERA,
    TRACKER_CARPARK,
    TRACKER_CROWD_LINE,
    TRACKER_EV_POSTAL,
)
from .coordinator import (
    async_build_global_coordinators,
    async_create_bicycle_parking_coordinator,
    async_create_bus_stop_coordinator,
    async_create_crowd_line_coordinator,
    async_create_ev_postal_coordinator,
    async_get_or_create_shared_coordinator,
)
from .services import async_register_services, async_unregister_services

_LOGGER = logging.getLogger(__name__)

# Maps the key portion of a global entity's unique_id (i.e. the part after
# "<entry_id>_") to the themed sub-device it belongs on. Train-alert entities
# (unique_id key "train_alert_<LINE>") are handled by prefix in the helper.
_GLOBAL_ENTITY_GROUPS: dict[str, tuple[str, str]] = {
    "traffic_incidents": GROUP_ROADS,
    "faulty_traffic_lights": GROUP_ROADS,
    "planned_road_openings": GROUP_ROADS,
    "approved_road_works": GROUP_ROADS,
    "vms_messages": GROUP_ROADS,
    "est_travel_times": GROUP_ROADS,
    "traffic_speed_bands": GROUP_ROADS,
    "taxis_available": GROUP_TAXIS,
    "lift_maintenance": GROUP_RAIL,
    "flood_alert": GROUP_ENVIRONMENT,
}


def _group_for_unique_id(entry_id: str, unique_id: str) -> tuple[str, str] | None:
    """Return the themed group tuple a global entity belongs to, or None."""
    prefix = f"{entry_id}_"
    if not unique_id.startswith(prefix):
        return None
    key = unique_id[len(prefix):]
    if key.startswith("train_alert_"):
        return GROUP_RAIL
    return _GLOBAL_ENTITY_GROUPS.get(key)


@callback
def _register_devices_and_migrate(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Register the hub + themed group devices and move any pre-existing global
    entities onto their group device.

    Changing an entity's ``device_info`` to a different device does not, by
    itself, re-home an already-registered entity - HA creates the new device
    but leaves the entity pointing at its original one. Installs upgraded from
    a version where all globals sat on the single hub device therefore need an
    explicit registry migration; this is a no-op on fresh installs and once
    migrated.
    """
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)

    # The top-level hub, which serves as the via_device parent for the themed
    # groups and per-tracker category devices.
    dev_reg.async_get_or_create(config_entry_id=entry.entry_id, **hub_device_info(entry))

    group_device_ids: dict[tuple[str, str], str] = {}

    def _ensure_group(group: tuple[str, str]) -> str:
        if group not in group_device_ids:
            device = dev_reg.async_get_or_create(
                config_entry_id=entry.entry_id, **group_device_info(entry, *group)
            )
            group_device_ids[group] = device.id
        return group_device_ids[group]

    # Global-entity groups are always present.
    for group in (GROUP_ROADS, GROUP_RAIL, GROUP_TAXIS, GROUP_ENVIRONMENT):
        _ensure_group(group)

    # Tracker category groups (Bus, Carparks, ...) only for tracker types that
    # are actually configured, so empty category devices don't clutter the UI.
    for tracker in entry.options.get("trackers", []):
        category = TRACKER_CATEGORY.get(tracker.get(CONF_TRACKER_TYPE))
        if category is not None:
            _ensure_group(category)

    # Move any pre-existing global entities onto their group device (changing
    # device_info alone does not re-home an already-registered entity).
    for reg_entry in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
        group = _group_for_unique_id(entry.entry_id, reg_entry.unique_id)
        if group is None:
            continue
        target_device_id = group_device_ids[group]
        if reg_entry.device_id != target_device_id:
            ent_reg.async_update_entity(reg_entry.entity_id, device_id=target_device_id)

    # Re-parent any pre-existing tracker devices under their category device.
    entry_prefix = f"{entry.entry_id}_"
    tracker_prefix_groups = {
        "bus_stop_": GROUP_BUS,
        "carpark_": GROUP_CARPARKS,
        "ev_": GROUP_EV,
        "bicycle_": GROUP_BICYCLE,
        "crowd_": GROUP_RAIL,
        "camera_": GROUP_ROADS,
    }
    for device in dr.async_entries_for_config_entry(dev_reg, entry.entry_id):
        ident = next((i[1] for i in device.identifiers if i[0] == DOMAIN), None)
        if not ident or not ident.startswith(entry_prefix):
            continue
        key = ident[len(entry_prefix):]
        for prefix, group in tracker_prefix_groups.items():
            if not key.startswith(prefix):
                continue
            target_device_id = group_device_ids.get(group)
            if target_device_id and device.via_device_id != target_device_id:
                dev_reg.async_update_device(device.id, via_device_id=target_device_id)
            break


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up LTA DataMall from a config entry."""
    account_key = entry.data[CONF_ACCOUNT_KEY]
    client = LTAApiClient(hass, account_key)

    try:
        global_coordinators = await async_build_global_coordinators(hass, client)
    except LTAAuthError as err:
        raise ConfigEntryAuthFailed(f"Invalid LTA DataMall AccountKey: {err}") from err
    except LTAApiError as err:
        raise ConfigEntryNotReady(f"Could not reach LTA DataMall: {err}") from err

    shared_coordinators: dict[str, object] = {}
    trackers: list[dict] = []

    for tracker in entry.options.get("trackers", []):
        ttype = tracker[CONF_TRACKER_TYPE]
        try:
            if ttype == TRACKER_BUS_STOP:
                coordinator = await async_create_bus_stop_coordinator(
                    hass, client, tracker[CONF_BUS_STOP_CODE]
                )
            elif ttype == TRACKER_EV_POSTAL:
                coordinator = await async_create_ev_postal_coordinator(
                    hass, client, tracker[CONF_POSTAL_CODE]
                )
            elif ttype == TRACKER_BICYCLE_PARKING:
                coordinator = await async_create_bicycle_parking_coordinator(
                    hass,
                    client,
                    tracker[CONF_LATITUDE],
                    tracker[CONF_LONGITUDE],
                    tracker[CONF_RADIUS_KM],
                )
            elif ttype == TRACKER_CROWD_LINE:
                coordinator = await async_create_crowd_line_coordinator(
                    hass, client, tracker[CONF_TRAIN_LINE]
                )
            elif ttype == TRACKER_CARPARK:
                coordinator = await async_get_or_create_shared_coordinator(
                    hass, client, shared_coordinators, EP_CARPARK_AVAILABILITY
                )
            elif ttype == TRACKER_CAMERA:
                coordinator = await async_get_or_create_shared_coordinator(
                    hass, client, shared_coordinators, EP_TRAFFIC_IMAGES
                )
            else:
                _LOGGER.warning("Unknown tracker type %s, skipping", ttype)
                continue
        except LTAApiError as err:
            raise ConfigEntryNotReady(f"Could not set up tracker {tracker}: {err}") from err

        trackers.append({"config": tracker, "coordinator": coordinator})

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "client": client,
        "global": global_coordinators,
        "shared": shared_coordinators,
        "trackers": trackers,
    }

    # Register the hub + themed group devices and re-home any global entities
    # left on the old single-device layout by an upgrade.
    _register_devices_and_migrate(hass, entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_update_listener))

    async_register_services(hass)

    return True


async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry whenever its trackers (options) change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not hass.data[DOMAIN]:
            async_unregister_services(hass)
    return unload_ok
