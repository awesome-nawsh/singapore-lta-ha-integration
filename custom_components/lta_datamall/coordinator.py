"""Data update coordinators for the LTA DataMall integration.

Three kinds of coordinator are used, all built on the same generic wrapper:

* Global - one per Singapore-wide dataset that backs an always-created
  entity (Traffic Incidents, Train Service Alerts, Flood Alerts, ...).
  Created once at setup and always polling.
* Shared/lazy - one per Singapore-wide dataset that has no per-item filter
  but backs *tracker* entities that each pick one item out of the list
  (Carpark Availability, Traffic Images). Created on demand the first time a
  matching tracker is configured, and shared by every tracker of that type
  so the full dataset is only fetched once, not once per tracker.
* Per-tracker - one per user-added tracker whose underlying API takes a
  location/line filter param (Bus Arrival, EV Charging Points, Bicycle
  Parking, Station Crowd Density), so each tracker's coordinator only ever
  fetches the data relevant to that tracker.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Awaitable, Callable

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import LTAApiClient, LTAApiError, LTAAuthError
from .const import (
    CROWD_LEVEL_MAP,
    DOMAIN,
    EP_CARPARK_AVAILABILITY,
    EP_EST_TRAVEL_TIMES,
    EP_FACILITIES_MAINTENANCE,
    EP_FAULTY_TRAFFIC_LIGHTS,
    EP_FLOOD_ALERTS,
    EP_ROAD_OPENINGS,
    EP_ROAD_WORKS,
    EP_TAXI_AVAILABILITY,
    EP_TRAFFIC_IMAGES,
    EP_TRAFFIC_INCIDENTS,
    EP_TRAFFIC_SPEED_BANDS,
    EP_TRAIN_SERVICE_ALERTS,
    EP_VMS,
    GLOBAL_UPDATE_INTERVALS,
    SHARED_TRACKER_BACKED_INTERVALS,
    TRACKER_UPDATE_INTERVALS,
)

_LOGGER = logging.getLogger(__name__)


class LTACoordinator(DataUpdateCoordinator[Any]):
    """Generic coordinator wrapping a single LTA DataMall fetch call."""

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        update_interval_seconds: int,
        fetch: Callable[[], Awaitable[Any]],
    ) -> None:
        self._fetch = fetch
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {name}",
            update_interval=timedelta(seconds=update_interval_seconds),
        )

    async def _async_update_data(self) -> Any:
        try:
            return await self._fetch()
        except LTAAuthError as err:
            raise UpdateFailed(f"LTA DataMall authentication failed: {err}") from err
        except LTAApiError as err:
            raise UpdateFailed(f"Error fetching from LTA DataMall: {err}") from err


def _global_fetchers(client: LTAApiClient) -> dict[str, Callable[[], Awaitable[Any]]]:
    """Map each always-on global endpoint to its client fetch coroutine."""
    return {
        EP_TRAIN_SERVICE_ALERTS: client.async_get_train_service_alerts,
        EP_TRAFFIC_INCIDENTS: client.async_get_traffic_incidents,
        EP_FAULTY_TRAFFIC_LIGHTS: client.async_get_faulty_traffic_lights,
        EP_VMS: client.async_get_vms,
        EP_FLOOD_ALERTS: client.async_get_flood_alerts,
        EP_ROAD_OPENINGS: client.async_get_road_openings,
        EP_ROAD_WORKS: client.async_get_road_works,
        EP_EST_TRAVEL_TIMES: client.async_get_est_travel_times,
        EP_TRAFFIC_SPEED_BANDS: client.async_get_traffic_speed_bands,
        EP_TAXI_AVAILABILITY: client.async_get_taxi_availability,
        EP_FACILITIES_MAINTENANCE: client.async_get_facilities_maintenance,
    }


def _shared_fetchers(client: LTAApiClient) -> dict[str, Callable[[], Awaitable[Any]]]:
    """Map each shared/lazy endpoint (backs trackers, no filter param) to its fetch."""
    return {
        EP_CARPARK_AVAILABILITY: client.async_get_carpark_availability,
        EP_TRAFFIC_IMAGES: client.async_get_traffic_images,
    }


async def async_build_global_coordinators(
    hass: HomeAssistant, client: LTAApiClient
) -> dict[str, LTACoordinator]:
    """Create and do the first refresh for every always-on global coordinator."""
    fetchers = _global_fetchers(client)
    coordinators: dict[str, LTACoordinator] = {}
    for endpoint, fetch in fetchers.items():
        interval = GLOBAL_UPDATE_INTERVALS[endpoint]
        coordinator = LTACoordinator(hass, endpoint, interval, fetch)
        await coordinator.async_config_entry_first_refresh()
        coordinators[endpoint] = coordinator
    return coordinators


async def async_get_or_create_shared_coordinator(
    hass: HomeAssistant,
    client: LTAApiClient,
    shared_coordinators: dict[str, LTACoordinator],
    endpoint: str,
) -> LTACoordinator:
    """Return the shared coordinator for ``endpoint``, creating it on first use."""
    if endpoint not in shared_coordinators:
        fetch = _shared_fetchers(client)[endpoint]
        interval = SHARED_TRACKER_BACKED_INTERVALS[endpoint]
        coordinator = LTACoordinator(hass, endpoint, interval, fetch)
        await coordinator.async_config_entry_first_refresh()
        shared_coordinators[endpoint] = coordinator
    return shared_coordinators[endpoint]


async def async_create_bus_stop_coordinator(
    hass: HomeAssistant, client: LTAApiClient, bus_stop_code: str
) -> LTACoordinator:
    """Per-tracker coordinator: bus arrivals for a single stop (all services)."""

    async def fetch() -> dict:
        return await client.async_get_bus_arrival(bus_stop_code)

    coordinator = LTACoordinator(
        hass, f"bus_stop_{bus_stop_code}", TRACKER_UPDATE_INTERVALS["bus_stop"], fetch
    )
    await coordinator.async_config_entry_first_refresh()
    return coordinator


async def async_create_ev_postal_coordinator(
    hass: HomeAssistant, client: LTAApiClient, postal_code: str
) -> LTACoordinator:
    """Per-tracker coordinator: EV charging points for a single postal code."""

    async def fetch() -> list[dict]:
        return await client.async_get_ev_charging_points(postal_code)

    coordinator = LTACoordinator(
        hass, f"ev_postal_{postal_code}", TRACKER_UPDATE_INTERVALS["ev_postal"], fetch
    )
    await coordinator.async_config_entry_first_refresh()
    return coordinator


async def async_create_bicycle_parking_coordinator(
    hass: HomeAssistant, client: LTAApiClient, lat: float, lon: float, radius_km: float
) -> LTACoordinator:
    """Per-tracker coordinator: bicycle parking lots near a point."""

    async def fetch() -> list[dict]:
        return await client.async_get_bicycle_parking(lat, lon, radius_km)

    coordinator = LTACoordinator(
        hass,
        f"bicycle_parking_{lat}_{lon}",
        TRACKER_UPDATE_INTERVALS["bicycle_parking"],
        fetch,
    )
    await coordinator.async_config_entry_first_refresh()
    return coordinator


async def async_create_crowd_line_coordinator(
    hass: HomeAssistant, client: LTAApiClient, train_line: str
) -> LTACoordinator:
    """Per-tracker coordinator: real-time + forecast station crowd density for a line."""

    async def fetch() -> dict:
        realtime = await client.async_get_station_crowd_realtime(train_line)
        forecast = await client.async_get_station_crowd_forecast(train_line)
        by_station: dict[str, dict] = {}
        for row in realtime:
            station = row.get("Station")
            if not station:
                continue
            by_station.setdefault(station, {})["realtime"] = row.get("CrowdLevel")
        for row in forecast:
            station = row.get("Station")
            if not station:
                continue
            by_station.setdefault(station, {}).setdefault("forecast", []).append(
                {
                    "start": row.get("Start"),
                    "crowd_level": CROWD_LEVEL_MAP.get(row.get("CrowdLevel"), row.get("CrowdLevel")),
                }
            )
        return by_station

    coordinator = LTACoordinator(
        hass, f"crowd_line_{train_line}", TRACKER_UPDATE_INTERVALS["crowd_line"], fetch
    )
    await coordinator.async_config_entry_first_refresh()
    return coordinator
