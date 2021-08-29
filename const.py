"""Constants used in Neptun integration."""

# configuration names
CONF_HUB = "hub"
CONF_HUBS = "hubs"
CONF_MQTT = "mqtt"
CONF_CONNECTION = "connection"
CONF_BAUDRATE = "baudrate"
CONF_BYTESIZE = "bytesize"
CONF_PARITY = "parity"
CONF_STOPBITS = "stopbits"
CONF_USER = "user"
CONF_PASSWORD = "password"
CONF_VALVES = "valves"
CONF_BINARY_SENSOR = "binary_sensor"
CONF_SWITCH = "switch"
CONF_INPUTS = ""
CONF_WRITE_TYPE = ""
CONF_COMMAND_MASK = "mask"

# service call attributes
ATTR_HUB = "hub"
ATTR_VALVE = "valve"
ATTR_VALUE = "value"

# data types

# call types
CALL_TYPE_COIL = "coil"

# service calls
SERVICE_OPEN_VALVE = "open_valve"
SERVICE_CLOSE_VALVE = "close_valve"
SERVICE_OPEN_ALL_VALVES = "open_all_valves"
SERVICE_CLOSE_ALL_VALVES = "close_all_valves"
SERVICE_SET_CONFIG_ATTRIBUTE = "set_config_attribute"

# integration names
NEPTUN_DOMAIN = "neptun"

# data item names
DATA_MQTT_CLIENT = "_neptun_mqtt_"

# module registers
REGISTER_STATUS = 0
NEPTUN_UNIT = 240

# hub sensor attributes
ATTR_KEYBOARD_LOCKED = "keyboard_locked"
MASK_KEYBOARD_LOCKED = 0b1000000000000
ATTR_PESSIMISTIC_WIRELESS_SENSOR = "pessimistic_wireless_sensor"
MASK_PESSIMISTIC_WIRELESS_SENSOR = 0b0100000000000
ATTR_VALVE_TWO_GROUPS = "two_valve_groups"
MASK_VALVE_TWO_GROUPS = 0b0010000000000
ATTR_WIRELESS_PAIRING = "wireless_pairing"
MASK_WIRELESS_PAIRING = 0b0000010000000
ATTR_FLOOR_WASHING = "floor_washing"
MASK_FLOOR_WASHING = 0b0000000000001
