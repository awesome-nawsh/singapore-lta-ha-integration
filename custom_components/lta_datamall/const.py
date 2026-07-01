"""Constants for the LTA DataMall integration."""
from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "lta_datamall"

BASE_URL = "https://datamall2.mytransport.sg/ltaodataservice"

CONF_ACCOUNT_KEY = "account_key"

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.CAMERA]

# ---------------------------------------------------------------------------
# API endpoint paths (relative to BASE_URL), per LTA DataMall API User Guide
# v6.8 (21 Apr 2026).
# ---------------------------------------------------------------------------
EP_BUS_ARRIVAL = "v3/BusArrival"
EP_BUS_SERVICES = "BusServices"
EP_BUS_ROUTES = "BusRoutes"
EP_BUS_STOPS = "BusStops"
EP_PV_BUS = "PV/Bus"
EP_PV_ODBUS = "PV/ODBus"
EP_PV_ODTRAIN = "PV/ODTrain"
EP_PV_TRAIN = "PV/Train"
EP_TAXI_AVAILABILITY = "Taxi-Availability"
EP_TAXI_STANDS = "TaxiStands"
EP_TRAIN_SERVICE_ALERTS = "TrainServiceAlerts"
EP_CARPARK_AVAILABILITY = "CarParkAvailabilityv2"
EP_EST_TRAVEL_TIMES = "EstTravelTimes"
EP_FAULTY_TRAFFIC_LIGHTS = "FaultyTrafficLights"
EP_ROAD_OPENINGS = "RoadOpenings"
EP_ROAD_WORKS = "RoadWorks"
EP_TRAFFIC_IMAGES = "Traffic-Imagesv2"
EP_TRAFFIC_INCIDENTS = "TrafficIncidents"
EP_TRAFFIC_SPEED_BANDS = "v4/TrafficSpeedBands"
EP_VMS = "VMS"
EP_BICYCLE_PARKING = "BicycleParkingv2"
EP_GEOSPATIAL_WHOLE_ISLAND = "GeospatialWholeIsland"
EP_FACILITIES_MAINTENANCE = "v2/FacilitiesMaintenance"
EP_STATION_CROWD_REALTIME = "PCDRealTime"
EP_STATION_CROWD_FORECAST = "PCDForecast"
EP_TRAFFIC_FLOW = "TrafficFlow"
EP_PLANNED_BUS_ROUTES = "PlannedBusRoutes"
EP_EV_CHARGING_POINTS = "EVChargingPoints"
EP_EV_CHARGING_POINTS_BATCH = "EVCBatch"
EP_FLOOD_ALERTS = "PubFloodAlerts"

# ---------------------------------------------------------------------------
# Global (Singapore-wide) datasets that are auto-created once the account key
# is validated - no per-item configuration required because the underlying
# API has no location filter. Keys map to an update interval in seconds,
# chosen from the "Update Freq" documented for each API.
# ---------------------------------------------------------------------------
GLOBAL_UPDATE_INTERVALS: dict[str, int] = {
    EP_TRAIN_SERVICE_ALERTS: 5 * 60,
    EP_TRAFFIC_INCIDENTS: 2 * 60,
    EP_FAULTY_TRAFFIC_LIGHTS: 2 * 60,
    EP_VMS: 2 * 60,
    EP_FLOOD_ALERTS: 3 * 60,
    EP_ROAD_OPENINGS: 24 * 60 * 60,
    EP_ROAD_WORKS: 24 * 60 * 60,
    EP_EST_TRAVEL_TIMES: 5 * 60,
    EP_TRAFFIC_SPEED_BANDS: 5 * 60,
    EP_TAXI_AVAILABILITY: 60,
    EP_FACILITIES_MAINTENANCE: 60 * 60,
}

# Update intervals for tracker (per-item) datasets that take a location/line
# filter param and therefore get their own dedicated coordinator instance,
# keyed by tracker type.
TRACKER_UPDATE_INTERVALS: dict[str, int] = {
    "bus_stop": 20,
    "ev_postal": 5 * 60,
    "bicycle_parking": 24 * 60 * 60,
    "crowd_line": 10 * 60,
}

# Endpoints with NO location filter param (they always return the full
# island-wide dataset) that back one or more *tracker* entities picking a
# specific item out of that list (e.g. one carpark, one camera). These are
# fetched via a single shared coordinator, started lazily only when at least
# one matching tracker has been configured - never once per tracker.
SHARED_TRACKER_BACKED_INTERVALS: dict[str, int] = {
    EP_CARPARK_AVAILABILITY: 60,
    EP_TRAFFIC_IMAGES: 2 * 60,
}

# Datasets exposed only as on-demand actions (services), never polled:
# reference/master data that changes ad hoc / monthly / quarterly, or that
# returns a pre-signed file download link rather than live records.
SERVICE_ONLY_ENDPOINTS = {
    EP_BUS_SERVICES,
    EP_BUS_ROUTES,
    EP_BUS_STOPS,
    EP_TAXI_STANDS,
    EP_PLANNED_BUS_ROUTES,
    EP_TRAFFIC_FLOW,
    EP_GEOSPATIAL_WHOLE_ISLAND,
    EP_PV_BUS,
    EP_PV_ODBUS,
    EP_PV_ODTRAIN,
    EP_PV_TRAIN,
    EP_EV_CHARGING_POINTS_BATCH,
}

# ---------------------------------------------------------------------------
# Tracker (options-flow-added) config keys
# ---------------------------------------------------------------------------
CONF_TRACKER_TYPE = "tracker_type"
CONF_BUS_STOP_CODE = "bus_stop_code"
CONF_SERVICE_NO = "service_no"
CONF_CARPARK_ID = "carpark_id"
CONF_POSTAL_CODE = "postal_code"
CONF_NAME = "name"
CONF_LATITUDE = "latitude"
CONF_LONGITUDE = "longitude"
CONF_RADIUS_KM = "radius_km"
CONF_TRAIN_LINE = "train_line"
CONF_CAMERA_ID = "camera_id"

TRACKER_BUS_STOP = "bus_stop"
TRACKER_CARPARK = "carpark"
TRACKER_EV_POSTAL = "ev_postal"
TRACKER_BICYCLE_PARKING = "bicycle_parking"
TRACKER_CROWD_LINE = "crowd_line"
TRACKER_CAMERA = "camera"

TRACKER_TYPES = [
    TRACKER_BUS_STOP,
    TRACKER_CARPARK,
    TRACKER_EV_POSTAL,
    TRACKER_BICYCLE_PARKING,
    TRACKER_CROWD_LINE,
    TRACKER_CAMERA,
]

DEFAULT_BICYCLE_RADIUS_KM = 0.5

# Train line codes as documented for Train Service Alerts (2.11) - used to
# create one "service alert" binary sensor per line, always present.
ALERT_TRAIN_LINES = ["EWL", "NSL", "NEL", "CCL", "DTL", "TEL", "BPL", "STL", "PTL"]

# Train line codes as documented for Station Crowd Density (2.24 / 2.25) -
# this is the set of valid values for the crowd_line tracker's TrainLine param.
CROWD_TRAIN_LINES = [
    "CCL",
    "CEL",
    "CGL",
    "DTL",
    "EWL",
    "NEL",
    "NSL",
    "BPL",
    "SLRT",
    "PLRT",
    "TEL",
]

CROWD_LEVEL_MAP = {"l": "low", "m": "moderate", "h": "high", "NA": "unknown"}

# Cap on list-type extra state attributes to avoid oversized recorder rows.
MAX_ATTR_LIST_ITEMS = 50

MANUFACTURER = "Land Transport Authority (Singapore)"
