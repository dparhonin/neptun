"""Support for Neptun."""
from __future__ import annotations

from typing import Any, Optional
from pymodbus.utilities import default

import voluptuous as vol
from voluptuous.validators import Boolean

from homeassistant.const import (
    ATTR_NAME,
    CONF_METHOD,
    CONF_NAME,
    CONF_PORT,
    CONF_TIMEOUT,
    CONF_TYPE,
    CONF_HOST,
)
import homeassistant.helpers.config_validation as cv

from const import (
    NEPTUN_DOMAIN as DOMAIN,
    ATTR_HUB,
    ATTR_VALVE,
    ATTR_VALUE,
    CONF_HUBS,
    CONF_MQTT,
    CONF_PARITY,
    CONF_BAUDRATE,
    CONF_BYTESIZE,
    CONF_STOPBITS,
    CONF_CONNECTION,
    CONF_USER,
    CONF_PASSWORD,
    CONF_VALVES,
)
from .neptun import async_neptun_setup

# def number(value: Any) -> int | float:
#     """Coerce a value to number without losing precision."""
#     if isinstance(value, int):
#         return value
#     if isinstance(value, float):
#         return value

#     try:
#         value = int(value)
#         return value
#     except (TypeError, ValueError):
#         pass
#     try:
#         value = float(value)
#         return value
#     except (TypeError, ValueError) as err:
#         raise vol.Invalid(f"invalid number {value}") from err


HUB_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_CONNECTION): {
            vol.Required(CONF_TYPE): "serial",
            vol.Optional(CONF_METHOD, default="rtu"): vol.Any("rtu", "ascii"),
            vol.Optional(CONF_BAUDRATE, default=9600): cv.positive_int,
            vol.Optional(CONF_BYTESIZE, default=8): vol.Any(5, 6, 7, 8),
            vol.Required(CONF_PORT): cv.string,
            vol.Optional(CONF_PARITY, default="N"): vol.Any("E", "O", "N"),
            vol.Optional(CONF_STOPBITS, default=1): vol.Any(1, 2),
            vol.Optional(CONF_TIMEOUT, default=1): cv.positive_int,
        },
        vol.Optional(CONF_VALVES): vol.All(cv.ensure_list, [cv.string]),
    }
)

MQTT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT): cv.port,
        vol.Required(CONF_USER): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)

NEPTUN_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_HUBS): vol.All(cv.ensure_list, [HUB_SCHEMA]),
        vol.Optional(CONF_MQTT): MQTT_SCHEMA,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: NEPTUN_SCHEMA,
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_ONE_VALVE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_HUB): cv.string,
        vol.Required(ATTR_VALVE): cv.positive_int,
    }
)

SERVICE_ALL_VALVES_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_HUB): cv.string,
    }
)

SERVICE_SET_ATTR_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_HUB): cv.string,
        vol.Required(ATTR_NAME): cv.string,
        vol.Required(ATTR_VALUE): cv.boolean,
    }
)


async def async_setup(hass, config):
    """Set up Neptun component."""
    return await async_neptun_setup(
        hass,
        config,
        SERVICE_ONE_VALVE_SCHEMA,
        SERVICE_ALL_VALVES_SCHEMA,
        SERVICE_SET_ATTR_SCHEMA,
    )
