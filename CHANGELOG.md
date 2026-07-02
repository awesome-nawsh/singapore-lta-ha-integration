# Changelog

All notable changes to this integration are documented here. Format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions
follow the `manifest.json` `version` field.

## [Unreleased]

Nothing yet.

## [0.1.4] - 2026-07-02

### Added

- Two on-demand actions to help discover tracker IDs without leaving Home
  Assistant: `lta_datamall.get_carpark_availability` (lists every carpark's
  `CarParkID`, development and free lots) and `lta_datamall.get_traffic_cameras`
  (lists every camera's `CameraID` and coordinates).
- A "Where to find each ID / value" reference table in `README.md` and
  `FUNCTIONAL_SPEC.md` mapping every tracker input to where to look it up.

## [0.1.3] - 2026-07-02

### Added

- Per-tracker devices now nest under a themed category device by type, so
  they group in the tree instead of hanging individually off the hub: **Bus**
  (bus-stop trackers), **Carparks**, **EV Charging**, and **Bicycle Parking**,
  with Station Crowd trackers folded into **Rail / MRT** and Traffic Camera
  trackers into **Roads & Traffic**. Category devices appear only for tracker
  types that are actually configured. Existing tracker devices are re-parented
  on upgrade.

## [0.1.2] - 2026-07-02

### Fixed

- Existing global entities now actually move onto the themed sub-devices
  introduced in 0.1.1. Changing an entity's `device_info` does not, on its
  own, re-home an already-registered entity (HA creates the new device but
  leaves the entity on its original one), so upgraded installs saw the four
  themed devices created but empty while all entities stayed on the hub. Setup
  now performs an explicit entity-registry migration; new installs and
  already-migrated installs are unaffected.

## [0.1.1] - 2026-07-02

### Changed

- The always-on Singapore-wide entities are now grouped into themed
  sub-devices ("Roads & Traffic", "Rail / MRT", "Taxis", "Environment &
  Safety") that hang off the main "LTA DataMall" hub device, instead of all
  ~19 entities appearing as one flat list under a single device. The hub
  device is now registered explicitly at setup so those sub-devices (and the
  per-tracker devices) have a `via_device` parent.

### Fixed

- Corrected the documented minimum Home Assistant version in the README to
  2024.6 to match `hacs.json`.
- Pointed the manifest `documentation` / `issue_tracker` / `codeowners` at
  the actual repository.

## [0.1.0] - 2026-07-01

Initial release. Full coverage of the LTA DataMall API User Guide v6.8 (21
Apr 2026) - all 30 documented endpoints.

### Added

- Config flow: AccountKey entry with live validation, stored per config entry.
- Options flow: add/remove trackers for bus stops, carparks, EV charging
  postal codes, bicycle parking points, train lines, and traffic cameras.
- 11 always-on global sensors/binary sensors covering Traffic Incidents,
  Faulty Traffic Lights, Planned Road Openings, Approved Road Works, VMS
  Messages, Taxis Available, MRT Lifts Under Maintenance, Estimated Travel
  Times, Traffic Speed (island-wide average), Flood Alert, and one Train
  Service Alert binary sensor per line (9 lines).
- Tracker entities: Bus Arrival (dynamic, one sensor per service at a
  stop), Carpark Availability, EV Charging Points, Bicycle Parking, Station
  Crowd Density (dynamic, one sensor per station on a tracked line,
  real-time + forecast), and traffic camera image entities.
- 12 on-demand actions for reference/bulk datasets: Bus Services, Bus
  Routes, Bus Stops, Taxi Stands, Planned Bus Routes, Traffic Flow,
  Geospatial Whole Island, EV Charging Points Batch, and the 4 Passenger
  Volume endpoints.
- HACS packaging (`hacs.json`) and CI validation (hassfest + HACS action).

### Notes

- No YAML configuration support - config flow / options flow only, by
  design (see `DESIGN.md`).
- See `FUNCTIONAL_SPEC.md` for the full entity/action catalog, and
  `TODO.md` for known limitations not addressed in this release.
