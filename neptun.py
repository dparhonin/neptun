"""Support for Neptun."""
from homeassistant.helpers.config_validation import boolean
from homeassistant.components import switch
import logging
import threading

from pymodbus.client.sync import ModbusSerialClient as ModbusClient
from pymodbus.constants import Defaults
from pymodbus.exceptions import ModbusException
from pymodbus.transaction import ModbusRtuFramer

import paho.mqtt.client as mqtt

from homeassistant.const import (
    ATTR_NAME,
    CONF_NAME,
    CONF_PORT,
    CONF_TIMEOUT,
    CONF_TYPE,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.helpers.discovery import async_load_platform

from .const import (
    ATTR_FLOOR_WASHING,
    ATTR_HUB,
    ATTR_KEYBOARD_LOCKED,
    ATTR_PESSIMISTIC_WIRELESS_SENSOR,
    ATTR_VALUE,
    ATTR_VALVE,
    ATTR_VALVE_TWO_GROUPS,
    ATTR_WIRELESS_PAIRING,
    CONF_BINARY_SENSOR,
    CONF_SWITCH,
    CONF_CONNECTION,
    MASK_FLOOR_WASHING,
    MASK_KEYBOARD_LOCKED,
    MASK_PESSIMISTIC_WIRELESS_SENSOR,
    MASK_VALVE_TWO_GROUPS,
    MASK_WIRELESS_PAIRING,
    NEPTUN_DOMAIN as DOMAIN,
    SERVICE_OPEN_VALVE,
    SERVICE_CLOSE_VALVE,
    SERVICE_OPEN_ALL_VALVES,
    SERVICE_CLOSE_ALL_VALVES,
    CONF_HUBS,
    CONF_MQTT,
    CONF_PARITY,
    CONF_STOPBITS,
    CONF_BYTESIZE,
    CONF_BAUDRATE,
    DATA_MQTT_CLIENT,
    REGISTER_STATUS,
    NEPTUN_UNIT,
    SERVICE_SET_CONFIG_ATTRIBUTE,
)

_LOGGER = logging.getLogger(__name__)


def bit_not(n, numbits=16):
    return (1 << numbits) - 1 - n


async def async_neptun_setup(
    hass,
    config,
    service_one_valve_schema,
    service_all_valves_schema,
    service_set_attr_schema,
):
    """Set up Neptun component."""

    _LOGGER.debug(">> Setting up the Neptun integration...")

    hass.data[DOMAIN] = neptunData = {}
    neptunCfg = config[DOMAIN]
    if CONF_HUBS in neptunCfg:
        for conf_hub in neptunCfg[CONF_HUBS]:
            neptunHub = NeptunHub(conf_hub)
            # modbus needs to be activated before components are loaded
            # to avoid a racing problem
            neptunHub.setup()
            neptunData[neptunHub.name] = neptunHub

            # load platforms
            for component in (CONF_BINARY_SENSOR, CONF_SWITCH):
                await async_load_platform(hass, component, DOMAIN, conf_hub, config)

    # Setup MQTT connection
    if CONF_MQTT in neptunCfg:
        mqttClient = MqttClient(neptunCfg[CONF_MQTT])
        mqttClient.setup()
        _LOGGER.info("MQTT client started")
        neptunData[DATA_MQTT_CLIENT] = mqttClient

    def stop_neptun(event):
        """Stop Neptun service."""
        for closeable in neptunData.values():
            closeable.close()
            del closeable

    def open_valve(service):
        """Open a valve on a Neptun hub"""
        hub = service.data[ATTR_HUB]
        valve = int(float(service.data[ATTR_VALVE]))
        neptunData[hub].open_valve(valve)

    def open_all_valves(service):
        """Open all valves on a Neptun hub"""
        hub = service.data[ATTR_HUB]
        neptunData[hub].open_all_valves()

    def close_valve(service):
        """Close a valve on a Neptun hub"""
        hub = service.data[ATTR_HUB]
        valve = int(float(service.data[ATTR_VALVE]))
        neptunData[hub].close_valve(valve)

    def close_all_valves(service):
        """Close all valves on a Neptun hub"""
        hub = service.data[ATTR_HUB]
        neptunData[hub].close_all_valves()

    def set_config_attribute(service):
        """Sets Neptun config's attribute"""
        hub = service.data[ATTR_HUB]
        name = service.data[ATTR_NAME]
        value = service.data[ATTR_VALUE]
        neptunData[hub].set_config_attribute(name, value)

    # register function to gracefully stop Neptun
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_neptun)

    # Register services for Neptun
    hass.services.async_register(
        DOMAIN,
        SERVICE_OPEN_VALVE,
        open_valve,
        schema=service_one_valve_schema,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_OPEN_ALL_VALVES,
        open_all_valves,
        schema=service_all_valves_schema,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CLOSE_VALVE,
        close_valve,
        schema=service_one_valve_schema,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CLOSE_ALL_VALVES,
        close_all_valves,
        schema=service_all_valves_schema,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_CONFIG_ATTRIBUTE,
        set_config_attribute,
        schema=service_set_attr_schema,
    )
    _LOGGER.debug("<< The Neptun integration has been set up successfully.")
    return True


class NeptunHub:
    """Thread safe wrapper class for pymodbus with Neptun features."""

    def __init__(self, client_config):
        """Initialize the Neptun hub."""

        # generic configuration
        self._client = None
        self._in_error = False
        self._lock = threading.Lock()
        self._config_name = client_config[CONF_NAME]
        if CONF_CONNECTION in client_config:
            conn_config = client_config[CONF_CONNECTION]
            self._config_type = conn_config[CONF_TYPE]
            self._config_port = conn_config[CONF_PORT]
            self._config_timeout = conn_config[CONF_TIMEOUT]
            # self._config_delay = 0
            Defaults.Timeout = 10
            if self._config_type == "serial":
                # serial configuration
                self._config_method = "rtu"  # client_config[CONF_METHOD]
                self._config_baudrate = conn_config[CONF_BAUDRATE]
                self._config_stopbits = conn_config[CONF_STOPBITS]
                self._config_bytesize = conn_config[CONF_BYTESIZE]
                self._config_parity = conn_config[CONF_PARITY]
            else:
                # network configuration
                raise Exception("Only serial connection types are supported!")

    @property
    def name(self):
        """Return the name of this hub."""
        return self._config_name

    def _log_error(self, exception_error: ModbusException, error_state=True):
        log_text = "Neptun: " + str(exception_error)
        if self._in_error:
            _LOGGER.debug(log_text)
        else:
            _LOGGER.error(log_text)
            self._in_error = error_state

    def setup(self):
        """Set up pymodbus client."""
        try:
            if self._config_type == "serial":
                _LOGGER.info("*** Setting up the serial Modbus client...")
                self._client = ModbusClient(
                    method=self._config_method,
                    port=self._config_port,
                    baudrate=self._config_baudrate,
                    stopbits=self._config_stopbits,
                    bytesize=self._config_bytesize,
                    parity=self._config_parity,
                    timeout=self._config_timeout,
                    retry_on_empty=True,
                )
                _LOGGER.info("*** Serial Modbus client created.")
            # elif self._config_type == "rtuovertcp":
            #     self._client = ModbusTcpClient(
            #         host=self._config_host,
            #         port=self._config_port,
            #         framer=ModbusRtuFramer,
            #         timeout=self._config_timeout,
            #     )
            # elif self._config_type == "tcp":
            #     self._client = ModbusTcpClient(
            #         host=self._config_host,
            #         port=self._config_port,
            #         timeout=self._config_timeout,
            #     )
            # elif self._config_type == "udp":
            #     self._client = ModbusUdpClient(
            #         host=self._config_host,
            #         port=self._config_port,
            #         timeout=self._config_timeout,
            #     )
        except ModbusException as exception_error:
            self._log_error(exception_error, error_state=False)
            return

        # Connect device
        self.connect()
        _LOGGER.info("*** Serial Modbus client connected.")

    def close(self):
        """Disconnect client."""
        with self._lock:
            try:
                if self._client:
                    self._client.close()
                    self._client = None
            except ModbusException as exception_error:
                self._log_error(exception_error)
                return

    def connect(self):
        """Connect client."""
        with self._lock:
            try:
                self._client.connect()
            except ModbusException as exception_error:
                self._log_error(exception_error, error_state=False)
                return

    def open_valve(self, valve):
        result = self.read_holding_registers(REGISTER_STATUS)
        if result is ModbusException:
            _LOGGER.error(
                "open_valve: Cannot read holding registers: {}".format(result)
            )
        else:
            status = result.registers[0]
            if valve == 1:
                status = status | 1 << 8
            elif valve == 2:
                status = status | 1 << 9
            else:
                raise Exception("Unsupported valve number: {}".format(valve))
            self.write_register(REGISTER_STATUS, status)

    def open_all_valves(self):
        result = self.read_holding_registers(REGISTER_STATUS)
        if result is ModbusException:
            _LOGGER.error(
                "open_all_valves: Cannot read holding registers: {}".format(result)
            )
        else:
            status = result.registers[0]
            status = status | 0b11 << 8
            self.write_register(REGISTER_STATUS, status)

    def close_valve(self, valve):
        result = self.read_holding_registers(REGISTER_STATUS)
        if result is ModbusException:
            _LOGGER.error(
                "close_valve: Cannot read holding registers: {}".format(result)
            )
        else:
            status = result.registers[0]
            if valve == 1:
                status = status & bit_not(1 << 8)
            elif valve == 2:
                status = status & bit_not(1 << 9)
            else:
                raise Exception("Unsupported valve number: ${valve}")
            self.write_register(REGISTER_STATUS, status)

    def close_all_valves(self):
        result = self.read_holding_registers(REGISTER_STATUS)
        if result is ModbusException:
            _LOGGER.error(
                "close_all_valves: Cannot read holding registers: {}".format(result)
            )
        else:
            status = result.registers[0]
            status = status & bit_not(0b11 << 8)
            self.write_register(REGISTER_STATUS, status)

    def do_set_bool_attribute(self, status, value, mask) -> int:
        if value == True or (isinstance(value, str) and value.lower()) == "true":
            return status | mask
        else:
            return status & ~mask

    def set_config_attribute(self, attr_name, attr_value):
        """Sets config attribute"""
        result = self.read_holding_registers(REGISTER_STATUS)
        if result is ModbusException:
            _LOGGER.error(
                "close_all_valves: Cannot read holding registers: {}".format(result)
            )
        else:
            status = result.registers[0]
            if attr_name == ATTR_KEYBOARD_LOCKED:
                status = self.do_set_bool_attribute(
                    status, attr_value, MASK_KEYBOARD_LOCKED
                )
            elif attr_name == ATTR_PESSIMISTIC_WIRELESS_SENSOR:
                status = self.do_set_bool_attribute(
                    status, attr_value, MASK_PESSIMISTIC_WIRELESS_SENSOR
                )
            elif attr_name == ATTR_VALVE_TWO_GROUPS:
                status = self.do_set_bool_attribute(
                    status, attr_value, MASK_VALVE_TWO_GROUPS
                )
            elif attr_name == ATTR_WIRELESS_PAIRING:
                status = self.do_set_bool_attribute(
                    status, attr_value, MASK_WIRELESS_PAIRING
                )
            elif attr_name == ATTR_FLOOR_WASHING:
                status = self.do_set_bool_attribute(
                    status, attr_value, MASK_FLOOR_WASHING
                )
            self.write_register(REGISTER_STATUS, status)

    def read_holding_registers(self, address, count=1):
        """Read holding registers."""
        with self._lock:
            kwargs = {"unit": NEPTUN_UNIT}
            try:
                result = self._client.read_holding_registers(address, count, **kwargs)
            except ModbusException as exception_error:
                result = exception_error
            if not hasattr(result, "registers"):
                self._log_error(result)
                return None
            self._in_error = False
            return result

    def write_register(self, address, value) -> bool:
        """Write register."""
        with self._lock:
            kwargs = {"unit": NEPTUN_UNIT}
            try:
                result = self._client.write_register(address, value, **kwargs)
                _LOGGER.debug(
                    "*** WriteRegister result: {}, func code={}".format(
                        result, result.function_code
                    )
                )
            except ModbusException as exception_error:
                result = exception_error
            if not hasattr(result, "function_code") or result.function_code > 0x80:
                self._log_error(result)
                return False
            self._in_error = False
            return True

    # def write_registers(self, unit, address, values) -> bool:
    #     """Write registers."""
    #     with self._lock:
    #         kwargs = {"unit": unit} if unit else {}
    #         try:
    #             result = self._client.write_registers(address, values, **kwargs)
    #         except ModbusException as exception_error:
    #             result = exception_error
    #         if not hasattr(result, "registers"):
    #             self._log_error(result)
    #             return False
    #         self._in_error = False
    #         return True


class MqttClient:
    def __init__(self, client_config):
        return

    def setup(self):
        return
