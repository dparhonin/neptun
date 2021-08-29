"""Support for Neptun valves."""
from __future__ import annotations
import asyncio

from datetime import timedelta
import datetime
import logging
from typing import AsyncContextManager

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import (
    CONF_NAME,
    STATE_ON,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_VALVES,
    NEPTUN_DOMAIN,
    REGISTER_STATUS,
)
from .neptun import NeptunHub
from pymodbus.payload import BinaryPayloadBuilder, BinaryPayloadDecoder
from pymodbus.constants import Endian

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant, config: ConfigType, async_add_entities, discovery_info=None
):
    """Read configuration and create Neptun valves."""
    valves = []

    _LOGGER.debug("*** Initializing valves...")
    hub: NeptunHub = hass.data[NEPTUN_DOMAIN][discovery_info[CONF_NAME]]
    for valveIndex, valveName in enumerate(discovery_info[CONF_VALVES]):
        valve = NeptunValve(hub, valveName, valveIndex)
        valves.append(valve)
        _LOGGER.debug("*** Valve discovered: {}".format(valve.name))
    _LOGGER.debug("*** Adding valves: {}".format(valves))
    async_add_entities(valves)


valveMasks = {0: 0b000100000000, 1: 0b001000000000}


class NeptunValve(SwitchEntity, RestoreEntity):
    """Base class representing a Neptun valve as a switch."""

    def __init__(self, hub: NeptunHub, valveName: str, valveIndex: int):
        """Initialize the valve."""
        self._hub: NeptunHub = hub
        self._name = valveName
        self._is_on = None
        self._available = True
        self._scan_interval = timedelta(seconds=10)
        self._command_mask = valveMasks[valveIndex]
        self._currentValue = 0

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        state = await self.async_get_last_state()
        if state:
            self._is_on = state.state == STATE_ON
        async_track_time_interval(
            self.hass, self.async_update_by_timer, self._scan_interval
        )

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._is_on

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def should_poll(self):
        """Return True if entity has to be polled for state."""
        return False

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    def turn_on(self, **kwargs):
        """Turn valve on."""
        self.do_turn(True)

    def turn_off(self, **kwargs):
        """Turn valve off."""
        self.do_turn(False)

    def do_turn(self, is_on):
        """Turning a valve."""
        _LOGGER.debug("*** Turning valve {}...".format(self.name))
        asyncio.run_coroutine_threadsafe(self.async_update(), self.hass.loop).result()
        if self._available:
            if is_on:
                command = self._currentValue | self._command_mask
            else:
                command = self._currentValue & ~self._command_mask
            command = command & 0x1FFF  # only meaningful bits
            _LOGGER.debug("*** Start writing value: {}".format(command))
            # encoder = BinaryPayloadBuilder(byteorder=Endian.Big)
            # encoder.add_16bit_uint(command)
            # payload = encoder.to_registers()
            result = self._hub.write_register(address=REGISTER_STATUS, value=command)
            _LOGGER.debug("*** Result received: {}".format(result))
            if result is False:
                self._available = False
                self.async_schedule_update_ha_state()
            else:
                self._available = True
                self._is_on = is_on
                self.async_schedule_update_ha_state()
        else:
            _LOGGER.warn(
                "Cannot turn a valve {} when it is unavailable!".format(self.name)
            )

    async def async_update_by_timer(self, now: datetime | None = None) -> None:
        await self.async_update()

    async def async_update(self):
        """Update the entity state."""
        _LOGGER.debug(">>> Updating valve: {}".format(self.name))
        current = await self.hass.async_add_executor_job(
            lambda: self._hub.read_holding_registers(REGISTER_STATUS)
        )
        if current is not None:
            _LOGGER.debug("*** Received registers: {}".format(current))
            # decoder = BinaryPayloadDecoder.fromRegisters(
            #     current.registers, byteorder=Endian.Big
            # )
            # self._currentValue = decoder.decode_16bit_uint()
            self._currentValue = current.registers[0]
            self._is_on = (
                self._currentValue & self._command_mask
            ) == self._command_mask
            self._available = True
            _LOGGER.debug(
                "*** Current register value: {}, mask={}, valve '{}'={}".format(
                    self._currentValue, self._command_mask, self.name, self._is_on
                )
            )
        else:
            self._available = False
            _LOGGER.warn(
                "*** Cannot read current register value for {}!".format(self.name)
            )
        self.async_schedule_update_ha_state()
        _LOGGER.debug("<<< Valve {} updated".format(self.name))
