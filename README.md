# LTA DataMall for Home Assistant

A HACS custom integration that connects Home Assistant to the Singapore
Land Transport Authority's [DataMall](https://datamall.lta.gov.sg/) APIs:
bus arrivals, train service alerts, carpark availability, EV charging
points, bicycle parking, traffic cameras, station crowd density, and more.

## Requirements

- A free LTA DataMall account and **AccountKey**. Register at
  https://datamall.lta.gov.sg/content/datamall/en/request-for-api.html.
- Home Assistant 2024.6 or newer.

## Installation (HACS)

1. HACS > Integrations > menu (⋮) > Custom repositories > add this
   repository URL, category "Integration".
2. Install "LTA DataMall (Singapore)", then restart Home Assistant.
3. Settings > Devices & Services > Add Integration > search "LTA DataMall".
4. Enter your AccountKey. It is stored only in this config entry and used
   only by this integration - never written to YAML, never shared.

## What you get automatically

As soon as the AccountKey is validated, these Singapore-wide entities are
created (no configuration needed, because the underlying APIs have no
location filter):

- Traffic Incidents, Faulty Traffic Lights, Planned Road Openings, Approved
  Road Works, VMS Messages - each a count sensor with the full list as an
  attribute.
- Taxis Available, MRT Lifts Under Maintenance - count sensors.
- Estimated Travel Times - segment count with per-expressway detail.
- Traffic Speed (Island-wide Average) - km/h, averaged from all reporting
  road links.
- Flood Alert - binary sensor.
- One "`<Line>` Line Service Alert" binary sensor per MRT/LRT line (EWL,
  NSL, NEL, CCL, DTL, TEL, BPL, STL, PTL).

## Adding trackers

Because most of Singapore's data is island-wide, you tell the integration
*which* items you care about via Settings > Devices & Services > LTA
DataMall > Configure:

| Tracker | What it needs | What you get |
|---|---|---|
| Bus stop | 5-digit bus stop code, optional service number | One sensor per service at that stop, showing minutes to next arrival |
| Carpark | CarParkID (LTA/URA/HDB) | Available lots sensor |
| EV charging | 6-digit postal code | Available connectors sensor per charging station found |
| Bicycle parking | Latitude/longitude + radius | Racks-found sensor |
| Train line | Line code | One crowd-level sensor per station on that line (real-time + forecast) |
| Traffic camera | CameraID | A camera entity showing the latest image |

Trackers can be added and removed at any time; the integration reloads
automatically to match.

### Where to find each ID / value

You supply an ID, code, or coordinate when adding a tracker. Here is where
to look each one up - several can be pulled from LTA itself using this
integration's own actions (Developer Tools > Actions), so you don't need to
leave Home Assistant:

| Tracker input | Where to find it |
|---|---|
| Bus stop code (5-digit) | Printed on the physical bus-stop pole; call `lta_datamall.get_bus_stops` (returns every stop's code, road name and coordinates); or search a stop on [BusRouter SG](https://busrouter.sg/). |
| Bus service number | Call `lta_datamall.get_bus_services` for the full list, or `lta_datamall.get_bus_routes` to see which services stop at a given code. |
| CarParkID | Call `lta_datamall.get_carpark_availability` to list every carpark (LTA/HDB/URA) with its `CarParkID`, development name and free lots; also on the [DataMall dynamic datasets page](https://datamall.lta.gov.sg/content/datamall/en/dynamic-data.html) or [data.gov.sg](https://data.gov.sg/). |
| EV charging postal code (6-digit) | Any Singapore 6-digit postal code. Look up an address on [OneMap](https://www.onemap.gov.sg/); or call `lta_datamall.get_ev_charging_points_batch` to list every charging point island-wide (each carries its address) and pick one. |
| Bicycle parking latitude / longitude | Read the coordinates off [OneMap](https://www.onemap.gov.sg/) or Google Maps (right-click a spot > the lat/long is shown). The radius defaults to 0.5 km. |
| Train line code | One of `CCL`, `CEL`, `CGL`, `DTL`, `EWL`, `NEL`, `NSL`, `BPL`, `SLRT`, `PLRT`, `TEL`. |
| Traffic CameraID | Call `lta_datamall.get_traffic_cameras` to list every camera with its `CameraID` and coordinates; the IDs are also documented in the bundled [`LTA_DataMall_API_User_Guide.pdf`](./LTA_DataMall_API_User_Guide.pdf). |

The master reference for every dataset is LTA's own
[DataMall API User Guide](https://datamall.lta.gov.sg/content/datamall/en/dynamic-data.html)
(also bundled in this repo as `LTA_DataMall_API_User_Guide.pdf`).

## Reference data (actions, not entities)

Bus Services, Bus Routes, Bus Stops, Taxi Stands, Planned Bus Routes,
Traffic Flow, Geospatial Whole Island, the 4 Passenger Volume datasets, and
the EV Charging Points Batch file are reference/bulk datasets that change ad
hoc, monthly, or quarterly (some just return a 5-minute pre-signed download
link rather than records). Polling these as sensors would create a lot of
near-static entities, so instead they're exposed as Home Assistant actions
you call on demand, e.g. in Developer Tools > Actions:

```yaml
action: lta_datamall.get_bus_services
data:
  service_no: "15"
```

Two further actions - `get_carpark_availability` and `get_traffic_cameras` -
expose the island-wide carpark and traffic-camera datasets on demand purely
so you can look up a `CarParkID` or `CameraID` to add as a tracker (these
datasets are otherwise only polled once a matching tracker exists).

See `services.yaml` for the full list and fields.

## Notes

- Update intervals per entity follow the frequency documented in LTA's own
  API User Guide (20 seconds for Bus Arrival, up to 24 hours for Road
  Works) - the integration does not poll faster than LTA publishes new data.
- Carpark Availability and Traffic Images have no per-item filter in LTA's
  API, so all carpark/camera trackers share a single poll of the full
  island-wide dataset rather than each triggering their own API call.

## Contributing

Issues and PRs welcome. Please run `hassfest` and the HACS validation
action locally (see `.github/workflows/validate.yml`) before submitting.
