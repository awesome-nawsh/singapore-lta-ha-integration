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
