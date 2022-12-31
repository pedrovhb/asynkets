from __future__ import annotations

import asyncio
from asyncio import Future
from collections import deque
from datetime import timedelta
from typing import Generator, AsyncIterator


class _BasePulse:
    """A pulse that can be triggered and waited for.

    Waiting for a pulse will block until the pulse is triggered, and will return
    the time at which the pulse was triggered. Alternatively, the pulse can be given
    a function to call when it is triggered. In this case, the return value of waiting
    on the pulse will be the result of calling the function.
    """

    def __init__(self) -> None:
        self._waiters = deque()
        self._value: float | None = None
        self._loop = asyncio.get_event_loop()

    def wait(self) -> Future[float]:
        """Wait for the pulse to be fired.

        Returns a future that will be resolved when the pulse is fired.
        The future's result will be the time at which the pulse was fired, as per time.time().
        """
        fut = asyncio.get_event_loop().create_future()
        self._waiters.append(fut)
        return fut

    def __await__(self) -> Generator[None, None, float]:
        """Wait for the pulse to be fired.

        Returns the time at which the pulse was fired, as given by time.time().
        """
        return self.wait().__await__()

    async def _aiter(self) -> AsyncIterator[float]:
        while True:
            yield await self

    def __aiter__(self) -> AsyncIterator[float]:
        return self._aiter()

    def _fire(self) -> None:
        """Fire the pulse, waking up all waiters.

        The resulting future will be resolved with the event loop time.
        """
        self._value = self._loop.time()
        for fut in self._waiters:
            fut.set_result(self._value)
        self._waiters.clear()


class Pulse(_BasePulse):
    fire = _BasePulse._fire


class TimePulse(_BasePulse):
    def __init__(self, period: float | timedelta) -> None:
        super().__init__()
        self._period = period if isinstance(period, float) else period.total_seconds()
        self._start_time = self._loop.time()
        self._ticks = 0
        self._loop.call_at(self._start_time + self._period, self._tick)

    def _tick(self) -> None:
        self._fire()
        self._ticks += 1
        self._loop.call_at(self._start_time + self._period * self._ticks, self._tick)


if __name__ == "__main__":
    # todo - add_callback
    import time

    async def main() -> None:
        pulse = Pulse()

        async def show_pulses() -> None:
            async for t in pulse:
                print(f"pulse1 fired at {t}")
            print("pulse1 finished")

        for _ in range(3):
            asyncio.create_task(show_pulses())

        pulse.fire()
        await asyncio.sleep(0.1)
        pulse.fire()
        await asyncio.sleep(0.1)
        pulse.fire()
        await asyncio.sleep(0.3)
        pulse.fire()
        await asyncio.sleep(0.3)
        print("pulse1 finished")

        time_pulse = TimePulse(0.25)

        async def show_time_pulses() -> None:
            async for t in time_pulse:
                print(f"time_pulse fired at {t}")
            print("time_pulse finished")

        for _ in range(3):
            asyncio.create_task(show_time_pulses())

        await asyncio.sleep(5)

        print("awaiting once", time.time())
        await time_pulse
        print("awaiting twice", time.time())
        await time_pulse
        print("awaiting thrice", time.time())
        await time_pulse
        print("awaiting finished", time.time())

    asyncio.run(main())
