"""Config and options flow for LTA DataMall.

The AccountKey is collected once in the initial config flow and stored only
in this config entry's data (HA's encrypted-at-rest storage) - it is never
written to YAML and is only ever used by this integration's own API client.

After setup, "trackers" (a bus stop, a carpark, a postal code for EV
charging, ...) are added and removed through the options flow. Trackers are
stored in ``entry.options["trackers"]`` and any change triggers a full
reload of the config entry (see ``async_update_listener`` in ``__init__.py``)
so coordinators/entities are rebuilt to match.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .api import LTAApiClient, LTAApiError, LTAAuthError
from .const import (
    CONF_ACCOUNT_KEY,
    CONF_BUS_STOP_CODE,
    CONF_CAMERA_ID,
    CONF_CARPARK_ID,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_POSTAL_CODE,
    CONF_RADIUS_KM,
    CONF_SERVICE_NO,
    CONF_TRACKER_TYPE,
    CONF_TRAIN_LINE,
    CROWD_TRAIN_LINES,
    DEFAULT_BICYCLE_RADIUS_KM,
    DOMAIN,
    TRACKER_BICYCLE_PARKING,
    TRACKER_BUS_STOP,
    TRACKER_CAMERA,
    TRACKER_CARPARK,
    TRACKER_CROWD_LINE,
    TRACKER_EV_POSTAL,
)

BUS_STOP_CODE_RE = re.compile(r"^\d{5}$")
POSTAL_CODE_RE = re.compile(r"^\d{6}$")


class LTAConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial setup (AccountKey only)."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            account_key = user_input[CONF_ACCOUNT_KEY].strip()
            client = LTAApiClient(self.hass, account_key)
            try:
                await client.async_validate_key()
            except LTAAuthError:
                errors["base"] = "invalid_auth"
            except LTAApiError:
                errors["base"] = "cannot_connect"
            else:
                unique_id = hashlib.sha256(account_key.encode()).hexdigest()[:16]
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="LTA DataMall",
                    data={CONF_ACCOUNT_KEY: account_key},
                    options={"trackers": []},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_ACCOUNT_KEY): str}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> "LTAOptionsFlow":
        return LTAOptionsFlow(config_entry)


class LTAOptionsFlow(config_entries.OptionsFlow):
    """Add/remove trackers (bus stops, carparks, EV postal codes, ...)."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._entry = config_entry

    def _trackers(self) -> list[dict[str, Any]]:
        return list(self._entry.options.get("trackers", []))

    async def _async_add_tracker(self, tracker: dict[str, Any]) -> FlowResult:
        trackers = self._trackers()
        trackers.append(tracker)
        return self.async_create_entry(title="", data={"trackers": trackers})

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "add_bus_stop",
                "add_carpark",
                "add_ev_postal",
                "add_bicycle_parking",
                "add_crowd_line",
                "add_camera",
                "remove_tracker",
            ],
        )

    async def async_step_add_bus_stop(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            code = user_input[CONF_BUS_STOP_CODE].strip()
            if not BUS_STOP_CODE_RE.match(code):
                errors["base"] = "invalid_bus_stop_code"
            else:
                return await self._async_add_tracker(
                    {
                        CONF_TRACKER_TYPE: TRACKER_BUS_STOP,
                        CONF_BUS_STOP_CODE: code,
                        CONF_SERVICE_NO: user_input.get(CONF_SERVICE_NO, "").strip() or None,
                    }
                )
        return self.async_show_form(
            step_id="add_bus_stop",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_BUS_STOP_CODE): str,
                    vol.Optional(CONF_SERVICE_NO, default=""): str,
                }
            ),
            errors=errors,
            description_placeholders={"example": "83139"},
        )

    async def async_step_add_carpark(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            return await self._async_add_tracker(
                {
                    CONF_TRACKER_TYPE: TRACKER_CARPARK,
                    CONF_CARPARK_ID: user_input[CONF_CARPARK_ID].strip(),
                }
            )
        return self.async_show_form(
            step_id="add_carpark",
            data_schema=vol.Schema({vol.Required(CONF_CARPARK_ID): str}),
            description_placeholders={"example": "A0007"},
        )

    async def async_step_add_ev_postal(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            postal = user_input[CONF_POSTAL_CODE].strip()
            if not POSTAL_CODE_RE.match(postal):
                errors["base"] = "invalid_postal_code"
            else:
                return await self._async_add_tracker(
                    {CONF_TRACKER_TYPE: TRACKER_EV_POSTAL, CONF_POSTAL_CODE: postal}
                )
        return self.async_show_form(
            step_id="add_ev_postal",
            data_schema=vol.Schema({vol.Required(CONF_POSTAL_CODE): str}),
            errors=errors,
            description_placeholders={"example": "123456"},
        )

    async def async_step_add_bicycle_parking(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            return await self._async_add_tracker(
                {
                    CONF_TRACKER_TYPE: TRACKER_BICYCLE_PARKING,
                    CONF_NAME: user_input[CONF_NAME].strip(),
                    CONF_LATITUDE: user_input[CONF_LATITUDE],
                    CONF_LONGITUDE: user_input[CONF_LONGITUDE],
                    CONF_RADIUS_KM: user_input.get(CONF_RADIUS_KM, DEFAULT_BICYCLE_RADIUS_KM),
                }
            )
        return self.async_show_form(
            step_id="add_bicycle_parking",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME): str,
                    vol.Required(CONF_LATITUDE): vol.Coerce(float),
                    vol.Required(CONF_LONGITUDE): vol.Coerce(float),
                    vol.Optional(CONF_RADIUS_KM, default=DEFAULT_BICYCLE_RADIUS_KM): vol.Coerce(float),
                }
            ),
        )

    async def async_step_add_crowd_line(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            return await self._async_add_tracker(
                {CONF_TRACKER_TYPE: TRACKER_CROWD_LINE, CONF_TRAIN_LINE: user_input[CONF_TRAIN_LINE]}
            )
        return self.async_show_form(
            step_id="add_crowd_line",
            data_schema=vol.Schema(
                {vol.Required(CONF_TRAIN_LINE): vol.In(CROWD_TRAIN_LINES)}
            ),
        )

    async def async_step_add_camera(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            return await self._async_add_tracker(
                {CONF_TRACKER_TYPE: TRACKER_CAMERA, CONF_CAMERA_ID: user_input[CONF_CAMERA_ID].strip()}
            )
        return self.async_show_form(
            step_id="add_camera",
            data_schema=vol.Schema({vol.Required(CONF_CAMERA_ID): str}),
            description_placeholders={"example": "1701"},
        )

    async def async_step_remove_tracker(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        trackers = self._trackers()
        if not trackers:
            return self.async_abort(reason="no_trackers")

        labels = {str(i): _tracker_label(t) for i, t in enumerate(trackers)}
        if user_input is not None:
            index = int(user_input["tracker"])
            del trackers[index]
            return self.async_create_entry(title="", data={"trackers": trackers})

        return self.async_show_form(
            step_id="remove_tracker",
            data_schema=vol.Schema({vol.Required("tracker"): vol.In(labels)}),
        )


def _tracker_label(tracker: dict[str, Any]) -> str:
    ttype = tracker.get(CONF_TRACKER_TYPE)
    if ttype == TRACKER_BUS_STOP:
        svc = tracker.get(CONF_SERVICE_NO)
        return f"Bus stop {tracker[CONF_BUS_STOP_CODE]}" + (f" (svc {svc})" if svc else " (all services)")
    if ttype == TRACKER_CARPARK:
        return f"Carpark {tracker[CONF_CARPARK_ID]}"
    if ttype == TRACKER_EV_POSTAL:
        return f"EV charging near postal {tracker[CONF_POSTAL_CODE]}"
    if ttype == TRACKER_BICYCLE_PARKING:
        return f"Bicycle parking near {tracker[CONF_NAME]}"
    if ttype == TRACKER_CROWD_LINE:
        return f"Station crowd density - {tracker[CONF_TRAIN_LINE]} line"
    if ttype == TRACKER_CAMERA:
        return f"Traffic camera {tracker[CONF_CAMERA_ID]}"
    return str(tracker)
