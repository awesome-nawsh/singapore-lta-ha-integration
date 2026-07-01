"""Sensor platform for LTA DataMall.

Three families of sensor are created:

* Global - one sensor per always-on Singapore-wide dataset (traffic
  incidents, road works, ...), attached to the shared hub device.
* Static trackers - one sensor per user-added carpark/EV-postal-code/
  bicycle-parking tracker, attached to that tracker's own device.
* Dynamic trackers - Bus Arrival and Station Crowd Density return a
  variable, data-driven set of items (the services currently serving a
  stop; the stations on a line), so their sensors are created/added the
  first time each item is seen in the coordinator data, matching the
  pattern HA core uses for e.g. weather forecast sub-entities.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_BUS_STOP_CODE,
    CONF_CARPARK_ID,
    CONF_NAME,
    CONF_POSTAL_CODE,
    CONF_TRACKER_TYPE,
    CONF_TRAIN_LINE,
    DOMAIN,
    EP_EST_TRAVEL_TIMES,
    EP_FACILITIES_MAINTENANCE,
    EP_FAULTY_TRAFFIC_LIGHTS,
    EP_ROAD_OPENINGS,
    EP_ROAD_WORKS,
    EP_TAXI_AVAILABILITY,
    EP_TRAFFIC_INCIDENTS,
    EP_TRAFFIC_SPEED_BANDS,
    EP_VMS,
    MAX_ATTR_LIST_ITEMS,
    TRACKER_BICYCLE_PARKING,
    TRACKER_BUS_STOP,
    TRACKER_CARPARK,
    TRACKER_CROWD_LINE,
    TRACKER_EV_POSTAL,
)
from .coordinator import LTACoordinator
from .entity import LTABaseEntity, hub_device_info, tracker_device_info

# Speed band -> approximate midpoint km/h, per API User Guide 2.19 (8 bands,
# 10 km/h wide, v4 TrafficSpeedBands).
_SPEED_BAND_MIDPOINT = {1: 5, 2: 15, 3: 25, 4: 35, 5: 45, 6: 55, 7: 65, 8: 75}


def _cap(items: list) -> list:
    return items[:MAX_ATTR_LIST_ITEMS]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up LTA DataMall sensors for a config entry."""
    runtime = hass.data[DOMAIN][entry.entry_id]
    global_coordinators: dict[str, LTACoordinator] = runtime["global"]
    trackers: list[dict[str, Any]] = runtime["trackers"]

    entities: list[SensorEntity] = []
    # Plain (non-Entity) helper objects that watch a coordinator and add new
    # sensors as new bus services / stations show up in its data. Kept alive
    # here (not garbage collected) for the lifetime of the config entry.
    managers: list[Any] = runtime.setdefault("_sensor_managers", [])
    device = hub_device_info(entry)

    entities.append(
        LTAGlobalCountSensor(
            global_coordinators[EP_TRAFFIC_INCIDENTS],
            entry,
            device,
            "traffic_incidents",
            "Traffic Incidents",
            attrs_fn=lambda data: {"incidents": _cap(data)},
        )
    )
    entities.append(
        LTAGlobalCountSensor(
            global_coordinators[EP_FAULTY_TRAFFIC_LIGHTS],
            entry,
            device,
            "faulty_traffic_lights",
            "Faulty Traffic Lights",
            attrs_fn=lambda data: {"faults": _cap(data)},
        )
    )
    entities.append(
        LTAGlobalCountSensor(
            global_coordinators[EP_ROAD_OPENINGS],
            entry,
            device,
            "planned_road_openings",
            "Planned Road Openings",
            attrs_fn=lambda data: {"road_openings": _cap(data)},
        )
    )
    entities.append(
        LTAGlobalCountSensor(
            global_coordinators[EP_ROAD_WORKS],
            entry,
            device,
            "approved_road_works",
            "Approved Road Works",
            attrs_fn=lambda data: {"road_works": _cap(data)},
        )
    )
    entities.append(
        LTAGlobalCountSensor(
            global_coordinators[EP_VMS],
            entry,
            device,
            "vms_messages",
            "VMS Messages",
            attrs_fn=lambda data: {"messages": _cap(data)},
        )
    )
    entities.append(
        LTAGlobalCountSensor(
            global_coordinators[EP_TAXI_AVAILABILITY],
            entry,
            device,
            "taxis_available",
            "Taxis Available",
            unit="taxis",
        )
    )
    entities.append(
        LTAGlobalCountSensor(
            global_coordinators[EP_FACILITIES_MAINTENANCE],
            entry,
            device,
            "lift_maintenance",
            "MRT Lifts Under Maintenance",
            unit="lifts",
            attrs_fn=lambda data: {"lifts": _cap(data)},
        )
    )
    entities.append(EstimatedTravelTimesSensor(global_coordinators[EP_EST_TRAVEL_TIMES], entry, device))
    entities.append(TrafficSpeedBandSensor(global_coordinators[EP_TRAFFIC_SPEED_BANDS], entry, device))

    for tracker in trackers:
        ttype = tracker["config"][CONF_TRACKER_TYPE]
        coordinator: LTACoordinator = tracker["coordinator"]
        config = tracker["config"]

        if ttype == TRACKER_BUS_STOP:
            managers.append(BusArrivalManager(coordinator, entry, config, async_add_entities))
        elif ttype == TRACKER_CARPARK:
            entities.append(CarparkSensor(coordinator, entry, config))
        elif ttype == TRACKER_EV_POSTAL:
            entities.append(EvChargingSensor(coordinator, entry, config))
        elif ttype == TRACKER_BICYCLE_PARKING:
            entities.append(BicycleParkingSensor(coordinator, entry, config))
        elif ttype == TRACKER_CROWD_LINE:
            managers.append(CrowdLineManager(coordinator, entry, config, async_add_entities))

    async_add_entities(entities)


class LTAGlobalCountSensor(LTABaseEntity, SensorEntity):
    """Generic 'count of records in a global dataset' sensor."""

    def __init__(
        self,
        coordinator: LTACoordinator,
        entry: ConfigEntry,
        device,
        key: str,
        name: str,
        unit: str | None = "incidents",
        attrs_fn: Callable[[list], dict] | None = None,
    ) -> None:
        super().__init__(coordinator, f"{entry.entry_id}_{key}", device)
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attrs_fn = attrs_fn

    @property
    def native_value(self) -> int:
        data = self.coordinator.data or []
        return len(data)

    @property
    def extra_state_attributes(self) -> dict | None:
        if self._attrs_fn is None:
            return None
        return self._attrs_fn(self.coordinator.data or [])


class EstimatedTravelTimesSensor(LTABaseEntity, SensorEntity):
    """Number of expressway segments currently reported, grouped as an attribute."""

    _attr_name = "Estimated Travel Times"
    _attr_native_unit_of_measurement = "segments"

    def __init__(self, coordinator: LTACoordinator, entry: ConfigEntry, device) -> None:
        super().__init__(coordinator, f"{entry.entry_id}_est_travel_times", device)

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data or [])

    @property
    def extra_state_attributes(self) -> dict:
        by_expressway: dict[str, list[dict]] = {}
        for row in _cap(self.coordinator.data or []):
            by_expressway.setdefault(row.get("Name", "?"), []).append(
                {
                    "direction": row.get("Direction"),
                    "start_point": row.get("StartPoint"),
                    "end_point": row.get("EndPoint"),
                    "est_time_min": row.get("EstTime"),
                }
            )
        return {"expressways": by_expressway}


class TrafficSpeedBandSensor(LTABaseEntity, SensorEntity):
    """Island-wide average traffic speed, derived from all reported speed bands."""

    _attr_name = "Traffic Speed (Island-wide Average)"
    _attr_native_unit_of_measurement = "km/h"

    def __init__(self, coordinator: LTACoordinator, entry: ConfigEntry, device) -> None:
        super().__init__(coordinator, f"{entry.entry_id}_traffic_speed_bands", device)

    @property
    def native_value(self) -> float | None:
        data = self.coordinator.data or []
        speeds = []
        for row in data:
            # Prefer the actual reported Minimum/MaximumSpeed for this link;
            # only fall back to the SpeedBand midpoint table if those are
            # missing (both are documented attributes of v4 TrafficSpeedBands).
            min_speed, max_speed = row.get("MinimumSpeed"), row.get("MaximumSpeed")
            try:
                if min_speed not in (None, "") and max_speed not in (None, ""):
                    speeds.append((float(min_speed) + float(max_speed)) / 2)
                    continue
            except (TypeError, ValueError):
                pass
            band = row.get("SpeedBand")
            if str(band).isdigit() and int(band) in _SPEED_BAND_MIDPOINT:
                speeds.append(_SPEED_BAND_MIDPOINT[int(band)])
        if not speeds:
            return None
        return round(sum(speeds) / len(speeds), 1)

    @property
    def extra_state_attributes(self) -> dict:
        return {"road_segments_reporting": len(self.coordinator.data or [])}


class CarparkSensor(LTABaseEntity, SensorEntity):
    """Available lots for one tracked CarParkID, filtered out of the shared dataset."""

    _attr_native_unit_of_measurement = "lots"

    def __init__(self, coordinator: LTACoordinator, entry: ConfigEntry, config: dict) -> None:
        carpark_id = config[CONF_CARPARK_ID]
        device = tracker_device_info(entry, f"carpark_{carpark_id}", f"Carpark {carpark_id}")
        super().__init__(coordinator, f"{entry.entry_id}_carpark_{carpark_id}", device)
        self._carpark_id = carpark_id
        self._attr_name = "Available Lots"

    def _rows(self) -> list[dict]:
        return [row for row in (self.coordinator.data or []) if row.get("CarParkID") == self._carpark_id]

    @property
    def native_value(self) -> int | None:
        rows = self._rows()
        if not rows:
            return None
        return sum(int(row.get("AvailableLots", 0)) for row in rows)

    @property
    def extra_state_attributes(self) -> dict:
        rows = self._rows()
        if not rows:
            return {}
        first = rows[0]
        return {
            "development": first.get("Development"),
            "area": first.get("Area"),
            "agency": first.get("Agency"),
            "by_lot_type": {row.get("LotType"): row.get("AvailableLots") for row in rows},
        }


class EvChargingSensor(LTABaseEntity, SensorEntity):
    """Available EV connectors at charging stations found for one postal code."""

    _attr_native_unit_of_measurement = "connectors"

    def __init__(self, coordinator: LTACoordinator, entry: ConfigEntry, config: dict) -> None:
        postal = config[CONF_POSTAL_CODE]
        device = tracker_device_info(entry, f"ev_{postal}", f"EV Charging - {postal}")
        super().__init__(coordinator, f"{entry.entry_id}_ev_{postal}", device)
        self._attr_name = "Available Connectors"

    @property
    def _stations(self) -> list[dict]:
        return self.coordinator.data or []

    @property
    def native_value(self) -> int:
        total = 0
        for station in self._stations:
            for point in station.get("chargingPoints", []):
                for ev in point.get("evIds", []):
                    if str(ev.get("status")) == "1":
                        total += 1
        return total

    @property
    def extra_state_attributes(self) -> dict:
        stations = []
        for station in self._stations:
            stations.append(
                {
                    "name": station.get("name"),
                    "address": station.get("address"),
                    "operator": next(
                        (p.get("operator") for p in station.get("chargingPoints", [])), None
                    ),
                    "status": station.get("status"),
                    "charging_points": len(station.get("chargingPoints", [])),
                }
            )
        return {"stations": _cap(stations)}


class BicycleParkingSensor(LTABaseEntity, SensorEntity):
    """Bicycle parking racks found within radius of a tracked point."""

    _attr_native_unit_of_measurement = "racks"

    def __init__(self, coordinator: LTACoordinator, entry: ConfigEntry, config: dict) -> None:
        name = config[CONF_NAME]
        device = tracker_device_info(entry, f"bicycle_{name}", f"Bicycle Parking - {name}")
        super().__init__(coordinator, f"{entry.entry_id}_bicycle_{name}", device)
        self._attr_name = "Racks Found"

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data or [])

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "locations": _cap(
                [
                    {
                        "description": row.get("Description"),
                        "rack_type": row.get("RackType"),
                        "rack_count": row.get("RackCount"),
                        "sheltered": row.get("ShelterIndicator"),
                        "latitude": row.get("Latitude"),
                        "longitude": row.get("Longitude"),
                    }
                    for row in (self.coordinator.data or [])
                ]
            )
        }


class BusArrivalManager:
    """Plain (non-entity) helper: listens for new bus services at a tracked
    stop and creates a BusArrivalSensor the first time each one is seen.
    Never passed to async_add_entities itself - only the sensors it creates
    are entities.
    """

    def __init__(
        self,
        coordinator: LTACoordinator,
        entry: ConfigEntry,
        config: dict,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        self.coordinator = coordinator
        self._entry = entry
        self._config = config
        self._async_add_entities = async_add_entities
        self._known_services: set[str] = set()
        self._device = tracker_device_info(
            entry, f"bus_stop_{config[CONF_BUS_STOP_CODE]}", f"Bus Stop {config[CONF_BUS_STOP_CODE]}"
        )
        coordinator.async_add_listener(self._handle_update)
        self._handle_update()

    @callback
    def _handle_update(self) -> None:
        data = self.coordinator.data or {}
        new_entities = []
        for service in data.get("Services", []):
            service_no = service.get("ServiceNo")
            if not service_no or service_no in self._known_services:
                continue
            self._known_services.add(service_no)
            new_entities.append(
                BusArrivalSensor(self.coordinator, self._entry, self._config, self._device, service_no)
            )
        if new_entities:
            self._async_add_entities(new_entities)


class BusArrivalSensor(LTABaseEntity, SensorEntity):
    """Minutes until the next bus for one service at one stop."""

    _attr_native_unit_of_measurement = "min"

    def __init__(
        self,
        coordinator: LTACoordinator,
        entry: ConfigEntry,
        config: dict,
        device,
        service_no: str,
    ) -> None:
        stop_code = config[CONF_BUS_STOP_CODE]
        super().__init__(
            coordinator, f"{entry.entry_id}_bus_{stop_code}_{service_no}", device
        )
        self._service_no = service_no
        self._attr_name = f"Service {service_no}"

    def _next_bus(self) -> dict | None:
        data = self.coordinator.data or {}
        for service in data.get("Services", []):
            if service.get("ServiceNo") == self._service_no:
                return service.get("NextBus")
        return None

    @property
    def available(self) -> bool:
        return super().available and self._next_bus() is not None

    @property
    def native_value(self) -> int | None:
        next_bus = self._next_bus()
        if not next_bus or not next_bus.get("EstimatedArrival"):
            return None
        try:
            eta = datetime.fromisoformat(next_bus["EstimatedArrival"])
        except ValueError:
            return None
        now = eta.tzinfo and datetime.now(eta.tzinfo) or datetime.now()
        return max(0, round((eta - now).total_seconds() / 60))

    @property
    def extra_state_attributes(self) -> dict:
        next_bus = self._next_bus() or {}
        data = self.coordinator.data or {}
        service = next(
            (s for s in data.get("Services", []) if s.get("ServiceNo") == self._service_no), {}
        )
        return {
            "operator": service.get("Operator"),
            "load": next_bus.get("Load"),
            "bus_type": next_bus.get("Type"),
            "wheelchair_accessible": next_bus.get("Feature"),
            "monitored": next_bus.get("Monitored"),
            "latitude": next_bus.get("Latitude"),
            "longitude": next_bus.get("Longitude"),
            "next_bus_2_eta": (service.get("NextBus2") or {}).get("EstimatedArrival"),
            "next_bus_3_eta": (service.get("NextBus3") or {}).get("EstimatedArrival"),
        }


class CrowdLineManager:
    """Plain (non-entity) helper: creates a StationCrowdSensor the first time
    each station on a tracked line is seen in the coordinator data.
    """

    def __init__(
        self,
        coordinator: LTACoordinator,
        entry: ConfigEntry,
        config: dict,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        self.coordinator = coordinator
        self._entry = entry
        self._config = config
        self._async_add_entities = async_add_entities
        self._known_stations: set[str] = set()
        line = config[CONF_TRAIN_LINE]
        self._device = tracker_device_info(entry, f"crowd_{line}", f"Station Crowd Density - {line} Line")
        coordinator.async_add_listener(self._handle_update)
        self._handle_update()

    @callback
    def _handle_update(self) -> None:
        data = self.coordinator.data or {}
        new_entities = []
        for station in data:
            if station in self._known_stations:
                continue
            self._known_stations.add(station)
            new_entities.append(
                StationCrowdSensor(self.coordinator, self._entry, self._config, self._device, station)
            )
        if new_entities:
            self._async_add_entities(new_entities)


class StationCrowdSensor(LTABaseEntity, SensorEntity):
    """Current crowd level (low/moderate/high) for one MRT/LRT station."""

    _attr_device_class = None

    def __init__(
        self,
        coordinator: LTACoordinator,
        entry: ConfigEntry,
        config: dict,
        device,
        station: str,
    ) -> None:
        line = config[CONF_TRAIN_LINE]
        super().__init__(coordinator, f"{entry.entry_id}_crowd_{line}_{station}", device)
        self._station = station
        self._attr_name = f"Station {station} Crowd Level"

    @property
    def native_value(self) -> str | None:
        return (self.coordinator.data or {}).get(self._station, {}).get("realtime")

    @property
    def extra_state_attributes(self) -> dict:
        info = (self.coordinator.data or {}).get(self._station, {})
        return {"forecast": info.get("forecast", [])}
