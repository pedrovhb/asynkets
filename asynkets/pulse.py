from __future__ import annotations

import time
import asyncio
from asyncio import Future
from collections import deque
from datetime import timedelta
from functools import partial
from typing import AsyncIterator, Callable, cast, Coroutine, Generator

try:
    from typing import ParamSpec
except ImportError:
    from typing_extensions import ParamSpec

from .fuse import Fuse

_P = ParamSpec("_P")


class PulseClosed(Exception):
    """Raised when a pulse is closed."""


class _BasePulse:
    def __init__(self) -> None:
        self._waiters: deque[Future[float]] = deque()
        self._value: float | None = None
        self._loop = asyncio.get_event_loop()
        self._closed = Fuse()
        self._pulse_callbacks: list[Callable[[float], object] | Callable[[], object]] = []

    def add_pulse_callback(
        self,
        callback: Callable[_P, object],
        thread_safe: bool = False,
        *__args: _P.args,
        **__kwargs: _P.kwargs,
    ) -> None:
        """Add a callback to be called when the pulse is fired.

        If it is a coroutine, it will be scheduled as a task; otherwise, it will be scheduled
        via the event loop's call_soon method if thread_safe is False, or via call_soon_threadsafe
        if thread_safe is True.
        """

        if asyncio.iscoroutinefunction(callback):
            _fn = cast(Callable[_P, Coroutine[object, object, object]], callback)

            def _cb() -> None:
                _ = asyncio.create_task(_fn(*__args, **__kwargs))

        elif thread_safe:

            def _cb() -> None:
                self._loop.call_soon_threadsafe(partial(callback, *__args, **__kwargs))

        else:

            def _cb() -> None:
                self._loop.call_soon(partial(callback, *__args, **__kwargs))

        self._pulse_callbacks.append(_cb)

    def _run_callbacks(self) -> None:
        for cb in self._pulse_callbacks:
            self._loop.call_soon(cb)

    @property
    def is_closed(self) -> bool:
        """Return True if the pulse is closed."""
        return self._closed.is_set()

    def close(self) -> None:
        """Close the pulse, waking up all waiters.

        The resulting future will have a PulseClosed exception set as its exception.
        """
        self._closed.set()
        for fut in self._waiters:
            fut.set_exception(PulseClosed())

    async def wait_closed(self) -> None:
        """Wait for the pulse to be closed."""
        await self._closed.wait()

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
            try:
                yield await self
            except PulseClosed:
                break

    def __aiter__(self) -> AsyncIterator[float]:
        return self._aiter()

    def _fire(self) -> None:
        """Fire the pulse, waking up all waiters.

        The resulting future will be resolved with the current time.
        """
        if self._closed.is_set():
            raise RuntimeError("Cannot fire a closed pulse")

        self._value = time.time()
        for fut in self._waiters:
            fut.set_result(self._value)
        self._waiters.clear()

        self._run_callbacks()


class Pulse(_BasePulse):
    """A pulse that can be triggered and waited for.

    Waiting for a pulse will block until the pulse is triggered, and will return
    the time at which the pulse was triggered. Alternatively, the pulse can be given
    a function to call when it is triggered. In this case, the return value of waiting
    on the pulse will be the result of calling the function.

    The pulse can be closed, which will cause all waiters to be woken up with a
    PulseClosed exception. After the pulse is closed, it cannot be fired again.

    The pulse can be used as an async iterator, which will yield the time at which
    the pulse is fired. The iterator will stop yielding when the pulse is closed.

    Examples:
        >>> pulse = Pulse()
        >>> pulse.fire()
        >>> await pulse
        123.456

        >>> pulse = Pulse()
        >>> pulse.add_pulse_callback(lambda: print("Pulse fired!"))
        >>> pulse.fire()
        Pulse fired!

        >>> pulse = Pulse()
        >>> async def pulse_subscriber(pulse: Pulse) -> None:
        ...     async for t in pulse:
        ...         print(t)
        >>> asyncio.create_task(pulse_subscriber(pulse))
        >>> pulse.fire()
        123.456
        >>> pulse.fire()
        123.457
        >>> pulse.close()
        >>> pulse.fire()
        Traceback (most recent call last):
        ...
        RuntimeError: Cannot fire a closed pulse
    """

    fire = _BasePulse._fire


class PeriodicPulse(_BasePulse):
    """A pulse that fires periodically.

    The pulse will fire every `interval` seconds, and will wait for `delay` seconds
    before the first pulse is fired. This can be used to implement a periodic task,
    and is different from asyncio's `loop.call_later` or `while True: await asyncio.sleep(x)`
    in that it will not drift over time.

    The pulse can be closed, which will cause all waiters to be woken up with a
    PulseClosed exception. After the pulse is closed, it does not fire again.

    The pulse can be used as an async iterator, which will yield the time at which
    the pulse is fired. The iterator will stop yielding when the pulse is closed.

    Examples:
        >>> pulse = PeriodicPulse(1.0)
        >>> async for t in pulse:
        ...     print(t)
        123.456
        124.456
        125.456

        >>> pulse = PeriodicPulse(period=timedelta(minutes=5), start_delay=0.5)
        >>> pulse.add_pulse_callback(lambda: print(f"Pulse fired! {time.time()}"))
        >>> await asyncio.sleep(60 * 15)
        Pulse fired! 12:00:00
        Pulse fired! 12:05:00
        Pulse fired! 12:10:00
    """

    def __init__(
        self,
        period: float | timedelta,
        start_delay: float | timedelta | None = None,
    ) -> None:
        """Create a periodic pulse.

        Args:
            period: The period of the pulse, in seconds or a timedelta.
            start_delay: The delay before the first pulse is fired. If None, the first pulse
                will be fired after `period` seconds. To fire the first pulse immediately,
                pass 0.
        """
        super().__init__()
        self._period = period.total_seconds() if isinstance(period, timedelta) else period

        self._ticks = 0

        if start_delay is None:
            self._start_delay = self._period
        elif isinstance(start_delay, timedelta):
            self._start_delay = start_delay.total_seconds()
        else:
            self._start_delay = start_delay

        self._start_time = self._loop.time()
        self._next_tick_handle = self._loop.call_at(
            self._start_time + self._start_delay,
            self._tick,
        )
        self._target_period: float | None = None

    def _tick(self) -> None:
        if self._closed.is_set():
            return

        self._fire()

        if self._target_period is not None:
            self._period = self._target_period
            self._target_period = None
            self._ticks = 0
            self._start_time = self._loop.time()
            self._start_delay = 0

        self._ticks += 1
        self._next_tick_handle = self._loop.call_at(
            when=self._start_time + self._period * self._ticks + self._start_delay,
            callback=self._tick,
        )

    @property
    def period(self) -> timedelta:
        """The period of the pulse."""
        return timedelta(seconds=self._period)

    @period.setter
    def period(self, period: float | timedelta) -> None:
        self._target_period = period if isinstance(period, float) else period.total_seconds()


if __name__ == "__main__":
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
        pulse.close()

        time_pulse = PeriodicPulse(0.25)

        async def show_time_pulses() -> None:
            # async for t in time_pulse:
            # print(f"time_pulse fired at {t}")
            t = await time_pulse
            print(f"time_pulse fired at {t}")
            print("time_pulse finished")

        for _ in range(3):
            asyncio.create_task(show_time_pulses())

        await asyncio.sleep(3)

        print("awaiting once", time.time())
        await time_pulse
        print("awaiting twice", time.time())
        await time_pulse
        print("awaiting thrice", time.time())
        await time_pulse
        print("awaiting finished", time.time())
        time_pulse.close()

        async def main_test_set_period() -> None:
            t = time.time()
            start_delay = 1 - divmod(t, 1)[1]  # start at the next second, for round numbers
            # await asyncio.sleep(start_delay)
            pulse = PeriodicPulse(0.1, start_delay=start_delay)
            start_time = time.time()
            print(f"start_time: {start_time}; period: {pulse.period}")
            pulse.add_pulse_callback(
                lambda: print(f"pulse fired at t+{time.time()-start_time:3.5f}")
            )
            await asyncio.sleep(1.3)
            print("setting period to 0.5")
            pulse.period = timedelta(seconds=0.5)
            await asyncio.sleep(5)
            pulse.close()

        await main_test_set_period()

    asyncio.run(main())


__all__ = ("PeriodicPulse", "Pulse", "PulseClosed")
