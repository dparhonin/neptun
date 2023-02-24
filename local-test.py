import unittest
import yaml

from const import ATTR_VALVE_TWO_GROUPS
from neptun import NeptunHub


class MyTestCase(unittest.TestCase):
    def test_something(self):
        with open("local-test-config.yaml") as stream:
            try:
                hub_conf = yaml.safe_load(stream)
                hub = NeptunHub(hub_conf)
                hub.setup()
                hub.set_config_attribute(ATTR_VALVE_TWO_GROUPS, True)
                # hub.open_valve(1)
                hub.close_valve(2)
                # hub.close_all_valves()
                # hub.open_all_valves()
            except yaml.YAMLError as exc:
                print(exc)


if __name__ == '__main__':
    unittest.main()
