from __future__ import annotations


class NoValueT:
    __slots__ = ()

    instance: NoValueT

    def __new__(cls) -> NoValueT:
        if not hasattr(cls, "instance"):
            cls.instance = super().__new__(cls)
        return cls.instance


NoValue = NoValueT()


__all__ = ("NoValue", "NoValueT")
