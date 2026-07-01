"""Thin async client for the Singapore LTA DataMall APIs.

Every call requires only an ``AccountKey`` header (per API User Guide v6.8,
change 3.4). Endpoints that return the OData ``value`` list are transparently
paginated using the ``$skip`` operator, since LTA caps most endpoints at 500
records per call (Bus Arrival and the single-record endpoints are the
exception and are fetched with a single request).
"""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    BASE_URL,
    EP_BICYCLE_PARKING,
    EP_BUS_ARRIVAL,
    EP_BUS_ROUTES,
    EP_BUS_SERVICES,
    EP_BUS_STOPS,
    EP_CARPARK_AVAILABILITY,
    EP_EST_TRAVEL_TIMES,
    EP_EV_CHARGING_POINTS,
    EP_EV_CHARGING_POINTS_BATCH,
    EP_FACILITIES_MAINTENANCE,
    EP_FAULTY_TRAFFIC_LIGHTS,
    EP_FLOOD_ALERTS,
    EP_GEOSPATIAL_WHOLE_ISLAND,
    EP_PLANNED_BUS_ROUTES,
    EP_PV_BUS,
    EP_PV_ODBUS,
    EP_PV_ODTRAIN,
    EP_PV_TRAIN,
    EP_ROAD_OPENINGS,
    EP_ROAD_WORKS,
    EP_STATION_CROWD_FORECAST,
    EP_STATION_CROWD_REALTIME,
    EP_TAXI_AVAILABILITY,
    EP_TAXI_STANDS,
    EP_TRAFFIC_FLOW,
    EP_TRAFFIC_IMAGES,
    EP_TRAFFIC_INCIDENTS,
    EP_TRAFFIC_SPEED_BANDS,
    EP_TRAIN_SERVICE_ALERTS,
    EP_VMS,
)

_LOGGER = logging.getLogger(__name__)

MAX_PAGES = 40  # hard safety cap: 40 * 500 = 20,000 records per dataset


class LTAApiError(Exception):
    """Raised for any non-auth error talking to LTA DataMall."""


class LTAAuthError(LTAApiError):
    """Raised when the AccountKey is rejected (HTTP 401/403)."""


class LTAApiClient:
    """Minimal async wrapper around the LTA DataMall REST API."""

    def __init__(self, hass: HomeAssistant, account_key: str) -> None:
        self._session: aiohttp.ClientSession = async_get_clientsession(hass)
        self._headers = {
            "AccountKey": account_key,
            "accept": "application/json",
        }

    async def _request(self, path: str, params: dict[str, Any] | None = None) -> dict:
        url = f"{BASE_URL}/{path}"
        try:
            async with self._session.get(
                url, headers=self._headers, params=params, timeout=aiohttp.ClientTimeout(total=20)
            ) as resp:
                if resp.status in (401, 403):
                    raise LTAAuthError(f"AccountKey rejected ({resp.status}) for {path}")
                if resp.status != 200:
                    body = await resp.text()
                    raise LTAApiError(f"HTTP {resp.status} for {path}: {body[:200]}")
                return await resp.json(content_type=None)
        except aiohttp.ClientError as err:
            raise LTAApiError(f"Error connecting to LTA DataMall ({path}): {err}") from err

    async def _get_all(self, path: str, params: dict[str, Any] | None = None) -> list[dict]:
        """Fetch every page of an OData-style endpoint (500 records/page)."""
        results: list[dict] = []
        base_params = dict(params or {})
        for page in range(MAX_PAGES):
            page_params = dict(base_params)
            if page:
                page_params["$skip"] = page * 500
            data = await self._request(path, page_params)
            batch = data.get("value", []) if isinstance(data, dict) else []
            results.extend(batch)
            if len(batch) < 500:
                break
        return results

    # -- Auth check -----------------------------------------------------
    async def async_validate_key(self) -> None:
        """Make a cheap call to confirm the AccountKey works."""
        await self._request(EP_BUS_STOPS)

    # -- Public-Transport related ----------------------------------------
    async def async_get_bus_arrival(self, bus_stop_code: str, service_no: str | None = None) -> dict:
        params = {"BusStopCode": bus_stop_code}
        if service_no:
            params["ServiceNo"] = service_no
        return await self._request(EP_BUS_ARRIVAL, params)

    async def async_get_bus_services(self, service_no: str | None = None) -> list[dict]:
        params = {"ServiceNo": service_no} if service_no else None
        return await self._get_all(EP_BUS_SERVICES, params)

    async def async_get_bus_routes(self) -> list[dict]:
        return await self._get_all(EP_BUS_ROUTES)

    async def async_get_bus_stops(self, bus_stop_code: str | None = None) -> list[dict]:
        params = {"BusStopCode": bus_stop_code} if bus_stop_code else None
        return await self._get_all(EP_BUS_STOPS, params)

    async def async_get_passenger_volume_bus(self, date: str | None = None) -> dict:
        return await self._request(EP_PV_BUS, {"Date": date} if date else None)

    async def async_get_passenger_volume_od_bus(self, date: str | None = None) -> dict:
        return await self._request(EP_PV_ODBUS, {"Date": date} if date else None)

    async def async_get_passenger_volume_od_train(self, date: str | None = None) -> dict:
        return await self._request(EP_PV_ODTRAIN, {"Date": date} if date else None)

    async def async_get_passenger_volume_train(self, date: str | None = None) -> dict:
        return await self._request(EP_PV_TRAIN, {"Date": date} if date else None)

    async def async_get_taxi_availability(self) -> list[dict]:
        return await self._get_all(EP_TAXI_AVAILABILITY)

    async def async_get_taxi_stands(self) -> list[dict]:
        return await self._get_all(EP_TAXI_STANDS)

    async def async_get_train_service_alerts(self) -> dict:
        return await self._request(EP_TRAIN_SERVICE_ALERTS)

    async def async_get_facilities_maintenance(self) -> list[dict]:
        return await self._get_all(EP_FACILITIES_MAINTENANCE)

    async def async_get_station_crowd_realtime(self, train_line: str) -> list[dict]:
        return await self._get_all(EP_STATION_CROWD_REALTIME, {"TrainLine": train_line})

    async def async_get_station_crowd_forecast(self, train_line: str) -> list[dict]:
        return await self._get_all(EP_STATION_CROWD_FORECAST, {"TrainLine": train_line})

    async def async_get_planned_bus_routes(self) -> list[dict]:
        return await self._get_all(EP_PLANNED_BUS_ROUTES)

    # -- Traffic related --------------------------------------------------
    async def async_get_carpark_availability(self) -> list[dict]:
        return await self._get_all(EP_CARPARK_AVAILABILITY)

    async def async_get_est_travel_times(self) -> list[dict]:
        return await self._get_all(EP_EST_TRAVEL_TIMES)

    async def async_get_faulty_traffic_lights(self) -> list[dict]:
        return await self._get_all(EP_FAULTY_TRAFFIC_LIGHTS)

    async def async_get_road_openings(self) -> list[dict]:
        return await self._get_all(EP_ROAD_OPENINGS)

    async def async_get_road_works(self) -> list[dict]:
        return await self._get_all(EP_ROAD_WORKS)

    async def async_get_traffic_images(self) -> list[dict]:
        return await self._get_all(EP_TRAFFIC_IMAGES)

    async def async_get_traffic_incidents(self) -> list[dict]:
        return await self._get_all(EP_TRAFFIC_INCIDENTS)

    async def async_get_traffic_speed_bands(self) -> list[dict]:
        return await self._get_all(EP_TRAFFIC_SPEED_BANDS)

    async def async_get_vms(self) -> list[dict]:
        return await self._get_all(EP_VMS)

    async def async_get_traffic_flow(self) -> list[dict]:
        return await self._get_all(EP_TRAFFIC_FLOW)

    # -- Active mobility / geospatial / EV / flood ------------------------
    async def async_get_bicycle_parking(self, lat: float, lon: float, dist_km: float | None = None) -> list[dict]:
        params: dict[str, Any] = {"Lat": lat, "Long": lon}
        if dist_km is not None:
            params["Dist"] = dist_km
        return await self._get_all(EP_BICYCLE_PARKING, params)

    async def async_get_geospatial_whole_island(self, layer_id: str) -> dict:
        return await self._request(EP_GEOSPATIAL_WHOLE_ISLAND, {"ID": layer_id})

    async def async_get_ev_charging_points(self, postal_code: str) -> list[dict]:
        return await self._get_all(EP_EV_CHARGING_POINTS, {"PostalCode": postal_code})

    async def async_get_ev_charging_points_batch(self) -> list[dict]:
        return await self._get_all(EP_EV_CHARGING_POINTS_BATCH)

    async def async_get_flood_alerts(self) -> list[dict]:
        return await self._get_all(EP_FLOOD_ALERTS)
