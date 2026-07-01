# TODO / Ideas Log

A living backlog. Add anything here as it comes up in conversation - it
doesn't need to be fully specified, a one-liner is fine. When something is
built, move it to `CHANGELOG.md` and delete it from here.

## User-requested ideas

_(Nothing logged yet - add requests here as they come up.)_

## Known limitations (identified during the v0.1.0 build)

These were consciously left out of v1 as out of scope, not bugs. See
`DESIGN.md` "Known limitations" for the full reasoning.

- [ ] Duplicate trackers that resolve to the same item (same carpark ID
      twice, two bicycle parking trackers with the same name, etc.) collide
      on `unique_id`. No duplicate detection in the options flow.
- [ ] No validation of tracker input against LTA's live master lists (bus
      stop codes / postal codes are only checked for correct digit format).
      An invalid-but-well-formatted code just yields an `unavailable` entity.
- [ ] Taxi Availability is count-only - no `device_tracker`/map view of
      individual available taxis (a deliberate call to avoid dumping large
      coordinate lists into recorder history, but worth revisiting if
      there's a real use case for it).

## Possible future features (not yet requested, just ideas)

- [ ] Diagnostics support (`diagnostics.py`) for easier bug reports from users.
- [ ] Repair issues (`homeassistant.helpers.issue_registry`) for stale/invalid
      tracker IDs instead of silently going `unavailable`.
- [ ] A `select`/`config_flow` step to look up and pick a bus stop by name
      instead of requiring the raw 5-digit code (would need a Bus Stops
      lookup call during the options flow).
- [ ] Local caching of the last known bus arrival to smooth over brief API
      hiccups without instantly flipping the entity to `unavailable`.
- [ ] Submit to the official HACS default repository (requires registering
      a brand/icon at github.com/home-assistant/brands first).
