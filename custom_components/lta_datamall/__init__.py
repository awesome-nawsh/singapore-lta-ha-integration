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
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .api import LTAApiClient, LTAApiError, LTAAuthError
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
    PLATFORMS,
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
