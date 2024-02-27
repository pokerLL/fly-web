from collections import defaultdict


class LowerKeyDefaultDict(defaultdict):
    def __getitem__(self, key):
        key = key.lower() if isinstance(key, str) else key
        return super().__getitem__(key)

    def __setitem__(self, key, value):
        key = key.lower() if isinstance(key, str) else key
        return super().__setitem__(key, value)


def ConfigDict():
    return LowerKeyDefaultDict(lambda: LowerKeyDefaultDict(lambda: None))


"""
cc = ConfigDict()
cc["abC"] = 1
print(cc)
cc["abC"] = 2
cc[1][2] = 3
cc[1][3] = 4
cc["A"]["b"] = 5
"""
