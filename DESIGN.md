# Design Decisions

This document records the decisions made while designing `lta_datamall`,
who made the call, and why - so future changes can be judged against the
original reasoning rather than guessed at. See `ARCHITECTURE.md` for how
these decisions were implemented.

## 1. Full API coverage in v1, not a core subset

**Decision:** cover all 30 documented DataMall endpoints in the first
version, rather than starting with just bus arrivals / train disruptions /
EV charging / carparks and adding the rest later.

**Why:** the maintainer's explicit choice when asked - larger initial build, but no
follow-up work needed to reach parity with the API guide.

## 2. Config Flow UI, not YAML

**Decision:** all configuration (AccountKey, trackers) goes through Home
Assistant's config flow / options flow UI. No `configuration.yaml` support.

**Why:** the maintainer's explicit choice. It's also the current HA-recommended
pattern (YAML config for integrations has been discouraged by HA core for
several years), and it's the only way to support add/remove of trackers
without restarting Home Assistant.

## 3. AccountKey stored per config entry, never in YAML

**Decision:** the AccountKey is entered once in the initial config flow step
and stored only in that config entry's data, in HA's own encrypted-at-rest
storage (`.storage/core.config_entries`). It's used only by that entry's own
`LTAApiClient` instance.

**Why:** the maintainer asked for this explicitly, wanting the key to be scoped to
"that integration only" rather than shared or written to a config file. This
also means multiple config entries with different keys are possible (e.g. a
second AccountKey for testing), each fully isolated.

## 4. Three-tier / four-tier data model, not "one coordinator per endpoint"

**Decision:** endpoints are split into global (always-on), shared/lazy
(backs item-picking trackers, no filter param), per-tracker (has a filter
param), and service-only (reference/bulk data) - see `ARCHITECTURE.md` for
the full breakdown.

**Why:** LTA's 30 endpoints are wildly heterogeneous - update frequency
ranges from 20 seconds (Bus Arrival) to quarterly (Traffic Flow), and only
some endpoints accept a location/line filter. A single polling strategy for
all of them would either hammer LTA's servers with endpoints that rarely
change, or under-poll the ones that matter. This was proposed as a plan and
explicitly approved by the maintainer before any code was written.

A specific refinement made *during* implementation (not part of the original
plan, but a direct consequence of reading the API guide closely): Carpark
Availability and Traffic Images have **no per-item filter parameter at all**
- the API always returns the full island-wide list. Treating "carpark" and
"camera" as regular per-tracker coordinators would have meant every carpark
tracker independently re-fetching the *entire* island-wide carpark dataset
on its own timer - wasteful, and a good way to get rate-limited with only a
handful of trackers configured. Instead they're `SHARED_TRACKER_BACKED`
datasets: one coordinator, created lazily the first time any matching
tracker exists, shared by all trackers of that type, filtered client-side by
`CarParkID` / `CameraID` in the entity itself.

## 5. Bus Arrival: one sensor per service, not one sensor per stop

**Decision:** adding a bus stop tracker creates one sensor per bus service at
that stop (`sensor.lta_bus_<stop>_<service>`, state = minutes to arrival),
rather than a single per-stop sensor with all services as attributes.

**Why:** the maintainer's explicit choice, asked directly during planning. A numeric
state per service is directly usable in automations and dashboard cards
without template parsing; the trade-off (more entities) was accepted
knowingly.

**Implementation consequence:** which services serve a stop isn't known
until the API responds (and can change), so entities are created
dynamically. `BusArrivalManager` (a plain, non-entity helper object, not
`CrowdLineManager`'s sibling) listens to the stop's coordinator and calls
`async_add_entities` the first time a new `ServiceNo` appears. The same
pattern is reused for Station Crowd Density, where the set of stations on a
line is similarly only known from the response.

## 6. Reference/bulk data as actions, not entities

**Decision:** Bus Services, Bus Routes, Bus Stops, Taxi Stands, Planned Bus
Routes, Traffic Flow, Geospatial Whole Island, the 4 Passenger Volume
endpoints, and EV Charging Points Batch are exposed as Home Assistant
actions (`lta_datamall.get_*`), not sensors.

**Why:** the maintainer approved this as proposed. Two independent reasons converged:
these datasets update ad hoc/monthly/quarterly (polling them as sensors
would create mostly-static entities for no benefit), and four of them (the
Passenger Volume endpoints, plus Geospatial Whole Island) don't return
records at all - they return a pre-signed S3 zip download link that expires
in 5 minutes, which isn't sensor-shaped data in the first place.

## 7. Traffic Speed Band average uses actual Min/MaxSpeed, not just the band midpoint

**Decision:** `TrafficSpeedBandSensor` averages `(MinimumSpeed +
MaximumSpeed) / 2` per road link when those fields are present, and only
falls back to a fixed speed-band-midpoint lookup table when they're missing.

**Why:** a self-correction made while reading the v4 TrafficSpeedBands
response schema closely - the API already publishes the actual measured
min/max speed per link (not just the 1-8 band number), so using the real
values is strictly more accurate for the same amount of code. Not asked for
explicitly; judged to be a clear improvement, not a scope change.

## 8. Update intervals follow LTA's documented frequency, capped, never faster

Each endpoint's polling interval was set to match the "Update Freq" LTA
documents in the API User Guide (v6.8), e.g. 20s for Bus Arrival, 1 min for
Carpark Availability, 24h for Road Works. This is a hard rule from
`CLAUDE.md` (the project's own instructions), reinforced here: no coordinator
should ever poll faster than LTA states it publishes new data.

## Known limitations / accepted edge cases

These were identified during the build and consciously left unaddressed as
out of scope for v1 (minimum code that solves the stated problem, not
speculative hardening):

- **Duplicate tracker collisions.** If a user adds two trackers that resolve
  to the same identity (e.g. the same carpark ID twice, or two bicycle
  parking trackers with the same `name`), their entities' `unique_id`s
  collide. Home Assistant will keep only one; nothing crashes, but the
  second tracker's sensor won't appear as a distinct entity. No duplicate
  detection is implemented in the options flow.
- **No pre-validation of tracker IDs against LTA's master lists.** Bus stop
  codes and postal codes are checked only for correct *format* (5/6 digits)
  at options-flow time, not checked against LTA's actual Bus Stops list or a
  real postal code. An invalid-but-correctly-formatted code will simply
  result in an entity that's `unavailable` (empty coordinator data) rather
  than a config-flow error.
- **Traffic camera images are fetched live, never cached**, by design (see
  `ARCHITECTURE.md`) - this is a deliberate correctness choice given the
  5-minute link expiry, not a limitation, but it does mean a `camera_image()`
  call is a live outbound `aiohttp` request every time, not a fast local read.
