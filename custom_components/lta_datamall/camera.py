"""Camera platform for LTA DataMall: tracked traffic cameras.

Traffic-Imagesv2 has no per-camera filter, so every camera tracker reads out
of the one shared, lazily-created coordinator (see coordinator.py). Each
``ImageLink`` is a pre-signed URL that expires after 5 minutes, so the image
is fetched fresh from the *current* coordinator data every time Home
Assistant asks for a frame rather than being cached.
"""
from __future__ import annotations

import logging

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_CAMERA_ID, CONF_TRACKER_TYPE, DOMAIN, GROUP_ROADS, TRACKER_CAMERA
from .coordinator import LTACoordinator
from .entity import LTABaseEntity, tracker_device_info

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up LTA DataMall camera trackers for a config entry."""
    runtime = hass.data[DOMAIN][entry.entry_id]
    entities = [
        TrafficCameraEntity(tracker["coordinator"], entry, tracker["config"])
        for tracker in runtime["trackers"]
        if tracker["config"][CONF_TRACKER_TYPE] == TRACKER_CAMERA
    ]
    async_add_entities(entities)


class TrafficCameraEntity(LTABaseEntity, Camera):
    """A single LTA traffic camera, identified by CameraID."""

    _attr_name = "Traffic Camera"

    def __init__(self, coordinator: LTACoordinator, entry: ConfigEntry, config: dict) -> None:
        Camera.__init__(self)
        camera_id = config[CONF_CAMERA_ID]
        device = tracker_device_info(
            entry, f"camera_{camera_id}", f"Traffic Camera {camera_id}", GROUP_ROADS[0]
        )
        LTABaseEntity.__init__(self, coordinator, f"{entry.entry_id}_camera_{camera_id}", device)
        self._camera_id = camera_id

    def _current_row(self) -> dict | None:
        for row in self.coordinator.data or []:
            if str(row.get("CameraID")) == str(self._camera_id):
                return row
        return None

    @property
    def extra_state_attributes(self) -> dict:
        row = self._current_row() or {}
        return {"latitude": row.get("Latitude"), "longitude": row.get("Longitude")}

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        row = self._current_row()
        if not row or not row.get("ImageLink"):
            return None
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(row["ImageLink"]) as resp:
                if resp.status != 200:
                    return None
                return await resp.read()
        except Exception:  # noqa: BLE001 - any fetch failure just means "no image"
            _LOGGER.debug("Failed to fetch traffic camera %s image", self._camera_id, exc_info=True)
            return None
