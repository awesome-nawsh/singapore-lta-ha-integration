# Functional Specification

What `lta_datamall` does, from a user's point of view. For internal
structure see `ARCHITECTURE.md`; for why it works this way see `DESIGN.md`.

## Setup

1. Install via HACS (custom repository, category Integration) and restart HA.
2. Settings > Devices & Services > Add Integration > "LTA DataMall".
3. Enter an LTA DataMall AccountKey. It's validated with a live API call
   before the entry is created; on success the entry is named "LTA
   DataMall" and the AccountKey is stored only in that entry.
4. A duplicate entry using the same AccountKey is rejected.

Failure modes surfaced to the user during setup:
- Wrong/revoked key -> "The AccountKey was rejected by LTA DataMall."
- No network / LTA unreachable -> "Could not reach LTA DataMall..."

## Entities created automatically (no configuration needed)

All attached to one shared "LTA DataMall" device.

| Entity | Platform | State | Key attributes | Update interval |
|---|---|---|---|---|
| Traffic Incidents | sensor | count | `incidents` (list, capped 50) | 2 min |
| Faulty Traffic Lights | sensor | count | `faults` (list, capped 50) | 2 min |
| Planned Road Openings | sensor | count | `road_openings` (list, capped 50) | 24 h |
| Approved Road Works | sensor | count | `road_works` (list, capped 50) | 24 h |
| VMS Messages | sensor | count | `messages` (list, capped 50) | 2 min |
| Taxis Available | sensor | count | - | 1 min |
| MRT Lifts Under Maintenance | sensor | count | `lifts` (list, capped 50) | 1 h |
| Estimated Travel Times | sensor | segment count | `expressways` (grouped detail) | 5 min |
| Traffic Speed (Island-wide Average) | sensor | km/h | `road_segments_reporting` | 5 min |
| Flood Alert | binary_sensor | on/off | `alerts` (list, capped 50) | 3 min |
| `<Line>` Line Service Alert × 9 | binary_sensor | on/off | direction, stations, free bus/shuttle info, message | 5 min |

The 9 train-line binary sensors cover EWL, NSL, NEL, CCL, DTL, TEL, BPL, STL,
PTL (the line codes documented for the Train Service Alerts API).

## Trackers (user-added, via the integration's Configure/options menu)

Each tracker is added/removed independently and takes effect after an
automatic reload of the integration (no restart needed).

| Tracker | Input | Entities created | Device |
|---|---|---|---|
| Bus stop | 5-digit stop code, optional service number | One sensor per bus service currently serving the stop (minutes to next arrival; attributes: operator, load, bus type, wheelchair accessibility, monitored flag, live coordinates, 2nd/3rd bus ETA) - created dynamically as services are seen | "Bus Stop `<code>`" |
| Carpark | CarParkID | One "Available Lots" sensor (sum across lot types; attributes: development, area, agency, per-lot-type breakdown) | "Carpark `<id>`" |
| EV charging | 6-digit postal code | One "Available Connectors" sensor (count of connectors currently free across every charging station found at that postal code; attributes: per-station detail) | "EV Charging - `<postal>`" |
| Bicycle parking | Name, latitude, longitude, radius (km, default 0.5) | One "Racks Found" sensor (count of parking locations in radius; attributes: per-location description/type/capacity/shelter/coordinates) | "Bicycle Parking - `<name>`" |
| Train line | Line code (CCL, CEL, CGL, DTL, EWL, NEL, NSL, BPL, SLRT, PLRT, TEL) | One "Station `<code>` Crowd Level" sensor per station on that line (state: low/moderate/high/unknown; attribute: 30-min forecast for the rest of the day) - created dynamically per station seen | "Station Crowd Density - `<line>` Line" |
| Traffic camera | CameraID | One camera entity showing the latest image (fetched live on request, never cached; attributes: latitude, longitude) | "Traffic Camera `<id>`" |

Removing a tracker removes its entities and device on the next reload.

## Actions (Developer Tools > Actions, or from automations/scripts)

Reference/bulk datasets that are not polled - each call hits LTA live and
returns its result as action response data.

| Action | Purpose | Optional input |
|---|---|---|
| `lta_datamall.get_bus_services` | Every bus service's operator/category/first-last stop/dispatch frequency | `service_no` |
| `lta_datamall.get_bus_routes` | Every stop, in order, along every service's route | - |
| `lta_datamall.get_bus_stops` | Bus stop code, road name, coordinates | `bus_stop_code` |
| `lta_datamall.get_taxi_stands` | Taxi stand locations | - |
| `lta_datamall.get_planned_bus_routes` | Planned new/updated bus routes not yet in effect | - |
| `lta_datamall.get_traffic_flow` | Hourly average traffic volume by road category | - |
| `lta_datamall.get_geospatial_layer` | 5-minute download link for a SHP geospatial layer | `layer_id` (required) |
| `lta_datamall.get_ev_charging_points_batch` | Every EV charging point island-wide in one call | - |
| `lta_datamall.get_passenger_volume_bus` | 5-minute download link: passenger volume by bus stop | `date` (YYYYMM) |
| `lta_datamall.get_passenger_volume_od_bus` | 5-minute download link: trip counts, bus stop to bus stop | `date` (YYYYMM) |
| `lta_datamall.get_passenger_volume_od_train` | 5-minute download link: trip counts, station to station | `date` (YYYYMM) |
| `lta_datamall.get_passenger_volume_train` | 5-minute download link: passenger volume by train station | `date` (YYYYMM) |

## Non-functional behavior

- No coordinator polls faster than LTA's documented publish frequency for
  that dataset (20 seconds up to 24 hours, depending on endpoint).
- List-type attributes are capped at 50 items to avoid oversized recorder
  history rows.
- Carpark Availability and Traffic Images are fetched once per poll cycle
  regardless of how many carpark/camera trackers are configured (see
  `ARCHITECTURE.md` §2).
- Auth failures surface as a re-authentication prompt on the integration;
  transient network failures mark entities unavailable rather than removing
  them.

## Explicitly out of scope (not implemented)

- No YAML configuration path - config flow / options flow only.
- No `device_tracker` entities for live taxi coordinates (Taxi Availability
  is exposed only as a count, to avoid dumping large coordinate lists into
  entity attributes/recorder history).
- No historical caching or local storage of Passenger Volume / Geospatial
  data - the action always fetches a fresh link from LTA.
- No pre-validation of tracker input against LTA's live master lists (see
  `DESIGN.md`, Known limitations).
- No de-duplication of trackers that resolve to the same underlying item.
