"""Support for Neptun Input sensors."""
from __future__ import annotations

from datetime import timedelta
import datetime
import logging
from typing import Any, Mapping
from pymodbus.exceptions import ModbusException

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
)
from homeassistant.const import (
    CONF_NAME,
)
from homeassistant.core import DOMAIN, HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    NEPTUN_DOMAIN,
    REGISTER_STATUS,
    ATTR_KEYBOARD_LOCKED,
    MASK_KEYBOARD_LOCKED,
    ATTR_PESSIMISTIC_WIRELESS_SENSOR,
    MASK_PESSIMISTIC_WIRELESS_SENSOR,
    ATTR_VALVE_TWO_GROUPS,
    MASK_VALVE_TWO_GROUPS,
    ATTR_WIRELESS_PAIRING,
    MASK_WIRELESS_PAIRING,
    ATTR_FLOOR_WASHING,
    MASK_FLOOR_WASHING,
)
from .neptun import NeptunHub

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities,
    discovery_info: DiscoveryInfoType | None = None,
):
    """Set up the Neptun binary sensors."""
    sensors = []

    hub: NeptunHub = hass.data[NEPTUN_DOMAIN][discovery_info[CONF_NAME]]
    _LOGGER.debug("*** Initializing common hub state...")

    sensor = NeptunHubSensor(hub)
    sensors.append(sensor)
    # for valveIndex, valveName in enumerate(discovery_info[CONF_VALVES]):
    #     sensor = NeptunHubSensor(hub, valveName, valveIndex)
    #     sensors.append(sensor)
    #     _LOGGER.debug("*** Sensor discovered: {}".format(valve.name))
    _LOGGER.debug("*** Adding sensors: {}".format(sensors))
    async_add_entities(sensors)


class NeptunHubSensor(BinarySensorEntity):
    """Neptun hub binary sensor."""

    def __init__(self, hub):
        """Initialize the Neptun hub binary sensor."""
        self._hub = hub
        self._name = NEPTUN_DOMAIN + "." + hub.name
        self._attributes = {
            ATTR_KEYBOARD_LOCKED: False,
            ATTR_PESSIMISTIC_WIRELESS_SENSOR: False,
            ATTR_VALVE_TWO_GROUPS: False,
            ATTR_WIRELESS_PAIRING: False,
            ATTR_FLOOR_WASHING: False,
        }
        self._value = None
        self._available = True
        self._scan_interval = timedelta(seconds=10)
        self._alarm_mask = 0b00000110

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        async_track_time_interval(
            self.hass, self.async_update_by_timer, self._scan_interval
        )

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self):
        """Return the state of the sensor."""
        return self._value

    @property
    def device_class(self) -> str | None:
        """Return the device class of the sensor."""
        return None

    @property
    def should_poll(self):
        """Return True if entity has to be polled for state.
        False if entity pushes its state to HA.
        """

        # Handle polling directly in this entity
        return False

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        return self._attributes

    def decode_attributes(self, command):
        """Decodes all Neptun status attributes from the status register value"""
        self._attributes[ATTR_KEYBOARD_LOCKED] = (
            command & MASK_KEYBOARD_LOCKED
        ) == MASK_KEYBOARD_LOCKED
        self._attributes[ATTR_PESSIMISTIC_WIRELESS_SENSOR] = (
            command & MASK_PESSIMISTIC_WIRELESS_SENSOR
        ) == MASK_PESSIMISTIC_WIRELESS_SENSOR
        self._attributes[ATTR_VALVE_TWO_GROUPS] = (
            command & MASK_VALVE_TWO_GROUPS
        ) == MASK_VALVE_TWO_GROUPS
        self._attributes[ATTR_WIRELESS_PAIRING] = (
            command & MASK_WIRELESS_PAIRING
        ) == MASK_WIRELESS_PAIRING
        self._attributes[ATTR_FLOOR_WASHING] = (
            command & MASK_FLOOR_WASHING
        ) == MASK_FLOOR_WASHING

    async def async_update_by_timer(self, now: datetime | None = None) -> None:
        await self.async_update()

    async def async_update(self):
        """Update the state of the sensor."""
        _LOGGER.debug(">>> Updating sensor: {}".format(self.name))
        result = await self.hass.async_add_executor_job(
            lambda: self._hub.read_holding_registers(REGISTER_STATUS)
        )
        if result is ModbusException:
            self._available = False
            _LOGGER.error(
                "Neptun sensor update: Cannot read holding registers: {}".format(result)
            )
        else:
            _LOGGER.debug("*** Received registers: {}".format(result))
            # decoder = BinaryPayloadDecoder.fromRegisters(
            #     current.registers, byteorder=Endian.Big
            # )
            # self._currentValue = decoder.decode_16bit_uint()
            _currentValue = result.registers[0]
            self.decode_attributes(_currentValue)
            self._value = (_currentValue & self._alarm_mask) != 0
            self._available = True
            _LOGGER.debug("*** Current register value: {}".format(_currentValue))
            _LOGGER.debug("*** Current sensor value: {}".format(self._value))
        self.async_schedule_update_ha_state()
        _LOGGER.debug("<<< Sensor {} updated".format(self.name))
