"""On-demand actions (services) for reference/bulk LTA DataMall datasets.

These datasets (bus master data, passenger volume, geospatial layers, ...)
update ad hoc, monthly, or quarterly, and some return a pre-signed file
download link rather than records. Polling them as sensors would create a
lot of near-static entities for little benefit, so they're exposed as
call-on-demand actions instead (see the architecture plan agreed with the
user). Response data is returned via ``supports_response=ONLY`` so they can
be used directly in templates/automations.
"""
from __future__ import annotations

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .api import LTAApiClient, LTAApiError
from .const import DOMAIN

SERVICE_GET_BUS_SERVICES = "get_bus_services"
SERVICE_GET_BUS_ROUTES = "get_bus_routes"
SERVICE_GET_BUS_STOPS = "get_bus_stops"
SERVICE_GET_TAXI_STANDS = "get_taxi_stands"
SERVICE_GET_PLANNED_BUS_ROUTES = "get_planned_bus_routes"
SERVICE_GET_TRAFFIC_FLOW = "get_traffic_flow"
SERVICE_GET_GEOSPATIAL_LAYER = "get_geospatial_layer"
SERVICE_GET_EV_CHARGING_POINTS_BATCH = "get_ev_charging_points_batch"
SERVICE_GET_CARPARK_AVAILABILITY = "get_carpark_availability"
SERVICE_GET_TRAFFIC_CAMERAS = "get_traffic_cameras"
SERVICE_GET_PASSENGER_VOLUME_BUS = "get_passenger_volume_bus"
SERVICE_GET_PASSENGER_VOLUME_OD_BUS = "get_passenger_volume_od_bus"
SERVICE_GET_PASSENGER_VOLUME_OD_TRAIN = "get_passenger_volume_od_train"
SERVICE_GET_PASSENGER_VOLUME_TRAIN = "get_passenger_volume_train"

_ALL_SERVICES = [
    SERVICE_GET_BUS_SERVICES,
    SERVICE_GET_BUS_ROUTES,
    SERVICE_GET_BUS_STOPS,
    SERVICE_GET_TAXI_STANDS,
    SERVICE_GET_PLANNED_BUS_ROUTES,
    SERVICE_GET_TRAFFIC_FLOW,
    SERVICE_GET_GEOSPATIAL_LAYER,
    SERVICE_GET_EV_CHARGING_POINTS_BATCH,
    SERVICE_GET_CARPARK_AVAILABILITY,
    SERVICE_GET_TRAFFIC_CAMERAS,
    SERVICE_GET_PASSENGER_VOLUME_BUS,
    SERVICE_GET_PASSENGER_VOLUME_OD_BUS,
    SERVICE_GET_PASSENGER_VOLUME_OD_TRAIN,
    SERVICE_GET_PASSENGER_VOLUME_TRAIN,
]


def _get_client(hass: HomeAssistant) -> LTAApiClient:
    entries = hass.data.get(DOMAIN, {})
    if not entries:
        raise HomeAssistantError("No LTA DataMall config entry is set up")
    # Single-account integration: any configured entry's client works.
    return next(iter(entries.values()))["client"]


def async_register_services(hass: HomeAssistant) -> None:
    """Register the reference-data actions once (idempotent)."""
    if hass.services.has_service(DOMAIN, SERVICE_GET_BUS_SERVICES):
        return

    async def _wrap(coro_name: str, call: ServiceCall, params: dict | None = None) -> ServiceResponse:
        client = _get_client(hass)
        try:
            result = await getattr(client, coro_name)(**(params or {}))
        except LTAApiError as err:
            raise HomeAssistantError(str(err)) from err
        return {"result": result}

    async def get_bus_services(call: ServiceCall) -> ServiceResponse:
        return await _wrap("async_get_bus_services", call, {"service_no": call.data.get("service_no")})

    async def get_bus_routes(call: ServiceCall) -> ServiceResponse:
        return await _wrap("async_get_bus_routes", call)

    async def get_bus_stops(call: ServiceCall) -> ServiceResponse:
        return await _wrap("async_get_bus_stops", call, {"bus_stop_code": call.data.get("bus_stop_code")})

    async def get_taxi_stands(call: ServiceCall) -> ServiceResponse:
        return await _wrap("async_get_taxi_stands", call)

    async def get_planned_bus_routes(call: ServiceCall) -> ServiceResponse:
        return await _wrap("async_get_planned_bus_routes", call)

    async def get_traffic_flow(call: ServiceCall) -> ServiceResponse:
        return await _wrap("async_get_traffic_flow", call)

    async def get_geospatial_layer(call: ServiceCall) -> ServiceResponse:
        return await _wrap("async_get_geospatial_whole_island", call, {"layer_id": call.data["layer_id"]})

    async def get_ev_charging_points_batch(call: ServiceCall) -> ServiceResponse:
        return await _wrap("async_get_ev_charging_points_batch", call)

    # Carpark Availability and Traffic Images are already polled by the shared
    # tracker-backed coordinators, but neither their CarParkID nor CameraID is
    # discoverable in the options flow. These on-demand actions reuse the same
    # client methods so a user can list every ID before adding a tracker.
    async def get_carpark_availability(call: ServiceCall) -> ServiceResponse:
        return await _wrap("async_get_carpark_availability", call)

    async def get_traffic_cameras(call: ServiceCall) -> ServiceResponse:
        return await _wrap("async_get_traffic_images", call)

    async def get_passenger_volume_bus(call: ServiceCall) -> ServiceResponse:
        return await _wrap("async_get_passenger_volume_bus", call, {"date": call.data.get("date")})

    async def get_passenger_volume_od_bus(call: ServiceCall) -> ServiceResponse:
        return await _wrap("async_get_passenger_volume_od_bus", call, {"date": call.data.get("date")})

    async def get_passenger_volume_od_train(call: ServiceCall) -> ServiceResponse:
        return await _wrap("async_get_passenger_volume_od_train", call, {"date": call.data.get("date")})

    async def get_passenger_volume_train(call: ServiceCall) -> ServiceResponse:
        return await _wrap("async_get_passenger_volume_train", call, {"date": call.data.get("date")})

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_BUS_SERVICES,
        get_bus_services,
        schema=vol.Schema({vol.Optional("service_no"): cv.string}),
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_GET_BUS_ROUTES, get_bus_routes, supports_response=SupportsResponse.ONLY
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_BUS_STOPS,
        get_bus_stops,
        schema=vol.Schema({vol.Optional("bus_stop_code"): cv.string}),
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_GET_TAXI_STANDS, get_taxi_stands, supports_response=SupportsResponse.ONLY
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_PLANNED_BUS_ROUTES,
        get_planned_bus_routes,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_GET_TRAFFIC_FLOW, get_traffic_flow, supports_response=SupportsResponse.ONLY
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_GEOSPATIAL_LAYER,
        get_geospatial_layer,
        schema=vol.Schema({vol.Required("layer_id"): cv.string}),
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_EV_CHARGING_POINTS_BATCH,
        get_ev_charging_points_batch,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_CARPARK_AVAILABILITY,
        get_carpark_availability,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_TRAFFIC_CAMERAS,
        get_traffic_cameras,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_PASSENGER_VOLUME_BUS,
        get_passenger_volume_bus,
        schema=vol.Schema({vol.Optional("date"): cv.string}),
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_PASSENGER_VOLUME_OD_BUS,
        get_passenger_volume_od_bus,
        schema=vol.Schema({vol.Optional("date"): cv.string}),
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_PASSENGER_VOLUME_OD_TRAIN,
        get_passenger_volume_od_train,
        schema=vol.Schema({vol.Optional("date"): cv.string}),
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_PASSENGER_VOLUME_TRAIN,
        get_passenger_volume_train,
        schema=vol.Schema({vol.Optional("date"): cv.string}),
        supports_response=SupportsResponse.ONLY,
    )


def async_unregister_services(hass: HomeAssistant) -> None:
    """Remove all registered actions once the last config entry is unloaded."""
    for service in _ALL_SERVICES:
        hass.services.async_remove(DOMAIN, service)
