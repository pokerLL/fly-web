from collections import UserDict

from fly.utils import ConfigDict


class FlyConfig(UserDict):
    def __init__(self, _dict):
        content = _dict
        self.data = self._parse_dat(content)

    def _parse_dat(self, raw_dict: dict[str, dict]):
        """
        raw_dict like:
            {
                "fly":{
                    "xxx":"xxx"
                    ...
                },
                "mysql":{
                },
                "redis":{
                }
            }
        will be parsed like:
            {
                "xxx":"xxx",
                ...
                "boot":{
                    "mysql":{
                    },
                    "redis":{
                    }
                }
            }
        """
        config = ConfigDict()
        for key, value in raw_dict.items():
            key = key.lower()
            if isinstance(value, dict):
                if key == "fly":
                    config.update(value)
                else:
                    config["boot"][key] = value
            else:
                raise TypeError(f"config value must be a dict, but got {type(value)}")
        return config
