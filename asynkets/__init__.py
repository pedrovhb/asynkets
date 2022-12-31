from __future__ import annotations

import asyncio
import time
from datetime import datetime

import math

from asyncio import Event, Future
from typing import (
    Literal,
    cast,
    SupportsFloat,
    Generator,
    Generic,
    TypeVar,
    Callable,
    overload,
    Type,
)

_T = TypeVar("_T")


if __name__ == "__main__":

    async def demo_pulse() -> None:
        pulse = Pulse()

        async def wait_pulse() -> None:
            print("Waiting for pulse")
            t = await pulse.wait()
            print("Pulse fired! Time:", t)
            t = await pulse.wait()
            print("Pulse fired! Time:", t)

        [asyncio.create_task(wait_pulse()) for _ in range(3)]
        pulse.fire()
        await asyncio.sleep(1)
        pulse.fire()
        await asyncio.sleep(1)
        pulse.fire()

    asyncio.run(demo_pulse())


__all__ = ("EventfulCounter", "Fuse", "SwitchEvent", "Pulse")
