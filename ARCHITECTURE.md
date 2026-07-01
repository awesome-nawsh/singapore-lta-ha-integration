# Architecture

This document describes how the `lta_datamall` HACS integration is put
together internally. For what it does from a user's perspective, see
`FUNCTIONAL_SPEC.md`. For why it's built this way, see `DESIGN.md`.

## Overview

A single Python package, `custom_components/lta_datamall/`, implementing a
standard Home Assistant "hub" integration with config flow support. It has
no third-party runtime dependencies - `manifest.json` declares
`requirements: []` - because it only uses `aiohttp` and `voluptuous`, both
of which Home Assistant provides to every integration.

```
custom_components/lta_datamall/
  __init__.py       setup/unload entry points, wires everything together
  manifest.json     HA integration metadata
  const.py          domain, endpoint paths, update intervals, config keys
  api.py            thin async HTTP client - one method per LTA endpoint
  coordinator.py    DataUpdateCoordinator factories (global/shared/tracker)
  config_flow.py    initial setup (AccountKey) + options flow (trackers)
  entity.py         shared device_info + base entity class
  sensor.py         global sensors, tracker sensors, dynamic sensors
  binary_sensor.py  flood alert, train line service alerts
  camera.py         tracked traffic cameras
  services.py       on-demand actions for reference/bulk datasets
  services.yaml     UI metadata for those actions
  strings.json / translations/en.json
hacs.json           HACS packaging metadata
.github/workflows/validate.yml   hassfest + HACS validation CI
```

## Data flow

```
LTA DataMall REST API
        |
     api.py            <- AccountKey header, JSON, $skip pagination
        |
  coordinator.py        <- DataUpdateCoordinator, one per dataset/tracker
        |
  entity.py + sensor.py/binary_sensor.py/camera.py
        |
   Home Assistant state machine / device registry
```

`services.py` bypasses the coordinator layer entirely: reference/bulk
endpoints are called directly, once, on demand, when the user invokes the
action - they are never polled.

## The three-tier coordinator model

This is the central design decision, and the key to understanding the
codebase. Every LTA DataMall endpoint falls into exactly one of three tiers,
determined by two questions: does the API take a location/line filter
parameter, and how often does the underlying data change?

### 1. Global coordinators (`GLOBAL_UPDATE_INTERVALS` in `const.py`)

One per Singapore-wide dataset that has **no filter parameter** and backs an
**always-present** entity: Train Service Alerts, Traffic Incidents, Faulty
Traffic Lights, VMS, Flood Alerts, Planned Road Openings, Approved Road
Works, Estimated Travel Times, Traffic Speed Bands, Taxi Availability,
Facilities Maintenance.

Created eagerly in `async_build_global_coordinators()` during
`async_setup_entry`, and polled for the lifetime of the config entry
regardless of what trackers exist. Their entities are attached to the
shared "hub" device (`hub_device_info()` in `entity.py`).

### 2. Shared/lazy coordinators (`SHARED_TRACKER_BACKED_INTERVALS`)

Datasets that also have **no filter parameter**, but back **tracker**
entities that each pick one item out of the full list: Carpark Availability
(filtered client-side by `CarParkID`) and Traffic Images (filtered
client-side by `CameraID`).

These are only created the first time a matching tracker is configured
(`async_get_or_create_shared_coordinator()` in `coordinator.py`), and every
tracker of that type shares the same coordinator instance - so the
island-wide dataset (potentially thousands of carparks, dozens of cameras)
is fetched **once** per poll cycle, never once per tracker.

### 3. Per-tracker coordinators (`TRACKER_UPDATE_INTERVALS`)

Datasets whose API **does** take a location/line filter, so LTA does the
filtering server-side and each tracker only ever fetches its own slice:

| Tracker type | Filter param | Coordinator factory |
|---|---|---|
| Bus stop | `BusStopCode` | `async_create_bus_stop_coordinator` |
| EV charging (postal) | `PostalCode` | `async_create_ev_postal_coordinator` |
| Bicycle parking | `Lat`/`Long` | `async_create_bicycle_parking_coordinator` |
| Station crowd density | `TrainLine` | `async_create_crowd_line_coordinator` |

Each configured tracker gets its own coordinator instance, created in
`async_setup_entry` (`__init__.py`) as it iterates `entry.options["trackers"]`.

### 4. Service-only endpoints (`SERVICE_ONLY_ENDPOINTS`)

Reference/bulk/pre-signed-download datasets that update ad hoc, monthly, or
quarterly: Bus Services, Bus Routes, Bus Stops, Taxi Stands, Planned Bus
Routes, Traffic Flow, Geospatial Whole Island, the 4 Passenger Volume
endpoints, and EV Charging Points Batch. These are never polled - they're
exposed as Home Assistant actions (`services.py` / `services.yaml`) that
call the API directly and return data via `SupportsResponse.ONLY`.

All four tiers share one generic coordinator class, `LTACoordinator` in
`coordinator.py` - a thin `DataUpdateCoordinator` wrapping a single fetch
coroutine. The tiers differ only in *when/how the coordinator is created
and what interval it uses*, never in the class itself.

## Request flow (`api.py`)

`LTAApiClient` is a thin async wrapper around `aiohttp`. Authentication is a
single `AccountKey` header, applied to every request. `_get_all()`
transparently paginates OData `value`-list endpoints via the `$skip`
operator (500 records/page, `MAX_PAGES` safety cap of 40 = 20,000 records);
single-record endpoints (Bus Arrival, Train Service Alerts, the download-link
endpoints) call `_request()` directly instead. HTTP 401/403 raise
`LTAAuthError`; anything else non-200 raises `LTAApiError`. Coordinators
translate these into `UpdateFailed`; `async_setup_entry` translates them into
`ConfigEntryAuthFailed` / `ConfigEntryNotReady` per HA convention.

## Config & runtime state

- `config_flow.py` collects the AccountKey once (`LTAConfigFlow`), validates
  it with a cheap `BusStops` call, and sets a unique ID derived from a SHA-256
  hash of the key (so the raw key never appears in the unique_id/logs, and a
  duplicate entry with the same key is rejected).
- Trackers are added/removed through `LTAOptionsFlow`, a menu-driven options
  flow. They're stored in `entry.options["trackers"]` as a plain list of
  dicts. Any change to options triggers `async_update_listener`, which calls
  `hass.config_entries.async_reload()` so coordinators/entities are rebuilt
  from scratch to match.
- Runtime state lives in `hass.data[DOMAIN][entry.entry_id]` as:
  ```python
  {
    "client": LTAApiClient,
    "global": {endpoint: LTACoordinator, ...},
    "shared": {endpoint: LTACoordinator, ...},   # populated lazily
    "trackers": [{"config": {...}, "coordinator": LTACoordinator}, ...],
    "_sensor_managers": [BusArrivalManager | CrowdLineManager, ...],
  }
  ```

## Entities & platforms

Platforms: `sensor`, `binary_sensor`, `camera` (`PLATFORMS` in `const.py`).
Every entity extends `LTABaseEntity` (a `CoordinatorEntity`, `entity.py`) and
attaches to either the shared hub device (`hub_device_info`) or a per-tracker
device (`tracker_device_info`).

The **dynamic-entity pattern** in `sensor.py` handles the two APIs that
return a variable, data-driven set of items: Bus Arrival (which services
currently serve a stop) and Station Crowd Density (which stations are on a
line). `BusArrivalManager` and `CrowdLineManager` are plain helper objects -
**not** entities themselves - that listen on a coordinator and call
`async_add_entities` the first time each new service/station appears. They're
kept alive in `runtime["_sensor_managers"]` so they aren't garbage collected,
and are never passed to `async_add_entities` themselves.

Traffic camera images (`camera.py`) are fetched fresh on every frame request,
never cached, because each `ImageLink` is a pre-signed URL that expires after
~5 minutes.

## Conventions for adding a new endpoint

1. Add an `EP_*` constant in `const.py`.
2. Add a client method in `api.py` (use `_get_all` for list endpoints, `_request` for single-record/link endpoints).
3. Place it in exactly one tier: `GLOBAL_UPDATE_INTERVALS`, `SHARED_TRACKER_BACKED_INTERVALS` (+ a tracker type), a dedicated tracker coordinator factory, or `SERVICE_ONLY_ENDPOINTS` (+ a handler in `services.py`/`services.yaml`).
4. Update intervals should match LTA's documented publish frequency (see `LTA_DataMall_API_User_Guide.pdf`) - never poll faster than LTA publishes.
5. Cap any list-type state attribute at `MAX_ATTR_LIST_ITEMS` to avoid oversized recorder rows.
6. Keep `strings.json` + `translations/en.json` + `services.yaml` in sync with any config_flow/services.py changes, or hassfest will fail.
